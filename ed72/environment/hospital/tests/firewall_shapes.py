"""Exact CONTRACTS v1 result shapes (docs/CONTRACTS.md, Tools v1). Any extra field is an error.

The enums are written out here instead of imported from ed72_sim, so a sim change that adds a
field or a value fails this check until CONTRACTS is changed through the contract-change skill.
"""

import re
from collections.abc import Callable
from typing import Any

Check = Callable[[Any], bool]

TOOLS = ("rules", "observe", "step")
ZONES = ("resus", "acute", "fast_track")
BED_ZONE = {f"R{i}": "resus" for i in range(1, 4)} | {f"A{i}": "acute" for i in range(1, 9)}
BED_ZONE |= {f"F{i}": "fast_track" for i in range(1, 7)}
REASONS = (
    "bad_action",
    "unknown_patient",
    "not_waiting",
    "zone_not_allowed",
    "no_free_bed",
    "unknown_staff",
    "staff_unavailable",
    "over_hard_limit",
    "ct_not_broken",
    "diversion_active",
)
ERRORS = ("call_cap_reached", "episode_over")
STAFF_STATUSES = ("on_shift", "resting", "fainted", "sick", "agency_ordered", "agency_left")
ANNOUNCED_EVENTS = ("flu_wave", "bus_crash")
PATIENT_ID = re.compile(r"P\d{3,}")
STAFF_ID = re.compile(r"D[1-6]|N[1-9]|A[DN][1-9]\d*")
CLOCK = re.compile(r"Day \d+ \d\d:\d\d")


def _count(v: Any) -> bool:
    return type(v) is int and v >= 0


def _bool(v: Any) -> bool:
    return type(v) is bool


def _one_of(*values: Any) -> Check:
    # type() first: True == 1 and 1 == 1.0 would otherwise pass an int enum or a bool field
    return lambda v: any(type(v) is type(x) and v == x for x in values)


def _matches(pattern: re.Pattern[str]) -> Check:
    return lambda v: type(v) is str and pattern.fullmatch(v) is not None


def _fatigue(v: Any) -> bool:
    return type(v) in (int, float) and 0 <= v <= 100


WAITING = {
    "id": _matches(PATIENT_ID),
    "esi": _one_of(1, 2, 3, 4, 5),
    "arrived_tick": _count,
    "waited_ticks": _count,
    "needs_ct": _bool,
}
EMPTY_BED = {"zone": _one_of(*ZONES), "bed": _one_of(*BED_ZONE), "patient": lambda v: v is None}
BED = EMPTY_BED | {
    "patient": _matches(PATIENT_ID),
    "esi": _one_of(1, 2, 3, 4, 5),
    "treated_ticks": _count,
    "treatment_ticks": _count,
    "covered": _bool,
    "waiting_for_ct": _bool,
}
STAFF = {
    "id": _matches(STAFF_ID),
    "role": _one_of("doctor", "nurse"),
    "agency": _bool,
    "location": _one_of(*ZONES, "rest"),
    "fatigue": _fatigue,
    "counts_as": _one_of(1, 0.6),
    "status": _one_of(*STAFF_STATUSES),
    "ticks_until_change": lambda v: v is None or _count(v),
}
OBSERVATION = {
    "tick": _count,
    "clock": _matches(CLOCK),
    "ticks_left": _count,
    "finished": _bool,
    "budget": {"spent": _count, "budget": _count, "hard_limit": _count},
    "waiting": [WAITING],
    "beds": lambda v: type(v) is list,  # items checked in observation_errors: two variants
    "staff": [STAFF],
    "ct": {"working": _bool, "down_ticks_left": _count},
    "warnings": [{"event": _one_of(*ANNOUNCED_EVENTS), "start_tick": _count}],
    "diversion": {"active": _bool, "ticks_left": _count},
    "totals": {k: _count for k in ("discharged", "deaths", "left", "diverted", "faints")},
    "last_rejected": [{"index": _count, "action": lambda v: type(v) is dict, "reason": _one_of(*REASONS)}],
}
RESULT_OK = {"index": _count, "ok": lambda v: v is True}
RESULT_REJECTED = {"index": _count, "ok": lambda v: v is False, "reason": _one_of(*REASONS)}


def shape_errors(value: Any, spec: Any, path: str) -> list[str]:
    """spec is a dict (exact keys), a one-item list (every element), or a Check."""
    if isinstance(spec, dict):
        if type(value) is not dict:
            return [f"{path}: expected an object, got {type(value).__name__}"]
        errors = [f"{path}.{k}: missing" for k in spec if k not in value]
        errors += [f"{path}.{k}: field not in CONTRACTS" for k in value if k not in spec]
        for k in spec.keys() & value.keys():
            errors += shape_errors(value[k], spec[k], f"{path}.{k}")
        return errors
    if isinstance(spec, list):
        if type(value) is not list:
            return [f"{path}: expected a list, got {type(value).__name__}"]
        return [e for i, item in enumerate(value) for e in shape_errors(item, spec[0], f"{path}[{i}]")]
    return [] if spec(value) else [f"{path}: value {value!r} not allowed by CONTRACTS"]


def observation_errors(obs: Any, path: str) -> list[str]:
    errors = shape_errors(obs, OBSERVATION, path)
    if errors or type(obs) is not dict:
        return errors
    seen = []
    for i, bed in enumerate(obs["beds"]):
        spec = EMPTY_BED if isinstance(bed, dict) and bed.get("patient") is None else BED
        bed_errors = shape_errors(bed, spec, f"{path}.beds[{i}]")
        errors += bed_errors
        if not bed_errors:
            seen.append(bed["bed"])
            if BED_ZONE[bed["bed"]] != bed["zone"]:
                errors.append(f"{path}.beds[{i}]: bed {bed['bed']} is not in zone {bed['zone']}")
    if not errors and sorted(seen) != sorted(BED_ZONE):
        errors.append(f"{path}.beds: expected every bed exactly once, got {seen}")
    for i, row in enumerate(obs["waiting"]):
        if row["waited_ticks"] != obs["tick"] - row["arrived_tick"]:
            errors.append(f"{path}.waiting[{i}]: waited_ticks does not match tick - arrived_tick")
    return errors


def result_errors(tool: str, payload: Any) -> list[str]:
    """Shape errors for one tool result, as the agent receives it."""
    if tool not in TOOLS:
        return [f"$: tool {tool!r} is not one of the CONTRACTS tools {TOOLS}"]
    if type(payload) is dict and "error" in payload:
        return shape_errors(payload, {"error": _one_of(*ERRORS)}, "$")
    if tool == "rules":
        return shape_errors(payload, {"text": lambda v: type(v) is str}, "$")
    if tool == "observe":
        return observation_errors(payload, "$")
    errors = shape_errors(payload, {"results": lambda v: type(v) is list, "observation": lambda v: True}, "$")
    if errors:
        return errors
    for i, row in enumerate(payload["results"]):
        spec = RESULT_OK if isinstance(row, dict) and row.get("ok") is True else RESULT_REJECTED
        errors += shape_errors(row, spec, f"$.results[{i}]")
        if isinstance(row, dict) and row.get("index") != i:
            errors.append(f"$.results[{i}]: index {row.get('index')!r} is not {i}")
    return errors + observation_errors(payload["observation"], "$.observation")
