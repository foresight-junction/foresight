"""Issue #9 extra events: off by default, each announced and reusing an existing mechanic."""

import dataclasses
import json
from pathlib import Path

import pytest
from ed72_sim import constants as c
from ed72_sim.config import Config, load_config
from ed72_sim.engine import Simulation
from ed72_sim.model import EventSpec
from ed72_sim.rules.events_extra import EXTRA_EVENTS
from ed72_sim.world import generate_world
from sim_fixtures import admit, advance, bed, crew, lines, make_world, patient, staff

DEFAULT_JSON = Path(__file__).resolve().parents[1] / "config" / "default.json"


def enabled(tmp_path: Path, *kinds: str) -> Config:
    path = tmp_path / "cfg.json"
    path.write_text(json.dumps({"events": {k: {"enabled": True} for k in kinds}}), encoding="utf-8")
    return load_config(str(path))


def episode(config: Config | None, seed: int) -> list[dict]:
    """A full episode with a simple active policy, so admissions, coverage and hazards all run."""
    sim = Simulation(generate_world(seed, config))
    sim.step(crew("resus", 2, 3))
    while not sim.finished:
        waiting = sim.observe()["waiting"]
        sim.step([admit(p["id"], "resus" if p["esi"] == 1 else "acute") for p in waiting])
    return sim.events


def test_extras_are_off_by_default() -> None:
    config = load_config(str(DEFAULT_JSON))
    assert all(config.events[k]["enabled"] is False for k in EXTRA_EVENTS)
    assert config.layout == "default"
    for seed in range(1, 6):
        assert [e.kind for e in generate_world(seed, config).events] == list(c.EVENTS)


@pytest.mark.parametrize("seed", range(1, 4))
def test_default_log_is_byte_identical_to_the_core_game(seed: int) -> None:
    world = generate_world(seed, load_config(str(DEFAULT_JSON)))
    core = dataclasses.replace(world, events=tuple(e for e in world.events if e.kind in c.EVENTS))
    assert world == core
    assert world.bed_counts == tuple(c.BEDS[z] for z in c.ZONES)
    assert json.dumps(episode(load_config(str(DEFAULT_JSON)), seed)) == json.dumps(episode(None, seed))


@pytest.mark.parametrize("seed", range(1, 4))
def test_enabling_extras_keeps_core_events_and_is_deterministic(tmp_path: Path, seed: int) -> None:
    config = enabled(tmp_path, *EXTRA_EVENTS)
    world = generate_world(seed, config)
    assert world.events[: len(c.EVENTS)] == generate_world(seed).events
    extras = world.events[len(c.EVENTS) :]
    assert [e.kind for e in extras] == list(EXTRA_EVENTS)
    for e in extras:
        lo, hi = EXTRA_EVENTS[e.kind]["window"]
        assert lo <= e.start_tick <= hi
    assert json.dumps(episode(config, seed)) == json.dumps(episode(config, seed))


def test_one_extra_does_not_move_another(tmp_path: Path) -> None:
    alone = {e.kind: e for e in generate_world(3, enabled(tmp_path, "doctor_sickness")).events}
    both = {e.kind: e for e in generate_world(3, enabled(tmp_path, *EXTRA_EVENTS)).events}
    assert alone["doctor_sickness"] == both["doctor_sickness"]


@pytest.mark.parametrize("kind", list(EXTRA_EVENTS))
def test_warning_shows_exact_start_until_the_event_ends(kind: str) -> None:
    spec = EXTRA_EVENTS[kind]
    sick = ("D2",) if kind == "doctor_sickness" else ()
    sim = Simulation(make_world(events=[EventSpec(kind, 20, spec["duration"], spec["warning"], sick)]))
    warned = []
    while sim.tick < 20 + spec["duration"] + 2:
        warnings = sim.observe()["warnings"]
        if warnings:
            assert warnings == [{"event": kind, "start_tick": 20}]
            warned.append(sim.tick)
        sim.step([])
    assert warned == list(range(20 - spec["warning"], 20 + spec["duration"]))
    assert [e["t"] for e in lines(sim, "event_start", kind=kind)] == [20]
    assert [e["t"] for e in lines(sim, "event_end", kind=kind)] == [20 + spec["duration"]]


def test_doctor_sickness_takes_the_doctor_off_shift_until_it_ends() -> None:
    sim = Simulation(make_world(events=[EventSpec("doctor_sickness", 5, 12, 4, ("D1",))]))
    advance(sim, 5, crew("acute", 1, 0))
    assert (staff(sim, "D1")["status"], staff(sim, "D1")["location"]) == ("sick", "rest")
    assert staff(sim, "D1")["ticks_until_change"] == 12
    advance(sim, 12)
    assert staff(sim, "D1")["status"] == "resting"


def test_second_mci_adds_bus_patients_in_its_window(tmp_path: Path) -> None:
    world = generate_world(4, enabled(tmp_path, "second_mci"))
    mci = next(e for e in world.events if e.kind == "second_mci")
    bus = next(e for e in world.events if e.kind == "bus_crash")
    late = [p for p in world.patients if p.source == "bus" and p.arrival_tick >= mci.start_tick]
    assert len(late) == c.BUS_EXTRA_PER_TICK * mci.duration
    assert {p.arrival_tick for p in late} == set(range(mci.start_tick, mci.start_tick + mci.duration))
    assert {p.esi for p in late} <= {1, 2, 3}
    early = [p for p in world.patients if p.source == "bus" and p.arrival_tick < mci.start_tick]
    assert {p.arrival_tick for p in early} == set(range(bus.start_tick, bus.start_tick + bus.duration))


def test_monitor_fault_closes_r3_to_new_patients_but_keeps_its_patient() -> None:
    first = [patient(n, tick=0, esi=1) for n in (1, 2, 3)]
    later = [patient(n, tick=6, esi=1) for n in (4, 5, 6)]
    sim = Simulation(make_world(first + later, events=[EventSpec("monitor_fault", 2, 6, 3)]))
    sim.step(crew("resus", 3, 3) + [admit(f"P00{n}", "resus") for n in (1, 2, 3)])
    advance(sim, 2)  # tick 3: fault active since tick 2
    assert bed(sim, "R3")["patient"] == "P003" and bed(sim, "R3")["covered"]
    assert bed(sim, "R3")["treated_ticks"] == 3
    advance(sim, 3)  # tick 6: P001-P003 finished at tick 5; P004-P006 arrive
    results = sim.step([admit(f"P00{n}", "resus") for n in (4, 5, 6)])["results"]
    assert [r["ok"] for r in results] == [True, True, False]
    assert results[2]["reason"] == "no_free_bed"
    assert bed(sim, "R3")["patient"] is None
    advance(sim, 1)  # tick 8: the fault ends in step 2
    assert sim.step([admit("P006", "resus")])["results"][0]["ok"]
    assert bed(sim, "R3")["patient"] == "P006"


BAD = [
    {"events": {"doctor_sickness": {"enabled": 1}}},
    {"events": {"flu_wave": {"enabled": True}}},
    {"events": {"second_mci": {"window": [130, 150]}}},
    {"events": {"monitor_fault": {"beds": 2}}},
]


@pytest.mark.parametrize("bad", BAD, ids=[json.dumps(b) for b in BAD])
def test_invalid_extra_config_raises(tmp_path: Path, bad: object) -> None:
    path = tmp_path / "cfg.json"
    path.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(ValueError):
        load_config(str(path))
