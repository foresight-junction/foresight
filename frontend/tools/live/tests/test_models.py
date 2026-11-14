import json
from types import SimpleNamespace

import pytest
from claude import CLAUDE_SCHEMA, ClaudeDecider
from kimi import API, KimiDecider
from llm import ModelFatal

OBS = {"tick": 3, "waiting": [], "last_rejected": [{"index": 0}]}
REPLY = {
    "thought": "Admit P1.",
    "actions": [{"type": "admit", "patient": "P1", "zone": "acute", "role": "x"}],
}


def test_kimi_sends_a_json_mode_chat_completion_and_parses_it() -> None:
    sent = {}

    def post(url, headers, body, timeout):
        sent.update(url=url, headers=headers, body=json.loads(body), timeout=timeout)
        reply = {"choices": [{"message": {"content": json.dumps(REPLY)}, "finish_reason": "stop"}]}
        return 200, json.dumps(reply).encode()

    d = KimiDecider("kimi-k3-1-pro", "secret", "low", post=post)
    d.start("HANDBOOK")
    actions, thought = d.decide(OBS, [], [])
    assert (actions, thought) == ([{"type": "admit", "patient": "P1", "zone": "acute"}], "Admit P1.")
    assert sent["url"] == API and sent["headers"]["Authorization"] == "Bearer secret"
    body = sent["body"]
    assert body["model"] == "kimi-k3-1-pro" and body["reasoning_effort"] == "low"
    assert body["response_format"] == {"type": "json_object"}
    assert body["messages"][0]["role"] == "system" and body["messages"][0]["content"].startswith("HANDBOOK")
    assert "last_rejected" not in json.loads(body["messages"][1]["content"])["observation"]


def test_kimi_reasoning_that_eats_max_tokens_skips_the_tick() -> None:
    def post(url, headers, body, timeout):
        return 200, json.dumps(
            {"choices": [{"message": {"content": ""}, "finish_reason": "length"}]}
        ).encode()

    actions, thought = KimiDecider("k", "s", post=post).decide(OBS, [], [])
    assert actions == [] and "length" in thought


def test_kimi_bad_key_is_fatal() -> None:
    def post(url, headers, body, timeout):
        return 401, b'{"error": {"message": "invalid_api_key"}}'

    with pytest.raises(ModelFatal, match="401"):
        KimiDecider("k", "s", post=post).decide(OBS, [], [])


def fake_claude(stop_reason: str = "end_turn", text: str = json.dumps(REPLY)):
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(stop_reason=stop_reason, content=[SimpleNamespace(type="text", text=text)])

    return SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=create))), calls


def test_claude_request_caches_the_handbook_and_asks_for_the_schema() -> None:
    client, calls = fake_claude()
    d = ClaudeDecider("claude-opus-5-5", "medium", client=client)
    d.start("HANDBOOK")
    actions, thought = d.decide(OBS, [], [])
    assert thought == "Admit P1."
    assert actions == [{"type": "admit", "patient": "P1", "zone": "acute"}]
    req = calls[0]
    assert req["model"] == "claude-opus-5-5"
    assert req["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert req["system"][0]["text"].startswith("HANDBOOK")
    assert req["output_config"]["effort"] == "medium"
    assert req["output_config"]["format"] == {"type": "json_schema", "schema": CLAUDE_SCHEMA}
    assert req["fallbacks"] == "default" and req["betas"] == ["server-side-fallback-2026-07-01"]


def test_claude_schema_closes_every_object() -> None:
    assert CLAUDE_SCHEMA["additionalProperties"] is False
    assert CLAUDE_SCHEMA["properties"]["actions"]["items"]["additionalProperties"] is False


def test_claude_refusal_skips_the_tick() -> None:
    client, _ = fake_claude(stop_reason="refusal", text="")
    actions, thought = ClaudeDecider("m", client=client).decide(OBS, [], [])
    assert actions == [] and "declined" in thought
