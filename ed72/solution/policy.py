"""ED-72 reference decisions from the public observation only.

Doctor time is the scarce resource: a patient needs about one doctor-tick on average, and a doctor
who rests enough to stay fresh works about 61% of ticks (handbook section 3). Near the default
arrival rate the department is at that limit, so the plan protects fresh staff and buys agency cover
as soon as a backlog shows that the permanent team cannot keep up.
"""

from dataclasses import dataclass, field
from itertools import count

# Public rates: rulebook sections 5 and 8. The cutoff avoids a faint on the next Resus tick.
MAX_SAFE_FATIGUE = 90 - 2.2
# Planning cap: permanent staff normally rest before the 60-point tired threshold, which keeps them
# at full coverage and leaves a reserve for patients who cannot wait.
FRESH_FATIGUE = 50
URGENT_ESI = 2
# Uncovered patients that justify an agency order, and how many orders may be in transit at once.
BACKLOG_TO_HIRE = 4
MAX_ORDERS_IN_TRANSIT = 2
# A backlog this large is worth leaving the budget for. One doctor past the budget costs 0.75
# budget points (section 8) and adds 48 covered acute bed-ticks. OVERSPEND_LIMIT bounds the loss.
BACKLOG_TO_OVERSPEND = 8
OVERSPEND_LIMIT = 16000
# An order arrives 4 ticks later (section 3), so a late one has too few ticks left to pay for itself.
LAST_HIRE_TICK = 135
LAST_CT_BREAKDOWN_START = 75
# ESI 4-5 start leaving after 16 ticks of waiting (section 4) and lose all their weight when they do.
AGED_LIGHT_WAIT = 13
AGED_LIGHT_RANK = 3.5
REPAIR_COST = 2000
AGENCY_PRICES = (("doctor", 900), ("nurse", 350))
ZONES = ("resus", "acute", "fast_track")
COVERAGE = {
    "resus": {"doctor": 1, "nurse": 1},
    "acute": {"doctor": 3, "nurse": 2},
    "fast_track": {"doctor": 4, "nurse": 3},
}
WEIGHTS = {1: 10, 2: 5, 3: 2, 4: 1, 5: 0.5}
PREFERENCES = {
    1: ("resus",),
    2: ("acute", "resus"),
    3: ("acute", "fast_track"),
    4: ("fast_track", "acute"),
    5: ("fast_track", "acute"),
}


def staff_plan(
    patients: dict[str, list[dict]], staff: list[dict], max_fatigue: float = MAX_SAFE_FATIGUE
) -> tuple[dict, dict]:
    pools = {
        role: sorted(
            (
                s
                for s in staff
                if s["role"] == role and s["status"] in ("resting", "on_shift") and s["fatigue"] < max_fatigue
            ),
            key=lambda s: (s["fatigue"], s["id"]),
        )
        for role in ("doctor", "nurse")
    }
    assigned = {zone: {role: [] for role in pools} for zone in ZONES}
    covered = dict.fromkeys(ZONES, 0)
    patients = {zone: sorted(rows, key=lambda p: p["esi"]) for zone, rows in patients.items()}
    while True:
        candidates = []
        for zone in ZONES:
            if covered[zone] == len(patients[zone]):
                continue
            additions = {}
            for role, pool in pools.items():
                units = sum(s["counts_as"] for s in assigned[zone][role])
                for size in count():
                    if units * COVERAGE[zone][role] + 1e-9 >= covered[zone] + 1:
                        additions[role] = pool[:size]
                        break
                    if size == len(pool):
                        break
                    units += pool[size]["counts_as"]
            if len(additions) != 2:
                continue
            capacity = min(
                int(
                    (
                        sum(s["counts_as"] for s in assigned[zone][role] + additions[role])
                        * COVERAGE[zone][role]
                    )
                    + 1e-9
                )
                for role in pools
            )
            capacity = min(capacity, len(patients[zone]))
            gain = sum(WEIGHTS[p["esi"]] for p in patients[zone][covered[zone] : capacity])
            cost = sum(len(rows) for rows in additions.values())
            candidates.append((gain / max(1, cost), -ZONES.index(zone), zone, additions, capacity))
        if not candidates:
            break
        _, _, zone, additions, capacity = max(candidates, key=lambda row: row[:2])
        for role, rows in additions.items():
            assigned[zone][role].extend(rows)
            pools[role] = pools[role][len(rows) :]
        covered[zone] = capacity
    locations = {s["id"]: zone for zone in ZONES for rows in assigned[zone].values() for s in rows}
    return locations, covered


