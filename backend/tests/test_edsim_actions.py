"""Engine unit tests: assignment constraints, invalid actions, resources, events, budget,
fatigue, waiting times and synthetic outcomes, using controlled patients."""

from __future__ import annotations

import copy

import pytest

from app.edsim import EDError, rules
from app.edsim import config as C
from tests.edsim_support import add_patient, advance_to, inject_event, quiet_sim, start


def _code(excinfo: pytest.ExceptionInfo[EDError]) -> str:
    return excinfo.value.code


# --- happy path ---------------------------------------------------------------------------
def test_treatment_runs_to_ready_and_discharge_frees_the_bed():
    sim = quiet_sim()
    p = add_patient(sim, acuity=3, duration=100)
    start(sim, p, "GEN-1", "res-d1", "rn-d4")
    sim.advance_time(1)
    assert p.first_active_min == 0 and p.stalled_reasons == []
    sim.advance_time(100)
    assert p.status == "ready" and p.disposition == "home"
    sim.act("discharge_patient", patient_ids=[p.patient_id])
    assert p.status == "discharged"
    assert sim.state.beds["GEN-1"].state(sim.state.minute) == "cleaning"
    assert sim.state.staff["res-d1"].patients == []


def test_admitted_patient_boards_until_transfer():
    sim = quiet_sim()
    sim.state.future_offers = []
    p = add_patient(sim, acuity=3, duration=10, admit_draw=0.0)
    start(sim, p, "GEN-1", "res-d1", "rn-d4")
    sim.advance_time(12)
    assert p.disposition == "admit"
    sim.act("discharge_patient", patient_ids=[p.patient_id])
    assert p.status == "boarding" and p.bed_id == "GEN-1" and p.doctor_id is None
    sim.act("request_transfer", patient_id=p.patient_id)
    assert sim.state.ledger["transfers"] == C.TRANSFER_FEE
    sim.advance_time(C.TRANSFER_MINUTES + 1)
    assert p.status == "transferred" and p.bed_id is None


def test_boarding_patient_can_move_to_a_hallway_bed():
    sim = quiet_sim()
    sim.state.future_offers = []
    p = add_patient(sim, acuity=2, complaint="chest_pain", duration=10, admit_draw=0.0)
    start(sim, p, "RESUS-1", "att-d1", "rn-d1")
    sim.advance_time(12)
    sim.act("discharge_patient", patient_ids=[p.patient_id])
    sim.act("request_resources", kind="hallway_bed", hours=8)
    sim.advance_time(C.LEAD_TIME_MINUTES)
    sim.act("assign_bed", patient_id=p.patient_id, bed_id="HALL-1")
    assert p.bed_id == "HALL-1"
    assert sim.state.beds["RESUS-1"].patient_id is None


# --- qualification, compatibility and capacity ---------------------------------------------
@pytest.mark.parametrize(
    ("acuity", "complaint", "bed", "doctor", "nurse", "code"),
    [
        (
            1,
            "chest_pain",
            "RESUS-1",
            "res-d1",
            "rn-d1",
            "STAFF_NOT_QUALIFIED",
        ),  # resident cannot lead acuity 1
        (2, "chest_pain", "MON-1", "att-d1", "rn-d4", "STAFF_NOT_QUALIFIED"),  # needs critical-care nurse
        (2, "chest_pain", "GEN-1", "att-d1", "rn-d1", "BED_INCOMPATIBLE"),
        (3, "abdominal_pain", "FT-1", "res-d1", "rn-d4", "BED_INCOMPATIBLE"),
        (3, "abdominal_pain", "GEN-1", "att-n1", "rn-d4", "STAFF_UNAVAILABLE"),  # night attending off duty
        (3, "abdominal_pain", "GEN-1", "res-d1", "rn-d7", "WRONG_ZONE"),  # rn-d7 starts in triage
        (3, "abdominal_pain", "GEN-1", "rn-d4", "rn-d5", "STAFF_NOT_QUALIFIED"),  # nurse in the doctor slot
        (3, "abdominal_pain", "NOPE-1", "res-d1", "rn-d4", "NOT_FOUND"),
    ],
)
def test_start_treatment_rejections(acuity, complaint, bed, doctor, nurse, code):
    sim = quiet_sim()
    p = add_patient(sim, acuity=acuity, complaint=complaint)
    with pytest.raises(EDError) as err:
        start(sim, p, bed, doctor, nurse)
    assert _code(err) == code
    assert p.status == "waiting" and p.bed_id is None


