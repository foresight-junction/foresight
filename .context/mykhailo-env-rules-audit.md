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
- [ ] 1. Audit + tests, in parallel: events/warnings/sick nurses; agency/faint/recovery; repair/divert/hard limit
- [ ] 2. Report mismatches to #4, consequences to lane B (#10)
- [ ] 3. Double-repair decision: reject reason vs HANDBOOK line
- [ ] 4. Check the reference (#16) still beats the baselines (#12, PR #52)
- [ ] 5. cross-review, ship-pr

## Decisions and notes
- 2026-11-14: Branch based on PR #48 because the rules under test live there; tests only, so the PR stays small once #48 merges.

## Handoff
- Done: claimed #6, plan above.
- Next: step 1.
- How to test: `cd ed72/environment/hospital && uv run --python 3.12 --with pytest pytest -q tests`
