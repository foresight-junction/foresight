"""Seeded world generator: draws every random number of an episode up front (see rng.py)."""

import math
import random

from . import constants as c
from .config import Config
from .model import EventSpec, PatientSpec, StaffSpec, World
from .rng import poisson, stream, weighted_choice
from .rules.events_extra import extra_events, extra_surges
from .rules.layouts import load_layout


def _uniform_int(rng: random.Random, lo: int, hi: int) -> int:
    return lo + int(rng.random() * (hi - lo + 1))


def _pick_nurses(rng: random.Random, nurses: list[str], count: int) -> tuple[str, ...]:
    pool = list(nurses)
    for i in range(count):  # partial Fisher-Yates
        j = i + int(rng.random() * (len(pool) - i))
        pool[i], pool[j] = pool[j], pool[i]
    return tuple(sorted(pool[:count]))


def _events(seed: int, nurses: list[str], config: Config) -> tuple[EventSpec, ...]:
    rng = stream(seed, "events")
    events = []
    for kind in c.EVENTS:
        cfg = config.events[kind]
        start = _uniform_int(rng, *cfg["window"])
        sick = _pick_nurses(rng, nurses, c.SICK_NURSES) if kind == "staff_sickness" else ()
        events.append(EventSpec(kind, start, cfg["duration"], cfg["warning"], sick))
    return tuple(events)


def _arrival_plan(seed: int, events: tuple[EventSpec, ...], config: Config) -> list[tuple[int, int, str]]:
    """(tick, esi, source) per patient, ordered by tick then base, flu, bus."""
    base_rng = stream(seed, "arrivals")
    surge = {
        "flu_wave": ("flu", c.FLU_EXTRA_PER_TICK, config.flu_mix, stream(seed, "flu")),
        "bus_crash": ("bus", c.BUS_EXTRA_PER_TICK, config.bus_mix, stream(seed, "bus")),
    } | extra_surges(seed, config.events, config.bus_mix)
    by_kind = {e.kind: e for e in events}
    plan = []
    for tick in range(c.TICKS):
        hour = (c.START_HOUR + tick * c.TICK_MINUTES / 60) % 24
        phase = 2 * math.pi * (hour - config.arrival_peak_hour) / 24
        mean = config.arrival_mean * (1 + config.arrival_amplitude * math.cos(phase))
        for _ in range(poisson(base_rng, mean)):
            plan.append((tick, weighted_choice(base_rng, c.ARRIVAL_MIX), "base"))
        for kind, (source, per_tick, mix, rng) in surge.items():
            event = by_kind[kind]
            if event.start_tick <= tick < event.start_tick + event.duration:
                plan.extend((tick, weighted_choice(rng, mix), source) for _ in range(per_tick))
    return plan


def generate_world(seed: int, config: Config | None = None) -> World:
    config = config or Config()
    staff = tuple(
        [StaffSpec(f"D{i}", "doctor") for i in range(1, c.N_DOCTORS + 1)]
        + [StaffSpec(f"N{i}", "nurse") for i in range(1, c.N_NURSES + 1)]
    )
    events = _events(seed, [s.id for s in staff if s.role == "nurse"], config)
    events += extra_events(seed, [s.id for s in staff if s.role == "doctor"], config.events)
    patients = []
    for n, (tick, esi, source) in enumerate(_arrival_plan(seed, events, config), start=1):
        pid = f"P{n:03d}"
        rng = stream(seed, f"patient:{pid}")
        ct_u, divert_u, upgrade_ct_u = rng.random(), rng.random(), rng.random()
        hazards = tuple(rng.random() for _ in range(c.TICKS))
        needs_ct = esi in c.CT_ESI and ct_u < c.CT_SHARE
        patients.append(PatientSpec(pid, tick, esi, needs_ct, source, divert_u, upgrade_ct_u, hazards))
    beds = load_layout(config.layout)
    return World(seed, tuple(patients), staff, events, config.budget, config.hard_limit, beds)
