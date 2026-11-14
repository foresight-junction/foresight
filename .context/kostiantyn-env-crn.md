# Branch: kostiantyn/env-crn

- **Issue:** #32
- **Owner:** kostiantyn
- **Agent:** kostiantyn-claude-2b
- **Parent branch:** main

## Goal
Action-independent randomness (common random numbers): `ed72_sim/rng.py` provides named substreams from (seed, name). Rule: the world generator pre-draws every random quantity (per-patient ones from `stream(seed, f"patient:{pid}")` in a fixed order); the sim core draws none. Done when test_rng.py passes and #3/#4 follow the rule.

## Files and folders I own
- ed72/environment/hospital/ed72_sim/rng.py
- ed72/environment/hospital/tests/test_rng.py

## Don't touch
- constants.py, model.py, world.py, sim core. The cross-policy CRN integration test lives in #4, not here.

## Contracts used or changed
- None. rng.py signatures and the sha256 derivation are frozen because #3 already calls them.

## Status
- [x] Pinned-value, derivation, distribution and validation tests
- [x] Input validation (ValueError) added without changing draw order
- [x] Rule posted on #3 and #4
- [ ] CRN integration test (in #4)

## Decisions and notes
- 2026-11-14: sim core draws no random numbers; world generation pre-draws everything. Pinned literals catch Python-version drift.

## Handoff
- Done: rng.py validation, 15 tests. Not done: integration test (#4).
- Test: `cd ed72/environment/hospital && python -m pytest -q tests/test_rng.py`
