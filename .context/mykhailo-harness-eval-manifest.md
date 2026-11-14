# Branch: mykhailo/harness-eval-manifest

- **Issue:** #105
- **Owner:** mykhailo
- **Agent:** lead
- **Parent branch:** main
- **Created:** Sat 20:44

## Goal
#105 (D12): eval summaries keep seed, config and instruction identity; rows never pool across them.

## Files and folders I own
- eval/manifest.py, eval/summarise.py, eval/tests/test_summarise.py

## Don't touch
- eval/run_all.sh, Makefile, eval/baselines/, eval/results/

## Contracts used or changed
Anything from docs/CONTRACTS.md this branch depends on or changes.
- 

## Status
- [x] manifest.py (derive + write_manifest CLI)
- [x] summarise.py groups by policy/model/seed/config/instruction; gaps match identity
- [x] tests (11 pass)
- [ ] runner hook (owner of run_all.sh)

## Decisions and notes
- Harbor 0.26.0 result.json records task_id.path, task_checksum, agent_info, config.agent; NOT the seed or config. Seed comes from ED72_SEED in <task>/environment/docker-compose.yaml (bare `ed72` = 42, `ed72-s<N>` name as fallback). So manifest.json written at run time is the reliable source; deriving later reads the live task dir and can drift.
- Missing seed/config/instruction shows `unknown`; such rows are never compared in the gap list.

## Handoff
- Done: module, summarise changes, tests. Test: `cd eval && uv run --no-project --python 3.12 --with pytest python -m pytest -q`.
- Needed in eval/run_all.sh (not edited here), after each `harbor run` in run_job, with $job the job name:
  `python3 "$REPO_ROOT/eval/manifest.py" "$JOBS_DIR/$job" --task "$TASK_DIR" --harbor-version 0.26.0`
  (a per-seed task dir needs `--task` pointing at it; `--seed N` overrides.)
