"""Budget accounting: per-minute wages and rentals, one-off supply charges."""

from __future__ import annotations

from app.edsim import config as C
from app.edsim.entities import ON_BREAK, ON_DUTY, Patient, Staff
from app.edsim.state import SimState


def charge_supplies(state: SimState, patient: Patient) -> None:
    if patient.supplies_charged:
        return
    patient.supplies_charged = True
    state.charge("supplies", C.SUPPLY_COST[patient.acuity] * state.supply_multiplier)


def _wage_multiplier(state: SimState, staff: Staff) -> float:
    if staff.team == "agency":
        return C.AGENCY_MULTIPLIER
    shift = staff.shift_at(state.minute)
    if shift is not None and state.minute >= shift.scheduled_end:
        return C.OVERTIME_MULTIPLIER
    return 1.0


def hourly_burn(state: SimState) -> float:
    """Current spend per hour on wages and rentals, as a manager's dashboard would show."""
    total = 0.0
    for staff in state.staff.values():
        if staff.status in (ON_DUTY, ON_BREAK):
            total += C.WAGE_PER_HOUR[staff.role] * _wage_multiplier(state, staff)
    for bed in state.beds.values():
        if bed.temporary and not bed.removed:
            total += C.RENTAL_PER_HOUR["hallway_bed"]
    for item in state.equipment.values():
        if item.temporary and not item.removed:
            total += C.RENTAL_PER_HOUR[item.kind]
    return total


def step_costs(state: SimState) -> None:
    for staff in state.staff.values():
        if staff.status not in (ON_DUTY, ON_BREAK):
            continue
        multiplier = _wage_multiplier(state, staff)
        category = "agency" if staff.team == "agency" else ("overtime" if multiplier > 1.0 else "wages")
        state.charge(category, C.WAGE_PER_HOUR[staff.role] * multiplier / C.MINUTES_PER_HOUR)
    for bed in state.beds.values():
        if bed.temporary and not bed.removed:
            state.charge("rentals", C.RENTAL_PER_HOUR["hallway_bed"] / C.MINUTES_PER_HOUR)
    for item in state.equipment.values():
        if item.temporary and not item.removed:
            state.charge("rentals", C.RENTAL_PER_HOUR[item.kind] / C.MINUTES_PER_HOUR)
