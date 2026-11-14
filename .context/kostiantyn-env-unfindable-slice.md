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
- [ ] Produce an OpenCode model run log and score when model credentials are available.

## Decisions and notes
- 2026-11-14: Keep S0 as a reproducible transport/security spike. Put the submission task in `harbor/unfindable/`.
- 2026-11-14: Use Harbor separate verifier mode and sidecar collect artifact; never score agent-writable verifier files.
- 2026-11-14: Require spectator/verifier credentials from configuration; Harbor generates its verifier credential at runtime and the collector reads it from a protected file.
- 2026-11-14: Harbor 0.26.0 is the current official release. Local install timed out at PyPI and Docker's Windows service could not be started; no Harbor run log exists yet. Do not substitute an oracle run for the required model playthrough.

## Handoff
- Done: issue #2 claimed; Harbor S0 files and real backend contracts inspected; task package added under `harbor/unfindable/`; contracts documented; root submission README added; feature branch pushed.
- Next: run the task through Harbor with `-a oracle` to validate packaging, then use OpenCode with a chosen model and save the Harbor run log and score. The oracle does not satisfy the required model playthrough.
- How to test: start Docker Desktop, install Harbor 0.26.0, then run `harbor run -p ./harbor/unfindable -a oracle`; run the OpenCode trial after confirming permission to use the configured paid model credential.
