"""Helpers for engine unit tests: controlled patients and injected events."""

from __future__ import annotations

from typing import Any

from app.edsim import Simulation
from app.edsim.entities import AWAITING_TRIAGE, WAITING, Patient, ScheduledEvent

NO_DETERIORATION = [1e9] * 8


def quiet_sim(seed: int = 7, hours: int = 24) -> Simulation:
    """A short run with no scheduled events and no natural arrivals, for controlled tests."""
    sim = Simulation("standard", seed, horizon_hours=hours)
    sim.state.future_patients = []
    sim.state.future_events = []
    sim.state.active_events.clear()
    return sim


def add_patient(
    sim: Simulation,
    acuity: int = 3,
    complaint: str = "abdominal_pain",
    *,
    triaged: bool = True,
    duration: float = 100.0,
    imaging: str | None = None,
    thresholds: list[float] | None = None,
    patience_z: float = 10.0,
    admit_draw: float = 0.99,
    vent_draw: float = 0.99,
    mode: str = "walk_in",
    arrival: int | None = None,
) -> Patient:
    state = sim.state
    pid = f"PT-T{len(state.patients) + 1:03d}"
    patient = Patient(
        patient_id=pid,
        age=40,
        arrival_min=state.minute if arrival is None else arrival,
        mode=mode,
        complaint=complaint,
        incident_id=None,
        acuity=acuity,
        initial_acuity=acuity,
        duration=duration,
        complication_factor=1.0,
        imaging=imaging,
        imaging_minutes=10 if imaging else 0,
        triage_minutes=5,
        thresholds=list(thresholds or NO_DETERIORATION),
        patience_z=patience_z,
        admit_draw=admit_draw,
        vent_draw=vent_draw,
    )
    if triaged:
        patient.triaged = True
        patient.triage_min = state.minute
        patient.status = WAITING
    else:
        patient.status = AWAITING_TRIAGE
    state.patients[pid] = patient
    return patient


def inject_event(sim: Simulation, kind: str, minute: int, **params: Any) -> None:
    state = sim.state
    event = ScheduledEvent(f"EV-T{len(state.future_events) + 1}", kind, minute, params)
    pending = state.future_events[state._next_event :] + [event]
    pending.sort(key=lambda e: (e.minute, e.event_id))
    state.future_events = state.future_events[: state._next_event] + pending


BED_ORDER = {"fast_track": 0, "general": 1, "hallway": 1, "monitored": 2, "resus": 3}


def _pick_staff(staff: list[dict], ok: Any, units: int) -> str | None:
    fits = [
        s for s in staff if s["status"] == "on_duty" and ok(s) and s["load_units"] + units <= s["capacity"]
    ]
    fits.sort(key=lambda s: (s["load_units"] / s["capacity"], s["fatigue"], s["staff_id"]))
    return fits[0]["staff_id"] if fits else None


def _pick_doctor(staff: list[dict], req: dict) -> str | None:
    return _pick_staff(staff, lambda s: s["role"] in req["doctor_roles"], req["doctor_units"])


def _pick_nurse(staff: list[dict], req: dict) -> str | None:
    def ok(s: dict) -> bool:
        if s["role"] != "nurse" or s.get("zone") != "floor":
            return False
        return not req["critical_care_nurse"] or "critical_care" in s["skills"]

    return _pick_staff(staff, ok, req["nurse_units"])


def simple_policy(sim: Simulation, step: int = 10, until: int | None = None) -> None:
    """A plain greedy manager that only uses the agent-facing API: discharge ready patients,
    start the most urgent waiting patients where a bed and staff fit, re-staff stalled ones.
    It is a test fixture for dynamics, not the reference strategy."""
    end = sim.state.horizon if until is None else until
    while not sim.finished and sim.state.minute < end:
        patients = sim.list_patients()["patients"]
        ready = [p["patient_id"] for p in patients if p["status"] == "ready"]
        for i in range(0, len(ready), 20):
            sim.act("discharge_patient", patient_ids=ready[i : i + 20])
        for row in [p for p in patients if p["status"] == "waiting"]:
            req = sim.patient(row["patient_id"])["requirements"]
            resources = sim.resource_status()
            beds = [
                b
                for b in resources["beds"]
                if b["state"] == "free"
                and ("general" if b["class"] == "hallway" else b["class"]) in req["bed_classes"]
            ]
            sign = -1 if req["monitoring"] else 1
            beds.sort(key=lambda b, sign=sign: sign * BED_ORDER[b["class"]])
            if not beds:
                continue
            staff = sim.staff_status()["staff"]
            doctor = _pick_doctor(staff, req)
            nurse = _pick_nurse(staff, req)
            free = [e for e in resources["equipment"] if e["state"] == "available"]
            equipment = []
            if req["ventilator"]:
                vents = [e["equipment_id"] for e in free if e["kind"] == "ventilator"]
                if not vents:
                    continue
                equipment.append(vents[0])
            if req["monitoring"] and beds[0]["class"] not in ("monitored", "resus"):
                monitors = [e["equipment_id"] for e in free if e["kind"] == "portable_monitor"]
                if not monitors:
                    continue
                equipment.append(monitors[0])
            if doctor and nurse:
                sim.act(
                    "start_treatment",
                    patient_id=row["patient_id"],
                    bed_id=beds[0]["bed_id"],
                    doctor_id=doctor,
                    nurse_id=nurse,
                    equipment_ids=equipment or None,
                )
        for row in sim.list_patients("in_treatment")["patients"]:
            req = sim.patient(row["patient_id"])["requirements"]
            for reason in row["stalled"]:
                staff = sim.staff_status()["staff"]
                if reason in ("no_doctor", "doctor_unavailable", "doctor_not_qualified"):
                    pick = _pick_doctor(staff, req)
                elif reason in ("no_nurse", "nurse_unavailable", "nurse_not_qualified"):
                    pick = _pick_nurse(staff, req)
                else:
                    continue
                if pick:
                    sim.act("assign_staff", staff_id=pick, patient_ids=[row["patient_id"]])
        sim.advance_time(min(step, end - sim.state.minute))


def advance_to(sim: Simulation, minute: int) -> None:
    while sim.state.minute < minute:
        sim.advance_time(min(120, minute - sim.state.minute))


def start(sim: Simulation, patient: Patient, bed: str, doctor: str, nurse: str, **kw: Any) -> dict:
    return sim.act(
        "start_treatment", patient_id=patient.patient_id, bed_id=bed, doctor_id=doctor, nurse_id=nurse, **kw
    )