def test_untriaged_patient_cannot_start_treatment():
    sim = quiet_sim()
    p = add_patient(sim, triaged=False)
    with pytest.raises(EDError) as err:
        start(sim, p, "GEN-1", "res-d1", "rn-d4")
    assert _code(err) == "NOT_TRIAGED"


def test_occupied_bed_is_unavailable():
    sim = quiet_sim()
    a, b = add_patient(sim), add_patient(sim)
    start(sim, a, "GEN-1", "res-d1", "rn-d4")
    with pytest.raises(EDError) as err:
        start(sim, b, "GEN-1", "res-d2", "rn-d5")
    assert _code(err) == "BED_UNAVAILABLE"


def test_attending_capacity_is_enforced():
    sim = quiet_sim()
    patients = [add_patient(sim, acuity=1, complaint="chest_pain") for _ in range(3)]
    start(sim, patients[0], "RESUS-1", "att-d1", "rn-d1")
    start(sim, patients[1], "RESUS-2", "att-d1", "rn-d2")
    with pytest.raises(EDError) as err:
        start(sim, patients[2], "RESUS-3", "att-d1", "rn-d3")
    assert _code(err) == "STAFF_AT_CAPACITY"
    assert sim.state.staff["att-d1"].patients == [patients[0].patient_id, patients[1].patient_id]


def test_assign_staff_replaces_the_previous_holder():
    sim = quiet_sim()
    p = add_patient(sim)
    start(sim, p, "GEN-1", "res-d1", "rn-d4")
    sim.act("assign_staff", staff_id="res-d2", patient_ids=[p.patient_id])
    assert p.doctor_id == "res-d2"
    assert sim.state.staff["res-d1"].patients == []
    assert sim.state.staff["res-d2"].patients == [p.patient_id]


# --- invalid actions ----------------------------------------------------------------------
def _snapshot(sim):
    truth = sim.truth()
    truth.pop("invalid_actions")
    return copy.deepcopy((truth, sim.resource_status(), sim.staff_status(include_off_duty=True)))


def test_rejected_action_changes_nothing_and_is_counted():
    sim = quiet_sim()
    p = add_patient(sim)
    before = _snapshot(sim)
    with pytest.raises(EDError) as err:
        # Every check passes except the last one: CT is shared imaging, not allocatable.
        start(sim, p, "GEN-1", "res-d1", "rn-d4", equipment_ids=["CT-1"])
    assert _code(err) == "WRONG_EQUIPMENT"
    assert _snapshot(sim) == before
    assert sim.state.invalid_actions["WRONG_EQUIPMENT"] == 1
    assert sim.state.log[-1]["kind"] == "action_rejected"


@pytest.mark.parametrize(
    ("name", "kwargs", "code"),
    [
        ("discharge_patient", {"patient_ids": "PT-T001"}, "INVALID_ARGUMENT"),
        ("discharge_patient", {"patient_ids": ["PT-T001", "PT-T001"]}, "INVALID_ARGUMENT"),
        ("discharge_patient", {"patient_ids": ["PT-9999"]}, "NOT_FOUND"),
        ("discharge_patient", {"patient_ids": ["PT-T001"]}, "NOT_READY"),
        ("schedule_break", {"staff_id": "res-d1", "minutes": 5}, "INVALID_ARGUMENT"),
        ("extend_shift", {"staff_id": "res-d1", "hours": 9}, "INVALID_ARGUMENT"),
        ("request_temporary_staff", {"role": "surgeon", "hours": 8}, "INVALID_ARGUMENT"),
        ("request_resources", {"kind": "helicopter", "hours": 8}, "INVALID_ARGUMENT"),
        ("request_repair", {"equipment_id": "CT-1"}, "NOT_FAILED"),
        ("set_diversion", {"active": "yes"}, "INVALID_ARGUMENT"),
        ("set_staff_zone", {"staff_id": "res-d1", "zone": "triage"}, "STAFF_NOT_QUALIFIED"),
        ("set_staff_zone", {"staff_id": "rn-d1", "zone": "triage"}, "STAFF_NOT_QUALIFIED"),
        ("assign_staff", {"staff_id": "res-d1", "patient_ids": ["PT-T001"]}, "WRONG_STATUS"),
        ("release_staff", {"staff_id": "res-d1", "patient_id": "PT-T001"}, "INVALID_ARGUMENT"),
        ("teleport", {}, "INVALID_ARGUMENT"),
    ],
)
def test_invalid_actions_return_structured_errors(name, kwargs, code):
    sim = quiet_sim()
    add_patient(sim)
    with pytest.raises(EDError) as err:
        sim.act(name, **kwargs)
    assert _code(err) == code
    assert set(err.value.payload()["error"]) == {"code", "message"}


