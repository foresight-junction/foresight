"""Pure rule functions: requirements, qualifications, compatibility and fatigue effects.

Shared by the engine (to decide whether treatment progresses) and by action validation
(to reject invalid assignments), so both always apply the same rules.
"""

from __future__ import annotations

import math

from app.edsim import config as C
from app.edsim.entities import Patient, Staff


def needs_monitoring(patient: Patient) -> bool:
    if patient.acuity <= 2:
        return True
    return patient.acuity == 3 and C.COMPLAINTS[patient.complaint].monitor_at_3


def needs_ventilator(patient: Patient) -> bool:
    if patient.complaint == "breathing_difficulty":
        return patient.acuity == 1 or (patient.acuity == 2 and patient.vent_draw < 0.3)
    if patient.complaint == "major_trauma":
        return patient.acuity == 1 and patient.vent_draw < 0.4
    return False


def needs_critical_care_nurse(patient: Patient) -> bool:
    return patient.acuity <= 2


def allowed_doctor_roles(patient: Patient) -> tuple[str, ...]:
    return ("attending",) if patient.acuity == 1 else C.DOCTOR_ROLES


def compatible_beds(patient: Patient) -> tuple[str, ...]:
    return C.COMPATIBLE_BEDS[patient.acuity]


def bed_class_ok(patient: Patient, bed_class: str) -> bool:
    effective = "general" if bed_class == "hallway" else bed_class
    return effective in compatible_beds(patient)


def bed_monitored(bed_class: str) -> bool:
    return bed_class in C.MONITORED_BEDS


def requirements(patient: Patient) -> dict[str, object]:
    """What treatment needs right now. Visible to the agent once the patient is triaged."""
    return {
        "bed_classes": list(compatible_beds(patient)),
        "doctor_roles": list(allowed_doctor_roles(patient)),
        "critical_care_nurse": needs_critical_care_nurse(patient),
        "monitoring": needs_monitoring(patient),
        "ventilator": needs_ventilator(patient),
        "imaging": patient.imaging,
        "doctor_units": C.DOCTOR_UNITS[patient.acuity],
        "nurse_units": C.NURSE_UNITS[patient.acuity],
    }


def units_for(staff: Staff, patient: Patient) -> int:
    return (C.DOCTOR_UNITS if staff.is_doctor else C.NURSE_UNITS)[patient.acuity]


def qualified(staff: Staff, patient: Patient) -> bool:
    if staff.is_doctor:
        return staff.role in allowed_doctor_roles(patient)
    return not needs_critical_care_nurse(patient) or "critical_care" in staff.skills


def speed_factor(fatigue: float) -> float:
    """Treatment speed: 1.0 up to fatigue 60, falling linearly to 0.6 at 100."""
    if fatigue <= 60:
        return 1.0
    return 1.0 - 0.4 * min(1.0, (fatigue - 60) / 40)


def risk_factor(fatigue: float) -> float:
    """Deterioration risk multiplier: 1.0 up to fatigue 70, rising linearly to 2.0 at 100."""
    if fatigue <= 70:
        return 1.0
    return 1.0 + min(1.0, (fatigue - 70) / 30)


def patience_minutes(patient: Patient) -> float | None:
    median = C.PATIENCE_MEDIAN.get(patient.acuity)
    if median is None:
        return None
    return median * math.exp(C.PATIENCE_SIGMA * patient.patience_z)


def hazard_rate_untreated(acuity: int, untreated_min: float) -> float:
    """Weibull hazard (shape 1.5): the longer a patient goes untreated, the faster risk grows."""
    tau = C.HAZARD_TAU[acuity]
    beta = C.HAZARD_SHAPE
    return beta / tau * (max(untreated_min, 1.0) / tau) ** (beta - 1)


def hazard_rate_treated(acuity: int) -> float:
    return C.TREATED_HAZARD_FACTOR / C.HAZARD_TAU[acuity]
