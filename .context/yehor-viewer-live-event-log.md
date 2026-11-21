# yehor/viewer-live-event-log

- **Owner:** Yehor
- **Agent:** yehor-codex-1
- **Base:** main
- **Issue:** #141

## Goal

Flush each simulated tail tick before publishing it in the live replay. Verify that the on-disk log reproduces the score and keeps the real agent-step count.

## Files I own

`ed72/environment/hospital/ed72_sim/engine.py`, `frontend/tools/live/recorder.py`, `frontend/tools/live/tests/test_recorder.py`.

## Don't touch

Published campaign artifacts.

## Handoff

Python live tooling passed with 55 passes and one skip. The hospital suite passed with 479 passes and one expected failure. The early-finish test checks the disk log and score.
