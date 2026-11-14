"""Agent actions. Each one validates everything first and only then mutates, so a
rejected action leaves the state exactly as it was."""

from __future__ import annotations

import math
from typing import Any

from app.edsim import config as C
from app.edsim import resources, rules, staffing
from app.edsim.entities import (
    BOARDING,
    DISCHARGED,
    DIVERTED,
    IN_TREATMENT,
    ON_BREAK,
    ON_DUTY,
    READY,
    WAITING,
    Bed,
    EDError,
    Equipment,
    Patient,
    Shift,
    Staff,
)
from app.edsim.flow import depart
from app.edsim.state import SimState

MAX_BATCH = 20
AGENCY_SKILLS = {
    "attending": frozenset({"critical_care"}),
    "resident": frozenset(),
    "nurse": frozenset({"triage"}),
}
AGENCY_TAG = {"attending": "att", "resident": "res", "nurse": "rn"}


# --- argument parsing and lookups -------------------------------------------------------
def _text(value: Any, arg: str) -> str:
    if not isinstance(value, str) or not value:
        raise EDError("INVALID_ARGUMENT", arg)
    return value


def _int(value: Any, arg: str, low: int, high: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise EDError("INVALID_ARGUMENT", f"{arg} must be an integer from {low} to {high}")
    return value


def _id_list(value: Any, arg: str) -> list[str]:
    if not isinstance(value, list) or not 1 <= len(value) <= MAX_BATCH:
        raise EDError("INVALID_ARGUMENT", f"{arg} must be a list of 1 to {MAX_BATCH} ids")
    ids = [_text(v, arg) for v in value]
    if len(set(ids)) != len(ids):
        raise EDError("INVALID_ARGUMENT", f"{arg} contains duplicates")
    return ids


def get_patient(state: SimState, patient_id: Any) -> Patient:
    patient = state.patients.get(_text(patient_id, "patient_id"))
    if patient is None or patient.status == DIVERTED:
        raise EDError("NOT_FOUND", f"patient {patient_id}")
    return patient


def _active_patient(state: SimState, patient_id: Any) -> Patient:
    patient = get_patient(state, patient_id)
    if patient.terminal:
        raise EDError("PATIENT_NOT_ACTIVE", patient.patient_id)
    return patient


def _staff(state: SimState, staff_id: Any) -> Staff:
    staff = state.staff.get(_text(staff_id, "staff_id"))
    if staff is None:
        raise EDError("NOT_FOUND", f"staff {staff_id}")
    return staff


def _bed(state: SimState, bed_id: Any) -> Bed:
    bed = state.beds.get(_text(bed_id, "bed_id"))
    if bed is None or bed.removed:
        raise EDError("NOT_FOUND", f"bed {bed_id}")
    return bed


def _equipment(state: SimState, equipment_id: Any) -> Equipment:
    item = state.equipment.get(_text(equipment_id, "equipment_id"))
    if item is None or item.removed:
        raise EDError("NOT_FOUND", f"equipment {equipment_id}")
    return item


# --- checks -------------------------------------------------------------------------------
def _check_bed(state: SimState, bed: Bed, patient: Patient) -> None:
    current = bed.state(state.minute)
    if current != "free":
        raise EDError("BED_UNAVAILABLE", f"{bed.bed_id} is {current}")
    if not rules.bed_class_ok(patient, bed.bed_class):
        allowed = ", ".join(rules.compatible_beds(patient))
        raise EDError("BED_INCOMPATIBLE", f"acuity {patient.acuity} needs one of: {allowed}")


def _check_staff(state: SimState, staff: Staff, patients: list[Patient]) -> None:
    if staff.status != ON_DUTY:
        raise EDError("STAFF_UNAVAILABLE", f"{staff.staff_id} is {staff.status}")
    if staff.role == "nurse" and staff.zone == "triage":
        raise EDError("WRONG_ZONE", staff.staff_id)
    for patient in patients:
        if not rules.qualified(staff, patient):
            raise EDError("STAFF_NOT_QUALIFIED", f"{staff.staff_id} cannot care for {patient.patient_id}")
    added = sum(rules.units_for(staff, p) for p in patients if p.patient_id not in staff.patients)
    used = staffing.load_units(state, staff)
    if used + added > C.CAPACITY[staff.role]:
        raise EDError("STAFF_AT_CAPACITY", f"{staff.staff_id} load {used}+{added} > {C.CAPACITY[staff.role]}")


def _check_equipment(state: SimState, item: Equipment) -> None:
    if item.kind not in C.HELD_EQUIPMENT:
        raise EDError("WRONG_EQUIPMENT", item.equipment_id)
    current = item.state(state.minute)
    if current != "available":
        raise EDError("EQUIPMENT_UNAVAILABLE", f"{item.equipment_id} is {current}")


def _role_check(staff: Staff, doctor: bool) -> None:
    if staff.is_doctor != doctor:
        raise EDError("STAFF_NOT_QUALIFIED", f"{staff.staff_id} is a {staff.role}")


def _in_bed(patient: Patient) -> None:
    if patient.status != IN_TREATMENT:
        raise EDError("WRONG_STATUS", f"{patient.patient_id} must be in a bed (in_treatment)")


# --- actions ------------------------------------------------------------------------------
def start_treatment(
    state: SimState,
    patient_id: Any,
    bed_id: Any,
    doctor_id: Any,
    nurse_id: Any,
    equipment_ids: Any = None,
) -> dict[str, Any]:
    patient = _active_patient(state, patient_id)
    if not patient.triaged:
        raise EDError("NOT_TRIAGED", patient.patient_id)
    if patient.status != WAITING:
        raise EDError("WRONG_STATUS", f"{patient.patient_id} is {patient.status}")
    bed = _bed(state, bed_id)
    _check_bed(state, bed, patient)
    doctor, nurse = _staff(state, doctor_id), _staff(state, nurse_id)
    _role_check(doctor, doctor=True)
    _role_check(nurse, doctor=False)
    _check_staff(state, doctor, [patient])
    _check_staff(state, nurse, [patient])
    ids = _id_list(equipment_ids, "equipment_ids") if equipment_ids else []
    items = [_equipment(state, e) for e in ids]
    for item in items:
        _check_equipment(state, item)

    resources.place(state, patient, bed)
    staffing.attach(doctor, patient, state)
    staffing.attach(nurse, patient, state)
    for item in items:
        item.patient_id = patient.patient_id
        patient.equipment.append(item.equipment_id)
    return {"patient_id": patient.patient_id, "bed_id": bed.bed_id, "status": patient.status}


def assign_bed(state: SimState, patient_id: Any, bed_id: Any) -> dict[str, Any]:
    """Place or move a patient. Patients whose treatment is complete (ready or boarding)
    may move to any free bed, e.g. a hallway bed, to release an acute bed."""
    patient = _active_patient(state, patient_id)
    if not patient.triaged:
        raise EDError("NOT_TRIAGED", patient.patient_id)
    if patient.status not in (WAITING, IN_TREATMENT, READY, BOARDING):
        raise EDError("WRONG_STATUS", f"{patient.patient_id} is {patient.status}")
    bed = _bed(state, bed_id)
    if patient.bed_id == bed.bed_id:
        raise EDError("INVALID_ARGUMENT", "patient is already in that bed")
    treatment_done = patient.status in (READY, BOARDING)
    if treatment_done:
        if bed.state(state.minute) != "free":
            raise EDError("BED_UNAVAILABLE", f"{bed.bed_id} is {bed.state(state.minute)}")
    else:
        _check_bed(state, bed, patient)
    previous = patient.bed_id
    if previous is not None:
        resources.start_cleaning(state, state.beds[previous])
    if treatment_done:
        bed.patient_id = patient.patient_id
        bed.clean_until = None
        patient.bed_id = bed.bed_id
    else:
        resources.place(state, patient, bed)
    return {"patient_id": patient.patient_id, "bed_id": bed.bed_id, "previous_bed_id": previous}


def assign_staff(state: SimState, staff_id: Any, patient_ids: Any) -> dict[str, Any]:
    staff = _staff(state, staff_id)
    patients = [_active_patient(state, pid) for pid in _id_list(patient_ids, "patient_ids")]
    for patient in patients:
        _in_bed(patient)
    _check_staff(state, staff, patients)
    for patient in patients:
        staffing.attach(staff, patient, state)
    return {"staff_id": staff.staff_id, "patients": list(staff.patients)}


def release_staff(state: SimState, staff_id: Any, patient_id: Any) -> dict[str, Any]:
    staff = _staff(state, staff_id)
    patient = get_patient(state, patient_id)
    if patient.patient_id not in staff.patients:
        raise EDError("INVALID_ARGUMENT", f"{staff.staff_id} is not assigned to {patient.patient_id}")
    staffing.detach(staff, patient)
    return {"staff_id": staff.staff_id, "patients": list(staff.patients)}


def allocate_equipment(state: SimState, equipment_id: Any, patient_id: Any) -> dict[str, Any]:
    item = _equipment(state, equipment_id)
    patient = _active_patient(state, patient_id)
    _in_bed(patient)
    _check_equipment(state, item)
    item.patient_id = patient.patient_id
    patient.equipment.append(item.equipment_id)
    return {"equipment_id": item.equipment_id, "patient_id": patient.patient_id}


def release_equipment(state: SimState, equipment_id: Any) -> dict[str, Any]:
    item = _equipment(state, equipment_id)
    if item.kind not in C.HELD_EQUIPMENT:
        raise EDError("WRONG_EQUIPMENT", item.equipment_id)
    if item.patient_id is None:
        raise EDError("INVALID_ARGUMENT", f"{item.equipment_id} is not allocated")
    state.patients[item.patient_id].equipment.remove(item.equipment_id)
    item.patient_id = None
    return {"equipment_id": item.equipment_id}


def discharge_patient(state: SimState, patient_ids: Any) -> dict[str, Any]:
    patients = [_active_patient(state, pid) for pid in _id_list(patient_ids, "patient_ids")]
    for patient in patients:
        if patient.status != READY:
            raise EDError("NOT_READY", f"{patient.patient_id} is {patient.status}")
    results = []
    for patient in patients:
        if patient.disposition == "home":
            depart(state, patient, DISCHARGED)
        else:
            staffing.detach_patient(state, patient)
            resources.release_equipment(state, patient)
            patient.status = BOARDING
            patient.boarding_since = state.minute
            state.inpatient_queue.append(patient.patient_id)
            state.emit("patient_boarding", patient_id=patient.patient_id)
        results.append({"patient_id": patient.patient_id, "status": patient.status})
    return {"results": results}


def request_transfer(state: SimState, patient_id: Any) -> dict[str, Any]:
    patient = _active_patient(state, patient_id)
    if patient.status != BOARDING or patient.transfer_at is not None:
        raise EDError("WRONG_STATUS", "only boarding patients without a pending transfer can be transferred")
    patient.transfer_at = state.minute + C.TRANSFER_MINUTES
    if patient.patient_id in state.inpatient_queue:
        state.inpatient_queue.remove(patient.patient_id)
    state.charge("transfers", C.TRANSFER_FEE)
    return {
        "patient_id": patient.patient_id,
        "departs_at": C.clock_label(patient.transfer_at),
        "cost": C.TRANSFER_FEE,
    }


def set_staff_zone(state: SimState, staff_id: Any, zone: Any) -> dict[str, Any]:
    staff = _staff(state, staff_id)
    if zone not in ("floor", "triage"):
        raise EDError("INVALID_ARGUMENT", "zone must be 'floor' or 'triage'")
    if staff.role != "nurse":
        raise EDError("STAFF_NOT_QUALIFIED", "only nurses change zone")
    if zone == "triage" and "triage" not in staff.skills:
        raise EDError("STAFF_NOT_QUALIFIED", f"{staff.staff_id} has no triage skill")
    if zone == "triage" and staff.patients:
        raise EDError("STAFF_BUSY", f"{staff.staff_id} has {len(staff.patients)} patients")
    if zone == "floor":
        staffing.abort_triage(staff)
    staff.zone = zone
    return {"staff_id": staff.staff_id, "zone": zone}


def schedule_break(state: SimState, staff_id: Any, minutes: Any) -> dict[str, Any]:
    staff = _staff(state, staff_id)
    minutes = _int(minutes, "minutes", *C.BREAK_RANGE)
    if staff.status != ON_DUTY:
        raise EDError("STAFF_UNAVAILABLE", f"{staff.staff_id} is {staff.status}")
    staff.break_until = state.minute + minutes
    staff.status = ON_BREAK
    staffing.abort_triage(staff)
    return {"staff_id": staff.staff_id, "back_at": C.clock_label(staff.break_until)}


def extend_shift(state: SimState, staff_id: Any, hours: Any) -> dict[str, Any]:
    staff = _staff(state, staff_id)
    hours = _int(hours, "hours", *C.EXTEND_RANGE)
    shift = staff.shift_at(state.minute)
    if staff.status not in (ON_DUTY, ON_BREAK) or shift is None:
        raise EDError("STAFF_UNAVAILABLE", f"{staff.staff_id} is {staff.status}")
    new_end = shift.end + hours * C.MINUTES_PER_HOUR
    if new_end - shift.start > C.MAX_CONTINUOUS_DUTY:
        raise EDError("SHIFT_LIMIT", f"{staff.staff_id} would work {(new_end - shift.start) // 60} hours")
    shift.end = new_end
    return {
        "staff_id": staff.staff_id,
        "shift_ends": C.clock_label(new_end),
        "overtime_from": C.clock_label(shift.scheduled_end),
    }


def request_temporary_staff(state: SimState, role: Any, hours: Any) -> dict[str, Any]:
    if role not in C.ROLES:
        raise EDError("INVALID_ARGUMENT", f"role must be one of {', '.join(C.ROLES)}")
    hours = _int(hours, "hours", *C.AGENCY_HOURS)
    if state.agency_requests[state.day_index] >= state.config.agency_daily_limit:
        raise EDError("LIMIT_REACHED", f"{state.config.agency_daily_limit} agency requests per day")
    start = state.minute + C.LEAD_TIME_MINUTES
    end = start + hours * C.MINUTES_PER_HOUR
    staff_id = state.next_id(f"agency-{AGENCY_TAG[role]}")
    state.staff[staff_id] = Staff(
        staff_id=staff_id,
        role=role,
        skills=AGENCY_SKILLS[role],
        team="agency",
        shifts=[Shift(start=start, end=end, scheduled_end=end)],
        fatigue=10.0,
    )
    state.agency_requests[state.day_index] += 1
    state.charge("agency", C.AGENCY_CALLOUT_FEE)
    return {
        "staff_id": staff_id,
        "role": role,
        "arrives_at": C.clock_label(start),
        "leaves_at": C.clock_label(end),
        "cost_per_hour": C.WAGE_PER_HOUR[role] * C.AGENCY_MULTIPLIER,
        "callout_fee": C.AGENCY_CALLOUT_FEE,
    }


def request_resources(state: SimState, kind: Any, hours: Any) -> dict[str, Any]:
    if kind not in C.RENTAL_PER_HOUR:
        raise EDError("INVALID_ARGUMENT", f"kind must be one of {', '.join(sorted(C.RENTAL_PER_HOUR))}")
    hours = _int(hours, "hours", *C.RENTAL_HOURS)
    if state.rental_requests[state.day_index] >= state.config.rental_daily_limit:
        raise EDError("LIMIT_REACHED", f"{state.config.rental_daily_limit} rentals per day")
    start = state.minute + C.LEAD_TIME_MINUTES
    until = start + hours * C.MINUTES_PER_HOUR
    if kind == "hallway_bed":
        resource_id = state.next_id("HALL")
        state.beds[resource_id] = Bed(
            bed_id=resource_id, bed_class="hallway", temporary=True, available_from=start, rental_until=until
        )
    else:
        resource_id = state.next_id(f"{C.EQUIPMENT_PREFIX[kind]}-R")
        state.equipment[resource_id] = Equipment(
            equipment_id=resource_id, kind=kind, temporary=True, available_from=start, rental_until=until
        )
    state.rental_requests[state.day_index] += 1
    return {
        "resource_id": resource_id,
        "kind": kind,
        "available_at": C.clock_label(start),
        "rental_until": C.clock_label(until),
        "cost_per_hour": C.RENTAL_PER_HOUR[kind],
    }


def request_repair(state: SimState, equipment_id: Any) -> dict[str, Any]:
    item = _equipment(state, equipment_id)
    if not item.failed:
        raise EDError("NOT_FAILED", item.equipment_id)
    if item.expedited:
        raise EDError("ALREADY_EXPEDITED", item.equipment_id)
    now = state.minute
    item.repair_at = now + math.ceil(max(0, item.repair_at - now) * C.REPAIR_SPEEDUP)
    item.repair_estimate = now + math.ceil(max(0, item.repair_estimate - now) * C.REPAIR_SPEEDUP)
    item.expedited = True
    state.charge("repairs", C.REPAIR_FEE)
    return {
        "equipment_id": item.equipment_id,
        "estimated_back_in_service": C.clock_label(item.repair_estimate),
        "cost": C.REPAIR_FEE,
    }


def set_diversion(state: SimState, active: Any) -> dict[str, Any]:
    if not isinstance(active, bool):
        raise EDError("INVALID_ARGUMENT", "active must be true or false")
    state.diversion = active
    return {"diversion": active}


ACTIONS = {
    "start_treatment": start_treatment,
    "assign_bed": assign_bed,
    "assign_staff": assign_staff,
    "release_staff": release_staff,
    "allocate_equipment": allocate_equipment,
    "release_equipment": release_equipment,
    "discharge_patient": discharge_patient,
    "request_transfer": request_transfer,
    "set_staff_zone": set_staff_zone,
    "schedule_break": schedule_break,
    "extend_shift": extend_shift,
    "request_temporary_staff": request_temporary_staff,
    "request_resources": request_resources,
    "request_repair": request_repair,
    "set_diversion": set_diversion,
}
