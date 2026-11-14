# Branch: kostiantyn/env-world

- **Issue:** #3
- **Owner:** kostiantyn
- **Agent:** kostiantyn-claude-2a
- **Parent branch:** main

## Goal
`generate_world(seed) -> World`: staff, events, base/flu/bus arrivals and per-patient dice, all from named seeded streams. Done when tests pass and the golden seed-1 test is stable.

## Files and folders I own
- ed72/environment/hospital/ed72_sim/world.py
- ed72/environment/hospital/tests/test_world.py

## Don't touch
- constants.py, model.py, rng.py

## Contracts used or changed
- Uses model.py types and rng.py streams: "events", "arrivals", "flu", "bus", "patient:<pid>". No contract change.

## Status
- [x] Tests written (12 pass with the existing constants test)
- [x] world.py: staff, events, arrival plan, patient draws
- [x] Golden test for seed 1

## Decisions and notes
- Flu and bus use their own streams so event knobs never shift base arrivals.
- Per-patient draw order: ct_u, divert_u, upgrade_ct_u, then 144 hazard uniforms.

## Handoff
Done: world generator and tests. Not done: nothing known.
Test: `cd ed72/environment/hospital && python -m pytest -q -p no:cacheprovider`
