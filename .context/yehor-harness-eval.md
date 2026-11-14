# Branch: yehor/harness-eval

- **Issue:** #23
- **Owner:** yehor
- **Agent:** yehor-claude-3d
- **Parent branch:** main
- **Created:** Sat 16:52

## Goal
`make eval` reproduces the reported results (reference, do-nothing, stop-early, 3 agent runs) and writes `eval/results/summary.md`, on a fresh clone with Docker, uv and one API key.

## Files and folders I own
- `Makefile`, `eval/run_all.sh`, `eval/summarise.py`, `eval/tests/`, `eval/results/.gitkeep`, this file

## Don't touch
- `eval/baselines/` (#12), `ed72/` (#21/#22/#31), `docs/`, `.env.example`, `.gitignore`

## Contracts used or changed
- Reads the CONTRACTS v1 score object (`reward`, `O/T/W/B`, `totals.died/faints`, `ended`) from `verifier/score_full.json`, falling back to `artifacts/evidence/report.json`. No changes.
- New host-only env var `ED72_MODEL` (and the `HARBOR` command override). Not yet in `.env.example`: asked on #23.

## Status
- [x] Verify Harbor 0.25.0 output layout (source + spike jobs)
- [x] `eval/summarise.py` + tests
- [x] `eval/run_all.sh` + `Makefile`
- [x] End-to-end `make eval-baselines` on the #21 spike fixture task (temporary copy)
- [ ] Real `make eval-baselines` on `ed72/` once #22 (+ #11 verifier, #16 reference) merge
- [ ] Stop-early once #12 ships `eval/baselines/harbor_agent.py:StopEarlyAgent`

## Decisions and notes
- Sat 17:00: Harbor runs as `uvx --python 3.12 --from harbor==0.25.0 harbor` (the #21 spike's pinned install), OpenCode as `--ak version=1.19.5`. `HARBOR=...` overrides the command.
- Harbor layout (harbor/models/trial/paths.py, checked against real spike jobs): `<jobs>/<job>/<trial>/{config.json (trial_name), result.json (TrialResult), verifier/reward.txt, verifier/score_full.json, artifacts/evidence/report.json}`. A trial without `result.json` is still running and is left out.
- A trial with no reward counts as 0, as Harbor's own `Mean` metric does (`harbor/metrics/base.py`).
- Each run writes to `eval/results/jobs/<timestamp>/`, so reruns never resume an old job. That folder is Harbor output and must not be committed: `eval/results/jobs/` needs a `.gitignore` line (asked on #23).
- Stop-early hook: run_all.sh runs `-a eval.baselines.harbor_agent:StopEarlyAgent` with `PYTHONPATH=<repo>` when `eval/baselines/harbor_agent.py` exists, otherwise prints SKIP. Proposed on #12.
- CI runs pytest only inside folders with a `pyproject.toml`; `eval/tests` runs in CI once `eval/pyproject.toml` exists (asked on #23).

## Handoff
- Done: summarise.py (5 tests), run_all.sh (preflight: Docker running, uv, `ed72/task.toml`, `ED72_MODEL` plus its provider key for `all`), Makefile targets `eval`, `eval-baselines`, `eval-summary` (`JOBS=<dir>`, default latest run).
- Verified: `make -n eval`, `bash -n eval/run_all.sh`, ruff, pytest. `make eval-baselines` ran end to end against the spike v1 fixture copied to `ed72/` in a temp dir (oracle 1.0, nop 0.0, stop-early skipped, summary written). The agent target was not run (costs money); its missing-model and missing-key failures were checked.
- Next: once #22 merges, rebase and run `make eval-baselines` for real; once #12 lands, check the stop-early import path.
- Test: `uv run --no-project --python 3.12 --with pytest pytest -q eval/tests`, then `make eval-baselines`.
