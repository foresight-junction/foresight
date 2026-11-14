# Difficulty tuning

## Gap tuning (Sat 14 Nov, after the first Gemini run)

**Why.** On the shipped seed 42 the reference scored 98.96 and Gemini 3.8 Flash scored 81.17 through OpenCode (`eval/results/2026-11-14-gemini-seed42/`). A gap of 17.8 points is too small for Break the Agent.

**Change.** Four knobs, each listed in SPEC §7 and documented in `HANDBOOK.md` in the same PR:

| Knob | Before | After |
|---|---|---|
| Daily-cycle amplitude (`arrival_amplitude`) | ±50% | ±90% (peak 5.7 per tick at 15:00, 0.3 at 03:00; the daily mean stays 3.0) |
| Staff sickness (`SICK_NURSES`) | 2 nurses | 3 nurses |
| Flu wave duration | 6 ticks | 10 ticks |
| Bus crash (`BUS_EXTRA_PER_TICK`, duration) | 5 per tick for 2 ticks | 6 per tick for 3 ticks |

Mean arrivals, event windows, warnings, severity mixes, hazards, budget and score weights are unchanged. Nothing new is hidden: the swing is the published formula, and the two announced surges still come with their exact start tick 10 and 8 ticks ahead.

**Method.** Everything ran in process, with no Docker and no paid runs. The reference is `ed72/solution` `ReferencePolicy`, and the baselines are `eval/baselines`. The Gemini proxy is the Python controller Gemini itself wrote in the seed-42 run (the last `write /app/run_ed.py` in `trajectory.json`), with its decision code unchanged and only the MCP transport replaced by direct `Simulation` calls. On the old defaults it scores 81.17 on seed 42, exactly the real run's score, so it reproduces the run. The search first changed single knobs (arrival mean 3.3–3.6, amplitude 0.7–0.9, budget, flu and bus mixes, warning lead times, event durations, sickness size, fatigue rates and hazard rates), then tried combinations. Each was scored on seeds 1–10 and 42, and the winner was checked on held-out seeds 11–20. Raising the mean arrival rate hurt the reference about as much as the proxy, so it was rejected. Shorter warnings, other severity mixes, a lower budget and higher hazard rates moved the gap by at most 1–2 points. The combination above moves it by 16 points on seed 42 while the reference stays above 89 on every seed.

The gemini proxy is one sample of one model's code, so it shows the direction of the change. It does not predict the next run; the real check is a fresh Gemini run on the new defaults.

### Before (old defaults)

| Policy | seed 1 | seed 2 | seed 3 | seed 4 | seed 5 | seed 42 | mean |
|---|---|---|---|---|---|---|---|
| reference | 99.7 | 98.8 | 99.4 | 96.8 | 97.5 | 99.0 | 98.5 |
| gemini proxy | 62.9 | 62.3 | 59.5 | 69.7 | 72.9 | 81.2 | 68.1 |
| severity_base | 60.8 | 54.1 | 43.1 | 46.3 | 56.8 | 47.0 | 51.3 |
| reactive_proxy | 57.8 | 62.7 | 61.7 | 59.6 | 67.2 | 60.1 | 61.5 |
| rest_in_quiet_periods | 70.5 | 55.8 | 72.7 | 70.7 | 70.9 | 81.7 | 70.4 |
| spend_to_limit | 61.7 | 63.7 | 53.4 | 63.4 | 61.1 | 58.8 | 60.3 |
| divert_all | 45.6 | 47.5 | 47.9 | 43.1 | 43.0 | 44.6 | 45.3 |
| stop_early | 3.8 | 4.0 | 5.5 | 5.7 | 4.7 | 5.6 | 4.9 |
| do_nothing | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| admit_light_only | 11.3 | 12.8 | 11.4 | 12.6 | 13.5 | 13.2 | 12.5 |
| admit_without_coverage | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| fill_beds_at_last_tick | 2.3 | 2.4 | 2.2 | 2.5 | 2.4 | 2.2 | 2.3 |
| random | 7.8 | 5.7 | 5.9 | 6.4 | 6.6 | 4.7 | 6.2 |

### After (new defaults)

| Policy | seed 1 | seed 2 | seed 3 | seed 4 | seed 5 | seed 42 | mean |
|---|---|---|---|---|---|---|---|
| reference | 97.2 | 94.7 | 94.0 | 89.7 | 98.3 | 97.4 | 95.2 |
| gemini proxy | 63.9 | 62.8 | 63.4 | 50.4 | 63.5 | 63.1 | 61.2 |
| severity_base | 46.9 | 54.1 | 55.5 | 36.6 | 56.6 | 30.7 | 46.7 |
| reactive_proxy | 49.9 | 52.8 | 53.3 | 48.5 | 57.1 | 58.9 | 53.4 |
| rest_in_quiet_periods | 64.4 | 55.3 | 52.6 | 59.0 | 71.8 | 39.2 | 57.1 |
| spend_to_limit | 57.5 | 62.0 | 63.0 | 54.3 | 62.9 | 68.0 | 61.3 |
| divert_all | 47.4 | 47.8 | 46.6 | 42.3 | 43.7 | 44.2 | 45.3 |
| stop_early | 3.9 | 5.1 | 5.5 | 5.0 | 5.2 | 6.6 | 5.2 |
| do_nothing | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| admit_light_only | 11.0 | 10.9 | 10.5 | 10.9 | 14.2 | 13.3 | 11.8 |
| admit_without_coverage | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| fill_beds_at_last_tick | 2.7 | 1.9 | 2.1 | 1.9 | 2.3 | 2.0 | 2.2 |
| random | 6.2 | 7.1 | 6.1 | 4.0 | 6.5 | 5.0 | 5.8 |

