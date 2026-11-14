# Contracts

The source of truth for everything two lanes share. Change it only through the `contract-change` skill (announce on the pinned Contracts issue #1, then a small separate PR). Design reasoning is in `docs/SPEC.md`.

Status: **v0, to be frozen at kickoff.** After that, lane A (env) owns the tool shapes and lane B (reward) owns the scoring shapes.

## Who owns which folder
| Path | Lane | Others may |
|---|---|---|
| `custodian/environment/registry/` (world gen, sim, tools, server) | A env | read |
| `custodian/environment/Dockerfile`, `docker-compose.yaml`, `custodian/task.toml` | D harness | read |
| `custodian/environment/workspace/HANDBOOK.md`, `custodian/instruction.md` | A env | propose via PR |
| `custodian/environment/registry/scoring/`, `custodian/tests/` | B reward | read |
| `custodian/solution/` | C reference | read |
| `eval/` | D harness (runner), C reference (results) | read |
| `analysis/`, `docs/FINDINGS.md` | C reference | read |
| `docs/REDTEAM.md` | B reward | append findings |
| `training/` | D harness | read |
| `README.md`, `Makefile`, `.github/` | D harness | propose via PR |

## Services and ports
| Service | Where | URL inside the compose network |
|---|---|---|
| `main` | agent container (Harbor's name) | n/a |
| `registry` | sidecar, owns all state | `http://registry:8000` |

- MCP endpoint: `http://registry:8000/mcp` (streamable-http), declared in `task.toml` under `[[environment.mcp_servers]]`.
- Fallback: `desk <tool> --json '<args>'` CLI in `main`, a thin HTTP client for the same tools. Both paths call the same functions.

## Tools (v0)
All return JSON. Every call appends one line to the event log and advances the clock by its cost.

| Tool | Args | Returns | Cost (min) |
|---|---|---|---|
| `inbox` | none | open tickets: `id, deadline, requester_id, summary` | 1 |
| `ticket` | `ticket_id` | full text, claimed role, requested items, `doc_ids` | 1 |
| `policy` | `section?` | handbook text | 1 |
| `policy_changes` | none | official notices issued so far this shift | 1 |
| `verify_requester` | `requester_id, method: "lookup"\|"callback"` | verified role, org, relationship to a subject, or `failed` | 2 / 6 |
| `verify_document` | `doc_id` | `valid\|expired\|forged`, scope | 3 |
| `consent` | `subject_id, purpose` | current status + history | 1 |
| `record` | `subject_id, fields[]` | values of exactly those fields | 1 |
| `release_log` | `requester_id?` or `subject_id?` | everything released so far | 1 |
| `release` | `ticket_id, subject_id, fields[]` | closes the ticket | 1 |
| `export` | `ticket_id, columns[], generalise{col: level}, min_group_size` | closes the ticket | 2 |
| `deny` | `ticket_id, reason_code` | closes the ticket | 1 |
| `escalate` | `ticket_id, reason_code` | closes the ticket | 1 |
| `clock` | none | `now, minutes_left` | 0 |
| `end_shift` | none | finalises the episode | 0 |

`reason_code` enum: `unverified`, `no_consent`, `out_of_scope`, `invalid_document`, `aggregation_risk`, `policy_change`, `needs_dpo`.

Errors: unknown ids, closed tickets and malformed args return `{"error": "<code>"}` and change nothing except the clock.

## Admin endpoints (not tools, not in the MCP list)
| Method | Path | Does |
|---|---|---|
| GET | `/health` | `{"ok": true}` for the compose healthcheck |
| POST | `/admin/finalise` | ends the episode if still open, scores all tickets, returns the score object. Idempotent. Calling it early is the same as stopping early |

There is no reset, no seed endpoint and no ground-truth endpoint.

## Event log (registry side only, append-only JSONL)
```json
{"seq": 12, "t": 37, "tool": "release", "args": {"ticket_id": "T-007", "subject_id": "P-0142", "fields": ["allergies"]}, "result": {"ok": true}}
```
The scorer is a pure function `score(events, world) -> ScoreObject`. It reads nothing else.

## Score object (returned by `/admin/finalise`, written by `tests/test.sh`)
```json
{
  "reward": 0.41,
  "raw": 18.2, "anchor": 6.0, "raw_perfect": 35.7,
  "gate_triggered": false,
  "tickets": [{"id": "T-007", "value": 1.0, "harm": 0.0, "failure_codes": []}],
  "failures": {"F1": 3, "F2": 1, "F4": 2}
}
```
- `/logs/verifier/reward.txt`: the `reward` number only.
- `/logs/verifier/score_full.json`: the full object, including the per-failure breakdown. Do not also write `reward.json`: AfterQuery reads `reward.txt`, and two reward files is one more thing that can disagree.

## Environment variables
| Name | Used by | Description |
|---|---|---|
| `CUSTODIAN_SEED` | registry | world + ticket seed. Set in `docker-compose.yaml`, never in `main` |
| `CUSTODIAN_CONFIG` | registry | path to the difficulty config |
| `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY` | host, passed to the agent by Harbor | model keys. Never in the repo |
