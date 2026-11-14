# Branch: mykhailo/env-rules-audit

- **Issue:** #6 (A4: events, warnings, agency staff, CT repair, diversion, budget limit)
- **Owner:** mykhailo
- **Agent:** mykhailo-claude-1
- **Parent branch:** kostiantyn/env-sim-core (PR #48). Retarget to main once #48 merges.
- **Created:** Sat 15:10

## Goal
Most A4 rules already live in the sim core (#4, PR #48). This branch checks each one against `docs/ED_Management_Simulator_RU.md` and SPEC §3/§4/§12, with one test per rule showing its sim consequence, and resolves the double-repair finding. Done when every A4 rule has a passing test (or a strict xfail naming the mismatch, reported to #4), and the reference (#16) still beats the baselines.

## Files and folders I own
- `ed72/environment/hospital/tests/test_rules_events.py` (subagent mykhailo-claude-1d)
- `ed72/environment/hospital/tests/test_rules_staff.py` (subagent mykhailo-claude-1e)
- `ed72/environment/hospital/tests/test_rules_actions.py` (subagent mykhailo-claude-1f)
- `.context/mykhailo-env-rules-audit.md`

## Don't touch
- `ed72_sim/engine.py`, `actions.py`, `state.py`, `observation.py`, `constants.py`, `world.py`, existing tests (#3/#4, kostiantyn-claude-2). Engine fixes go to them on #4 / PR #48 first.
- Scoring (#10), collect (#11).

## Contracts used or changed
- Uses CONTRACTS v1 actions, reasons and observation. Possible change: a `repair_pending` reject reason (contract-change on #1), pending the decision below.

## Status
- [x] 1. Audit + tests, in parallel (subagents 1d/1e/1f): 37 tests, no mismatch with the rulebook
- [x] 2. Results posted on #6; HANDBOOK lines requested on #7
- [x] 3. Double repair: proposed a HANDBOOK line, no engine or contract change (open for objections on #6)
- [ ] 4. Check the reference (#16) still beats the baselines (#12, PR #52)
- [ ] 5. cross-review, ship-pr

## Decisions and notes
- 2026-11-14: Branch based on PR #48 because the rules under test live there; tests only, so the PR stays small once #48 merges.
- 2026-11-14: Double repair: the rulebook is silent; the engine charges €2 000 and changes nothing. Chosen: document it in HANDBOOK (#7) rather than add a `repair_pending` reason, so no contract change before the 22:00 freeze.
- 2026-11-14: Run tests with `uv run --no-project` so uv doesn't create a uv.lock in the hospital project (not ours).

## Handoff
- Done: 37 rule tests in `tests/test_rules_{events,staff,actions}.py`; full suite 94 passed; no engine mismatch.
- #48 merged; main is merged into this branch, so the diff against main is only these tests and this file.
- In progress: code-review round 1 found tests that couldn't fail (flu, hard-limit repair, diversion length, agency leave tick); subagent mykhailo-claude-1i is strengthening them, each checked against a deliberately broken engine.
- Next: commit those fixes, open the PR (`Closes #6`), then step 4 once #16 posts a reference score.
- How to test: `cd ed72/environment/hospital && uv run --no-project --python 3.12 --with pytest pytest -q tests`
