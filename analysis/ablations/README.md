# ablations

Lever ablations for issue #36 (C6). One policy, six switches; each variant changes exactly one lever.

- `ed72_ablations/standin.py`: `StandInPolicy(levers)`, a severity-first player with demand-based
  staffing from the least tired (a tired person counts as 0.6, as in the sim). MOCK: the #16 reference
  has no lever switches, so the ablations run on this stand-in. It reads only the CONTRACTS v1
  observation (a JSON copy, as over MCP) and returns a list of actions (AGENTS.md §10.4).
- `ed72_ablations/run.py`: plays every variant in process (`generate_world` -> `Simulation` ->
  `observe`/`step` to the end -> `score(sim.events)`) and prints a markdown table. `--policy reference`
  adds one row: `ed72_reference.ReferencePolicy().act` from `ed72/solution/` (or `--reference-dir`),
  unablated; `None` from it means stop, and the rest of the episode runs with no actions.
- The simulator is stdlib-only, so `run.py` puts `ed72/environment/hospital` on `sys.path` instead of
  depending on that project (it would also pull in fastmcp). This project has no dependencies.

## Run

```bash
cd analysis/ablations
uv run --python 3.12 python -m ed72_ablations.run --seeds 1 2 3 [--config PATH] [--json out.json] \
    [--policy standin|reference] [--reference-dir PATH]
uv run --python 3.12 --with pytest pytest -q
```

## Levers

Five skill ablations: removing the lever removes that skill.

| Lever | Code | Full policy | Removed |
|---|---|---|---|
| `resus_reservation` | F1 | resus for ESI 1, ESI 2 only if a resus bed stays free; ESI 3-5 never in resus | first free allowed bed, resus first |
| `rest_rotation` | F2 | only the staff the beds need are on shift, fresh before tired, least tired first, nobody above 87.7 | the same crew stays on shift until they faint at 90; nobody is sent to rest |
| `warnings` | F3 | while a bus crash is announced keep acute free (ESI 4-5 wait for fast track); surge agency ordered to arrive at the start (bus: 2 doctors + 2 nurses, flu: 1 nurse) | warnings ignored |
| `ct_repair` | F4 | repair when the CT is down for more than 3 ticks and a CT or ESI 1-2 patient is present, within budget; once per breakdown, retried if rejected | never repair |
| `agency` | F5 | order agency when the beds need more fresh (fatigue <= 60) staff than there are, within the soft budget | no shortfall orders (the warning surge orders belong to F3 and stay) |

One added habit, listed apart because it is not a skill ablation:

