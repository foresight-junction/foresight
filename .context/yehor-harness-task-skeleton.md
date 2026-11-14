# Branch: yehor/harness-task-skeleton

- **Issue:** #22
- **Owner:** yehor
- **Agent:** lead
- **Parent branch:** main
- **Created:** Sat 16:12

## Goal
Package the ED-72 task for Harbor with an isolated main image, hospital sidecar, collect hook, and MCP wiring.

## Files and folders I own
- `ed72/task.toml`
- `ed72/environment/Dockerfile`
- `ed72/environment/docker-compose.yaml`
- `ed72/environment/hospital/Dockerfile`
- `ed72/environment/hospital/start.sh`
- `.context/yehor-harness-task-skeleton.md`

## Don't touch
- Simulator, scorer, tool server, verifier, tests, instructions, and solution files owned by lanes A, B, or C.

## Contracts used or changed
- Depends on `hospital` at `http://hospital:8000/mcp` over streamable HTTP, `/health`, separate verifier mode, and sidecar-collected `/evidence/report.json`. No contract changes.

## Status
- [x] Harbor task packaging and explicit main/hospital image isolation.
- [x] Harbor 0.25.0 lint and production `nop` run passed against the synced branch with the merged handbook, server, engine, scorer, and verifier. Nop: 1/1, no exceptions, reward 0.
- [x] Real #16 reference completed through Harbor against current main and the same production packaging. Oracle: 1/1, no exceptions, reward 0.999552 (score 99.9552), spend €7,000, 146 tool calls, 140 ticks with actions, ended at tick 143. This used the exact pushed reference branch in a temporary overlay because its code is not on main yet.
- [ ] Ask integrator whether #22 can go ready before the #16 reference PR merges; keep #58 draft until that decision.

## Decisions and notes
- 2026-11-14: Hospital builds from `ed72/environment` so `workspace/HANDBOOK.md` is available to the sidecar; Dockerfiles use explicit copies to keep the main image isolated.
- 2026-11-14: Leave `ED72_CONFIG` unset while calibration owns config selection. The server's `generate_world(seed)` and verifier's `load_config(None)` both use constants defaults. No config JSON copy is needed until a shared custom path is selected; then server and replay must use the same file.
- 2026-11-14: The branch is synced through main `59d55c8` (current merge commit `3c222c3`). The reference run used main `dd5c768`, which already had the real engine, verifier, and handbook; later main merges did not change those inputs.
- 2026-11-14: The first #16 run found that `ward rules` prints plain handbook text while the reference expected JSON. The #16 branch now handles raw text and passes. Kostiantyn selected an optional JSON output mode for a #5 follow-up; that change is still pending, and #16 may switch to it.

## Handoff
- Done: Harbor lint, production nop, and full reference Harbor validation passed. The reference overlay used main `dd5c7689254c864a7bb0a1bdb03fbdb96ab067af`, #16 ref branch `5264305d86b6e957f6c5e8472ba51bccc015c497`, and this branch's packaging. It used the #16 raw-rules adapter as committed; no temporary source patch was applied. Temporary job artifacts are under `/tmp/ed72-unpatched-ref.XkMQb7/jobs/`.
- Done: #5 server, #7 handbook, and #64 config are merged. #16 reference is on PR #76 and is a dependency of the full reference check; #58 stays draft pending integrator guidance.
- How to test packaging on this branch: `HARBOR_TELEMETRY=0 PYTHONIOENCODING=utf-8 uvx harbor==0.25.0 lint ed72`, then `HARBOR_TELEMETRY=0 PYTHONIOENCODING=utf-8 uvx harbor==0.25.0 run -p ./ed72 -a nop`.
