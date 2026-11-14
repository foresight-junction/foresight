"""Stand-in reference policy with one switch per rulebook lever (F1-F6), for the ablations of issue #36.

MOCK: this stands in for the #16 reference policy (ed72/solution/) until that lands. Once it does, the
ablations should run the real reference with the same lever switches, and these numbers are replaced.

The policy reads only the public CONTRACTS v1 observation (the dict `observe` returns) and returns a
list of actions. It never reads the world, the seed, the event log or the sim internals (AGENTS.md
§10.4). The rule numbers below are the public ones from the handbook (rulebook §3, §5, §8), restated so
the policy never imports the sim.

Removing a lever gives the policy without that one skill; everything else stays the same.
"""

import math

ZONES = ("resus", "acute", "fast_track")
ROLES = ("doctor", "nurse")
ASSIGNABLE = ("on_shift", "resting")
BEDS_PER = {
    "doctor": {"resus": 1, "acute": 3, "fast_track": 4},
    "nurse": {"resus": 1, "acute": 2, "fast_track": 3},
}
ALLOWED = {
    1: ("resus",),
    2: ("resus", "acute"),
    3: ("resus", "acute", "fast_track"),
    4: ("resus", "acute", "fast_track"),
    5: ("resus", "acute", "fast_track"),
}
AGENCY_COST = {"doctor": 900, "nurse": 350}
AGENCY_DELAY = 4
REPAIR_COST = 2000
REPAIR_TICKS = 3
TIRED_ABOVE = 60.0  # above this a person counts as 0.6 and W counts them as tired
FAINT_AT = 90.0
MAX_GAIN = 2.2  # resus, the fastest fatigue gain per tick

ALL_LEVERS = frozenset(
    {"resus_reservation", "rest_rotation", "warnings", "ct_repair", "agency", "no_panic_divert"}
)

# Never put anyone on shift who could reach 90 after this tick's gain: a faint costs W and 10 ticks.
SAFE_MAX = FAINT_AT - MAX_GAIN - 0.1
# Agency staff ordered ahead of an announced event, timed to arrive at its start (rulebook §7).
SURGE_AGENCY = {"bus_crash": {"doctor": 2, "nurse": 2}, "flu_wave": {"doctor": 0, "nurse": 1}}
# Without the no_panic_divert lever: divert whenever more than this many patients are waiting.
PANIC_QUEUE = 3


def _admit(patient: str, zone: str) -> dict:
    return {"type": "admit", "patient": patient, "zone": zone}


def _assign(staff: str, to: str) -> dict:
    return {"type": "assign", "staff": staff, "to": to}


