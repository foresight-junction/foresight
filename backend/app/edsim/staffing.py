"""Staff scheduling, assignment bookkeeping, breaks and fatigue."""

from __future__ import annotations

from app.edsim import config as C
from app.edsim import rules
from app.edsim.entities import OFF_DUTY, ON_BREAK, ON_DUTY, SICK, Patient, Staff
from app.edsim.state import SimState


def load_units(state: SimState, staff: Staff) -> int:
    return sum(rules.units_for(staff, state.patients[pid]) for pid in staff.patients)


def attach(staff: Staff, patient: Patient, state: SimState) -> None:
    """Make `staff` the patient's doctor or nurse, replacing whoever held that slot."""
    slot = "doctor_id" if staff.is_doctor else "nurse_id"
    current = getattr(patient, slot)
    if current == staff.staff_id:
        return
    if current is not None:
        state.staff[current].patients.remove(patient.patient_id)
    setattr(patient, slot, staff.staff_id)
    staff.patients.append(patient.patient_id)


def detach(staff: Staff, patient: Patient) -> None:
    slot = "doctor_id" if staff.is_doctor else "nurse_id"
    if getattr(patient, slot) == staff.staff_id:
        setattr(patient, slot, None)
    if patient.patient_id in staff.patients:
        staff.patients.remove(patient.patient_id)


def detach_patient(state: SimState, patient: Patient) -> None:
    for staff_id in (patient.doctor_id, patient.nurse_id):
        if staff_id is not None:
            detach(state.staff[staff_id], patient)


def release_all_patients(state: SimState, staff: Staff) -> list[str]:
    released = list(staff.patients)
    for pid in released:
        detach(staff, state.patients[pid])
    return released


def abort_triage(staff: Staff) -> None:
    staff.triaging = None
    staff.triage_done_at = None


def step_shifts(state: SimState) -> None:
    """Moves staff between duty states at the start of each minute. Staff going off duty or
    falling sick hand over: they are released from their patients, who stall until the
    agent reassigns them."""
    minute = state.minute
    for staff in state.staff.values():
        if staff.break_until is not None and minute >= staff.break_until:
            staff.break_until = None
        shift = staff.shift_at(minute)
        if staff.is_sick(minute):
            target = SICK
        elif shift is None:
            target = OFF_DUTY
        elif staff.break_until is not None:
            target = ON_BREAK
        else:
            target = ON_DUTY
        if target == staff.status:
            continue
        previous = staff.status
        staff.status = target
        if target in (OFF_DUTY, SICK):
            released = release_all_patients(state, staff)
            abort_triage(staff)
            staff.break_until = None
            state.emit(
                "staff_sick" if target == SICK else "staff_off_duty",
                staff_id=staff.staff_id,
                released_patients=released,
            )
        elif target == ON_DUTY and previous == ON_BREAK:
            state.emit("break_ended", staff_id=staff.staff_id)
        elif target == ON_DUTY:
            state.emit("staff_on_duty", staff_id=staff.staff_id, role=staff.role, zone=staff.zone)


def step_fatigue(state: SimState) -> None:
    minute = state.minute
    night = C.FATIGUE_NIGHT if C.is_night(minute) else 1.0
    for staff in state.staff.values():
        if staff.status == ON_DUTY:
            if staff.role == "nurse" and staff.zone == "triage":
                load = 0.75 if staff.triaging else 0.25
            else:
                load = load_units(state, staff) / C.CAPACITY[staff.role]
            shift = staff.shift_at(minute)
            overtime = C.FATIGUE_OVERTIME if shift is not None and minute >= shift.scheduled_end else 1.0
            staff.fatigue += C.FATIGUE_BASE * (0.5 + load) * night * overtime
        elif staff.status == ON_BREAK:
            staff.fatigue -= C.FATIGUE_BREAK_RECOVERY
        else:
            staff.fatigue -= C.FATIGUE_REST_RECOVERY
        staff.fatigue = min(100.0, max(0.0, staff.fatigue))
        if staff.status in (ON_DUTY, ON_BREAK):
            state.acc["staff_duty_minutes"] += 1
            if staff.fatigue > C.FATIGUE_HIGH:
                state.acc["staff_high_fatigue_minutes"] += 1
