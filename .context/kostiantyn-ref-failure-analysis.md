# Branch: kostiantyn/ref-failure-analysis

- **Issue:** #19
- **Owner:** kostiantyn
- **Agent:** kostiantyn-claude-2j
- **Parent branch:** main

## Goal
Analysis tooling only: score_full.json (+ event log) to report.md and failures.svg. No findings: no real agent runs exist yet (#17/#18).

## Files and folders I own
- analysis/, .context/kostiantyn-ref-failure-analysis.md

## Don't touch
- docs/FINDINGS.md (written by lane C after real runs), everything else.

## Contracts used or changed
- CONTRACTS v1 score object and event-log lines (read only). No changes.

## Status
- [x] loaders, tables, trajectories, svg, CLI
- [x] synthetic tests (10)
- [ ] docs/FINDINGS.md: waits for real runs

## Decisions and notes
- ESI weights and loss values are copied into tables.py (no sim import); keep in sync with constants.py.
- F3, F4, F5, F9 are absent from score objects today: shown as n/a.

## Handoff
Done: tool and tests. Not done: findings. Test: `cd analysis && python -m pytest -q`.
Use: `python -m ed72_analysis.report --run opus/seed1=score_full.json,events.jsonl --out out/`