@pytest.mark.parametrize("minutes", [0, 121, -5, "10", True, 2.5])
def test_advance_time_rejects_bad_durations(minutes):
    sim = quiet_sim()
    with pytest.raises(EDError) as err:
        sim.advance_time(minutes)
    assert _code(err) == "INVALID_ARGUMENT"
    assert sim.state.minute == 0


# --- equipment, imaging and beds -----------------------------------------------------------
def test_monitoring_need_met_by_portable_monitor_in_general_bed():
    sim = quiet_sim()
    p = add_patient(sim, acuity=3, complaint="chest_pain")
    start(sim, p, "GEN-1", "res-d1", "rn-d4")
    sim.advance_time(1)
    assert "needs_monitoring" in p.stalled_reasons
    sim.act("allocate_equipment", equipment_id="PMON-1", patient_id=p.patient_id)
    sim.advance_time(1)
    assert p.stalled_reasons == []


def test_ventilator_failure_stalls_patient_and_expedited_repair_shortens_downtime():
    sim = quiet_sim()
    p = add_patient(sim, acuity=1, complaint="breathing_difficulty")
    assert rules.needs_ventilator(p)
    start(sim, p, "RESUS-1", "att-d1", "rn-d1", equipment_ids=["VENT-1"])
    sim.advance_time(1)
    assert p.stalled_reasons == []
    inject_event(sim, "equipment_failure", 2, equipment_id="VENT-1", downtime=300, estimate=300)
    sim.advance_time(2)
    vent = sim.state.equipment["VENT-1"]
    assert vent.failed and "VENT-1" not in p.equipment
    assert "needs_ventilator" in p.stalled_reasons
    assert any(e["kind"] == "equipment_failure" for e in sim.active_events()["events"])
    with pytest.raises(EDError) as err:
        sim.act("allocate_equipment", equipment_id="VENT-1", patient_id=p.patient_id)
    assert _code(err) == "EQUIPMENT_UNAVAILABLE"

    sim.act("request_repair", equipment_id="VENT-1")
    assert sim.state.ledger["repairs"] == C.REPAIR_FEE
    assert vent.repair_at <= sim.state.minute + 90
    with pytest.raises(EDError) as err:
        sim.act("request_repair", equipment_id="VENT-1")
    assert _code(err) == "ALREADY_EXPEDITED"
    sim.advance_time(91)
    assert not vent.failed
    assert not any(e["kind"] == "equipment_failure" for e in sim.active_events()["events"])


def test_imaging_caps_progress_until_scan_and_ct_failure_requeues():
    sim = quiet_sim()
    p = add_patient(sim, acuity=3, imaging="ct", duration=100)
    start(sim, p, "GEN-1", "res-d1", "rn-d4")
    sim.advance_time(2)
    assert p.imaging_status == "scanning"
    inject_event(
        sim, "equipment_failure", sim.state.minute + 1, equipment_id="CT-1", downtime=600, estimate=600
    )
    sim.advance_time(100)
    assert p.imaging_status == "queued" and p.patient_id in sim.state.imaging_queue["ct"]
    assert p.work_done == pytest.approx(C.IMAGING_CAP * p.duration)
    assert "awaiting_imaging" in p.stalled_reasons


def test_bed_closure_closes_free_beds_now_and_occupied_beds_when_vacated():
    sim = quiet_sim()
    p = add_patient(sim, acuity=5, duration=5)
    start(sim, p, "FT-1", "res-d1", "rn-d4")
    inject_event(sim, "bed_closure", 1, bed_class="fast_track", count=4, duration=240)
    sim.advance_time(1)
    beds = sim.state.beds
    assert beds["FT-2"].state(sim.state.minute) == "closed"
    assert beds["FT-1"].close_pending_until is not None
    q = add_patient(sim, acuity=5)
    with pytest.raises(EDError) as err:
        start(sim, q, "FT-2", "res-d2", "rn-d5")
    assert _code(err) == "BED_UNAVAILABLE"
    sim.advance_time(10)
    sim.act("discharge_patient", patient_ids=[p.patient_id])
    assert beds["FT-1"].state(sim.state.minute) == "closed"


# --- staffing --------------------------------------------------------------------------------
def test_sick_staff_member_hands_over_and_patient_stalls_until_reassigned():
    sim = quiet_sim()
    p = add_patient(sim)
    start(sim, p, "GEN-1", "res-d1", "rn-d4")
    inject_event(
        sim, "staff_sickness", 5, staff_id="res-d1", variant="left_mid_shift", sick_from=5, sick_until=720
    )
    sim.advance_time(6)
    assert sim.state.staff["res-d1"].status == "sick"
    assert p.doctor_id is None and "no_doctor" in p.stalled_reasons
    sim.act("assign_staff", staff_id="res-d2", patient_ids=[p.patient_id])
    sim.advance_time(1)
    assert p.stalled_reasons == []


