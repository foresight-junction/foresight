from ed72_sim.engine import Simulation
from ed72_sim.model import EventSpec
from sim_fixtures import admit, advance, bed, crew, lines, make_world, patient, staff


def test_coverage_prefers_severity_then_admission_time_then_bed() -> None:
    # P001 (ESI 3) is admitted a tick earlier than P002 (ESI 1) and P003 (ESI 2): one pair covers one bed
    patients = [patient(1, 0, 3), patient(2, 1, 1), patient(3, 1, 2)]
    sim = Simulation(make_world(patients))
    sim.step([admit("P001", "resus"), *crew("resus", 1, 1)])
    assert bed(sim, "R1")["treated_ticks"] == 1 and lines(sim, "covered", patient="P001")
    sim.step([admit("P002", "resus"), admit("P003", "resus")])
    covered = {b["patient"]: b["covered"] for b in sim.observe()["beds"] if b["patient"]}
    assert covered == {"P001": False, "P002": True, "P003": False}  # ESI 1 first; observation == step 6
    assert [e["patient"] for e in lines(sim, "covered")] == ["P001", "P002"]
    assert bed(sim, "R1")["treated_ticks"] == 1  # P001 stalled this tick


def test_covered_line_is_written_once() -> None:
    sim = Simulation(make_world([patient(1, 0, 3)]))
    sim.step([admit("P001", "acute"), *crew("acute", 1, 1)])
    advance(sim, 1)
    assert len(lines(sim, "covered")) == 1


def test_tired_staff_count_as_six_tenths_with_integer_floor() -> None:
    sim = Simulation(make_world([patient(i, 0, 3) for i in range(1, 9)]))
    # acute: doctors 0.6 + 0.6 + 1.0 = 2.2 -> floor(2.2 * 3) = 6 beds; 4 nurses -> 8 beds; 8 patients present
    sim.state.find_staff("D1").fatigue10 = 700
    sim.state.find_staff("D2").fatigue10 = 700
    sim.step([*crew("acute", 3, 4), *[admit(f"P{i:03d}", "acute") for i in range(1, 9)]])
    assert len(lines(sim, "covered")) == 6
    assert sum(b["covered"] for b in sim.observe()["beds"] if b["patient"]) == 6
    assert staff(sim, "D1")["counts_as"] == 0.6 and staff(sim, "D3")["counts_as"] == 1


def test_one_tired_doctor_cannot_cover_a_resus_bed() -> None:
    sim = Simulation(make_world([patient(1, 0, 1)]))
    sim.state.find_staff("D1").fatigue10 = 700
    sim.step([*crew("resus", 1, 1), admit("P001", "resus")])  # 0.6 of a doctor covers 0 resus beds
    assert not lines(sim, "covered")
    sim.state.find_staff("D2").fatigue10 = 700
    sim.step(crew("resus", 2, 2))  # 1.2 doctors -> 1 bed (nurses are fresh)
    assert lines(sim, "covered", patient="P001")


def test_discharge_frees_bed_and_counts() -> None:
    sim = Simulation(make_world([patient(1, 0, 5), patient(2, 1, 4)]))
    sim.step([admit("P001", "fast_track"), *crew("fast_track", 1, 1)])  # ESI 5: 1 tick
    assert lines(sim, "discharged", patient="P001")[0]["t"] == 0
    assert bed(sim, "F1")["patient"] is None
    sim.step([admit("P002", "fast_track")])
    assert lines(sim, "admitted", patient="P002")[0]["bed"] == "F1"
    assert sim.observe()["totals"]["discharged"] == 1


def test_ct_stall_at_half_treatment_then_repair() -> None:
    world = make_world([patient(1, 0, 1, needs_ct=True)], [EventSpec("ct_breakdown", 2, 16, 0)])
    sim = Simulation(world)
    sim.step([admit("P001", "resus"), *crew("resus", 1, 1)])  # tick 0: treated 1
    advance(sim, 2)  # ticks 1, 2: treated 3 = half of 6; CT went down at tick 2 step 2
    assert bed(sim, "R1")["treated_ticks"] == 3
    advance(sim, 1)  # tick 3: stalls
    b = bed(sim, "R1")
    assert (b["treated_ticks"], b["waiting_for_ct"], b["covered"]) == (3, True, True)
    advance(sim, 1)  # tick 4 stalls too
    sim.step([{"type": "repair"}])  # at tick 5: back at tick 8
    assert bed(sim, "R1")["treated_ticks"] == 3
    advance(sim, 2)  # ticks 6, 7 stall
    assert bed(sim, "R1")["treated_ticks"] == 3
    advance(sim, 1)  # tick 8: scanner back, scanned, treated 4
    b = bed(sim, "R1")
    assert (b["treated_ticks"], b["waiting_for_ct"]) == (4, False)
    advance(sim, 2)
    assert lines(sim, "discharged", patient="P001")[0]["t"] == 10


def test_patient_without_ct_need_ignores_a_broken_scanner() -> None:
    world = make_world([patient(1, 0, 1, needs_ct=False)], [EventSpec("ct_breakdown", 0, 16, 0)])
    sim = Simulation(world)
    sim.step([admit("P001", "resus"), *crew("resus", 1, 1)])
    advance(sim, 5)
    assert lines(sim, "discharged", patient="P001")[0]["t"] == 5


