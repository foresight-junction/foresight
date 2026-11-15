"""CI ordering test for the scripted baselines (issue #12, EVAL §5).

Plays every baseline in eval/baselines/ against the real sim on each shipped seed and scores it.
The reference checks import ed72/solution/ed72_reference.py and skip only if that file is missing.
"""

import importlib
import sys
from functools import cache
from pathlib import Path

import pytest

HOSPITAL = Path(__file__).resolve().parents[3]
REPO = Path(__file__).resolve().parents[6]
for path in (HOSPITAL, REPO / "eval" / "baselines", REPO / "ed72" / "solution"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

pytest.importorskip("ed72_sim.engine")
pytest.importorskip("ed72_sim.world")

from ed72_baselines import BASELINES, EXPLOITS
from ed72_baselines.sim_client import play

SHIPPED_SEEDS = (1, 2, 3)  # CI ordering seeds; a Harbor run's seed is ED72_SEED (docker-compose.yaml)
DIVERT_ALL_CAP = 50.0  # rulebook §13 says "about 47 points" at best; seed 2 measures 48.1
# The reference policy: ed72/solution/ed72_reference.py, class ReferencePolicy.
REFERENCE_MODULE = "ed72_reference"
SCRIPTED = sorted(set(BASELINES) - {"random"})


@cache
def events(name: str, seed: int) -> tuple[dict, ...]:
    return tuple(play(BASELINES[name](), seed))


def count(log: tuple[dict, ...], event: str) -> int:
    return sum(1 for e in log if e.get("event") == event)


def rejections(log: tuple[dict, ...]) -> list[str]:
    return [r["reason"] for e in log if e["src"] == "agent" for r in e["result"]["results"] if not r["ok"]]


def score(log: tuple[dict, ...] | list[dict]) -> float:
    scoring = pytest.importorskip("ed72_sim.scoring.score")
    return scoring.score(list(log))["score"]


@cache
def reference_score(seed: int) -> float:
    try:
        module = importlib.import_module(REFERENCE_MODULE)
    except ModuleNotFoundError:
        pytest.skip(f"reference policy module {REFERENCE_MODULE!r} not found in ed72/solution")
    return score(play(module.ReferencePolicy(), seed))


@pytest.mark.parametrize("name", sorted(BASELINES))
@pytest.mark.parametrize("seed", SHIPPED_SEEDS)
def test_baseline_plays_a_full_episode(seed: int, name: str) -> None:
    log = events(name, seed)
    assert log[-1]["event"] == "episode_end"
    assert "bad_action" not in rejections(log)


@pytest.mark.parametrize("name", SCRIPTED)
def test_scripted_baselines_send_only_valid_actions(name: str) -> None:
    assert rejections(events(name, SHIPPED_SEEDS[0])) == []


@pytest.mark.parametrize("seed", SHIPPED_SEEDS)
def test_do_nothing_admits_nobody(seed: int) -> None:
    assert count(events("do_nothing", seed), "admitted") == 0


@pytest.mark.parametrize("seed", SHIPPED_SEEDS)
def test_stop_early_discharges_fewer_than_reactive_proxy(seed: int) -> None:
    assert count(events("stop_early", seed), "discharged") < count(
        events("reactive_proxy", seed), "discharged"
    )


def test_same_seed_same_actions_same_log() -> None:
    seed = SHIPPED_SEEDS[0]
    assert play(BASELINES["reactive_proxy"](), seed) == play(BASELINES["reactive_proxy"](), seed)


@pytest.mark.parametrize("seed", SHIPPED_SEEDS)
def test_do_nothing_scores_zero(seed: int) -> None:
    assert score(events("do_nothing", seed)) == 0


@pytest.mark.parametrize("seed", SHIPPED_SEEDS)
def test_stop_early_below_reactive_proxy(seed: int) -> None:
    assert score(events("stop_early", seed)) < score(events("reactive_proxy", seed))


@pytest.mark.parametrize("seed", SHIPPED_SEEDS)
def test_divert_all_about_47_or_less(seed: int) -> None:
    assert score(events("divert_all", seed)) <= DIVERT_ALL_CAP


@pytest.mark.parametrize("seed", SHIPPED_SEEDS)
def test_reactive_proxy_below_reference(seed: int) -> None:
    assert score(events("reactive_proxy", seed)) < reference_score(seed)


@pytest.mark.parametrize("name", sorted(EXPLOITS))
@pytest.mark.parametrize("seed", SHIPPED_SEEDS)
def test_exploit_below_reference(seed: int, name: str) -> None:
    assert score(events(name, seed)) < reference_score(seed)
