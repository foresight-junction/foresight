# yehor/viewer-replay-url

- **Owner:** Yehor
- **Agent:** yehor-codex-1
- **Base:** main
- **Issue:** #142

## Goal

Print a replay query that works on the viewer’s current host and port. Cover the standard, custom-directory, and no-save cases.

## Files I own

`frontend/tools/live/serve.py`, `frontend/tools/live/README.md`, `frontend/tools/live/tests/test_serve.py`.

## Don't touch

Published campaign artifacts.

## Handoff

The replay tooling suite passed with 58 passes and one skip, including default, custom, and no-save cases.
