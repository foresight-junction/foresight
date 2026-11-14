"""Hand-built worlds for engine tests. A hazard uniform of 0.999 never fires, 0.0 always fires."""

from ed72_sim import constants as c
from ed72_sim.engine import Simulation
from ed72_sim.model import EventSpec, PatientSpec, StaffSpec, World

SAFE = 0.999


def patient(
    n: int,
    tick: int = 0,
    esi: int = 3,
    *,
    needs_ct: bool = False,
    source: str = "base",
    divert_u: float = 0.99,
    upgrade_ct_u: float = 0.99,
    hazard: float = SAFE,
    hazard_at: dict[int, float] | None = None,
) -> PatientSpec:
    u = [hazard] * c.TICKS
    for t, value in (hazard_at or {}).items():
        u[t] = value
    return PatientSpec(f"P{n:03d}", tick, esi, needs_ct, source, divert_u, upgrade_ct_u, tuple(u))


def make_world(
    patients: tuple[PatientSpec, ...] | list[PatientSpec] = (),
    events: tuple[EventSpec, ...] | list[EventSpec] = (),
    hard_limit: int = c.HARD_LIMIT,
) -> World:
    staff = tuple(StaffSpec(f"D{i}", "doctor") for i in range(1, 7))
    staff += tuple(StaffSpec(f"N{i}", "nurse") for i in range(1, 10))
    ordered = tuple(sorted(patients, key=lambda p: (p.arrival_tick, p.id)))
    return World(1, ordered, staff, tuple(events), c.BUDGET, hard_limit)


def crew(zone: str, doctors: int, nurses: int) -> list[dict]:
    """Assign actions that put the first doctors and nurses on shift in a zone."""
    actions = [{"type": "assign", "staff": f"D{i}", "to": zone} for i in range(1, doctors + 1)]
    return actions + [{"type": "assign", "staff": f"N{i}", "to": zone} for i in range(1, nurses + 1)]


def admit(pid: str, zone: str) -> dict:
    return {"type": "admit", "patient": pid, "zone": zone}


def advance(sim: Simulation, ticks: int, actions: list[dict] | None = None) -> None:
    """Step `ticks` times; the actions go in the first step only."""
    for i in range(ticks):
        sim.step(actions if i == 0 and actions else [])


def lines(sim: Simulation, event: str, **match: object) -> list[dict]:
    return [e for e in sim.events if e.get("event") == event and all(e.get(k) == v for k, v in match.items())]


def bed(sim: Simulation, bed_id: str) -> dict:
    return next(b for b in sim.observe()["beds"] if b["bed"] == bed_id)


def staff(sim: Simulation, staff_id: str) -> dict:
    return next(s for s in sim.observe()["staff"] if s["id"] == staff_id)
