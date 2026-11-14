# Proposal: extra events and a second bed layout (issue #9)

Status: built on `mykhailo/env-extra-events`, **all off by default**. With `config/default.json` the world and the event log are byte-identical to main. Nothing here is part of the game until the team agrees on #1. The engine owner (#4/#8) has to review the hooks.

## How to turn it on

In the `ED72_CONFIG` file:

```json
{
  "events": {
    "doctor_sickness": {"enabled": true},
    "second_mci": {"enabled": true},
    "monitor_fault": {"enabled": true}
  },
  "layout": "compact"
}
```

Each extra event also takes `window`, `duration` and `warning`, the same as the core events. The extras draw from their own seeded streams (`events_extra` and `mci`). Turning one on never moves a core event, a base arrival's tick or ESI, or another extra's start tick. Patient ids after the first extra arrival do shift, because ids follow arrival order.

Each extra is announced the way flu_wave and bus_crash are: `warnings[]` shows `{"event": <kind>, "start_tick": t}` from `warning` ticks before the start until the event ends, and the log gets `event_start` and `event_end` with the new kind. No observation field, action or reason changes.

## Events

**doctor_sickness** (window 80–89, 12 ticks, 4 ticks of warning). One doctor, chosen by the seed, is off sick for 12 ticks. It uses the staff_sickness mechanic: a doctor on shift leaves at once and comes back to the rest room with the fatigue they left with. There are only 6 doctors, and in Resus one doctor covers one bed, so losing one is a bigger hit than losing a nurse. With 4 ticks of notice, a good agent orders agency cover (which takes 4 ticks to arrive) or rests its other doctors beforehand. It tests **F3** (ignoring a warning) and **F9** (keeping the same plan after the staff change). It also pushes toward **F7**, because a careless agent keeps admitting to beds it can no longer cover.

**second_mci** (window 124–133, 2 ticks, 8 ticks of warning). A second mass-casualty arrival that uses the bus_crash mechanic: 5 extra patients per tick for 2 ticks, drawn from `bus_mix` (ESI 1 20%, ESI 2 30%, ESI 3 50%) and logged with `source: "bus"`. It comes on the last night, when staff are tired and the agent may have spent its budget, so a policy that handled the first crash by burning out its staff pays for that here. It tests **F3**, **F2** (no rest rotation, so nobody is fresh at tick 124) and **F1** (Resus beds held by low-acuity patients when two ESI 1 patients arrive).

**monitor_fault** (window 40–47, 8 ticks, 3 ticks of warning). The highest-numbered Resus bed (R3 in the default layout) takes no new patient while the fault lasts. An admit that could only use that bed is rejected with the existing `no_free_bed` reason. A patient already in that bed stays and keeps being treated, so no treatment rule changes. Resus is the only zone that treats ESI 1, so its capacity drops from 3 to 2 for 8 ticks. It tests **F1** directly: an agent that fills Resus with ESI 3–5 patients has no ESI 1 bed left. It also tests **F3**, because the agent can clear the bed during the 3 ticks of notice.

## Second layout: `compact`

`config/layouts/compact.json` has Resus 2, Acute 9 and Fast-track 6, so the department still has 17 beds. Bed ids stay R/A/F-numbered (R1–R2, A1–A9, F1–F6), so the observation keeps its shape and only the number of `beds[]` rows changes. Fewer ESI 1 beds make the bus crash and F1 harder. The extra Acute bed can take ESI 2 patients at +1 tick, which rewards an agent that understands the zone table over one that sends every severe patient to Resus. `config/layouts/default.json` is the rulebook layout and is used when no `layout` is given.

## Known gaps (need owners outside #9)

- `scoring/failures.py` `_allowed_bed_free` (F6) reads `constants.BEDS`. With `compact`, or while `monitor_fault` closes a bed, it miscounts free beds, so F6 is wrong in those runs. The reward itself (O, T, W, B) does not use bed counts. Fix: replay the closed bed from `event_start`/`event_end`, and read bed counts from an `episode_start` field or the config. That is a log change, so it goes through `contract-change`.
- `server.py` builds `generate_world(seed)` without `load_config(ED72_CONFIG)` (flagged on #5). Until that is wired, none of these options reach the live episode, only `collect.py`'s replay.
- `HANDBOOK.md` (#7) needs the lines below, and EVAL baselines (#12) need re-running, before any of this is enabled.

## HANDBOOK lines to add if enabled

Events table rows:

| Event | Start window (tick) | Warning | Effect |
|---|---|---|---|
| Doctor sickness | 80–89 | 4 ticks ahead | 1 doctor (chosen by the seed) off sick for 12 ticks; a doctor on shift leaves at once and returns to rest with the fatigue they left with |
| Second mass casualty | 124–133 | 8 ticks ahead | 10 extra patients over 2 ticks (5 per tick): ESI 1 20%, ESI 2 30%, ESI 3 50% |
| Resus monitor fault | 40–47 | 3 ticks ahead | for 8 ticks the highest-numbered Resus bed takes no new patient (`no_free_bed`); a patient already in it stays and keeps being treated |

Department line, only if `compact` is used:

> Beds: Resus 2 (R1–R2), Acute 9 (A1–A9), Fast-track 6 (F1–F6), 17 in all.
