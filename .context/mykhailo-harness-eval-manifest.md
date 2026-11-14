# Branch: mykhailo/harness-eval-manifest

- **Issue:** #105
- **Owner:** mykhailo
- **Agent:** lead
- **Parent branch:** main
- **Created:** Sat 20:44

## Goal
#105 (D12): eval summaries keep seed, config and instruction identity; rows never pool across them.

## Files and folders I own
- eval/manifest.py, eval/summarise.py, eval/tests/test_summarise.py, eval/tests/test_manifest.py, eval/MANIFEST.md

## Don't touch
- eval/run_all.sh, Makefile, eval/baselines/, eval/results/

## Contracts used or changed
Anything from docs/CONTRACTS.md this branch depends on or changes.
- 

## Status
- [x] manifest.py (derive + write_manifest CLI)
- [x] summarise.py groups by policy/model/seed/config/instruction; gaps match identity
- [x] tests (11 pass)
- [x] schema 2 manifest (seed_source, hashes, runtime, model/repeat), plan.json, completeness + exit 4 (subagent mykhailo-claude-1s)
- [ ] runner hook: Kostya (#83) is sole editor of run_all.sh; calls in eval/MANIFEST.md

## Decisions and notes
- Authority: Yehor is sole merger/orchestrator; no PRs or merges from this branch without his hand-off.
- Host ED72_SEED counts only if compose interpolates it; a literal compose seed wins (compose_literal).
- Harbor 0.26.0 result.json records task_id.path, task_checksum, agent_info, config.agent; NOT the seed or config. Seed comes from ED72_SEED in <task>/environment/docker-compose.yaml (bare `ed72` = 42, `ed72-s<N>` name as fallback). So manifest.json written at run time is the reliable source; deriving later reads the live task dir and can drift.
- Missing seed/config/instruction shows `unknown`; such rows are never compared in the gap list.

## Handoff
- Done: module, summarise changes, tests. Test: `cd eval && uv run --no-project --python 3.12 --with pytest python -m pytest -q`.
- Needed in eval/run_all.sh (Kostya only): `manifest.py plan` before the first harbor run, `manifest.py write` after each run; exact calls in eval/MANIFEST.md.
