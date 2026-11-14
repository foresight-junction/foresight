import pytest
from ed72_sim import constants as c
from ed72_sim.engine import Simulation
from ed72_sim.model import EventSpec
from sim_fixtures import admit, advance, bed, crew, lines, make_world, patient

REPAIR = {"type": "repair"}
DIVERT = {"type": "divert"}


def broken_ct(start: int = 0, duration: int = 16, **world: int) -> Simulation:
    return Simulation(make_world(events=[EventSpec("ct_breakdown", start, duration, 0)], **world))


def spent(sim: Simulation) -> int:
    return sim.observe()["budget"]["spent"]


def test_repair_costs_2000_and_emits_a_spend_event() -> None:
    sim = broken_ct()
    sim.step([REPAIR])
    assert spent(sim) == 2_000 == c.REPAIR_COST
    assert [(e["item"], e["amount"]) for e in lines(sim, "spend")] == [("repair", 2_000)]


def test_rejected_repair_costs_nothing() -> None:
    sim = Simulation(make_world())
    assert sim.step([REPAIR])["results"][0]["reason"] == "ct_not_broken"
    assert spent(sim) == 0 and not lines(sim, "spend")


def test_repair_cannot_delay_a_breakdown_that_ends_within_three_ticks() -> None:
    sim = broken_ct(duration=2)
    sim.step([REPAIR])
    assert sim.observe()["ct"] == {"working": False, "down_ticks_left": 1}
    sim.step([])
    assert sim.observe()["ct"]["working"] is True
    assert lines(sim, "event_end", kind="ct_breakdown")[0]["t"] == 2


def test_second_repair_is_accepted_and_charged_but_changes_nothing() -> None:
    # Rulebook §8 only says repair is valid "while the CT is down"; it is silent on a repair already pending.
    sim = broken_ct()
    sim.step([REPAIR])
    after_first = sim.observe()["ct"]
    out = sim.step([REPAIR])
    assert out["results"][0]["ok"] is True
    assert spent(sim) == 4_000
    assert after_first == {"working": False, "down_ticks_left": 2}
    assert out["observation"]["ct"] == {"working": False, "down_ticks_left": 1}
    advance(sim, 1)
    assert lines(sim, "event_end", kind="ct_breakdown")[0]["t"] == 3


def test_repair_over_the_hard_limit_is_rejected_without_effect() -> None:
    sim = broken_ct(hard_limit=3_999)
    sim.step([REPAIR])
    assert spent(sim) == 2_000
    out = sim.step([REPAIR])
    assert out["results"][0]["reason"] == "over_hard_limit"
    assert spent(sim) == 2_000
    assert out["observation"]["ct"]["down_ticks_left"] == 1


def test_hard_limit_is_inclusive_and_shared_by_agency_and_repair() -> None:
    sim = broken_ct(hard_limit=2_350)
    out = sim.step([{"type": "agency", "role": "nurse"}, REPAIR, {"type": "agency", "role": "nurse"}])
    assert [r.get("reason") for r in out["results"]] == [None, None, "over_hard_limit"]
    assert spent(sim) == 2_350 and out["observation"]["budget"]["hard_limit"] == 2_350


def test_spending_past_the_budget_is_allowed_up_to_the_hard_limit() -> None:
    sim = Simulation(make_world())
    out = sim.step([{"type": "agency", "role": "doctor"} for _ in range(c.HARD_LIMIT // 900)])
    assert all(r["ok"] for r in out["results"])
    assert c.BUDGET < spent(sim) <= c.HARD_LIMIT


def test_divert_is_free() -> None:
    sim = Simulation(make_world())
    assert sim.step([DIVERT])["results"][0]["ok"] is True
    assert spent(sim) == 0 and not lines(sim, "spend")


@pytest.mark.parametrize(("divert_u", "turned_away"), [(0.69, True), (0.70, False)])
def test_diversion_share_is_strictly_below_70_percent(divert_u: float, turned_away: bool) -> None:
    sim = Simulation(make_world([patient(1, 1, 3, divert_u=divert_u)]))
    sim.step([DIVERT])
    assert bool(lines(sim, "diverted", patient="P001")) is turned_away
    assert [p["id"] for p in sim.observe()["waiting"]] == ([] if turned_away else ["P001"])


def test_diversion_also_turns_away_bus_crash_patients() -> None:
    bus = [patient(i, 2, 1, source="bus", divert_u=0.1) for i in (1, 2)]
    sim = Simulation(make_world(bus, [EventSpec("bus_crash", 2, 2, 8)]))
    sim.step([DIVERT])
    sim.step([])
    assert {e["patient"] for e in lines(sim, "diverted")} == {"P001", "P002"}
    assert sim.observe()["waiting"] == []


def test_diversion_expires_after_four_arrival_ticks_and_can_be_renewed() -> None:
    late = patient(1, 5, 3, divert_u=0.0)
    sim = Simulation(make_world([late]))
    sim.step([DIVERT])
    advance(sim, 4)
    assert sim.observe()["diversion"] == {"active": False, "ticks_left": 0}
    assert [p["id"] for p in sim.observe()["waiting"]] == ["P001"]
    assert sim.step([DIVERT])["results"][0]["ok"] is True


def test_waiting_for_ct_flag_and_stall_while_the_scanner_is_down() -> None:
    world = make_world([patient(1, 0, 1, needs_ct=True)], [EventSpec("ct_breakdown", 1, 16, 0)])
    sim = Simulation(world)
    sim.step(crew("resus", 1, 1) + [admit("P001", "resus")])
    advance(sim, 3)
    row = bed(sim, "R1")
    assert row["treated_ticks"] == 3 == (c.TREATMENT_TICKS[1] + 1) // 2
    assert row["waiting_for_ct"] is True and row["covered"] is True
    advance(sim, 4)
    assert bed(sim, "R1")["treated_ticks"] == 3
    sim.step([REPAIR])
    advance(sim, 3)
    assert bed(sim, "R1")["patient"] is None or bed(sim, "R1")["treated_ticks"] > 3
