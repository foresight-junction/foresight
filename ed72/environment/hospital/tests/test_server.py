import asyncio
import json
import sys
from pathlib import Path

import pytest
from fastmcp import Client
from starlette.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import server
from mock_sim import MockSimulation


def make_host(tmp_path: Path, seed: int = 7, name: str = "events.jsonl") -> server.ToolHost:
    return server.ToolHost(MockSimulation(seed), "HANDBOOK TEXT", tmp_path / name)


def read_log(host: server.ToolHost) -> list[dict]:
    return [json.loads(line) for line in host.log_path.read_text().splitlines()]


def mcp_call(host: server.ToolHost, tool: str, args: dict, raise_on_error: bool = True):
    async def run():
        async with Client(server.build_server(host)) as c:
            return await c.call_tool(tool, args, raise_on_error=raise_on_error)

    return asyncio.run(run())


def test_lists_exactly_three_tools(tmp_path):
    async def run():
        async with Client(server.build_server(make_host(tmp_path))) as c:
            return {t.name for t in await c.list_tools()}

    assert asyncio.run(run()) == {"rules", "observe", "step"}


def test_rules_returns_handbook(tmp_path):
    assert mcp_call(make_host(tmp_path), "rules", {}).data == {"text": "HANDBOOK TEXT"}


def test_step_returns_results_and_advances_tick(tmp_path):
    host = make_host(tmp_path)
    out = mcp_call(host, "step", {"actions": [{"type": "repair"}]}).data
    assert out["results"] == [{"index": 0, "ok": False, "reason": "bad_action"}]
    assert out["observation"]["tick"] == 1
    assert host.sim.observe()["tick"] == 1


def test_more_than_50_actions_are_rejected_past_the_cap(tmp_path):
    host = make_host(tmp_path)
    out = host.call("step", {"actions": [{"type": "repair"}] * 53})
    assert len(out["results"]) == 53
    assert all(r["reason"] == "bad_action" for r in out["results"])
    assert out["results"][50:] == [{"index": i, "ok": False, "reason": "bad_action"} for i in (50, 51, 52)]
    assert host.sim.observe()["last_rejected"][-1]["index"] == 49


def test_call_cap(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "CALL_CAP", 5)
    host = make_host(tmp_path)
    for _ in range(5):
        assert "error" not in host.call("step", {"actions": []})
    tick = host.sim.observe()["tick"]
    for tool, args in [("step", {"actions": []}), ("observe", {}), ("rules", {})]:
        assert host.call(tool, args) == {"error": "call_cap_reached"}
    assert host.sim.observe()["tick"] == tick


def test_default_call_cap_is_500(tmp_path):
    host = make_host(tmp_path)
    for _ in range(500):
        assert "error" not in host.call("observe", {})
    assert host.call("observe", {}) == {"error": "call_cap_reached"}


def test_episode_over_after_144_steps(tmp_path):
    host = make_host(tmp_path)
    for _ in range(144):
        assert "error" not in host.call("step", {"actions": []})
    assert host.call("observe", {})["finished"] is True
    assert host.call("step", {"actions": []}) == {"error": "episode_over"}


def test_event_log_format(tmp_path):
    host = make_host(tmp_path, seed=3)
    host.call("observe", {})
    for _ in range(3):
        host.call("step", {"actions": []})
    host.call("rules", {})
    lines = read_log(host)
    assert [line["seq"] for line in lines] == list(range(1, len(lines) + 1))
    agent = [line for line in lines if line["src"] == "agent"]
    assert [line["tool"] for line in agent] == ["observe", "step", "step", "step", "rules"]
    assert [line["t"] for line in agent] == [0, 0, 1, 2, 3]
    assert agent[1]["args"] == {"actions": []}
    sim = [line for line in lines if line["src"] == "sim"]
    assert sim and all(line["event"] in {"arrival", "admitted"} for line in sim)


def test_sim_admitted_event_is_logged(tmp_path):
    host = make_host(tmp_path, seed=7)
    waiting = host.sim.observe()["waiting"]
    assert waiting
    action = {"type": "admit", "patient": waiting[0]["id"], "zone": "acute"}
    host.call("step", {"actions": [action]})
    admitted = [line for line in read_log(host) if line.get("event") == "admitted"]
    assert admitted[0]["src"] == "sim" and admitted[0]["patient"] == waiting[0]["id"]


def test_invalid_args_give_tool_error(tmp_path):
    assert mcp_call(make_host(tmp_path), "step", {"actions": "bad"}, raise_on_error=False).is_error


def test_same_seed_same_actions_same_log(tmp_path):
    logs = []
    for name in ("a.jsonl", "b.jsonl"):
        host = make_host(tmp_path, seed=11, name=name)
        for _ in range(20):
            wait = host.sim.observe()["waiting"]
            acts = [{"type": "admit", "patient": p["id"], "zone": "acute"} for p in wait]
            host.call("step", {"actions": acts})
        logs.append(host.log_path.read_text())
    assert logs[0] == logs[1]
    for line in logs[0].splitlines():
        json.loads(line)


def test_health(tmp_path):
    app = server.build_server(make_host(tmp_path)).http_app()
    with TestClient(app) as client:
        res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"ok": True}


if __name__ == "__main__":
    pytest.main([__file__])
