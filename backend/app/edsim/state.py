"""The simulation state container: entities, schedules, budget ledger, log and accumulators."""

from __future__ import annotations

from collections import Counter
from typing import Any

from app.edsim import config as C
from app.edsim.entities import ActiveEvent, Bed, Equipment, Patient, ScheduledEvent, Staff
from app.edsim.generator import Scenario

LEDGER_CATEGORIES = ("wages", "overtime", "agency", "supplies", "rentals", "repairs", "transfers")


class SimState:
    def __init__(self, scenario: Scenario) -> None:
        self.config: C.DifficultyConfig = scenario.config
        self.seed = scenario.seed
        self.horizon = scenario.config.horizon_minutes
        self.minute = 0
        self.initial_budget = scenario.budget
        self.budget = scenario.budget

        # Hidden future: consumed in order as the clock reaches each entry.
        self.future_patients: list[Patient] = list(scenario.patients)
        self.future_events: list[ScheduledEvent] = list(scenario.events)
        self.future_offers: list[int] = list(scenario.inpatient_offers)
        self._next_patient = 0
        self._next_event = 0
        self._next_offer = 0

        self.patients: dict[str, Patient] = {}
        self.staff: dict[str, Staff] = {s.staff_id: s for s in scenario.staff}
        self.beds: dict[str, Bed] = {b.bed_id: b for b in scenario.beds}
        self.equipment: dict[str, Equipment] = {e.equipment_id: e for e in scenario.equipment}
        self.active_events: dict[str, ActiveEvent] = {}
        self.imaging_queue: dict[str, list[str]] = {kind: [] for kind in C.IMAGING}
        self.inpatient_queue: list[str] = []
        self.diversion = False
        self.supply_multiplier = 1.0
        self.supply_until: int | None = None

        self.ledger: dict[str, float] = dict.fromkeys(LEDGER_CATEGORIES, 0.0)
        self.agency_requests: Counter[int] = Counter()
        self.rental_requests: Counter[int] = Counter()
        self.id_counters: Counter[str] = Counter()

        self.log: list[dict[str, Any]] = []
        self._seq = 0
        self.action_counts: Counter[str] = Counter()
        self.invalid_actions: Counter[str] = Counter()
        # Ground-truth accumulators for the evaluator (never exposed to the agent).
        self.acc: Counter[str] = Counter()

    # --- schedules -------------------------------------------------------------------
    def due_patients(self) -> list[Patient]:
        due: list[Patient] = []
        while self._next_patient < len(self.future_patients):
            patient = self.future_patients[self._next_patient]
            if patient.arrival_min > self.minute:
                break
            due.append(patient)
            self._next_patient += 1
        return due

    def due_events(self) -> list[ScheduledEvent]:
        due: list[ScheduledEvent] = []
        while self._next_event < len(self.future_events):
            event = self.future_events[self._next_event]
            if event.minute > self.minute:
                break
            due.append(event)
            self._next_event += 1
        return due

    def due_offers(self) -> int:
        count = 0
        while (
            self._next_offer < len(self.future_offers) and self.future_offers[self._next_offer] <= self.minute
        ):
            count += 1
            self._next_offer += 1
        return count

    # --- budget ----------------------------------------------------------------------
    @property
    def spent(self) -> float:
        return sum(self.ledger.values())

    def charge(self, category: str, amount: float) -> None:
        self.ledger[category] += amount

    # --- ids and log -----------------------------------------------------------------
    def next_id(self, prefix: str) -> str:
        self.id_counters[prefix] += 1
        return f"{prefix}-{self.id_counters[prefix]}"

    def emit(self, kind: str, visibility: str = "agent", **data: Any) -> None:
        """visibility: 'agent' (agent and spectators), 'spectator', or 'truth' (evaluator only)."""
        self._seq += 1
        self.log.append(
            {"seq": self._seq, "minute": self.minute, "kind": kind, "visibility": visibility, **data}
        )

    @property
    def day_index(self) -> int:
        return self.minute // (24 * C.MINUTES_PER_HOUR)

    @property
    def finished(self) -> bool:
        return self.minute >= self.horizon
