"""Mutable simulation entities. Fields marked hidden must never reach `views.py` output."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Patient statuses
AWAITING_TRIAGE = "awaiting_triage"
WAITING = "waiting"
IN_TREATMENT = "in_treatment"
READY = "ready"
BOARDING = "boarding"
DISCHARGED = "discharged"
ADMITTED = "admitted"
TRANSFERRED = "transferred"
LWBS = "lwbs"
CRITICAL_EVENT = "critical_event"
DIVERTED = "diverted"
ACTIVE_STATUSES = (AWAITING_TRIAGE, WAITING, IN_TREATMENT, READY, BOARDING)
TERMINAL_STATUSES = (DISCHARGED, ADMITTED, TRANSFERRED, LWBS, CRITICAL_EVENT, DIVERTED)

# Staff statuses
OFF_DUTY = "off_duty"
ON_DUTY = "on_duty"
ON_BREAK = "on_break"
SICK = "sick"

ERROR_MESSAGES: dict[str, str] = {
    "INVALID_ARGUMENT": "An argument is missing or malformed.",
    "NOT_FOUND": "No such patient, staff member, bed or equipment.",
    "EPISODE_FINISHED": "The 72-hour simulation has ended.",
    "PATIENT_NOT_ACTIVE": "The patient is no longer in the department.",
    "NOT_TRIAGED": "The patient has not been triaged yet.",
    "WRONG_STATUS": "The patient is not in a status that allows this action.",
    "NOT_READY": "Treatment is not complete, so the patient cannot be discharged.",
    "BED_UNAVAILABLE": "The bed is occupied, being cleaned, closed or not yet available.",
    "BED_INCOMPATIBLE": "The bed class does not meet the patient's acuity requirements.",
    "STAFF_UNAVAILABLE": "The staff member is not on duty, is on a break, or is sick.",
    "STAFF_NOT_QUALIFIED": "The staff member's role or skills do not meet the patient's requirements.",
    "STAFF_AT_CAPACITY": "The assignment would exceed the staff member's workload capacity.",
    "STAFF_BUSY": "The staff member still has patients assigned.",
    "WRONG_ZONE": "The staff member is working in triage and cannot take floor patients.",
    "EQUIPMENT_UNAVAILABLE": "The equipment is in use, out of service or not yet available.",
    "WRONG_EQUIPMENT": "That equipment type cannot be allocated to a patient.",
    "NOT_FAILED": "The equipment is not out of service.",
    "ALREADY_EXPEDITED": "An expedited repair is already under way.",
    "LIMIT_REACHED": "The daily limit for this request has been reached.",
    "SHIFT_LIMIT": "The extension would exceed the maximum continuous duty time.",
}


class EDError(Exception):
    def __init__(self, code: str, detail: str | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.detail = detail

    def payload(self) -> dict[str, Any]:
        message = ERROR_MESSAGES.get(self.code, self.code)
        if self.detail:
            message = f"{message} ({self.detail})"
        return {"error": {"code": self.code, "message": message}}


@dataclass
class Patient:
    patient_id: str
    age: int
    arrival_min: int
    mode: str  # walk_in | ambulance
    complaint: str
    incident_id: str | None
    acuity: int  # true current acuity; visible only once triaged
    initial_acuity: int
    # hidden draws
    duration: float  # treatment work minutes at full speed
    complication_factor: float  # 1.0 when no complication
    imaging: str | None  # ct | xray | None (visible after triage)
    imaging_minutes: int
    triage_minutes: int
    thresholds: list[float]
    patience_z: float
    admit_draw: float
    vent_draw: float
    # runtime
    status: str = AWAITING_TRIAGE
    triaged: bool = False
    triage_min: int | None = None
    bed_id: str | None = None
    doctor_id: str | None = None
    nurse_id: str | None = None
    equipment: list[str] = field(default_factory=list)
    work_done: float = 0.0
    complication_applied: bool = False
    imaging_status: str | None = None  # queued | scanning | done
    imaging_queued_min: int | None = None
    hazard: float = 0.0
    untreated_min: float = 0.0
    threshold_index: int = 0
    deteriorations: int = 0
    first_active_min: int | None = None
    placed_min: int | None = None
    ready_min: int | None = None
    departed_min: int | None = None
    disposition: str | None = None  # home | admit, revealed at completion
    boarding_since: int | None = None
    transfer_at: int | None = None
    supplies_charged: bool = False
    active_minutes: int = 0
    stalled_reasons: list[str] = field(default_factory=list)
    care_risk: float = 1.0  # hidden: fatigue risk multiplier of the current care team

    @property
    def terminal(self) -> bool:
        return self.status in TERMINAL_STATUSES

    @property
    def placed(self) -> bool:
        return self.bed_id is not None


@dataclass
class Shift:
    start: int
    end: int
    scheduled_end: int  # end before any extension; minutes past it are overtime


@dataclass
class Staff:
    staff_id: str
    role: str  # attending | resident | nurse
    skills: frozenset[str]
    team: str  # day | night | agency
    shifts: list[Shift]
    fatigue: float
    zone: str = "floor"  # floor | triage (nurses only)
    status: str = OFF_DUTY
    patients: list[str] = field(default_factory=list)
    break_until: int | None = None
    sick_from: int | None = None
    sick_until: int | None = None
    triaging: str | None = None
    triage_done_at: int | None = None

    def shift_at(self, minute: int) -> Shift | None:
        for shift in self.shifts:
            if shift.start <= minute < shift.end:
                return shift
        return None

    def is_sick(self, minute: int) -> bool:
        return (
            self.sick_from is not None
            and self.sick_until is not None
            and self.sick_from <= minute < self.sick_until
        )

    @property
    def is_doctor(self) -> bool:
        return self.role in ("attending", "resident")


@dataclass
class Bed:
    bed_id: str
    bed_class: str
    temporary: bool = False
    available_from: int = 0
    rental_until: int | None = None
    patient_id: str | None = None
    clean_until: int | None = None
    closed_until: int | None = None
    close_pending_until: int | None = None
    removed: bool = False

    def state(self, minute: int) -> str:
        if self.removed:
            return "removed"
        if minute < self.available_from:
            return "pending"
        if self.patient_id is not None:
            return "occupied"
        if self.closed_until is not None and minute < self.closed_until:
            return "closed"
        if self.clean_until is not None and minute < self.clean_until:
            return "cleaning"
        return "free"


@dataclass
class Equipment:
    equipment_id: str
    kind: str
    temporary: bool = False
    available_from: int = 0
    rental_until: int | None = None
    patient_id: str | None = None  # holder (held kinds) or patient being scanned (imaging)
    scan_done_at: int | None = None
    failed: bool = False
    repair_at: int | None = None  # hidden true repair time
    repair_estimate: int | None = None  # visible estimate
    expedited: bool = False
    removed: bool = False

    def state(self, minute: int) -> str:
        if self.removed:
            return "removed"
        if minute < self.available_from:
            return "pending"
        if self.failed:
            return "out_of_service"
        if self.patient_id is not None:
            return "in_use"
        return "available"


@dataclass
class ScheduledEvent:
    event_id: str
    kind: str
    minute: int
    params: dict[str, Any]


@dataclass
class ActiveEvent:
    event_id: str
    kind: str
    started_min: int
    description: str
    details: dict[str, Any]
    ends_min: int | None = None  # hidden true end; views show only announced estimates
