"""Red-team round 2 (#14), part 1: attacks on the tool server (server.py over FastMCP 4.2.0).

Covers round 1's pending rows 28-30 and note N1. A test that asserts a defence holds is a plain test;
an open exploit is `xfail(strict=True)` asserting the safe behaviour, so it flips when fixed.
Findings are summarised in docs/REDTEAM.md.
"""

import asyncio
import copy
import dataclasses
import json
import re
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

import collect
import pytest
import server
from ed72_sim import constants as c
from ed72_sim.engine import Simulation
from ed72_sim.scoring.score import score
from ed72_sim.world import generate_world
from fastmcp import Client
from starlette.testclient import TestClient
from test_redteam_round1 import greedy_actions

HOSPITAL = Path(__file__).resolve().parents[1]
SEED = 1
PROTOCOL = "2025-06-18"
JSONRPC_HEADERS = {"accept": "application/json, text/event-stream", "content-type": "application/json"}
# Words that would mean a reply leaks the host, the source, the seed or the hidden world.
LEAK_MARKERS = (
    "Traceback",
    "site-packages",
    "C:\\",
    "/home/",
    "/logs/",
    "events.jsonl",
    "ED72_SEED",
    "seed",
    "hazard_u",
    "divert_u",
    "upgrade_ct_u",
    "ed72_sim",
)
SOURCE_FILE = re.compile(r"[\w/\\]+\.py\b")


def make_host(tmp_path: Path, seed: int = SEED) -> server.ToolHost:
    tmp_path.mkdir(parents=True, exist_ok=True)
    return server.ToolHost(Simulation(generate_world(seed), tmp_path / "events.jsonl"), "HANDBOOK TEXT")


def log_lines(host: server.ToolHost) -> list[dict]:
    return [json.loads(line) for line in host.sim._log_path.read_text(encoding="utf-8").splitlines()]


def agent_lines(host: server.ToolHost) -> list[dict]:
    return [line for line in log_lines(host) if line["src"] == "agent"]


def run_client(host: server.ToolHost, body) -> object:
    async def go():
        async with Client(server.build_server(host)) as client:
            return await body(client)

    return asyncio.run(go())


def assert_no_leak(text: str) -> None:
    for marker in LEAK_MARKERS:
        assert marker not in text, f"{marker!r} leaked in {text[:300]!r}"
    assert not SOURCE_FILE.search(text), f"a source file name leaked in {text[:300]!r}"


class RawMcp:
    """JSON-RPC over the real streamable-HTTP app, so the attacker controls the exact bytes."""

    def __init__(self, client: TestClient) -> None:
        self.client = client
        init = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": PROTOCOL,
                "capabilities": {},
                "clientInfo": {"name": "rt", "version": "1"},
            },
        }
        res = client.post("/mcp", headers=JSONRPC_HEADERS, json=init)
        assert res.status_code == 200
        self.headers = {
            **JSONRPC_HEADERS,
            "mcp-session-id": res.headers["mcp-session-id"],
            "mcp-protocol-version": PROTOCOL,
        }
        client.post(
            "/mcp", headers=self.headers, json={"jsonrpc": "2.0", "method": "notifications/initialized"}
        )

    def send(self, method: str, params: dict | None = None):
        body = {"jsonrpc": "2.0", "id": 2, "method": method, "params": params or {}}
        return self.client.post("/mcp", headers=self.headers, json=body)

    def step_raw(self, arguments_json: str):
        body = (
            '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"step","arguments":'
            + arguments_json
            + "}}"
        )
        return self.client.post("/mcp", headers=self.headers, content=body)


@pytest.fixture
def raw(tmp_path):
    host = make_host(tmp_path)
    with TestClient(server.build_server(host).http_app()) as client:
        yield host, RawMcp(client)


# --- row 28: routes and MCP features --------------------------------------------------------------


PROBE_PATHS = [
    "/",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/admin",
    "/reset",
    "/seed",
    "/finalize",
    "/events",
    "/log",
    "/sse",
    "/messages",
    "/messages/",
    "/mcp/tools",
    "/mcp/x",
    "/.well-known/oauth-authorization-server",
    "/.well-known/oauth-protected-resource",
    "/..%2fserver.py",
    "/health/..%2f..%2fserver.py",
    "/%2e%2e/%2e%2e/etc/passwd",
    "/static/..%5cserver.py",
]


