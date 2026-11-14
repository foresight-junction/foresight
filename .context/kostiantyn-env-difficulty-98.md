# Branch: kostiantyn/env-difficulty-98

- **Issue:** #69 (with #98); coordinated by the orchestrator (kostiantyn-claude-6), merged into `kostiantyn/final`
- **Owner:** kostiantyn
- **Agent:** kostiantyn-claude-6a
- **Parent branch:** kostiantyn/final
- **Created:** 2026-11-14

## Goal
Adopt #98 (arrival mean 4.0 plus the scarcity-planning reference), and fix the AGENTS 10.5 divert-all ceiling it broke.

## Files and folders I own
- `ed72_sim/constants.py` (values), `HANDBOOK.md`, `docs/SPEC.md` §7, `docs/TUNING.md`, `ed72/solution/policy.py` (from #98), pinned-value tests

## Don't touch
- README, `eval/run_all.sh`

## Contracts used or changed
- None.

## Status
- [x] Merge `origin/yehor/ref-gap-planner` and drop its stray hospital `uv.lock`
- [x] DIVERT_SHARE 0.7 -> 0.75; divert-all at most 45.2 on seeds 1-20 and 42
- [ ] One Gemini run at the new defaults (the orchestrator schedules it)

## Decisions and notes
- 2026-11-14: diversion share chosen because only diverting policies feel it. Superseded my independent tuning in PR #101.

## Handoff
Done: merge, fix, docs, tests. Test: `cd eval/baselines && PYTHONPATH=../../ed72/environment/hospital uv run python -m ed72_baselines.table 1 2 3 4 5 42`.
