"""End of episode with the real engine, scorer and collect.py: no fakes (issue #15)."""

import json
from pathlib import Path

import collect
from ed72_sim import constants as c
from ed72_sim.engine import Simulation
from ed72_sim.model import World
from ed72_sim.scoring.score import score
from ed72_sim.world import generate_world
from sim_fixtures import admit, crew, make_world, patient

REFUSED = {"error": "call_cap_reached"}


def run(world: World, plan: dict[int, list[dict]], steps: int, log_path: Path | None = None) -> Simulation:
    """Make `steps` step calls (actions from `plan` by tick), then let the episode resolve itself."""
    sim = Simulation(world, log_path)
    for t in range(steps):
        sim.step(plan.get(t, []))
    sim.run_to_end()
    return sim


def row(report: dict, pid: str) -> dict:
    return next(p for p in report["patients"] if p["id"] == pid)


def loss(report: dict, pid: str) -> float:
    """Recover one patient's loss from O when it is the only patient."""
    assert report["totals"]["arrived"] == 1
    return round(1 - report["O"], 6)


def lone(outcome_plan: dict[int, list[dict]], steps: int = c.TICKS, esi: int = 3, tick: int = 0) -> dict:
    return score(run(make_world([patient(1, tick, esi)]), outcome_plan, steps).events)


def test_agent_stops_after_tick_12_and_the_rest_resolves_with_staff_left_in_place() -> None:
    world = make_world([patient(1, 10, 3), patient(2, 50, 3)])
    plan = {10: crew("acute", 1, 1) + [admit("P001", "acute")]}
    sim = run(world, plan, 12)
    report = score(sim.events)

    assert sim.events[-1]["event"] == "episode_end" and sim.events[-1]["t"] == c.TICKS - 1
    assert sum(1 for e in sim.events if e["src"] == "agent") == 12
    done = next(e for e in sim.events if e.get("event") == "discharged")
    assert done["patient"] == "P001" and done["t"] > 11  # finished after the agent stopped

    assert row(report, "P001")["outcome"] == "discharged" and row(report, "P001")["on_time"] is True
    assert row(report, "P002")["outcome"] == "never_admitted" and row(report, "P002")["on_time"] is False
    # weights 2 and 2: one patient lost entirely
    assert report["O"] == 0.5 and report["T"] == 0.5
    assert report["ended"] == "agent_stopped"
    assert report["tool_calls"] == 12 and report["ticks_with_actions"] == 1
    assert report["failures"]["F10"] == c.TICKS - 1 - 11


def test_call_cap_refuses_actions_and_collect_replay_matches_live(tmp_path: Path) -> None:
    log = tmp_path / "events.jsonl"
    seed = 5
    sim = Simulation(generate_world(seed), log)
    for t in range(20):
        sim.step(crew("acute", 2, 3) if t == 0 else [])
    waiting = sim.observe()["waiting"]
    target = next(p["id"] for p in waiting if p["esi"] >= 3)
    refused = [admit(target, "acute")]
    sim.record_call("step", {"actions": refused}, REFUSED)
    sim.run_to_end()
    live = score(sim.events)

    assert live["ended"] == "call_cap"
    assert live["tool_calls"] == 21  # the refused call counts as a call
    assert row(live, target)["admitted_tick"] is None  # the refused admit never ran
    assert not any(e.get("event") == "admitted" and e["patient"] == target for e in sim.events)

    out = tmp_path / "report.json"
    replayed = collect.collect(seed, log, out)
    assert json.loads(out.read_text(encoding="utf-8")) == replayed
    assert replayed == live


def test_collect_replay_keeps_call_cap_and_tool_calls(tmp_path: Path) -> None:
    log = tmp_path / "events.jsonl"
    sim = Simulation(generate_world(5), log)
    for t in range(20):
        sim.step([])
    sim.record_call("observe", {}, {"ok": True})
    sim.record_call("step", {"actions": []}, REFUSED)
    sim.run_to_end()
    live = score(sim.events)
    assert live["ended"] == "call_cap" and live["tool_calls"] == 22
    assert collect.collect(5, log, tmp_path / "report.json") == live


def test_in_bed_at_end_never_covered_costs_the_same_as_never_admitted() -> None:
    in_bed = lone({0: [admit("P001", "acute")]})
    p = row(in_bed, "P001")
    assert p["outcome"] == "in_bed_end" and p["first_covered_tick"] is None and p["on_time"] is False
    assert p["admitted_tick"] == 0
    assert loss(in_bed, "P001") == c.LOSS_FAILED == 1.0

    never = lone({})
    assert row(never, "P001")["outcome"] == "never_admitted"
    assert in_bed["O"] == never["O"] == 0.0


def test_in_bed_at_end_covered_once_costs_0_3() -> None:
    # Staff cover the bed at tick 0, then everybody is sent to rest so treatment stalls.
    # ESI 4 needs 2 ticks; covered on tick 0 only, then the crew leaves.
    leave = [{"type": "assign", "staff": "D1", "to": "rest"}, {"type": "assign", "staff": "N1", "to": "rest"}]
    plan = {0: crew("acute", 1, 1) + [admit("P001", "acute")], 1: leave}
    report = lone(plan, esi=4)
    p = row(report, "P001")
    assert p["outcome"] == "in_bed_end" and p["first_covered_tick"] == 0 and p["on_time"] is True
    assert loss(report, "P001") == c.LOSS_IN_BED_COVERED == 0.3


def test_diverted_patient_loses_0_7_and_is_late() -> None:
    world = make_world([patient(1, 1, 3, divert_u=0.0)])
    report = score(run(world, {0: [{"type": "divert"}]}, c.TICKS).events)
    p = row(report, "P001")
    assert p["outcome"] == "diverted" and p["on_time"] is False
    assert loss(report, "P001") == c.LOSS_DIVERTED == 0.75
    assert report["T"] == 0.0 and report["totals"]["diverted"] == 1


def test_filling_beds_on_the_last_tick_with_nobody_on_shift_earns_nothing() -> None:
    queue = [patient(n, 130 + n, esi) for n, esi in enumerate([3, 4, 5, 4, 5, 3], start=1)]
    plan = {c.TICKS - 1: [admit(p.id, "acute") for p in queue]}
    report = score(run(make_world(queue), plan, c.TICKS).events)

    assert report["ended"] == "tick_143"
    for p in queue:
        r = row(report, p.id)
        assert r["outcome"] == "in_bed_end" and r["admitted_tick"] == c.TICKS - 1
        assert r["first_covered_tick"] is None and r["on_time"] is False
    assert report["O"] == 0.0 and report["T"] == 0.0


def scripted(sim: Simulation, t: int) -> list[dict]:
    """Crew acute and resus on tick 0, then admit what is waiting to the first allowed zone."""
    actions = crew("acute", 3, 5) if t == 0 else []
    for p in sim.observe()["waiting"]:
        zone = "resus" if p["esi"] <= 2 else "acute"
        actions.append(admit(p["id"], zone))
    return actions


def test_collect_round_trip_matches_live_run_after_scripted_policy_stops(tmp_path: Path) -> None:
    log = tmp_path / "events.jsonl"
    sim = Simulation(generate_world(3), log)
    for t in range(40):
        sim.step(scripted(sim, t))
    sim.run_to_end()
    live = score(sim.events)

    report = collect.collect(3, log, tmp_path / "report.json")
    assert report == live
    assert report["ended"] == "agent_stopped"
    assert report["tool_calls"] == 40
    assert report["failures"]["F10"] == c.TICKS - 1 - 39
    assert report["totals"]["discharged"] > 0