def test_shift_change_releases_day_staff_and_brings_night_staff_on():
    sim = quiet_sim()
    advance_to(sim, 600)
    p = add_patient(sim, duration=10_000)
    start(sim, p, "GEN-1", "res-d1", "rn-d4")
    advance_to(sim, 721)
    assert sim.state.staff["res-d1"].status == "off_duty"
    assert sim.state.staff["res-n1"].status == "on_duty"
    assert p.doctor_id is None and p.nurse_id is None
    assert {"no_doctor", "no_nurse"} <= set(p.stalled_reasons)


def test_extend_shift_keeps_staff_and_bills_overtime():
    sim = quiet_sim()
    advance_to(sim, 700)
    sim.act("extend_shift", staff_id="res-d1", hours=2)
    sim.advance_time(30)
    assert sim.state.staff["res-d1"].status == "on_duty"
    assert sim.state.ledger["overtime"] == pytest.approx(10 * C.WAGE_PER_HOUR["resident"] * 1.5 / 60)
    with pytest.raises(EDError) as err:
        sim.act("extend_shift", staff_id="res-d1", hours=3)
    assert _code(err) == "SHIFT_LIMIT"


def test_agency_staff_arrive_after_lead_time_and_daily_limit_applies():
    sim = quiet_sim()
    result = sim.act("request_temporary_staff", role="nurse", hours=8)
    staff_id = result["staff_id"]
    assert sim.state.ledger["agency"] == C.AGENCY_CALLOUT_FEE
    sim.advance_time(C.LEAD_TIME_MINUTES - 1)
    assert sim.state.staff[staff_id].status == "off_duty"
    sim.advance_time(1)
    assert sim.state.staff[staff_id].status == "on_duty"
    for _ in range(sim.state.config.agency_daily_limit - 1):
        sim.act("request_temporary_staff", role="resident", hours=4)
    with pytest.raises(EDError) as err:
        sim.act("request_temporary_staff", role="resident", hours=4)
    assert _code(err) == "LIMIT_REACHED"


def test_triage_nurse_triages_ambulances_first():
    sim = quiet_sim()
    walk_in = add_patient(sim, triaged=False, mode="walk_in", arrival=0)
    ambulance = add_patient(sim, triaged=False, mode="ambulance", arrival=0)
    sim.advance_time(1)  # triage assignment happens at the start of the next minute
    assert sim.state.staff["rn-d7"].triaging == ambulance.patient_id
    sim.advance_time(10)
    assert ambulance.triaged and ambulance.triage_min < (walk_in.triage_min or 10**6)
    assert sim.patient(ambulance.patient_id)["acuity"] == ambulance.acuity


def test_no_triage_nurse_means_no_triage():
    sim = quiet_sim()
    sim.act("set_staff_zone", staff_id="rn-d7", zone="floor")
    p = add_patient(sim, triaged=False)
    sim.advance_time(30)
    assert not p.triaged
    assert "no nurse is working in triage" in sim.department_status()["alerts"]


# --- fatigue -----------------------------------------------------------------------------------
def test_fatigue_rises_faster_with_load_and_recovers_on_break():
    sim = quiet_sim()
    staff = sim.state.staff
    busy, idle = staff["rn-d1"], staff["rn-d2"]
    busy.fatigue = idle.fatigue = 20.0
    p = add_patient(sim, acuity=1, complaint="chest_pain")
    start(sim, p, "RESUS-1", "att-d1", "rn-d1")
    sim.advance_time(60)
    assert busy.fatigue > idle.fatigue > 20.0
    level = idle.fatigue
    sim.act("schedule_break", staff_id="rn-d2", minutes=30)
    sim.advance_time(30)
    assert idle.fatigue < level and idle.status == "on_duty"


def test_off_duty_staff_recover_and_tired_staff_slow_treatment():
    sim = quiet_sim()
    night = sim.state.staff["att-n1"]
    night.fatigue = 50.0
    sim.advance_time(60)
    assert night.fatigue == pytest.approx(50.0 - 60 * C.FATIGUE_REST_RECOVERY)
    p = add_patient(sim, duration=1000)
    start(sim, p, "GEN-1", "res-d1", "rn-d4")
    sim.state.staff["res-d1"].fatigue = 100.0
    sim.advance_time(10)
    assert p.work_done == pytest.approx(10 * rules.speed_factor(100.0))


