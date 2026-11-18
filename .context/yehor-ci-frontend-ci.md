# yehor/ci-frontend-ci

- **Owner:** Yehor
- **Agent:** yehor-codex-1
- **Base:** main
- **Issue:** #140

## Goal

Add the existing Python replay exporter and live-server tests to CI on Python 3.12. Verify clean collection without model credentials.

## Files I own

`.github/workflows/ci.yml`, `frontend/tools/live/README.md`.

## Don't touch

Published campaign artifacts.

## Handoff

Added the Python replay and live tests to GitHub Actions. The workflow command passed locally with 55 passes and one intentional skip. See the live viewer guide for the command.
