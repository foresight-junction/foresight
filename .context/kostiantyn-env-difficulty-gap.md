# Branch: kostiantyn/env-difficulty-gap

- **Issue:** none yet; coordinated by the orchestrator session (kostiantyn-claude-6), merged into `kostiantyn/final`
- **Owner:** kostiantyn
- **Agent:** kostiantyn-claude-6a
- **Parent branch:** kostiantyn/final
- **Created:** 2026-11-14

## Goal
Widen the reference-minus-model gap through SPEC §7 knobs only, keeping every EVAL §5 ordering.

## Files and folders I own
- `ed72/environment/hospital/ed72_sim/constants.py` (values only), `ed72/environment/hospital/config/default.json`
- `ed72/environment/workspace/HANDBOOK.md` (rate tables), `docs/SPEC.md` §7 (and the §3 event table, §12 arrival row that restate the values), `docs/TUNING.md`
- Tests that pin those values: `tests/test_config.py`, `tests/test_rules_events.py`, `tests/test_world.py`, `analysis/ablations/tests/test_ablations.py` (stand-in floor)

## Don't touch
- Sim and scorer logic, README, `eval/run_all.sh`

## Contracts used or changed
- None. Shapes unchanged; only rate values move.

## Status
- [x] Amplitude 0.9, 3 sick nurses, flu 10 ticks, bus 6/tick for 3 ticks
- [x] All hospital, eval, eval/baselines, solution and ablations tests pass
- [ ] One Gemini run on the new defaults (the orchestrator schedules it)

## Decisions and notes
- 2026-11-14: tuned against a local port of Gemini's own seed-42 controller (reproduces 81.17 exactly). Raising arrival mean hurt the reference as much as the proxy, so it was rejected. Details in `docs/TUNING.md`.

## Handoff
Done: config change, docs, tests. Not done: the real Gemini run. Test: `cd eval/baselines && PYTHONPATH=../../ed72/environment/hospital uv run python -m ed72_baselines.table 1 2 3 4 5 42`.
