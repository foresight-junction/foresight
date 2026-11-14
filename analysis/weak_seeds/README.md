# Weak seeds of the ED-72 reference (issue #106)

Analysis only. Nothing in `ed72/solution/` was changed: the changes in section 4 are proposals for
its owner (kostiantyn-codex-16), kept as `proposals.patch`. Rules frozen; shipped config
(`arrival_mean` 4.0, diversion share 0.75).

Reproduce (the simulator needs Python 3.12): `uv run --python 3.12 python analysis/weak_seeds/run.py --seeds 11 2 19 --detail 11 2 19`.
`--reference-dir DIR` runs another copy of `ed72_reference.py`. Code base: main `83f93c9` (branch started at `a488a93`; main has since moved).

## 1. Confirmed numbers (unmodified reference, in process)

| seed | score | O | T | W | B | spend | died | left | never adm. | diverted | faints |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 42 | 94.02 | 0.989 | 0.885 | 1.000 | 0.713 | 15450 | 0 | 11 | 0 | 0 | 0 |
| 1 | 93.37 | 0.973 | 0.915 | 1.000 | 0.713 | 15450 | 2 | 6 | 0 | 0 | 0 |
| 2 | 88.59 | 0.952 | 0.793 | 0.957 | 0.683 | 15800 | 0 | 42 | 36 | 0 | 0 |
| 3 | 94.01 | 0.989 | 0.888 | 1.000 | 0.713 | 15450 | 0 | 14 | 0 | 0 | 0 |
| 4 | 92.67 | 0.982 | 0.860 | 1.000 | 0.683 | 15800 | 1 | 16 | 0 | 0 | 0 |
| 5 | 94.05 | 0.989 | 0.903 | 1.000 | 0.683 | 15800 | 1 | 11 | 0 | 0 | 0 |
| 11 | 84.42 | 0.927 | 0.709 | 0.903 | 0.671 | 15950 | 4 | 44 | 49 | 0 | 0 |
| 12 | 94.43 | 0.990 | 0.910 | 1.000 | 0.700 | 15600 | 0 | 15 | 0 | 0 | 0 |
| 13 | 93.61 | 0.987 | 0.889 | 1.000 | 0.683 | 15800 | 1 | 8 | 0 | 0 | 0 |
| 14 | 93.58 | 0.976 | 0.914 | 1.000 | 0.713 | 15450 | 1 | 13 | 0 | 0 | 0 |
| 15 | 93.65 | 0.983 | 0.905 | 1.000 | 0.683 | 15800 | 1 | 12 | 0 | 0 | 0 |
| 16 | 92.03 | 0.969 | 0.882 | 0.994 | 0.683 | 15800 | 3 | 18 | 0 | 0 | 0 |
| 17 | 93.49 | 0.977 | 0.898 | 1.000 | 0.729 | 15250 | 1 | 16 | 0 | 0 | 0 |
| 18 | 95.70 | 0.991 | 0.936 | 1.000 | 0.771 | 14750 | 0 | 14 | 0 | 0 | 0 |
| 19 | 89.04 | 0.947 | 0.843 | 0.940 | 0.683 | 15800 | 2 | 38 | 23 | 0 | 0 |
| 20 | 89.93 | 0.956 | 0.841 | 0.960 | 0.683 | 15800 | 1 | 51 | 21 | 0 | 0 |

Shipped seeds 42, 1-5 range 88.6-94.1, mean 92.79: this matches #103 (mean about 92.8, seed 2 = 88.6).
Held-out 11-20 minimum is 84.42 (seed 11): confirmed. Weakest after it: seeds 2 (88.6), 19 (89.0), 20 (89.9).
All weak seeds score high on W/B and lose elsewhere; B is about 0.68-0.71 on every seed (spend about 15.8k against the 12k budget, about 3 points, a constant).

## 2. Where the weak seeds lose points

