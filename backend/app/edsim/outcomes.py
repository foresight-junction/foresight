"""Synthetic outcomes: deterioration risk, critical events and leaving without being seen.

Each patient accumulates hazard; when it passes the patient's next pre-drawn Exp(1)
threshold the patient deteriorates. Thresholds are drawn at scenario generation, so the
agent's decisions change exposure to risk, never the random numbers themselves.
"""

from __future__ import annotations

from app.edsim import config as C
from app.edsim import rules
from app.edsim.entities import AWAITING_TRIAGE, CRITICAL_EVENT, IN_TREATMENT, LWBS, WAITING, Patient
from app.edsim.flow import depart
from app.edsim.state import SimState

AT_RISK = (AWAITING_TRIAGE, WAITING, IN_TREATMENT)


def _deteriorate(state: SimState, patient: Patient) -> None:
    patient.deteriorations += 1
    patient.hazard = 0.0
    patient.threshold_index = min(patient.threshold_index + 1, len(patient.thresholds) - 1)
    if patient.acuity == 1:
        state.acc["critical_events"] += 1
        state.emit("critical_event", patient_id=patient.patient_id)
        depart(state, patient, CRITICAL_EVENT)
        return
    patient.acuity -= 1
    patient.untreated_min /= 2
    remaining = max(0.0, patient.duration - patient.work_done)
    patient.duration += 0.3 * remaining
    state.acc["deteriorations"] += 1
    state.emit(
        "patient_deteriorated",
        patient_id=patient.patient_id,
        acuity=patient.acuity if patient.triaged else None,
    )


def step_outcomes(state: SimState) -> None:
    for patient in list(state.patients.values()):
        if patient.status not in AT_RISK:
            continue
        if patient.status == IN_TREATMENT and not patient.stalled_reasons:
            rate = rules.hazard_rate_treated(patient.acuity) * patient.care_risk
        else:
            patient.untreated_min += 1
            rate = rules.hazard_rate_untreated(patient.acuity, patient.untreated_min)
            if patient.status == IN_TREATMENT:
                rate *= C.STALLED_HAZARD_FACTOR
        patient.hazard += rate
        if patient.hazard >= patient.thresholds[patient.threshold_index]:
            _deteriorate(state, patient)

    for patient in list(state.patients.values()):
        # Anyone not yet actually treated may give up, including patients parked in a bed
        # with no staff, so parking patients is not a way to avoid walk-outs.
        if patient.status not in AT_RISK or patient.first_active_min is not None:
            continue
        patience = rules.patience_minutes(patient)
        if patience is not None and state.minute - patient.arrival_min >= patience:
            state.acc["lwbs"] += 1
            depart(state, patient, LWBS)
