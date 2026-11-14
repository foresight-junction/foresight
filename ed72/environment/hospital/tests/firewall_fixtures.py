"""MOCK: hand-written tool results shaped like CONTRACTS v1, with matching ground truth.

Used to test the firewall checks before the real sim (#4) and server (#5) are merged. The truth is
a world at tick 37: the CT broke down at tick 30 (unannounced, so now visible), the flu wave starts
at 45 (announced 10 ticks ahead, so its warning is shown), the sick call at 60 and the bus crash at
101 are still in the future, and P053 onwards have not arrived yet.
"""

import copy

from firewall_checks import HiddenEvent, Truth

TICK = 37
SEED = 918_273
DICE = (0.7310581063434194, 0.04871219638511032)

TRUTH = Truth(
    seed=SEED,
    arrivals={f"P{n:03d}": (n - 1) * TICK // 51 for n in range(1, 53)}
    | {f"P{n:03d}": n - 15 for n in range(53, 61)},
    events=(
        HiddenEvent("staff_sickness", 60, 20),
        HiddenEvent("flu_wave", 45, 6),
        HiddenEvent("ct_breakdown", 30, 16),
        HiddenEvent("bus_crash", 101, 2),
    ),
    dice=frozenset(DICE),
)

_BEDS = (
    [
        {
            "zone": "resus",
            "bed": "R1",
            "patient": "P049",
            "esi": 1,
            "treated_ticks": 2,
            "treatment_ticks": 6,
            "covered": True,
            "waiting_for_ct": False,
        }
    ]
    + [{"zone": "resus", "bed": f"R{i}", "patient": None} for i in (2, 3)]
    + [{"zone": "acute", "bed": f"A{i}", "patient": None} for i in range(1, 4)]
    + [
        {
            "zone": "acute",
            "bed": "A4",
            "patient": "P047",
            "esi": 2,
            "treated_ticks": 3,
            "treatment_ticks": 6,
            "covered": False,
            "waiting_for_ct": True,
        }
    ]
    + [{"zone": "acute", "bed": f"A{i}", "patient": None} for i in range(5, 9)]
    + [{"zone": "fast_track", "bed": f"F{i}", "patient": None} for i in range(1, 7)]
)


def _staff(staff_id: str, role: str, location: str, fatigue: float) -> dict:
    on_shift = location != "rest"
    return {
        "id": staff_id,
        "role": role,
        "agency": False,
        "location": location,
        "fatigue": fatigue,
        "counts_as": 0.6 if fatigue > 60 else 1,
        "status": "on_shift" if on_shift else "resting",
        "ticks_until_change": None,
    }


_STAFF = [
    _staff(f"D{i}", "doctor", z, 20.5 + i)
    for i, z in enumerate(["resus", "acute", "acute"] + ["rest"] * 3, 1)
]
_STAFF += [
    _staff(f"N{i}", "nurse", z, 55.0 + i)
    for i, z in enumerate(["resus", "acute", "acute", "acute"] + ["rest"] * 5, 1)
]
_STAFF.append(
    {
        "id": "AN1",
        "role": "nurse",
        "agency": True,
        "location": "rest",
        "fatigue": 0,
        "counts_as": 1,
        "status": "agency_ordered",
        "ticks_until_change": 2,
    }
)

_LAST_REJECTED = [
    {
        "index": 1,
        "action": {"type": "admit", "patient": "P050", "zone": "fast_track"},
        "reason": "zone_not_allowed",
    }
]

_OBSERVATION = {
    "tick": TICK,
    "clock": "Day 2 02:30",
    "ticks_left": 107,
    "finished": False,
    "budget": {"spent": 1250, "budget": 12000, "hard_limit": 24000},
    "waiting": [{"id": "P051", "esi": 2, "arrived_tick": 36, "waited_ticks": 1, "needs_ct": True}],
    "beds": _BEDS,
    "staff": _STAFF,
    "ct": {"working": False, "down_ticks_left": 9},
    "warnings": [{"event": "flu_wave", "start_tick": 45}],
    "diversion": {"active": False, "ticks_left": 0},
    "totals": {"discharged": 41, "deaths": 2, "left": 0, "diverted": 0, "faints": 1},
    "last_rejected": _LAST_REJECTED,
}

_STEP = {
    "results": [{"index": 0, "ok": True}, {"index": 1, "ok": False, "reason": "zone_not_allowed"}],
    "observation": _OBSERVATION,
}

# Real handbook text names event kinds and example ids; the rules result is not value-checked.
_RULES = {"text": "# ED-72 handbook\nThe CT may break down (ct_breakdown). Example: admit P042 to resus."}


def observation() -> dict:
    return copy.deepcopy(_OBSERVATION)


def step_result() -> dict:
    return copy.deepcopy(_STEP)


def rules_result() -> dict:
    return copy.deepcopy(_RULES)
