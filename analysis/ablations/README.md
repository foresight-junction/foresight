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
(`test_each_lever_changes_only_what_it_owns`). Known limit: F1 is allowed to differ in admit, assign and
agency types (admit zones feed staffing and the shortfall count), so that check stays at the action-type
level. F3 is checked at decision level: it differs only while a warning is visible, and ESI 1-2 admits
stay identical. The levers share the soft budget, checked in the
order repair, surge agency, shortfall agency.

## Results at the shipped config (arrival_mean 4.0), seeds 42, 1, 2, 3

Run on main at `4b51656` (PR #104), no config file (the built-in defaults equal `config/default.json`:
arrival_mean 4.0, soft budget 12000). Command:
`python -m ed72_ablations.run --seeds 42 1 2 3 --policy reference --json out.json`. No `ed72-s*` seed
folders exist; the shipped seeds are 42 (the task default) plus 1-3.

**Which policy each row ablates.** Rows `full` to `adds panic divert (F6)` are the STAND-IN
(`standin.py`) with one lever switched off. The last row is the CURRENT #98 reference
(`ed72/solution/ed72_reference.py`), played unablated: it has no lever switches, so it is a yardstick,
not an ablation.

| variant | mean score | O | T | W | B | delta vs full | seed 42 | seed 1 | seed 2 | seed 3 |
|---|---|---|---|---|---|---|---|---|---|---|
| full | 87.81 | 0.911 | 0.813 | 0.854 | 1.000 |  | 89.08 | 94.27 | 78.34 | 89.54 |
| no resus_reservation (F1) | 48.24 | 0.518 | 0.435 | 0.627 | 1.000 | -39.57 | 46.94 | 56.52 | 40.92 | 48.57 |
| no rest_rotation (F2) | 43.46 | 0.498 | 0.430 | 0.000 | 1.000 | -44.36 | 41.78 | 40.67 | 45.44 | 45.94 |
| no warnings (F3) | 82.15 | 0.864 | 0.736 | 0.804 | 1.000 | -5.66 | 83.72 | 90.56 | 72.14 | 82.17 |
| no ct_repair (F4) | 87.18 | 0.903 | 0.809 | 0.861 | 1.000 | -0.64 | 73.70 | 94.95 | 87.36 | 92.70 |
| no agency (F5) | 43.63 | 0.478 | 0.373 | 0.565 | 1.000 | -44.18 | 39.04 | 52.31 | 40.14 | 43.06 |
| adds panic divert (F6) | 59.70 | 0.628 | 0.472 | 1.000 | 1.000 | -28.11 | 57.02 | 62.63 | 56.46 | 62.70 |
| reference (unablated, #98) | 92.50 | 0.976 | 0.870 | 0.989 | 0.705 | +4.69 | 94.02 | 93.37 | 88.59 | 94.01 |

Per-seed delta vs full (seed 42, 1, 2, 3), in points:

| variant | seed 42 | seed 1 | seed 2 | seed 3 |
|---|---|---|---|---|
| no resus_reservation (F1) | -42.1 | -37.7 | -37.4 | -41.0 |
| no rest_rotation (F2) | -47.3 | -53.6 | -32.9 | -43.6 |
| no warnings (F3) | -5.4 | -3.7 | -6.2 | -7.4 |
| no ct_repair (F4) | -15.4 | +0.7 | +9.0 | +3.2 |
| no agency (F5) | -50.0 | -42.0 | -38.2 | -46.5 |
| adds panic divert (F6) | -32.1 | -31.6 | -21.9 | -26.8 |
| reference (#98), for scale | +4.9 | -0.9 | +10.3 | +4.5 |

**Stand-in vs reference.** The stand-in (87.8 mean) is 4.7 below the current reference (92.5): behind on
three seeds out of four, ahead by 0.9 on seed 1, and with O 0.911 against 0.976. It is still a strong policy
(severity-first alone scores about 31 on seed 1), so ablating it says something real, but the deltas are
those of a policy about 5 points short of the reference, not of the reference. The stand-in keeps B at
1.000 by staying under the soft budget (spend 11.2-11.9k), while the reference overspends (15.5-15.8k,
B 0.705) and buys 4.7 points of O and T with it. It was tuned for 1.5-3.0 and not retuned here.

**Reading per lever.**

- **F5 agency (-44.2):** now the largest lever, together with F2 and F1. At 4.0 the 6 doctors and 9
  nurses cannot cover the beds alone; without agency 47-92 patients die per seed (spend falls to the 4850
  of base salaries).
- **F2 rest rotation (-44.4):** W falls to 0 and 53-79 patients die; 60 faints per seed.
- **F1 resus reservation (-39.6):** low-acuity patients take resus beds and each ties up a doctor; deaths
  42-76 per seed.
- **F6 panic divert (-28.1):** an added habit, not a skill. 269-365 diversions per seed (of 561-635 arrivals) at loss 0.75.
  It shows that diverting hurts.
- **F3 warnings (-5.7):** small but consistent on all four seeds (-3.7 to -7.4), the first nonzero delta
  for warnings. It shows up as T and O (0.864 vs 0.911): holding acute free and ordering surge agency
  ahead of the bus crash saves ESI 2-3 patients. At 3.0 it was exactly 0.
- **F4 CT repair (-0.6, noisy):** per-seed deltas range from -15.4 (seed 42, 12 deaths) to +9.0 (seed 2).
  The mean is inside the noise. The 2000 repair competes with agency for the same soft budget, so on some
  seeds skipping the repair frees money that is worth more as agency. On the mean, F4 is inert; the
  seed-42 loss shows it can matter when the breakdown overlaps a rush. Four seeds do not separate these.

For #8 and #19: F1, F2, F5 carry the score at 4.0, F3 carries a few points, F4 does not carry the mean.
No rules were added to force a nonzero delta.

## Earlier results (superseded): lower arrival means

Kept for the history of #36. These used the same stand-in at `arrival_mean` 1.5 and 3.0, seeds 1-3, with
the #16 reference at 5264305 (not the current one). They are NOT the shipped difficulty.

### Defaults of that time (1.5) and 3.0

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

## What the deltas meant at 1.5 and 3.0

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
