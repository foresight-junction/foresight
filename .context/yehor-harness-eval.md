# Branch: yehor/harness-eval

- **Issue:** #23
- **Owner:** yehor
- **Agent:** yehor-claude-3d
- **Parent branch:** main
- **Created:** Sat 16:52

## Goal
`make eval` reproduces the reported results (reference, do-nothing, stop-early, 3 agent runs) and writes `eval/results/summary.md`, on a fresh clone with Docker, uv and one API key.

## Files and folders I own
- `Makefile`, `eval/run_all.sh`, `eval/summarise.py`, `eval/tests/`, `eval/pyproject.toml`, `eval/uv.lock`, `eval/results/.gitkeep`, this file
- Granted by the coordinator Sat 17:20: `.gitignore` (`eval/results/jobs/`), `.env.example` (`ED72_MODEL`, `HARBOR`)

## Don't touch
- `eval/baselines/` (#12), `ed72/` (#21/#22/#31), `docs/` (including the CONTRACTS env table: its owner adds the rows)

## Contracts used or changed
- Reads the CONTRACTS v1 score object (`reward`, `O/T/W/B`, `totals.died/faints`, `ended`) from `verifier/score_full.json`, falling back to `artifacts/evidence/report.json`. No changes.
- New host-only env vars `ED72_MODEL` and `HARBOR` (optional). Both are in `.env.example` and were announced on #1 (additive). The CONTRACTS env table is left for its owner, as the contract-change skill wants contract edits in their own PR.

## Status
- [x] Verify Harbor 0.25.0 output layout (source + spike jobs)
- [x] `eval/summarise.py` + tests
- [x] `eval/run_all.sh` + `Makefile`
- [x] End-to-end `make eval-baselines` on the #21 spike fixture task (temporary copy)
- [ ] Real `make eval-baselines` on `ed72/` once #22 (+ #11 verifier, #16 reference) merge
- [ ] Stop-early once #12 ships `eval/baselines/ed72_baselines/harbor_agent.py:StopEarlyAgent`

## Decisions and notes
- Sat 17:00: Harbor runs as `uvx --python 3.12 --from harbor==0.25.0 harbor` (the #21 spike's pinned install), OpenCode as `--ak version=1.19.5`. `HARBOR=...` overrides the command.
- Harbor layout (harbor/models/trial/paths.py, checked against real spike jobs): `<jobs>/<job>/<trial>/{config.json (trial_name), result.json (TrialResult), verifier/reward.txt, verifier/score_full.json, artifacts/evidence/report.json}`. A trial without `result.json` is still running and is left out.
- A trial with no reward counts as 0, as Harbor's own `Mean` metric does (`harbor/metrics/base.py`).
- Each run writes to `eval/results/jobs/<timestamp>/`, so reruns never resume an old job. That folder is Harbor output and must not be committed: `eval/results/jobs/` needs a `.gitignore` line (asked on #23).
- Stop-early hook (changed Sat 17:25 to fit PR #52's `ed72_baselines` package): run_all.sh runs `-a ed72_baselines.harbor_agent:StopEarlyAgent` with `PYTHONPATH=eval/baselines` when `eval/baselines/ed72_baselines/harbor_agent.py` exists, otherwise prints SKIP. Posted on #12; PR #52 has no Harbor agent yet.
- Sat 17:05 (Codex CLI review): Harbor can exit 0 with errored trials, so summarise.py exits 3 when any finished trial has no reward (test.sh always writes one). Errors column = any Harbor exception or no reward.
- `.env` fills only unset vars and Harbor's `--env-file` is not passed: Harbor loads it with `override=True` (harbor/cli/jobs.py), so an empty `KEY=` from `.env.example` would blank a shell key.
- `eval/pyproject.toml` (stdlib uv project) sets `testpaths = ["tests"]`, so CI's per-project pytest in `eval/` collects only `eval/tests`, and `eval/baselines/` runs its own tests.

## Handoff
- State: PR #53 is ready for review, issue #23 is labelled `review`, and Kostiantyn (@xand1ex999) merges. CI is green (hospital 73 tests, eval 7, each run once). On a local merge with #52, `eval/baselines` collects its 27 tests once.
- Done: summarise.py (7 tests), run_all.sh (checks first for a running Docker, uv, `ed72/task.toml`, and for `all` `ED72_MODEL` plus its provider key), Makefile `eval` / `eval-baselines` / `eval-summary` (`JOBS=<dir>`, default latest run), `eval/pyproject.toml`, `.gitignore` and `.env.example` entries.
- Verified: `make eval-baselines` end to end on the spike v1 fixture as `ed72/` in a temp copy (oracle 1.0, nop 0.0). The agent target was never run (it costs money).
- Next: once #58 merges, merge main in, run `make eval-baselines`, and paste `eval/results/summary.md` into PR #53. When #52 adds `eval/baselines/ed72_baselines/harbor_agent.py:StopEarlyAgent`, check that stop-early runs. Add the CONTRACTS env rows for `ED72_MODEL` / `HARBOR` (announced on #1) through the owner or a contract PR.
- Test: `cd eval && uv run --with pytest pytest -q`, then `make eval-baselines`.
