"""Rulebook §7 (events and warnings) and §5 (sick staff), seen through the sim's public surface."""

import pytest
from ed72_sim import constants as c
from ed72_sim.engine import Simulation
from ed72_sim.model import EventSpec
from ed72_sim.world import generate_world
from sim_fixtures import admit, advance, crew, lines, make_world, patient, staff


def _warnings_by_tick(sim: Simulation, until: int) -> dict[int, list[dict]]:
    seen = {}
    while sim.tick < until:
        seen[sim.tick] = sim.observe()["warnings"]
        sim.step([])
    return seen


def test_event_table_matches_the_rulebook() -> None:
    assert {k: (v["window"], v["duration"], v["warning"]) for k, v in c.EVENTS.items()} == {
        "staff_sickness": ((28, 35), 20, 0),
        "flu_wave": ((50, 61), 6, 10),
        "ct_breakdown": ((66, 75), 16, 0),
        "bus_crash": ((96, 109), 2, 8),
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
    assert (warned[0], warned[-1]) == (20, 35)
    assert all(seen[t] == [{"event": "flu_wave", "start_tick": 30}] for t in warned)


@pytest.mark.parametrize("kind", ["ct_breakdown", "staff_sickness"])
def test_unannounced_event_leaves_no_trace_in_observation_before_it_starts(kind: str) -> None:
    sick = ("N1", "N2") if kind == "staff_sickness" else ()
    sim = Simulation(make_world(events=[EventSpec(kind, 10, 16, 0, sick)]))
    quiet = sim.observe()
    while sim.tick < 10:
        obs = sim.observe()
        assert obs["warnings"] == []
        assert obs["ct"] == {"working": True, "down_ticks_left": 0}
        assert [s["status"] for s in obs["staff"]] == [s["status"] for s in quiet["staff"]]
        assert not lines(sim, "event_start")
        sim.step([])
    assert lines(sim, "event_start", kind=kind)[0]["t"] == 10
    assert sim.observe()["warnings"] == []


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
    assert sim.observe()["beds"][3]["covered"] is True
    sim.step([])
    assert (staff(sim, "N1")["status"], staff(sim, "N1")["location"]) == ("sick", "rest")
    assert not any(b.get("covered") for b in sim.observe()["beds"])


def test_sick_nurse_is_back_resting_exactly_20_ticks_after_she_left() -> None:
    world = make_world(events=[EventSpec("staff_sickness", 30, 20, 0, ("N3", "N4"))])
    sim = Simulation(world)
    advance(sim, 30)
    assert staff(sim, "N3")["status"] == "sick" and staff(sim, "N3")["ticks_until_change"] == 20
    advance(sim, 19)
    assert staff(sim, "N3")["status"] == "sick" and staff(sim, "N3")["ticks_until_change"] == 1
    advance(sim, 1)
    assert [staff(sim, n)["status"] for n in ("N3", "N4")] == ["resting", "resting"]
    assert staff(sim, "N3")["ticks_until_change"] is None


def test_sickness_only_hits_the_two_named_nurses() -> None:
    sim = Simulation(make_world(events=[EventSpec("staff_sickness", 1, 20, 0, ("N1", "N2"))]))
    advance(sim, 1)
    sick = sorted(s["id"] for s in sim.observe()["staff"] if s["status"] == "sick")
    assert sick == ["N1", "N2"]


def test_flu_wave_adds_two_arrivals_per_tick_for_six_ticks_mostly_esi_3_to_5() -> None:
    flu = [patient(n, 10 + n // 2, 3 + n % 3, source="flu") for n in range(12)]
    sim = Simulation(make_world(flu, [EventSpec("flu_wave", 10, 6, 10)]))
    advance(sim, 20)
    arrivals = lines(sim, "arrival", source="flu")
    assert [e["t"] for e in arrivals].count(10) == 2
    assert len(arrivals) == 12 and {e["t"] for e in arrivals} == set(range(10, 16))


@pytest.mark.parametrize(
    ("kind", "source", "per_tick", "ticks", "esi"),
    [("flu_wave", "flu", 2, 6, {3, 4, 5}), ("bus_crash", "bus", 5, 2, {1, 2, 3})],
)
def test_seeded_world_surges_fill_exactly_the_event_window(
    kind: str, source: str, per_tick: int, ticks: int, esi: set[int]
) -> None:
    for seed in range(1, 6):
        world = generate_world(seed)
        event = next(e for e in world.events if e.kind == kind)
        surge = [p for p in world.patients if p.source == source]
        assert len(surge) == per_tick * ticks
        assert {p.arrival_tick for p in surge} == set(range(event.start_tick, event.start_tick + ticks))
        assert {p.esi for p in surge} <= esi


def test_seeded_world_events_are_announced_per_the_rulebook() -> None:
    for seed in range(1, 6):
        world = generate_world(seed)
        warned = {e.kind: e.warning_ticks for e in world.events}
        assert warned == {"staff_sickness": 0, "flu_wave": 10, "ct_breakdown": 0, "bus_crash": 8}
        sick = next(e for e in world.events if e.kind == "staff_sickness")
        assert len(sick.staff) == 2 and all(s.startswith("N") for s in sick.staff)
