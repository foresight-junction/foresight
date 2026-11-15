# yehor/harness-final-check

Final pre-submission check of main (781e143): does it run, and is the README accurate.

## Status
- Done: every CI check passes (7 uv projects, 743 tests; ruff; bash -n; frontend lint/build/108 tests).
- Done: keyless Harbor baselines on seed 3101 give reference 0.959, stop-early 0.046, do-nothing 0.000, matching README.
- Done: docs and comment fixes listed under Decisions.

## Decisions
- frontend/pnpm-workspace.yaml approves esbuild builds. Without it, `pnpm install --frozen-lockfile` exits 1 on pnpm 11+; CI pins pnpm 10 so it never saw this. Tested fresh installs on pnpm 10.20.0 and 12.18.0.
- HANDBOOK.md now states nine behaviours the sim already had (50-action cut-off, bed choice, coverage tie-break, CT pause still covered, agency departure and charging, zone fatigue mean, fractional hour, uniform event windows, which nurses fall sick). Each was checked against ed72_sim. No rule or rate changed.
- eval/results/summary.md is gitignored: it is regenerated per run and an untracked copy marks runs `+dirty`.

## Handoff
- Next: merge, then rerun `ED72_SEED=3101 make eval-baselines` on a clean checkout of main for a certified summary.
- Test: `make eval-baselines` (needs Docker), CI script in .github/workflows/ci.yml.
- Open: AGENTS.md team table is still TODO; public seeds 3101–3103 could be used to pre-compute arrivals by an agent with internet access (design note, not fixed).
