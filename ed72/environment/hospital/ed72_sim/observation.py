"""The agent's view of the state (CONTRACTS v1 Observation). Never reads world data about the future."""

from ed72_sim import constants as c
from ed72_sim.state import BED_IDS, StaffState, State


def clock(tick: int) -> str:
    minutes = c.START_HOUR * 60 + c.TICK_MINUTES * tick
    return f"Day {minutes // 1440 + 1} {minutes % 1440 // 60:02d}:{minutes % 60:02d}"


def _ticks_until_change(s: StaffState, tick: int) -> int | None:
    if s.status == "agency_left":
        return None
    due = [x for x in (s.return_tick, s.arrive_tick, s.leave_tick) if x is not None]
    return max(0, min(due) - tick) if due else None


def _staff(s: StaffState, tick: int) -> dict:
    return {
        "id": s.id,
        "role": s.role,
        "agency": s.agency,
        "location": s.location,
        "fatigue": s.fatigue10 / 10,
        "counts_as": c.TIRED_COUNTS_AS if s.tired else 1,
        "status": s.status,
        "ticks_until_change": _ticks_until_change(s, tick),
    }


def _beds(state: State) -> list[dict]:
    covered = set(state.covered_ids())
    rows = []
    for zone in c.ZONES:
        for bed in BED_IDS[zone]:
            pid = state.beds[bed]
            if pid is None:
                rows.append({"zone": zone, "bed": bed, "patient": None})
                continue
            p = state.patients[pid]
            half = (p.needed + 1) // 2
            rows.append(
                {
                    "zone": zone,
                    "bed": bed,
                    "patient": pid,
                    "esi": p.esi,
                    "treated_ticks": p.treated,
                    "treatment_ticks": p.needed,
                    "covered": pid in covered,
                    "waiting_for_ct": p.needs_ct
                    and not p.scanned
                    and p.treated == half
                    and not state.ct_working,
                }
            )
    return rows


def build_observation(state: State, tick: int, finished: bool) -> dict:
    world = state.world
    diversion_left = max(0, state.divert_last - tick)
    ct_left = 0 if state.ct_return_tick is None else max(0, state.ct_return_tick - tick)
    return {
        "tick": tick,
        "clock": clock(tick),
        "ticks_left": 0 if finished else c.TICKS - tick,
        "finished": finished,
        "budget": {"spent": state.spent, "budget": world.budget, "hard_limit": world.hard_limit},
        "waiting": [
            {
                "id": p.spec.id,
                "esi": p.esi,
                "arrived_tick": p.spec.arrival_tick,
                "waited_ticks": tick - p.spec.arrival_tick,
                "needs_ct": p.needs_ct,
            }
            for p in state.waiting()
        ],
        "beds": _beds(state),
        "staff": [_staff(s, tick) for s in state.staff],
        "ct": {"working": state.ct_working, "down_ticks_left": ct_left},
        "warnings": [
            {"event": e.kind, "start_tick": e.start_tick}
            for e in world.events
            if e.warning_ticks > 0 and e.start_tick - e.warning_ticks <= tick < e.start_tick + e.duration
        ],
        "diversion": {"active": diversion_left > 0, "ticks_left": diversion_left},
        "totals": dict(state.totals),
        "last_rejected": list(state.last_rejected),
    }
