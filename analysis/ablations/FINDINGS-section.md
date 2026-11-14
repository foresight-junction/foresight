## Lever ablations (F1-F6), shipped config

Source: `analysis/ablations/` (issue #36), run on main at `4b51656`, default config (arrival_mean 4.0,
soft budget 12000), seeds 42, 1, 2, 3. Reproduce with
`cd analysis/ablations && uv run --python 3.12 python -m ed72_ablations.run --seeds 42 1 2 3 --policy reference`.

**What is ablated.** The levers are switches on a stand-in policy (`standin.py`), because the current
reference (`ed72/solution/ed72_reference.py`) has no lever switches. The stand-in is 4.7 points below the
reference (87.8 vs 92.5): the deltas below are those of a strong but slightly weaker player. The last row
is the unablated reference, shown for scale only.

| variant | mean score | O | T | W | B | delta vs full | seed 42 | seed 1 | seed 2 | seed 3 |
|---|---|---|---|---|---|---|---|---|---|---|
| full (stand-in) | 87.81 | 0.911 | 0.813 | 0.854 | 1.000 |  | 89.08 | 94.27 | 78.34 | 89.54 |
| no resus reservation (F1) | 48.24 | 0.518 | 0.435 | 0.627 | 1.000 | -39.57 | 46.94 | 56.52 | 40.92 | 48.57 |
| no rest rotation (F2) | 43.46 | 0.498 | 0.430 | 0.000 | 1.000 | -44.36 | 41.78 | 40.67 | 45.44 | 45.94 |
| no warnings (F3) | 82.15 | 0.864 | 0.736 | 0.804 | 1.000 | -5.66 | 83.72 | 90.56 | 72.14 | 82.17 |
| no CT repair (F4) | 87.18 | 0.903 | 0.809 | 0.861 | 1.000 | -0.64 | 73.70 | 94.95 | 87.36 | 92.70 |
| no agency (F5) | 43.63 | 0.478 | 0.373 | 0.565 | 1.000 | -44.18 | 39.04 | 52.31 | 40.14 | 43.06 |
| adds panic divert (F6) | 59.70 | 0.628 | 0.472 | 1.000 | 1.000 | -28.11 | 57.02 | 62.63 | 56.46 | 62.70 |
| reference (#98, unablated) | 92.50 | 0.976 | 0.870 | 0.989 | 0.705 | +4.69 | 94.02 | 93.37 | 88.59 | 94.01 |

**Reading.**

- F1, F2 and F5 each cost about 40-44 points on every seed (deaths in the dozens). At 4.0 the staff
  cannot cover the beds without agency, rest rotation and resus reservation.
- F6 (panic diversion) costs 28 points: diverting is a trap, not a skill. It is the one added habit.
- F3 (warnings) costs 5.7 points, -3.7 to -7.4 on all four seeds: holding acute free and ordering surge
  agency ahead of the bus crash saves ESI 2-3 patients. Zero at lower arrival rates; it matters at 4.0.
- F4 (CT repair) is inert on the mean (-0.64): -15.4 on seed 42, +9.0 on seed 2. The 2000 repair competes
  with agency for the same soft budget, so a repair can lose points. This is reported as found; four
  seeds cannot separate a small effect from noise, and no rule was added to force a delta.
- The reference overspends the soft budget (B 0.705, spend about 15.5k) and still beats the stand-in,
  which keeps B at 1.000.

Limits: one stand-in, four seeds, deterministic worlds; F1's lockstep ownership check is at action-type
level, not decision level (README).
