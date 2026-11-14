"""Patient flow: arrivals, triage, treatment progress, completion and departures."""

from __future__ import annotations

from app.edsim import config as C
from app.edsim import resources, rules, staffing
from app.edsim.budget import charge_supplies
from app.edsim.entities import (
    ADMITTED,
    AWAITING_TRIAGE,
    BOARDING,
    DIVERTED,
    IN_TREATMENT,
    ON_DUTY,
    READY,
    TRANSFERRED,
    WAITING,
    Patient,
)
from app.edsim.state import SimState


def depart(state: SimState, patient: Patient, status: str) -> None:
    """Patient leaves the department: free every resource; the bed goes to cleaning."""
    staffing.detach_patient(state, patient)
    resources.release_equipment(state, patient)
    resources.leave_imaging(state, patient)
    if patient.patient_id in state.inpatient_queue:
        state.inpatient_queue.remove(patient.patient_id)
    for staff in state.staff.values():
        if staff.triaging == patient.patient_id:
            staffing.abort_triage(staff)
    if patient.bed_id is not None:
        resources.start_cleaning(state, state.beds[patient.bed_id])
        patient.bed_id = None
    patient.status = status
    patient.departed_min = state.minute
    state.emit("patient_departed", patient_id=patient.patient_id, outcome=status)


def step_arrivals(state: SimState) -> None:
    for patient in state.due_patients():
        state.patients[patient.patient_id] = patient
        if state.diversion and patient.mode == "ambulance" and patient.incident_id is None:
            patient.status = DIVERTED
            patient.departed_min = state.minute
            state.acc["diverted"] += 1
            state.emit("ambulance_diverted")
            continue
        if patient.incident_id:
            # Major-incident casualties arrive with a field triage category.
            patient.triaged = True
            patient.triage_min = state.minute
            patient.status = WAITING
        state.emit(
            "patient_arrived",
            patient_id=patient.patient_id,
            mode=patient.mode,
            complaint=patient.complaint,
            incident_id=patient.incident_id,
            acuity=patient.acuity if patient.triaged else None,
        )


def step_triage(state: SimState) -> None:
    for staff in state.staff.values():
        if staff.triaging is None or staff.triage_done_at is None or state.minute < staff.triage_done_at:
            continue
        patient = state.patients[staff.triaging]
        staffing.abort_triage(staff)
        if patient.status != AWAITING_TRIAGE:
            continue
        patient.triaged = True
        patient.triage_min = state.minute
        patient.status = WAITING
        state.emit(
            "patient_triaged", patient_id=patient.patient_id, acuity=patient.acuity, staff_id=staff.staff_id
        )

    in_progress = {s.triaging for s in state.staff.values() if s.triaging}
    queue = sorted(
        (
            p
            for p in state.patients.values()
            if p.status == AWAITING_TRIAGE and p.patient_id not in in_progress
        ),
        key=lambda p: (p.mode != "ambulance", p.arrival_min, p.patient_id),
    )
    nurses = [
        s
        for s in state.staff.values()
        if s.role == "nurse" and s.zone == "triage" and s.status == ON_DUTY and s.triaging is None
    ]
    for nurse, patient in zip(nurses, queue, strict=False):
        nurse.triaging = patient.patient_id
        nurse.triage_done_at = state.minute + patient.triage_minutes


def stall_reasons(state: SimState, patient: Patient) -> tuple[list[str], float, float]:
    """Why treatment cannot progress this minute, plus the speed and risk factors from
    the assigned staff's fatigue."""
    reasons: list[str] = []
    bed = state.beds[patient.bed_id] if patient.bed_id else None
    if bed is None:
        reasons.append("no_bed")
    elif not rules.bed_class_ok(patient, bed.bed_class):
        reasons.append("bed_incompatible")
    speed, risk = 1.0, 1.0
    for slot, label in (("doctor_id", "doctor"), ("nurse_id", "nurse")):
        staff_id = getattr(patient, slot)
        if staff_id is None:
            reasons.append(f"no_{label}")
            continue
        member = state.staff[staff_id]
        if member.status != ON_DUTY:
            reasons.append(f"{label}_unavailable")
        elif not rules.qualified(member, patient):
            reasons.append(f"{label}_not_qualified")
        speed = min(speed, rules.speed_factor(member.fatigue))
        risk = max(risk, rules.risk_factor(member.fatigue))
    held = [state.equipment[e] for e in patient.equipment]
    if rules.needs_monitoring(patient) and not (bed is not None and rules.bed_monitored(bed.bed_class)):
        if not any(e.kind == "portable_monitor" and not e.failed for e in held):
            reasons.append("needs_monitoring")
    if rules.needs_ventilator(patient) and not any(e.kind == "ventilator" and not e.failed for e in held):
        reasons.append("needs_ventilator")
    if (
        patient.imaging
        and patient.imaging_status != "done"
        and patient.work_done >= C.IMAGING_CAP * patient.duration - 1e-9
    ):
        reasons.append("awaiting_imaging")
    return reasons, speed, risk


def step_treatment(state: SimState) -> None:
    for patient in state.patients.values():
        if patient.status != IN_TREATMENT:
            continue
        reasons, speed, risk = stall_reasons(state, patient)
        patient.stalled_reasons = reasons
        patient.care_risk = risk
        if reasons:
            continue
        if patient.first_active_min is None:
            patient.first_active_min = state.minute
            charge_supplies(state, patient)
            state.emit(
                "treatment_started",
                patient_id=patient.patient_id,
                wait_minutes=state.minute - patient.arrival_min,
            )
        patient.active_minutes += 1
        cap = patient.duration
        if patient.imaging and patient.imaging_status != "done":
            cap = C.IMAGING_CAP * patient.duration
        patient.work_done = min(cap, patient.work_done + speed)
        if (
            not patient.complication_applied
            and patient.complication_factor > 1.0
            and patient.work_done >= C.COMPLICATION_AT * patient.duration
        ):
            patient.complication_applied = True
            patient.duration *= patient.complication_factor
            state.emit("treatment_extended", patient_id=patient.patient_id)
        if patient.work_done >= patient.duration - 1e-9:
            patient.status = READY
            patient.ready_min = state.minute
            patient.disposition = "admit" if patient.admit_draw < C.ADMIT_PROB[patient.acuity] else "home"
            state.emit("treatment_complete", patient_id=patient.patient_id, disposition=patient.disposition)


def step_dispositions(state: SimState) -> None:
    for _ in range(state.due_offers()):
        if state.inpatient_queue:
            depart(state, state.patients[state.inpatient_queue[0]], ADMITTED)
        else:
            state.acc["inpatient_offers_unused"] += 1
    for patient in list(state.patients.values()):
        if (
            patient.status == BOARDING
            and patient.transfer_at is not None
            and state.minute >= patient.transfer_at
        ):
            depart(state, patient, TRANSFERRED)


def sample(state: SimState) -> None:
    for patient in state.patients.values():
        if patient.status in (AWAITING_TRIAGE, WAITING):
            state.acc["waiting_patient_minutes"] += 1
        elif patient.status == BOARDING:
            state.acc["boarding_minutes"] += 1
        elif patient.status == READY:
            state.acc["ready_idle_minutes"] += 1
        elif patient.status == IN_TREATMENT and patient.stalled_reasons:
            state.acc["stalled_minutes"] += 1
    if state.diversion:
        state.acc["diversion_minutes"] += 1