| Lever | Code | Full policy | Removed |
|---|---|---|---|
| `no_panic_divert` | F6 | never divert | divert whenever more than 3 patients are waiting (issue #36 variant 6: it adds a harmful behaviour) |

Each lever changes only the action types it owns, checked in lockstep on the same observations
(`test_each_lever_changes_only_what_it_owns`). The levers share the soft budget, checked in the
order repair, surge agency, shortfall agency.

## Results, seeds 1-3

Default config (the constants; `arrival_mean` 1.5). Reference: `origin/kostiantyn/ref-policy` at 5264305.

| variant | mean score | O | T | W | B | delta vs full | seed 1 | seed 2 | seed 3 |
|---|---|---|---|---|---|---|---|---|---|
| full | 99.48 | 0.994 | 0.997 | 1.000 | 1.000 |  | 99.42 | 99.29 | 99.73 |
| no resus_reservation (F1) | 98.68 | 0.994 | 0.957 | 1.000 | 1.000 | -0.80 | 98.31 | 98.46 | 99.27 |
| no rest_rotation (F2) | 89.54 | 0.994 | 0.997 | 0.000 | 1.000 | -9.94 | 89.49 | 89.36 | 89.76 |
| no warnings (F3) | 99.48 | 0.994 | 0.997 | 1.000 | 1.000 | +0.00 | 99.42 | 99.29 | 99.73 |
| no ct_repair (F4) | 99.48 | 0.994 | 0.997 | 1.000 | 1.000 | +0.00 | 99.42 | 99.29 | 99.73 |
| no agency (F5) | 99.48 | 0.994 | 0.997 | 1.000 | 1.000 | +0.00 | 99.42 | 99.29 | 99.73 |
| adds panic divert (F6) | 85.54 | 0.865 | 0.816 | 1.000 | 1.000 | -13.94 | 83.53 | 83.94 | 89.15 |
| reference (unablated, #16) | 99.48 | 0.994 | 0.997 | 1.000 | 1.000 | +0.00 | 99.42 | 99.29 | 99.73 |

`arrival_mean` 3.0 (the value #67 ships; run from a scratch config `{"arrival_mean": 3.0}`):

| variant | mean score | O | T | W | B | delta vs full | seed 1 | seed 2 | seed 3 |
|---|---|---|---|---|---|---|---|---|---|
| full | 99.27 | 0.993 | 0.991 | 1.000 | 1.000 |  | 99.69 | 98.79 | 99.33 |
| no resus_reservation (F1) | 78.75 | 0.827 | 0.727 | 0.763 | 1.000 | -20.52 | 82.52 | 74.56 | 79.17 |
| no rest_rotation (F2) | 56.75 | 0.639 | 0.601 | 0.000 | 1.000 | -42.52 | 60.29 | 60.71 | 49.24 |
| no warnings (F3) | 99.27 | 0.993 | 0.991 | 1.000 | 1.000 | +0.00 | 99.69 | 98.69 | 99.43 |
| no ct_repair (F4) | 99.21 | 0.993 | 0.991 | 0.994 | 1.000 | -0.06 | 99.50 | 98.79 | 99.33 |
| no agency (F5) | 99.22 | 0.993 | 0.989 | 1.000 | 1.000 | -0.04 | 99.69 | 98.79 | 99.20 |
| adds panic divert (F6) | 65.51 | 0.681 | 0.550 | 1.000 | 1.000 | -33.76 | 65.12 | 62.94 | 68.46 |
| reference (unablated, #16) | 99.30 | 0.993 | 0.993 | 1.000 | 1.000 | +0.03 | 99.69 | 98.79 | 99.43 |

The stand-in matches the #16 reference exactly on every seed at the default and within 0.1 per seed
at 3.0, so the deltas are a fair estimate of what each skill is worth to a player of reference strength.

## What the deltas mean

- **F1:** -0.8 at the default (only T: ESI 1 patients covered a tick late, nobody dies), -20.5 at 3.0,
  where low-acuity patients in resus block ESI 1 beds and use a whole doctor each.
- **F2:** the biggest lever. -9.9 at the default, all through W = 0 (tired crews still cover the
  beds); -42.5 at 3.0, where faints also cost coverage and lives.
- **F3: zero at both settings.** Assignments take effect the same tick, and the bus crash and flu wave
  fit into the free beds with the staff at hand, so there is nothing to prepare. The warnings carry no
  value for a sensible player.
- **F4: zero at the default, -0.06 at 3.0.** A broken CT only delays discharge while beds are spare.
- **F5: zero at the default, -0.04 at 3.0.** Demand-based staffing with rest rarely runs short of fresh
  staff, so shortfall-driven agency orders barely matter.
- **F6 (added habit):** -13.9 at the default, -33.8 at 3.0. Each panic diversion turns away 70 % of
  4 ticks of arrivals at loss 0.7. This shows that diverting hurts, not that not-diverting is a skill.

For #8: F3, F4 and F5 are toothless at both settings. Raising the arrival rate makes F1 and F2 matter
but leaves the reference at 99, so it does not create a gap on these three. They need other knobs
(fewer staff or beds, longer or overlapping events, a bigger bus crash, a shorter warning) before
they carry score.
