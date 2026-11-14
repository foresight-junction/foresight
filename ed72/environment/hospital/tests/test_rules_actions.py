import pytest
from ed72_sim import constants as c
from ed72_sim.engine import Simulation
from ed72_sim.model import EventSpec
from ed72_sim.world import generate_world
from sim_fixtures import advance, lines, make_world, patient

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
    sim = broken_ct(hard_limit=c.REPAIR_COST - 1)
    out = sim.step([REPAIR])
    assert out["results"][0]["reason"] == "over_hard_limit"
    assert spent(sim) == 0 and not lines(sim, "spend")
    assert out["observation"]["ct"] == {"working": False, "down_ticks_left": 15}  # no early return
    advance(sim, 14)
    assert sim.observe()["ct"] == {"working": False, "down_ticks_left": 1}


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


@pytest.mark.parametrize(("divert_u", "turned_away"), [(0.69, True), (0.7, False)])
def test_diversion_share_is_strictly_below_75_percent(divert_u: float, turned_away: bool) -> None:
    sim = Simulation(make_world([patient(1, 1, 3, divert_u=divert_u)]))
    sim.step([DIVERT])
    assert bool(lines(sim, "diverted", patient="P001")) is turned_away
    assert [p["id"] for p in sim.observe()["waiting"]] == ([] if turned_away else ["P001"])


def test_diversion_also_turns_away_bus_crash_patients_each_by_its_own_draw() -> None:
    seen = set()
    for seed in range(1, 6):
        world = generate_world(seed)
        bus = [p for p in world.patients if p.source == "bus"]
        sim = Simulation(world)
        advance(sim, bus[0].arrival_tick - 1)
        sim.step([DIVERT])  # covers the two bus-crash ticks
        advance(sim, 2)
        diverted = {e["patient"] for e in lines(sim, "diverted")}
        assert {p.id for p in bus if p.divert_u < c.DIVERT_SHARE} == diverted & {p.id for p in bus}
        arrived = {e["patient"] for e in lines(sim, "arrival", source="bus")}
        assert arrived == {p.id for p in bus if p.divert_u >= c.DIVERT_SHARE}
        seen |= {p.divert_u < c.DIVERT_SHARE for p in bus}
    assert seen == {True, False}


def test_diversion_expires_after_four_arrival_ticks_and_can_be_renewed() -> None:
    sim = Simulation(make_world([patient(n, n, 3, divert_u=0.69) for n in range(1, 7)]))
    sim.step([DIVERT])  # ticks 1..4 are covered
    for n in range(1, 5):
        assert [e["patient"] for e in lines(sim, "diverted")] == [f"P{k:03d}" for k in range(1, n + 1)]
        sim.step([])
    assert sim.tick == 5 and not [e for e in lines(sim, "arrival") if e["t"] < 5]
    assert sim.observe()["diversion"] == {"active": False, "ticks_left": 0}
    assert [p["id"] for p in sim.observe()["waiting"]] == ["P005"]
    assert sim.step([DIVERT])["results"][0]["ok"] is True