def test_only_mcp_and_health_are_routed(tmp_path):
    app = server.build_server(make_host(tmp_path)).http_app()
    assert sorted(route.path for route in app.routes) == ["/health", "/mcp"]


@pytest.mark.parametrize("method", ["GET", "POST", "PUT", "DELETE"])
@pytest.mark.parametrize("path", PROBE_PATHS)
def test_other_paths_answer_404(tmp_path, method, path):
    with TestClient(server.build_server(make_host(tmp_path)).http_app()) as client:
        res = client.request(method, path, follow_redirects=False)
    assert res.status_code == 404
    assert_no_leak(res.text)


def test_health_answers_only_ok_true_and_only_to_get(tmp_path):
    host = make_host(tmp_path)
    with TestClient(server.build_server(host).http_app()) as client:
        res = client.get("/health")
        assert res.status_code == 200
        assert res.content == b'{"ok":true}'
        for method in ("POST", "PUT", "DELETE", "PATCH", "OPTIONS"):
            assert client.request(method, "/health").status_code == 405
        assert client.get("/health?seed=1&debug=1").json() == {"ok": True}
    assert host.calls == 0
    assert agent_lines(host) == []


def test_get_mcp_without_a_session_is_refused_and_leaks_nothing(tmp_path):
    with TestClient(server.build_server(make_host(tmp_path)).http_app()) as client:
        res = client.get("/mcp")
    assert res.status_code >= 400
    assert_no_leak(res.text)


def test_no_resources_prompts_or_templates_are_exposed(tmp_path):
    async def body(client):
        got = {
            "resources": await client.list_resources(),
            "templates": await client.list_resource_templates(),
            "prompts": await client.list_prompts(),
        }
        errors = []
        for uri in ("file:///etc/passwd", "file:///proc/self/environ", "resource://world", "data://state"):
            with pytest.raises(Exception) as err:
                await client.read_resource(uri)
            errors.append(str(err.value))
        with pytest.raises(Exception) as err:
            await client.get_prompt("system")
        errors.append(str(err.value))
        return got, errors

    got, errors = run_client(make_host(tmp_path), body)
    assert got == {"resources": [], "templates": [], "prompts": []}
    for text in errors:
        assert_no_leak(text)


def test_completion_logging_and_sampling_methods_leak_nothing(raw):
    host, mcp = raw
    for method, params in [
        (
            "completion/complete",
            {"ref": {"type": "ref/prompt", "name": "x"}, "argument": {"name": "a", "value": ""}},
        ),
        ("logging/setLevel", {"level": "debug"}),
        ("sampling/createMessage", {"messages": [], "maxTokens": 1}),
        ("resources/read", {"uri": "file:///etc/passwd"}),
        ("admin/reset", {}),
    ]:
        res = mcp.send(method, params)
        assert_no_leak(res.text)
        assert '"tick"' not in res.text
    assert host.calls == 0
    assert host.sim.tick == 0


def test_tool_list_is_exactly_the_three_tools_with_closed_schemas(tmp_path):
    tools = run_client(make_host(tmp_path), lambda client: client.list_tools())
    by_name = {t.name: t for t in tools}
    assert set(by_name) == {"rules", "observe", "step"}
    for name in ("rules", "observe"):
        assert by_name[name].input_schema == {
            "type": "object",
            "additionalProperties": False,
            "properties": {},
        }
    step_schema = by_name["step"].input_schema
    assert step_schema["required"] == ["actions"]
    assert step_schema["additionalProperties"] is False
    assert step_schema["properties"] == {"actions": {"items": {}, "type": "array"}}


def test_tool_descriptions_and_instructions_leak_nothing(tmp_path):
    async def body(client):
        tools = await client.list_tools()
        return client.instructions, [t.model_dump_json() for t in tools]

    instructions, dumps = run_client(make_host(tmp_path), body)
    assert instructions == "Run the ED for 144 ticks. Call `rules` first, then `step` once per tick."
    for text in [instructions, *dumps]:
        assert_no_leak(text)


# --- row 29: call cap under spam and concurrency, oversized payloads, N1 ---------------------------


