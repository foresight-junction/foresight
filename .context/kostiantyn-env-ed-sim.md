# Branch: kostiantyn/env-ed-sim

- **Issue:** none yet (GitHub issue not created; needs a human OK to touch GitHub)
- **Owner:** kostiantyn
- **Agent:** kostiantyn-claude-1
- **Parent branch:** kostiantyn/env-unfindable-slice (at 57d26a7)
- **Created:** 2026-11-14

## Goal
Replace the Unfindable registry environment with the Emergency Department Management Simulator: a deterministic 72-hour ED engine, MCP tools, a 0..1 evaluator, a reference agent and baselines, a Harbor task and a 3D spectator view. Done when a Harbor run with the reference agent and an OpenCode + Kimi run both produce `/logs/verifier/reward.txt`.

## Files and folders I own
- `backend/app/edsim/` (new engine)
- `backend/tests/edsim_support.py`, `backend/tests/test_edsim_*.py`
- `docs/ed/`
- Later milestones: `backend/app/` wiring, `backend/agents/`, `harbor/`, `frontend/`, `README.md`, `docs/CONTRACTS.md` (via contract-change)

## Don't touch
- `spikes/s0-harbor/` (historical transport spike)
- `.env` (holds the Verda/Moonshot keys)

## Contracts used or changed
- None yet. M2 will change the MCP tool set, `/admin/*` response shapes and `UF_*` env vars through the contract-change skill.

## Status
- [x] M1 Phase 1: repository audit and migration inventory (`docs/ed/MIGRATION.md`)
- [x] M1 Phase 2: architecture (`docs/ed/ARCHITECTURE.md`)
- [x] M1 Phase 4: engine `backend/app/edsim/` with 77 tests; full backend suite 134 passed
- [ ] M2: MCP tools + evaluator (waiting on decisions D1–D4 in MIGRATION.md)
- [ ] M3: reference agent and baselines
- [ ] M4: Harbor task and Kimi run
- [ ] M5: old-domain removal and README
- [ ] M6: 3D visualization

## Decisions and notes
- 2026-11-14: New branch rather than editing the Unfindable branch, so the working Unfindable submission stays intact.
- 2026-11-14: Time-stepped engine (1 sim-minute) with a pre-generated exogenous schedule (common random numbers). Stdlib only: no new dependencies.
- 2026-11-14: Calibrated with a throwaway greedy manager: resus 3 beds (standard/easy), acuity-1 hazard scale 45, treated hazard factor 0.01, fatigue base 0.095, targets 10/20/60/120/240, budgets 95k/106k/110k.
- 2026-11-14: Old `backend/app/sim` and its 57 tests are untouched in M1 and still pass; they are replaced in M2.

## Handoff
- Done: audit, architecture, engine and tests (M1).
- Next: get approval on D1–D4, then M2 (MCP tools on `app.edsim.Simulation`, evaluator, `/admin/finalize`, remove `app/sim`).
- How to test: `cd backend && .venv/Scripts/python.exe -m pytest -q` (or `uv run pytest -q`). Quick look: `python -c "from app.edsim import Simulation; s=Simulation('standard', 1); s.run_to_end(); print(s.metrics())"`.
