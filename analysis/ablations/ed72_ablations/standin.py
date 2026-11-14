"""Stand-in reference policy with one switch per rulebook lever (F1-F6), for the ablations of issue #36.

MOCK: this stands in for the #16 reference policy (ed72/solution/), which has no lever switches. The
ablations run on this stand-in; the #16 reference runs unablated beside it (`run.py --policy reference`).

The policy reads only the public CONTRACTS v1 observation (the dict `observe` returns) and returns a
list of actions. It never reads the world, the seed, the event log or the sim internals (AGENTS.md
§10.4). The rule numbers below are the public ones from the handbook (rulebook §3, §5, §8), restated so
the policy never imports the sim; tests/test_ablations.py checks them against ed72_sim.constants.

Removing a lever removes only the decisions that lever owns; everything else is computed the same way.
The one coupling left is the shared budget: every order is capped by the soft budget, so a lever that
spends less leaves more for the others. Spending is checked in a fixed order (repair, surge agency,
shortfall agency), so agency orders can never crowd out a repair.
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
# Removing no_panic_divert ADDS a harmful habit (issue #36 variant 6) rather than removing a skill:
# without the lever the policy diverts whenever more than this many patients are waiting.
PANIC_QUEUE = 3


def _admit(patient: str, zone: str) -> dict:
    return {"type": "admit", "patient": patient, "zone": zone}


def _assign(staff: str, to: str) -> dict:
    return {"type": "assign", "staff": staff, "to": to}


class StandInPolicy:
    """Severity-first admits, demand-based staffing from the least tired, plus the six levers.

    One instance plays one episode. Its only memory is which warnings it already ordered surge staff
    for; the repair rule reads the observation alone.
    """

    def __init__(self, levers: frozenset[str] = ALL_LEVERS) -> None:
        unknown = set(levers) - ALL_LEVERS
        if unknown:
            raise ValueError(f"unknown lever(s) {sorted(unknown)}")
        self.levers = frozenset(levers)
        self._surge_ordered: set[tuple[str, int]] = set()

    def __call__(self, obs: dict) -> list[dict]:
        if obs["finished"]:
            return []
        admits = self._admits(obs)
        occupied = dict.fromkeys(ZONES, 0)
        for bed in obs["beds"]:
            if bed["patient"] is not None:
                occupied[bed["zone"]] += 1
        for a in admits:
            occupied[a["zone"]] += 1
        spent = obs["budget"]["spent"]
        repair = self._repair(obs, spent)
        spent += REPAIR_COST * len(repair)
        surge = self._surge_agency(obs, spent)
        spent += sum(AGENCY_COST[a["role"]] for a in surge)
        shortfall = self._shortfall_agency(obs, occupied, spent, surge)
        return admits + self._staffing(obs, occupied) + repair + surge + shortfall + self._divert(obs)

    # --- admits -------------------------------------------------------------------------------

    def _zones_for(self, esi: int, free: dict[str, int], bus_soon: bool) -> tuple[str, ...]:
        if "resus_reservation" not in self.levers:
            zones = ALLOWED[esi]  # F1: whoever is next takes the first free allowed bed, resus first
        elif esi == 1:
            zones = ("resus",)
        elif esi == 2:
            # Acute costs a third of a doctor, resus a whole one. Resus only if one stays free for ESI 1.
            zones = ("acute", "resus") if free["resus"] >= 2 else ("acute",)
        else:
            zones = ("acute", "fast_track") if esi == 3 else ("fast_track", "acute")
        if bus_soon and esi >= 3:
            # F3 prep: keep acute free for the bus crash's ESI 2-3. ESI 3 may still overflow into it;
            # ESI 4-5 wait instead (they have 16 ticks before they may leave).
            zones = tuple(z for z in zones if z != "acute") + (("acute",) if esi == 3 else ())
        return zones

    def _admits(self, obs: dict) -> list[dict]:
        free = dict.fromkeys(ZONES, 0)
        for bed in obs["beds"]:
            if bed["patient"] is None:
                free[bed["zone"]] += 1
        bus_soon = "warnings" in self.levers and any(
            w["event"] == "bus_crash" and w["start_tick"] > obs["tick"] for w in obs["warnings"]
        )
        actions = []
        for p in sorted(obs["waiting"], key=lambda w: (w["esi"], w["arrived_tick"], w["id"])):
            zone = next((z for z in self._zones_for(p["esi"], free, bus_soon) if free[z] > 0), None)
            if zone is not None:
                free[zone] -= 1
                actions.append(_admit(p["id"], zone))
        return actions

    # --- staffing -----------------------------------------------------------------------------

    def _staffing(self, obs: dict, occupied: dict[str, int]) -> list[dict]:
        """Put on shift the staff the occupied beds need, counting a tired person as 0.6 (rulebook §5)."""
        rotate = "rest_rotation" in self.levers
        pool = [s for s in obs["staff"] if s["status"] in ASSIGNABLE]
        if rotate:
            # Fresh before tired, least tired first, nobody who might faint this tick.
            pool = [s for s in pool if s["fatigue"] <= SAFE_MAX]
            pool.sort(key=lambda s: (s["counts_as"] < 1, s["fatigue"], s["id"]))
        else:
            # F2: keep the same crew on shift until they faint, then call in whoever is free.
            pool.sort(key=lambda s: (s["status"] != "on_shift", s["id"]))
        target: dict[str, str] = {}
        tenths = {(z, r): 0 for z in ZONES for r in ROLES}  # coverage in tenths of a person, as the sim
        for zone in ZONES:
            for role in ROLES:
                for s in pool:
                    if tenths[zone, role] * BEDS_PER[role][zone] // 10 >= occupied[zone]:
                        break
                    if s["id"] in target or s["role"] != role:
                        continue
                    target[s["id"]] = zone
                    tenths[zone, role] += round(s["counts_as"] * 10)
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
        return actions

    # --- spending -----------------------------------------------------------------------------

    def _order(self, wanted: dict[str, int], spent: int, budget: int) -> list[dict]:
        actions = []
        for role in ROLES:
            for _ in range(wanted.get(role, 0)):
                if spent + AGENCY_COST[role] > budget:
                    break  # stay inside the soft budget, so B stays 1
                spent += AGENCY_COST[role]
                actions.append({"type": "agency", "role": role})
        return actions

    def _surge_agency(self, obs: dict, spent: int) -> list[dict]:
        """F3: agency staff for an announced event, ordered so they arrive at its start."""
        if "warnings" not in self.levers:
            return []
        wanted = dict.fromkeys(ROLES, 0)
        for w in obs["warnings"]:
            key = (w["event"], w["start_tick"])
            if key in self._surge_ordered or not 0 < w["start_tick"] - obs["tick"] <= AGENCY_DELAY:
                continue
            self._surge_ordered.add(key)
            for role, n in SURGE_AGENCY.get(w["event"], {}).items():
                wanted[role] += n
        return self._order(wanted, spent, obs["budget"]["budget"])

    def _shortfall_agency(
        self, obs: dict, occupied: dict[str, int], spent: int, surge: list[dict]
    ) -> list[dict]:
        """F5: order agency when the beds need more fresh staff than there are.

        Computed from the observation the same way whatever the other levers do: fresh people needed
        for full coverage, minus assignable fresh people, minus agency already or just ordered.
        """
        if "agency" not in self.levers:
            return []
        wanted = {}
        for role in ROLES:
            need = sum(math.ceil(occupied[z] / BEDS_PER[role][z]) for z in ZONES)
            fresh = sum(
                1
                for s in obs["staff"]
                if s["role"] == role and s["status"] in ASSIGNABLE and s["fatigue"] <= TIRED_ABOVE
            )
            pending = sum(1 for s in obs["staff"] if s["role"] == role and s["status"] == "agency_ordered")
            pending += sum(1 for a in surge if a["role"] == role)
            wanted[role] = max(0, need - fresh - pending)
        return self._order(wanted, spent, obs["budget"]["budget"])

    def _repair(self, obs: dict, spent: int) -> list[dict]:
        """F4: repair once per breakdown, when it saves ticks and a CT or ESI 1-2 patient is present.

        An accepted repair brings the CT back within REPAIR_TICKS, so `down_ticks_left <= REPAIR_TICKS`
        means a repair is pending (or no longer pays); a rejected repair leaves it above, and is retried.
        """
        if "ct_repair" not in self.levers:
            return []
        ct = obs["ct"]
        if ct["working"] or ct["down_ticks_left"] <= REPAIR_TICKS:
            return []
        useful = any(w["needs_ct"] for w in obs["waiting"]) or any(
            b["patient"] is not None and (b["waiting_for_ct"] or b["esi"] <= 2) for b in obs["beds"]
        )
        if not useful or spent + REPAIR_COST > obs["budget"]["budget"]:
            return []
        return [{"type": "repair"}]

    def _divert(self, obs: dict) -> list[dict]:
        if "no_panic_divert" in self.levers:
            return []  # the full policy never diverts
        if obs["diversion"]["active"] or len(obs["waiting"]) <= PANIC_QUEUE:
            return []
        return [{"type": "divert"}]  # F6: panic diversion on queue length alone
