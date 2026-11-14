import copy
import json
from collections import Counter
from pathlib import Path

from ed72_sim import constants as c
from ed72_sim.engine import Simulation
from ed72_sim.model import PatientSpec, World
from ed72_sim.rng import stream, weighted_choice
from sim_fixtures import advance, lines, make_world, patient


def test_do_nothing_run_ends_with_episode_end_and_then_refuses() -> None:
    sim = Simulation(make_world([patient(1, 0, 4), patient(2, 100, 1)]))
    assert sim.events[0] == {
        "seq": 0,
        "t": 0,
        "src": "sim",
        "event": "episode_start",
        "budget": 12_000,
        "hard_limit": 24_000,
    }
    sim.run_to_end()
    assert sim.finished and sim.tick == c.TICKS - 1
    assert sim.events[-1]["event"] == "episode_end" and sim.events[-1]["t"] == 143
    assert not any(e["src"] == "agent" for e in sim.events)
    assert [e["seq"] for e in sim.events] == list(range(len(sim.events)))
    assert len(lines(sim, "staff_fatigue")) == c.TICKS
    obs = sim.observe()
    assert obs["finished"] is True and obs["ticks_left"] == 0
    before = len(sim.events)
    assert sim.step([{"type": "divert"}]) == {"error": "episode_over"}
    assert len(sim.events) == before and sim.observe() == obs


def test_step_line_carries_actions_and_results() -> None:
    sim = Simulation(make_world([patient(1, 0, 3)]))
    actions = [{"type": "admit", "patient": "P001", "zone": "acute"}, {"type": "repair"}]
    sim.step(actions)
    line = next(e for e in sim.events if e["src"] == "agent")
    assert line["tool"] == "step" and line["t"] == 0 and line["args"] == {"actions": actions}
    assert line["result"] == {
        "results": [{"index": 0, "ok": True}, {"index": 1, "ok": False, "reason": "ct_not_broken"}]
    }
    admitted = next(e for e in sim.events if e.get("event") == "admitted")
    assert admitted["seq"] < line["seq"]


def test_log_file_matches_events_and_is_byte_identical(tmp_path: Path) -> None:
    world = make_world([patient(1, 0, 3), patient(2, 5, 1, hazard_at={5: 0.01})])
    script = {
        0: [{"type": "admit", "patient": "P001", "zone": "acute"}],
        3: [{"type": "agency", "role": "nurse"}],
    }
    paths = []
    for name in ("a.jsonl", "b.jsonl"):
        path = tmp_path / name
        sim = Simulation(world, log_path=path)
        while not sim.finished:
            sim.step(script.get(sim.tick, []))
        assert [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()] == sim.events
        paths.append(path)
    assert paths[0].read_bytes() == paths[1].read_bytes()


