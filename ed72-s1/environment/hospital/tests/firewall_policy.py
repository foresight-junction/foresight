"""Scripted test-double policy for the firewall episodes (issue #31). Not a reference policy.

It sees only the observation, like the agent. It staffs the zones, rotates tired staff, admits by
severity, orders agency staff on warnings, repairs the CT, diverts once and passes some ticks.
It also sends probes, invalid actions whose CONTRACTS reason is known in advance, so every
rejection reason is exercised.
"""

from collections.abc import Callable
from dataclasses import dataclass, field

MAX_ACTIONS = 50
HARD_LIMIT_PROBE_TICK = 138
DIVERT_TICK = 20
TIRED = 75.0
RESTED = 30.0
ADMIT_ZONES = {
    1: ("resus",),
    2: ("resus", "acute"),
    3: ("acute", "fast_track"),
    4: ("fast_track", "acute"),
    5: ("fast_track", "acute"),
}
OPENING = {
    "resus": ("D1", "N1", "N2"),
    "acute": ("D2", "D3", "N3", "N4", "N5", "N6"),
    "fast_track": ("D4", "N7"),
}
AGENCY_COST = {"doctor": 900, "nurse": 350}


@dataclass(frozen=True)
class Probe:
    tick: int
    index: int
    reason: str
    action: dict


@dataclass
class ScriptedPolicy:
    probes: list[Probe] = field(default_factory=list)
    _sent: set[str] = field(default_factory=set)  # one-off probes already sent
    _answered: set[tuple[str, int]] = field(default_factory=set)  # warnings already acted on
    _agency_nurses: int = 0

    def actions(self, obs: dict, future_patient: str | None = None) -> list[dict]:
        """One tick's actions. future_patient is an id that has not arrived yet, chosen by the test."""
        tick = obs["tick"]
        out: list[dict] = []

        def probe(action: dict, reason: str) -> None:
            self.probes.append(Probe(tick, len(out), reason, action))
            out.append(action)

        if tick % 9 == 4:
            return out
        if tick == 0:
            out += [{"type": "assign", "staff": s, "to": z} for z, crew in OPENING.items() for s in crew]
        else:
            out += self._rotate(obs["staff"])
        if tick == 1:
            probe({"type": "teleport"}, "bad_action")
            probe({"type": "admit", "patient": "P001"}, "bad_action")
            probe({"type": "admit", "patient": "P9999", "zone": "acute"}, "unknown_patient")
            probe({"type": "assign", "staff": "D99", "to": "acute"}, "unknown_staff")
            if obs["ct"]["working"]:
                probe({"type": "repair"}, "ct_not_broken")
        if future_patient and "future" not in self._sent:
            self._sent.add("future")
            probe({"type": "admit", "patient": future_patient, "zone": "acute"}, "unknown_patient")
        if not obs["ct"]["working"] and "repair" not in self._sent:
            self._sent.add("repair")
            out.append({"type": "repair"})
        if tick == DIVERT_TICK:
            out.append({"type": "divert"})
        if tick == DIVERT_TICK + 1:
            probe({"type": "divert"}, "diversion_active")
        for w in obs["warnings"]:
            if (w["event"], w["start_tick"]) not in self._answered:
                self._answered.add((w["event"], w["start_tick"]))
                self._agency_nurses += 1
                out.append({"type": "agency", "role": "nurse"})
                probe(
                    {"type": "assign", "staff": f"AN{self._agency_nurses}", "to": "acute"},
                    "staff_unavailable",
                )
        self._admit(obs, out, probe)
        if tick == HARD_LIMIT_PROBE_TICK:
            spent = obs["budget"]["spent"]
            for _ in range(MAX_ACTIONS - len(out)):
                order = {"type": "agency", "role": "doctor"}
                if spent + AGENCY_COST["doctor"] > obs["budget"]["hard_limit"]:
                    probe(order, "over_hard_limit")
                else:
                    spent += AGENCY_COST["doctor"]
                    out.append(order)
        return out

    def _rotate(self, staff: list[dict]) -> list[dict]:
        """Swap each tired person on shift for a rested one of the same role."""
        rested = [s for s in staff if s["status"] == "resting" and s["fatigue"] <= RESTED]
        out = []
        for s in staff:
            if s["status"] != "on_shift" or s["fatigue"] <= TIRED:
                continue
            spare = next((r for r in rested if r["role"] == s["role"]), None)
            if spare is None:
                continue
            rested.remove(spare)
            out.append({"type": "assign", "staff": spare["id"], "to": s["location"]})
            out.append({"type": "assign", "staff": s["id"], "to": "rest"})
        return out

    def _admit(self, obs: dict, out: list[dict], probe: Callable[[dict, str], None]) -> None:
        free = {z: 0 for z in ("resus", "acute", "fast_track")}
        for bed in obs["beds"]:
            free[bed["zone"]] += bed["patient"] is None
        waiting = sorted(obs["waiting"], key=lambda p: (p["esi"], p["arrived_tick"], p["id"]))
        occupied = next((b for b in obs["beds"] if b["patient"] is not None), None)
        if occupied and "not_waiting" not in self._sent:
            self._sent.add("not_waiting")
            probe({"type": "admit", "patient": occupied["patient"], "zone": occupied["zone"]}, "not_waiting")
        severe = next((p for p in waiting if p["esi"] <= 2), None)
        if severe and "zone" not in self._sent:
            self._sent.add("zone")
            probe({"type": "admit", "patient": severe["id"], "zone": "fast_track"}, "zone_not_allowed")
        if obs["tick"] >= 2 and len(waiting) > free["resus"] and "full" not in self._sent:
            # every ESI may use resus, so filling it and admitting one more must hit no_free_bed
            self._sent.add("full")
            for p in waiting[: free["resus"]]:
                out.append({"type": "admit", "patient": p["id"], "zone": "resus"})
            last = waiting[free["resus"]]
            probe({"type": "admit", "patient": last["id"], "zone": "resus"}, "no_free_bed")
            waiting = waiting[free["resus"] :]
            free["resus"] = 0
        for p in waiting:
            zone = next((z for z in ADMIT_ZONES[p["esi"]] if free[z] > 0), None)
            if zone is not None and len(out) < MAX_ACTIONS - 1:
                free[zone] -= 1
                out.append({"type": "admit", "patient": p["id"], "zone": zone})
