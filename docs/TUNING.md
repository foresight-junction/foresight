# Difficulty screening (issue #67)

## Decision

Kostiantyn selected **3.0 arrivals per tick** for the default, with the remaining knobs unchanged. The scores below compare candidate configurations on seeds 1–5. Held-out seeds and model performance still need their separate evaluation.

## Method and source pins

- Base tree: `origin/main` **d1986f054adc9ca4c06ed3863a4e04c7ecac80c9**, containing merged baseline runner (#52) and config loader (#64).
- Reference: only [`ed72/solution/policy.py` from `kostiantyn/ref-policy` at `cc53151`](https://github.com/xand1ex999/guinness/blob/cc53151a31fb6db8557b1a9c65274f63580c922a/ed72/solution/policy.py) was overlaid in the temporary run tree. Its `ReferencePolicy.actions(obs)` was adapted to the baseline runner's `act(obs)` method. The policy used only the public observation.
- Idle-then-fill probe: `greedy_actions` from [red-team commit `407ffd7`](https://github.com/xand1ex999/guinness/blob/407ffd7e988ea965b3e7b77896f9978569b9d79d/ed72/environment/hospital/tests/test_redteam_round1.py); it returns no actions before tick 143, then staffs and fills from the final public observation.
- Seeds 1–5, exactly one changed knob (`arrival_mean`), all other `Config()` defaults unchanged. The 2.45 and 2.475 rows include all five seeds; other initial screens at 2.1, 2.4, 2.5, 2.7, and 2.575 helped bracket the transition.
- Policies are the merged `eval/baselines/` classes: severity-first, reactive proxy, stop-early, do-nothing, divert-all, rest-in-quiet-periods, admit-light-only, admit-without-coverage, fill-beds-at-last-tick, spend-to-limit, and seeded random, plus the reference and idle-then-fill probes above.
- Driver: from a disposable archive of the base commit, overlay the reference file with `git show cc53151a31fb6db8557b1a9c65274f63580c922a:ed72/solution/policy.py`, then from `eval/baselines/` run `PYTHONPATH=../../ed72/environment/hospital:../../ed72/solution uv run python -` with a `ConfiguredClient` that constructs `Simulation(generate_world(seed, dataclasses.replace(Config(), arrival_mean=mean)))`, calls `run_episode(client, policy)`, runs the tail with `sim.run_to_end()`, and scores `sim.events`. `ReferencePolicy.actions(obs)` is wrapped as `act(obs)`. The exact #62 greedy helper is linked above. No code or run artifacts from the temporary driver were retained.

The same integer seed makes each candidate reproducible; changing `arrival_mean` changes the number and order of draws in the arrivals stream, so these are deterministic candidate-specific worlds rather than identical patient-by-patient worlds. Do not infer monotonic score changes from adjacent values. [PR #73's later F1 attribution fix](https://github.com/xand1ex999/guinness/pull/73) was not in the base tree; it only changes a failure label, not numeric reward components.

## Per-seed scores

Scores are out of 100.

### `arrival_mean = 2.45`

| Policy | Seed 1 | Seed 2 | Seed 3 | Seed 4 | Seed 5 |
|---|---:|---:|---:|---:|---:|
| Reference | 98.64 | 99.38 | 100.00 | 97.53 | 98.20 |
| Severity-first | 84.43 | 85.70 | 74.43 | 51.73 | 64.53 |
| Reactive proxy | 65.27 | 71.11 | 62.57 | 63.22 | 67.16 |
| Stop-early | 3.54 | 5.57 | 5.40 | 3.63 | 5.08 |
| Do-nothing | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| Divert-all | 44.98 | 52.45 | 53.47 | 46.25 | 44.13 |
| Rest-in-quiet-periods | 85.46 | 88.80 | 84.38 | 83.15 | 85.95 |
| Admit-light-only | 11.29 | 11.53 | 11.72 | 11.03 | 11.43 |
| Admit-without-coverage | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| Fill-beds-at-last-tick | 3.30 | 2.70 | 2.96 | 2.65 | 2.53 |
| Spend-to-limit | 74.97 | 84.28 | 65.83 | 63.02 | 83.53 |
| Random | 8.53 | 6.38 | 5.97 | 7.88 | 11.57 |
| Idle-then-fill (#62) | 3.30 | 2.70 | 2.96 | 2.65 | 2.53 |

Reference beats every listed baseline on all five seeds; severity-first is below 90 on all five. Divert-all's worst score is **53.47**, above the roughly 47-point target.

### `arrival_mean = 2.475`

| Policy | Seed 1 | Seed 2 | Seed 3 | Seed 4 | Seed 5 |
|---|---:|---:|---:|---:|---:|
| Reference | 98.30 | 98.28 | 99.42 | 97.52 | 98.16 |
| Severity-first | 81.35 | 79.28 | 72.78 | 51.86 | 87.84 |
| Reactive proxy | 62.01 | 70.79 | 63.53 | 62.94 | 68.06 |
| Stop-early | 3.36 | 5.41 | 5.38 | 3.64 | 5.17 |
| Do-nothing | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| Divert-all | 43.16 | 49.97 | 56.27 | 46.65 | 44.74 |
| Rest-in-quiet-periods | 83.44 | 86.38 | 80.08 | 84.65 | 89.53 |
| Admit-light-only | 10.77 | 11.69 | 12.33 | 11.17 | 11.87 |
| Admit-without-coverage | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| Fill-beds-at-last-tick | 2.74 | 2.62 | 2.70 | 2.66 | 2.57 |
| Spend-to-limit | 73.97 | 70.81 | 66.19 | 63.16 | 82.17 |
| Random | 9.31 | 5.82 | 6.46 | 8.10 | 10.53 |
| Idle-then-fill (#62) | 2.74 | 2.62 | 2.70 | 2.66 | 2.57 |

Reference beats every listed baseline on all five seeds; severity-first is below 90 on all five. Divert-all's worst score is **56.27**, above target.

### `arrival_mean = 3.0`

| Policy | Seed 1 | Seed 2 | Seed 3 | Seed 4 | Seed 5 |
|---|---:|---:|---:|---:|---:|
| Reference | 99.69 | 98.79 | 99.43 | 96.78 | 97.54 |
| Severity-first | 60.77 | 54.09 | 43.05 | 46.26 | 56.78 |
| Reactive proxy | 57.76 | 62.73 | 61.75 | 59.61 | 67.16 |
| Stop-early | 3.84 | 4.04 | 5.54 | 5.67 | 4.66 |
| Do-nothing | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| Divert-all | 45.56 | 47.51 | 47.93 | 43.09 | 42.97 |
| Rest-in-quiet-periods | 70.46 | 55.78 | 72.72 | 70.71 | 70.90 |
| Admit-light-only | 11.29 | 12.79 | 11.43 | 12.63 | 13.49 |
| Admit-without-coverage | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| Fill-beds-at-last-tick | 2.30 | 2.45 | 2.24 | 2.46 | 2.37 |
| Spend-to-limit | 61.73 | 63.66 | 53.36 | 63.43 | 61.09 |
| Random | 10.35 | 5.61 | 7.15 | 7.00 | 9.72 |
| Idle-then-fill (#62) | 2.30 | 2.45 | 2.24 | 2.46 | 2.37 |

At 3.0, do-nothing is 0, stop-early is below reactive proxy, the reference beats reactive and every exploit on all five seeds, and divert-all's worst score is **47.93**. Severity-first is at most 60.77. This candidate passes the tested score ordering, though severity-first falls below reactive proxy on four of five seeds; the #69 aspiration that reactive remain below severity-first is not met. Idle-then-fill remains below 0.05 reward (max 2.46 points).

## Why 3.0

The selected configuration produced the strongest separation between the reference and the tested baselines while keeping divert-all near 47 points. The reference outscored the reactive proxy and every exploit on all five seeds. The original red-team greedy comparison remains pinned to its 1.5-arrival setup. The tables above cover the new default.
