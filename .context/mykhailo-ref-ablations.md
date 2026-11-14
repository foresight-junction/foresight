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
- [x] Review fixes: levers decoupled (lockstep ownership test), counts_as in staffing, stateless repair,
  obs-key and constants-sync tests, F6 listed as an added habit, `--policy reference` row
- [ ] Move the table into docs/FINDINGS.md (coordinate with #19); file the toothless-lever numbers on #8

## Decisions and notes
- Sat: import the sim via `sys.path` (stdlib-only) rather than a path dependency, which would pull fastmcp.
- Sat: surge agency on a warning belongs to `warnings` (F3); shortfall agency to `agency` (F5).
- Sat: spend order repair -> surge -> shortfall, all capped at the soft budget (the only cross-lever coupling).
- Sat: F3, F4, F5 are about 0 at the default and at arrival_mean 3.0. The #16 reference (5264305)
  scores the same as the full stand-in. Finding for #8.
- Sat: `--policy reference` needs ed72/solution/ (not on main yet); pass `--reference-dir` to an extracted copy.

## Handoff
- Done: stand-in + runner + tests + README, results in `analysis/ablations/README.md`.
- Next: FINDINGS.md section; rerun with `--policy reference` once #16 merges.
- Test: `cd analysis/ablations && uv run --python 3.12 --with pytest pytest -q` (24 tests);
  table: `uv run --python 3.12 python -m ed72_ablations.run`.
