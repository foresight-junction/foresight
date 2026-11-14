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
- 2026-11-14: Reviewed proposed CONTRACTS v1 (#43) and verifier PR #45. MCP tools and score fields changed, but the Harbor boundary still uses `hospital`, `/mcp`, `/health`, separate mode, `/app/collect.py`, `ED72_SEED`, writable `/evidence`, and the `/evidence/report.json` sidecar artifact. No packaging edit was needed.

## Handoff
Done / not done / how to test. Keep this current: another agent may pick it up.
- Done: Harbor 0.25.0 lint passed on the temporary #21 smoke task. Oracle passed 1/1 at reward 1.0; nop passed 1/1 at 0.0. Re-ran a temporary #43/#45 integration fixture with the v1 tools and report shape: oracle passed at mocked reward 0.708; nop passed at mocked reward 0.252. Those numbers only demonstrate the verifier plumbing, not policy quality. Both smoke result sets are under `/tmp/`. `bash -n` passed. Harbor's generated compose overlay supplies the `main` service build configuration, so standalone `docker compose config` is not applicable to this intentionally partial compose file; both Harbor runs verified the merged compose configuration. The actual task still needs lane A's server/simulator and lane B's scorer before the integrated branch run. OpenCode model smoke is handled under #21.