@dataclass
class ReferencePolicy:
    name = "reference"
    hired_warnings: set[tuple[str, int]] = field(default_factory=set)
    repair_tick: int | None = None

    def actions(self, observation: dict) -> list[dict]:
        if observation["finished"]:
            return []
        tick = observation["tick"]
        actions = []
        spent = observation["budget"]["spent"]
        # Agency hires are discretionary; urgent CT repairs may exceed the soft budget.
        limit = min(observation["budget"]["budget"], observation["budget"]["hard_limit"])
        if observation["ct"]["working"]:
            self.repair_tick = None
        elif self.repair_tick is None and spent + REPAIR_COST <= observation["budget"]["hard_limit"]:
            actions.append({"type": "repair"})
            spent += REPAIR_COST
            self.repair_tick = tick
        for warning in observation["warnings"]:
            key = (warning["event"], warning["start_tick"])
            if key not in self.hired_warnings and 0 <= warning["start_tick"] - tick <= 9:
                for role, price in AGENCY_PRICES * 2:
                    if spent + price + REPAIR_COST <= limit:
                        actions.append({"type": "agency", "role": role})
                        spent += price
                self.hired_warnings.add(key)
        patients = {zone: [] for zone in ZONES}
        free = dict.fromkeys(ZONES, 0)
        for bed in observation["beds"]:
            if bed["patient"] is None:
                free[bed["zone"]] += 1
            else:
                patients[bed["zone"]].append(bed)
        admissions = []
        for patient in sorted(observation["waiting"], key=_admission_order):
            for zone in PREFERENCES[patient["esi"]]:
                if zone == "resus" and patient["esi"] == 2 and free[zone] <= 1:
                    continue
                if free[zone]:
                    free[zone] -= 1
                    patients[zone].append(patient)
                    admissions.append({"type": "admit", "patient": patient["id"], "zone": zone})
                    break
        unplaced = len(observation["waiting"]) - len(admissions)
        locations, covered = staff_plan(patients, observation["staff"], FRESH_FATIGUE)
        uncovered = _uncovered(patients, covered)
        if any(p["esi"] <= URGENT_ESI for p in uncovered):
            # Tired staff count for less and cost wellbeing, but a waiting ESI 1-2 can die this tick.
            locations, covered = staff_plan(patients, observation["staff"])
            uncovered = _uncovered(patients, covered)
        actions.extend(self._backlog_hires(observation, locations, len(uncovered) + unplaced, spent))
        covered_ids = {
            p["id"] if "id" in p else p["patient"]
            for zone, rows in patients.items()
            for p in sorted(rows, key=lambda p: p["esi"])[: covered[zone]]
        }
        for member in observation["staff"]:
            if member["status"] in ("resting", "on_shift"):
                destination = locations.get(member["id"], "rest")
                if destination != member["location"]:
                    actions.append({"type": "assign", "staff": member["id"], "to": destination})
        actions.extend(a for a in admissions if a["patient"] in covered_ids)
        if len(actions) > 50:
            raise RuntimeError("Reference plan exceeds the 50-action limit")
        return actions

    act = actions

    def _backlog_hires(self, observation: dict, locations: dict, backlog: int, spent: int) -> list[dict]:
        """Order the role that has no fresh person left when patients are going uncovered."""
        staff = observation["staff"]
        tick = observation["tick"]
        in_transit = sum(s["status"] == "agency_ordered" for s in staff)
        if backlog < BACKLOG_TO_HIRE or in_transit >= MAX_ORDERS_IN_TRANSIT or tick > LAST_HIRE_TICK:
            return []
        budget = observation["budget"]
        limit = budget["budget"]
        if backlog >= BACKLOG_TO_OVERSPEND:
            limit = max(limit, min(OVERSPEND_LIMIT, budget["hard_limit"]))
        # Keep one repair affordable until the breakdown window (section 5) has passed.
        reserve = REPAIR_COST if tick <= LAST_CT_BREAKDOWN_START and self.repair_tick is None else 0
        hires = []
        for role, price in AGENCY_PRICES:
            spare = any(
                s["role"] == role
                and s["status"] in ("resting", "on_shift")
                and s["fatigue"] < FRESH_FATIGUE
                and s["id"] not in locations
                for s in staff
            )
            if not spare and spent + price + reserve <= limit:
                hires.append({"type": "agency", "role": role})
                spent += price
        return hires


def _admission_order(patient: dict) -> tuple:
    """Severity first, except that a light patient close to walking out goes ahead of other light patients."""
    esi = patient["esi"]
    rank = AGED_LIGHT_RANK if esi >= 4 and patient["waited_ticks"] >= AGED_LIGHT_WAIT else esi
    return (rank, patient["arrived_tick"], patient["id"])


def _uncovered(patients: dict[str, list[dict]], covered: dict[str, int]) -> list[dict]:
    return [
        p for zone, rows in patients.items() for p in sorted(rows, key=lambda p: p["esi"])[covered[zone] :]
    ]
