"""Difficulty configs and the constant tables the engine is built on.

All clinical-sounding labels here are abstract simulation variables for an operational
benchmark; none of them encode real diagnosis or treatment.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

MINUTES_PER_HOUR = 60
HORIZON_MINUTES = 72 * MINUTES_PER_HOUR
CLOCK_START_HOUR = 7  # minute 0 is 07:00 on day 1
MAX_ADVANCE_MINUTES = 120

ACUITY_LEVELS = (1, 2, 3, 4, 5)

# Door-to-treatment targets (minutes) per acuity, used by metrics and the evaluator.
TARGET_WAIT = {1: 10, 2: 20, 3: 60, 4: 120, 5: 240}
# Nominal treatment work per acuity at full staff speed; true durations are drawn around it.
EXPECTED_DURATION = {1: 200, 2: 160, 3: 120, 4: 70, 5: 45}
# Deterioration time scale per acuity (minutes untreated until cumulative hazard reaches 1).
HAZARD_TAU = {1: 45, 2: 90, 3: 300, 4: 900, 5: 2000}
HAZARD_SHAPE = 1.5
TREATED_HAZARD_FACTOR = 0.01  # active treatment: constant rate of 0.01 / tau
STALLED_HAZARD_FACTOR = 0.5  # placed but stalled: half the untreated rate
# Median patience (minutes) before a not-yet-treated patient leaves without being seen.
PATIENCE_MEDIAN = {3: 240, 4: 180, 5: 150}
PATIENCE_SIGMA = 0.5

DOCTOR_UNITS = {1: 5, 2: 3, 3: 2, 4: 1, 5: 1}
NURSE_UNITS = {1: 12, 2: 6, 3: 4, 4: 3, 5: 3}
CAPACITY = {"attending": 10, "resident": 8, "nurse": 12}
DOCTOR_ROLES = ("attending", "resident")
ROLES = ("attending", "resident", "nurse")

BED_CLASSES = ("resus", "monitored", "general", "fast_track")
BED_PREFIX = {"resus": "RESUS", "monitored": "MON", "general": "GEN", "fast_track": "FT", "hallway": "HALL"}
COMPATIBLE_BEDS = {
    1: ("resus",),
    2: ("resus", "monitored"),
    3: ("resus", "monitored", "general"),
    4: ("resus", "monitored", "general", "fast_track"),
    5: ("resus", "monitored", "general", "fast_track"),
}
MONITORED_BEDS = ("resus", "monitored")
BED_CLEAN_MINUTES = 15

HELD_EQUIPMENT = ("ventilator", "portable_monitor")
IMAGING = ("ct", "xray")
EQUIPMENT_PREFIX = {"ventilator": "VENT", "portable_monitor": "PMON", "ct": "CT", "xray": "XRAY"}
IMAGING_MINUTES = {"ct": (15, 25), "xray": (8, 12)}
IMAGING_CAP = 0.5  # treatment cannot pass 50% until a required scan is done
COMPLICATION_AT = 0.6

FATIGUE_BASE = 0.095
FATIGUE_NIGHT = 1.2
FATIGUE_OVERTIME = 1.5
FATIGUE_BREAK_RECOVERY = 0.5
FATIGUE_REST_RECOVERY = 0.15
FATIGUE_HIGH = 80.0
MAX_CONTINUOUS_DUTY = 16 * MINUTES_PER_HOUR
BREAK_RANGE = (15, 60)
EXTEND_RANGE = (1, 4)

WAGE_PER_HOUR = {"attending": 140.0, "resident": 75.0, "nurse": 50.0}
OVERTIME_MULTIPLIER = 1.5
AGENCY_MULTIPLIER = 2.2
AGENCY_CALLOUT_FEE = 300.0
AGENCY_HOURS = (4, 12)
LEAD_TIME_MINUTES = 60
SUPPLY_COST = {1: 900.0, 2: 500.0, 3: 250.0, 4: 80.0, 5: 40.0}
RENTAL_PER_HOUR = {"hallway_bed": 30.0, "portable_monitor": 25.0, "ventilator": 90.0}
RENTAL_HOURS = (4, 24)
REPAIR_FEE = 2500.0
REPAIR_SPEEDUP = 0.3  # expedited repair keeps 30% of the remaining downtime
TRANSFER_FEE = 1800.0
TRANSFER_MINUTES = 60

AMBULANCE_PROB = {1: 0.9, 2: 0.6, 3: 0.3, 4: 0.1, 5: 0.03}
ADMIT_PROB = {1: 0.85, 2: 0.6, 3: 0.3, 4: 0.05, 5: 0.0}
COMPLICATION_PROB = 0.08
COMPLICATION_FACTOR = (1.6, 2.2)
DURATION_SIGMA = 0.3
TRIAGE_MINUTES = (4, 8)
THRESHOLDS_PER_PATIENT = 8

# Relative arrival rate for each hour of the day (index 0 = 00:00).
DIURNAL = (
    0.55, 0.45, 0.40, 0.35, 0.35, 0.40, 0.50, 0.70, 0.90, 1.05, 1.20, 1.30,
    1.35, 1.35, 1.30, 1.30, 1.30, 1.30, 1.30, 1.25, 1.15, 1.00, 0.85, 0.70,
)  # fmt: skip


@dataclass(frozen=True)
class Complaint:
    weight: float
    acuity_weights: dict[int, float]
    ct: float = 0.0
    xray: float = 0.0
    monitor_at_3: bool = False


COMPLAINTS: dict[str, Complaint] = {
    "chest_pain": Complaint(12, {1: 0.05, 2: 0.35, 3: 0.45, 4: 0.15}, ct=0.1, xray=0.3, monitor_at_3=True),
    "breathing_difficulty": Complaint(10, {1: 0.08, 2: 0.30, 3: 0.42, 4: 0.20}, xray=0.6, monitor_at_3=True),
    "major_trauma": Complaint(6, {1: 0.20, 2: 0.40, 3: 0.30, 4: 0.10}, ct=0.8),
    "neuro_symptoms": Complaint(6, {1: 0.05, 2: 0.40, 3: 0.40, 4: 0.15}, ct=0.9, monitor_at_3=True),
    "abdominal_pain": Complaint(16, {2: 0.10, 3: 0.55, 4: 0.30, 5: 0.05}, ct=0.3),
    "minor_injury": Complaint(26, {3: 0.10, 4: 0.55, 5: 0.35}, xray=0.5),
    "fever_infection": Complaint(16, {2: 0.10, 3: 0.45, 4: 0.35, 5: 0.10}, xray=0.2),
    "mental_health": Complaint(8, {2: 0.10, 3: 0.40, 4: 0.40, 5: 0.10}),
}
INCIDENT_COMPLAINTS = {"major_trauma": 0.7, "breathing_difficulty": 0.15, "minor_injury": 0.15}
INCIDENT_ACUITY = {1: 0.25, 2: 0.40, 3: 0.35}


@dataclass(frozen=True)
class TeamSpec:
    attending: int
    resident: int
    nurse: int
    nurse_critical_care: int
    nurse_triage: int


@dataclass(frozen=True)
class DifficultyConfig:
    name: str
    base_arrivals_per_hour: float
    beds: dict[str, int]
    equipment: dict[str, int]
    day_team: TeamSpec
    night_team: TeamSpec
    budget: float
    # kind -> (min, max) number of occurrences over the full 72 hours
    events: dict[str, tuple[int, int]]
    inpatient_offers_per_hour: tuple[float, float] = (1.2, 0.4)  # (day, night)
    agency_daily_limit: int = 4
    rental_daily_limit: int = 4
    horizon_minutes: int = HORIZON_MINUTES
    notes: str = field(default="", compare=False)

    def with_horizon(self, hours: int) -> DifficultyConfig:
        """Shorter runs for development and tests. Budget and event counts scale with time."""
        if not 1 <= hours <= 72:
            raise ValueError("horizon_hours must be between 1 and 72")
        return replace(self, horizon_minutes=hours * MINUTES_PER_HOUR)


_STANDARD_DAY = TeamSpec(attending=2, resident=2, nurse=7, nurse_critical_care=3, nurse_triage=3)
_STANDARD_NIGHT = TeamSpec(attending=1, resident=2, nurse=5, nurse_critical_care=2, nurse_triage=2)
_BEDS = {"resus": 3, "monitored": 6, "general": 10, "fast_track": 4}
_EQUIPMENT = {"ventilator": 2, "portable_monitor": 3, "ct": 1, "xray": 1}

CONFIGS: dict[str, DifficultyConfig] = {
    "easy": DifficultyConfig(
        name="easy",
        base_arrivals_per_hour=2.0,
        beds=_BEDS,
        equipment=_EQUIPMENT,
        day_team=_STANDARD_DAY,
        night_team=_STANDARD_NIGHT,
        budget=95_000.0,
        events={
            "major_incident": (0, 1),
            "demand_spike": (1, 2),
            "staff_sickness": (1, 1),
            "equipment_failure": (1, 2),
            "bed_closure": (0, 1),
            "supply_shortage": (0, 1),
            "budget_cut": (0, 0),
        },
    ),
    "standard": DifficultyConfig(
        name="standard",
        base_arrivals_per_hour=2.5,
        beds=_BEDS,
        equipment=_EQUIPMENT,
        day_team=_STANDARD_DAY,
        night_team=_STANDARD_NIGHT,
        budget=106_000.0,
        events={
            "major_incident": (1, 2),
            "demand_spike": (2, 3),
            "staff_sickness": (2, 3),
            "equipment_failure": (2, 4),
            "bed_closure": (1, 2),
            "supply_shortage": (1, 1),
            "budget_cut": (0, 1),
        },
    ),
    "hard": DifficultyConfig(
        name="hard",
        base_arrivals_per_hour=2.9,
        beds={**_BEDS, "resus": 2},
        equipment=_EQUIPMENT,
        day_team=_STANDARD_DAY,
        night_team=TeamSpec(attending=1, resident=1, nurse=5, nurse_critical_care=2, nurse_triage=2),
        budget=110_000.0,
        events={
            "major_incident": (2, 3),
            "demand_spike": (3, 4),
            "staff_sickness": (3, 4),
            "equipment_failure": (3, 5),
            "bed_closure": (2, 3),
            "supply_shortage": (1, 2),
            "budget_cut": (1, 1),
        },
        agency_daily_limit=3,
    ),
}


def load_config(name: str, horizon_hours: int | None = None) -> DifficultyConfig:
    if name not in CONFIGS:
        raise ValueError(f"unknown difficulty {name!r}; choose one of {sorted(CONFIGS)}")
    config = CONFIGS[name]
    return config.with_horizon(horizon_hours) if horizon_hours else config


def hour_of_day(minute: int) -> int:
    return (CLOCK_START_HOUR + minute // MINUTES_PER_HOUR) % 24


def is_night(minute: int) -> bool:
    return hour_of_day(minute) >= 23 or hour_of_day(minute) < 7


def clock_label(minute: int) -> str:
    total = CLOCK_START_HOUR * MINUTES_PER_HOUR + minute
    day = total // (24 * MINUTES_PER_HOUR) + 1
    hh, mm = divmod(total % (24 * MINUTES_PER_HOUR), MINUTES_PER_HOUR)
    return f"Day {day} {hh:02d}:{mm:02d}"
