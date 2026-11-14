"""Whole-run engine tests: reproducibility, arrivals, surges, time progression, the
hidden-information firewall, and that management quality changes outcomes."""

from __future__ import annotations

import json
import time
from collections import Counter

import pytest

from app.edsim import CONFIGS, EDError, Simulation
from app.edsim import config as C
from app.edsim.generator import build_scenario, expected_roster_cost
from tests.edsim_support import simple_policy

HIDDEN_KEYS = {
    "duration",
    "complication_factor",
    "thresholds",
    "threshold_index",
    "hazard",
    "untreated_min",
    "patience_z",
    "admit_draw",
    "vent_draw",
    "imaging_minutes",
    "triage_minutes",
    "care_risk",
    "repair_at",
    "ends_min",
    "seed",
    "initial_acuity",
    "work_done",
}


def _keys(value) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {k for v in value.values() for k in _keys(v)}
    if isinstance(value, list):
        return {k for v in value for k in _keys(v)}
    return set()


def _fingerprint(sim: Simulation) -> str:
    return json.dumps({"truth": sim.truth(), "log": sim.state.log}, sort_keys=True, default=str)


# --- reproducibility ------------------------------------------------------------------------
def test_same_seed_and_same_actions_give_identical_runs():
    runs = []
    for _ in range(2):
        sim = Simulation("standard", 11, horizon_hours=24)
        simple_policy(sim)
        runs.append(_fingerprint(sim))
    assert runs[0] == runs[1]


def test_do_nothing_runs_are_identical_and_seeds_differ():
    a, b, c = Simulation("standard", 5), Simulation("standard", 5), Simulation("standard", 6)
    for sim in (a, b, c):
        sim.run_to_end()
    assert _fingerprint(a) == _fingerprint(b)
    assert _fingerprint(a) != _fingerprint(c)


def test_agent_actions_never_change_the_exogenous_scenario():
    """Common random numbers: arrivals and patient attributes do not depend on decisions."""
    idle = Simulation("standard", 21, horizon_hours=24)
    idle.run_to_end()
    managed = Simulation("standard", 21, horizon_hours=24)
    simple_policy(managed)

    def arrivals(sim):
        return [
            (p["patient_id"], p["arrival_min"], p["complaint"], p["initial_acuity"])
            for p in sim.truth()["patients"]
        ]

    assert arrivals(idle) == arrivals(managed)
    assert [e.minute for e in idle.scenario.events] == [e.minute for e in managed.scenario.events]


# --- arrival generation ------------------------------------------------------------------------
@pytest.mark.parametrize("seed", [1, 2, 3, 4, 5])
def test_arrivals_are_plausible_sorted_and_within_horizon(seed):
    scenario = build_scenario(CONFIGS["standard"], seed)
    minutes = [p.arrival_min for p in scenario.patients]
    assert 150 <= len(minutes) <= 280
    assert minutes == sorted(minutes)
    assert all(0 <= m < C.HORIZON_MINUTES for m in minutes)
    assert len({p.patient_id for p in scenario.patients}) == len(minutes)


def test_arrivals_follow_the_day_night_curve():
    by_hour: Counter[int] = Counter()
    for seed in range(1, 9):
        for p in build_scenario(CONFIGS["standard"], seed).patients:
            if p.incident_id is None:
                by_hour[C.hour_of_day(p.arrival_min)] += 1
    daytime = sum(by_hour[h] for h in range(11, 20))
    night = sum(by_hour[h] for h in range(1, 7))
    assert daytime / 9 > 2 * (night / 6)


def test_acuity_mix_and_ambulance_share_are_plausible():
    patients = [p for seed in range(1, 6) for p in build_scenario(CONFIGS["standard"], seed).patients]
    acuity = Counter(p.initial_acuity for p in patients)
    assert acuity[3] + acuity[4] > acuity[1] + acuity[2]
    ambulance = [p for p in patients if p.mode == "ambulance"]
    walk_in = [p for p in patients if p.mode == "walk_in"]
    urgent_ambulance = sum(1 for p in ambulance if p.initial_acuity <= 2) / len(ambulance)
    urgent_walk_in = sum(1 for p in walk_in if p.initial_acuity <= 2) / len(walk_in)
    assert urgent_ambulance > urgent_walk_in


def test_difficulties_scale_demand_and_all_run():
    counts = {name: len(build_scenario(cfg, 3).patients) for name, cfg in CONFIGS.items()}
    assert counts["easy"] < counts["standard"] < counts["hard"]
    for name in CONFIGS:
        sim = Simulation(name, 3, horizon_hours=6)
        sim.run_to_end()
        assert sim.finished


def test_roster_cost_fits_inside_every_budget():
    for cfg in CONFIGS.values():
        assert expected_roster_cost(cfg) < 0.6 * cfg.budget


# --- surges and events ---------------------------------------------------------------------------
def _seed_with(kind: str):
    for seed in range(1, 50):
        scenario = build_scenario(CONFIGS["standard"], seed)
        for event in scenario.events:
            if event.kind == kind:
                return seed, event
    raise AssertionError(f"no seed with {kind}")


