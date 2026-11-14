# Branch: leonardodadenchik/fe-pixel-viewer--claude-1a

- **Issue:** #97
- **Owner:** leonardodadenchik
- **Agent:** leonardodadenchik-claude-1a (helper of leonardodadenchik-claude-1)
- **Parent branch:** leonardodadenchik/fe-pixel-viewer
- **Created:** Sat 19:59

## Goal
Replay data for the pixel viewer: seed-42 replays for reference, Gemini's own script and the reactive
proxy, plus index.json, all from `frontend/tools/export_replay.py`.

## Files and folders I own
- `frontend/tools/**`, `frontend/public/replays/**`, this file

## Don't touch
- `frontend/src/**` (types.ts is the lead's), `ed72/`, `eval/`, `docs/`

## Contracts used or changed
- Uses CONTRACTS v1 observation/action/result/event shapes via `frontend/src/replay/types.ts`. No changes.

## Status
- [x] Gemini controller extracted verbatim to `frontend/tools/gemini_policy/run_ed.py` (trajectory steps[18])
- [x] In-process MCP transport: `frontend/tools/gemini_policy/adapter.py`
- [x] Exporter policies: reference, gemini, reactive, do-nothing; `--all`; index.json written every run
- [x] Replays for seed 42 (reference 0.989617, gemini 0.811712, reactive 0.600970)
- [x] `frontend/tools/test_export_replay.py` (21 tests)

## Decisions and notes
- Sat: Gemini replay reproduces the real run exactly (reward 0.811712, identical per-patient outcomes).
  The controller has no randomness and the sim is unchanged since the run's checkout 7173934.
  Only `tool_calls` differs (144 vs 148): the real run also had observe calls outside the step loop.
- Sat: run_ed.py imports `mcp`; the adapter stubs those modules during import so no new dependency.
- Sat: `frontend/tools/ruff.toml` excludes run_ed.py so ruff never rewrites the model's code.
- Sat: a policy that returns None (do-nothing) gets `[]` steps for the remaining ticks: same sim events
  and reward, and one replay tick per sim tick. Only score.ended/tool_calls differ from a real stop.
- Sat: do-nothing is not in `--all` (SHIPPED): its replay is ~1.6 MB, over the ~1.5 MB budget, and
  every remaining field is required by types.ts. `--policy do-nothing` still writes it.

## Handoff
- Regenerate: `PYTHONPATH="ed72/environment/hospital;ed72/solution;eval/baselines" uv run --no-project --python 3.12 python frontend/tools/export_replay.py --all`
- Test: same PYTHONPATH, `uv run --no-project --python 3.12 --with pytest python -m pytest frontend/tools -q`
- The tests fail if a shipped replay is stale, so rerun `--all` after any sim or policy change.
