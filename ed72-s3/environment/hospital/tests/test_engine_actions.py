from ed72_sim.engine import Simulation
from ed72_sim.model import EventSpec
from sim_fixtures import admit, advance, bed, crew, lines, make_world, patient, staff


def test_esi1_is_admitted_in_the_tick_it_arrives() -> None:
    sim = Simulation(make_world([patient(1, 0, 1)]))
    assert [w["id"] for w in sim.observe()["waiting"]] == ["P001"]
    out = sim.step([admit("P001", "resus")])
    assert out["results"] == [{"index": 0, "ok": True}]
    assert lines(sim, "admitted", patient="P001", t=0, zone="resus", bed="R1")


def test_admit_takes_first_free_bed_and_adds_zone_ticks() -> None:
    patients = [patient(1, 0, 2), patient(2, 0, 2), patient(3, 0, 3), patient(4, 0, 3)]
    sim = Simulation(make_world(patients))
    sim.step(
        [admit("P001", "acute"), admit("P002", "acute"), admit("P003", "fast_track"), admit("P004", "resus")]
    )
    assert lines(sim, "admitted", patient="P002")[0]["bed"] == "A2"
    obs = sim.observe()
    needed = {b["patient"]: b["treatment_ticks"] for b in obs["beds"] if b["patient"]}
    # ESI 2: 5 + 1 in acute; ESI 3: 3 + 1 in fast-track, 3 + 0 in resus
    assert needed == {"P001": 6, "P002": 6, "P003": 4, "P004": 3}


def test_zone_extra_ticks_for_esi2_in_resus_and_esi4_fast_track() -> None:
    sim = Simulation(make_world([patient(1, 0, 2), patient(2, 0, 4)]))
    sim.step([admit("P001", "resus"), admit("P002", "fast_track")])
    assert bed(sim, "R1")["treatment_ticks"] == 5
    assert bed(sim, "F1")["treatment_ticks"] == 2


def test_every_rejection_reason_and_valid_actions_still_apply() -> None:
    patients = [patient(1, 0, 1), patient(2, 0, 3), patient(3, 0, 3), patient(4, 0, 3), patient(5, 0, 3)]
    sim = Simulation(make_world(patients))
    sim.state.find_staff("D3").status = "fainted"
    sim.state.spent = 23_500  # an agency doctor (900) would pass the hard limit; a nurse (350) fits
    actions = [
        {"type": "teleport"},  # 0 bad_action
        {"type": "admit", "patient": "P001"},  # 1 bad_action (no zone)
        {"type": "admit", "patient": "P001", "zone": "icu"},  # 2 bad_action (unknown zone)
        "admit P001",  # 3 bad_action (not a dict)
        admit("P099", "resus"),  # 4 unknown_patient (future or missing)
        admit("P001", "acute"),  # 5 zone_not_allowed
        admit("P002", "resus"),  # 6 ok
        admit("P002", "resus"),  # 7 not_waiting
        admit("P003", "resus"),  # 8 ok
        admit("P004", "resus"),  # 9 ok
        admit("P005", "resus"),  # 10 no_free_bed
        {"type": "assign", "staff": "X9", "to": "acute"},  # 11 unknown_staff
        {"type": "assign", "staff": "D3", "to": "acute"},  # 12 staff_unavailable
        {"type": "assign", "staff": "D1", "to": "mars"},  # 13 bad_action
        {"type": "agency", "role": "doctor"},  # 14 over_hard_limit
        {"type": "agency", "role": "nurse"},  # 15 ok
        {"type": "repair"},  # 16 ct_not_broken
        {"type": "divert"},  # 17 ok
        {"type": "divert"},  # 18 diversion_active
        {"type": "assign", "staff": "D1", "to": "acute"},  # 19 ok
    ]
    out = sim.step(actions)
    reasons = {r["index"]: r.get("reason") for r in out["results"]}
    assert reasons == {
        0: "bad_action", 1: "bad_action", 2: "bad_action", 3: "bad_action", 4: "unknown_patient",
        5: "zone_not_allowed", 6: None, 7: "not_waiting", 8: None, 9: None, 10: "no_free_bed",
        11: "unknown_staff", 12: "staff_unavailable", 13: "bad_action", 14: "over_hard_limit",
        15: None, 16: "ct_not_broken", 17: None, 18: "diversion_active", 19: None,
    }  # fmt: skip
    assert sim.state.spent == 23_850
    assert staff(sim, "D1")["location"] == "acute"
    rejected = sim.observe()["last_rejected"]
    assert {r["index"] for r in rejected} == {i for i, reason in reasons.items() if reason}
    assert rejected[5] == {"index": 5, "action": admit("P001", "acute"), "reason": "zone_not_allowed"}


def test_last_rejected_resets_on_the_next_step() -> None:
    sim = Simulation(make_world())
    sim.step([{"type": "repair"}])
    assert len(sim.observe()["last_rejected"]) == 1
    sim.step([])
    assert sim.observe()["last_rejected"] == []


