"""The tick loop (SPEC §4). Draws no random numbers: every roll is read from the World."""

import copy
import json
from pathlib import Path

from ed72_sim import constants as c
from ed72_sim.actions import apply_actions
from ed72_sim.model import World
from ed72_sim.observation import build_observation
from ed72_sim.state import FAINT10, GAIN10, REST10, PatientState, State

_SCALARS = (str, int, float, bool, type(None))


def _copy_actions(actions: object) -> object:
    """copy.deepcopy, with a fast path for the usual list of flat dicts of scalars."""
    if type(actions) is list and all(
        type(a) is dict and all(type(k) is str and type(v) in _SCALARS for k, v in a.items()) for a in actions
    ):
        return [dict(a) for a in actions]
    return copy.deepcopy(actions)


class Simulation:
    def __init__(self, world: World, log_path: str | Path | None = None) -> None:
        self.world = world
        self.state = State(world)
        self.tick = 0
        self.finished = False
        self.events: list[dict] = []
        self._log_path = Path(log_path) if log_path is not None else None
        self._pending: list[str] = []  # log lines not yet on disk; flushed before each public call returns
        self._arrivals: dict[int, list] = {}
        for spec in world.patients:
            self._arrivals.setdefault(spec.arrival_tick, []).append(spec)
        try:
            self._emit("episode_start", budget=world.budget, hard_limit=world.hard_limit)
            self._begin_tick()
        finally:
            self._flush()

    def observe(self) -> dict:
        return build_observation(self.state, self.tick, self.finished)

    def step(self, actions: list[dict]) -> dict:
        if self.finished:
            return {"error": "episode_over"}
        results = self._resolve(actions, copy_actions=True)
        return {"results": results, "observation": self.observe()}

    def replay_step(self, actions: list[dict]) -> None:
        """step() for collect.py's replay: the same log lines, without the observation it never reads.
        The actions come fresh from json.loads and nothing else holds them, so they are logged uncopied."""
        if not self.finished:
            self._resolve(actions, copy_actions=False)

    def _resolve(self, actions: list[dict], *, copy_actions: bool) -> list[dict]:
        try:
            results = apply_actions(self.state, self.tick, actions, self._emit)
            logged = _copy_actions(actions) if copy_actions else actions
            self._write(
                {"src": "agent", "tool": "step", "args": {"actions": logged}, "result": {"results": results}}
            )
            self._finish_tick()
        finally:
            self._flush()
        return results

    def advance_without_actions(self) -> None:
        """Advance and flush one tick without logging an agent call."""
        if self.finished:
            return
        try:
            self._finish_tick()
        finally:
            self._flush()

    def run_to_end(self) -> None:
        """Run the remaining ticks with no actions. Writes no agent lines: the agent made no calls,
        and the scorer reads `ended`, `tool_calls` and F10 from the agent lines."""
        try:
            while not self.finished:
                self._finish_tick()
        finally:
            self._flush()

    def record_call(self, tool: str, args: dict, result: dict) -> None:
        """Log a call the server answered without resolving a tick: rules, observe, or a refused call.
        A refused call carries "error" in its result; collect.py and the scorer never replay it."""
        try:
            self._write({"src": "agent", "tool": tool, "args": args, "result": result})
        finally:
            self._flush()

    def _finish_tick(self) -> None:
        self._step6_treat()
        self._step7_hazards()
        self._step8_fatigue()
        if self.tick < c.TICKS - 1:
            self.tick += 1
            self._begin_tick()
        else:
            self.finished = True
            self._emit("episode_end")

    # --- log ---------------------------------------------------------------------------------

    def _write(self, fields: dict) -> None:
        line = {"seq": len(self.events), "t": self.tick, **fields}
        self.events.append(line)
        if self._log_path is not None:
            # Serialised now, so a later change to a mutable field cannot alter what reaches the file.
            self._pending.append(json.dumps(line, separators=(",", ":")) + "\n")

    def _flush(self) -> None:
        # One open per public call instead of one per line: a tick writes about 15 lines, and on
        # some filesystems opening the file costs far more than writing to it.
        if self._pending and self._log_path is not None:
            with self._log_path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write("".join(self._pending))
        self._pending.clear()

    def _emit(self, event: str, **fields: object) -> None:
        self._write({"src": "sim", "event": event, **fields})

    # --- steps 1-3: start of tick --------------------------------------------------------------

    def _begin_tick(self) -> None:
        self._step1_staff()
        self._step2_events()
        self._step3_arrivals()

    def _step1_staff(self) -> None:
        t = self.tick
        for s in self.state.staff:
            if s.agency and s.status not in ("agency_ordered", "agency_left") and s.leave_tick == t:
                s.status, s.location = "agency_left", "rest"
        for s in self.state.staff:
            if s.status in ("fainted", "sick") and s.return_tick == t:
                s.status, s.location, s.return_tick = "resting", "rest", None
            elif s.status == "agency_ordered" and s.arrive_tick == t:
                s.status, s.arrive_tick = "resting", None

    def _step2_events(self) -> None:
        t, state = self.tick, self.state
        for ev in self.world.events:
            end = ev.start_tick + ev.duration
            if ev.start_tick == t:
                self._emit("event_start", kind=ev.kind, ends_tick=end)
                if ev.kind == "ct_breakdown":
                    state.ct_return_tick = (
                        end if state.ct_return_tick is None else min(state.ct_return_tick, end)
                    )
                elif ev.kind == "staff_sickness":
                    self._make_sick(ev.staff, end)
            if end == t and ev.kind != "ct_breakdown":
                self._emit("event_end", kind=ev.kind)
        if state.ct_return_tick == t:
            state.ct_return_tick = None
            self._emit("event_end", kind="ct_breakdown")

    def _make_sick(self, staff_ids: tuple[str, ...], back_tick: int) -> None:
        for staff_id in staff_ids:
            s = self.state.find_staff(staff_id)
            if s is not None and s.status != "agency_left":
                s.status, s.location, s.return_tick = "sick", "rest", back_tick

    def _step3_arrivals(self) -> None:
        t, state = self.tick, self.state
        for spec in self._arrivals.get(t, []):
            patient = PatientState(spec, esi=spec.esi, needs_ct=spec.needs_ct)
            state.patients[spec.id] = patient
            if t <= state.divert_last and spec.divert_u < c.DIVERT_SHARE:
                patient.status = "diverted"
                state.totals["diverted"] += 1
                self._emit("diverted", patient=spec.id, esi=spec.esi)
            else:
                self._emit(
                    "arrival", patient=spec.id, esi=spec.esi, needs_ct=spec.needs_ct, source=spec.source
                )

    # --- step 6: coverage, treatment, discharge -----------------------------------------------

    def _step6_treat(self) -> None:
        state = self.state
        for p in state.patients.values():
            p.covered_now = False
        ct_ok = state.ct_working
        for pid in state.covered_ids():
            p = state.patients[pid]
            p.covered_now = True
            if not p.ever_covered:
                p.ever_covered = True
                self._emit("covered", patient=pid)
            if p.needs_ct and not p.scanned and p.treated == (p.needed + 1) // 2:
                if not ct_ok:
                    continue  # stalled at the scanner
                p.scanned = True
            p.treated += 1
            if p.treated >= p.needed:
                self._leave_bed(p, "discharged")
                state.totals["discharged"] += 1
                self._emit("discharged", patient=pid)
        on_shift = [s for s in state.staff if s.status == "on_shift"]
        self._emit("staff_fatigue", on_shift_above_60=sum(s.tired for s in on_shift), on_shift=len(on_shift))

    def _leave_bed(self, p: PatientState, status: str) -> None:
        self.state.beds[p.bed] = None
        p.status = status

    # --- step 7: hazards ------------------------------------------------------------------------

    def _step7_hazards(self) -> None:
        for p in self.state.patients.values():
            if p.status == "waiting":
                self._waiting_hazard(p)
            elif p.status == "bed":
                self._bed_hazard(p)

    def _die(self, p: PatientState, cause: str) -> None:
        if p.status == "bed":
            self._leave_bed(p, "died")
        else:
            p.status = "died"
        self.state.totals["deaths"] += 1
        self._emit("death", patient=p.spec.id, cause=cause)

    def _waiting_hazard(self, p: PatientState) -> None:
        u = p.spec.hazard_u[self.tick]
        waited = self.tick - p.spec.arrival_tick
        if p.esi == 1:
            if u < c.P_DEATH_ESI1_WAITING:
                self._die(p, "waiting")
        elif p.esi == 2:
            if waited > c.ESI2_WAIT_GRACE and u < c.P_DEATH_ESI2_WAITING:
                self._die(p, "waiting")
        elif p.esi == 3:
            if waited > c.ESI3_WAIT_GRACE and u < c.P_UPGRADE_ESI3:
                p.esi = 2
                p.needs_ct = p.spec.upgrade_ct_u < c.CT_SHARE
                self._emit("upgrade", patient=p.spec.id, esi=2, needs_ct=p.needs_ct)
        elif waited > c.ESI45_WAIT_GRACE and u < c.P_LEAVE_ESI45:
            p.status = "left"
            self.state.totals["left"] += 1
            self._emit("left", patient=p.spec.id)

    def _bed_hazard(self, p: PatientState) -> None:
        if p.esi not in c.P_DEATH_UNCOVERED:
            return
        u = p.spec.hazard_u[self.tick]
        if not p.covered_now:
            if u < c.P_DEATH_UNCOVERED[p.esi]:
                self._die(p, "uncovered_bed")
        elif self.state.zone_tired(p.zone) and u < c.P_DEATH_FATIGUE:
            self._die(p, "fatigue")

    # --- step 8: fatigue --------------------------------------------------------------------------

    def _step8_fatigue(self) -> None:
        for s in self.state.staff:
            if s.status == "on_shift":
                s.fatigue10 += GAIN10[s.location]
            elif s.status in ("resting", "fainted"):
                s.fatigue10 = max(0, s.fatigue10 - REST10)
        for s in self.state.staff:
            if s.status == "on_shift" and s.fatigue10 >= FAINT10:
                s.status, s.location = "fainted", "rest"
                s.return_tick = self.tick + c.FAINT_TICKS + 1
                self.state.totals["faints"] += 1
                self._emit("faint", staff=s.id)
