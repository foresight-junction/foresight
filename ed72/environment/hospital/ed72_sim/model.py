"""The generated world: everything the seed fixes, before any agent acts.

All randomness lives here, drawn by the world generator (world.py). The sim core draws no random
numbers, so an agent's actions change which hazards a patient is exposed to, never the dice
(common random numbers, issue #32).
"""

from dataclasses import dataclass

from . import constants as c


@dataclass(frozen=True)
class PatientSpec:
    id: str  # "P001", "P002", ... in arrival order
    arrival_tick: int
    esi: int  # ESI on arrival
    needs_ct: bool
    source: str  # "base", "flu" or "bus"
    divert_u: float  # turned away if a diversion is active and divert_u < DIVERT_SHARE
    upgrade_ct_u: float  # after an ESI 3 -> 2 upgrade, needs CT if upgrade_ct_u < CT_SHARE
    hazard_u: tuple[float, ...]  # one uniform per tick, indexed by tick; a hazard fires if u < p


@dataclass(frozen=True)
class StaffSpec:
    id: str  # "D1".."D6", "N1".."N9"; agency staff are created by the sim when ordered
    role: str  # "doctor" or "nurse"


@dataclass(frozen=True)
class EventSpec:
    kind: str  # "staff_sickness", "flu_wave", "ct_breakdown" or "bus_crash"
    start_tick: int
    duration: int
    warning_ticks: int  # 0 = unannounced; otherwise shown from start_tick - warning_ticks
    staff: tuple[str, ...] = ()  # the nurses who fall sick, for staff_sickness


@dataclass(frozen=True)
class World:
    seed: int
    patients: tuple[PatientSpec, ...]  # sorted by arrival_tick, then id
    staff: tuple[StaffSpec, ...]
    events: tuple[EventSpec, ...]
    budget: int
    hard_limit: int
    bed_counts: tuple[int, ...] = tuple(c.BEDS[z] for z in c.ZONES)  # per zone, in c.ZONES order
