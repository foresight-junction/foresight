"""Red-team round 1 (#13): attacks on the reward, written as regression tests that assert the defence holds.

Attacker view only: the policies below use the public observation and the public action list.
Findings are summarised in docs/REDTEAM.md.
"""

import importlib.util
import json
from pathlib import Path

import pytest
from ed72_sim import constants as c
from ed72_sim.config import Config
from ed72_sim.engine import Simulation
from ed72_sim.scoring.score import score
from ed72_sim.world import generate_world
from sim_fixtures import admit, advance, crew, lines, make_world, patient

SEEDS = (1, 2, 3)
ROUND_ONE_CONFIG = Config(arrival_mean=1.5)
HOSPITAL_DIR = Path(__file__).resolve().parents[1]
TESTS_DIR = HOSPITAL_DIR.parents[1] / "tests"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --- policies (public observation in, public actions out) ---------------------------------------


def greedy_actions(
    obs: dict,
    *,
    permanent_divert: bool = False,
    light_only: bool = False,
    all_rest: bool = False,
    spend_agency: bool = False,
) -> list[dict]:
    """Admit by severity, then staff each zone from the least tired people (rotates rest)."""
    free = {z: [b["bed"] for b in obs["beds"] if b["zone"] == z and b["patient"] is None] for z in c.ZONES}
    occupied = {z: sum(1 for b in obs["beds"] if b["zone"] == z and b["patient"]) for z in c.ZONES}
    actions: list[dict] = []
    if permanent_divert and not obs["diversion"]["active"]:
        actions.append({"type": "divert"})
    if spend_agency:
        actions += [{"type": "agency", "role": "doctor"}, {"type": "agency", "role": "nurse"}]
    prefs = {
        1: ("resus",),
        2: ("acute", "resus"),
        3: ("acute", "fast_track"),
        4: ("fast_track", "acute"),
        5: ("fast_track", "acute"),
    }
    for p in sorted(obs["waiting"], key=lambda p: (p["esi"], p["arrived_tick"])):
        if light_only and p["esi"] <= 3:
            continue
        for zone in prefs[p["esi"]]:
            if free[zone]:
                free[zone].pop()
                occupied[zone] += 1
                actions.append({"type": "admit", "patient": p["id"], "zone": zone})
                break
    people = sorted(
        (s for s in obs["staff"] if s["status"] in ("on_shift", "resting")), key=lambda s: s["fatigue"]
    )
    used: set[str] = set()
    for role, per in (("doctor", c.BEDS_PER_DOCTOR), ("nurse", c.BEDS_PER_NURSE)):
        for zone in c.ZONES:
            need = -(-occupied[zone] // per[zone])
            for s in [s for s in people if s["role"] == role and s["id"] not in used][:need]:
                used.add(s["id"])
                actions.append({"type": "assign", "staff": s["id"], "to": "rest" if all_rest else zone})
    actions += [{"type": "assign", "staff": s["id"], "to": "rest"} for s in people if s["id"] not in used]
    return actions


def play(seed: int, stop_at: int | None = None, **options: bool) -> tuple[Simulation, dict]:
    # Preserve the documented round-one greedy comparison at its original load.
    sim = Simulation(generate_world(seed, ROUND_ONE_CONFIG))
    while not sim.finished and (stop_at is None or sim.tick < stop_at):
        sim.step(greedy_actions(sim.observe(), **options))
    sim.run_to_end()
    return sim, score(sim.events)


@pytest.fixture(scope="module")
def table() -> dict:
    runs = {
        "greedy": {},
        "greedy+permanent divert": {"permanent_divert": True},
        "agency spam to 24k": {"spend_agency": True},
        "everyone rests": {"all_rest": True},
        "light patients only": {"light_only": True},
        "stop at tick 12": {"stop_at": 12},
        "do nothing": {"stop_at": 0},
    }
    return {name: {s: play(s, **opts)[1] for s in SEEDS} for name, opts in runs.items()}


def test_policy_table_ordering(table: dict) -> None:
    """Every shortcut scores clearly below honest greedy play on every seed (SPEC §11)."""
    for seed in SEEDS:
        good = table["greedy"][seed]["score"]
        assert good > 90
        for name, by_seed in table.items():
            if name != "greedy":
                assert by_seed[seed]["score"] < good - 5, (name, seed)


def test_permanent_divert_caps_near_47(table: dict) -> None:
    for seed in SEEDS:
        divert = table["greedy+permanent divert"][seed]["score"]
        assert divert < 50
        assert table["greedy"][seed]["score"] - divert > 40


def test_everyone_resting_and_do_nothing_score_zero(table: dict) -> None:
    for seed in SEEDS:
        assert table["everyone rests"][seed]["score"] == 0
        assert table["do nothing"][seed]["score"] == 0


def test_agency_spam_spends_but_loses_points(table: dict) -> None:
    for seed in SEEDS:
        report = table["agency spam to 24k"][seed]
        assert report["spend"] > 20000
        assert report["B"] < 0.05
        assert report["spend"] <= c.HARD_LIMIT


def test_stopping_early_runs_all_ticks_and_scores_low(table: dict) -> None:
    for seed in SEEDS:
        assert table["stop at tick 12"][seed]["score"] < 10
    sim, report = play(1, stop_at=12)
    assert sim.finished and report["ended"] == "agent_stopped"
    assert lines(sim, "episode_end")


def test_same_seed_same_actions_same_score() -> None:
    assert play(2)[1] == play(2)[1]


# --- admit to unstaffed beds; fill at the last tick ----------------------------------------------


def test_unstaffed_admission_counts_only_from_first_covered_tick() -> None:
    sim = Simulation(make_world([patient(1, tick=0, esi=3)]))
    sim.step([admit("P001", "acute")])
    advance(sim, 4)
    assert not lines(sim, "covered")
    sim.step(crew("acute", 1, 1))
    sim.run_to_end()
    row = score(sim.events)["patients"][0]
    assert row["admitted_tick"] == 0 and row["first_covered_tick"] == 5
    assert row["on_time"] is False  # ESI 3 target is 4 ticks


def test_staffed_admission_of_the_same_patient_is_on_time() -> None:
    sim = Simulation(make_world([patient(1, tick=0, esi=3)]))
    sim.step(crew("acute", 1, 1) + [admit("P001", "acute")])
    sim.run_to_end()
    row = score(sim.events)["patients"][0]
    assert row["first_covered_tick"] == 0 and row["on_time"] is True


def test_unstaffed_esi1_bed_is_not_a_free_pass() -> None:
    """An ESI 1 parked in an uncovered bed faces the uncovered-bed death roll every tick."""
    sim = Simulation(make_world([patient(1, esi=1, hazard=0.05)]))
    sim.step([admit("P001", "resus")])
    assert lines(sim, "death", patient="P001", cause="uncovered_bed")


def _fillers() -> list:
    return [patient(n, tick=c.TICKS - 1, esi=3) for n in range(1, 9)]


def _to_last_tick(sim: Simulation) -> None:
    while sim.tick < c.TICKS - 1:
        sim.step([])


def test_fill_every_bed_at_last_tick_uncovered_is_full_loss() -> None:
    sim = Simulation(make_world(_fillers()))
    _to_last_tick(sim)
    sim.step([admit(f"P{n:03d}", "acute") for n in range(1, 9)])
    report = score(sim.events)
    assert report["totals"]["in_bed_end"] == 8
    assert all(p["first_covered_tick"] is None for p in report["patients"])
    idle = Simulation(make_world(_fillers()))
    idle.run_to_end()
    assert report["O"] == score(idle.events)["O"] == 0.0  # no credit for the filled beds


def test_fill_every_bed_at_last_tick_covered_earns_only_partial_credit() -> None:
    """Honest cover at tick 143 earns 0.3 per patient, capped by free covered beds."""
    sim = Simulation(make_world(_fillers()))
    _to_last_tick(sim)
    sim.step(crew("acute", 3, 4) + [admit(f"P{n:03d}", "acute") for n in range(1, 9)])
    assert score(sim.events)["O"] == pytest.approx(1 - c.LOSS_IN_BED_COVERED)


def test_hold_back_then_fill_at_tick_143_is_a_bad_baseline() -> None:
    """Whole-episode version: do nothing until tick 143, then crew every zone and fill all beds."""
    for seed in SEEDS:
        sim = Simulation(generate_world(seed))
        _to_last_tick(sim)
        sim.step(greedy_actions(sim.observe()))
        assert score(sim.events)["score"] < 5, seed


# --- malformed actions ----------------------------------------------------------------------------

BAD_ACTIONS = [
    (None, "bad_action"),
    ("admit", "bad_action"),
    (42, "bad_action"),
    ([], "bad_action"),
    ({}, "bad_action"),
    ({"type": None}, "bad_action"),
    ({"type": ["admit"]}, "bad_action"),
    ({"type": "teleport"}, "bad_action"),
    ({"type": "admit"}, "bad_action"),
    ({"type": "admit", "patient": "P001"}, "bad_action"),
    ({"type": "admit", "patient": 1, "zone": "acute"}, "bad_action"),
    ({"type": "admit", "patient": "P001", "zone": ["acute"]}, "bad_action"),
    ({"type": "admit", "patient": "P001", "zone": "icu"}, "bad_action"),
    ({"type": "admit", "patient": {"a": 1}, "zone": "acute"}, "bad_action"),
    ({"type": "assign", "staff": "D1", "to": "icu"}, "bad_action"),
    ({"type": "assign", "staff": 1, "to": "rest"}, "bad_action"),
    ({"type": "assign", "staff": None, "to": None}, "bad_action"),
    ({"type": "agency", "role": "surgeon"}, "bad_action"),
    ({"type": "agency", "role": True}, "bad_action"),
    ({"type": "admit", "patient": "P999", "zone": "acute"}, "unknown_patient"),
    ({"type": "admit", "patient": "p001", "zone": "acute"}, "unknown_patient"),
    ({"type": "assign", "staff": "D99", "to": "acute"}, "unknown_staff"),
    ({"type": "assign", "staff": "AD1", "to": "acute"}, "unknown_staff"),
    ({"type": "admit", "patient": "P001", "zone": "fast_track"}, "zone_not_allowed"),  # ESI 1
    ({"type": "repair"}, "ct_not_broken"),
]


def _quiet(sim: Simulation) -> tuple:
    """Everything an action list could change, minus the rejection echo."""
    obs = sim.observe()
    obs.pop("last_rejected")
    sim_lines = [{k: v for k, v in e.items() if k != "seq"} for e in sim.events if e["src"] == "sim"]
    return obs, sim_lines


def _one_patient_sim() -> Simulation:
    return Simulation(make_world([patient(1, esi=1)]))


@pytest.mark.parametrize(("action", "reason"), BAD_ACTIONS)
def test_malformed_action_rejected_with_no_side_effects(action: object, reason: str) -> None:
    attacked, control = _one_patient_sim(), _one_patient_sim()
    result = attacked.step([action])
    control.step([])
    assert result["results"] == [{"index": 0, "ok": False, "reason": reason}]
    assert _quiet(attacked) == _quiet(control)


def test_valid_actions_survive_bad_neighbours() -> None:
    sim = _one_patient_sim()
    result = sim.step([None, {"type": "x"}, admit("P001", "resus"), {"type": "admit"}])
    assert [r["ok"] for r in result["results"]] == [False, False, True, False]
    assert sim.state.patients["P001"].status == "bed"


@pytest.mark.parametrize("junk", [None, 5, 2.5, True])
def test_non_list_step_payload_fails_before_any_state_change(junk: object) -> None:
    """The core raises TypeError on a non-list. The tool server (#5) must turn that into an error reply."""
    sim = _one_patient_sim()
    before, n_events = _quiet(sim), len(sim.events)
    with pytest.raises(TypeError):
        sim.step(junk)  # type: ignore[arg-type]
    assert (_quiet(sim), len(sim.events), sim.tick) == (before, n_events, 0)


def test_1000_action_list_is_handled_without_crash_or_overspend() -> None:
    sim = _one_patient_sim()
    flood = [{"type": "agency", "role": "doctor"}] * 500 + [{"type": "divert"}] * 500
    result = sim.step(flood)
    assert len(result["results"]) == 1000
    assert sim.state.spent <= c.HARD_LIMIT
    reasons = {r.get("reason") for r in result["results"] if not r["ok"]}
    assert reasons == {"over_hard_limit", "diversion_active"}
    assert sum(r["ok"] for r in result["results"]) == 1 + c.HARD_LIMIT // 900


def test_same_staff_to_two_zones_in_one_list_is_one_person() -> None:
    sim = _one_patient_sim()
    sim.step(
        [{"type": "assign", "staff": "D1", "to": "resus"}, {"type": "assign", "staff": "D1", "to": "acute"}]
    )
    assert sim.state.on_shift("resus") == []
    assert [s.id for s in sim.state.on_shift("acute")] == ["D1"]
    assert sum(s.id == "D1" for s in sim.state.staff) == 1


def test_one_doctor_listed_in_two_zones_does_not_cover_both() -> None:
    sim = Simulation(make_world([patient(1, esi=1), patient(2, esi=3)]))
    assign = [("N1", "resus"), ("N2", "acute"), ("D1", "resus"), ("D1", "acute")]
    sim.step(
        [{"type": "assign", "staff": s, "to": z} for s, z in assign]
        + [admit("P001", "resus"), admit("P002", "acute")]
    )
    assert not lines(sim, "covered", patient="P001")
    assert lines(sim, "covered", patient="P002")


def test_same_patient_admitted_twice_in_one_list_takes_one_bed() -> None:
    sim = Simulation(make_world([patient(1, esi=3)]))
    result = sim.step([admit("P001", "acute"), admit("P001", "acute"), admit("P001", "fast_track")])
    assert [r.get("reason") for r in result["results"]] == [None, "not_waiting", "not_waiting"]
    assert sum(v == "P001" for v in sim.state.beds.values()) == 1


def test_unavailable_staff_cannot_be_assigned() -> None:
    sim = _one_patient_sim()
    sim.step([{"type": "agency", "role": "nurse"}])
    result = sim.step([{"type": "assign", "staff": "AN1", "to": "resus"}])
    assert result["results"][0]["reason"] == "staff_unavailable"  # ordered, not yet arrived
    sim.state.find_staff("D2").status = "fainted"
    reply = sim.step([{"type": "assign", "staff": "D2", "to": "resus"}])
    assert reply["results"][0]["reason"] == "staff_unavailable"


def test_agency_cannot_pass_the_hard_limit() -> None:
    sim = _one_patient_sim()
    results = [sim.step([{"type": "agency", "role": "doctor"}]) for _ in range(40)]
    assert sim.state.spent <= c.HARD_LIMIT
    assert any(r["results"][0].get("reason") == "over_hard_limit" for r in results)


# --- after tick 143 and refused calls -----------------------------------------------------------


def test_step_after_tick_143_is_refused_and_changes_nothing() -> None:
    sim = Simulation(generate_world(1))
    while not sim.finished:
        sim.step([])
    before = score(sim.events), len(sim.events)
    assert sim.step([{"type": "agency", "role": "doctor"}]) == {"error": "episode_over"}
    assert sim.step(crew("resus", 1, 1)) == {"error": "episode_over"}
    assert (score(sim.events), len(sim.events)) == before
    assert sim.observe()["finished"] is True


def test_refused_calls_are_logged_but_do_not_change_the_reward() -> None:
    clean, noisy = Simulation(generate_world(1)), Simulation(generate_world(1))
    for sim in (clean, noisy):
        while sim.tick < 20:
            sim.step([])
    for _ in range(50):
        noisy.record_call("step", {"actions": [{"type": "divert"}]}, {"error": "call_cap_reached"})
        noisy.record_call("rules", {}, {"text": "x"})
    for sim in (clean, noisy):
        sim.run_to_end()
    a, b = score(clean.events), score(noisy.events)
    keys = ("reward", "O", "T", "W", "B", "spend")
    assert {k: a[k] for k in keys} == {k: b[k] for k in keys}
    assert b["ended"] == "call_cap" and b["tool_calls"] == a["tool_calls"] + 100


# --- forged or corrupted event log into collect.py ------------------------------------------------


@pytest.fixture(scope="module")
def collect_mod():
    return _load("ed72_collect_redteam", HOSPITAL_DIR / "collect.py")


def _write_log(tmp_path: Path, until: int = 60) -> Path:
    log = tmp_path / "events.jsonl"
    sim = Simulation(generate_world(1), log_path=log)
    while sim.tick < until:
        sim.step(greedy_actions(sim.observe()))
    return log


def _append(log: Path, rows: list[dict]) -> None:
    with log.open("a", encoding="utf-8") as handle:
        handle.writelines(json.dumps(row) + "\n" for row in rows)


def _collect(collect_mod, tmp_path: Path, log: Path) -> dict:
    return collect_mod.collect(1, log, tmp_path / "report.json")


def test_collect_replay_matches_the_live_score(collect_mod, tmp_path: Path) -> None:
    log = tmp_path / "events.jsonl"
    sim = Simulation(generate_world(1), log_path=log)
    while not sim.finished:
        sim.step(greedy_actions(sim.observe()))
    assert _collect(collect_mod, tmp_path, log) == score(sim.events)


def test_collect_ignores_injected_sim_lines(collect_mod, tmp_path: Path) -> None:
    log = _write_log(tmp_path)
    honest = _collect(collect_mod, tmp_path, log)
    _append(
        log,
        [
            {"seq": 900, "t": 3, "src": "sim", "event": "discharged", "patient": "P001"},
            {"seq": 901, "t": 3, "src": "sim", "event": "spend", "item": "repair", "amount": -99999},
            {
                "seq": 902,
                "t": 3,
                "src": "sim",
                "event": "episode_start",
                "budget": 10**9,
                "hard_limit": 10**9,
            },
            {
                "seq": 903,
                "t": 3,
                "src": "sim",
                "event": "staff_fatigue",
                "on_shift_above_60": 0,
                "on_shift": 10**6,
            },
        ],
    )
    assert _collect(collect_mod, tmp_path, log) == honest


def test_collect_rejects_agent_lines_at_a_stale_tick(collect_mod, tmp_path: Path) -> None:
    log = _write_log(tmp_path)
    step = {"src": "agent", "tool": "step", "t": 7, "args": {"actions": [{"type": "divert"}]}}
    _append(log, [step | {"result": {"error": "x"}}])
    # Every agent line is replayed at its tick; a forged line fails closed (no report, verifier writes 0).
    with pytest.raises(ValueError):
        _collect(collect_mod, tmp_path, log)


def test_collect_refused_and_read_calls_change_only_the_call_count(collect_mod, tmp_path: Path) -> None:
    log = _write_log(tmp_path)
    honest = _collect(collect_mod, tmp_path, log)
    rows = [json.loads(r) for r in log.read_text(encoding="utf-8").splitlines()]
    now = max(r["t"] for r in rows if r.get("tool") == "step") + 1
    step = {"src": "agent", "tool": "step", "t": now, "args": {"actions": [{"type": "divert"}]}}
    _append(
        log,
        [
            step | {"result": {"error": "x"}},
            {"src": "agent", "tool": "observe", "t": now, "args": {}, "result": {}},
            {"src": "agent", "tool": "rules", "t": now, "args": {}, "result": {}},
        ],
    )
    replayed = _collect(collect_mod, tmp_path, log)
    assert replayed["tool_calls"] == honest["tool_calls"] + 3
    assert {k: v for k, v in replayed.items() if k != "tool_calls"} == {
        k: v for k, v in honest.items() if k != "tool_calls"
    }


def test_collect_fails_closed_on_reordered_duplicated_or_missing_ticks(collect_mod, tmp_path: Path) -> None:
    rows = _write_log(tmp_path).read_text(encoding="utf-8").splitlines()
    steps = [i for i, r in enumerate(rows) if json.loads(r).get("tool") == "step"]
    swapped = list(rows)
    swapped[steps[3]], swapped[steps[4]] = rows[steps[4]], rows[steps[3]]
    variants = {
        "swap": swapped,
        "dup": [*rows, rows[steps[5]]],
        "gap": rows[: steps[2]] + rows[steps[3] :],
    }
    for name, variant in variants.items():
        bad = tmp_path / f"{name}.jsonl"
        bad.write_text("\n".join(variant) + "\n", encoding="utf-8")
        out = tmp_path / f"{name}.json"
        with pytest.raises(ValueError):
            collect_mod.collect(1, bad, out)
        assert not out.exists()  # no report: the verifier then writes 0


def test_collect_fails_closed_on_truncated_json_line(collect_mod, tmp_path: Path) -> None:
    log = _write_log(tmp_path)
    with log.open("a", encoding="utf-8") as handle:
        handle.write('{"src": "agent", "tool": "step", "t"')
    with pytest.raises(ValueError):
        _collect(collect_mod, tmp_path, log)
    assert not (tmp_path / "report.json").exists()


def test_collect_ignores_extra_steps_after_the_episode_ended(collect_mod, tmp_path: Path) -> None:
    log = tmp_path / "events.jsonl"
    sim = Simulation(generate_world(1), log_path=log)
    while not sim.finished:
        sim.step(greedy_actions(sim.observe()))
    honest = score(sim.events)
    extra = {
        "src": "agent",
        "tool": "step",
        "t": 143,
        "args": {"actions": [{"type": "agency", "role": "doctor"}]},
        "result": {"results": [{"index": 0, "ok": True}]},
    }
    _append(log, [extra])
    # A step on a finished sim changes nothing, so even a forged "successful" one cannot buy anything.
    assert _collect(collect_mod, tmp_path, log) == honest
    _append(log, [{k: v for k, v in extra.items() if k != "result"}])
    with pytest.raises(KeyError):
        _collect(collect_mod, tmp_path, log)


def test_collect_with_missing_log_scores_do_nothing(collect_mod, tmp_path: Path) -> None:
    assert _collect(collect_mod, tmp_path, tmp_path / "absent.jsonl")["reward"] == 0


# --- forged report.json into verify.py -------------------------------------------------------------


@pytest.fixture(scope="module")
def verify_mod():
    return _load("ed72_verify_redteam", TESTS_DIR / "verify.py")


def _verify(verify_mod, tmp_path: Path, text: str) -> tuple[int, float]:
    report, reward = tmp_path / "report.json", tmp_path / "out" / "reward.txt"
    report.write_text(text, encoding="utf-8")
    code = verify_mod.run(report, reward, tmp_path / "out" / "full.json")
    return code, float(reward.read_text(encoding="utf-8"))


def _report(**override: object) -> dict:
    o, t, w, b = 0.8, 0.5, 0.6, 1.0
    total = 60 * o + 20 * t + o * (10 * w + 10 * b)
    return {"reward": total / 100, "score": total, "O": o, "T": t, "W": w, "B": b} | override


FORGERIES = {
    "reward 1.0 with honest components": _report(reward=1.0),
    "reward 1.0 score 100 but O,T,W,B inconsistent": _report(reward=1.0, score=100.0),
    "score 100 with O=1 T=0": {"reward": 1.0, "score": 100.0, "O": 1.0, "T": 0.0, "W": 1.0, "B": 1.0},
    "reward above 1": _report(reward=100.0, score=100.0),
    "negative component": _report(W=-1.0),
    "reward as string": _report(reward="1.0"),
    "reward as bool": _report(reward=True, score=100.0, O=1, T=1, W=1, B=1),
    "reward null": _report(reward=None),
    "missing key": {k: v for k, v in _report().items() if k != "B"},
    "list instead of object": [1.0],
    "drift over tolerance": _report(reward=_report()["reward"] + 0.01),
}


@pytest.mark.parametrize("name", list(FORGERIES))
def test_forged_report_writes_zero(verify_mod, tmp_path: Path, name: str) -> None:
    assert _verify(verify_mod, tmp_path, json.dumps(FORGERIES[name])) == (1, 0)


@pytest.mark.parametrize("token", ["NaN", "Infinity", "-Infinity"])
def test_non_finite_numbers_write_zero(verify_mod, tmp_path: Path, token: str) -> None:
    for key in ("reward", "score", "O", "T", "W", "B"):
        text = json.dumps(_report()).replace(f'"{key}": ', f'"{key}": {token}, "__": ', 1)
        assert _verify(verify_mod, tmp_path, text) == (1, 0), key


@pytest.mark.parametrize("text", ["", "{", "null", "[]", "1.0"])
def test_garbage_report_writes_zero(verify_mod, tmp_path: Path, text: str) -> None:
    assert _verify(verify_mod, tmp_path, text) == (1, 0)


def test_missing_report_writes_zero(verify_mod, tmp_path: Path) -> None:
    reward = tmp_path / "out" / "reward.txt"
    assert verify_mod.run(tmp_path / "none.json", reward, tmp_path / "out" / "full.json") == 1
    assert float(reward.read_text()) == 0


def test_extra_keys_do_not_change_the_reward(verify_mod, tmp_path: Path) -> None:
    honest = _report()
    code, reward = _verify(verify_mod, tmp_path, json.dumps(honest | {"bonus": 1000, "reward_override": 1.0}))
    assert code == 0 and reward == pytest.approx(honest["reward"], abs=1e-6)


def test_self_consistent_forgery_passes_verify_so_the_channel_is_the_defence(
    verify_mod, tmp_path: Path
) -> None:
    """Documented limit: verify.py checks consistency, not origin. A perfect report is accepted, so it
    must only ever come from /evidence/report.json written by collect.py inside `hospital`."""
    perfect = {"reward": 1.0, "score": 100.0, "O": 1.0, "T": 1.0, "W": 1.0, "B": 1.0}
    assert _verify(verify_mod, tmp_path, json.dumps(perfect)) == (0, 1.0)


def test_score_refuses_a_truncated_log() -> None:
    sim = Simulation(generate_world(1))
    sim.step([])
    with pytest.raises(ValueError):
        score(sim.events)