class StandInPolicy:
    """Severity-first admits, demand-based staffing from the least tired, plus the six levers.

    One instance plays one episode: it remembers only what it has already done (repair sent,
    surge agency ordered), which it could also read back from the observation.
    """

    def __init__(self, levers: frozenset[str] = ALL_LEVERS) -> None:
        unknown = set(levers) - ALL_LEVERS
        if unknown:
            raise ValueError(f"unknown lever(s) {sorted(unknown)}")
        self.levers = frozenset(levers)
        self._repaired = False
        self._surge_ordered: set[tuple[str, int]] = set()

    def __call__(self, obs: dict) -> list[dict]:
        if obs["finished"]:
            return []
        actions = self._admits(obs)
        occupied = dict.fromkeys(ZONES, 0)
        for bed in obs["beds"]:
            if bed["patient"] is not None:
                occupied[bed["zone"]] += 1
        for a in actions:
            occupied[a["zone"]] += 1
        staffing, short = self._staffing(obs, occupied)
        actions += staffing
        agency = self._agency(obs, short)
        spent = obs["budget"]["spent"] + sum(AGENCY_COST[a["role"]] for a in agency)
        actions += agency
        actions += self._repair(obs, spent)
        actions += self._divert(obs)
        return actions

    # --- admits -------------------------------------------------------------------------------

    def _bus_soon(self, obs: dict) -> bool:
        return "warnings" in self.levers and any(
            w["event"] == "bus_crash" and w["start_tick"] > obs["tick"] for w in obs["warnings"]
        )

    def _zones_for(self, esi: int, free: dict[str, int], bus_soon: bool) -> tuple[str, ...]:
        if "resus_reservation" not in self.levers:
            # F1: whoever is next takes the first free allowed bed, resus first.
            return ALLOWED[esi]
        if esi == 1:
            return ("resus",)
        if esi == 2:
            # Acute costs a third of a doctor, resus a whole one. Resus only if one stays free for ESI 1.
            return ("acute", "resus") if free["resus"] >= 2 else ("acute",)
        if bus_soon:
            # F3 prep: keep acute free for the bus crash's ESI 2-3 patients; ESI 4-5 can wait 16 ticks.
            return ("fast_track",) if esi >= 4 else ("fast_track", "acute")
        return ("acute", "fast_track") if esi == 3 else ("fast_track", "acute")

    def _admits(self, obs: dict) -> list[dict]:
        free = dict.fromkeys(ZONES, 0)
        for bed in obs["beds"]:
            if bed["patient"] is None:
                free[bed["zone"]] += 1
        bus_soon = self._bus_soon(obs)
        actions = []
        for p in sorted(obs["waiting"], key=lambda w: (w["esi"], w["arrived_tick"], w["id"])):
            zone = next((z for z in self._zones_for(p["esi"], free, bus_soon) if free[z] > 0), None)
            if zone is not None:
                free[zone] -= 1
                actions.append(_admit(p["id"], zone))
        return actions

    # --- staffing -----------------------------------------------------------------------------

    def _staffing(self, obs: dict, occupied: dict[str, int]) -> tuple[list[dict], dict[str, int]]:
        """Put exactly the staff the occupied beds need on shift; return (actions, fresh shortfall)."""
        rotate = "rest_rotation" in self.levers
        pool = [s for s in obs["staff"] if s["status"] in ASSIGNABLE]
        if rotate:
            # Least tired first; nobody on shift who might faint this tick.
            pool = [s for s in pool if s["fatigue"] <= SAFE_MAX]
            pool.sort(key=lambda s: (s["fatigue"], s["id"]))
        else:
            # F2: keep the same crew on shift until they faint, then call in whoever is free.
            pool.sort(key=lambda s: (s["status"] != "on_shift", s["id"]))
        target: dict[str, str] = {}
        placed = {(z, r): 0 for z in ZONES for r in ROLES}
        short = dict.fromkeys(ROLES, 0)
        for fresh_only in (True, False):
            for zone in ZONES:
                for role in ROLES:
                    need = math.ceil(occupied[zone] / BEDS_PER[role][zone]) - placed[zone, role]
                    for s in pool:
                        if need <= 0:
                            break
                        if s["id"] in target or s["role"] != role:
                            continue
                        if fresh_only and rotate and s["fatigue"] > TIRED_ABOVE:
                            continue
                        target[s["id"]] = zone
                        placed[zone, role] += 1
                        need -= 1
                    if fresh_only and need > 0:
                        short[role] += need
        actions = []
        for s in obs["staff"]:
            if s["status"] not in ASSIGNABLE:
                continue
            to = target.get(s["id"])
            if to is None:
                if not rotate and s["status"] == "on_shift":
                    continue  # F2: nobody is sent to rest
                to = "rest"
            if to != s["location"]:
                actions.append(_assign(s["id"], to))
        return actions, short

    # --- spending -----------------------------------------------------------------------------

    def _agency(self, obs: dict, short: dict[str, int]) -> list[dict]:
        if "agency" not in self.levers:
            return []  # F5: never order agency staff
        budget = obs["budget"]
        spent = budget["spent"]
        actions = []
        pending = {
            r: sum(1 for s in obs["staff"] if s["status"] == "agency_ordered" and s["role"] == r)
            for r in ROLES
        }
        orders = {r: max(0, short[r] - pending[r]) for r in ROLES}
        if "warnings" in self.levers:
            for w in obs["warnings"]:
                key = (w["event"], w["start_tick"])
                lead = w["start_tick"] - obs["tick"]
                if key in self._surge_ordered or not 0 < lead <= AGENCY_DELAY:
                    continue
                self._surge_ordered.add(key)
                for role, n in SURGE_AGENCY.get(w["event"], {}).items():
                    orders[role] += n
        for role in ROLES:
            for _ in range(orders[role]):
                if spent + AGENCY_COST[role] > budget["budget"]:
                    break  # stay inside the soft budget, so B stays 1
                spent += AGENCY_COST[role]
                actions.append({"type": "agency", "role": role})
        return actions

    def _repair(self, obs: dict, spent: int) -> list[dict]:
        if "ct_repair" not in self.levers or self._repaired:
            return []  # F4: never repair
        ct, budget = obs["ct"], obs["budget"]
        if ct["working"] or ct["down_ticks_left"] <= REPAIR_TICKS:
            return []
        stuck = any(b["patient"] is not None and b["waiting_for_ct"] for b in obs["beds"])
        coming = any(w["needs_ct"] for w in obs["waiting"]) or any(
            b["patient"] is not None and b["esi"] <= 2 for b in obs["beds"]
        )
        if not (stuck or coming) or spent + REPAIR_COST > budget["budget"]:
            return []
        self._repaired = True
        return [{"type": "repair"}]

    def _divert(self, obs: dict) -> list[dict]:
        if "no_panic_divert" in self.levers:
            return []  # the full policy never diverts
        if obs["diversion"]["active"] or len(obs["waiting"]) <= PANIC_QUEUE:
            return []
        return [{"type": "divert"}]  # F6: panic diversion on queue length alone
