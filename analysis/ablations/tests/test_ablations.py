"""Stand-in and ablation checks: valid actions only, deterministic, every lever changes play."""

from functools import cache

import pytest
from ed72_ablations.run import Simulation, generate_world, load_config, play, score, variants
from ed72_ablations.standin import ALL_LEVERS, StandInPolicy

SEEDS = (1, 2, 3)


@cache
def trace(levers: frozenset[str], seed: int) -> list[list[dict]]:
    return play(StandInPolicy(levers), seed)[1]


def test_full_policy_sends_only_accepted_actions() -> None:
    for seed in SEEDS:
        sim = Simulation(generate_world(seed, load_config(None)))
        while not (obs := sim.observe())["finished"]:
            actions = StandInPolicy()(obs)
            assert len(actions) <= 50  # CONTRACTS: at most 50 actions per step
            rejected = [r for r in sim.step(actions)["results"] if not r["ok"]]
            assert rejected == [], (seed, obs["tick"], rejected)


@pytest.mark.parametrize("name", list(variants()))
def test_every_variant_sends_only_accepted_actions(name: str) -> None:
    sim = Simulation(generate_world(1, load_config(None)))
    policy = StandInPolicy(variants()[name])
    while not (obs := sim.observe())["finished"]:
        rejected = [r for r in sim.step(policy(obs))["results"] if not r["ok"]]
        assert rejected == [], (obs["tick"], rejected)


def test_same_seed_same_score() -> None:
    first, trace1 = play(StandInPolicy(), 2)
    second, trace2 = play(StandInPolicy(), 2)
    assert trace1 == trace2
    assert first["score"] == second["score"]


@pytest.mark.parametrize("lever", sorted(ALL_LEVERS))
def test_each_lever_changes_the_actions(lever: str) -> None:
    full = [trace(ALL_LEVERS, seed) for seed in SEEDS]
    ablated = [trace(ALL_LEVERS - {lever}, seed) for seed in SEEDS]
    assert full != ablated, f"removing {lever} changes nothing on seeds {SEEDS}"


def test_full_beats_do_nothing() -> None:
    sim = Simulation(generate_world(1, load_config(None)))
    while not sim.observe()["finished"]:
        sim.step([])
    nothing = score(sim.events)["score"]
    full = play(StandInPolicy(), 1)[0]["score"]
    assert full > nothing
    assert full >= 97  # at least as strong as the team's severity-first player


def test_unknown_lever_is_refused() -> None:
    with pytest.raises(ValueError, match="unknown lever"):
        StandInPolicy(frozenset({"telepathy"}))
