import pytest
from ed72_sim.engine import Simulation
from sim_fixtures import admit, advance, bed, crew, lines, make_world, patient


def test_esi1_waiting_death_threshold_is_strictly_below_015() -> None:
    sim = Simulation(
        make_world([patient(1, 0, 1, hazard_at={0: 0.149}), patient(2, 0, 1, hazard_at={0: 0.15})])
    )
    sim.step([])
    assert [(e["patient"], e["cause"], e["t"]) for e in lines(sim, "death")] == [("P001", "waiting", 0)]
    assert [w["id"] for w in sim.observe()["waiting"]] == ["P002"]
    assert sim.observe()["totals"]["deaths"] == 1


def test_esi2_waiting_hazard_starts_after_one_full_tick() -> None:
    sim = Simulation(make_world([patient(1, 0, 2, hazard=0.0)]))
    advance(sim, 2)  # ticks 0 and 1: waited 0 and 1, not more than 1
    assert not lines(sim, "death")
    advance(sim, 1)
    assert [(e["t"], e["cause"]) for e in lines(sim, "death")] == [(2, "waiting")]


@pytest.mark.parametrize(("ct_u", "needs_ct"), [(0.4, True), (0.6, False)])
def test_esi3_upgrades_after_six_ticks_then_follows_esi2_rules(ct_u: float, needs_ct: bool) -> None:
    sim = Simulation(make_world([patient(1, 0, 3, hazard=0.0, upgrade_ct_u=ct_u)]))
    advance(sim, 7)  # ticks 0..6: waited 0..6, none greater than 6
    assert not lines(sim, "upgrade")
    advance(sim, 1)  # tick 7: waited 7
    up = lines(sim, "upgrade")
    assert [(e["t"], e["esi"], e["needs_ct"]) for e in up] == [(7, 2, needs_ct)]
    waiting = sim.observe()["waiting"][0]
    assert (waiting["esi"], waiting["needs_ct"]) == (2, needs_ct)
    assert not lines(sim, "death")  # one hazard per tick
    advance(sim, 1)
    assert [(e["t"], e["cause"]) for e in lines(sim, "death")] == [(8, "waiting")]


def test_esi3_upgrade_threshold_is_strictly_below_008() -> None:
    sim = Simulation(make_world([patient(1, 0, 3, hazard_at={7: 0.08, 8: 0.079})]))
    advance(sim, 8)
    assert not lines(sim, "upgrade")
    advance(sim, 1)
    assert lines(sim, "upgrade")[0]["t"] == 8


@pytest.mark.parametrize("esi", [4, 5])
def test_esi45_leave_after_sixteen_ticks(esi: int) -> None:
    sim = Simulation(make_world([patient(1, 0, esi, hazard=0.0)]))
    advance(sim, 17)  # ticks 0..16: waited up to 16
    assert not lines(sim, "left")
    advance(sim, 1)
    assert [e["t"] for e in lines(sim, "left")] == [17]
    assert sim.observe()["totals"]["left"] == 1 and sim.observe()["waiting"] == []


def test_no_waiting_hazard_on_the_admission_tick() -> None:
    sim = Simulation(make_world([patient(1, 0, 1, hazard=0.0)]))
    sim.step([admit("P001", "resus"), *crew("resus", 1, 1)])
    assert not lines(sim, "death")  # covered, zone fresh: no bed hazard either


def test_uncovered_bed_deaths_by_esi() -> None:
    patients = [
        patient(1, 0, 1, hazard_at={0: 0.099}),
        patient(2, 0, 2, hazard_at={0: 0.029}),
        patient(3, 0, 3, hazard=0.0),
    ]
    sim = Simulation(make_world(patients))
    sim.step([admit("P001", "resus"), admit("P002", "acute"), admit("P003", "acute")])
    assert [(e["patient"], e["cause"]) for e in lines(sim, "death")] == [
        ("P001", "uncovered_bed"),
        ("P002", "uncovered_bed"),
    ]
    assert bed(sim, "R1")["patient"] is None and bed(sim, "A1")["patient"] is None  # deaths free the bed
    assert bed(sim, "A2")["patient"] == "P003"  # ESI 3 on a bed: no hazard


def test_uncovered_thresholds_are_strict() -> None:
    patients = [patient(1, 0, 1, hazard_at={0: 0.10}), patient(2, 0, 2, hazard_at={0: 0.03})]
    sim = Simulation(make_world(patients))
    sim.step([admit("P001", "resus"), admit("P002", "acute")])
    assert not lines(sim, "death")


def test_covered_bed_has_no_uncovered_hazard() -> None:
    sim = Simulation(make_world([patient(1, 0, 1, hazard=0.05)]))
    sim.step([admit("P001", "resus"), *crew("resus", 1, 1)])
    assert not lines(sim, "death")


def _tired_resus(sim: Simulation, fatigue10: int) -> list[dict]:
    for name in ("D1", "D2", "N1", "N2"):
        sim.state.find_staff(name).fatigue10 = fatigue10
    return crew("resus", 2, 2)


def test_fatigue_death_needs_covered_bed_in_a_tired_zone() -> None:
    sim = Simulation(make_world([patient(1, 0, 1, hazard_at={0: 0.014})]))
    sim.step([admit("P001", "resus"), *_tired_resus(sim, 700)])  # 1.2 of each role covers one bed
    assert [(e["patient"], e["cause"]) for e in lines(sim, "death")] == [("P001", "fatigue")]


def test_fatigue_hazard_boundaries() -> None:
    survivors = [
        (700, 0.015),  # u is not below p
        (600, 0.0),  # mean fatigue exactly 60 is not above 60
    ]
    for fatigue10, u in survivors:
        sim = Simulation(make_world([patient(1, 0, 1, hazard=u)]))
        sim.step([admit("P001", "resus"), *_tired_resus(sim, fatigue10)])
        assert not lines(sim, "death"), (fatigue10, u)


def test_fatigue_hazard_uses_zone_mean_not_one_tired_person() -> None:
    sim = Simulation(make_world([patient(1, 0, 1, hazard=0.0)]))
    sim.state.find_staff("D1").fatigue10 = 800
    sim.step([admit("P001", "resus"), *crew("resus", 2, 2)])  # mean (800+0+0+0)/4 = 20
    assert not lines(sim, "death")
