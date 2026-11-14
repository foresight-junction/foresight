"""CI ordering test for the scripted baselines (issue #12, EVAL §5).

Plays every baseline in eval/baselines/ against the real sim and scorer on each shipped seed.
It skips until the sim core (#4), world generator and scorer (#10) are importable, and the
reference checks skip until the reference policy (#16) is importable.
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
pytest.importorskip("ed72_sim.scoring.score")

from ed72_baselines import BASELINES, EXPLOITS
from ed72_baselines.sim_client import play_and_score

SHIPPED_SEEDS = (1, 2, 3)  # update together with the seeds in task.toml / SPEC §12
DIVERT_ALL_CAP = 50.0  # rulebook §13 says "about 47 points" at best; seed 2 measures 48.1
# Assumed home of the reference policy (#16): ed72/solution/ed72_reference.py, class ReferencePolicy.
REFERENCE_MODULE = "ed72_reference"


@cache
def baseline_score(name: str, seed: int) -> float:
    return play_and_score(BASELINES[name](), seed)["score"]


@cache
def reference_score(seed: int) -> float:
    try:
        module = importlib.import_module(REFERENCE_MODULE)
    except ModuleNotFoundError:
        pytest.skip(f"reference policy module {REFERENCE_MODULE!r} not importable yet (#16)")
    return play_and_score(module.ReferencePolicy(), seed)["score"]


@pytest.mark.parametrize("seed", SHIPPED_SEEDS)
def test_do_nothing_scores_zero(seed: int) -> None:
    assert baseline_score("do_nothing", seed) == 0


@pytest.mark.parametrize("seed", SHIPPED_SEEDS)
def test_stop_early_below_reactive_proxy(seed: int) -> None:
    assert baseline_score("stop_early", seed) < baseline_score("reactive_proxy", seed)


@pytest.mark.parametrize("seed", SHIPPED_SEEDS)
def test_divert_all_about_47_or_less(seed: int) -> None:
    assert baseline_score("divert_all", seed) <= DIVERT_ALL_CAP


@pytest.mark.parametrize("seed", SHIPPED_SEEDS)
def test_reactive_proxy_below_reference(seed: int) -> None:
    assert baseline_score("reactive_proxy", seed) < reference_score(seed)


@pytest.mark.parametrize("name", sorted(EXPLOITS))
@pytest.mark.parametrize("seed", SHIPPED_SEEDS)
def test_exploit_below_reference(seed: int, name: str) -> None:
    assert baseline_score(name, seed) < reference_score(seed)


def test_same_seed_same_actions_same_score() -> None:
    seed = SHIPPED_SEEDS[0]
    first = play_and_score(BASELINES["reactive_proxy"](), seed)
    again = play_and_score(BASELINES["reactive_proxy"](), seed)
    assert first == again
