"""Issue #6 rules: agency staff lifecycle and faint recovery, seen through the public surface."""

from ed72_sim import constants as c
from ed72_sim.engine import Simulation
from sim_fixtures import admit, advance, lines, make_world, patient, staff

ORDER_NURSE = {"type": "agency", "role": "nurse"}
ORDER_DOCTOR = {"type": "agency", "role": "doctor"}


def assign(staff_id: str, to: str) -> dict:
    return {"type": "assign", "staff": staff_id, "to": to}


def reasons(out: dict) -> list[str | None]:
    return [r.get("reason") for r in out["results"]]


def test_doctor_costs_900_and_nurse_350_in_budget_and_spend_log() -> None:
    sim = Simulation(make_world())
    sim.step([ORDER_DOCTOR, ORDER_NURSE])
    assert sim.observe()["budget"]["spent"] == 900 + 350
    assert [(e["item"], e["amount"]) for e in lines(sim, "spend")] == [
        ("agency_doctor", 900),
        ("agency_nurse", 350),
    ]


def test_agency_ids_count_per_role_in_order_of_ordering() -> None:
    sim = Simulation(make_world())
    sim.step([ORDER_NURSE, ORDER_DOCTOR, ORDER_NURSE])
    agency = [(s["id"], s["role"]) for s in sim.observe()["staff"] if s["agency"]]
    assert agency == [("AN1", "nurse"), ("AD1", "doctor"), ("AN2", "nurse")]


def test_each_order_arrives_four_ticks_after_its_own_order_tick() -> None:
    sim = Simulation(make_world())
    sim.step([ORDER_NURSE])
    sim.step([ORDER_NURSE])
    assert (staff(sim, "AN1")["ticks_until_change"], staff(sim, "AN2")["ticks_until_change"]) == (2, 3)
    advance(sim, 2)
    assert (staff(sim, "AN1")["status"], staff(sim, "AN2")["status"]) == ("resting", "agency_ordered")


def test_arrived_agency_nurse_can_be_assigned_and_covers_a_bed() -> None:
    sim = Simulation(make_world([patient(1, 4, esi=4)]))
    advance(sim, 1, [ORDER_NURSE, ORDER_DOCTOR])
    advance(sim, 3)
    assert sim.observe()["tick"] == 4
    out = sim.step([assign("AD1", "fast_track"), assign("AN1", "fast_track"), admit("P001", "fast_track")])
    assert reasons(out) == [None, None, None]
    assert staff(sim, "AN1")["status"] == "on_shift"
    assert next(b for b in out["observation"]["beds"] if b["patient"] == "P001")["covered"]


def test_agency_staff_fatigue_gains_like_regular_staff_after_arrival() -> None:
    sim = Simulation(make_world())
    advance(sim, 1, [ORDER_NURSE])
    advance(sim, 3)
    assert staff(sim, "AN1")["fatigue"] == 0
    advance(sim, 1, [assign("AN1", "resus")])
    assert staff(sim, "AN1")["fatigue"] == c.FATIGUE_GAIN["resus"]


def test_agency_contract_ends_mid_shift_and_moves_staff_to_rest() -> None:
    sim = Simulation(make_world([patient(1, 4, esi=4)]))
    advance(sim, 1, [ORDER_NURSE, ORDER_DOCTOR])
    advance(sim, 3)
    sim.step([assign("AD1", "fast_track"), assign("AN1", "fast_track"), admit("P001", "fast_track")])
    last = 4 + c.AGENCY_STAY - 1  # arrive + 15 is the last contract tick
    advance(sim, last - sim.tick)
    assert sim.tick == last
    an = staff(sim, "AN1")
    assert (an["status"], an["location"], an["ticks_until_change"]) == ("on_shift", "fast_track", 1)
    assert staff(sim, "AD1")["status"] == "on_shift"
    advance(sim, 1)
    an = staff(sim, "AN1")
    assert (an["status"], an["location"], an["ticks_until_change"]) == ("agency_left", "rest", None)
    assert staff(sim, "AD1")["status"] == "agency_left"


def test_assign_agency_before_arrival_or_after_leaving_is_staff_unavailable() -> None:
    sim = Simulation(make_world())
    assert reasons(sim.step([ORDER_NURSE, assign("AN1", "acute")])) == [None, "staff_unavailable"]
    last = c.AGENCY_DELAY + c.AGENCY_STAY - 1
    advance(sim, last - sim.tick)
    assert sim.tick == last and staff(sim, "AN1")["status"] == "resting"
    assert reasons(sim.step([assign("AN1", "acute")])) == [None]  # still within the contract
    assert staff(sim, "AN1")["status"] == "agency_left"
    assert reasons(sim.step([assign("AN1", "acute")])) == ["staff_unavailable"]


def test_ordering_beyond_hard_limit_is_rejected_and_not_charged() -> None:
    sim = Simulation(make_world(hard_limit=1_000))
    out = sim.step([ORDER_DOCTOR, ORDER_NURSE, ORDER_DOCTOR])
    assert reasons(out) == [None, "over_hard_limit", "over_hard_limit"]
    assert sim.observe()["budget"]["spent"] == 900
    assert [s["id"] for s in sim.observe()["staff"] if s["agency"]] == ["AD1"]
    assert len(lines(sim, "spend")) == 1


def test_hard_limit_allows_spending_exactly_up_to_the_limit() -> None:
    sim = Simulation(make_world(hard_limit=1_250))
    assert reasons(sim.step([ORDER_DOCTOR, ORDER_NURSE])) == [None, None]
    assert sim.observe()["budget"]["spent"] == 1_250


def test_fainted_staff_cannot_be_assigned_until_they_return() -> None:
    sim = Simulation(make_world())
    advance(sim, 41, [assign("N1", "resus")])
    assert staff(sim, "N1")["status"] == "fainted"
    assert reasons(sim.step([assign("N1", "acute")])) == ["staff_unavailable"]
    advance(sim, c.FAINT_TICKS - 1)
    assert staff(sim, "N1")["status"] == "resting"
    assert reasons(sim.step([assign("N1", "acute")])) == [None]
