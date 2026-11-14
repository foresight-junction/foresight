import pytest
from serve import parse_start


def test_parse_start_accepts_a_seed_and_agent(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    assert parse_start(b'{"seed": 7, "agent": "llm"}') == (7, "gemini")  # old name still works
    assert parse_start(b'{"seed": 7, "agent": "gemini"}') == (7, "gemini")
    assert parse_start(b'{"seed": 0, "agent": "reference"}') == (0, "reference")


@pytest.mark.parametrize(
    "body",
    [
        b"not json",
        b'{"seed": "7", "agent": "reference"}',
        b'{"seed": true, "agent": "reference"}',
        b'{"seed": -1, "agent": "reference"}',
        b'{"seed": 2147483648, "agent": "reference"}',
        b'{"seed": 7, "agent": "random"}',
    ],
)
def test_parse_start_rejects_bad_requests(body: bytes) -> None:
    with pytest.raises(ValueError):
        parse_start(body)


def test_llm_needs_a_key(monkeypatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        parse_start(b'{"seed": 7, "agent": "llm"}')


def test_each_model_needs_its_own_key(monkeypatch) -> None:
    for name in ("GEMINI_API_KEY", "VERDA_INFERENCE_API_KEY", "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("VERDA_INFERENCE_API_KEY", "x")
    assert parse_start(b'{"seed": 1, "agent": "kimi"}') == (1, "kimi")
    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        parse_start(b'{"seed": 1, "agent": "claude"}')
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    assert parse_start(b'{"seed": 1, "agent": "claude"}') == (1, "claude")


def test_claude_also_takes_claude_api_key(monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    monkeypatch.setenv("CLAUDE_API_KEY", "x")
    assert parse_start(b'{"seed": 1, "agent": "claude"}') == (1, "claude")
