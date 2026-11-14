# Branch: mykhailo/env-extra-events

- **Issue:** #9
- **Owner:** mykhailo
- **Agent:** lead
- **Parent branch:** main
- **Created:** Sat 15:38

## Goal
Off-by-default extra events (doctor_sickness, second_mci, monitor_fault) and a second bed layout (compact), as a proposal for #1. Done when the default config gives a byte-identical log to main and the new tests pass.

## Files and folders I own
- ed72/environment/hospital/ed72_sim/rules/ (events_extra.py, layouts.py)
- ed72/environment/hospital/config/layouts/
- ed72/environment/hospital/tests/test_events_extra.py, tests/test_layouts.py
- docs/proposals/extra-events.md
- Small hooks (owner kostiantyn-claude-2 reviews): engine.py `_step2_events`, world.py `_events`/`_arrival_plan`/`generate_world`, state.py `State` (bed_ids, closed_beds), observation.py `_beds`, actions.py `_admit` (lead approved), config.py (`layout`, `enabled`), model.py `World.bed_counts`; default.json gets off-by-default keys.

## Don't touch
- scoring/, server.py, HANDBOOK.md, CONTRACTS.md

## Contracts used or changed
- None. With extras on: only new warnings[].event values and event_start/event_end kinds; second_mci patients use source "bus".

## Status
- [x] Extra events in rules/events_extra.py, own seeded streams, enabled: false by default
- [x] Layout key + config/layouts/{default,compact}.json; bed ids per State
- [x] Defaults-off check: 20 seeded episodes (10 seeds, idle + greedy policy) byte-identical to main, with no config and with default.json
- [x] Tests: test_events_extra.py, test_layouts.py
- [x] Proposal doc with HANDBOOK lines

## Decisions and notes
- monitor_fault closes the highest-numbered Resus bed to new admissions (existing `no_free_bed`); its patient stays and is treated. No treatment rule changes.
- Extras draw from streams "events_extra" and "mci"; all extras are drawn even if disabled, so enabling one never moves another.
- Gap: scoring/failures.py F6 uses constants.BEDS, so it is wrong under compact or monitor_fault. server.py does not load ED72_CONFIG yet (#5).

## Handoff
Done: everything above, pushed. Not done: HANDBOOK text (#7), baseline re-runs (#12), F6 fix, team decision on #1.
Test: `cd ed72/environment/hospital && uv run --python 3.12 --with pytest pytest -q`. Enable with `{"events": {"monitor_fault": {"enabled": true}}, "layout": "compact"}` in ED72_CONFIG.
