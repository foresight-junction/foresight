"""#14 round 2: a refused call adds a bounded number of bytes to the event log, and scoring is unchanged."""

import json
from pathlib import Path

import collect
import server
from ed72_sim import constants as c
from ed72_sim.engine import Simulation
from ed72_sim.scoring.score import score
from ed72_sim.world import generate_world

BIG = "x" * 1_000_000


def make_host(tmp_path: Path) -> server.ToolHost:
    tmp_path.mkdir(parents=True, exist_ok=True)
    return server.ToolHost(Simulation(generate_world(1), tmp_path / "events.jsonl"), "HANDBOOK")


def log_size(host: server.ToolHost) -> int:
    return host.sim._log_path.stat().st_size


def agent_lines(host: server.ToolHost) -> list[dict]:
    lines = [json.loads(x) for x in host.sim._log_path.read_text(encoding="utf-8").splitlines()]
    return [x for x in lines if x["src"] == "agent"]


def test_refused_step_with_5000_huge_actions_adds_a_few_kb(tmp_path):
    host = make_host(tmp_path)
    for _ in range(c.TICKS):
        host.call("step", {"actions": []})
    before = log_size(host)
    junk = {"type": "admit", "patient": BIG, "zone": BIG, "staff": BIG, "to": BIG, "role": BIG, "extra": BIG}
    assert host.call("step", {"actions": [junk] * 5_000}) == {"error": "episode_over"}
    added = log_size(host) - before
    assert added < 20_000
    logged = agent_lines(host)[-1]["args"]["actions"]
    assert len(logged) == server.MAX_ACTIONS
    assert set(logged[0]) <= set(server.LOGGED_ACTION_FIELDS)
    assert all(len(v) <= server.MAX_LOGGED_CHARS for v in logged[0].values())


def test_refused_step_keeps_contract_fields_and_replaces_non_dicts(tmp_path):
    host = make_host(tmp_path)
    for _ in range(c.TICKS):
        host.call("step", {"actions": []})
    host.call("step", {"actions": [{"type": "assign", "staff": "D3", "to": "rest", "pad": 1}, 7, None, [1]]})
    assert agent_lines(host)[-1]["args"]["actions"] == [
        {"type": "assign", "staff": "D3", "to": "rest"},
        "<non-dict>",
        "<non-dict>",
        "<non-dict>",
    ]


def test_post_cap_calls_add_bounded_bytes_each(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "CALL_CAP", 5)
    host = make_host(tmp_path)
    for _ in range(5):
        host.call("observe", {})
    before = log_size(host)
    payload = {"actions": [{"type": "repair", "pad": BIG}] * 5_000}
    for i in range(2_000):
        tool = ("rules", "observe", "step")[i % 3]
        assert host.call(tool, payload if tool == "step" else {}) == {"error": "call_cap_reached"}
    per_call = (log_size(host) - before) / 2_000
    assert per_call < 200
    assert all(x["args"] == {} for x in agent_lines(host)[5:])


def test_bounded_log_leaves_reward_calls_and_end_unchanged_and_replays(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "CALL_CAP", 40)
    host = make_host(tmp_path)
    for _ in range(10):
        host.call("step", {"actions": [{"type": "divert"}]})
    # 30 more calls to hit the cap, then a flood of oversized refused calls.
    for _ in range(30):
        host.call("observe", {})
    flood = [{"type": "repair", "pad": BIG}] * 5_000
    for _ in range(300):
        host.call("step", {"actions": flood})
    out = tmp_path / "report.json"
    replayed = collect.collect(1, host.sim._log_path, out)
    assert replayed["tool_calls"] == 40 + 300
    assert replayed["ended"] == "call_cap"

    # Unbounded reference: the same calls with their full, unsanitised args, then the same finish.
    ref = Simulation(generate_world(1))
    for _ in range(10):
        ref.step([{"type": "divert"}])
    for _ in range(30):
        ref.record_call("observe", {}, {"ok": True})
    for _ in range(300):
        ref.record_call("step", {"actions": flood}, {"error": "call_cap_reached"})
    ref.run_to_end()
    assert replayed == score(ref.events)

    # Control: same 10 steps, no flood and no cap. Only tool_calls and ended may differ.
    control = make_host(tmp_path / "control")
    for _ in range(10):
        control.call("step", {"actions": [{"type": "divert"}]})
    control_report = collect.collect(1, control.sim._log_path, tmp_path / "control.json")
    assert replayed["reward"] == control_report["reward"]
    assert replayed["score"] == control_report["score"]
