# Branch: kostiantyn/env-unfindable-slice

- **Issue:** #2
- **Owner:** kostiantyn
- **Agent:** kostiantyn-codex-1
- **Parent branch:** main
- **Created:** 2026-11-14

## Goal
Package the Unfindable pilot as a Harbor task that OpenCode can run, with the required scalar reward file.

## Files and folders I own
- `.gitignore`
- `backend/`
- `frontend/`
- `docs/unfindable/`
- `docs/CONTRACTS.md` (through issue #1 and the contract-change skill only)
- `spikes/s0-harbor/`
- `harbor/unfindable/`
- `README.md`

## Don't touch
- Existing spike implementation in `spikes/s0-harbor/`

## Contracts used or changed
- Added the Unfindable routes, shared event/reset/reward shapes, MCP endpoint, and `UF_*` / `VITE_*` configuration to `docs/CONTRACTS.md` through the contract-change workflow.

## Status
- [x] Add a self-contained Harbor pilot task using the real backend and scalar `/logs/verifier/reward.txt` output.
- [x] Document the shared Unfindable API and configuration contracts.
- [x] Validate Harbor 0.26.0 Docker run: Oracle reward 1.0; no-op reward 0.0.
- [ ] Produce an OpenCode model run log and score when model credentials are available.

## Decisions and notes
- 2026-11-14: Keep S0 as a reproducible transport/security spike. Put the submission task in `harbor/unfindable/`.
- 2026-11-14: Use Harbor separate verifier mode and sidecar collect artifact; never score agent-writable verifier files.
- 2026-11-14: Require spectator/verifier credentials from configuration; Harbor generates its verifier credential at runtime and the collector reads it from a protected file.
- 2026-11-14: Installed Harbor 0.26.0 in ignored `.venv/` and ran the task with Docker. The first Oracle trial exposed a trailing newline in the verifier token header; `collect.py` now strips it. Oracle scored 1.0 and `nop` scored 0.0 in complete separate-verifier runs. Jobs are in ignored `.venv/harbor-jobs/`.

## Handoff
- Done: issue #2 claimed; Harbor task, verifier and README are in place; Harbor lint passes; Oracle=1.0 and nop=0.0 in Harbor 0.26.0 Docker runs; feature branch has the original package commits pushed.
- Next: run OpenCode with a chosen model and save the Harbor run log and score. Oracle does not satisfy the required model playthrough.
- How to test: `harbor lint ./harbor/unfindable`; `harbor run -p ./harbor/unfindable -a oracle` (expected 1.0); `harbor run -p ./harbor/unfindable -a nop` (expected 0.0). Run the OpenCode trial only after confirming permission to use the configured model credential, which may incur cost.
