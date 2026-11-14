# Branch: yehor/harness-task-skeleton

- **Issue:** #22
- **Owner:** yehor
- **Agent:** lead
- **Parent branch:** main
- **Created:** Sat 16:12

## Goal
Create the ED-72 Harbor task packaging with the required main/hospital isolation, collect hook, and MCP sidecar wiring. Validate the task config and, once simulator stub files are available, run both oracle and nop through Harbor to confirm reward collection.

## Files and folders I own
- `ed72/task.toml`
- `ed72/environment/Dockerfile`
- `ed72/environment/docker-compose.yaml`
- `ed72/environment/hospital/Dockerfile`
- `ed72/environment/hospital/start.sh`
- `.context/yehor-harness-task-skeleton.md`

## Don't touch
- All simulator, scorer, tool server, verifier, tests, instructions, and solution files owned by lanes A, B, or C.

## Contracts used or changed
Anything from docs/CONTRACTS.md this branch depends on or changes.
- Depends on `hospital` at `http://hospital:8000/mcp` over streamable HTTP, `/health`, separate verifier mode, and sidecar-collected `/evidence/report.json`. No contract changes.

## Status
- [x] Packaging updated for the v1 hospital server and handbook path; isolated main and hospital Docker images build.
- [x] Harbor smoke with current #5 server/ward and #45 collector/verifier passed with temporary simulator/scorer modules.
- [ ] Run the task with the real simulator/scorer and handbook after their files land.

## Decisions and notes
Short and dated: why we chose X, new dependencies and why, gotchas.
- 2026-11-14: Mirror Harbor 0.25.0 packaging verified by #21, renamed to `hospital` and ED-72. The ED-72 simulator/scorer and report schema remain lane-owned.
- 2026-11-14: Do not set `ED72_CONFIG` until lane A selects the file path. `ED72_SEED` is set only by compose, as the contract requires.
- 2026-11-14: PR #43 merged and selected the `ed72/` layout. The hospital service builds from `ed72/environment` with `hospital/Dockerfile`, so it can copy `workspace/HANDBOOK.md` to `/app/HANDBOOK.md` and still use explicit COPYs for the hospital sources.
- 2026-11-14: The #5 server reads `HANDBOOK.md` beside `server.py`. Its `mock_sim.py` is only imported with `USE_MOCKS=1` and its docstring says it is not copied into the hospital image; production compose leaves `USE_MOCKS` unset.
- 2026-11-14: Hospital Dockerfile copies only `hospital/server.py`, `collect.py`, `start.sh`, `ed72_sim/`, and `workspace/HANDBOOK.md`; main Dockerfile copies only the handbook and executable `ward` CLI.

## Handoff
Done / not done / how to test. Keep this current: another agent may pick it up.
- Done: Built both Dockerfiles from a temporary environment-root context containing the exact current #5 `server.py`/`ward`, exact #45 `collect.py`/tests, marker handbook, and generated fake `ed72_sim` modules. Main-image inspection found `/app/HANDBOOK.md` and `/usr/local/bin/ward`, with no `/app/server.py`, `collect.py`, `mock_sim.py`, or `ed72_sim/`. Hospital-image inspection found the server, collect hook, simulator package, handbook, and writable `/evidence`, with no `mock_sim.py` or default `USE_MOCKS`. Harbor 0.25.0 lint passed; oracle passed 1/1 at mocked reward 0.708 and nop 1/1 at mocked reward 0.252. Logs are in `/tmp/ed72-actual-source-smoke-results/`. These scores verify packaging/reward plumbing only; they do not validate the real simulator or policy. `bash -n` passes. The checked-in task still needs real `server.py`, `collect.py`, `ed72_sim/`, tests, and HANDBOOK from lanes A/B. OpenCode model smoke remains #21.
