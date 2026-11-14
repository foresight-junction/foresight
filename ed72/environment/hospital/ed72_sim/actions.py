"""Tick step 5: validate and apply the agent's actions in order (CONTRACTS v1 reasons)."""

from collections.abc import Callable

from ed72_sim import constants as c
from ed72_sim.state import BED_IDS, StaffState, State

Emit = Callable[..., None]
ASSIGNABLE = ("on_shift", "resting")


def apply_actions(state: State, tick: int, actions: list, emit: Emit) -> list[dict]:
    results = []
    rejected = []
    for index, action in enumerate(actions):
        reason = _apply(state, tick, action, emit)
        if reason is None:
            results.append({"index": index, "ok": True})
        else:
            results.append({"index": index, "ok": False, "reason": reason})
            rejected.append({"index": index, "action": action, "reason": reason})
    state.last_rejected = rejected
    return results


def _apply(state: State, tick: int, action: object, emit: Emit) -> str | None:
    if not isinstance(action, dict):
        return "bad_action"
    handlers = {
        "admit": _admit,
        "assign": _assign,
        "agency": _agency,
        "repair": _repair,
        "divert": _divert,
    }
    kind = action.get("type")
    handler = handlers.get(kind) if isinstance(kind, str) else None
    if handler is None:
        return "bad_action"
    return handler(state, tick, action, emit)


def _admit(state: State, tick: int, action: dict, emit: Emit) -> str | None:
    patient_id, zone = action.get("patient"), action.get("zone")
    if not isinstance(patient_id, str) or not isinstance(zone, str) or zone not in c.ZONES:
        return "bad_action"
    patient = state.patients.get(patient_id)
    if patient is None:
        return "unknown_patient"
    if patient.status != "waiting":
        return "not_waiting"
    if zone not in c.ZONE_EXTRA_TICKS[patient.esi]:
        return "zone_not_allowed"
    bed = next((b for b in BED_IDS[zone] if state.beds[b] is None), None)
    if bed is None:
        return "no_free_bed"
    state.beds[bed] = patient_id
    patient.status = "bed"
    patient.zone, patient.bed, patient.admitted_tick = zone, bed, tick
    patient.needed = c.TREATMENT_TICKS[patient.esi] + c.ZONE_EXTRA_TICKS[patient.esi][zone]
    emit("admitted", patient=patient_id, zone=zone, bed=bed)
    return None


def _assign(state: State, tick: int, action: dict, emit: Emit) -> str | None:
    staff_id, target = action.get("staff"), action.get("to")
    if not isinstance(staff_id, str) or not isinstance(target, str) or target not in (*c.ZONES, "rest"):
        return "bad_action"
    person = state.find_staff(staff_id)
    if person is None:
        return "unknown_staff"
    if person.status not in ASSIGNABLE:
        return "staff_unavailable"
    person.location = target
    person.status = "resting" if target == "rest" else "on_shift"
    return None


def _spend(state: State, hard_limit: int, item: str, amount: int, emit: Emit) -> str | None:
    if state.spent + amount > hard_limit:
        return "over_hard_limit"
    state.spent += amount
    emit("spend", item=item, amount=amount)
    return None


def _agency(state: State, tick: int, action: dict, emit: Emit) -> str | None:
    role = action.get("role")
    if not isinstance(role, str) or role not in c.AGENCY_COST:
        return "bad_action"
    reason = _spend(state, state.world.hard_limit, f"agency_{role}", c.AGENCY_COST[role], emit)
    if reason is not None:
        return reason
    state.agency_ordered[role] += 1
    arrive = tick + c.AGENCY_DELAY
    state.staff.append(
        StaffState(
            id=f"A{role[0].upper()}{state.agency_ordered[role]}",
            role=role,
            agency=True,
            status="agency_ordered",
            arrive_tick=arrive,
            leave_tick=arrive + c.AGENCY_STAY,
        )
    )
    return None


def _repair(state: State, tick: int, action: dict, emit: Emit) -> str | None:
    if state.ct_return_tick is None:
        return "ct_not_broken"
    reason = _spend(state, state.world.hard_limit, "repair", c.REPAIR_COST, emit)
    if reason is not None:
        return reason
    state.ct_return_tick = min(state.ct_return_tick, tick + c.REPAIR_TICKS)
    return None


def _divert(state: State, tick: int, action: dict, emit: Emit) -> str | None:
    if state.divert_last - tick > 0:
        return "diversion_active"
    state.divert_last = tick + c.DIVERT_TICKS
    return None
