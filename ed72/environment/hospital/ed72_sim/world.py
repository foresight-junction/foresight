"""Seeded world generator: draws every random number of an episode up front (see rng.py)."""

import math
import random

from . import constants as c
from .model import EventSpec, PatientSpec, StaffSpec, World
from .rng import poisson, stream, weighted_choice


def _uniform_int(rng: random.Random, lo: int, hi: int) -> int:
    return lo + int(rng.random() * (hi - lo + 1))


def _pick_nurses(rng: random.Random, nurses: list[str], count: int) -> tuple[str, ...]:
    pool = list(nurses)
    for i in range(count):  # partial Fisher-Yates
        j = i + int(rng.random() * (len(pool) - i))
        pool[i], pool[j] = pool[j], pool[i]
    return tuple(sorted(pool[:count]))


def _events(seed: int, nurses: list[str]) -> tuple[EventSpec, ...]:
    rng = stream(seed, "events")
    events = []
    for kind, cfg in c.EVENTS.items():
        start = _uniform_int(rng, *cfg["window"])
        sick = _pick_nurses(rng, nurses, c.SICK_NURSES) if kind == "staff_sickness" else ()
        events.append(EventSpec(kind, start, cfg["duration"], cfg["warning"], sick))
    return tuple(events)


def _arrival_plan(seed: int, events: tuple[EventSpec, ...]) -> list[tuple[int, int, str]]:
    """(tick, esi, source) per patient, ordered by tick then base, flu, bus."""
    base_rng = stream(seed, "arrivals")
    surge = {
        "flu_wave": ("flu", c.FLU_EXTRA_PER_TICK, c.FLU_MIX, stream(seed, "flu")),
        "bus_crash": ("bus", c.BUS_EXTRA_PER_TICK, c.BUS_MIX, stream(seed, "bus")),
    }
    by_kind = {e.kind: e for e in events}
    plan = []
    for tick in range(c.TICKS):
        hour = (c.START_HOUR + tick * c.TICK_MINUTES / 60) % 24
        phase = 2 * math.pi * (hour - c.ARRIVAL_PEAK_HOUR) / 24
        mean = c.ARRIVAL_MEAN * (1 + c.ARRIVAL_AMPLITUDE * math.cos(phase))
        for _ in range(poisson(base_rng, mean)):
            plan.append((tick, weighted_choice(base_rng, c.ARRIVAL_MIX), "base"))
        for kind, (source, per_tick, mix, rng) in surge.items():
            event = by_kind[kind]
            if event.start_tick <= tick < event.start_tick + event.duration:
                plan.extend((tick, weighted_choice(rng, mix), source) for _ in range(per_tick))
    return plan


def generate_world(seed: int) -> World:
    staff = tuple(
        [StaffSpec(f"D{i}", "doctor") for i in range(1, c.N_DOCTORS + 1)]
        + [StaffSpec(f"N{i}", "nurse") for i in range(1, c.N_NURSES + 1)]
    )
    events = _events(seed, [s.id for s in staff if s.role == "nurse"])
    patients = []
    for n, (tick, esi, source) in enumerate(_arrival_plan(seed, events), start=1):
        pid = f"P{n:03d}"
        rng = stream(seed, f"patient:{pid}")
        ct_u, divert_u, upgrade_ct_u = rng.random(), rng.random(), rng.random()
        hazards = tuple(rng.random() for _ in range(c.TICKS))
        needs_ct = esi in c.CT_ESI and ct_u < c.CT_SHARE
        patients.append(PatientSpec(pid, tick, esi, needs_ct, source, divert_u, upgrade_ct_u, hazards))
    return World(seed, tuple(patients), staff, events, c.BUDGET, c.HARD_LIMIT)
