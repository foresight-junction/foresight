# Branch: kostiantyn/env-sim-core

- **Issue:** #4
- **Owner:** kostiantyn
- **Agent:** lead
- **Parent branch:** main
- **Created:** Sat 14:29

## Goal
Deterministic tick engine `Simulation` (world in, event log and observations out). It draws no random
numbers: every roll uses world data. Works unchanged once `ed72_sim/world.py` (other branch) lands.

## Files and folders I own
- ed72/environment/hospital/ed72_sim/{state,actions,observation,engine}.py
- ed72/environment/hospital/tests/sim_fixtures.py, tests/test_engine_*.py

## Don't touch
- constants.py, model.py, rng.py, world.py, scoring/, server

## Contracts used or changed
CONTRACTS v1 Observation, Action, ActionResult, event log lines (plus the batch additions). No changes.

## Status
- [x] 1. state + observation
- [x] 2. actions
- [x] 3. tick loop (steps 1-3, 6)
- [x] 4. hazards + fatigue (steps 7-8)
- [x] 5. CRN + full-run tests (46 tests)

## Decisions and notes
- Fatigue is stored as integer tenths (gains are multiples of 0.1) so "> 60" never hits float noise.
- Only arrived patients are known ids; a future id is `unknown_patient` (hides the future).
- A sickness event also hits a fainted nurse (becomes sick, returns at start+duration).
- Observation `ticks_left` = 144 - tick (counts the current tick), 0 once finished.
- A diversion ordered at tick o shows ticks_left 3 in the observation of tick o+1 (o+4 - t).
- Agent `step` line is written after the sim lines step 5 produced (admitted, spend), before steps 6-8.

## Handoff
Done: everything in the brief. Not done: nothing known; no world.py integration test yet (needs #3 world gen).
Test: `cd ed72/environment/hospital && python -m pytest -q` (46 pass).
Use: `Simulation(world, log_path=None)`, `.observe()`, `.step(actions)`, `.run_to_end()`, `.events`.
