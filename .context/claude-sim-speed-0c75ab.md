# Branch: claude/sim-speed-0c75ab

- **Issue:** none (orchestrated task from kostiantyn-claude-6; merged into `kostiantyn/final`)
- **Owner:** kostiantyn
- **Agent:** kostiantyn-claude-6b
- **Parent branch:** kostiantyn/final
- **Created:** 2026-11-14

## Goal
Make the sim, the collect replay and the hospital test suite faster with zero behaviour change: same seed and
actions give byte-identical event logs and score objects.

## Files and folders I own
- `ed72/environment/hospital/ed72_sim/` internals (not config default values, not HANDBOOK.md)
- `ed72/environment/hospital/collect.py`
- `ed72/environment/hospital/tests/`, `ed72_sim/**/tests` (not the thresholds in `test_baselines.py`)

## Don't touch
- Config default values, HANDBOOK rate tables, baseline thresholds (difficulty agent)

## Contracts used or changed
- None changed. Tool results, event-log lines and the score object are unchanged.

## Status
- [x] Profile (reference episode, collect, pytest --durations)
- [x] Engine: log lines written once per public call instead of one file open per line
- [x] Engine: `replay_step` for collect (no unused observation, no copy of freshly parsed actions)
- [x] Engine: plain-JSON fast path for the copy of logged actions; world gen hazard draws via list comp
- [x] Tests: firewall analysis once per module; cached worlds in test_world; ward CLI in-process except 2 runs
- [x] Identical-output proof on seeds 1-5, 42 for every baseline, severity and reference

## Decisions and notes
- 2026-11-14: the log file is still complete when each public call (`__init__`, `step`, `replay_step`,
  `run_to_end`, `record_call`) returns, which is all the server and collect.py rely on. Lines are serialised
  at emit time, so later mutation cannot change them. Pinned by `test_log_file_is_complete_after_every_public_call`.
- The actions copy happens after `apply_actions`, as before, so even an exceptional path behaves the same.

## Handoff
- Done: see Status. Test: `uv run --with pytest pytest -q` in `ed72/environment/hospital`.
- Proof: dump every baseline + severity + reference on seeds 1-5, 42 (events, score, collect replay, log bytes,
  every observation) before and after; `diff -r` is empty.
