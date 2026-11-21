from argparse import Namespace

import pytest
import serve
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


@pytest.mark.parametrize(("directory", "no_save"), [("runs", False), ("custom", False), ("runs", True)])
def test_new_episode_prints_query_only_for_viewer_replays(tmp_path, monkeypatch, capsys, directory, no_save):
    monkeypatch.setattr(serve, "RUNS_DIR", tmp_path / "runs")
    monkeypatch.setattr(serve.tempfile, "mkdtemp", lambda **kwargs: str(tmp_path))
    monkeypatch.delenv("ED72_CONFIG", raising=False)
    args = Namespace(
        gemini_model=None, kimi_model=None, claude_model=None, no_save=no_save, save_dir=tmp_path / directory
    )
    _, _, save_path = serve.new_episode(42, "reference", args)
    output = capsys.readouterr().out

    if no_save:
        assert save_path is None
        assert "save  " not in output
    else:
        assert str(save_path) in output
    if directory == "runs" and not no_save:
        assert f"viewer query: ?replay=runs/{save_path.name}" in output
        assert "localhost:" not in output
    else:
        assert "?replay=" not in output