Points are exact: O points = (60 + 10W + 10B) x weight x loss / total weight, T points = 20 x weight / total weight per patient not covered on time. Per-seed tables (outcome, ESI, failure code, arrival time, largest patient losses) come from `--detail`.

| seed | score | O pts lost | T pts lost | W pts lost | B pts lost | main O losses |
|---|---|---|---|---|---|---|
| 11 | 84.42 | 5.50 | 5.82 | 0.90 | 3.05 | 4 died (1.57), 44 left (1.67), 49 never admitted (1.98) |
| 2 | 88.59 | 3.67 | 4.14 | 0.41 | 3.01 | 42 left (1.79), 36 never admitted (1.49), no deaths |
| 19 | 89.04 | 4.05 | 3.14 | 0.57 | 3.00 | 2 ESI 1 died (1.12), 38 left, 23 never admitted |

Findings:

1. **The loss is ESI 4-5 volume at the end of the day, not clinical failures.** ESI 4 and 5 patients who leave or are never admitted are 3.3 of seed 2's 3.7 O points (ESI 4: 2.31, ESI 5: 1.02) and 3.65 of seed 11's 5.5. Failure codes are nearly empty (F8 upgrades only; one F7 on seed 11; no F1, F2, F6, F10).
2. **Time: ticks 96-143.** On seed 2, arrivals in ticks 96-143 carry 3.51 of 3.67 O points and 3.2 of 4.14 T points. Bus crash at tick 106 (seed 2) / 107 (seed 11) floods the ED, and the queue (30-70 waiting, mostly ESI 3-5) never drains before tick 143. Flu wave (50-61), CT breakdown (66-75) and sickness (28-35) cost almost nothing on any weak seed (arrival buckets 24-95 lose under 0.7 points in total).
3. **Seed 2, ticks 120-132: staff idle while the queue grows.** Trace: tick 123 has 62 waiting, 12 of 17 beds in use but only 5 covered; by tick 126 only 5 beds are in use while 69 wait, with 6 of 9 doctors and 9 of 13 nurses resting. Agency nurses ordered for the bus crash have fatigue above 50, so `staff_plan(FRESH_FATIGUE=50)` removes them all at once; the wider plan (cap 87.8) runs only when an ESI 1-2 patient is uncovered, and none is. Result: no admissions for about 8 ticks, ESI 4 patients cross the 16-tick leave threshold (`left`: 42).
4. **Seed 11, ticks 108-141: doctors run to fatigue 80+.** Budget is at the 16000 overspend cap by tick 114 (22 spend events), the six permanent doctors work through fatigue 41 to 84 by the end, W loses 0.90 points, and 44 patients leave. Backlog hires after tick 115 are paid for but pay back little (section 4).
5. **Resus use is not the problem.** Seed 11's two early ESI 1 deaths (P055 tick 10, P255 tick 58) arrive when resus is full of other ESI 1-2 patients (ESI 1 hazard 0.15 per tick, no free bed), and F1 is 0 everywhere. Rest timing, repair and diversion do not appear: repair is automatic, diversion is never used.

## 3. Sensitivity (all on the 16 seeds above unless said otherwise)

One-at-a-time changes to the unmodified reference, mean / min: `OVERSPEND_LIMIT` 14000: 90.87 / 73.5; 18000: 91.65 / 84.2; 20000: 91.16 / 83.0. `MAX_ORDERS_IN_TRANSIT` 3: 91.17 / 74.8. `BACKLOG_TO_HIRE` 3: 91.91 / 77.8. `FRESH_FATIGUE` 45: 92.39 / 87.7; 55: 92.46 / 83.9. Baseline 92.29 / 84.42. The hiring and budget constants are at a local optimum; the landscape is rough (small moves swing the minimum by several points), so a change is judged on out-of-sample seeds too.

## 4. Proposals (scratch copies outside the repo; `proposals.patch` applies cleanly to `ed72/solution/policy.py`)