On seed 42 the reference-minus-proxy gap grows from 17.8 to 34.3 points. Over seeds 1–10 and 42 the mean gap grows from 28.6 to 35.0, and reference minus reactive proxy grows from 37.9 to 42.8. All of EVAL §5 holds on every seed above: do-nothing is 0; stop-early < reactive proxy < reference; divert-all is at most 47.8; every exploit and baseline is below the reference.

**Held-out seeds 11–20 (new defaults):** reference mean 95.3 (min 92.4), gemini proxy 64.7, reactive proxy 54.3, severity_base 51.3, spend_to_limit 64.3 and divert_all 46.7. The reference beats every baseline on every seed. Divert-all reaches 51.2 on seed 15 only. That seed is not shipped, and the CI cap of 50 applies to seeds 1–3.

**Tests moved with the values.** The pinned rulebook event table and the partial-override default in `tests/test_config.py` and `tests/test_rules_events.py` follow the new durations. The golden seed-1 world in `tests/test_world.py` has 444 patients and new event ticks, because the third sick nurse takes one more draw from the event stream. The ablations stand-in floor drops from 97 to 95: it scores 96.9 on seed 1. The `test_baselines.py` thresholds did not need to move.

## Arrival-rate screening (issue #67)

### Decision

Kostiantyn selected **3.0 arrivals per tick** for the default, with the remaining knobs unchanged. The scores below compare candidate configurations on seeds 1–5. Held-out seeds and model performance still need their separate evaluation.

### Method and source pins

- Base tree: `origin/main` **d1986f054adc9ca4c06ed3863a4e04c7ecac80c9**, containing merged baseline runner (#52) and config loader (#64).
- Reference: only [`ed72/solution/policy.py` from `kostiantyn/ref-policy` at `cc53151`](https://github.com/xand1ex999/guinness/blob/cc53151a31fb6db8557b1a9c65274f63580c922a/ed72/solution/policy.py) was overlaid in the temporary run tree. Its `ReferencePolicy.actions(obs)` was adapted to the baseline runner's `act(obs)` method. The policy used only the public observation.
- Idle-then-fill probe: `greedy_actions` from [red-team commit `407ffd7`](https://github.com/xand1ex999/guinness/blob/407ffd7e988ea965b3e7b77896f9978569b9d79d/ed72/environment/hospital/tests/test_redteam_round1.py); it returns no actions before tick 143, then staffs and fills from the final public observation.
- Seeds 1–5, exactly one changed knob (`arrival_mean`), all other `Config()` defaults unchanged. The 2.45 and 2.475 rows include all five seeds; other initial screens at 2.1, 2.4, 2.5, 2.7, and 2.575 helped bracket the transition.
- Policies are the merged `eval/baselines/` classes: severity-first, reactive proxy, stop-early, do-nothing, divert-all, rest-in-quiet-periods, admit-light-only, admit-without-coverage, fill-beds-at-last-tick, spend-to-limit, and seeded random, plus the reference and idle-then-fill probes above.
- Driver: from a disposable archive of the base commit, overlay the reference file with `git show cc53151a31fb6db8557b1a9c65274f63580c922a:ed72/solution/policy.py`, then from `eval/baselines/` run `PYTHONPATH=../../ed72/environment/hospital:../../ed72/solution uv run python -` with a `ConfiguredClient` that constructs `Simulation(generate_world(seed, dataclasses.replace(Config(), arrival_mean=mean)))`, calls `run_episode(client, policy)`, runs the tail with `sim.run_to_end()`, and scores `sim.events`. `ReferencePolicy.actions(obs)` is wrapped as `act(obs)`. The exact #62 greedy helper is linked above. No code or run artifacts from the temporary driver were retained.

The same integer seed makes each candidate reproducible; changing `arrival_mean` changes the number and order of draws in the arrivals stream, so these are deterministic candidate-specific worlds rather than identical patient-by-patient worlds. Do not infer monotonic score changes from adjacent values. [PR #73's later F1 attribution fix](https://github.com/xand1ex999/guinness/pull/73) was not in the base tree; it only changes a failure label, not numeric reward components.

### Per-seed scores

Scores are out of 100.

#### `arrival_mean = 2.45`

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

#### `arrival_mean = 2.475`

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

#### `arrival_mean = 3.0`

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

### Why 3.0

The selected configuration produced the strongest separation between the reference and the tested baselines while keeping divert-all near 47 points. The reference outscored the reactive proxy and every exploit on all five seeds. The original red-team greedy comparison remains pinned to its 1.5-arrival setup. The tables above cover the new default.
