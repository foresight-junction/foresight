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
- [x] Packaging implemented; Harbor smoke passed with oracle reward 1.0 and nop reward 0.0.
- [ ] Run the task from the completed ED-72 tree after lane A/B files land.

## Decisions and notes
Short and dated: why we chose X, new dependencies and why, gotchas.
- 2026-11-14: Mirror Harbor 0.25.0 packaging verified by #21, renamed to `hospital` and ED-72. The ED-72 simulator/scorer and report schema remain lane-owned.
- 2026-11-14: Do not set `ED72_CONFIG` until lane A selects the file path. `ED72_SEED` is set only by compose, as the contract requires.
- 2026-11-14: Sidecar Dockerfile copies only `server.py`, `collect.py`, and `ed72_sim/`; avoid baking local files into the service image.
- 2026-11-14: Team still needs to choose `backend/` versus `ed72/` for Kostiantyn's engine. This branch follows the current `ed72/` task contract and avoids simulator internals.

## Handoff
Done / not done / how to test. Keep this current: another agent may pick it up.
- Done: Harbor 0.25.0 lint passed on the temporary smoke task. `harbor run` passed with oracle (1/1, reward 1.0) and nop (1/1, reward 0.0); run logs are under `/tmp/ed72-harbor-smoke-results2/`. `bash -n` passed. Harbor's generated compose overlay supplies the `main` service build configuration, so standalone `docker compose config` is not applicable to this intentionally partial compose file; the Harbor run verified the merged compose configuration. The actual branch task is missing lane-owned `instruction.md`, tests, server, collect, and sim files, so run `harbor lint ed72` and both policies once those files land. OpenCode model smoke is handled under #21.
