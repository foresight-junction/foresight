# Post-submission code cleanup

- **Branch** `yehor/post-submission-code-cleanup`
- **Base** `5ab2d30`

## Goal

Improve readability in the simulator, scorer, reference policy, evaluation tools and replay viewer. Preserve the submitted rules, contracts and replay data.

## Handoff

- The cleanup covers `analysis/weak_seeds/`, simulator actions, scoring, RNG comments, the reference policy, the evaluator's JSON reader, viewer source and replay tools, and the seed generator.
- Ruff, shell syntax, seed-generator tests, all seven Python suites on Python 3.12, and the viewer typecheck, build and tests passed. Reference actions, events, score reports and weak-seed summaries matched the base across nine seeds.
- Run `ED72_SEED=3101 make eval-baselines` to reproduce the container check. The reference, do-nothing and stop-early scores were 95.86, 0.00 and 4.56.
- The cleanup is ready for the requested local integration into `main`.
