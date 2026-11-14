"""Unexpected events: applies scheduled events to the state and expires active ones.

Every event changes engine state (staff availability, equipment, beds, prices, budget,
arrivals). The agent learns about an event only when it starts, through the active-event
list and the log.
"""

from __future__ import annotations

from typing import Any

from app.edsim import config as C
from app.edsim import resources
from app.edsim.entities import ActiveEvent, ScheduledEvent
from app.edsim.state import SimState


def _activate(
    state: SimState, event: ScheduledEvent, description: str, details: dict[str, Any], ends: int | None
) -> None:
    state.active_events[event.event_id] = ActiveEvent(
        event_id=event.event_id,
        kind=event.kind,
        started_min=state.minute,
        description=description,
        details=details,
        ends_min=ends,
    )
    state.emit(
        "event_started", event_id=event.event_id, event_kind=event.kind, description=description, **details
    )


def _staff_sickness(state: SimState, event: ScheduledEvent) -> None:
    p = event.params
    staff = state.staff[p["staff_id"]]
    staff.sick_from, staff.sick_until = p["sick_from"], p["sick_until"]
    if p["variant"] == "shift_cancelled":
        when = C.clock_label(p["sick_from"])
        text = f"{staff.staff_id} ({staff.role}) called in sick and will miss the shift starting {when}"
    else:
        text = f"{staff.staff_id} ({staff.role}) has fallen ill and is leaving the shift now"
    details = {"staff_id": staff.staff_id, "role": staff.role, "absent_from": C.clock_label(p["sick_from"])}
    _activate(state, event, text, details, p["sick_until"])


def _equipment_failure(state: SimState, event: ScheduledEvent) -> None:
    p = event.params
    item = state.equipment[p["equipment_id"]]
    if item.failed:  # two failures drawn for the same item overlap; the first one stands
        state.emit("event_skipped", visibility="truth", event_id=event.event_id)
        return
    item.failed = True
    item.repair_at = state.minute + p["downtime"]
    item.repair_estimate = state.minute + p["estimate"]
    if item.kind in C.HELD_EQUIPMENT and item.patient_id is not None:
        state.patients[item.patient_id].equipment.remove(item.equipment_id)
        item.patient_id = None
    elif item.kind in C.IMAGING:
        resources.abort_scan(state, item.equipment_id)
    details = {
        "equipment_id": item.equipment_id,
        "equipment_kind": item.kind,
        "estimated_back_in_service": C.clock_label(item.repair_estimate),
    }
    # Ends when the repair completes (resources.step_equipment), not at a fixed time.
    _activate(state, event, f"{item.equipment_id} ({item.kind}) is out of service", details, None)


def _bed_closure(state: SimState, event: ScheduledEvent) -> None:
    p = event.params
    until = state.minute + p["duration"]
    beds = sorted(
        (
            b
            for b in state.beds.values()
            if b.bed_class == p["bed_class"] and not b.temporary and not b.removed
        ),
        key=lambda b: (b.patient_id is not None, b.bed_id),
    )[: p["count"]]
    for bed in beds:
        if bed.patient_id is None:
            bed.closed_until = until
        else:
            bed.close_pending_until = until
    ids = [b.bed_id for b in beds]
    details = {"bed_ids": ids, "bed_class": p["bed_class"], "reopens_at": C.clock_label(until)}
    text = f"{len(ids)} {p['bed_class']} beds closed for deep cleaning; occupied ones close when vacated"
    _activate(state, event, text, details, until)


def _supply_shortage(state: SimState, event: ScheduledEvent) -> None:
    p = event.params
    until = state.minute + p["duration"]
    state.supply_multiplier = p["multiplier"]
    state.supply_until = until
    details = {"supply_cost_multiplier": p["multiplier"], "until": C.clock_label(until)}
    _activate(state, event, "Supplier shortage: treatment supplies cost more", details, until)


def _budget_cut(state: SimState, event: ScheduledEvent) -> None:
    amount = round(state.initial_budget * event.params["fraction"], 2)
    state.budget = round(state.budget - amount, 2)
    details = {"amount": amount, "new_budget": state.budget}
    _activate(state, event, "Finance office reduced the department budget", details, state.minute + 60)


def _demand_spike(state: SimState, event: ScheduledEvent) -> None:
    # The arrival increase is already in the generated arrivals; only its existence is announced.
    end = state.minute + event.params["duration"]
    _activate(state, event, "Regional services report a surge in demand", {}, end)


def _major_incident(state: SimState, event: ScheduledEvent) -> None:
    p = event.params
    details = {
        "estimated_casualties": p["estimate"],
        "first_arrival_expected": C.clock_label(p["first_arrival"]),
    }
    text = f"Major incident declared: about {p['estimate']} casualties expected by ambulance"
    _activate(state, event, text, details, p["first_arrival"] + p["spread"] + 60)


HANDLERS = {
    "staff_sickness": _staff_sickness,
    "equipment_failure": _equipment_failure,
    "bed_closure": _bed_closure,
    "supply_shortage": _supply_shortage,
    "budget_cut": _budget_cut,
    "demand_spike": _demand_spike,
    "major_incident": _major_incident,
}


def step_events(state: SimState) -> None:
    for event in list(state.active_events.values()):
        if event.ends_min is not None and state.minute >= event.ends_min:
            del state.active_events[event.event_id]
            state.emit("event_ended", event_id=event.event_id, event_kind=event.kind)
    if state.supply_until is not None and state.minute >= state.supply_until:
        state.supply_multiplier = 1.0
        state.supply_until = None
    for event in state.due_events():
        HANDLERS[event.kind](state, event)
