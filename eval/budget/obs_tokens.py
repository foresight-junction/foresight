"""Token size of a realistic ED-72 observation and step result (CONTRACTS v1 shape).

uv run --no-project --python 3.12 --with tiktoken python eval/budget/obs_tokens.py
"""

import json

import tiktoken

enc = tiktoken.get_encoding("o200k_base")


def bed(zone: str, bed_id: str, i: int, filled: bool) -> dict:
    if not filled:
        return {"zone": zone, "bed": bed_id, "patient": None}
    return {
        "zone": zone,
        "bed": bed_id,
        "patient": f"P{100 + i:03d}",
        "esi": 1 + i % 5,
        "treated_ticks": i % 4,
        "treatment_ticks": 5,
        "covered": i % 3 != 0,
        "waiting_for_ct": False,
    }


def observation(n_waiting: int, n_agency: int, filled_ratio: float) -> dict:
    zones = [("resus", "R", 3), ("acute", "A", 8), ("fast_track", "F", 6)]
    beds, i = [], 0
    for zone, prefix, count in zones:
        for k in range(1, count + 1):
            beds.append(bed(zone, f"{prefix}{k}", i, (i % 10) < filled_ratio * 10))
            i += 1
    staff = []
    for k in range(1, 7):
        staff.append(
            {
                "id": f"D{k}",
                "role": "doctor",
                "agency": False,
                "location": "acute",
                "fatigue": 41.6,
                "counts_as": 1,
                "status": "on_shift",
                "ticks_until_change": None,
            }
        )
    for k in range(1, 10):
        staff.append(
            {
                "id": f"N{k}",
                "role": "nurse",
                "agency": False,
                "location": "rest",
                "fatigue": 63.2,
                "counts_as": 0.6,
                "status": "resting",
                "ticks_until_change": None,
            }
        )
    for k in range(1, n_agency + 1):
        staff.append(
            {
                "id": f"AN{k}",
                "role": "nurse",
                "agency": True,
                "location": "fast_track",
                "fatigue": 12.0,
                "counts_as": 1,
                "status": "on_shift",
                "ticks_until_change": 9,
            }
        )
    waiting = [
        {
            "id": f"P{200 + k:03d}",
            "esi": 2 + k % 4,
            "arrived_tick": 30 + k,
            "waited_ticks": k,
            "needs_ct": k % 5 == 0,
        }
        for k in range(n_waiting)
    ]
    return {
        "tick": 37,
        "clock": "Day 1 02:30",
        "ticks_left": 107,
        "finished": False,
        "budget": {"spent": 1250, "budget": 12000, "hard_limit": 24000},
        "waiting": waiting,
        "beds": beds,
        "staff": staff,
        "ct": {"working": False, "down_ticks_left": 9},
        "warnings": [{"event": "bus_crash", "start_tick": 101}],
        "diversion": {"active": False, "ticks_left": 0},
        "totals": {"discharged": 41, "deaths": 2, "left": 0, "diverted": 0, "faints": 1},
        "last_rejected": [],
    }


def tokens(obj: dict, compact: bool) -> int:
    text = json.dumps(obj, separators=(",", ":")) if compact else json.dumps(obj, indent=2)
    return len(enc.encode(text))


cases = {
    "quiet (3 waiting, 60% beds)": observation(3, 0, 0.6),
    "busy (12 waiting, 100% beds, 2 agency)": observation(12, 2, 1.0),
    "surge (25 waiting, 100% beds, 4 agency)": observation(25, 4, 1.0),
}
for name, obs in cases.items():
    step = {"results": [{"index": i, "ok": True} for i in range(6)], "observation": obs}
    print(
        f"{name}: obs compact={tokens(obs, True)} indented={tokens(obs, False)}"
        f" | step result compact={tokens(step, True)}",
    )
