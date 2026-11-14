# Branch: kostiantyn/reward-scorer

- **Issue:** #10 ([reward] B1: Scorer)
- **Owner:** kostiantyn
- **Agent:** kostiantyn-claude-2d
- **Parent branch:** main
- **Created:** Sat 14:29

## Goal
`score(events) -> dict`: pure scorer over the hospital event log, per rulebook section 11 and SPEC section 6 (CONTRACTS v1 score object).

## Files and folders I own
- ed72/environment/hospital/ed72_sim/scoring/ (`__init__.py`, `score.py`, `failures.py`)
- ed72/environment/hospital/tests/test_score.py

## Don't touch
- constants.py, model.py, rng.py (orchestrator owns them)

## Contracts used or changed
- Reads the CONTRACTS v1 score object and the batch event lines. No changes.

## Status
- [x] Tests first (synthetic logs)
- [x] score.py: patients, O, T, W, B, totals
- [x] failures.py: F1, F2, F6, F7, F8, F10 replay
- [ ] Orchestrator review and ship

## Decisions and notes
- F3, F4, F5, F9 are reported as 0; C4 owns them.
- No patients at all gives O = T = 1.0.

## Handoff
Done: scorer, failure replay, 28 tests. Not done: F3/F4/F5/F9, `ended` override (collect.py).
Test: `cd ed72/environment/hospital && python -m pytest -q`