def test_major_incident_alert_precedes_a_burst_of_field_triaged_ambulances():
    seed, event = _seed_with("major_incident")
    sim = Simulation("standard", seed)
    casualties = [p for p in sim.scenario.patients if p.incident_id == event.event_id]
    assert len(casualties) == event.params["size"]
    assert all(p.mode == "ambulance" for p in casualties)
    first = min(p.arrival_min for p in casualties)
    assert first >= event.minute + 15
    assert max(p.arrival_min for p in casualties) <= first + event.params["spread"]
    while sim.state.minute < event.minute:
        sim.advance_time(min(120, event.minute - sim.state.minute))
    assert any(e["event_id"] == event.event_id for e in sim.active_events()["events"])
    visible = {p["patient_id"] for p in sim.list_patients()["patients"]}
    assert not visible & {p.patient_id for p in casualties}
    while sim.state.minute <= first:
        sim.advance_time(1)
    arrived = [p for p in casualties if p.patient_id in sim.state.patients]
    assert arrived and all(p.triaged for p in arrived)


def test_every_event_kind_occurs_across_seeds_and_changes_state():
    kinds: Counter[str] = Counter()
    for seed in range(1, 11):
        kinds.update(e.kind for e in build_scenario(CONFIGS["standard"], seed).events)
    assert set(kinds) == {
        "major_incident",
        "demand_spike",
        "staff_sickness",
        "equipment_failure",
        "bed_closure",
        "supply_shortage",
        "budget_cut",
    }
    seed, failure = _seed_with("equipment_failure")
    sim = Simulation("standard", seed)
    while sim.state.minute <= failure.minute:
        sim.advance_time(min(120, failure.minute + 1 - sim.state.minute))
    assert sim.state.equipment[failure.params["equipment_id"]].failed


def test_demand_spike_raises_arrivals_in_its_window():
    inside = before = 0
    for seed in range(1, 21):
        scenario = build_scenario(CONFIGS["standard"], seed)
        for event in (e for e in scenario.events if e.kind == "demand_spike"):
            start, end = event.minute, event.minute + event.params["duration"]
            regular = [p.arrival_min for p in scenario.patients if not p.incident_id]
            inside += sum(1 for m in regular if start <= m < end)
            before += sum(1 for m in regular if start - (end - start) <= m < start)
    assert inside > 1.2 * before


# --- time progression ------------------------------------------------------------------------------
def test_full_run_reaches_exactly_72_hours_and_then_rejects_actions():
    sim = Simulation("standard", 2)
    started = time.perf_counter()
    sim.run_to_end()
    assert time.perf_counter() - started < 5.0
    assert sim.state.minute == C.HORIZON_MINUTES and sim.finished
    assert sim.department_status()["clock"]["time"] == "Day 4 07:00"
    with pytest.raises(EDError) as err:
        sim.advance_time(10)
    assert err.value.code == "EPISODE_FINISHED"
    with pytest.raises(EDError) as err:
        sim.act("set_diversion", active=True)
    assert err.value.code == "EPISODE_FINISHED"


def test_advance_is_truncated_at_the_horizon():
    sim = Simulation("standard", 2, horizon_hours=1)
    sim.advance_time(50)
    result = sim.advance_time(120)
    assert result["minutes_advanced"] == 10 and sim.finished


def test_all_generated_patients_arrive_and_are_accounted_for():
    sim = Simulation("standard", 4)
    simple_policy(sim, step=15)
    truth = sim.truth()
    assert len(truth["patients"]) == len(sim.scenario.patients)


# --- hidden-information firewall ---------------------------------------------------------------------
def test_agent_views_never_expose_hidden_state_or_the_future():
    seed, _ = _seed_with("major_incident")
    sim = Simulation("standard", seed, horizon_hours=24)
    seen_keys: set[str] = set()
    while not sim.finished:
        simple_policy(sim, step=30, until=min(sim.state.horizon, sim.state.minute + 120))
        views = [
            sim.department_status(),
            sim.list_patients(),
            sim.staff_status(include_off_duty=True),
            sim.resource_status(),
            sim.budget_status(),
            sim.active_events(),
            sim.metrics(),
            sim.recent_log(),
        ]
        rows = sim.list_patients()["patients"]
        views += [sim.patient(r["patient_id"]) for r in rows]
        for view in views:
            seen_keys |= _keys(view)
        for row in rows:
            patient = sim.state.patients[row["patient_id"]]
            assert patient.arrival_min <= sim.state.minute
            if not patient.triaged:
                assert row["acuity"] is None and "requirements" not in sim.patient(row["patient_id"])
            if patient.status not in ("ready", "boarding"):
                assert "disposition" not in row
    assert not seen_keys & HIDDEN_KEYS
    agent_kinds = {e["kind"] for e in sim.recent_log(limit=100_000)["entries"]}
    assert not agent_kinds & {"episode_started", "episode_finished", "event_skipped"}


# --- management quality matters ---------------------------------------------------------------------
@pytest.mark.parametrize("seed", [1, 2])
def test_managing_the_department_beats_doing_nothing(seed):
    idle = Simulation("standard", seed)
    idle.run_to_end()
    managed = Simulation("standard", seed)
    simple_policy(managed)
    idle_outcomes = Counter(p["status"] for p in idle.truth()["patients"])
    managed_outcomes = Counter(p["status"] for p in managed.truth()["patients"])
    assert managed_outcomes["critical_event"] < idle_outcomes["critical_event"] / 3
    assert managed_outcomes["lwbs"] < idle_outcomes["lwbs"] / 10
    completed = managed_outcomes["discharged"] + managed_outcomes["admitted"]
    assert completed > 0.7 * len(managed.scenario.patients)
