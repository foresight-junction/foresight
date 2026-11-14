import json

import gemini
import pytest
from gemini import GeminiDecider, GeminiFatal, parse_reply

OBS = {"tick": 3, "finished": False, "waiting": [], "last_rejected": [{"index": 0, "reason": "x"}]}


def reply(text: str, thought_part: bool = False) -> dict:
    parts = [{"text": "thinking...", "thought": True}] if thought_part else []
    return {"candidates": [{"content": {"parts": [*parts, {"text": text}]}, "finishReason": "STOP"}]}


class FakePost:
    """MOCK: stands in for the Gemini REST endpoint; replays canned (status, body) pairs."""

    def __init__(self, *responses: tuple[int, dict]) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, dict[str, str], dict]] = []

    def __call__(self, url: str, headers: dict[str, str], body: bytes, timeout: float) -> tuple[int, bytes]:
        self.calls.append((url, headers, json.loads(body)))
        status, payload = self.responses.pop(0)
        return status, json.dumps(payload).encode()


@pytest.fixture(autouse=True)
def no_backoff(monkeypatch):
    monkeypatch.setattr(gemini, "BACKOFF_S", 0)


def ok(thought: str = "t", actions: list | None = None) -> tuple[int, dict]:
    return 200, reply(json.dumps({"thought": thought, "actions": actions or []}))


def test_parses_plain_json_and_skips_thought_parts():
    text = json.dumps(
        {"thought": "Admit P1.", "actions": [{"type": "admit", "patient": "P1", "zone": "acute"}]}
    )
    assert parse_reply(reply(text, thought_part=True)) == (
        [{"type": "admit", "patient": "P1", "zone": "acute"}],
        "Admit P1.",
    )


def test_parses_fenced_json_and_drops_unused_fields():
    text = (
        '```json\n{"thought":"rest D1","actions":[{"type":"assign","staff":"D1","to":"rest","zone":""}]}\n```'
    )
    assert parse_reply(reply(text)) == ([{"type": "assign", "staff": "D1", "to": "rest"}], "rest D1")


def test_unknown_action_types_pass_through_for_the_sim_to_reject():
    text = json.dumps({"thought": "", "actions": [{"type": "teleport"}, "nonsense"]})
    assert parse_reply(reply(text))[0] == [{"type": "teleport"}, "nonsense"]


@pytest.mark.parametrize(
    "response",
    [
        reply("not json"),
        reply('{"thought":"x"}'),
        {"candidates": []},
        {"promptFeedback": {"blockReason": "SAFETY"}},
    ],
)
def test_bad_replies_raise(response):
    with pytest.raises(ValueError):
        parse_reply(response)


def test_bad_output_steps_nothing_then_gives_up():
    post = FakePost((200, reply("garbage")), (200, reply("garbage")), (200, reply("garbage")))
    decider = GeminiDecider("m", "KEY", post=post)
    actions, thought = decider.decide(OBS, [], [])
    assert actions == [] and thought.startswith("(no decision: unparseable JSON")
    decider.decide(OBS, [], [])
    with pytest.raises(GeminiFatal):
        decider.decide(OBS, [], [])


def test_a_good_reply_resets_the_failure_count():
    post = FakePost((200, reply("garbage")), (200, reply("garbage")), ok(), (200, reply("garbage")))
    decider = GeminiDecider("m", "KEY", post=post)
    for _ in range(4):
        decider.decide(OBS, [], [])


def test_retries_5xx_and_429_then_succeeds():
    post = FakePost((503, {"error": {"message": "busy"}}), (429, {}), ok("go", [{"type": "repair"}]))
    assert GeminiDecider("m", "KEY", post=post).decide(OBS, [], []) == ([{"type": "repair"}], "go")
    assert len(post.calls) == 3


def test_retries_exhausted_is_a_no_decision_tick():
    post = FakePost(*[(500, {"error": {"message": "down"}})] * 3)
    actions, thought = GeminiDecider("m", "KEY", post=post).decide(OBS, [], [])
    assert actions == [] and "HTTP 500: down" in thought


def test_client_errors_are_fatal():
    post = FakePost((404, {"error": {"message": "model not found"}}))
    with pytest.raises(GeminiFatal, match="HTTP 404: model not found"):
        GeminiDecider("m", "KEY", post=post).decide(OBS, [], [])


def test_request_shape():
    post = FakePost(ok("first"), ok("second"))
    decider = GeminiDecider("gemini-x", "KEY", post=post)
    decider.start("HANDBOOK TEXT")
    decider.decide(OBS, [], [])
    last_actions = [{"type": "admit", "patient": "P9", "zone": "resus"}, {"type": "repair"}]
    results = [{"index": 0, "ok": False, "reason": "no_free_bed"}, {"index": 1, "ok": True}]
    decider.decide(OBS, last_actions, results)

    url, headers, body = post.calls[1]
    assert url.endswith("/models/gemini-x:generateContent")
    assert headers["x-goog-api-key"] == "KEY" and "KEY" not in json.dumps(body)
    assert body["systemInstruction"]["parts"][0]["text"].startswith("HANDBOOK TEXT")
    fmt = body["generationConfig"]["responseFormat"]["text"]
    assert fmt["mimeType"] == "APPLICATION_JSON" and fmt["schema"]["required"] == ["thought", "actions"]
    turn = json.loads(body["contents"][0]["parts"][0]["text"])
    assert "last_rejected" not in turn["observation"] and turn["observation"]["tick"] == 3
    assert turn["rejected_last_tick"] == [{"action": last_actions[0], "reason": "no_free_bed"}]
    assert turn["your_last_thoughts"] == ["first"]
