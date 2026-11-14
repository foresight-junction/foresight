"""All data here is SYNTHETIC: hand-made score objects and logs, not agent results."""

import json
import xml.etree.ElementTree as ET

import pytest
from ed72_analysis import report, tables, trajectories
from ed72_analysis.loading import Run, parse_run_arg
from ed72_analysis.svg import failures_svg


def _patient(pid: str, esi: int, outcome: str, covered: int | None = None) -> dict:
    return {
        "id": pid,
        "esi": esi,
        "outcome": outcome,
        "arrived_tick": 1,
        "admitted_tick": None,
        "first_covered_tick": covered,
        "on_time": False,
        "failure_codes": [],
    }


def _score(failures: dict, patients: list[dict], score: float = 50.0, deaths: int = 1) -> dict:
    return {
        "score": score,
        "O": 0.5,
        "T": 0.25,
        "W": 1.0,
        "B": 1.0,
        "spend": 1000,
        "totals": {"died": deaths, "faints": 2},
        "patients": patients,
        "failures": failures,
        "ended": "tick_143",
    }


PATIENTS = [
    _patient("P001", 1, "died"),
    _patient("P002", 2, "never_admitted"),
    _patient("P003", 3, "discharged"),
    _patient("P004", 5, "died"),
    _patient("P005", 1, "died"),
]
FAILURES = {"F1": 3, "F7": 1}

EVENTS = [
    {"seq": 0, "t": 0, "src": "sim", "event": "episode_start", "budget": 12000, "hard_limit": 24000},
    {
        "seq": 1,
        "t": 1,
        "src": "sim",
        "event": "arrival",
        "patient": "P003",
        "esi": 3,
        "needs_ct": False,
        "source": "base",
    },
    {"seq": 2, "t": 1, "src": "sim", "event": "admitted", "patient": "P003", "zone": "resus", "bed": "R1"},
    {
        "seq": 3,
        "t": 2,
        "src": "sim",
        "event": "arrival",
        "patient": "P001",
        "esi": 1,
        "needs_ct": True,
        "source": "base",
    },
    {"seq": 4, "t": 2, "src": "agent", "tool": "step", "args": {"actions": []}, "result": {"results": []}},
    {"seq": 5, "t": 3, "src": "sim", "event": "upgrade", "patient": "P001", "esi": 1, "needs_ct": True},
    {"seq": 6, "t": 4, "src": "sim", "event": "death", "patient": "P001", "cause": "waiting"},
    {
        "seq": 7,
        "t": 5,
        "src": "sim",
        "event": "arrival",
        "patient": "P002",
        "esi": 2,
        "needs_ct": False,
        "source": "flu",
    },
    {"seq": 8, "t": 143, "src": "sim", "event": "episode_end"},
]


def _run(label: str = "opus/seed1", failures: dict | None = None, score: float = 50.0) -> Run:
    return Run(label, _score(FAILURES if failures is None else failures, PATIENTS, score))


def test_score_table_has_run_and_group_mean() -> None:
    table = tables.score_table([_run("opus/seed1", score=40.0), _run("opus/seed2", score=60.0), _run("gpt")])
    assert "| opus/seed1 | 40 |" in table
    assert "**opus mean (n=2)** | 50 |" in table
    assert "gpt mean" not in table  # a lone run has no mean row


def test_failure_table_marks_missing_codes_na() -> None:
    other = _run("b", failures={"F1": 2, "F2": 5})
    table = tables.failure_table([_run("a"), other])
    lines = table.splitlines()
    assert lines[0] == "| run | F1 | F2 | F7 |"
    assert lines[2] == "| a | 3 | n/a | 1 |"
    assert lines[3] == "| b | 2 | 5 | n/a |"
    assert "F3" not in table  # codes absent everywhere get no column


def test_esi_table_loss_share() -> None:
    lines = tables.esi_table(_run()).splitlines()
    esi1 = next(line for line in lines if line.startswith("| ESI 1"))
    # ESI1: two deaths weight 10 each = 20; ESI2 5; ESI5 0.5; discharged 0 -> total 25.5
    assert esi1.split(" | ")[1] == "2"
    assert esi1.rstrip(" |").endswith("78%")
    assert next(line for line in lines if line.startswith("| ESI 4")).rstrip(" |").endswith("0%")


def test_esi_share_is_na_without_loss() -> None:
    run = Run("x", _score({}, [_patient("P1", 3, "discharged")]))
    assert tables.esi_table(run).splitlines()[2].rstrip(" |").endswith("n/a")


def test_pick_patients_highest_weight_first_and_limit() -> None:
    picked = trajectories.pick_patients(_score(FAILURES, PATIENTS))
    assert [p["id"] for p in picked] == ["P001", "P005", "P002"]


def test_timeline_order_and_context() -> None:
    p = {"id": "P001", "outcome": "died"}
    lines = trajectories.timeline(EVENTS, p)
    assert [line.split(":")[0] for line in lines] == ["t2", "t3", "t4"]
    assert "arrived ESI 1" in lines[0]
    assert lines[2].endswith("died, cause waiting")


def test_timeline_shows_zone_occupancy_and_never_admitted() -> None:
    events = [
        *EVENTS[:3],
        {
            "seq": 9,
            "t": 6,
            "src": "sim",
            "event": "arrival",
            "patient": "P009",
            "esi": 2,
            "needs_ct": False,
            "source": "base",
        },
        {
            "seq": 10,
            "t": 9,
            "src": "sim",
            "event": "admitted",
            "patient": "P009",
            "zone": "resus",
            "bed": "R2",
        },
        EVENTS[-1],
    ]
    lines = trajectories.timeline(events, {"id": "P009", "outcome": "died"})
    assert "after 3 ticks waiting (1 other patients in resus)" in lines[1]
    lines = trajectories.timeline(EVENTS, {"id": "P002", "outcome": "never_admitted"})
    assert lines[-1] == "t143: episode ended, never admitted (138 ticks after arrival)"


def test_svg_is_well_formed_and_labelled() -> None:
    root = ET.fromstring(failures_svg([_run("a"), _run("b & c", failures={"F1": 1})]))
    text = " ".join(t.text or "" for t in root.iter("{http://www.w3.org/2000/svg}text"))
    assert "b & c" in text
    assert "4" in text


def test_parse_run_arg_rejects_bad_input() -> None:
    with pytest.raises(ValueError):
        parse_run_arg("no-equals-sign")


def test_cli_end_to_end(tmp_path) -> None:
    (tmp_path / "s1.json").write_text(json.dumps(_score(FAILURES, PATIENTS)))
    (tmp_path / "s2.json").write_text(json.dumps(_score({"F1": 1}, PATIENTS, score=70.0)))
    (tmp_path / "e1.jsonl").write_text("\n".join(json.dumps(e) for e in EVENTS) + "\n")
    out = tmp_path / "out"
    report.main(
        [
            "--run",
            f"opus/seed1={tmp_path / 's1.json'},{tmp_path / 'e1.jsonl'}",
            "--run",
            f"opus/seed2={tmp_path / 's2.json'}",
            "--out",
            str(out),
        ]
    )
    md = (out / "report.md").read_text()
    assert "opus mean (n=2)" in md
    assert "## Trajectory excerpts" in md
    assert "### opus/seed1" in md.split("## Trajectory excerpts")[1]
    assert "### opus/seed2" not in md.split("## Trajectory excerpts")[1]  # no log, no excerpts
    ET.parse(out / "failures.svg")
