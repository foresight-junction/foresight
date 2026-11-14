# analysis

Stdlib-only tooling for the failure analysis (issue #19). It never imports the simulator.

- Reads one or more `score_full.json` files (CONTRACTS score object) and optionally the matching event log JSONL.
- Run: `python -m ed72_analysis.report --run opus/seed1=score_full.json,events.jsonl --run opus/seed2=other.json --out out/`
- Labels like `opus/seed1` are grouped by the text before `/`; groups with 2+ runs get a mean row.
- Writes `out/report.md` (scores, failures by code, outcomes by ESI, up to 3 trajectory excerpts per run with a log) and `out/failures.svg`.
- Codes missing from a score object show as `n/a`, never 0.
- Tests: `cd analysis && python -m pytest -q`
- The findings themselves are written into `docs/FINDINGS.md` by lane C after real agent runs. This tool only produces the tables.
