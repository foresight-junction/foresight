"""Scripted baselines (rulebook §12) and the severity-first base the exploit probes build on.

Each policy reads only the observation. The rule numbers below are the public ones from the
handbook (rulebook §3, §5, §8); they are restated here so the baselines never import the sim.

The exploit probes (exploits.py) sit on top of `SeverityPolicy`, a plain severity-first player, so each one
differs from sensible play in exactly one shortcut. `SeverityPolicy` is not the reference policy
(that one lives in ed72/solution/, lane C).
"""

import math
from typing import ClassVar

from ed72_baselines.client import Action, Observation

ZONES = ("resus", "acute", "fast_track")
ALLOWED_ZONES = {
    1: ("resus",),
    2: ("resus", "acute"),
    3: ("resus", "acute", "fast_track"),
    4: ("resus", "acute", "fast_track"),
    5: ("resus", "acute", "fast_track"),
}
BEDS_PER = {
    "doctor": {"resus": 1, "acute": 3, "fast_track": 4},
    "nurse": {"resus": 1, "acute": 2, "fast_track": 3},
}
AGENCY_COST = {"doctor": 900, "nurse": 350}
REPAIR_COST = 2000
REPAIR_TICKS = 3
LAST_TICK = 143
ASSIGNABLE = ("on_shift", "resting")


def admit(patient: str, zone: str) -> Action:
    return {"type": "admit", "patient": patient, "zone": zone}


def assign(staff: str, to: str) -> Action:
    return {"type": "assign", "staff": staff, "to": to}


def free_beds(obs: Observation) -> dict[str, int]:
    free = dict.fromkeys(ZONES, 0)
    for bed in obs["beds"]:
        if bed["patient"] is None:
            free[bed["zone"]] += 1
    return free


def occupied_beds(obs: Observation) -> dict[str, int]:
    used = dict.fromkeys(ZONES, 0)
    for bed in obs["beds"]:
        if bed["patient"] is not None:
            used[bed["zone"]] += 1
    return used


class DoNothing:
    """Never acts (rulebook §12, rank 4, score 0)."""

    name = "do_nothing"

    def act(self, obs: Observation) -> list[Action] | None:
        return None


class ReactiveProxy:
    """Scripted stand-in for typical model play (rulebook §12, rank 2).

    First come first served into the first free bed in bed order R1..A8..F6, so light cases fill
    resus. Fixed posts until fatigue 85, then rest until RETURN_FATIGUE. Orders agency staff only
    when the queue reaches 10. Ignores warnings, never repairs the CT, never diverts.
    """

    name = "reactive_proxy"
    REST_AT = 85.0
    RETURN_FATIGUE = 30.0  # our choice; the rulebook only fixes the 85
    AGENCY_QUEUE = 10
    POSTS: ClassVar[dict[str, tuple[str, ...]]] = {
        "doctor": ("resus", "resus", "acute", "acute", "fast_track", "fast_track"),
        "nurse": ("resus", "resus", "resus", "acute", "acute", "acute", "acute", "fast_track", "fast_track"),
    }
    AGENCY_POST = "acute"

    def __init__(self) -> None:
        self._next_agency = "doctor"

    def _post(self, staff: dict) -> str:
        if staff["agency"]:
            return self.AGENCY_POST
        posts = self.POSTS[staff["role"]]
        return posts[(int(staff["id"][1:]) - 1) % len(posts)]

    def act(self, obs: Observation) -> list[Action] | None:
        actions: list[Action] = []
        for s in obs["staff"]:
            if s["status"] == "on_shift" and s["fatigue"] >= self.REST_AT:
                actions.append(assign(s["id"], "rest"))
            elif s["status"] == "resting" and s["fatigue"] <= self.RETURN_FATIGUE:
                actions.append(assign(s["id"], self._post(s)))

        pending = any(s["status"] == "agency_ordered" for s in obs["staff"])
        cost = AGENCY_COST[self._next_agency]
        budget = obs["budget"]
        queue_full = len(obs["waiting"]) >= self.AGENCY_QUEUE
        if queue_full and not pending and budget["spent"] + cost <= budget["hard_limit"]:
            actions.append({"type": "agency", "role": self._next_agency})
            self._next_agency = "nurse" if self._next_agency == "doctor" else "doctor"

        free = [b["zone"] for b in obs["beds"] if b["patient"] is None]
        for p in sorted(obs["waiting"], key=lambda w: (w["arrived_tick"], w["id"])):
            zone = next((z for z in free if z in ALLOWED_ZONES[p["esi"]]), None)
            if zone is not None:
                free.remove(zone)
                actions.append(admit(p["id"], zone))
        return actions


class StopEarly:
    """Plays the reactive proxy for 12 ticks, then stops calling tools (rulebook §12, rank 3)."""

    name = "stop_early"
    TICKS = 12

    def __init__(self) -> None:
        self._proxy = ReactiveProxy()

    def act(self, obs: Observation) -> list[Action] | None:
        if obs["tick"] >= self.TICKS:
            return None
        return self._proxy.act(obs)


class SeverityPolicy:
    """Severity-first admits, resus kept for ESI 1-2, demand-based staffing from the least tired,
    CT repaired within budget. The honest base the exploit probes deviate from."""

    name = "severity"
    PREFERRED: ClassVar[dict[int, tuple[str, ...]]] = {
        1: ("resus",),
        2: ("resus", "acute"),
        3: ("acute", "fast_track"),
        4: ("fast_track", "acute"),
        5: ("fast_track", "acute"),
    }
    REST_AT = 58.0  # stays under 60, where a person counts as 0.6
    READY_AT = 30.0

    def admits(self, obs: Observation) -> list[Action]:
        free = free_beds(obs)
        actions = []
        for p in sorted(obs["waiting"], key=lambda w: (w["esi"], w["arrived_tick"], w["id"])):
            zone = next((z for z in self.PREFERRED[p["esi"]] if free[z] > 0), None)
            if zone is not None:
                free[zone] -= 1
                actions.append(admit(p["id"], zone))
        return actions

    def staffing(self, obs: Observation, occupied: dict[str, int]) -> list[Action]:
        ready = [
            s
            for s in obs["staff"]
            if (s["status"] == "on_shift" and s["fatigue"] < self.REST_AT)
            or (s["status"] == "resting" and s["fatigue"] <= self.READY_AT)
        ]
        ready.sort(key=lambda s: (s["fatigue"], s["id"]))
        target: dict[str, str] = {}
        for zone in ZONES:
            for role in ("doctor", "nurse"):
                need = math.ceil(occupied[zone] / BEDS_PER[role][zone])
                for s in [s for s in ready if s["role"] == role and s["id"] not in target][:need]:
                    target[s["id"]] = zone
        actions = []
        for s in obs["staff"]:
            if s["status"] not in ASSIGNABLE:
                continue
            to = target.get(s["id"], "rest")
            if to != s["location"]:
                actions.append(assign(s["id"], to))
        return actions

    def repair(self, obs: Observation, limit_key: str = "budget") -> list[Action]:
        ct, budget = obs["ct"], obs["budget"]
        if ct["working"] or ct["down_ticks_left"] <= REPAIR_TICKS:
            return []
        if budget["spent"] + REPAIR_COST > budget[limit_key]:
            return []
        return [{"type": "repair"}]

    def plan(self, obs: Observation, admits: list[Action]) -> list[Action]:
        occupied = occupied_beds(obs)
        for a in admits:
            occupied[a["zone"]] += 1
        return admits + self.staffing(obs, occupied) + self.repair(obs)

    def act(self, obs: Observation) -> list[Action] | None:
        return self.plan(obs, self.admits(obs))
