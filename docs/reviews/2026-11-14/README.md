# Repository review: 14 November 2026

Published on `yehor/docs-review-findings` for Kostya to triage and create follow-up issues. This preserves the completed review's fixed snapshots; it is not a fresh claim about changes made afterward.

- [Detailed findings and reproductions](findings.md)
- [Argon review validation: six additional items and all twelve dispositions](argon-validation.md)
- [Reviewed branch heads](branch-heads.json)
- [Original review task](https://github.com/xand1ex999/guinness/issues/88)

One-off review completed for @xand1ex999, requested by Yehor. Review performed with three Astra subagents on separate areas, with findings checked and consolidated before posting.

**Snapshot:** full main review and Docker runs at `b6234af4011eb1276b976605b0b31c94a23c7de8`. During the review, PRs #86, #85 and #79 merged. Their complete delta through `474829afe5f9b5bf5b10f18561ce149c634a957f` was reviewed and the affected suites rerun. The simulator, scorer, public server, reference and Harbor task were unchanged by that delta.

**Argon follow-up:** the supplied older review was validated against `474829a`. [The addendum](argon-validation.md) adds six scoped triage items (four P2, two P3), marks the critical configuration claim already fixed, rejects the Bash-array crash, and separates optional robustness from demonstrated defects. No supplied patch was applied.

**Original result:** seven actionable findings posted to existing owner issues, including two current run/reproduction blockers. During the review phase, no source changes, commits, merges or paid model calls were made. This branch subsequently publishes documentation only.

| Priority | Finding | Evidence and suggested fix |
|---|---|---|
| P1 | Running solution uv tests leaves a .venv symlink that makes Harbor reject the task | [#22 comment](https://github.com/xand1ex999/guinness/issues/22#issuecomment-6880688691). Verified solution .harborignore restores task validation. |
| P1 | make eval-baselines exits 0 while skipping required stop-early | [#83 comment](https://github.com/xand1ex999/guinness/issues/83#issuecomment-6880690005). Implement existing adapter task and fail preflight if required policies are absent. |
| P2 | Multi-seed summaries merge different seeds under '-' | [#23 comment](https://github.com/xand1ex999/guinness/issues/23#issuecomment-6880796659). Preserve evaluator-side seed identity and compare matched groups. |
| P2 | Refused-call log growth remains unbounded by bytes after the branch's 50-action fix | [#14 comment](https://github.com/xand1ex999/guinness/issues/14#issuecomment-6880797869). Log compact refused-call metadata and test a serialized-byte bound. No reward increase established. |
| P2, deferred feature | Compact layout data is absent from the hospital image | [#9 comment](https://github.com/xand1ex999/guinness/issues/9#issuecomment-6880799119). Copy layout files and test inside the image. |
| P2, deferred feature | F1 misses blocking when only two resus beds are usable | [#9 comment](https://github.com/xand1ex999/guinness/issues/9#issuecomment-6880799119). Replay actual layout/closure capacity for failure analysis. Reward unaffected. |
| P2, nondefault config | A zero-warning monitor fault hides current bed availability | [#9 comment](https://github.com/xand1ex999/guinness/issues/9#issuecomment-6880799119). Expose availability/active events or reject this configuration. Default warning case is not claimed broken. |

Also recorded: the known stale strict-xfail causes redteam2 to fail despite the asserted behavior passing; and [the preinstalled-agent proposal depends on Harbor 0.26 while main pins 0.25](https://github.com/xand1ex999/guinness/issues/37#issuecomment-6880822206). Existing stop-early/E1 findings were extended with fresh evidence rather than duplicated as new issues.

**Verification**

- Initial main: hospital 355 passed; solution 22 passed; baselines 106 passed (includes scorer ordering); eval 7 passed; analysis 10 passed. **500 passing project-test results**. Ruff lint, formatting and shell syntax passed.
- Latest integrated main `474829a`: affected projects rerun: analysis 10, ablations 24, eval 7, baselines 115, probes 18 passed. Ruff lint passed; 144 files formatted; seed-script suite passed.
- Real Docker/Harbor run from a pristine snapshot: Harbor **0.25.0**, Docker **29.9.2**, Python 3.12, macOS ARM64; seed **42**; reference **0.989617**, nop **0.000000**, no Harbor exceptions. Reference completed tick 143. Stop-early was skipped, so this is not a complete judge matrix.
- Dirty-after-tests control: same snapshot failed Harbor validation; temporary `ed72/solution/.harborignore` changed `Task.is_valid_dir` from false to true without removing the virtualenv.
- Extra-events branch: hospital **381 passed**. Additional deterministic reproductions established the capacity/visibility findings.
- Redteam2 branch: **468 passed, 1 skipped, 1 xfailed, 1 strict-XPASS failure**. Bounded local HTTP reproduction confirmed refused-log size.
- Ablation branch: **24 passed**. Its table with main's simulator/reference reproduced the published 3.0-arrival results.
- Probe branch: project **17 passed, 1 skipped** and hospital **349 passed, 1 skipped** before reference integration; after integration the probe project has **18 passed**.
- Probe measurement against main on seeds 1,2,3,4,5,42 passed all five-point reference-margin checks. Invalid-action policy scored zero. Reference scores: 99.6904, 98.7879, 99.4327, 96.7790, 97.5411, 98.9617. Source-seed replay is correctly excluded from foreign-seed comparisons.
- Independent normal-gameplay source review found no new verified error in tick order, coverage, fatigue, CT, agency/diversion timing, score arithmetic or reference decisions.

**Coverage and limits**

Inventoried all **51 remote branch heads** including main. Deep review covered the current ED-72 simulator, scoring, tools/CLI, collector/verifier, Docker/Harbor packaging, reference, baseline/evaluation/analysis code, CI and related tests, plus current branch changes:

| Branch | Reviewed head | Scope/result |
|---|---|---|
| kostiantyn/reward-exploit-probes | a67a7ce | Probe policies, measurement and tests; integrated and checked after #85 merged |
| mykhailo/harness-seeds | 5da7e31 | Script and tests; integrated and checked after #86 merged |
| mykhailo/ref-ablations | 29d633d | Runner, stand-in, tests and result reproduction; integrated and checked after #79 merged |
| mykhailo/env-extra-events | 2df7b8a | Full production diff, layout/events/tests, scoring/packaging interactions |
| mykhailo/reward-redteam-2 | 97ee2a3 | Production diff and red-team tests; includes env-server-config's c281e04 logging change |
| leonardodadenchik/harness-model-budget | 8fc2de7 | Estimate code and proposal/version compatibility; no paid measurements |
| yehor/harness-readme | 3e5bac3 | Draft README/demo instructions and current dependency/result limitations |
| mykhailo/ref-first-run | 5b56bf1 | Historical rehearsal evidence and its explicitly identified older integration snapshot |

Ancestor branches are covered through main. Older superseded documentation/stack branches were compared for relevant unique changes. `research`, `kostiantyn/env-ed-sim` and `kostiantyn/env-unfindable-slice` are historical research/prototypes explicitly excluded from the current ED-72 game by SPEC; they were inventoried and classified, **not given a fresh line-by-line audit or full legacy frontend/backend test run**. No claim is made to have run every historical branch independently.

No frontier-model run, full paid model/seed matrix, x86 Docker run or production deployment was performed. This is a fixed-snapshot review, not an ongoing watcher. Findings remain for the existing owners and Kostya to prioritize; completing this review does not mean those defects have been fixed.
