"""MOCK: a stand-in for ed72_sim.Simulation until #4 lands.

It implements only the CONTRACTS v1 surface the tool server needs: observe(),
step(actions) and an `events` list of sim-written log lines. Used only when
USE_MOCKS=1 and in the server tests; it is not copied into the hospital image.
"""

import random

LAST_TICK = 143
BEDS = {"resus": ["R1", "R2", "R3"], "acute": [f"A{i}" for i in range(1, 9)], "fast_track": ["F1", "F2"]}


class MockSimulation:
    def __init__(self, seed: int) -> None:
        self.rng = random.Random(seed)
        self.tick = 0
        self.finished = False
        self.next_id = 1
        self.waiting: list[dict] = []
        self.beds: dict[str, str | None] = {bed: None for beds in BEDS.values() for bed in beds}
        self.events: list[dict] = []
        self.last_rejected: list[dict] = []
        self._arrive()

    def _arrive(self) -> None:
        for _ in range(self.rng.randint(0, 2)):
            patient = {"id": f"P{self.next_id:03d}", "esi": self.rng.randint(1, 5), "arrived_tick": self.tick}
            self.next_id += 1
            self.waiting.append(patient)
            self.events.append({"t": self.tick, "src": "sim", "event": "arrival", "patient": patient["id"]})

    def observe(self) -> dict:
        return {
            "tick": self.tick,
            "ticks_left": LAST_TICK - self.tick,
            "finished": self.finished,
            "waiting": [dict(p, waited_ticks=self.tick - p["arrived_tick"]) for p in self.waiting],
            "beds": [
                {"zone": zone, "bed": bed, "patient": self.beds[bed]}
                for zone, beds in BEDS.items()
                for bed in beds
            ],
            "last_rejected": self.last_rejected,
        }

    def _admit(self, action: dict) -> str | None:
        patient = next((p for p in self.waiting if p["id"] == action.get("patient")), None)
        zone = action.get("zone")
        if zone not in BEDS:
            return "bad_action"
        if patient is None:
            return "unknown_patient"
        free = [bed for bed in BEDS[zone] if self.beds[bed] is None]
        if not free:
            return "no_free_bed"
        self.beds[free[0]] = patient["id"]
        self.waiting.remove(patient)
        self.events.append(
            {"t": self.tick, "src": "sim", "event": "admitted", "patient": patient["id"], "bed": free[0]}
        )
        return None

    def step(self, actions: list[dict]) -> dict:
        results = []
        self.last_rejected = []
        for index, action in enumerate(actions):
            reason = self._admit(action) if action.get("type") == "admit" else "bad_action"
            if reason is None:
                results.append({"index": index, "ok": True})
            else:
                results.append({"index": index, "ok": False, "reason": reason})
                self.last_rejected.append({"index": index, "action": action, "reason": reason})
        if self.tick == LAST_TICK:
            self.finished = True
        else:
            self.tick += 1
            self._arrive()
        return {"results": results, "observation": self.observe()}