def test_assign_moves_between_zone_and_rest() -> None:
    sim = Simulation(make_world())
    sim.step(crew("acute", 1, 0))
    assert (staff(sim, "D1")["location"], staff(sim, "D1")["status"]) == ("acute", "on_shift")
    sim.step([{"type": "assign", "staff": "D1", "to": "rest"}])
    assert (staff(sim, "D1")["location"], staff(sim, "D1")["status"]) == ("rest", "resting")


def test_agency_arrives_stays_and_leaves() -> None:
    sim = Simulation(make_world())
    out = sim.step([{"type": "agency", "role": "nurse"}, {"type": "assign", "staff": "AN1", "to": "acute"}])
    assert out["results"][1] == {"index": 1, "ok": False, "reason": "staff_unavailable"}
    assert lines(sim, "spend") == [{**lines(sim, "spend")[0], "item": "agency_nurse", "amount": 350}]
    assert staff(sim, "AN1")["status"] == "agency_ordered"
    assert staff(sim, "AN1")["ticks_until_change"] == 3  # observed at tick 1, arrives at tick 4
    advance(sim, 3)  # now at tick 4
    an = staff(sim, "AN1")
    assert (an["status"], an["fatigue"], an["location"], an["agency"]) == ("resting", 0, "rest", True)
    assert an["ticks_until_change"] == 16
    advance(sim, 15)  # tick 19: last tick of the contract
    assert staff(sim, "AN1")["status"] == "resting"
    advance(sim, 1)  # tick 20 step 1
    an = staff(sim, "AN1")
    assert (an["status"], an["ticks_until_change"]) == ("agency_left", None)
    out = sim.step([{"type": "assign", "staff": "AN1", "to": "acute"}])
    assert out["results"][0]["reason"] == "staff_unavailable"


def test_agency_ids_follow_order_and_hard_limit_blocks_spend() -> None:
    sim = Simulation(make_world(hard_limit=24_000))
    out = sim.step([{"type": "agency", "role": "doctor"} for _ in range(27)])
    oks = [r["ok"] for r in out["results"]]
    assert oks.count(True) == 26 and out["results"][26]["reason"] == "over_hard_limit"
    ids = [s["id"] for s in sim.observe()["staff"] if s["agency"]]
    assert ids[0] == "AD1" and ids[-1] == "AD26"
    assert sim.observe()["budget"]["spent"] == 23_400
    sim.step([{"type": "agency", "role": "nurse"}, {"type": "repair"}])
    assert staff(sim, "AN1")["status"] == "agency_ordered"


def test_diversion_window_and_overlap_rule() -> None:
    patients = [patient(i, i, 3, divert_u=0.5) for i in range(1, 7)] + [patient(7, 2, 3, divert_u=0.9)]
    sim = Simulation(make_world(patients))
    sim.step([{"type": "divert"}])
    assert sim.observe()["diversion"] == {"active": True, "ticks_left": 3}  # observed at tick 1
    assert sim.step([{"type": "divert"}])["results"][0]["reason"] == "diversion_active"
    advance(sim, 3)  # now at tick 5; arrivals of ticks 1-4 were covered
    diverted = {e["patient"] for e in lines(sim, "diverted")}
    assert diverted == {"P001", "P002", "P003", "P004"}
    assert sim.observe()["totals"]["diverted"] == 4
    arrived = {e["patient"] for e in lines(sim, "arrival")}
    assert {"P005", "P007"} <= arrived  # P007 has divert_u 0.9; P005 arrives after the window
    assert "P006" not in arrived  # tick 6 has not started
    sim2 = Simulation(make_world([]))
    sim2.step([{"type": "divert"}])
    advance(sim2, 3)  # tick 4: ticks_left 0, a new divert is allowed
    assert sim2.observe()["diversion"] == {"active": False, "ticks_left": 0}
    assert sim2.step([{"type": "divert"}])["results"][0]["ok"] is True


def test_diverted_patient_is_not_waiting_and_not_admittable() -> None:
    sim = Simulation(make_world([patient(1, 1, 3, divert_u=0.1)]))
    sim.step([{"type": "divert"}])
    assert sim.observe()["waiting"] == []
    assert sim.step([admit("P001", "acute")])["results"][0]["reason"] == "not_waiting"


def test_ct_repair_returns_scanner_early_and_needs_a_broken_ct() -> None:
    sim = Simulation(make_world(events=[EventSpec("ct_breakdown", 2, 16, 0)]))
    advance(sim, 2)  # tick 2: down
    obs = sim.observe()
    assert obs["ct"] == {"working": False, "down_ticks_left": 16}
    sim.step([{"type": "repair"}])  # ordered at tick 2: back at tick 5
    assert sim.observe()["ct"] == {"working": False, "down_ticks_left": 2}
    advance(sim, 2)  # tick 5 step 2 brings it back
    assert sim.observe()["ct"] == {"working": True, "down_ticks_left": 0}
    assert lines(sim, "event_end", kind="ct_breakdown")[0]["t"] == 5
    assert sim.step([{"type": "repair"}])["results"][0]["reason"] == "ct_not_broken"
    advance(sim, 15)
    assert len(lines(sim, "event_end", kind="ct_breakdown")) == 1  # no second end at tick 18
