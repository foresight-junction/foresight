"""The simulation engine: owns the clock and runs each subsystem in a fixed order.

Each simulated minute has two phases:
- begin: discrete happenings at the start of minute t (events, repairs, beds, shifts,
  arrivals, inpatient offers and transfers, triage, imaging). The agent then sees the
  state at minute t and may act while the clock is frozen.
- run: continuous processes during minute t (treatment progress, deterioration risk and
  walk-outs, fatigue, costs, metric sampling). Then the clock moves to t+1.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict
from typing import Any

from app.edsim import budget, events, flow, outcomes, resources, staffing, views
from app.edsim import config as C
from app.edsim.actions import ACTIONS, get_patient
from app.edsim.entities import EDError
from app.edsim.generator import build_scenario
from app.edsim.state import SimState

NOTABLE = {
    "event_started",
    "event_ended",
    "critical_event",
    "patient_deteriorated",
    "treatment_complete",
    "treatment_extended",
    "staff_sick",
    "staff_off_duty",
    "equipment_repaired",
    "ambulance_diverted",
}
SAFE_ARG_TYPES = (str, int, float, bool, type(None))


def _summarize_args(kwargs: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in kwargs.items():
        if isinstance(value, SAFE_ARG_TYPES):
            out[key] = value
        elif isinstance(value, list) and all(isinstance(v, SAFE_ARG_TYPES) for v in value):
            out[key] = value[:20]
    return out


class Simulation:
    def __init__(
        self,
        difficulty: str = "standard",
        seed: int = 0,
        *,
        horizon_hours: int | None = None,
        config: C.DifficultyConfig | None = None,
    ) -> None:
        cfg = config or C.load_config(difficulty, horizon_hours)
        self.scenario = build_scenario(cfg, seed)
        self.state = SimState(self.scenario)
        self.state.emit(
            "episode_started",
            visibility="spectator",
            difficulty=cfg.name,
            horizon_minutes=cfg.horizon_minutes,
        )
        self._begin_minute()

    # --- time -------------------------------------------------------------------------
    @property
    def finished(self) -> bool:
        return self.state.finished

    def _begin_minute(self) -> None:
        s = self.state
        events.step_events(s)
        resources.step_equipment(s)
        resources.step_beds(s)
        staffing.step_shifts(s)
        flow.step_arrivals(s)
        flow.step_dispositions(s)
        flow.step_triage(s)
        resources.step_imaging(s)

    def _run_minute(self) -> None:
        s = self.state
        flow.step_treatment(s)
        outcomes.step_outcomes(s)
        staffing.step_fatigue(s)
        budget.step_costs(s)
        flow.sample(s)

    def _step(self) -> None:
        self._run_minute()
        self.state.minute += 1
        if self.state.finished:
            self.state.emit("episode_finished", visibility="spectator")
        else:
            self._begin_minute()

    def advance_time(self, minutes: Any) -> dict[str, Any]:
        """Run the department for 1..120 minutes with no new decisions."""
        if self.finished:
            self.state.invalid_actions["EPISODE_FINISHED"] += 1
            raise EDError("EPISODE_FINISHED")
        if (
            isinstance(minutes, bool)
            or not isinstance(minutes, int)
            or not 1 <= minutes <= C.MAX_ADVANCE_MINUTES
        ):
            self.state.invalid_actions["INVALID_ARGUMENT"] += 1
            raise EDError("INVALID_ARGUMENT", f"minutes must be an integer from 1 to {C.MAX_ADVANCE_MINUTES}")
        start_minute = self.state.minute
        start_seq = len(self.state.log)
        steps = min(minutes, self.state.horizon - self.state.minute)
        for _ in range(steps):
            self._step()
        self.state.action_counts["advance_time"] += 1
        window = [e for e in self.state.log[start_seq:] if e["visibility"] == "agent"]
        happened = Counter(e["kind"] for e in window)
        notable = [{k: v for k, v in e.items() if k != "visibility"} for e in window if e["kind"] in NOTABLE]
        return {
            "from": C.clock_label(start_minute),
            "to": C.clock_label(self.state.minute),
            "minutes_advanced": steps,
            "clock": views.clock(self.state),
            "happened": dict(happened),
            "notable": notable[-40:],
        }

    def run_to_end(self) -> None:
        """Fast-forward with no further decisions; used when an agent stops early."""
        while not self.finished:
            self.advance_time(C.MAX_ADVANCE_MINUTES)

    # --- actions ----------------------------------------------------------------------
    def act(self, name: str, **kwargs: Any) -> dict[str, Any]:
        action = ACTIONS.get(name)
        if action is None:
            raise EDError("INVALID_ARGUMENT", f"unknown action {name}")
        try:
            if self.finished:
                raise EDError("EPISODE_FINISHED")
            result = action(self.state, **kwargs)
        except EDError as err:
            self.state.invalid_actions[err.code] += 1
            self.state.emit("action_rejected", action=name, code=err.code, args=_summarize_args(kwargs))
            raise
        self.state.action_counts[name] += 1
        self.state.emit("action", action=name, args=_summarize_args(kwargs))
        return result

    # --- observations -----------------------------------------------------------------
    def department_status(self) -> dict[str, Any]:
        return views.department_status(self.state)

    def list_patients(self, status: str | None = None) -> dict[str, Any]:
        return views.list_patients(self.state, status)

    def patient(self, patient_id: Any) -> dict[str, Any]:
        return views.patient_detail(self.state, get_patient(self.state, patient_id))

    def staff_status(self, include_off_duty: bool = False) -> dict[str, Any]:
        return views.staff_status(self.state, include_off_duty)

    def resource_status(self) -> dict[str, Any]:
        return views.resource_status(self.state)

    def budget_status(self) -> dict[str, Any]:
        return views.budget_status(self.state)

    def active_events(self) -> dict[str, Any]:
        return views.active_events(self.state)

    def metrics(self) -> dict[str, Any]:
        return views.department_metrics(self.state)

    def recent_log(self, since_minute: int | None = None, limit: int = 100) -> dict[str, Any]:
        return views.recent_log(self.state, since_minute, limit)

    # --- evaluator side ---------------------------------------------------------------
    def truth(self) -> dict[str, Any]:
        """Ground truth for the evaluator. Never exposed through agent tools."""
        s = self.state
        return {
            "seed": s.seed,
            "difficulty": s.config.name,
            "horizon_minutes": s.horizon,
            "minute": s.minute,
            "finished": s.finished,
            "initial_budget": s.initial_budget,
            "budget": s.budget,
            "spent": s.spent,
            "ledger": dict(s.ledger),
            "accumulators": dict(s.acc),
            "patients": [asdict(p) for p in s.patients.values()],
            "action_counts": dict(s.action_counts),
            "invalid_actions": dict(s.invalid_actions),
        }