def _random_world(n: int = 150, seed: int = 7) -> World:
    patients = []
    for i in range(n):
        rng = stream(seed, f"patient:P{i + 1:03d}")
        esi = weighted_choice(rng, c.ARRIVAL_MIX)
        needs_ct = esi in c.CT_ESI and rng.random() < c.CT_SHARE
        divert_u, upgrade_u = rng.random(), rng.random()
        hazard = tuple(rng.random() for _ in range(c.TICKS))
        patients.append(
            PatientSpec(f"P{i + 1:03d}", i * c.TICKS // n, esi, needs_ct, "base", divert_u, upgrade_u, hazard)
        )
    return make_world(patients)


PREFERRED = {
    1: ("resus",),
    2: ("resus", "acute"),
    3: ("acute", "fast_track", "resus"),
    4: ("fast_track", "acute"),
    5: ("fast_track", "acute"),
}


def _busy_policy(obs: dict) -> list[dict]:
    actions: list[dict] = []
    if obs["tick"] == 0:
        layout = {
            "resus": ("D1", "N1"),
            "acute": ("D2", "D3", "N2", "N3", "N4"),
            "fast_track": ("D4", "N5", "N6"),
        }
        actions += [{"type": "assign", "staff": s, "to": z} for z, ids in layout.items() for s in ids]
    if obs["tick"] in (10, 40):
        actions.append({"type": "agency", "role": "nurse"})
    if obs["tick"] in (20, 60):
        actions.append({"type": "divert"})
    if not obs["ct"]["working"]:
        actions.append({"type": "repair"})
    free = [b for b in obs["beds"] if b["patient"] is None]
    for w in sorted(obs["waiting"], key=lambda w: (w["esi"], w["arrived_tick"])):
        for zone in PREFERRED[w["esi"]]:
            spot = next((b for b in free if b["zone"] == zone), None)
            if spot:
                free.remove(spot)
                actions.append({"type": "admit", "patient": w["id"], "zone": zone})
                break
    return actions


def _arrival_multiset(sim: Simulation, world: World) -> Counter:
    specs = {p.id: p for p in world.patients}
    out = Counter()
    for e in sim.events:
        if e.get("event") in ("arrival", "diverted"):
            out[(e["patient"], e["esi"], specs[e["patient"]].needs_ct, e["t"])] += 1
    return out


def test_common_random_numbers_arrivals_do_not_depend_on_actions() -> None:
    world = _random_world()
    frozen = copy.deepcopy(world)
    idle = Simulation(world)
    idle.run_to_end()
    busy = Simulation(world)
    while not busy.finished:
        busy.step(_busy_policy(busy.observe()))
    assert world == frozen  # the sim never mutates or re-rolls the world
    expected = Counter((p.id, p.esi, p.needs_ct, p.arrival_tick) for p in world.patients)
    assert _arrival_multiset(idle, world) == expected == _arrival_multiset(busy, world)
    # the busy run really behaved differently, so the equality above is not vacuous
    assert lines(busy, "diverted") and not lines(idle, "diverted")
    assert lines(busy, "discharged") and not lines(idle, "discharged")
    # a patient who dies waiting in both runs dies on the same tick: luck belongs to the patient
    idle_deaths = {e["patient"]: e["t"] for e in lines(idle, "death", cause="waiting")}
    busy_deaths = {e["patient"]: e["t"] for e in lines(busy, "death", cause="waiting")}
    shared = [pid for pid in idle_deaths if pid in busy_deaths and world.patients[int(pid[1:]) - 1].esi <= 2]
    assert shared and all(idle_deaths[pid] == busy_deaths[pid] for pid in shared)


def test_same_world_and_actions_give_the_same_log() -> None:
    world = _random_world(60, seed=3)
    logs = []
    for _ in range(2):
        sim = Simulation(world)
        while not sim.finished:
            sim.step(_busy_policy(sim.observe()))
        logs.append(sim.events)
    assert logs[0] == logs[1]
    advance(Simulation(world), 1)  # smoke: a fresh sim from the same world is still usable


def test_record_call_logs_an_agent_line_without_advancing() -> None:
    sim = Simulation(make_world([patient(1, 0, 3)]))
    before = sim.observe()
    sim.record_call("step", {"actions": []}, {"error": "call_cap_reached"})
    assert sim.events[-1] == {
        "seq": len(sim.events) - 1,
        "t": 0,
        "src": "agent",
        "tool": "step",
        "args": {"actions": []},
        "result": {"error": "call_cap_reached"},
    }
    assert sim.tick == 0 and sim.observe() == before


def test_run_to_end_after_an_agent_stops_writes_no_agent_lines() -> None:
    sim = Simulation(make_world([patient(1, 0, 3)]))
    for _ in range(5):
        sim.step([])
    sim.run_to_end()
    agent_ticks = [e["t"] for e in sim.events if e["src"] == "agent"]
    assert agent_ticks == [0, 1, 2, 3, 4]
    assert sim.finished and sim.events[-1]["event"] == "episode_end"
