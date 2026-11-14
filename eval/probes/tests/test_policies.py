from copy import deepcopy

import pytest

from eval.probes.invalid_actions import invalid_actions
from eval.probes.replay import replay
from eval.probes.runner import assert_margin, play
from eval.probes.stop_early import STOP_TICKS, stop_early


def test_stop_horizons_leave_the_rest_of_episode_to_collector() -> None:
    for tick in STOP_TICKS:
        policy = stop_early(lambda obs: [], tick)
        assert policy({"tick": tick}) is None
        if tick:
            assert policy({"tick": tick - 1}) == []
    with pytest.raises(ValueError):
        stop_early(lambda obs: [], -1)


def test_replay_uses_ticks_and_copies_actions() -> None:
    script = [{"tick": 2, "actions": [{"type": "admit", "patient": "P001", "zone": "resus"}]}]
    policy = replay(script)
    script[0]["actions"].clear()
    assert policy({"tick": 1}) == []
    actions = policy({"tick": 2})
    actions.clear()
    assert policy({"tick": 2})[0]["patient"] == "P001"
    with pytest.raises(ValueError):
        replay([{"tick": 0, "actions": []}] * 2)


def test_invalid_spam_reaches_contract_limit_without_valid_operations() -> None:
    actions = invalid_actions({})
    assert len(actions) == 50
    assert all(action.get("role") != "nurse" for action in actions)


def test_public_runner_stops_without_a_hidden_finalize_call() -> None:
    # MOCK: only a contract transport for runner control-flow tests.
    calls = []
    observation = {"tick": 0, "finished": False}

    def call(tool: str, arguments: dict) -> dict:
        calls.append(tool)
        if tool == "rules":
            return {"text": "fixture"}
        if tool == "step":
            observation["tick"] += 1
            return {"observation": deepcopy(observation), "results": []}
        return deepcopy(observation)

    assert len(play(call, stop_early(lambda obs: [], 6))) == 6
    assert calls == ["rules", "observe"] + ["step"] * 6


def test_probe_threshold_does_not_silently_accept_a_small_gap() -> None:
    assert_margin(80, 75)
    with pytest.raises(AssertionError):
        assert_margin(80, 76)


@pytest.mark.parametrize("rules_output", ["Public handbook\n", '{"text": "Public handbook\\n"}'])
def test_ward_normalizes_raw_rules_text_and_preserves_json_results(
    monkeypatch: pytest.MonkeyPatch, rules_output: str
) -> None:
    from subprocess import CompletedProcess

    from eval.probes.runner import ward

    # MOCK: subprocess outputs match #5 ward's confirmed CLI behavior.
    def run(command: list[str], **kwargs: object) -> CompletedProcess:
        stdout = rules_output if command[1] == "rules" else '{"tick": 0}'
        return CompletedProcess(command, 0, stdout=stdout)

    monkeypatch.setattr("eval.probes.runner.subprocess.run", run)
    assert ward("rules", {}) == {"text": "Public handbook\n"}
    assert ward("observe", {}) == {"tick": 0}


def test_ward_preserves_transport_diagnostics(monkeypatch: pytest.MonkeyPatch) -> None:
    from subprocess import CompletedProcess

    from eval.probes.runner import ward

    # MOCK: a real CLI failure must retain its stderr message.
    monkeypatch.setattr(
        "eval.probes.runner.subprocess.run",
        lambda command, **kwargs: CompletedProcess(command, 1, stdout="", stderr="call_cap_reached"),
    )
    with pytest.raises(RuntimeError, match="call_cap_reached"):
        ward("step", {"actions": []})


def test_json_rules_errors_are_not_mistaken_for_handbook_text(monkeypatch: pytest.MonkeyPatch) -> None:
    from subprocess import CompletedProcess

    from eval.probes.runner import ward

    # MOCK: tool errors may be returned as JSON even after successful transport.
    monkeypatch.setattr(
        "eval.probes.runner.subprocess.run",
        lambda command, **kwargs: CompletedProcess(command, 0, stdout='{"error": "call_cap_reached"}'),
    )
    with pytest.raises(RuntimeError, match="call_cap_reached"):
        ward("rules", {})
