# yehor/harness-eval-seed

- **Owner:** Yehor
- **Agent:** yehor-codex-1
- **Base:** main
- **Issue:** #143

## Goal

Match simulator integer parsing and Compose’s default semantics. Verify that the plan, manifest, and keyless run agree on a signed seed.

## Files I own

`eval/manifest.py`, `eval/tests/test_manifest.py`.

## Don't touch

Published campaign artifacts.

## Handoff

The evaluation suite passed with 69 tests, including signed Compose overrides and historical summaries.
