# yehor/ref-analysis-loss

- **Owner:** Yehor
- **Agent:** yehor-codex-1
- **Base:** main
- **Issue:** #145

## Goal

Use the outcome component to identify the diversion loss applied to each analyzed score.

## Files I own

`analysis/ed72_analysis/tables.py` and `analysis/tests/test_report.py`.

## Don't touch

The scorer and published campaign artifacts.

## Handoff

The analysis suite passed with 15 tests, including both diversion rates, absent or inconsistent provenance, and a six-decimal rounding midpoint.
