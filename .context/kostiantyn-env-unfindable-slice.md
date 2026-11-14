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

## Handoff
- Done: issue #2 claimed; Harbor S0 files and real backend contracts inspected; task package added under `harbor/unfindable/`; contract change announced on issue #1 and documented in `docs/CONTRACTS.md`.
- Next: write the short submission README, then run an OpenCode model trial and save its log and score.
- How to test: `harbor run -p ./harbor/unfindable -a oracle`; run OpenCode with the organizer's model when credentials are available.
