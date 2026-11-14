"""Policy behaviour against the MOCK fake client. Scores need the real sim: see test_baselines.py."""

import pytest
from ed72_baselines import BASELINES, run_episode
from ed72_baselines.client import TOOL_CALL_CAP
from ed72_baselines.exploits import (
    AdmitLightOnly,
    AdmitWithoutCoverage,
    DivertAll,
    FillBedsAtLastTick,
    RandomPolicy,
    SpendToLimit,
)
from ed72_baselines.policies import DoNothing, ReactiveProxy, SeverityPolicy, StopEarly
from fake_client import ALLOWED, TICKS, ZONES, FakeClient

FIELDS = {
    "admit": {"type", "patient", "zone"},
    "assign": {"type", "staff", "to"},
    "agency": {"type", "role"},
    "repair": {"type"},
    "divert": {"type"},
}


def valid_shape(action: dict) -> bool:
    kind = action.get("type")
    if kind not in FIELDS or set(action) != FIELDS[kind]:
        return False
    if kind == "admit":
        return isinstance(action["patient"], str) and action["zone"] in ZONES
    if kind == "assign":
        return isinstance(action["staff"], str) and action["to"] in (*ZONES, "rest")
    if kind == "agency":
        return action["role"] in ("doctor", "nurse")
    return True


def play(policy) -> FakeClient:
    client = FakeClient()
    run_episode(client, policy)
    return client


def admits(client: FakeClient) -> list[tuple[int, dict]]:
    return [(t, a) for t, step in enumerate(client.steps) for a in step if a["type"] == "admit"]


@pytest.mark.parametrize("name", sorted(BASELINES))
def test_every_baseline_emits_valid_actions_within_the_cap(name: str) -> None:
    client = play(BASELINES[name]())
    assert len(client.calls) <= TOOL_CALL_CAP
    for step in client.steps:
        assert len(step) <= 50
        assert all(valid_shape(a) for a in step), step


@pytest.mark.parametrize("name", ["reactive_proxy", "divert_all", "spend_to_limit", "fill_beds_at_last_tick"])
def test_full_players_step_every_tick(name: str) -> None:
    client = play(BASELINES[name]())
    assert len(client.steps) == TICKS
    assert client.finished


def test_do_nothing_never_steps() -> None:
    client = play(DoNothing())
    assert client.steps == []


def test_stop_early_steps_twelve_ticks_like_the_proxy() -> None:
    early, proxy = play(StopEarly()), play(ReactiveProxy())
    assert len(early.steps) == StopEarly.TICKS
    assert early.steps == proxy.steps[: StopEarly.TICKS]


def test_reactive_proxy_puts_light_cases_in_resus() -> None:
    client = play(ReactiveProxy())
    first_tick, first = admits(client)[0]
    assert first_tick == 0 and first["zone"] == "resus"  # P001 is ESI 4
    esi = {pid: p["esi"] for pid, p in client.patients.items()}
    assert all(a["zone"] in ALLOWED[esi[a["patient"]]] for _, a in admits(client))


def test_reactive_proxy_rests_staff_at_85() -> None:
    proxy = ReactiveProxy()
    obs = FakeClient().observe()
    obs["staff"][0].update(status="on_shift", location="resus", fatigue=85.0)
    obs["staff"][1].update(status="on_shift", location="resus", fatigue=84.9)
    actions = proxy.act(obs)
    assert {"type": "assign", "staff": "D1", "to": "rest"} in actions
    assert not any(a.get("staff") == "D2" for a in actions)


def test_reactive_proxy_orders_agency_only_at_queue_ten() -> None:
    obs = FakeClient(arrivals={0: [3] * 9}).observe()
    assert not any(a["type"] == "agency" for a in ReactiveProxy().act(obs))
    obs = FakeClient(arrivals={0: [3] * 10}).observe()
    assert {"type": "agency", "role": "doctor"} in ReactiveProxy().act(obs)


def test_severity_keeps_resus_for_esi_1_and_2() -> None:
    client = play(SeverityPolicy())
    esi = {pid: p["esi"] for pid, p in client.patients.items()}
    assert all(esi[a["patient"]] <= 2 for _, a in admits(client) if a["zone"] == "resus")


def test_divert_all_diverts_whenever_no_diversion_runs() -> None:
    client = play(DivertAll())
    divert_ticks = [t for t, step in enumerate(client.steps) if {"type": "divert"} in step]
    assert divert_ticks == list(range(0, TICKS, 4))


def test_admit_light_only_admits_only_esi_4_and_5() -> None:
    client = play(AdmitLightOnly())
    esi = {pid: p["esi"] for pid, p in client.patients.items()}
    assert admits(client) and all(esi[a["patient"]] >= 4 for _, a in admits(client))


def test_admit_light_only_is_not_blocked_by_severe_cases() -> None:
    obs = FakeClient(arrivals={0: [3] * 14 + [4]}).observe()
    assert AdmitLightOnly().act(obs)[0] == {"type": "admit", "patient": "P015", "zone": "fast_track"}


def test_admit_without_coverage_never_puts_anyone_on_shift() -> None:
    client = play(AdmitWithoutCoverage())
    assert admits(client)
    assert all(a["to"] == "rest" for step in client.steps for a in step if a["type"] == "assign")


def test_fill_beds_at_last_tick_admits_only_at_tick_143() -> None:
    client = play(FillBedsAtLastTick())
    assert {t for t, _ in admits(client)} == {TICKS - 1}
    assert len(admits(client)) == 17


def test_spend_to_limit_reaches_but_never_passes_the_hard_limit() -> None:
    client = play(SpendToLimit())
    assert 24000 - 350 < client.spent <= 24000
    assert all(r["reason"] != "over_hard_limit" for r in client.last_rejected)


def test_random_is_reproducible_from_its_seed() -> None:
    assert play(RandomPolicy(seed=7)).steps == play(RandomPolicy(seed=7)).steps
    assert play(RandomPolicy(seed=7)).steps != play(RandomPolicy(seed=8)).steps