**P1: widen the plan to staff below the tired threshold whenever 3 or more patients are uncovered, and never plan staff above 60.** In `act()`: the wider `staff_plan` runs when an ESI 1-2 patient is uncovered **or** `len(uncovered) + unplaced >= 3`, and it uses `max_fatigue=60` instead of 87.8. Reason: findings 3 and 4. A cap of 60 keeps staff at full `counts_as` and out of the W penalty. A higher cap was worse (70: 92.14 / 82.2; 62: 92.14 / 82.8; 87.8 only for ESI 1-2: 92.49 / 85.6).

**P2: `LAST_HIRE_TICK` 135 to 115.** Reason: finding 4. A late order arrives 4 ticks later and stays 16, but ticks 115-135 hires are paid for the most and cover too little queue. Sweep with P1 (mean / min on the 16 seeds): 130: 92.90 / 88.46; 120: 93.60 / 88.46; 115: 93.77 / 88.46; 110: 93.74 / 88.46; 105: 93.25 / 87.35; 100: 91.18 / 82.4. Take 115, not 110: 105 is a cliff (bus crash hires land there). P2 alone (without P1): 92.84 / 84.42, so it is only safe with P1.

Per-seed scores (16 seeds, 42 and 1-5 shipped, 11-20 held out):

| seed | baseline | P1 | P2 only | P1 + P2 |
|---|---|---|---|---|
| 42 | 94.02 | 94.02 | 94.02 | 94.02 |
| 1 | 93.37 | 93.37 | 94.73 | 94.73 |
| 2 | 88.59 | 91.64 | 87.32 | 92.78 |
| 3 | 94.01 | 94.07 | 95.55 | 95.94 |
| 4 | 92.67 | 92.84 | 93.24 | 93.48 |
| 5 | 94.05 | 93.95 | 96.09 | 96.17 |
| 11 | 84.42 | 88.46 | 84.42 | 88.46 |
| 12 | 94.43 | 94.18 | 94.96 | 96.44 |
| 13 | 93.61 | 93.61 | 95.80 | 95.80 |
| 14 | 93.58 | 93.58 | 93.58 | 93.58 |
| 15 | 93.65 | 93.71 | 93.63 | 94.00 |
| 16 | 92.03 | 92.11 | 91.85 | 92.34 |
| 17 | 93.49 | 93.52 | 94.13 | 94.38 |
| 18 | 95.70 | 95.70 | 97.18 | 97.18 |
| 19 | 89.04 | 90.52 | 89.04 | 90.52 |
| 20 | 89.93 | 90.43 | 89.93 | 90.43 |

| set | baseline mean / min | P1 | P1 + P2 |
|---|---|---|---|
| 16 seeds above | 92.29 / 84.42 | 92.86 / 88.46 | 93.77 / 88.46 |
| held-out 11-20 | 91.99 / 84.42 | 92.58 / 88.46 | 93.31 / 88.46 |
| shipped 42, 1-5 | 92.79 / 88.59 | 93.31 / 91.64 | 94.52 / 92.78 |
| **untuned seeds 21-50** (not used to pick the values) | 92.59 / 85.99 | 93.05 / 88.20 | 93.48 / 88.75 |
| **untuned seeds 100-139** (the #98 held-out set) | 92.18 / 80.87 | 92.73 / 84.29 | 93.49 / 84.29 |

Both changes pass the rule (no lower mean, no lower held-out minimum) on every set. P1 lowers two single seeds slightly (seed 5 by 0.10, seed 12 by 0.25); P1 + P2 lowers none. Gain is about +0.5 (P1) and +0.9 to +1.5 (P1 + P2) on the mean, and +2.2 to +4.0 on the minimum. Seed 2 goes 88.59 to 92.78 and seed 11 84.42 to 88.46.

Not worth proposing: raising the overspend limit (worse, section 3), a lower trigger than 3 (same), a late-game relaxation of the cap (no change), `FRESH_FATIGUE` 45 or 48 (lower mean).

Any change to `ed72/solution/` needs the owner and a pin before the #18 matrix.
