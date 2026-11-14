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
- [x] Produce an OpenCode model run log and score with Verda Kimi K3.1 Pro.

## Decisions and notes
- 2026-11-14: Keep S0 as a reproducible transport/security spike. Put the submission task in `harbor/unfindable/`.
- 2026-11-14: Use Harbor separate verifier mode and sidecar collect artifact; never score agent-writable verifier files.
- 2026-11-14: Require spectator/verifier credentials from configuration; Harbor generates its verifier credential at runtime and the collector reads it from a protected file.
- 2026-11-14: Installed Harbor 0.26.0 in ignored `.venv/` and ran the task with Docker. The first Oracle trial exposed a trailing newline in the verifier token header; `collect.py` now strips it. Oracle scored 1.0 and `nop` scored 0.0 in complete separate-verifier runs. Jobs are in ignored `.venv/harbor-jobs/`.
- 2026-11-14: OpenCode 1.19.5 with Verda Kimi K3.1 Pro completed all 11 requests in Harbor 0.26.0 separate-verifier mode and scored 1.0 with no critical or minor leaks. The run is saved under `.venv/harbor-jobs/verda-kimi/2026-11-14__11-33-03/`. The Verda key is in ignored `.env` as `VERDA_INFERENCE_API_KEY`; do not commit it.

## Handoff
- Done: issue #2 claimed; Harbor task, verifier and README are in place; Harbor lint passes; Oracle=1.0 and nop=0.0; OpenCode 1.19.5 with Verda Kimi K3.1 Pro=1.0 on all 11 requests. The full local run is in `.venv/harbor-jobs/verda-kimi/2026-11-14__11-33-03/`. The feature branch has the original package commits pushed.
- Next: add a sanitized Harbor model run log and score to the tracked submission artifacts before submission. Keep `.env` out of Git.
- How to test: `harbor lint ./harbor/unfindable`; `harbor run -p ./harbor/unfindable -a oracle` (expected 1.0); `harbor run -p ./harbor/unfindable -a nop` (expected 0.0); `harbor run -p ./harbor/unfindable -a opencode -m verda/kimi-k3-1-pro --base-url https://inference.verda.com/v1 --api-format openai_chat_completions --api-key-name VERDA_INFERENCE_API_KEY --env-file .env --agent-setup-timeout-multiplier 3` (expected successful model run; may incur inference charges).
