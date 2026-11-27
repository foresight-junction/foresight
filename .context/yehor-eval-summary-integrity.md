# Branch: yehor/eval-summary-integrity

- **Issue:** #154
- **Owner:** Yehor (@yehorm14)
- **Agent:** yehor-codex-1a
- **Parent branch:** main at `5108a97`

## Goal
Reject invalid evaluation rewards and mark explicit timeouts incomplete while preserving valid partial scores.

## Files and folders I own
- `eval/summarise.py`
- `eval/tests/test_summarise.py`
- `.context/yehor-eval-summary-integrity.md`

## Don't touch
- Runner, verifier, scorer, and simulator.

## Contracts used or changed
- Uses the reward range and `ended` enum in `docs/CONTRACTS.md`.

## Status
- Reward validation and timeout handling implemented.
- Offline Python 3.12 eval suite passed with 96 tests. Ruff and a direct CLI smoke check passed.

## Handoff
- Orchestrator handles the push and pull request.
- Run `uv run --offline --python 3.12 --with pytest pytest -q` from `eval/`.
