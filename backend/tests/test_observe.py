from __future__ import annotations

import json

from fastapi.testclient import TestClient

from agents.baselines import ReleaseAll
from agents.reference import ReferenceAgent
from app.main import create_app
from app.schemas import ObservationEvent
from app.settings import Settings
from tests.conftest import make_state, run_agent

SENSITIVE = ("full_name", "date_of_birth", "street_address", "phone", "email", "employer", "school")


def _sensitive_values(state) -> set[str]:
    values = set()
    for person in state.service.world.persons:
        for field_name in SENSITIVE:
            value = getattr(person, field_name)
            if value and len(value) > 3:
                values.add(value)
    return values


async def test_events_validate_and_are_ordered():
    state = make_state(scenario="pilot")
    await run_agent(state, ReferenceAgent)
    events = state.bus.history
    for event in events:
        ObservationEvent.model_validate(event)
    seqs = [e["seq"] for e in events]
    assert seqs == list(range(seqs[0], seqs[0] + len(seqs)))
    started = {e["call_id"] for e in events if e["type"] == "TOOL_CALL_STARTED"}
    completed = [e["call_id"] for e in events if e["type"] == "TOOL_CALL_COMPLETED"]
    assert started == set(completed) and len(completed) == len(set(completed))
    assert events[0]["type"] == "EPISODE_STARTED" and events[-1]["type"] == "EPISODE_FINISHED"


async def test_respond_event_order_matches_contract():
    state = make_state(scenario="pilot")
    await run_agent(state, ReferenceAgent)
    events = state.bus.history
    index = next(
        i
        for i, e in enumerate(events)
        if e["type"] == "TOOL_CALL_STARTED" and e["tool"] == "respond" and e["request_id"] == "P-06"
    )
    window = [e["type"] for e in events[index : index + 6]]
    assert window[:4] == ["TOOL_CALL_STARTED", "DECISION_SUBMITTED", "STATE_CHANGED", "TOOL_CALL_COMPLETED"]
    assert window[4] == "REWARD_UPDATED"


async def test_no_raw_sensitive_values_reach_the_stream():
    state = make_state(scenario="pilot")
    await run_agent(state, ReleaseAll)
    stream = json.dumps(state.bus.history, ensure_ascii=False)
    leaked = [v for v in _sensitive_values(state) if v in stream]
    assert not leaked
    assert any(e["type"] == "PRIVACY_LEAK_DETECTED" for e in state.bus.history)


async def test_observation_does_not_change_reward():
    on = await run_agent(make_state(scenario="pilot", observe=True), ReleaseAll)
    off = await run_agent(make_state(scenario="pilot", observe=False), ReleaseAll)
    assert on["reward"] == off["reward"]


async def test_live_reveal_off_hides_evaluator_events_until_finalize():
    state = make_state(scenario="pilot", live_reveal=False)
    await run_agent(state, ReferenceAgent)
    reveal = [e for e in state.bus.history if e["visibility"] == "evaluator_reveal"]
    assert [e["type"] for e in reveal] == ["EPISODE_FINISHED"]


def test_http_routes_require_tokens():
    app = create_app(Settings(scenario="slice", spectator_token="s-test", verifier_token="v-test"))
    with TestClient(app) as client:
        assert client.get("/health").json() == {"ok": True}
        assert client.get("/observe/history").status_code == 401
        assert client.get("/observe/history", params={"token": "wrong"}).status_code == 401
        history = client.get("/observe/history", params={"token": "s-test"}).json()
        assert history[0]["type"] == "EPISODE_STARTED"
        assert client.post("/admin/finalize").status_code == 401
        assert client.post("/admin/finalize", headers={"X-Verifier-Token": "s-test"}).status_code == 401
        final = client.post("/admin/finalize", headers={"X-Verifier-Token": "v-test"}).json()
        assert final["reward"]["reward"] == 0.0
        reset = client.post(
            "/admin/reset", json={"scenario": "pilot"}, headers={"X-Verifier-Token": "v-test"}
        )
        assert reset.json()["total_requests"] == 11
        bad = client.post("/admin/reset", json={"scenario": "../etc"}, headers={"X-Verifier-Token": "v-test"})
        assert bad.status_code == 400


def test_observe_disabled_returns_401():
    app = create_app(Settings(scenario="slice", observe=False))
    with TestClient(app) as client:
        assert client.get("/observe/history", params={"token": "spect"}).status_code == 401
