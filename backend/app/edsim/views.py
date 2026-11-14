"""Agent-visible projections of the state.

This module is the firewall: it builds every observation from an explicit allow-list of
fields. It never outputs true durations, hazard, thresholds, patience, admission draws,
true repair times, future arrivals or events, the seed, or reward information.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from app.edsim import config as C
from app.edsim import rules, staffing
from app.edsim.budget import hourly_burn
from app.edsim.entities import (
    ACTIVE_STATUSES,
    AWAITING_TRIAGE,
    BOARDING,
    DIVERTED,
    IN_TREATMENT,
    OFF_DUTY,
    ON_BREAK,
    ON_DUTY,
    READY,
    WAITING,
    Patient,
    Staff,
)
from app.edsim.state import SimState

INCOMING_WINDOW = 240  # off-duty staff starting within this many minutes are listed


def clock(state: SimState) -> dict[str, Any]:
    return {
        "minute": state.minute,
        "time": C.clock_label(state.minute),
        "remaining_minutes": max(0, state.horizon - state.minute),
        "finished": state.finished,
    }


def _label(minute: int | None) -> str | None:
    return C.clock_label(minute) if minute is not None else None


def _wait(state: SimState, patient: Patient) -> int | None:
    if patient.first_active_min is not None or patient.terminal:
        return None
    return state.minute - patient.arrival_min


def patient_row(state: SimState, patient: Patient) -> dict[str, Any]:
    row: dict[str, Any] = {
        "patient_id": patient.patient_id,
        "status": patient.status,
        "acuity": patient.acuity if patient.triaged else None,
        "complaint": patient.complaint,
        "mode": patient.mode,
        "arrived": C.clock_label(patient.arrival_min),
        "waiting_minutes": _wait(state, patient),
    }
    if patient.bed_id or patient.doctor_id or patient.nurse_id:
        row.update(bed_id=patient.bed_id, doctor_id=patient.doctor_id, nurse_id=patient.nurse_id)
    if patient.equipment:
        row["equipment"] = list(patient.equipment)
    if patient.status == IN_TREATMENT:
        row["stalled"] = list(patient.stalled_reasons)
        row["active_minutes"] = patient.active_minutes
        row["expected_minutes"] = C.EXPECTED_DURATION[patient.acuity]
    if patient.status in (READY, BOARDING):
        row["disposition"] = patient.disposition
    if patient.incident_id:
        row["incident_id"] = patient.incident_id
    return row


def patient_detail(state: SimState, patient: Patient) -> dict[str, Any]:
    detail = patient_row(state, patient)
    started = patient.first_active_min
    detail.update(
        age=patient.age,
        arrival_minute=patient.arrival_min,
        triaged_at=_label(patient.triage_min),
        treatment_started_at=_label(started),
        door_to_treatment_minutes=started - patient.arrival_min if started is not None else None,
        deteriorations=patient.deteriorations,
        treatment_extended=patient.complication_applied,
    )
    if patient.triaged:
        detail["requirements"] = rules.requirements(patient)
        detail["target_wait_minutes"] = C.TARGET_WAIT[patient.acuity]
        detail["imaging_status"] = patient.imaging_status
    if patient.status == BOARDING:
        detail["boarding_since"] = _label(patient.boarding_since)
        detail["transfer_pending"] = patient.transfer_at is not None
    if patient.departed_min is not None:
        detail["departed_at"] = _label(patient.departed_min)
    return detail


def list_patients(state: SimState, status: str | None = None) -> dict[str, Any]:
    rows = [
        patient_row(state, p)
        for p in state.patients.values()
        if p.status in ACTIVE_STATUSES and (status is None or p.status == status)
    ]
    priority = {READY: 0, WAITING: 1, AWAITING_TRIAGE: 2, IN_TREATMENT: 3, BOARDING: 4}
    rows.sort(key=lambda r: (priority[r["status"]], r["acuity"] or 9, -(r["waiting_minutes"] or 0)))
    return {"clock": clock(state), "count": len(rows), "patients": rows}


def staff_row(state: SimState, staff: Staff) -> dict[str, Any]:
    shift = staff.shift_at(state.minute)
    upcoming = [s for s in staff.shifts if s.start > state.minute]
    row: dict[str, Any] = {
        "staff_id": staff.staff_id,
        "role": staff.role,
        "skills": sorted(staff.skills),
        "team": staff.team,
        "status": staff.status,
        "fatigue": round(staff.fatigue),
    }
    if staff.role == "nurse":
        row["zone"] = staff.zone
    if staff.status in (ON_DUTY, ON_BREAK):
        row.update(
            load_units=staffing.load_units(state, staff),
            capacity=C.CAPACITY[staff.role],
            patients=list(staff.patients),
            shift_ends=_label(shift.end) if shift else None,
            in_overtime=bool(shift and state.minute >= shift.scheduled_end),
        )
        if staff.triaging:
            row["triaging"] = staff.triaging
        if staff.break_until is not None:
            row["back_from_break"] = _label(staff.break_until)
    if upcoming:
        row["next_shift_starts"] = _label(upcoming[0].start)
    if staff.sick_from is not None and staff.sick_until is not None and state.minute < staff.sick_until:
        row["absent"] = {"from": _label(staff.sick_from), "until": _label(staff.sick_until)}
    return row


def staff_status(state: SimState, include_off_duty: bool = False) -> dict[str, Any]:
    def listed(staff: Staff) -> bool:
        if include_off_duty or staff.status != OFF_DUTY:
            return True
        return any(0 < sh.start - state.minute <= INCOMING_WINDOW for sh in staff.shifts)

    rows = [staff_row(state, s) for s in state.staff.values() if listed(s)]
    on_duty = Counter(s.role for s in state.staff.values() if s.status == ON_DUTY)
    return {"clock": clock(state), "on_duty": dict(on_duty), "staff": rows}


def resource_status(state: SimState) -> dict[str, Any]:
    beds = []
    for bed in state.beds.values():
        if bed.removed:
            continue
        row: dict[str, Any] = {"bed_id": bed.bed_id, "class": bed.bed_class, "state": bed.state(state.minute)}
        if bed.patient_id:
            row["patient_id"] = bed.patient_id
        if bed.closed_until is not None and state.minute < bed.closed_until:
            row["reopens_at"] = _label(bed.closed_until)
        if bed.close_pending_until is not None:
            row["closes_when_vacated"] = True
        if bed.temporary:
            row["available_at"] = _label(bed.available_from)
            row["rental_until"] = _label(bed.rental_until)
        beds.append(row)
    equipment = []
    for item in state.equipment.values():
        if item.removed:
            continue
        row = {"equipment_id": item.equipment_id, "kind": item.kind, "state": item.state(state.minute)}
        if item.patient_id:
            row["patient_id"] = item.patient_id
        if item.failed and item.repair_estimate is not None:
            row["estimated_back_in_service"] = _label(item.repair_estimate)
            row["expedited"] = item.expedited
        if item.temporary:
            row["available_at"] = _label(item.available_from)
            row["rental_until"] = _label(item.rental_until)
        equipment.append(row)
    return {
        "clock": clock(state),
        "beds": beds,
        "equipment": equipment,
        "imaging_queues": {kind: list(queue) for kind, queue in state.imaging_queue.items()},
        "inpatient_queue": list(state.inpatient_queue),
        "diversion": state.diversion,
    }


def budget_status(state: SimState) -> dict[str, Any]:
    return {
        "clock": clock(state),
        "budget": round(state.budget, 2),
        "spent": round(state.spent, 2),
        "remaining": round(state.budget - state.spent, 2),
        "by_category": {k: round(v, 2) for k, v in state.ledger.items()},
        "current_burn_per_hour": round(hourly_burn(state), 2),
        "supply_cost_multiplier": state.supply_multiplier,
        "agency_requests_today": state.agency_requests[state.day_index],
        "agency_daily_limit": state.config.agency_daily_limit,
        "rental_requests_today": state.rental_requests[state.day_index],
        "rental_daily_limit": state.config.rental_daily_limit,
        "prices": {
            "wage_per_hour": C.WAGE_PER_HOUR,
            "overtime_multiplier": C.OVERTIME_MULTIPLIER,
            "agency_multiplier": C.AGENCY_MULTIPLIER,
            "agency_callout_fee": C.AGENCY_CALLOUT_FEE,
            "supplies_by_acuity": C.SUPPLY_COST,
            "rental_per_hour": C.RENTAL_PER_HOUR,
            "expedited_repair": C.REPAIR_FEE,
            "transfer": C.TRANSFER_FEE,
        },
    }


def active_events(state: SimState) -> dict[str, Any]:
    return {
        "clock": clock(state),
        "events": [
            {
                "event_id": e.event_id,
                "kind": e.kind,
                "started": C.clock_label(e.started_min),
                "description": e.description,
                "details": dict(e.details),
            }
            for e in state.active_events.values()
        ],
    }


def department_metrics(state: SimState) -> dict[str, Any]:
    """Operational figures a manager can see on a dashboard. Not the evaluator's reward."""
    arrived = [p for p in state.patients.values() if p.status != DIVERTED]
    outcomes = Counter(p.status for p in arrived if p.terminal)
    door_to_treatment: dict[str, float] = {}
    within_target: dict[str, float] = {}
    for acuity in C.ACUITY_LEVELS:
        waits = [
            p.first_active_min - p.arrival_min
            for p in arrived
            if p.first_active_min is not None and p.initial_acuity == acuity
        ]
        if waits:
            door_to_treatment[str(acuity)] = round(sum(waits) / len(waits), 1)
            within = sum(1 for w in waits if w <= C.TARGET_WAIT[acuity])
            within_target[str(acuity)] = round(within / len(waits), 3)
    on_duty = [s for s in state.staff.values() if s.status in (ON_DUTY, ON_BREAK)]
    in_use = sum(1 for b in state.beds.values() if not b.removed and b.patient_id is not None)
    usable = sum(1 for b in state.beds.values() if not b.removed and b.state(state.minute) != "pending")
    return {
        "clock": clock(state),
        "arrived": len(arrived),
        "ambulances_diverted": state.acc["diverted"],
        "in_department": sum(1 for p in arrived if not p.terminal),
        "outcomes": dict(outcomes),
        "deteriorations": state.acc["deteriorations"] + state.acc["critical_events"],
        "mean_door_to_treatment_by_acuity": door_to_treatment,
        "share_within_target_by_acuity": within_target,
        "bed_occupancy": round(in_use / usable, 3) if usable else 0.0,
        "mean_fatigue_on_duty": round(sum(s.fatigue for s in on_duty) / len(on_duty), 1) if on_duty else 0.0,
        "rejected_actions": sum(state.invalid_actions.values()),
    }


