"""Rulebook §7 (events and warnings) and §5 (sick staff), seen through the sim's public surface."""

import pytest
from ed72_sim import constants as c
from ed72_sim.engine import Simulation
from ed72_sim.model import EventSpec
from sim_fixtures import admit, advance, bed, crew, lines, make_world, patient, staff


def _warnings_by_tick(sim: Simulation, until: int) -> dict[int, list[dict]]:
    seen = {}
    while sim.tick < until:
        seen[sim.tick] = sim.observe()["warnings"]
        sim.step([])
    return seen


def test_event_table_matches_the_rulebook() -> None:
    assert {k: (v["window"], v["duration"], v["warning"]) for k, v in c.EVENTS.items()} == {
        "staff_sickness": ((28, 35), 20, 0),
        "flu_wave": ((50, 61), 10, 10),
        "ct_breakdown": ((66, 75), 16, 0),
        "bus_crash": ((96, 109), 3, 8),
    }


def test_bus_crash_warning_shows_exact_start_from_8_ticks_before_until_it_ends() -> None:
    sim = Simulation(make_world(events=[EventSpec("bus_crash", 20, 2, 8)]))
    seen = _warnings_by_tick(sim, 24)
    warned = [t for t, w in seen.items() if w == [{"event": "bus_crash", "start_tick": 20}]]
    assert warned == [12, 13, 14, 15, 16, 17, 18, 19, 20, 21]
    assert all(w == [] for t, w in seen.items() if t not in warned)


def test_flu_warning_lasts_from_10_ticks_before_through_the_last_flu_tick() -> None:
    sim = Simulation(make_world(events=[EventSpec("flu_wave", 30, 6, 10)]))
    seen = _warnings_by_tick(sim, 40)
    warned = [t for t, w in seen.items() if w]
    assert warned == list(range(20, 36))  # 10 ticks of notice, then the flu ticks 30..35
    assert all(seen[t] == [{"event": "flu_wave", "start_tick": 30}] for t in warned)


@pytest.mark.parametrize("kind", ["ct_breakdown", "staff_sickness"])
def test_unannounced_event_leaves_no_trace_in_observation_before_it_starts(kind: str) -> None:
    duration = c.EVENTS[kind]["duration"]
    sick = ("N1", "N2") if kind == "staff_sickness" else ()
    sim = Simulation(make_world(events=[EventSpec(kind, 10, duration, c.EVENTS[kind]["warning"], sick)]))
    quiet = sim.observe()
    while sim.tick < 10:
        obs = sim.observe()
        assert obs["warnings"] == []
        assert obs["ct"] == {"working": True, "down_ticks_left": 0}
        assert [s["status"] for s in obs["staff"]] == [s["status"] for s in quiet["staff"]]
        assert not lines(sim, "event_start")
        sim.step([])
    assert lines(sim, "event_start", kind=kind)[0]["t"] == 10
    obs = sim.observe()
    assert obs["warnings"] == []
    if kind == "ct_breakdown":
        assert obs["ct"] == {"working": False, "down_ticks_left": duration}
    else:
        assert [s["id"] for s in obs["staff"] if s["status"] == "sick"] == ["N1", "N2"]


def test_ct_breakdown_shows_its_downtime_only_once_it_has_started() -> None:
    sim = Simulation(make_world(events=[EventSpec("ct_breakdown", 5, 16, 0)]))
    advance(sim, 5)
    assert sim.observe()["ct"] == {"working": False, "down_ticks_left": 16}
    advance(sim, 4)
    assert sim.observe()["ct"] == {"working": False, "down_ticks_left": 12}


def test_sick_nurse_on_shift_leaves_her_zone_and_the_beds_lose_coverage() -> None:
    world = make_world([patient(1, 0, 3)], [EventSpec("staff_sickness", 2, 20, 0, ("N1",))])
    sim = Simulation(world)
    sim.step(crew("acute", 1, 1) + [admit("P001", "acute")])
    assert bed(sim, "A1")["covered"] is True
    sim.step([])
    assert (staff(sim, "N1")["status"], staff(sim, "N1")["location"]) == ("sick", "rest")
    assert not any(b.get("covered") for b in sim.observe()["beds"])


def test_sickness_only_hits_the_two_named_nurses() -> None:
    sim = Simulation(make_world(events=[EventSpec("staff_sickness", 1, 20, 0, ("N1", "N2"))]))
    advance(sim, 1)
    sick = sorted(s["id"] for s in sim.observe()["staff"] if s["status"] == "sick")
    assert sick == ["N1", "N2"]
