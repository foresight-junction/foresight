# ablations

Lever ablations for issue #36 (C6). One policy, six switches; each variant removes exactly one skill.

- `ed72_ablations/standin.py`: `StandInPolicy(levers)`, a severity-first player with demand-based
  staffing from the least tired. MOCK: it stands in for the #16 reference until that lands. It reads
  only the CONTRACTS v1 observation and returns a list of actions (AGENTS.md §10.4).
- `ed72_ablations/run.py`: plays every variant in process (`generate_world` -> `Simulation` ->
  `observe`/`step` to the end -> `score(sim.events)`) and prints a markdown table.
- The simulator is stdlib-only, so `run.py` puts `ed72/environment/hospital` on `sys.path` instead of
  depending on that project (it would also pull in fastmcp). This project has no dependencies.

## Run

```bash
cd analysis/ablations
uv run --python 3.12 python -m ed72_ablations.run --seeds 1 2 3 [--config PATH] [--json out.json]
uv run --python 3.12 --with pytest pytest -q
```

## Levers

| Lever | Code | Full policy | Removed |
|---|---|---|---|
| `resus_reservation` | F1 | resus for ESI 1, ESI 2 only if a resus bed stays free; ESI 3-5 never in resus | first free allowed bed, resus first |
| `rest_rotation` | F2 | only the staff the beds need are on shift, least tired first, nobody above 87.7 | the same crew stays on shift until they faint at 90; nobody is sent to rest |
| `warnings` | F3 | on a bus crash warning keep acute free (ESI 4-5 wait for fast track); order agency (bus: 2 doctors + 2 nurses, flu: 1 nurse) to arrive at the start | warnings ignored |
| `ct_repair` | F4 | repair once when the CT is down for more than 3 ticks and a CT or ESI 1-2 patient is present, within budget | never repair |
| `agency` | F5 | order agency when the beds need more fresh (fatigue <= 60) staff than there are, within the soft budget | never order agency (this also disables the warning-driven orders) |
| `no_panic_divert` | F6 | never divert | divert whenever more than 3 patients are waiting |

## Results, seeds 1-3, default config

| variant | mean score | O | T | W | B | delta vs full | seed 1 | seed 2 | seed 3 |
|---|---|---|---|---|---|---|---|---|---|
| full | 99.48 | 0.994 | 0.997 | 1.000 | 1.000 |  | 99.42 | 99.29 | 99.73 |
| no resus_reservation (F1) | 98.68 | 0.994 | 0.957 | 1.000 | 1.000 | -0.80 | 98.31 | 98.46 | 99.27 |
| no rest_rotation (F2) | 82.71 | 0.927 | 0.892 | 0.000 | 1.000 | -16.77 | 80.97 | 82.69 | 84.47 |
| no warnings (F3) | 99.48 | 0.994 | 0.997 | 1.000 | 1.000 | +0.00 | 99.42 | 99.29 | 99.73 |
| no ct_repair (F4) | 99.48 | 0.994 | 0.997 | 1.000 | 1.000 | +0.00 | 99.42 | 99.29 | 99.73 |
| no agency (F5) | 99.48 | 0.994 | 0.997 | 1.000 | 1.000 | +0.00 | 99.42 | 99.29 | 99.73 |
| no no_panic_divert (F6) | 85.54 | 0.865 | 0.816 | 1.000 | 1.000 | -13.94 | 83.53 | 83.94 | 89.15 |

The full stand-in has 0 deaths and 0 faints on all three seeds; its only losses are patients still in
a bed at tick 143 and a few late first coverages.

- **F1, -0.8:** small. Low-acuity patients in resus cost T (6 ESI 1 arrivals over three seeds are covered late, ESI 1 target is 0 ticks) but nobody dies:
  with 17 beds and ~1.5 arrivals per tick, resus is rarely full. At `arrival_mean` 3.0 it costs -19.3.
- **F2, -16.8:** the biggest lever. W drops to 0 (15-23 faints, most of the shift above 60), and faints
  cost coverage, so 2-5 deaths per seed.
- **F3, 0.0: toothless.** Staffing is instant (assign takes effect the same tick), so there is nothing
  to prepare; the bus crash's 10 patients fit into free beds with idle staff. Still 0.0 at `arrival_mean` 2.5 and 3.0.
- **F4, 0.0: toothless at the default.** A CT stall only delays discharge; with spare beds it costs nothing.
  -0.8 at `arrival_mean` 2.5.
- **F5, 0.0: toothless at the default.** Demand-based staffing with rest never runs short of fresh staff.
  -3.0 at `arrival_mean` 3.0.
- **F6, -13.9:** each panic diversion turns away 70 % of 4 ticks of arrivals at loss 0.7 each. This
  measures self-harm rather than a skill the agent lacks; the full policy simply never diverts.

The actions differ for every lever (tests), so the zero deltas are the game, not dead code. For #8:
at the default difficulty only rest rotation and not diverting matter; warnings, CT repair and agency
staff add nothing to a sensible player, and the score stays about 98-99 even at twice the arrival rate.