def test_call_cap_holds_under_threads(tmp_path):
    host = make_host(tmp_path)
    replies: list[dict] = []
    guard = threading.Lock()

    def spam(worker: int) -> None:
        for i in range(70):
            tool = ("rules", "observe", "step")[(worker + i) % 3]
            out = host.call(tool, {"actions": []} if tool == "step" else {})
            with guard:
                replies.append(out)

    threads = [threading.Thread(target=spam, args=(w,)) for w in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert host.calls == 560
    assert sum(1 for r in replies if r == {"error": "call_cap_reached"}) == 60
    lines = log_lines(host)
    assert [line["seq"] for line in lines] == list(range(len(lines)))
    agent = [line for line in lines if line["src"] == "agent"]
    assert len(agent) == 560
    good_steps = [a for a in agent if a["tool"] == "step" and "error" not in a["result"]]
    assert len(good_steps) == host.sim.tick + host.sim.finished
    assert [a["t"] for a in good_steps] == list(range(len(good_steps)))
    assert all(a["result"] == {"error": "call_cap_reached"} for a in agent[500:])


SERVER_CODE = """
import pathlib, sys
import server
from ed72_sim.engine import Simulation
from ed72_sim.world import generate_world
server.CALL_CAP = int(sys.argv[3])
h = server.ToolHost(Simulation(generate_world(1), pathlib.Path(sys.argv[2])), "HANDBOOK TEXT")
server.build_server(h).run(transport="streamable-http", host="127.0.0.1", port=int(sys.argv[1]), path="/mcp")
"""


def start_server(log: Path, cap: int) -> tuple[subprocess.Popen, str]:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    proc = subprocess.Popen(
        [sys.executable, "-c", SERVER_CODE, str(port), str(log), str(cap)],
        cwd=HOSPITAL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    deadline = time.time() + 30
    while True:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1)
            return proc, f"http://127.0.0.1:{port}/mcp"
        except OSError:
            if time.time() > deadline or proc.poll() is not None:
                proc.kill()
                raise RuntimeError("hospital server did not start")
            time.sleep(0.2)


@pytest.fixture
def http_server(tmp_path):
    log = tmp_path / "events.jsonl"
    proc, url = start_server(log, cap=40)
    try:
        yield url, log
    finally:
        proc.kill()
        proc.wait()


def test_call_cap_holds_across_parallel_http_sessions(http_server):
    url, log = http_server

    async def one_client(n: int) -> list[dict]:
        out = []
        async with Client(url) as client:
            for i in range(15):
                tool = "step" if (n + i) % 2 else "observe"
                res = await client.call_tool(tool, {"actions": []} if tool == "step" else {})
                out.append(res.structured_content)
        return out

    async def main() -> list[dict]:
        groups = await asyncio.gather(*(one_client(n) for n in range(4)))
        return [r for g in groups for r in g]

    replies = asyncio.run(main())
    assert len(replies) == 60
    assert sum(1 for r in replies if r == {"error": "call_cap_reached"}) == 20
    lines = [json.loads(x) for x in log.read_text(encoding="utf-8").splitlines()]
    assert [line["seq"] for line in lines] == list(range(len(lines)))
    agent = [line for line in lines if line["src"] == "agent"]
    assert len(agent) == 60
    assert all(a["result"] == {"error": "call_cap_reached"} for a in agent[40:])


def test_sessions_share_one_hospital_and_reconnecting_does_not_reset(http_server):
    url, _ = http_server

    async def main() -> tuple[int, int, int]:
        async with Client(url) as a, Client(url) as b:
            await a.call_tool("step", {"actions": []})
            seen_by_b = (await b.call_tool("observe", {})).structured_content["tick"]
            await b.call_tool("step", {"actions": []})
            seen_by_a = (await a.call_tool("observe", {})).structured_content["tick"]
        async with Client(url) as fresh:
            after_reconnect = (await fresh.call_tool("observe", {})).structured_content["tick"]
        return seen_by_b, seen_by_a, after_reconnect

    assert asyncio.run(main()) == (1, 2, 2)


def run_episode(host: server.ToolHost, spam_per_tick: int) -> dict:
    for _ in range(c.TICKS):
        for i in range(spam_per_tick):
            host.call("rules" if i % 2 else "observe", {})
        host.call("step", {"actions": greedy_actions(host.sim.observe())})
    return score(host.sim.events)


def test_rules_and_observe_spam_does_not_change_the_reward(tmp_path):
    quiet = run_episode(make_host(tmp_path / "a"), 0)
    spam = run_episode(make_host(tmp_path / "b"), 2)
    for key in ("O", "T", "W", "B", "score", "reward"):
        if key in quiet:
            assert spam[key] == quiet[key]


@pytest.mark.parametrize(
    "args",
    [{"actions": "admit"}, {"actions": None}, {"actions": 5}, {"actions": {"type": "divert"}}, {}, {"a": []}],
    ids=["string", "null", "number", "dict", "missing", "wrong-key"],
)
def test_non_list_step_is_refused_before_the_sim(tmp_path, args):
    """N1: FastMCP's schema check refuses a non-list before ToolHost or the sim see it."""
    host = make_host(tmp_path)
    before = copy.deepcopy(host.sim.events)
    res = run_client(host, lambda client: client.call_tool("step", args, raise_on_error=False))
    assert res.is_error
    assert_no_leak(res.content[0].text)
    assert host.sim.tick == 0
    assert host.sim.events == before
    # Not counted and not logged: harmless for the reward, see docs/REDTEAM.md N4.
    assert host.calls == 0


def test_10000_actions_reach_the_log_as_50(tmp_path):
    host = make_host(tmp_path)
    actions = [{"type": "divert"}] + [{"type": "repair"}] * 9_999
    res = run_client(host, lambda client: client.call_tool("step", {"actions": actions}))
    assert len(res.structured_content["results"]) == 10_000
    step = next(a for a in agent_lines(host) if a["tool"] == "step")
    assert len(step["args"]["actions"]) == server.MAX_ACTIONS


def test_body_over_4_mib_is_refused_with_413(raw):
    host, mcp = raw
    res = mcp.step_raw('{"actions":[{"type":"repair","x":"' + "A" * (4 * 1024 * 1024) + '"}]}')
    assert res.status_code == 413
    assert host.sim.tick == 0 and host.calls == 0


def test_deeply_nested_json_is_refused_by_the_parser(raw):
    host, mcp = raw
    for depth in (200, 5_000):
        res = mcp.step_raw('{"actions":[{"type":"divert","x":' + "[" * depth + "]" * depth + "}]}")
        assert res.status_code == 400 and "-32700" in res.text
    assert host.sim.tick == 0 and host.calls == 0
    assert not host.sim.observe()["diversion"]["active"]


def test_huge_integer_is_refused_by_the_parser(raw):
    host, mcp = raw
    res = mcp.step_raw('{"actions":[{"type":"divert","x":' + "9" * 4_301 + "}]}")
    assert res.status_code == 400 and "-32700" in res.text
    assert host.sim.tick == 0 and not host.sim.observe()["diversion"]["active"]


def test_odd_values_that_parse_are_logged_and_replay_exactly(raw, tmp_path):
    """A 4300-digit int, NaN and a 120-deep list all pass the parser. Each step is applied and
    logged; the NaN and deep cases then fail to serialise the reply (N5), but replay still matches."""
    host, mcp = raw
    for junk in ("9" * 4_300, "NaN", "[" * 120 + "]" * 120, '"' + "B" * 100_000 + '"'):
        tick = host.sim.tick
        # A rejected action is echoed back in last_rejected, so the reply has to serialise it.
        res = mcp.step_raw('{"actions":[{"type":"repair","x":' + junk + "}]}")
        assert res.status_code == 200
        assert host.sim.tick == tick + 1
    steps = [a for a in agent_lines(host) if a["tool"] == "step"]
    assert [a["t"] for a in steps] == [0, 1, 2, 3]
    host.sim.run_to_end()
    replay = collect.collect(SEED, host.sim._log_path, tmp_path / "report.json")
    assert replay == score(host.sim.events)


@pytest.mark.xfail(
    sys.platform == "win32",
    strict=True,
    # pydantic-core's Windows build caps serialisation depth below 100; on Linux (CI, the hospital
    # image) the 120-deep echo serialises, so there this is a plain regression test.
    reason="N5 (Windows only): a step whose reply cannot be serialised returns is_error "
    "although the tick advanced",
)
def test_a_step_that_advanced_the_tick_does_not_reply_with_an_error(raw):
    host, mcp = raw
    res = mcp.step_raw('{"actions":[{"type":"repair","x":' + "[" * 120 + "]" * 120 + "}]}")
    assert host.sim.tick == 1
    assert '"isError":true' not in res.text


@pytest.mark.xfail(
    strict=True,
    reason="latent (N6): engine.step applies actions before copying them for the log; "
    "a copy failure leaves live state the log does not have. Not reachable over HTTP today",
)
def test_a_failed_log_write_leaves_no_unlogged_state(tmp_path):
    host = make_host(tmp_path)
    junk: list = []
    for _ in range(2_000):
        junk = [junk]
    with pytest.raises(RecursionError):
        host.call("step", {"actions": [{"type": "divert", "x": junk}]})
    assert not host.sim.observe()["diversion"]["active"]


def test_refused_step_logs_at_most_50_actions(tmp_path):
    """E1, fixed in c281e04: a refused step logged every action it was sent, past the 50 cap."""
    host = make_host(tmp_path)
    for _ in range(c.TICKS):
        host.call("step", {"actions": []})
    host.call("step", {"actions": [{"type": "repair", "pad": "x" * 1_000}] * 5_000})
    refused = agent_lines(host)[-1]
    assert refused["result"] == {"error": "episode_over"}
    assert len(refused["args"]["actions"]) <= server.MAX_ACTIONS


def test_after_the_cap_nothing_moves_and_after_the_end_only_reads_work(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "CALL_CAP", c.TICKS + 2)
    host = make_host(tmp_path)
    for _ in range(c.TICKS):
        host.call("step", {"actions": []})
    assert host.call("observe", {})["finished"] is True
    assert host.call("step", {"actions": [{"type": "divert"}]}) == {"error": "episode_over"}
    events = copy.deepcopy(host.sim.events)
    for tool in ("rules", "observe", "step"):
        assert host.call(tool, {"actions": []} if tool == "step" else {}) == {"error": "call_cap_reached"}
    new = host.sim.events[len(events) :]
    assert host.sim.events[: len(events)] == events
    assert all(e["src"] == "agent" and e["result"] == {"error": "call_cap_reached"} for e in new)


# --- row 30: error text and value-level covert channels ---------------------------------------------


def test_error_replies_leak_no_path_source_or_seed(tmp_path):
    async def body(client):
        texts = []
        for name, args in [
            ("step", {"actions": "x"}),
            ("step", {}),
            ("rules", {"reveal": 1}),
            ("observe", {"debug": True}),
            ("world", {}),
            ("../server", {}),
        ]:
            res = await client.call_tool(name, args, raise_on_error=False)
            texts.append(res.content[0].text)
        return texts

    for text in run_client(make_host(tmp_path), body):
        assert_no_leak(text)


def truncated_future(world, horizon: int):
    """The same world up to `horizon`; after it, no arrivals, no new events and no hazards."""
    patients = tuple(
        dataclasses.replace(p, hazard_u=p.hazard_u[: horizon + 1] + (0.999,) * (c.TICKS - horizon - 1))
        for p in world.patients
        if p.arrival_tick <= horizon
    )
    events = tuple(e for e in world.events if e.start_tick - e.warning_ticks <= horizon)
    return dataclasses.replace(world, patients=patients, events=events)


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_observations_do_not_depend_on_the_future(seed):
    """If any value, float or ordering in the observation carried future arrivals, events or dice,
    two worlds that agree only up to tick H would give different observations before H."""
    horizon = 60
    world = generate_world(seed)
    real, cut = Simulation(world), Simulation(truncated_future(world, horizon))
    assert len(cut.world.patients) < len(world.patients)
    for _ in range(horizon):
        obs = real.observe()
        assert cut.observe() == obs
        actions = greedy_actions(obs)
        assert cut.step(actions) == real.step(actions)
    assert cut.observe() == real.observe()


def walk_floats(value, out: list) -> list:
    if isinstance(value, float):
        out.append(value)
    elif isinstance(value, dict):
        for v in value.values():
            walk_floats(v, out)
    elif isinstance(value, list):
        for v in value:
            walk_floats(v, out)
    return out


def test_no_observation_float_carries_rng_state():
    world = generate_world(SEED)
    uniforms = {u for p in world.patients for u in (p.divert_u, p.upgrade_ct_u, *p.hazard_u)}
    sim = Simulation(world)
    floats: list[float] = []
    while not sim.finished:
        obs = sim.observe()
        walk_floats(obs, floats)
        sim.step(greedy_actions(obs))
    assert floats
    assert all(round(f * 10) == f * 10 or abs(round(f * 10) - f * 10) < 1e-9 for f in floats)
    assert not uniforms & set(floats)