def test_faint_at_90_and_return_at_about_65() -> None:
    sim = Simulation(make_world())
    sim.step(crew("resus", 1, 0))  # tick 0 step 8: 2.2
    advance(sim, 39)  # through tick 39: 40 gains = 88.0
    assert staff(sim, "D1")["fatigue"] == 88.0 and not lines(sim, "faint")
    advance(sim, 1)  # tick 40: 90.2
    faint = lines(sim, "faint")
    assert [(e["t"], e["staff"]) for e in faint] == [(40, "D1")]
    d1 = staff(sim, "D1")
    assert (d1["status"], d1["location"], d1["ticks_until_change"]) == ("fainted", "rest", 10)
    assert sim.observe()["totals"]["faints"] == 1
    advance(sim, 9)  # steps of ticks 41..49, recovering 2.5 each; now tick 50
    d1 = staff(sim, "D1")
    assert (d1["status"], d1["ticks_until_change"]) == ("fainted", 1)
    advance(sim, 1)  # tick 50's step recovers once more; tick 51 step 1 returns D1
    d1 = staff(sim, "D1")
    assert (d1["status"], d1["location"], d1["fatigue"]) == ("resting", "rest", 65.2)


def test_resting_staff_recover_and_floor_at_zero() -> None:
    sim = Simulation(make_world())
    sim.step(crew("acute", 1, 0))
    advance(sim, 4)  # 5 gains of 1.6 = 8.0
    sim.step([{"type": "assign", "staff": "D1", "to": "rest"}])
    assert staff(sim, "D1")["fatigue"] == 5.5
    advance(sim, 3)
    assert staff(sim, "D1")["fatigue"] == 0


def test_staff_fatigue_line_counts_on_shift_and_tired() -> None:
    sim = Simulation(make_world())
    sim.state.find_staff("D1").fatigue10 = 700
    sim.step(crew("acute", 2, 1))
    line = lines(sim, "staff_fatigue", t=0)[0]
    assert (line["on_shift"], line["on_shift_above_60"]) == (3, 1)


def test_sickness_takes_nurses_off_post_and_returns_them_with_their_fatigue() -> None:
    world = make_world(events=[EventSpec("staff_sickness", 3, 20, 0, ("N1", "N2"))])
    sim = Simulation(world)
    sim.step(crew("acute", 0, 1))  # N1 on shift; N2 resting
    advance(sim, 2)  # now tick 3: N1 gained 1.6 at ticks 0, 1, 2 and fell sick in step 2
    n1 = staff(sim, "N1")
    assert (n1["status"], n1["location"], n1["ticks_until_change"], n1["fatigue"]) == (
        "sick",
        "rest",
        20,
        4.8,
    )
    assert staff(sim, "N2")["status"] == "sick"
    start = lines(sim, "event_start", kind="staff_sickness")[0]
    assert (start["t"], start["ends_tick"]) == (3, 23)
    out = sim.step([{"type": "assign", "staff": "N1", "to": "acute"}])
    assert out["results"][0]["reason"] == "staff_unavailable"
    advance(sim, 19)  # tick 23 step 1
    n1 = staff(sim, "N1")
    assert (n1["status"], n1["location"], n1["fatigue"]) == ("resting", "rest", 4.8)
    assert lines(sim, "event_end", kind="staff_sickness")[0]["t"] == 23


def test_announced_events_warn_until_they_end_unannounced_never() -> None:
    world = make_world(events=[EventSpec("flu_wave", 12, 6, 10), EventSpec("ct_breakdown", 5, 16, 0)])
    sim = Simulation(world)
    advance(sim, 1)
    assert sim.observe()["warnings"] == []  # tick 1; the warning starts at tick 2
    advance(sim, 1)
    assert sim.observe()["warnings"] == [{"event": "flu_wave", "start_tick": 12}]
    advance(sim, 15)  # tick 17: event runs 12..17
    assert sim.observe()["warnings"] == [{"event": "flu_wave", "start_tick": 12}]
    advance(sim, 1)  # tick 18: ended
    assert sim.observe()["warnings"] == []
    assert lines(sim, "event_start", kind="flu_wave")[0]["ends_tick"] == 18
    assert lines(sim, "event_end", kind="flu_wave")[0]["t"] == 18


def test_clock_and_observation_shape() -> None:
    sim = Simulation(make_world([patient(1, 0, 2, needs_ct=True)]))
    obs = sim.observe()
    assert (obs["tick"], obs["clock"], obs["ticks_left"], obs["finished"]) == (0, "Day 1 08:00", 144, False)
    assert obs["waiting"] == [
        {"id": "P001", "esi": 2, "arrived_tick": 0, "waited_ticks": 0, "needs_ct": True}
    ]
    assert len(obs["beds"]) == 17 and obs["beds"][0] == {"zone": "resus", "bed": "R1", "patient": None}
    assert [s["id"] for s in obs["staff"]] == [
        *(f"D{i}" for i in range(1, 7)),
        *(f"N{i}" for i in range(1, 10)),
    ]
    assert obs["budget"] == {"spent": 0, "budget": 12_000, "hard_limit": 24_000}
    advance(sim, 33)
    assert sim.observe()["clock"] == "Day 2 00:30"
