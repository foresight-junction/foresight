"""Beds, equipment and imaging: allocation helpers and per-minute upkeep."""

from __future__ import annotations

from app.edsim import config as C
from app.edsim.entities import IN_TREATMENT, Bed, Patient
from app.edsim.state import SimState


def start_cleaning(state: SimState, bed: Bed) -> None:
    bed.patient_id = None
    bed.clean_until = state.minute + C.BED_CLEAN_MINUTES
    if bed.close_pending_until is not None and bed.close_pending_until > state.minute:
        bed.closed_until = bed.close_pending_until
    bed.close_pending_until = None


def place(state: SimState, patient: Patient, bed: Bed) -> None:
    bed.patient_id = patient.patient_id
    bed.clean_until = None
    patient.bed_id = bed.bed_id
    patient.status = IN_TREATMENT
    if patient.placed_min is None:
        patient.placed_min = state.minute
    if patient.imaging and patient.imaging_status is None:
        patient.imaging_status = "queued"
        patient.imaging_queued_min = state.minute
        state.imaging_queue[patient.imaging].append(patient.patient_id)


def release_equipment(state: SimState, patient: Patient) -> None:
    for equipment_id in patient.equipment:
        state.equipment[equipment_id].patient_id = None
    patient.equipment = []


def leave_imaging(state: SimState, patient: Patient) -> None:
    if patient.imaging is None or patient.imaging_status in (None, "done"):
        return
    queue = state.imaging_queue[patient.imaging]
    if patient.patient_id in queue:
        queue.remove(patient.patient_id)
    for item in state.equipment.values():
        if item.kind == patient.imaging and item.patient_id == patient.patient_id:
            item.patient_id = None
            item.scan_done_at = None
    patient.imaging_status = None


def abort_scan(state: SimState, equipment_id: str) -> None:
    """A scanner failed mid-scan: the patient goes back to the front of the queue."""
    item = state.equipment[equipment_id]
    if item.patient_id is None:
        return
    patient = state.patients[item.patient_id]
    patient.imaging_status = "queued"
    state.imaging_queue[item.kind].insert(0, patient.patient_id)
    item.patient_id = None
    item.scan_done_at = None


def step_beds(state: SimState) -> None:
    for bed in state.beds.values():
        if bed.removed:
            continue
        if bed.closed_until is not None and state.minute >= bed.closed_until:
            bed.closed_until = None
            state.emit("bed_reopened", bed_id=bed.bed_id)
        if bed.clean_until is not None and state.minute >= bed.clean_until:
            bed.clean_until = None
        if bed.temporary and state.minute == bed.available_from:
            state.emit("rental_available", resource_id=bed.bed_id)
        if bed.temporary and bed.rental_until is not None and state.minute >= bed.rental_until:
            if bed.patient_id is None:
                bed.removed = True
                state.emit("rental_returned", resource_id=bed.bed_id)


def step_equipment(state: SimState) -> None:
    for item in state.equipment.values():
        if item.removed:
            continue
        if item.failed and item.repair_at is not None and state.minute >= item.repair_at:
            item.failed = False
            item.repair_at = None
            item.repair_estimate = None
            item.expedited = False
            state.emit("equipment_repaired", equipment_id=item.equipment_id)
            for event in list(state.active_events.values()):
                if (
                    event.kind == "equipment_failure"
                    and event.details.get("equipment_id") == item.equipment_id
                ):
                    del state.active_events[event.event_id]
                    state.emit("event_ended", event_id=event.event_id, event_kind=event.kind)
        if item.temporary and state.minute == item.available_from:
            state.emit("rental_available", resource_id=item.equipment_id)
        if item.temporary and item.rental_until is not None and state.minute >= item.rental_until:
            if item.patient_id is None:
                item.removed = True
                state.emit("rental_returned", resource_id=item.equipment_id)


def step_imaging(state: SimState) -> None:
    for item in state.equipment.values():
        if item.kind not in C.IMAGING or item.removed or item.failed:
            continue
        if (
            item.patient_id is not None
            and item.scan_done_at is not None
            and state.minute >= item.scan_done_at
        ):
            patient = state.patients[item.patient_id]
            patient.imaging_status = "done"
            state.emit("imaging_done", patient_id=patient.patient_id, modality=item.kind)
            item.patient_id = None
            item.scan_done_at = None
        if item.patient_id is None:
            queue = state.imaging_queue[item.kind]
            candidates = [state.patients[pid] for pid in queue if state.patients[pid].placed]
            if not candidates:
                continue
            nxt = min(candidates, key=lambda p: (p.acuity, p.imaging_queued_min or 0, p.patient_id))
            queue.remove(nxt.patient_id)
            nxt.imaging_status = "scanning"
            item.patient_id = nxt.patient_id
            item.scan_done_at = state.minute + nxt.imaging_minutes
            state.emit("imaging_started", patient_id=nxt.patient_id, modality=item.kind)
