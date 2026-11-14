"""MOCK: a tiny hand-written stand-in for the hospital tools, for unit tests only.

It returns CONTRACTS v1 shapes and validates actions with the v1 reasons, but its dynamics are
crude (fixed arrivals, treatment ignores coverage, no hazards). It is never used for scoring.
"""

from typing import Any

ZONES = ("resus", "acute", "fast_track")
BED_IDS = {
    "resus": ["R1", "R2", "R3"],
    "acute": [f"A{i}" for i in range(1, 9)],
    "fast_track": [f"F{i}" for i in range(1, 7)],
}
ALLOWED = {1: {"resus"}, 2: {"resus", "acute"}, 3: set(ZONES), 4: set(ZONES), 5: set(ZONES)}
TREAT = {1: 6, 2: 5, 3: 3, 4: 2, 5: 1}
GAIN = {"resus": 2.2, "acute": 1.6, "fast_track": 1.6}
COST = {"doctor": 900, "nurse": 350}
TICKS = 144
CT_DOWN = (66, 82)


class FakeClient:
    def __init__(self, arrivals: dict[int, list[int]] | None = None) -> None:
        # MOCK: by default one patient per tick, ESI cycling 4, 1, 3, 5, 2.
        self.arrivals = (
            arrivals if arrivals is not None else {t: [(4, 1, 3, 5, 2)[t % 5]] for t in range(TICKS)}
        )
        self.tick = 0
        self.finished = False
        self.calls: list[str] = []
        self.steps: list[list[dict]] = []
        self.spent = 0
        self.ct_back = None
        self.divert_until = -1
        self.patients: dict[str, dict] = {}
        self.beds: dict[str, str | None] = {b: None for ids in BED_IDS.values() for b in ids}
        self.staff = [self._person(f"D{i}", "doctor") for i in range(1, 7)]
        self.staff += [self._person(f"N{i}", "nurse") for i in range(1, 10)]
        self.agency = {"doctor": 0, "nurse": 0}
        self.last_rejected: list[dict] = []
        self.diverted = 0
        self._arrive()

    @staticmethod
    def _person(sid: str, role: str, agency: bool = False) -> dict:
        return {
            "id": sid,
            "role": role,
            "agency": agency,
            "location": "rest",
            "fatigue": 0.0,
            "status": "resting",
            "due": None,
        }

    def _arrive(self) -> None:
        if self.tick == CT_DOWN[0]:
            self.ct_back = CT_DOWN[1]
        if self.ct_back == self.tick:
            self.ct_back = None
        for s in self.staff:
            if s["status"] == "agency_ordered" and s["due"] == self.tick:
                s["status"], s["due"] = "resting", None
        for esi in self.arrivals.get(self.tick, []):
            pid = f"P{len(self.patients) + 1:03d}"
            diverted = self.tick <= self.divert_until
            self.diverted += diverted
            self.patients[pid] = {
                "esi": esi,
                "arrived": self.tick,
                "status": "diverted" if diverted else "waiting",
            }

    def rules(self) -> dict[str, Any]:
        self.calls.append("rules")
        return {"text": "MOCK handbook"}

    def observe(self) -> dict[str, Any]:
        self.calls.append("observe")
        return self._obs()

    def _obs(self) -> dict[str, Any]:
        beds = []
        for zone in ZONES:
            for bed in BED_IDS[zone]:
                pid = self.beds[bed]
                if pid is None:
                    beds.append({"zone": zone, "bed": bed, "patient": None})
                else:
                    p = self.patients[pid]
                    beds.append(
                        {
                            "zone": zone,
                            "bed": bed,
                            "patient": pid,
                            "esi": p["esi"],
                            "treated_ticks": p["treated"],
                            "treatment_ticks": TREAT[p["esi"]],
                            "covered": True,
                            "waiting_for_ct": False,
                        }
                    )
        down = 0 if self.ct_back is None else self.ct_back - self.tick
        return {
            "tick": self.tick,
            "clock": "MOCK",
            "ticks_left": 0 if self.finished else TICKS - self.tick,
            "finished": self.finished,
            "budget": {"spent": self.spent, "budget": 12000, "hard_limit": 24000},
            "waiting": [
                {
                    "id": pid,
                    "esi": p["esi"],
                    "arrived_tick": p["arrived"],
                    "waited_ticks": self.tick - p["arrived"],
                    "needs_ct": False,
                }
                for pid, p in self.patients.items()
                if p["status"] == "waiting"
            ],
            "beds": beds,
            "staff": [
                {
                    "id": s["id"],
                    "role": s["role"],
                    "agency": s["agency"],
                    "location": s["location"],
                    "fatigue": round(s["fatigue"], 1),
                    "counts_as": 0.6 if s["fatigue"] > 60 else 1,
                    "status": s["status"],
                    "ticks_until_change": None if s["due"] is None else s["due"] - self.tick,
                }
                for s in self.staff
            ],
            "ct": {"working": self.ct_back is None, "down_ticks_left": down},
            "warnings": [],
            "diversion": {
                "active": self.divert_until - self.tick > 0,
                "ticks_left": max(0, self.divert_until - self.tick),
            },
            "totals": {"discharged": 0, "deaths": 0, "left": 0, "diverted": self.diverted, "faints": 0},
            "last_rejected": self.last_rejected,
        }

    def step(self, actions: list[dict]) -> dict[str, Any]:
        self.calls.append("step")
        if self.finished:
            return {"error": "episode_over"}
        self.steps.append(actions)
        results = []
        for i, action in enumerate(actions):
            reason = self._apply(action)
            results.append(
                {"index": i, "ok": True} if reason is None else {"index": i, "ok": False, "reason": reason}
            )
        self.last_rejected = [
            {"index": r["index"], "action": actions[r["index"]], "reason": r["reason"]}
            for r in results
            if not r["ok"]
        ]
        for bed, pid in self.beds.items():
            if pid is not None:
                p = self.patients[pid]
                p["treated"] += 1
                if p["treated"] >= TREAT[p["esi"]]:
                    self.beds[bed], p["status"] = None, "discharged"
        for s in self.staff:
            if s["status"] == "on_shift":
                s["fatigue"] += GAIN[s["location"]]
            elif s["status"] == "resting":
                s["fatigue"] = max(0.0, s["fatigue"] - 2.5)
        if self.tick < TICKS - 1:
            self.tick += 1
            self._arrive()
        else:
            self.finished = True
        return {"results": results, "observation": self._obs()}

    def _apply(self, a: object) -> str | None:
        if not isinstance(a, dict):
            return "bad_action"
        kind = a.get("type")
        if kind == "admit":
            pid, zone = a.get("patient"), a.get("zone")
            if not isinstance(pid, str) or zone not in ZONES:
                return "bad_action"
            p = self.patients.get(pid)
            if p is None:
                return "unknown_patient"
            if p["status"] != "waiting":
                return "not_waiting"
            if zone not in ALLOWED[p["esi"]]:
                return "zone_not_allowed"
            bed = next((b for b in BED_IDS[zone] if self.beds[b] is None), None)
            if bed is None:
                return "no_free_bed"
            self.beds[bed] = pid
            p.update(status="bed", zone=zone, treated=0)
            return None
        if kind == "assign":
            sid, to = a.get("staff"), a.get("to")
            if not isinstance(sid, str) or to not in (*ZONES, "rest"):
                return "bad_action"
            s = next((x for x in self.staff if x["id"] == sid), None)
            if s is None:
                return "unknown_staff"
            if s["status"] not in ("on_shift", "resting"):
                return "staff_unavailable"
            s["location"], s["status"] = to, "resting" if to == "rest" else "on_shift"
            return None
        if kind == "agency":
            role = a.get("role")
            if role not in COST:
                return "bad_action"
            if self.spent + COST[role] > 24000:
                return "over_hard_limit"
            self.spent += COST[role]
            self.agency[role] += 1
            person = self._person(f"A{role[0].upper()}{self.agency[role]}", role, agency=True)
            person.update(status="agency_ordered", due=self.tick + 4)
            self.staff.append(person)
            return None
        if kind == "repair":
            if self.ct_back is None:
                return "ct_not_broken"
            if self.spent + 2000 > 24000:
                return "over_hard_limit"
            self.spent += 2000
            self.ct_back = min(self.ct_back, self.tick + 3)
            return None
        if kind == "divert":
            if self.divert_until - self.tick > 0:
                return "diversion_active"
            self.divert_until = self.tick + 4
            return None
        return "bad_action"
