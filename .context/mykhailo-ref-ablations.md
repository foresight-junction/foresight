# Branch: mykhailo/ref-ablations

- **Issue:** #36
- **Owner:** mykhailo
- **Agent:** lead mykhailo-claude-1, built by mykhailo-claude-1j
- **Parent branch:** main
- **Created:** Sat 15:38

## Goal
Measure what each rulebook lever (F1-F6) is worth: a stand-in reference with one switch per lever,
each variant run on seeds 1-3, scored by the real scorer in process.

## Files and folders I own
- `analysis/ablations/` (own uv project: `ed72_ablations/`, `tests/`, `README.md`)
- `.context/mykhailo-ref-ablations.md`

## Don't touch
- `ed72/` (sim, scorer, solution), `eval/`, `docs/`

## Contracts used or changed
- Uses CONTRACTS v1 Observation and Action shapes; `score(events)`; `generate_world(seed, config)`; `load_config(path)`. Changes nothing.

## Status
- [x] Stand-in policy with six levers (`standin.py`), MOCK until #16 lands
- [x] In-process runner and markdown table (`run.py`)
- [x] Tests: valid actions only, determinism, each lever changes actions, beats do-nothing
- [x] README with seeds 1-3 table and per-lever reading
- [ ] Swap the stand-in for the #16 reference when it exists; move the table into docs/FINDINGS.md

## Decisions and notes
- Sat: import the sim via `sys.path` (stdlib-only) rather than a path dependency, which would pull fastmcp.
- Sat: the `agency` lever also gates the warning-driven agency orders, so "no agency" means no agency at all.
- Sat: F3, F4, F5 cost 0.0 at the default config; F3 stays 0 even at arrival_mean 3.0. Finding for #8.

## Handoff
- Done: stand-in + runner + tests + README, results in `analysis/ablations/README.md`.
- Next: run the real #16 reference with the same switches; issue for #8 with the toothless levers.
- Test: `cd analysis/ablations && uv run --python 3.12 --with pytest pytest -q` (17 tests);
  table: `uv run --python 3.12 python -m ed72_ablations.run`.
