"""Stand-in and ablation checks: valid actions, public inputs only, rule numbers in sync with the sim,
deterministic, and each lever changes only the decisions it owns."""

import json
from collections import Counter
from functools import cache

import pytest
from ed72_ablations import standin
from ed72_ablations.run import Simulation, generate_world, load_config, play, score, variants
from ed72_ablations.standin import ALL_LEVERS, StandInPolicy
from ed72_sim import constants as c

SEEDS = (1, 2, 3)

# CONTRACTS v1 Observation: every key at every level.
OBS_KEYS = {
    "tick", "clock", "ticks_left", "finished", "budget", "waiting", "beds", "staff", "ct",
    "warnings", "diversion", "totals", "last_rejected",
}  # fmt: skip
NESTED_KEYS = {
    "budget": {"spent", "budget", "hard_limit"},
    "waiting": {"id", "esi", "arrived_tick", "waited_ticks", "needs_ct"},
    "beds": {
        "zone",
        "bed",
        "patient",
        "esi",
        "treated_ticks",
        "treatment_ticks",
        "covered",
        "waiting_for_ct",
    },
    "staff": {"id", "role", "agency", "location", "fatigue", "counts_as", "status", "ticks_until_change"},
    "ct": {"working", "down_ticks_left"},
    "warnings": {"event", "start_tick"},
    "diversion": {"active", "ticks_left"},
    "totals": {"discharged", "deaths", "left", "diverted", "faints"},
    "last_rejected": {"index", "action", "reason"},
}
CONTRACT_KEYS = OBS_KEYS | set().union(*NESTED_KEYS.values())


def _copy(obs: dict) -> dict:
    return json.loads(json.dumps(obs))


@cache
def trace(levers: frozenset[str], seed: int) -> list[list[dict]]:
    return play(StandInPolicy(levers), seed)[1]


@pytest.mark.parametrize("name", list(variants()))
def test_every_variant_sends_only_accepted_actions(name: str) -> None:
    for seed in SEEDS:
        sim = Simulation(generate_world(seed, load_config(None)))
        policy = StandInPolicy(variants()[name])
        while not (obs := sim.observe())["finished"]:
            actions = policy(_copy(obs))
            assert len(actions) <= 50  # CONTRACTS: at most 50 actions per step
            rejected = [r for r in sim.step(actions)["results"] if not r["ok"]]
            assert rejected == [], (seed, obs["tick"], rejected)


class Recording(dict):
    """A dict that records every key read from it or from anything nested inside it."""

    def __init__(self, data: dict, seen: set[str]) -> None:
        super().__init__({k: _wrap(v, seen) for k, v in data.items()})
        self._seen = seen

    def __getitem__(self, key: str) -> object:
        self._seen.add(key)
        return super().__getitem__(key)

    def get(self, key: str, default: object = None) -> object:
        self._seen.add(key)
        return super().get(key, default)


def _wrap(value: object, seen: set[str]) -> object:
    if isinstance(value, dict):
        return Recording(value, seen)
    if isinstance(value, list):
        return [_wrap(v, seen) for v in value]
    return value


def test_policy_reads_only_contract_observation_keys() -> None:
    seen: set[str] = set()
    for name, levers in variants().items():
        sim = Simulation(generate_world(1, load_config(None)))
        policy = StandInPolicy(levers)
        while not (obs := sim.observe())["finished"]:
            assert set(obs) == OBS_KEYS, name  # the sim still emits the v1 shape
            sim.step(policy(Recording(_copy(obs), seen)))
    assert seen, "recording saw no reads"
    assert seen <= CONTRACT_KEYS, seen - CONTRACT_KEYS


def test_copied_rule_numbers_match_the_sim() -> None:
    assert standin.ZONES == c.ZONES
    assert standin.BEDS_PER == {"doctor": c.BEDS_PER_DOCTOR, "nurse": c.BEDS_PER_NURSE}
    allowed = {esi: set(zones) for esi, zones in standin.ALLOWED.items()}
    assert allowed == {esi: set(zones) for esi, zones in c.ZONE_EXTRA_TICKS.items()}
    assert standin.AGENCY_COST == c.AGENCY_COST
    assert standin.AGENCY_DELAY == c.AGENCY_DELAY
    assert standin.REPAIR_COST == c.REPAIR_COST
    assert standin.REPAIR_TICKS == c.REPAIR_TICKS
    assert standin.TIRED_ABOVE == c.FATIGUE_TIRED
    assert standin.FAINT_AT == c.FATIGUE_FAINT
    assert standin.MAX_GAIN == max(c.FATIGUE_GAIN.values())


def test_same_seed_same_score() -> None:
    first, trace1 = play(StandInPolicy(), 2)
    second, trace2 = play(StandInPolicy(), 2)
    assert trace1 == trace2
    assert first["score"] == second["score"]


# Action types each lever may change, given the same observation. Admit placement feeds staffing and
# the shortfall count, so the two levers that move admits may change those too.
OWNED = {
    "resus_reservation": {"admit", "assign", "agency"},
    "rest_rotation": {"assign"},
    "warnings": {"admit", "assign", "agency"},
    "ct_repair": {"repair"},
    "agency": {"agency"},
    "no_panic_divert": {"divert"},
}


def _others(actions: list[dict], owned: set[str]) -> Counter:
    return Counter(json.dumps(a, sort_keys=True) for a in actions if a["type"] not in owned)


@pytest.mark.parametrize("lever", sorted(ALL_LEVERS))
def test_each_lever_changes_only_what_it_owns(lever: str) -> None:
    """Lockstep: on each observation of the lever-off episode, both policies decide; outside the
    lever's own action types the decisions must be identical."""
    owned = OWNED[lever]
    for seed in SEEDS:
        sim = Simulation(generate_world(seed, load_config(None)))
        full, off = StandInPolicy(), StandInPolicy(ALL_LEVERS - {lever})
        while not (obs := sim.observe())["finished"]:
            want, got = full(_copy(obs)), off(_copy(obs))
            assert _others(want, owned) == _others(got, owned), (seed, obs["tick"])
            if lever == "warnings" and want != got:
                assert obs["warnings"], (seed, obs["tick"])  # prep only while a warning is visible
                # Decision level: prep holds back only ESI 3-5 patients, so ESI 1-2 admits are the same.
                urgent = {p["id"] for p in obs["waiting"] if p["esi"] <= 2}
                urgent_admits = [
                    {a["patient"] for a in acts if a["type"] == "admit"} & urgent for acts in (want, got)
                ]
                assert urgent_admits[0] == urgent_admits[1], (seed, obs["tick"])
            if lever == "agency":
                # Surge orders belong to warnings: removing agency keeps every one of them.
                assert sum(a["type"] == "agency" for a in got) <= sum(a["type"] == "agency" for a in want)
            sim.step(got)


@pytest.mark.parametrize("lever", sorted(ALL_LEVERS))
def test_each_lever_is_wired(lever: str) -> None:
    """The switch reaches the sim. This shows the code runs, not that the lever is worth anything."""
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
    assert full >= 90  # stand-in scores 94.3 on seed 1 at 4.0 arrivals; severity-first scores 30.6


def test_unknown_lever_is_refused() -> None:
    with pytest.raises(ValueError, match="unknown lever"):
        StandInPolicy(frozenset({"telepathy"}))
