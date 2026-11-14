# Findings for Kostya's issue triage

These seven findings were verified at the commits named below. Before creating new issues, check whether the linked owner issue already tracks the fix or whether a later commit resolves it. The stop-early integration gap and refused-log problem already had owner threads; their evidence here extends those threads. Three optional extra-event findings concern a deferred branch, not the shipped default game.

## Proposed issue titles

1. [P1] Exclude solution virtualenvs from Harbor task inputs.
2. [P1] Fail evaluation when the required stop-early baseline is unavailable.
3. [P2] Preserve seed identity in evaluation summaries.
4. [P2] Bound retained bytes for refused tool calls.
5. [P2] Package compact-layout files in the hospital image.
6. [P2] Compute F1 using actual resus capacity and closures.
7. [P2] Make zero-warning monitor closures observable or reject that configuration.

## Evidence, reproduction and suggested fixes

### Owner issue #22

[Original review comment](https://github.com/xand1ex999/guinness/issues/22#issuecomment-6880688691)

[yehor-codex-review] to kostiantyn-codex-0 and kostiantyn-claude-4: [P1] normal solution tests make the Harbor task invalid; verified fix below. Refs #88.

@xand1ex999 Reviewed main `b6234af4011eb1276b976605b0b31c94a23c7de8`. A clean snapshot runs correctly, but running the normal `uv run --with pytest pytest -q` in `ed72/solution` creates `.venv/bin/python3`, which points outside the task. Harbor 0.25.0 validates the solution input tree before launching and rejects this symlink. Both reference and nop then fail before starting, and `make eval-baselines` reports `ValueError: Either datasets or tasks must be provided.` The underlying validation error is `Input paths must stay within the task: .../ed72/solution/.venv/bin/python3`.

Trigger: the [solution Python project](https://github.com/xand1ex999/guinness/blob/b6234af4011eb1276b976605b0b31c94a23c7de8/ed72/solution/pyproject.toml#L1-L9) followed by the [Harbor launch](https://github.com/xand1ex999/guinness/blob/b6234af4011eb1276b976605b0b31c94a23c7de8/eval/run_all.sh#L72-L83). Git's `.gitignore` does not apply to Harbor's solution-input filtering.

Reproduce:
```sh
(cd ed72/solution && uv run --python 3.12 --with pytest pytest -q)
make eval-baselines
```

Suggested fix: add `ed72/solution/.harborignore` with `.venv/`, `__pycache__/`, and `.pytest_cache/` (or export a clean task before every Harbor run). I tested the ignore-file approach in the temporary snapshot: `Task.is_valid_dir(Path("ed72"))` changes from false to true with the existing virtualenv still present. Add a regression that creates a solution virtualenv and validates the packaged task. No repository files were changed by this review.

Control: pristine same-commit snapshot completed both Docker runs with reference **0.989617**, nop **0.0**, zero exceptions. Thus this is a reproducibility failure after the documented development workflow, not a simulator failure.

### Owner issue #83

[Original review comment](https://github.com/xand1ex999/guinness/issues/83#issuecomment-6880690005)

[yehor-codex-review] to kostiantyn-codex-0 and kostiantyn-claude-4: [P1] confirmed stop-early is missing from the successful one-command evaluation. Refs #88, #23.

@xand1ex999 On main `b6234af`, a pristine `make eval-baselines` run with Harbor 0.25.0 completed reference **0.989617** and nop **0.0**, then printed `SKIP stop-early: .../eval/baselines/ed72_baselines/harbor_agent.py not found` and exited **0**. The summary contains only two finished trials. This confirms the existing #83 integration gap through the real Docker path.

The [skip branch at eval/run_all.sh:85–89](https://github.com/xand1ex999/guinness/blob/b6234af4011eb1276b976605b0b31c94a23c7de8/eval/run_all.sh#L85-L89) never appends to `FAILED`, so the advertised full baseline command can claim success without a required judge baseline.

Suggested fix: supply the Harbor stop-early adapter using the existing 12-tick policy, and fail preflight before launching jobs if any required policy is missing. Check the final job set, not just rewards of whichever jobs happened to run. Acceptance: the baseline command produces exactly reference, nop and stop-early, each with a verifier score; deleting the adapter makes the command fail rather than silently produce an incomplete table.

No duplicate issue opened; this belongs to #83. No source changes or merges made.

### Owner issue #23

[Original review comment](https://github.com/xand1ex999/guinness/issues/23#issuecomment-6880796659)

[yehor-codex-review] to kostiantyn-codex-0: [P2] distinct seed runs collapse into one summary group. Refs #88, #18, #26.

@xand1ex999 At main b6234af, [load_trial](https://github.com/xand1ex999/guinness/blob/b6234af4011eb1276b976605b0b31c94a23c7de8/eval/summarise.py#L100-L118) reads the seed only from `report['seed']`. The current scorer does not emit that field, so every real run is assigned `'-'`. [build_rows](https://github.com/xand1ex999/guinness/blob/b6234af4011eb1276b976605b0b31c94a23c7de8/eval/summarise.py#L154-L157) then combines distinct task seeds under the same policy/model. Both actual Docker runs in this review showed Seed `-`.

Verified with temporary copies of the actual completed Harbor metadata: task paths `/tasks/ed72-s1` and `/tasks/ed72-s2`, with illustrative rewards 0.9 and 0.5, produced one row `(seed='-', runs=2, mean=0.7)`. These illustrative values are a grouping reproduction, not new measured game scores. This loses per-seed ranges and can compare unmatched seed mixes when some matrix runs fail or are absent.

Suggested fix: preserve an explicit evaluator-side task-to-seed manifest and read it when summarising (or add seed metadata to the hospital-only score artifact through the contract workflow). Do not expose the seed in public tools. Keep unknown seed identity distinct per task rather than pooling unrelated runs. Add a two-task regression with the current score shape and verify separate seed rows and matched reference/model gaps.

### Owner issue #14

[Original review comment](https://github.com/xand1ex999/guinness/issues/14#issuecomment-6880797869)

[yehor-codex-review] to mykhailo-claude-1 and kostiantyn-claude-4: [P2] E1's action-count fix does not bound refused-call log bytes. Refs #88, PR #82.

@xand1ex999 Reviewed branch `mykhailo/reward-redteam-2` at `97ee2a3e1cde9ddcbf99bfbe9fc22bdb1402022e`. [server.py:54–58](https://github.com/xand1ex999/guinness/blob/97ee2a3e1cde9ddcbf99bfbe9fc22bdb1402022e/ed72/environment/hospital/server.py#L54-L58) keeps the first 50 action objects, including arbitrary extra fields. A bounded local test through the real FastMCP HTTP app sent one refused action containing a 100,000-character extra field after the cap: response `call_cap_reached`, tick unchanged, **100,145 bytes appended to the event log**. No load/stress test was needed. Further calls after the cap also keep being logged.

This is an incomplete repair of the pre-existing log-growth problem, not evidence of a reward-increasing exploit. The 4 MiB HTTP request limit and the 50-action count do not provide a useful per-record byte bound.

Suggested fix: record refused steps with empty arguments or a compact reason/count record, since collect.py never replays their actions. Set a byte/depth bound or normalize the retained fields for successful/rejected action logs as well; define bounded post-cap logging without losing the call-cap outcome. Add a regression using one large action, asserting serialized log bytes rather than only action count. Update REDTEAM's claim accordingly.

Separate verification note: the full branch hospital suite gave **468 passed, 1 skipped, 1 xfailed, 1 failure**. The failure is the already-known strict XPASS in `test_a_step_that_advanced_the_tick_does_not_reply_with_an_error`; update/remove the stale xfail based on the currently pinned framework behavior before considering this branch green. I am not reporting N5/N6 as newly established exploits.

### Owner issue #9

[Original review comment](https://github.com/xand1ex999/guinness/issues/9#issuecomment-6880799119)

[yehor-codex-review] to mykhailo-claude-1: three verified prerequisites before enabling the deferred extra-events branch. Refs #88, PR #84.

@xand1ex999 Reviewed `mykhailo/env-extra-events` at `2df7b8a8543738d7f891c400a86674ca17b3cd6b`. These are **deferred-feature findings**, not claims that the current default task is broken. The branch hospital suite passes all 381 tests.

1. **[P2] Compact layout is missing from the hospital image.** [layouts.py:11–24](https://github.com/xand1ex999/guinness/blob/2df7b8a8543738d7f891c400a86674ca17b3cd6b/ed72/environment/hospital/ed72_sim/rules/layouts.py#L11-L24) loads `/app/config/layouts/compact.json`, but the [Dockerfile](https://github.com/xand1ex999/guinness/blob/2df7b8a8543738d7f891c400a86674ca17b3cd6b/ed72/environment/hospital/Dockerfile#L11-L15) never copies config/layouts and Compose supplies no mount. The source tree returns `(2,9,6)`; the same loader with the image's absent layout directory raises `unknown layout 'compact'`. Copy the layout files into the hospital image and test config/world loading and collector replay there. Default layout works because it bypasses the file.

2. **[P2] F1 misses resus blocking with reduced capacity.** [failures.py:54–57](https://github.com/xand1ex999/guinness/blob/2df7b8a8543738d7f891c400a86674ca17b3cd6b/ed72/environment/hospital/ed72_sim/scoring/failures.py#L54-L57) still requires three occupied resus beds. Deterministic reproduction: two ESI 3 patients occupy all usable resus beds, an ESI 1 arrives, admission returns `no_free_bed`, and the ESI 1 dies waiting. F1 is **0** with compact layout and **0** with a monitor fault closing R3; the three-bed default control gives **1**. Reward is unaffected, but analysis is wrong. The proposal acknowledges F6's constant-capacity gap; carry actual layout/closure state into log-based analysis for F1 too, with both regression cases.

3. **[P2, zero-warning config only] Monitor faults can hide current availability.** Config accepts `warning: 0`, [_beds](https://github.com/xand1ex999/guinness/blob/2df7b8a8543738d7f891c400a86674ca17b3cd6b/ed72/environment/hospital/ed72_sim/observation.py#L36-L40) omits closure state, and [warnings](https://github.com/xand1ex999/guinness/blob/2df7b8a8543738d7f891c400a86674ca17b3cd6b/ed72/environment/hospital/ed72_sim/observation.py#L84-L87) excludes zero-warning events even while active. Otherwise identical worlds with/without a tick-0 monitor fault produced identical complete public observations, although one had R3 closed. Expose active availability, include active zero-warning events, or reject that configuration until represented. The default three-tick warning is inferable with the proposed handbook rule and is not the case reported here.

No feature changes or merge requested during the freeze; these notes are for the existing owner and Kostya's prioritization.


## Additional validated findings from Argon's supplied review

[Full validation, source links, reproduction evidence and fixes](argon-validation.md). These six items are additional to the original seven above, validated against main `474829afe5f9b5bf5b10f18561ce149c634a957f`:

1. A1 [P2] Reject nonfinite numeric configuration before world generation.
2. A2 [P3] Extend the main-branch push hook's ordinary-command coverage.
3. A3 [P3] Validate worktree-removal slugs and encode status query values.
4. A4 [P2] Read all versioned board-check inputs from the selected ref.
5. A5 [P2] Keep unused ticks separate from clinical failure counts in the SVG.
6. A6 [P2] Parse supported .env quoting without changing model/key values.

Kostya should create or reuse owner issues after triage. Argon's critical server/config claim is already fixed; its Bash 3.2 crash did not reproduce. The addendum records all twelve dispositions and corrections to the proposed fixes. No implementation changes are included.
