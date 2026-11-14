# Branch: kostiantyn/harness-stop-early

- **Issue:** #83
- **Owner:** kostiantyn
- **Agent:** kostiantyn-codex-83
- **Parent branch:** main
- **Created:** Sat 21:11

## Goal
Run the existing 12-tick stop-early policy through Harbor's public tools. Require complete baselines and integrate #105's planned/per-attempt manifests before model calls.

## Files and folders I own
- eval/run_all.sh; eval/tests/test_run_all.py
- eval/baselines/ed72_baselines/harbor_agent.py and ward_driver.py
- eval/baselines/tests/test_harbor_agent.py; eval/baselines/pyproject.toml and uv.lock
- This context file.

## Don't touch
- Simulator, scorer, public contracts and reference policy.
- eval/manifest.py and eval/summarise.py belong to #105 (Mykhailo).
- Provider/budget documentation belongs to #37; release selection belongs to Yehor.

## Contracts used or changed
Uses v1 rules/observe/step, 500-call cap and existing provider environment variables; no public contract changes planned.

## Status
- [x] Claimed #83 from main 346f677; requested #105 API and #37 settings in English.
- [x] Adapter, fail-fast preflight and documented #105 plan/write integration.
- [x] Real Harbor stop-early smoke: 0.058304, 14 calls, agent_stopped, zero exceptions.
- [x] Baseline tests 122 passed; evaluator/runner tests 44 passed (32 runner scenarios).
- [ ] Independent reviews, gated commit/push, PR handoff to Yehor.

## Decisions and notes
- Yehor alone merges/orchestrates (latest #39/#83 instruction supersedes old role text). No paid batch or self-merge.
- Reuse StopEarly rather than duplicate the policy. Only public baseline modules are copied to main.
- Harbor 0.26.0 is the existing runner dependency; add it to baseline test dependencies to verify the real custom-agent API.
- Depends on #120 (#105 manifest API) before this runner can execute; #112 supplies host seed interpolation.
- Required baseline reports are checked before paid runs, even if Harbor returns zero with trial exceptions.
- Shell exit status is retained in each job's harbor-exit-code.txt; API/schema semantics remain with #105.
- Independent Codex review fixed nullable streams and MCP capabilities; final review found no further issues.
- Claude cross-review: retain ward's stderr on nonzero exit and stdout-only adapter failures (fixed). Its repeat-count finding is declined: #105 explicitly documents repeat=1 on a job manifest for Harbor -k3; plan entries carry all repeats.
- noslop: removed error paths that discarded ward diagnostics; no public rule or contract changed.

## Handoff
Adapter/preflight/runner integration implemented and reviewed. Next: gated commit, sync current main, test against merged #120 and hand PR to Yehor. Test: `uv run --with pytest pytest -q` in eval and eval/baselines; `bash -n eval/run_all.sh`. Smoke logs: eval/results/jobs/stop-early-83-smoke-v2 (gitignored). No paid batch or merge performed. Worktree is occupied.