# --- budget ------------------------------------------------------------------------------------
def test_wages_supplies_and_budget_cut():
    sim = quiet_sim()
    sim.advance_time(60)
    day_hourly = 2 * 140 + 2 * 75 + 7 * 50
    assert sim.state.ledger["wages"] == pytest.approx(day_hourly)
    inject_event(sim, "supply_shortage", 61, duration=720, multiplier=1.6)
    inject_event(sim, "budget_cut", 61, fraction=0.1)
    sim.advance_time(1)
    p = add_patient(sim, acuity=3)
    start(sim, p, "GEN-1", "res-d1", "rn-d4")
    sim.advance_time(1)
    assert sim.state.ledger["supplies"] == pytest.approx(C.SUPPLY_COST[3] * 1.6)
    assert sim.state.budget == pytest.approx(sim.state.initial_budget * 0.9)
    assert sim.budget_status()["remaining"] == pytest.approx(sim.state.budget - sim.state.spent, abs=0.01)


# --- waiting times and outcomes ------------------------------------------------------------------
def test_waiting_and_door_to_treatment_minutes():
    sim = quiet_sim()
    p = add_patient(sim, arrival=0)
    sim.advance_time(30)
    assert sim.patient(p.patient_id)["waiting_minutes"] == 30
    start(sim, p, "GEN-1", "res-d1", "rn-d4")
    sim.advance_time(1)
    detail = sim.patient(p.patient_id)
    assert detail["door_to_treatment_minutes"] == 30
    assert detail["waiting_minutes"] is None


def test_untreated_urgent_patient_deteriorates_then_has_a_critical_event():
    sim = quiet_sim()
    p = add_patient(sim, acuity=2, complaint="chest_pain", thresholds=[0.05] * 8)
    sim.advance_time(120)
    assert p.deteriorations == 2 and p.status == "critical_event"
    kinds = [e["kind"] for e in sim.state.log if e.get("patient_id") == p.patient_id]
    assert "patient_deteriorated" in kinds and "critical_event" in kinds
    assert sim.state.acc["critical_events"] == 1


def test_active_treatment_carries_far_less_risk_than_waiting():
    sim = quiet_sim()
    waiting = add_patient(sim, acuity=2, complaint="chest_pain")
    treated = add_patient(sim, acuity=2, complaint="chest_pain", duration=10_000)
    start(sim, treated, "MON-1", "att-d1", "rn-d1")
    sim.advance_time(60)
    assert treated.hazard < waiting.hazard / 10


def test_deterioration_upgrades_requirements_and_can_strand_a_patient_in_the_wrong_bed():
    sim = quiet_sim()
    p = add_patient(sim, acuity=3, complaint="abdominal_pain", duration=10_000, thresholds=[0.0, 1e9])
    start(sim, p, "GEN-1", "res-d1", "rn-d4")
    sim.advance_time(2)
    assert p.acuity == 2
    assert "bed_incompatible" in p.stalled_reasons and "nurse_not_qualified" in p.stalled_reasons


def test_low_acuity_patient_leaves_without_being_seen_even_if_parked_in_a_bed():
    sim = quiet_sim()
    parked = add_patient(sim, acuity=4, patience_z=-10.0)  # patience of about one minute
    treated = add_patient(sim, acuity=4, patience_z=-10.0, duration=10_000)
    sim.act("assign_bed", patient_id=parked.patient_id, bed_id="GEN-1")
    start(sim, treated, "GEN-2", "res-d1", "rn-d4")
    sim.advance_time(5)
    assert parked.status == "lwbs" and parked.bed_id is None
    assert treated.status == "in_treatment"


def test_diversion_turns_away_ambulances_but_not_major_incident_casualties():
    sim = quiet_sim()
    sim.act("set_diversion", active=True)
    ambulance = add_patient(sim, mode="ambulance", arrival=5, triaged=False)
    walk_in = add_patient(sim, mode="walk_in", arrival=5, triaged=False)
    incident = add_patient(sim, mode="ambulance", arrival=5, triaged=False)
    incident.incident_id = "EV-X"
    for patient in (ambulance, walk_in, incident):
        del sim.state.patients[patient.patient_id]
    sim.state.future_patients = [ambulance, walk_in, incident]
    sim.advance_time(6)
    assert ambulance.status == "diverted"
    assert walk_in.status in ("awaiting_triage", "waiting")
    assert incident.status == "waiting" and incident.triaged
    with pytest.raises(EDError) as err:
        sim.patient(ambulance.patient_id)
    assert _code(err) == "NOT_FOUND"
