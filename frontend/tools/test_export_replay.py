"""Replays are complete, internally consistent, and score what the scorer says.

Needs PYTHONPATH="ed72/environment/hospital;ed72/solution;eval/baselines" (':' off Windows).
"""

import json
from pathlib import Path

import pytest
from ed72_sim.engine import Simulation
from ed72_sim.scoring import score
from ed72_sim.world import generate_world

from export_replay import OUT_DIR, POLICIES, SHIPPED, TICKS, export, write_index, write_replay

SEED = 42
GEMINI_REAL_RUN = (
    Path(__file__).resolve().parents[2] / "eval/results/2026-11-14-gemini-seed42/score_full.json"
)


@pytest.fixture(scope="module", params=list(POLICIES))
def replay(request: pytest.FixtureRequest) -> dict:
    return export(request.param, SEED)


def test_one_tick_per_sim_tick(replay: dict) -> None:
    assert [t["tick"] for t in replay["ticks"]] == list(range(TICKS))
    assert all(t["obs"]["tick"] == t["tick"] for t in replay["ticks"])
    assert replay["final_obs"]["finished"]


def test_one_result_per_action(replay: dict) -> None:
    for t in replay["ticks"]:
        assert len(t["results"]) == len(t["actions"])
        assert [r["index"] for r in t["results"]] == list(range(len(t["actions"])))


def test_events_grouped_by_tick(replay: dict) -> None:
    for t in replay["ticks"]:
        assert all(e["t"] == t["tick"] and e["src"] == "sim" for e in t["events"])
    seqs = [e["seq"] for t in replay["ticks"] for e in t["events"]]
    assert seqs == sorted(seqs)
    events = [e["event"] for t in replay["ticks"] for e in t["events"]]
    assert events[0] == "episode_start" and events[-1] == "episode_end"


def test_reward_matches_scorer_on_replayed_actions(replay: dict) -> None:
    sim = Simulation(generate_world(replay["meta"]["seed"]))
    for t in replay["ticks"]:
        sim.step(t["actions"])
    sim.run_to_end()
    assert replay["meta"]["reward"] == score(sim.events)["reward"]


@pytest.mark.skip(
    reason="The Harbor run (0.8117) used the rules before main's load-4.0 and diversion-0.75 changes; "
    "the same script now scores 0.589. Re-enable against a Harbor run on the current rules."
)
def test_gemini_matches_real_run() -> None:
    real = json.loads(GEMINI_REAL_RUN.read_text(encoding="utf-8"))
    got = export("gemini", SEED)["meta"]["score"]
    assert got["reward"] == real["reward"]
    assert got["patients"] == real["patients"]


@pytest.mark.parametrize("name", SHIPPED)
def test_shipped_replays_are_current(name: str) -> None:
    shipped = json.loads((OUT_DIR / f"{name}-seed{SEED}.json").read_text(encoding="utf-8"))
    assert shipped == export(name, SEED)


def test_index_lists_reference_first(tmp_path: Path) -> None:
    for name in reversed(list(POLICIES)):
        write_replay(export(name, SEED), tmp_path)
    index = json.loads(write_index(tmp_path).read_text(encoding="utf-8"))
    assert [e["policy"] for e in index] == list(POLICIES)
    assert set(index[0]) == {"file", "label", "policy", "seed", "reward"}
    assert index[0]["file"] == f"reference-seed{SEED}.json"
