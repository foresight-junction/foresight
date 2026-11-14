"""Extra events (issue #9, a proposal): off by default, turned on per kind in the config's `events`.

Each reuses an existing mechanic and is announced like flu_wave and bus_crash: the warning shows the
kind and the exact start tick from `warning` ticks ahead until the event ends.

- doctor_sickness: one doctor (chosen by the seed) goes sick, the staff_sickness mechanic.
- second_mci: a second mass-casualty arrival, the bus_crash mechanic (source "bus", bus_mix).
- monitor_fault: the highest-numbered Resus bed takes no new patient while the fault lasts. A patient
  already in it stays and keeps being treated, so no treatment rule changes.

Draws come from their own streams ("events_extra", "mci"), and all extras are drawn whether enabled or
not, so turning one on never moves another's start tick and the default world is untouched.
"""

import random
from typing import Any

from ed72_sim import constants as c
from ed72_sim.model import EventSpec
from ed72_sim.rng import stream

EXTRA_EVENTS: dict[str, dict[str, Any]] = {
    "doctor_sickness": {"window": (80, 89), "duration": 12, "warning": 4, "enabled": False},
    "second_mci": {"window": (124, 133), "duration": 2, "warning": 8, "enabled": False},
    "monitor_fault": {"window": (40, 47), "duration": 8, "warning": 3, "enabled": False},
}
SICK_KINDS = ("staff_sickness", "doctor_sickness")


def default_extra_events() -> dict[str, dict[str, Any]]:
    return {kind: dict(spec) for kind, spec in EXTRA_EVENTS.items()}


def _uniform_int(rng: random.Random, lo: int, hi: int) -> int:
    return lo + int(rng.random() * (hi - lo + 1))


def extra_events(seed: int, doctors: list[str], events: dict[str, dict[str, Any]]) -> tuple[EventSpec, ...]:
    rng = stream(seed, "events_extra")
    out = []
    for kind in EXTRA_EVENTS:
        cfg = events[kind]
        start = _uniform_int(rng, *cfg["window"])
        sick = (doctors[int(rng.random() * len(doctors))],) if kind == "doctor_sickness" else ()
        if cfg["enabled"]:
            out.append(EventSpec(kind, start, cfg["duration"], cfg["warning"], sick))
    return tuple(out)


def extra_surges(seed: int, events: dict[str, dict[str, Any]], bus_mix: dict[int, float]) -> dict:
    """Surge entries for world._arrival_plan, same shape as its flu and bus entries."""
    if not events["second_mci"]["enabled"]:
        return {}
    return {"second_mci": ("bus", c.BUS_EXTRA_PER_TICK, bus_mix, stream(seed, "mci"))}


def on_start(state: Any, event: EventSpec) -> None:
    if event.kind == "monitor_fault":
        state.closed_beds.add(state.bed_ids["resus"][-1])


def on_end(state: Any, event: EventSpec) -> None:
    if event.kind == "monitor_fault":
        state.closed_beds.discard(state.bed_ids["resus"][-1])
