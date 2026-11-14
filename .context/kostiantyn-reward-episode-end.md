# Branch: kostiantyn/reward-episode-end

- **Issue:** #15
- **Owner:** kostiantyn
- **Agent:** kostiantyn-claude-2g
- **Parent branch:** main
- **Created:** Sat 15:06

## Goal
Prove end of episode end to end with the real engine, scorer and collect.py: remaining ticks, outcome classes, both rulebook section 13 fixes and the `ended` field.

## Files and folders I own
- ed72/environment/hospital/tests/test_end_of_episode.py
- this context file

## Don't touch
- collect.py, engine.py, scoring/ (bugs go in the handoff below)

## Contracts used or changed
- ScoreObject `ended`; no change. `timeout` clarification proposed on #1 (agent timeout is reported as `agent_stopped`).

## Status
- [x] Cases: stop after 12 steps, call cap, in bed never covered (1), in bed covered (0.3), diverted (0.7, late), last-tick fill, collect round trip
- [x] Tests pass (120 passed, 1 xfailed)

## Decisions and notes
- The code already did the logic; no source change was needed.
- Found a gap in collect.py (see Handoff), pinned with a strict xfail test.

## Handoff
Done: tests/test_end_of_episode.py (7 passing, 1 strict xfail).
Not done: collect.py drops refused step lines (and observe/rules lines) when replaying, so a replayed call-cap run reports `ended: agent_stopped` and a low `tool_calls`. Fix: replay every non-step agent line with `sim.record_call(tool, args, result)` and keep stepping for the successful step lines; then remove the xfail.
Test: `cd ed72/environment/hospital && python -m pytest -q -p no:cacheprovider`