def department_status(state: SimState) -> dict[str, Any]:
    active = [p for p in state.patients.values() if p.status in ACTIVE_STATUSES]
    waiting = [p for p in active if p.status == WAITING]
    beds: dict[str, Counter[str]] = {}
    for bed in state.beds.values():
        if not bed.removed:
            beds.setdefault(bed.bed_class, Counter())[bed.state(state.minute)] += 1
    on_duty = [s for s in state.staff.values() if s.status == ON_DUTY]
    alerts: list[str] = []
    ready = [p.patient_id for p in active if p.status == READY]
    if ready:
        alerts.append(f"{len(ready)} patient(s) ready for discharge: {', '.join(ready[:8])}")
    urgent = [p.patient_id for p in waiting if p.acuity <= 2]
    if urgent:
        alerts.append(f"acuity 1-2 patients waiting for treatment: {', '.join(urgent)}")
    stalled = [p for p in active if p.status == IN_TREATMENT and p.stalled_reasons]
    for patient in stalled[:8]:
        alerts.append(f"{patient.patient_id} stalled: {', '.join(patient.stalled_reasons)}")
    if not any(s.role == "nurse" and s.zone == "triage" for s in on_duty):
        alerts.append("no nurse is working in triage")
    for item in state.equipment.values():
        if item.failed and not item.removed:
            alerts.append(f"{item.equipment_id} out of service")
    longest = max(
        (p for p in active if p.first_active_min is None),
        key=lambda p: state.minute - p.arrival_min,
        default=None,
    )
    return {
        "clock": clock(state),
        "patients": {
            "awaiting_triage": sum(1 for p in active if p.status == AWAITING_TRIAGE),
            "waiting_by_acuity": {str(a): sum(1 for p in waiting if p.acuity == a) for a in C.ACUITY_LEVELS},
            "in_treatment": sum(1 for p in active if p.status == IN_TREATMENT),
            "stalled": len(stalled),
            "ready": len(ready),
            "boarding": sum(1 for p in active if p.status == BOARDING),
        },
        "longest_wait": (
            {
                "patient_id": longest.patient_id,
                "minutes": state.minute - longest.arrival_min,
                "acuity": longest.acuity if longest.triaged else None,
            }
            if longest
            else None
        ),
        "beds": {cls: dict(counts) for cls, counts in beds.items()},
        "staff_on_duty": dict(Counter(s.role for s in on_duty)),
        "staff_on_break": sum(1 for s in state.staff.values() if s.status == ON_BREAK),
        "triage_nurses": [s.staff_id for s in on_duty if s.role == "nurse" and s.zone == "triage"],
        "budget": {
            "budget": round(state.budget, 2),
            "spent": round(state.spent, 2),
            "remaining": round(state.budget - state.spent, 2),
        },
        "diversion": state.diversion,
        "active_events": [{"event_id": e.event_id, "kind": e.kind} for e in state.active_events.values()],
        "alerts": alerts,
    }


def recent_log(state: SimState, since_minute: int | None = None, limit: int = 100) -> dict[str, Any]:
    entries = [
        {k: v for k, v in e.items() if k != "visibility"}
        for e in state.log
        if e["visibility"] == "agent" and (since_minute is None or e["minute"] >= since_minute)
    ]
    return {"clock": clock(state), "entries": entries[-limit:]}
