"""MOCK: a stand-in for ed72_sim.engine.Simulation until #3/#4 land on main.

It mirrors the real class's surface the tool server uses (kostiantyn/env-sim-core):
observe(), step(actions) returning `episode_over` after the last tick, `finished`,
an `events` list whose `seq` is the list index, a JSONL log file, and the
`record_call` method requested on #4. Used only with USE_MOCKS=1 and in the server
tests; it is not copied into the hospital image.
"""

import copy
import json
import random
from pathlib import Path

TICKS = 144
EVENT_LOG_PATH = "/var/lib/ed72/events.jsonl"
BEDS = {"resus": ["R1", "R2", "R3"], "acute": [f"A{i}" for i in range(1, 9)], "fast_track": ["F1", "F2"]}


class MockSimulation:
    def __init__(self, seed: int, log_path: Path | None = None) -> None:
        self.rng = random.Random(seed)
        self.tick = 0
        self.finished = False
        self.next_id = 1
        self.waiting: list[dict] = []
        self.beds: dict[str, str | None] = {bed: None for beds in BEDS.values() for bed in beds}
        self.events: list[dict] = []
        self.last_rejected: list[dict] = []
        self.log_path = log_path
        self._arrive()

    def _write(self, fields: dict) -> None:
        line = {"seq": len(self.events), "t": self.tick, **fields}
        self.events.append(line)
        if self.log_path is not None:
            with self.log_path.open("a", encoding="utf-8", newline="\n") as f:
                f.write(json.dumps(line, separators=(",", ":")) + "\n")

    def record_call(self, tool: str, args: dict, result: dict) -> None:
        self._write({"src": "agent", "tool": tool, "args": args, "result": result})

    def _arrive(self) -> None:
        for _ in range(self.rng.randint(0, 2)):
            patient = {"id": f"P{self.next_id:03d}", "esi": self.rng.randint(1, 5), "arrived_tick": self.tick}
            self.next_id += 1
            self.waiting.append(patient)
            self._write({"src": "sim", "event": "arrival", "patient": patient["id"]})

    def observe(self) -> dict:
        return {
            "tick": self.tick,
            "ticks_left": TICKS - 1 - self.tick,
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
        self._write({"src": "sim", "event": "admitted", "patient": patient["id"], "bed": free[0]})
        return None

    def step(self, actions: list[dict]) -> dict:
        if self.finished:
            return {"error": "episode_over"}
        results = []
        self.last_rejected = []
        for index, action in enumerate(actions):
            is_admit = isinstance(action, dict) and action.get("type") == "admit"
            reason = self._admit(action) if is_admit else "bad_action"
            if reason is None:
                results.append({"index": index, "ok": True})
            else:
                results.append({"index": index, "ok": False, "reason": reason})
                self.last_rejected.append({"index": index, "action": action, "reason": reason})
        self.record_call("step", {"actions": copy.deepcopy(actions)}, {"results": results})
        if self.tick == TICKS - 1:
            self.finished = True
        else:
            self.tick += 1
            self._arrive()
        return {"results": results, "observation": self.observe()}
