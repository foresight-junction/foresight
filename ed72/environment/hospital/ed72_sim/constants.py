"""Every rule number of the game, in one place.

Sources: rulebook docs/ED_Management_Simulator_RU.md (section in brackets) and the decisions in
docs/SPEC.md §12. Values marked TUNE are starting points for the difficulty config (issue #8).
Any change here must also change HANDBOOK.md and docs/SPEC.md (AGENTS.md rule 10.3).
"""

from typing import Final

# Episode (§2)
TICKS: Final = 144
TICK_MINUTES: Final = 30
START_HOUR: Final = 8

# Department (§3)
ZONES: Final = ("resus", "acute", "fast_track")
BEDS: Final = {"resus": 3, "acute": 8, "fast_track": 6}
BED_PREFIX: Final = {"resus": "R", "acute": "A", "fast_track": "F"}
BEDS_PER_DOCTOR: Final = {"resus": 1, "acute": 3, "fast_track": 4}
BEDS_PER_NURSE: Final = {"resus": 1, "acute": 2, "fast_track": 3}

# Patients (§4). ZONE_EXTRA_TICKS[esi][zone] is the extra treatment time in that zone;
# a zone missing from the inner dict may not treat that ESI.
ESI_LEVELS: Final = (1, 2, 3, 4, 5)
ARRIVAL_MIX: Final = {1: 0.04, 2: 0.14, 3: 0.34, 4: 0.30, 5: 0.18}
TREATMENT_TICKS: Final = {1: 6, 2: 5, 3: 3, 4: 2, 5: 1}
TARGET_TICKS: Final = {1: 0, 2: 1, 3: 4, 4: 8, 5: 12}
OUTCOME_WEIGHT: Final = {1: 10.0, 2: 5.0, 3: 2.0, 4: 1.0, 5: 0.5}
ZONE_EXTRA_TICKS: Final = {
    1: {"resus": 0},
    2: {"resus": 0, "acute": 1},
    3: {"resus": 0, "acute": 0, "fast_track": 1},
    4: {"resus": 0, "acute": 0, "fast_track": 0},
    5: {"resus": 0, "acute": 0, "fast_track": 0},
}
CT_ESI: Final = (1, 2)
CT_SHARE: Final = 0.5

# Arrivals (§4, SPEC §12): Poisson per tick, mean ARRIVAL_MEAN * (1 + AMPLITUDE * cos(2*pi*(h - PEAK)/24)).
ARRIVAL_MEAN: Final = 4.0  # TUNE
ARRIVAL_AMPLITUDE: Final = 0.5  # TUNE
ARRIVAL_PEAK_HOUR: Final = 15.0  # TUNE

# Staff (§5)
N_DOCTORS: Final = 6
N_NURSES: Final = 9
FATIGUE_GAIN: Final = {"resus": 2.2, "acute": 1.6, "fast_track": 1.6}
FATIGUE_REST: Final = 2.5
FATIGUE_TIRED: Final = 60.0
TIRED_COUNTS_AS: Final = 0.6
FATIGUE_FAINT: Final = 90.0
FAINT_TICKS: Final = 10
AGENCY_DELAY: Final = 4
AGENCY_STAY: Final = 16
AGENCY_COST: Final = {"doctor": 900, "nurse": 350}

# Hazards (§6): chance per tick
P_DEATH_ESI1_WAITING: Final = 0.15
P_DEATH_ESI2_WAITING: Final = 0.04
ESI2_WAIT_GRACE: Final = 1  # hazard applies when waited ticks > this
P_UPGRADE_ESI3: Final = 0.08
ESI3_WAIT_GRACE: Final = 6
P_LEAVE_ESI45: Final = 0.08
ESI45_WAIT_GRACE: Final = 16
P_DEATH_UNCOVERED: Final = {1: 0.10, 2: 0.03}
P_DEATH_FATIGUE: Final = 0.015  # ESI 1-2 on a covered bed in a zone with mean on-shift fatigue > 60

# Events (§7). warning = ticks of notice before start (0 = unannounced).
EVENTS: Final = {
    "staff_sickness": {"window": (28, 35), "duration": 20, "warning": 0},
    "flu_wave": {"window": (50, 61), "duration": 6, "warning": 10},
    "ct_breakdown": {"window": (66, 75), "duration": 16, "warning": 0},
    "bus_crash": {"window": (96, 109), "duration": 2, "warning": 8},
}
SICK_NURSES: Final = 2
FLU_EXTRA_PER_TICK: Final = 2
FLU_MIX: Final = {3: 0.40, 4: 0.35, 5: 0.25}  # TUNE
BUS_EXTRA_PER_TICK: Final = 5
BUS_MIX: Final = {1: 0.20, 2: 0.30, 3: 0.50}

# Actions and budget (§8)
REPAIR_COST: Final = 2000
REPAIR_TICKS: Final = 3
DIVERT_TICKS: Final = 4
DIVERT_SHARE: Final = 0.7
BUDGET: Final = 12000
HARD_LIMIT: Final = 24000

# Score (§11, SPEC §6)
LOSS_DISCHARGED: Final = 0.0
LOSS_IN_BED_COVERED: Final = 0.3
LOSS_DIVERTED: Final = 0.75  # TUNE: rulebook §13 fix; keeps permanent diversion under about 47 points at 4.0 arrivals
LOSS_FAILED: Final = 1.0  # died, left, never admitted, or in a bed at the end with no covered tick
W_TIRED_WEIGHT: Final = 1.0  # TUNE
W_FAINT_WEIGHT: Final = 0.05  # TUNE

# Hospital-side file the server appends the event log to; collect.py replays it.
EVENT_LOG_PATH: Final = "/var/lib/ed72/events.jsonl"
