# Contracts

The source of truth for everything two lanes share. Change it only through the `contract-change` skill (announce on the pinned Contracts issue #1, then a small separate PR). Design reasoning is in `docs/SPEC.md`.

Status: **v0 for ED-72, replaces the Custodian contracts.** Announced on issue #1. Lane A (env) owns the tool shapes and lane B (reward) owns the scoring shapes.

## Who owns which folder
| Path | Lane | Others may |
|---|---|---|
| `ed72/environment/hospital/` (sim, tools, server) | A env | read |
| `ed72/environment/workspace/HANDBOOK.md`, `ed72/instruction.md` | A env | propose via PR |
| `ed72/environment/hospital/ed72_sim/scoring/`, `ed72/tests/` | B reward | read |
| `ed72/environment/hospital/collect.py` | B reward | read |
| `docs/REDTEAM.md` | B reward | append findings |
| `ed72/solution/` | C reference | read |
| `analysis/`, `docs/FINDINGS.md`, results in `eval/` | C reference | read |
| Dockerfiles, `docker-compose.yaml`, `ed72/task.toml` | D harness | read |
| `eval/` (runner), `training/` | D harness | read |
| `README.md`, `Makefile`, `.github/` | D harness | propose via PR |

## Services and ports
| Service | Where | URL inside the compose network |
|---|---|---|
| `main` | agent container (Harbor's name). Holds `HANDBOOK.md` and the `ward` CLI only | n/a |
| `hospital` | sidecar. Owns all state, the sim, the seed and the scorer | `http://hospital:8000` |

- MCP endpoint: `http://hospital:8000/mcp` (streamable-http), declared in `task.toml` under `[[environment.mcp_servers]]`.
- Fallback: `ward <tool> --json '<args>'` CLI in `main`, a thin client for the same tools. Both paths call the same functions.

## Tools (v0)
All return compact JSON. 21 tools: 8 read, 13 act. The clock moves only on `advance`.

| Tool | Args | Returns | Sim cost |
|---|---|---|---|
| `board` | none | beds with occupant, waiting list (`patient_id, label, waited_min`), ambulances free | 0 |
| `patient` | `patient_id` | label, last assessed acuity and when, health band as last observed, assigned staff, orders | 0 |
| `roster` | none | staff with role, skill, on shift or not, fatigue, current load; on-call pool | 0 |
| `equipment` | none | monitors, ventilators, CT: status and who is using them | 0 |
| `budget` | none | remaining, spent so far by category, price list | 0 |
| `notices` | none | notices issued so far (surge forecasts, maintenance warnings) | 0 |
| `handbook` | `section?` | handbook text | 0 |
| `clock` | none | `now_min, hour, minutes_left, calls_left` | 0 |
| `assess` | `patient_id, nurse_id` | true acuity and health now | 0, but occupies the nurse 10 min |
| `admit` | `patient_id, bed_id` | `ok` | 0 |
| `assign` | `staff_id, patient_id` | `ok` | 0 |
| `order_test` | `patient_id, test: "ct"\|"lab"` | `ok`, result time | 0 |
| `discharge` | `patient_id` | `ok`, optional `warning` | 0 |
| `transfer` | `patient_id` | `ok`. Uses an ambulance, 90-minute drive, costs budget | 0 |
| `set_diversion` | `on: bool` | `ok` | 0 |
| `call_in` | `staff_id` | `ok`, arrival time. Costs budget | 0 |
| `extend_shift` | `staff_id, hours` | `ok`. Overtime, costs budget | 0 |
| `send_on_break` | `staff_id, minutes` | `ok` | 0, but the person is away for `minutes` |
| `repair` | `equipment_id, tier: "standard"\|"emergency"` | `ok`, ready time. Costs budget | 0 |
| `advance` | `minutes` (15 to 120) | digest: arrivals, completions, events, `stopped_early_reason` | up to `minutes` |
| `end_shift` | none | `ok`. Ends the episode; the remaining time is fast-forwarded with no new actions | 0 |

- Read tools cost no sim time. Every call, read or act, counts toward the 600-call cap, counted by the hospital.
- `advance` returns early when a label 1 or 2 patient arrives or an event fires, and says why in `stopped_early_reason`.
- No tool ever returns the true acuity of an unassessed patient.
- Every call appends one line to the event log.

## Errors
Failed calls return `{"error": "<code>"}`. They change nothing, but they still count toward the call cap.

`error` enum: `unknown_id`, `bad_args`, `bed_occupied`, `staff_unavailable`, `skill_mismatch`, `equipment_unavailable`, `budget_exhausted`, `no_ambulance`, `call_cap_reached`, `episode_over`.

`discharge_criteria_not_met_warning` is not an error. The discharge goes through and the result is `{"ok": true, "warning": "discharge_criteria_not_met_warning"}`. The handbook lists the criteria.

## Admin endpoints (not tools, not in the MCP list)
| Method | Path | Does |
|---|---|---|
| GET | `/health` | `{"ok": true}` for the compose healthcheck |

There is no finalise HTTP endpoint. There is no reset, no undo, no seed endpoint and no ground-truth endpoint.

Finalising happens in `ed72/environment/hospital/collect.py`, inside the `hospital` container. Harbor runs it through the `[[verifier.collect]]` hook. It ends the episode if it is still open, fast-forwards the remaining time, runs the 12-hour handover tail, replays the anchors and the floor, scores, and writes `/evidence/report.json`. `task.toml` declares that file as a sidecar artifact. The verifier runs with `environment_mode = "separate"`, because in Kostiantyn's spike a root agent forged the reward in shared mode.

`tests/test.sh` reads only `/evidence/report.json`. It writes `/logs/verifier/reward.txt` (the number only, 0 on any error) and `/logs/verifier/score_full.json`.

## Event log (hospital side only, append-only JSONL)
Agent action. `t` is sim minutes.
```json
{"seq": 41, "t": 185, "src": "agent", "tool": "admit", "args": {"patient_id": "P-0031", "bed_id": "R2"}, "result": {"ok": true}}
```
Lines the sim writes itself carry `"src": "sim"` and an `"event"` field:
```json
{"seq": 42, "t": 190, "src": "sim", "event": "arrival", "patient_id": "P-0032", "label": 3}
{"seq": 57, "t": 245, "src": "sim", "event": "deterioration", "patient_id": "P-0027", "health": 41}
{"seq": 88, "t": 410, "src": "sim", "event": "death", "patient_id": "P-0019"}
{"seq": 93, "t": 460, "src": "sim", "event": "staff_sick", "staff_id": "N-07", "hours": 24}
{"seq": 101, "t": 515, "src": "sim", "event": "equipment_down", "equipment_id": "CT-1"}
```
The scorer is a pure function `score(events, world) -> ScoreObject`. It reads nothing else. There is no LLM judge.

## Score object (written to `/evidence/report.json`, copied by `tests/test.sh`)
```json
{
  "reward": 0.64,
  "H": 520.0, "H_anchor": 1210.0, "H_floor": 140.0,
  "anchors": {"do_nothing": 1840.0, "fcfs_label": 1210.0, "discharge_all": 1650.0, "transfer_all": 1500.0,
              "divert_all": 1720.0, "call_in_all": 1330.0, "random": 1580.0},
  "modules": {"M1": 300.0, "M2": 120.0, "M3": 70.0, "M4": 30.0},
  "patients": [{"id": "P-0019", "outcome": "died", "harm": 100.0, "failure_codes": ["F1", "F2"]}],
  "failures": {"F1": 9, "F2": 6, "F3": 1, "F4": 0, "F5": 3, "F6": 1, "F7": 2, "F8": 2, "F9": 1, "F10": 0},
  "tool_calls": 412,
  "ended": "end_shift"
}
```
- `reward = clip((H_anchor - H) / (H_anchor - H_floor), 0, 1)`. In the example: (1210 - 520) / (1210 - 140) = 0.64.
- `H_anchor` is the lowest value in `anchors`. `H` is the sum of the four `modules`.
- `outcome` enum: `discharged`, `admitted_ok`, `transferred`, `diverted`, `left_unseen`, `harmed`, `died`, `in_department`.
- `ended` enum: `end_shift`, `hour_72`, `call_cap`, `timeout` (the 1800 s agent timeout).
- `patients` is abbreviated here. The real file has one entry per patient who arrived.
- `modules` and `failures` are for analysis. They do not affect the reward.
- `/logs/verifier/reward.txt`: the `reward` number only.
- `/logs/verifier/score_full.json`: the full object. Do not also write `reward.json`: AfterQuery reads `reward.txt`, and two reward files is one more thing that can disagree.

## Environment variables
| Name | Used by | Description |
|---|---|---|
| `ED72_SEED` | hospital only | world and patient seed. Set in `docker-compose.yaml`, never in `main` |
| `ED72_CONFIG` | hospital only | path to the difficulty config |
| `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY` | host, passed to the agent by Harbor | model keys. Never in the repo |
