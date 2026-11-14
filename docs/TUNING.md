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

## Update, Sat 14 Nov 22:40: proposal to move the default to 4.0 (issue #69)

Status: proposed on `yehor/ref-gap-planner`. The difficulty value is Kostiantyn's decision.

### Why reopen it

A local run of OpenCode with Kimi K3.1 Pro on seed 42 at 3.0 scored **0.9876**; the oracle scored 0.9896. The model made 144 `step` calls with no exploit, no deaths and no faints. Gemini 3.8 Flash scored 0.8117 on the same seed. At 3.0 a strong model has no gap.

At 3.0 the two slow resources never bind. In the reference run on seed 42 the most tired person peaks at fatigue 31 (tired starts at 60) and spend is €7 000 of €12 000, so W and B are a free 20 points and turn-by-turn severity-first play is enough.

Doctor time is the limit. With full zones a patient needs about 1.05 doctor-ticks (0.04·6 + 0.14·2 + 0.34·1 + 0.30·0.5 + 0.18·0.25). A doctor who stays fresh works 2.5 / (2.5 + 1.6) = 61% of ticks, so six doctors supply about 3.66 doctor-ticks per tick. The permanent team saturates near 3.5 arrivals per tick. Above that, the score depends on buying agency cover in time (4 ticks of delay, 16 of stay), on deciding when leaving the budget pays, and on keeping staff under the tired threshold. All of these follow from handbook numbers.

### What changes

- `arrival_mean` 3.0 → 4.0. No other knob, rule, tool or score change.
- The reference plans for scarcity (`ed72/solution/policy.py`): it keeps permanent staff under fatigue 50 unless an ESI 1–2 patient would go uncovered, and orders agency staff whenever four or more patients go uncovered and no fresh person of that role is left. It stays within the budget until eight or more are uncovered, then spends up to €16 000. It reads only the observation.

### Scores at 4.0 (out of 100, local sim, no model)

| Policy | Seed 42 | Seed 1 | Seed 2 | Seed 3 | Seed 4 | Seed 5 |
|---|---:|---:|---:|---:|---:|---:|
| Reference (this branch) | 94.02 | 93.37 | 88.59 | 94.01 | 92.67 | 94.05 |
| Previous reference (main) | 57.29 | 71.55 | 64.16 | 67.46 | 57.14 | 64.36 |
| Severity-first | 29.28 | 30.58 | 26.06 | 29.83 | 37.45 | 32.44 |
| Reactive proxy | 48.05 | 47.33 | 44.69 | 50.12 | 49.66 | 47.43 |
| Stop-early | 5.83 | 4.23 | 5.37 | 5.01 | 4.73 | 5.11 |
| Do-nothing | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| Divert-all | 44.75 | 48.75 | 48.99 | 44.35 | 46.02 | 43.20 |
| Rest-in-quiet-periods | 29.28 | 29.81 | 26.06 | 40.23 | 34.55 | 33.66 |
| Admit-light-only | 14.68 | 11.81 | 11.66 | 11.07 | 12.86 | 12.13 |
| Admit-without-coverage | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| Fill-beds-at-last-tick | 1.98 | 1.77 | 1.69 | 1.68 | 1.71 | 1.69 |
| Spend-to-limit | 39.61 | 46.78 | 34.31 | 43.12 | 46.15 | 35.64 |
| Random | 5.15 | 4.71 | 4.81 | 6.50 | 5.35 | 4.74 |

Do-nothing is 0, stop-early is below the reactive proxy, and the reference beats the reactive proxy and every exploit on all six seeds. Divert-all's worst score is 48.99. The same seed and actions give the same score.

Reference mean and range on twelve seeds (42, 1–11), by arrival mean:

| Arrival mean | Reference (this branch) | Previous reference (main) |
|---|---|---|
| 3.0 | 98.4 (96–100) | 96.6 (86–100) |
| 3.6 | 95.3 (90–98) | 79.0 (58–98) |
| 3.8 | 92.6 (82–96) | 68.7 (52–94) |
| 4.0 | 92.0 (84–95) | 60.6 (49–72) |

The previous reference plays about as well as Kimi did at 3.0 (98.96 against 98.76 on seed 42), so its row is the nearest scripted estimate of a strong model that keeps playing turn by turn. A stronger stand-in, the previous reference plus hiring two doctors and a nurse whenever ten patients wait, averages 72.7 (58–86) at 4.0. Neither is a model run.

### Not measured yet

No model has been run at 4.0. The Kimi and Gemini scores above are at 3.0. The gap at 4.0 needs one agent run per model before the README table is updated.
