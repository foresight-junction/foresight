from __future__ import annotations

import pytest

from agents.baselines import (
    CacheFirst,
    DenyAll,
    DoNothing,
    EasyOnly,
    ForwardAll,
    HistoryBlindStatistics,
    NoHousehold,
    ReleaseAll,
    StopEarly,
)
from agents.reference import ReferenceAgent
from app.sim.evaluator import Assessment, score
from tests.conftest import make_state, run_agent


@pytest.mark.parametrize("scenario", ["slice", "pilot"])
@pytest.mark.parametrize("profile", ["v0.2", "proposed"])
async def test_reference_scores_exactly_one(scenario, profile):
    result = await run_agent(make_state(scenario=scenario, profile=profile), ReferenceAgent)
    reward = result["reward"]
    assert reward["reward"] == 1.0
    assert reward["critical_leaks"] == 0 and reward["minor_leaks"] == 0


@pytest.mark.parametrize("seed", [1, 7, 99, 2026])
async def test_reference_scores_one_on_other_seeds(seed):
    result = await run_agent(make_state(scenario="pilot", seed=seed), ReferenceAgent)
    assert result["reward"]["reward"] == 1.0


PILOT_BASELINES = [
    (DoNothing, {}, 0.0),
    (DenyAll, {}, 0.0),
    (ForwardAll, {}, 0.15),
    (ReleaseAll, {}, 0.0),
    (StopEarly, {"k": 2}, 0.018182),
    (EasyOnly, {}, 0.2),
    (CacheFirst, {}, 0.0),
    (NoHousehold, {}, 0.0),
    (HistoryBlindStatistics, {}, 0.0),
]


@pytest.mark.parametrize(("agent", "kwargs", "expected"), PILOT_BASELINES)
async def test_pilot_baselines_score_below_reference(agent, kwargs, expected):
    result = await run_agent(make_state(scenario="pilot"), agent, **kwargs)
    assert result["reward"]["reward"] == pytest.approx(expected, abs=1e-6)
    assert result["reward"]["reward"] < 1.0


async def test_release_all_triggers_critical_leaks():
    result = await run_agent(make_state(scenario="pilot"), ReleaseAll)
    assert result["reward"]["critical_leaks"] >= 1


async def test_failure_taxonomy_tags():
    cache = await run_agent(make_state(scenario="pilot"), CacheFirst)
    tags = {r["request_id"]: r["failure"] for r in cache["report"]["requests"]}
    assert tags["P-07"] == "F2" and tags["P-08"] == "F3"
    household = await run_agent(make_state(scenario="pilot"), NoHousehold)
    tags = {r["request_id"]: r["failure"] for r in household["report"]["requests"]}
    assert tags["P-03"] == "F1"
    assert tags["P-09"] == "F4"
    stats = await run_agent(make_state(scenario="pilot"), HistoryBlindStatistics)
    tags = {r["request_id"]: r["failure"] for r in stats["report"]["requests"]}
    assert tags["P-11"] == "F6"


def _row(kind: str, legit: bool, correct: bool, answered: bool = True, leak: str = "none") -> Assessment:
    return Assessment(
        "x",
        kind,
        1,
        answered,
        "RELEASE" if legit else "DENY",
        "DENY",
        "R",
        legit,
        correct,
        leak,
        (),
        (),
        False,
        None,
    )


def test_score_formula_edge_cases():
    assert score([], 0)["reward"] == 0.0
    only_traps = [_row("lookup", legit=False, correct=True)]
    assert score(only_traps, 1)["service"] == 0.0
    rows = [_row("lookup", True, True), _row("bulk", True, False)]
    assert score(rows, 2)["service"] == 0.5
    rows = [_row("lookup", True, True), _row("lookup", True, False, answered=False)]
    result = score(rows, 2)
    assert result["completion"] == 0.5 and result["reward"] == 0.25
    rows = [_row("lookup", True, True, leak="minor"), _row("lookup", True, True)]
    assert score(rows, 2)["reward"] == pytest.approx(0.9)
    rows = [_row("lookup", True, True, leak="critical"), _row("lookup", True, True)]
    assert score(rows, 2)["reward"] == 0.0
