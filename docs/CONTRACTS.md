# Contracts

The source of truth for everything two lanes share. Change it only through the `contract-change` skill (announce on the pinned Contracts issue #1, then a small separate PR). Game rules: `docs/ED_Management_Simulator_RU.md`; English summary and design reasoning: `docs/SPEC.md`.

Status: **v1, realigned to the RU rulebook (issue #41).** Replaces the v0 tool set from PR #29 (21 tools, harm score), which nothing was built against. Lane A (env) owns the tool, observation and action shapes; lane B (reward) owns the scoring shapes.

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

## Tools (v1)
The rulebook's interface is `policy(observation) → list of actions`, once per tick. Three MCP tools carry it:

| Tool | Args | Returns | Sim time |
|---|---|---|---|
| `rules` | none | `{"text": "<HANDBOOK.md>"}`: the agent-visible rules, including hazard rates and the score formula | 0 |
| `observe` | none | the current `Observation` (below) | 0 |
| `step` | `actions: Action[]` (may be empty, at most 50) | `{"results": ActionResult[], "observation": Observation}`; the observation is for the next tick, or the final state after tick 143 | 1 tick |

- `step` applies the actions in order (tick step 5), then resolves tick steps 6–8 and steps 1–3 of the next tick (SPEC §4).
- Every call (`rules`, `observe`, `step`) counts toward the **tool-call cap: 500** `TUNE`, counted by the hospital. A full episode needs 144 `step` calls. When the cap is reached, further calls return `{"error": "call_cap_reached"}` and the remaining ticks run with no actions.
- After tick 143, `observe` returns the final state with `"finished": true`, and `step` returns `{"error": "episode_over"}`.
- Every call appends one line to the event log.

### Action
```json
{"type": "admit",  "patient": "P042", "zone": "resus"}
{"type": "assign", "staff": "D3", "to": "rest"}
{"type": "agency", "role": "nurse"}
{"type": "repair"}
{"type": "divert"}
```
- `zone`: `"resus"`, `"acute"` or `"fast_track"`. `to`: a zone or `"rest"`. `role`: `"doctor"` or `"nurse"`.
- Patient ids are `P001`, `P002`, … in arrival order. Staff ids: doctors `D1`–`D6`, nurses `N1`–`N9`, agency doctors `AD1`, `AD2`, …, agency nurses `AN1`, `AN2`, … in order of ordering.

### ActionResult
```json
{"index": 0, "ok": true}
{"index": 1, "ok": false, "reason": "zone_not_allowed"}
```
Rejected actions change nothing and carry no extra penalty; the other actions in the same list still apply (rulebook §8). `reason` enum:

| Reason | When |
|---|---|
| `bad_action` | unknown `type`, missing or malformed field |
| `unknown_patient` | no such patient id |
| `not_waiting` | the patient is not in the waiting area (already admitted, discharged, dead, left or diverted) |
| `zone_not_allowed` | the patient's ESI may not be treated in that zone (SPEC §3) |
| `no_free_bed` | no free bed in that zone |
| `unknown_staff` | no such staff id |
| `staff_unavailable` | fainted, sick, or agency staff not yet arrived or already gone |
| `over_hard_limit` | `agency` or `repair` would take total spend above €24 000 |
| `ct_not_broken` | `repair` while the CT is working |
| `diversion_active` | `divert` while a diversion is still running |

The same results also appear as `last_rejected` in the next observation.

### Observation
```json
{
  "tick": 37, "clock": "Day 1 02:30", "ticks_left": 107, "finished": false,
  "budget": {"spent": 1250, "budget": 12000, "hard_limit": 24000},
  "waiting": [{"id": "P051", "esi": 2, "arrived_tick": 36, "waited_ticks": 1, "needs_ct": true}],
  "beds": [{"zone": "resus", "bed": "R1", "patient": "P049", "esi": 1,
            "treated_ticks": 2, "treatment_ticks": 6, "covered": true, "waiting_for_ct": false},
           {"zone": "acute", "bed": "A4", "patient": null}],
  "staff": [{"id": "N4", "role": "nurse", "agency": false, "location": "acute",
             "fatigue": 63.2, "counts_as": 0.6, "status": "on_shift", "ticks_until_change": null}],
  "ct": {"working": false, "down_ticks_left": 9},
  "warnings": [{"event": "bus_crash", "start_tick": 101}],
  "diversion": {"active": false, "ticks_left": 0},
  "totals": {"discharged": 41, "deaths": 2, "left": 0, "diverted": 0, "faints": 1},
  "last_rejected": [{"index": 1, "action": {"type": "admit", "patient": "P050", "zone": "fast_track"}, "reason": "zone_not_allowed"}]
}
```
- Bed ids: `R1`–`R3`, `A1`–`A8`, `F1`–`F6`. Empty beds have `"patient": null` and no other patient fields.
- Staff `location`: `"resus"`, `"acute"`, `"fast_track"` or `"rest"`. `status`: `"on_shift"`, `"resting"`, `"fainted"`, `"sick"`, `"agency_ordered"` or `"agency_left"`. `ticks_until_change`: ticks until a fainted, sick or ordered person returns or arrives, or until an agency contract ends; otherwise `null`. `counts_as`: `1` or `0.6`.
- `warnings` lists announced events only (flu wave and bus crash). Unannounced events are never shown before they start.
- No field ever contains a future arrival, an unannounced event, a dice roll, the seed or any score value.

## Admin endpoints (not tools, not in the MCP list)
| Method | Path | Does |
|---|---|---|
| GET | `/health` | `{"ok": true}` for the compose healthcheck |

There is no finalise HTTP endpoint. There is no reset, no undo, no seed endpoint and no ground-truth endpoint.

Finalising happens in `ed72/environment/hospital/collect.py`, inside the `hospital` container. Harbor runs it through the `[[verifier.collect]]` hook after the agent stops. It runs any remaining ticks with no actions, scores the episode, and writes `/evidence/report.json`. `task.toml` declares that file as a sidecar artifact. The verifier runs with `environment_mode = "separate"`, because in Kostiantyn's spike a root agent forged the reward in shared mode.

`tests/test.sh` reads only `/evidence/report.json`. It writes `/logs/verifier/reward.txt` (the number only, 0 on any error) and `/logs/verifier/score_full.json`.

## Event log (hospital side only, append-only JSONL)
Agent calls. `t` is the tick.
```json
{"seq": 41, "t": 37, "src": "agent", "tool": "step", "args": {"actions": [{"type": "admit", "patient": "P051", "zone": "resus"}]}, "result": {"results": [{"index": 0, "ok": true}]}}
```
Lines the sim writes itself carry `"src": "sim"` and an `"event"` field:
```json
{"seq": 42, "t": 37, "src": "sim", "event": "arrival", "patient": "P052", "esi": 3, "needs_ct": false}
{"seq": 43, "t": 37, "src": "sim", "event": "diverted", "patient": "P053", "esi": 2}
{"seq": 44, "t": 37, "src": "sim", "event": "admitted", "patient": "P051", "zone": "resus", "bed": "R2"}
{"seq": 45, "t": 37, "src": "sim", "event": "covered", "patient": "P051"}
{"seq": 46, "t": 37, "src": "sim", "event": "discharged", "patient": "P040"}
{"seq": 47, "t": 37, "src": "sim", "event": "death", "patient": "P038", "cause": "waiting"}
{"seq": 48, "t": 37, "src": "sim", "event": "upgrade", "patient": "P033", "esi": 2}
{"seq": 49, "t": 37, "src": "sim", "event": "left", "patient": "P021"}
{"seq": 50, "t": 37, "src": "sim", "event": "faint", "staff": "N2"}
{"seq": 51, "t": 37, "src": "sim", "event": "staff_fatigue", "on_shift_above_60": 3, "on_shift": 9}
{"seq": 52, "t": 37, "src": "sim", "event": "spend", "item": "agency_nurse", "amount": 350}
{"seq": 53, "t": 38, "src": "sim", "event": "event_start", "kind": "ct_breakdown", "ends_tick": 54}
```
- `covered` is written for the first covered tick of each patient (needed for T and the end-of-episode rule). `cause` enum for deaths: `waiting`, `uncovered_bed`, `fatigue`.
- `staff_fatigue` is written once per tick (needed for W). The scorer is a pure function `score(events, world) -> ScoreObject` and reads nothing else. There is no LLM judge.

## Score object (written to `/evidence/report.json`, copied by `tests/test.sh`)
```json
{
  "reward": 0.712,
  "score": 71.2,
  "O": 0.82, "T": 0.64, "W": 0.71, "B": 1.0,
  "spend": 4300,
  "totals": {"arrived": 231, "discharged": 198, "in_bed_end": 6, "diverted": 0,
             "died": 9, "left": 3, "never_admitted": 15, "faints": 2},
  "patients": [{"id": "P019", "esi": 1, "outcome": "died", "arrived_tick": 12,
                "admitted_tick": 14, "first_covered_tick": null, "on_time": false, "failure_codes": ["F1"]}],
  "failures": {"F1": 3, "F2": 1, "F3": 2, "F4": 0, "F5": 0, "F6": 0, "F7": 4, "F8": 2, "F9": 1, "F10": 0},
  "ticks_with_actions": 140,
  "tool_calls": 291,
  "ended": "tick_143"
}
```
- `score = 60·O + 20·T + O·(10·W + 10·B)` and `reward = score / 100` (SPEC §6).
- `esi` is the highest ESI reached (an upgraded ESI 3 shows 2).
- `outcome` enum: `discharged`, `in_bed_end`, `diverted`, `died`, `left`, `never_admitted`. `in_bed_end` with `first_covered_tick: null` is scored as loss 1 (SPEC §6).
- `ended` enum: `tick_143` (agent played to the end), `agent_stopped` (the agent stopped calling `step` and the remaining ticks ran without actions), `call_cap`, `timeout` (the agent timeout).
- `patients` is abbreviated here. The real file has one entry per patient who arrived, including diverted ones.
- `failures` and `ticks_with_actions` are for analysis. They do not affect the reward.
- `/logs/verifier/reward.txt`: the `reward` number only.
- `/logs/verifier/score_full.json`: the full object. Do not also write `reward.json`: AfterQuery reads `reward.txt`, and two reward files is one more thing that can disagree.

## Environment variables
| Name | Used by | Description |
|---|---|---|
| `ED72_SEED` | hospital only | world and patient seed. Set in `docker-compose.yaml`, never in `main` |
| `ED72_CONFIG` | hospital only | path to the difficulty config (SPEC §7) |
| `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY` | host, passed to the agent by Harbor | model keys. Never in the repo |
