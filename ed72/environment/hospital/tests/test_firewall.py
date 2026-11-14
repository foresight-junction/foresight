"""Hidden-information firewall (issue #31): no tool result may leak the future, the seed or the score.

Three groups:
- checker tests on MOCK CONTRACTS-shaped fixtures, including mutations that must be caught. They
  pin the checks independently of the sim, so a sim bug cannot hide inside the base case;
- episode tests (a) to (e): a scripted policy plays full episodes on two seeds against the real
  sim and every raw result is checked. The same episode through the MCP server (in-memory client),
  the call cap and the tool list skip until the tool server (#57) merges; (f) skips until the
  image layout (#58) exists;
- episode mutations: the sim's view function is monkeypatched to leak, and the suite must fail.
"""

import asyncio
import copy
import dataclasses
import json
import re
from collections.abc import Awaitable, Callable
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import firewall_fixtures as fx
import pytest
from firewall_checks import (
    WARNING_LEAD,
    Truth,
    Violation,
    check_result,
    past_log_violations,
    truth_from_world,
)
from firewall_policy import ScriptedPolicy
from firewall_shapes import REASONS, TOOLS

HOSPITAL = Path(__file__).resolve().parents[1]
ENVIRONMENT = HOSPITAL.parent
SEEDS = (918_273, 4_071_999)  # large, so the seed's digits are distinctive in results


def rules_of(violations: list[Violation]) -> set[str]:
    return {v.rule for v in violations}


# --- checker tests on fixtures (run today) -------------------------------------------------------


@pytest.mark.parametrize(
    ("tool", "payload"),
    [
        ("observe", fx.observation()),
        ("step", fx.step_result()),
        ("rules", fx.rules_result()),
        ("step", {"error": "episode_over"}),
        ("observe", {"error": "call_cap_reached"}),
    ],
)
def test_clean_fixture_passes(tool: str, payload: dict) -> None:
    assert check_result(tool, json.dumps(payload), fx.TRUTH, fx.TICK) == []


def test_agent_echo_in_last_rejected_is_not_value_checked() -> None:
    obs = fx.observation()
    obs["last_rejected"][0]["action"] = {"type": "admit", "patient": "P060", "zone": "acute", "seed": 1}
    assert check_result("observe", json.dumps(obs), fx.TRUTH, fx.TICK) == []


def _set(path: list[Any], value: Any) -> Callable[[dict], None]:
    def mutate(payload: dict) -> None:
        node = payload
        for key in path[:-1]:
            node = node[key]
        node[path[-1]] = value

    return mutate


def _append(path: list[Any], value: Any) -> Callable[[dict], None]:
    def mutate(payload: dict) -> None:
        node = payload
        for key in path:
            node = node[key]
        node.append(value)

    return mutate


def _delete(path: list[Any]) -> Callable[[dict], None]:
    def mutate(payload: dict) -> None:
        node = payload
        for key in path[:-1]:
            node = node[key]
        del node[path[-1]]

    return mutate


OBS = ["observation"]
# (name, tool, mutation applied to the clean step result or rules result, assertion it must trip)
MUTATIONS = [
    # (a) future arrivals and unannounced events
    (
        "future_arrival_waiting",
        "step",
        _append(
            [*OBS, "waiting"],
            {"id": "P053", "esi": 3, "arrived_tick": 38, "waited_ticks": 0, "needs_ct": False},
        ),
        "a",
    ),
    ("future_patient_in_bed", "step", _set([*OBS, "beds", 1, "patient"], "P055"), "a"),
    ("future_patient_in_text", "step", _set([*OBS, "clock"], "Day 2 02:30, next P053"), "a"),
    (
        "unannounced_warning",
        "step",
        _append([*OBS, "warnings"], {"event": "staff_sickness", "start_tick": 60}),
        "a",
    ),
    ("sick_before_sick_call", "step", _set([*OBS, "staff", 10, "status"], "sick"), "a"),
    ("future_tick_field", "step", _set([*OBS, "waiting", 0, "arrived_tick"], 60), "a"),
    # (b) seed, config, dice, score
    ("seed_field", "step", _set([*OBS, "seed"], fx.SEED), "b"),
    ("seed_value_in_known_field", "step", _set([*OBS, "budget", "budget"], fx.SEED), "b"),
    ("score_value", "step", _set([*OBS, "totals", "score"], 71.2), "b"),
    ("score_components", "step", _set(["O"], 0.82), "b"),
    ("reward", "step", _set(["reward"], 0.712), "b"),
    ("rng_state", "step", _set([*OBS, "ct", "rng"], [3, [1, 2], None]), "b"),
    ("dice_roll", "step", _set([*OBS, "staff", 0, "fatigue"], fx.DICE[0]), "b"),
    ("log_path_in_rules", "rules", _set(["text"], "Log: /var/lib/ed72/events.jsonl"), "b"),
    ("seed_in_rules", "rules", _set(["text"], f"Today's seed is {fx.SEED}."), "b"),
    ("config_env", "step", _set([*OBS, "clock"], "ED72_CONFIG=/cfg/hard.json"), "b"),
    # (c) warnings
    (
        "warning_too_early",
        "step",
        _append([*OBS, "warnings"], {"event": "bus_crash", "start_tick": 101}),
        "c",
    ),
    ("warning_wrong_start", "step", _set([*OBS, "warnings", 0, "start_tick"], 46), "c"),
    ("warning_missing", "step", _set([*OBS, "warnings"], []), "c"),
    ("warning_duplicate", "step", _append([*OBS, "warnings"], {"event": "flu_wave", "start_tick": 45}), "c"),
    # (d) exact shapes
    ("extra_field", "step", _set([*OBS, "waiting", 0, "true_esi"], 1), "d"),
    ("extra_top_level", "step", _set(["debug"], {}), "d"),
    ("missing_field", "step", _delete([*OBS, "ct"]), "d"),
    ("bool_as_int", "step", _set([*OBS, "finished"], 0), "d"),
    ("bad_reason", "step", _set(["results", 1, "reason"], "patient_will_die"), "d"),
    ("bed_missing", "step", _delete([*OBS, "beds", 16]), "d"),
    ("bed_wrong_zone", "step", _set([*OBS, "beds", 0, "zone"], "acute"), "d"),
    ("waited_inconsistent", "step", _set([*OBS, "waiting", 0, "waited_ticks"], 5), "d"),
    ("tick_mismatch", "step", _set([*OBS, "tick"], 36), "d"),
    ("countdown_on_regular_staff", "step", _set([*OBS, "staff", 0, "ticks_until_change"], 23), "d"),
]


@pytest.mark.parametrize(("name", "tool", "mutate", "rule"), MUTATIONS, ids=[m[0] for m in MUTATIONS])
def test_fixture_mutation_is_caught(name: str, tool: str, mutate: Callable[[dict], None], rule: str) -> None:
    payload = fx.rules_result() if tool == "rules" else fx.step_result()
    mutate(payload)
    violations = check_result(tool, json.dumps(payload), fx.TRUTH, fx.TICK)
    assert rule in rules_of(violations), violations


def test_ct_down_before_breakdown_is_caught() -> None:
    later = dataclasses.replace(
        fx.TRUTH,
        events=tuple(
            dataclasses.replace(e, start_tick=40) if e.kind == "ct_breakdown" else e for e in fx.TRUTH.events
        ),
    )
    assert "a" in rules_of(check_result("observe", json.dumps(fx.observation()), later, fx.TICK))


@pytest.mark.parametrize(
    "payload",
    [
        {"error": "call_cap_reached", "calls": 500},
        {"error": "out_of_budget"},
        {"error": "episode_over", "seed": 1},
    ],
)
def test_error_results_carry_nothing_else(payload: dict) -> None:
    assert "d" in rules_of(check_result("step", json.dumps(payload), fx.TRUTH, fx.TICK))


def test_unknown_tool_and_non_json_are_caught() -> None:
    assert "d" in rules_of(check_result("ground_truth", json.dumps(fx.observation()), fx.TRUTH, fx.TICK))
    assert "d" in rules_of(check_result("observe", "seed=918273", fx.TRUTH, fx.TICK))


# --- episodes on the real sim; the MCP variants skip until the tool server (#57) merges ---------


@dataclasses.dataclass(frozen=True)
class Call:
    tool: str
    args: dict
    raw: str
    as_of: int  # the sim's true tick after the call
    log_len: int  # length of the sim's event log after the call
    channels: tuple[str, ...] = ()  # anything the agent received besides the one JSON text block


@dataclasses.dataclass
class Episode:
    seed: int
    truth: Truth
    world: Any
    calls: list[Call]
    policy: ScriptedPolicy
    log: list[dict]


Caller = Callable[[str, dict], Awaitable[tuple[str, tuple[str, ...]]]]


def _sim_stack() -> tuple[ModuleType, ModuleType]:
    engine = pytest.importorskip("ed72_sim.engine", reason="needs the sim core (#48)")
    world = pytest.importorskip("ed72_sim.world", reason="needs the world generator (#46)")
    return engine, world


def _server_stack() -> tuple[ModuleType, ModuleType]:
    fastmcp = pytest.importorskip("fastmcp", reason="needs fastmcp in the hospital pyproject (#57)")
    server = pytest.importorskip("server", reason="needs the tool server (#57)")
    return server, fastmcp


def _handbook() -> str:
    path = ENVIRONMENT / "workspace" / "HANDBOOK.md"
    return path.read_text(encoding="utf-8") if path.exists() else "MOCK: handbook not written yet (#7)"


async def _loop(call: Caller, sim: Any, truth: Truth, ticks: int, policy: ScriptedPolicy) -> list[Call]:
    """Play like an agent: rules once, then observe and step every tick, recording each raw result."""
    calls: list[Call] = []

    async def record(tool: str, args: dict) -> dict:
        raw, channels = await call(tool, args)
        calls.append(Call(tool, copy.deepcopy(args), raw, sim.tick, len(sim.events), channels))
        return json.loads(raw)

    await record("rules", {})
    while True:
        obs = await record("observe", {})
        if obs["finished"]:
            await record("step", {"actions": []})  # must be episode_over
            break
        if obs["tick"] >= ticks:
            break
        future = next((pid for pid, t in truth.arrivals.items() if t > obs["tick"]), None)
        await record("step", {"actions": policy.actions(obs, future)})
    return calls


async def _drive(sim: Any, truth: Truth, ticks: int, policy: ScriptedPolicy, via_mcp: bool) -> list[Call]:
    if not via_mcp:
        # The sim's own results, as server.ToolHost passes them on below the call cap.
        async def direct(tool: str, args: dict) -> tuple[str, tuple[str, ...]]:
            if tool == "rules":
                return json.dumps({"text": _handbook()}), ()
            return json.dumps(sim.observe() if tool == "observe" else sim.step(args["actions"])), ()

        return await _loop(direct, sim, truth, ticks, policy)
    server, fastmcp = _server_stack()
    async with fastmcp.Client(server.build_server(server.ToolHost(sim, _handbook()))) as client:

        async def mcp(tool: str, args: dict) -> tuple[str, tuple[str, ...]]:
            result = await client.call_tool(tool, args)
            raw = result.content[0].text
            return raw, output_channel_problems(result.content, result.structured_content, raw)

        return await _loop(mcp, sim, truth, ticks, policy)


def play(seed: int, ticks: int = 10_000, via_mcp: bool = False) -> Episode:
    engine, world_mod = _sim_stack()
    world = world_mod.generate_world(seed)
    sim = engine.Simulation(world)
    truth = truth_from_world(world)
    policy = ScriptedPolicy()
    calls = asyncio.run(_drive(sim, truth, ticks, policy, via_mcp))
    return Episode(seed, truth, world, calls, policy, sim.events)


def output_channel_problems(content: list[Any], structured: Any, raw: str) -> tuple[str, ...]:
    """The agent must get one text block, and structured content (if any) equal to it."""
    problems = []
    if len(content) != 1 or getattr(content[0], "type", None) != "text":
        problems.append(f"{len(content)} content blocks: {[getattr(b, 'type', b) for b in content]}")
    if structured is not None and structured != json.loads(raw):
        problems.append("structured content differs from the text block")
    return tuple(problems)


def echo_violations(calls: list[Call]) -> list[Violation]:
    """last_rejected must be exactly the rejected actions of the previous applied step.

    walk() does not look inside last_rejected[i].action, so this is what keeps that echo from
    becoming a channel, in observe results as well as step results.
    """
    out = []
    expected: list[dict] = []
    for c in calls:
        payload = json.loads(c.raw)
        if not isinstance(payload, dict) or "error" in payload:
            continue
        if c.tool == "step" and isinstance(payload.get("results"), list):
            expected = [
                {"index": r["index"], "action": c.args["actions"][r["index"]], "reason": r.get("reason")}
                for r in payload["results"]
                if isinstance(r, dict) and r.get("ok") is False
            ]
        obs = payload if c.tool == "observe" else payload.get("observation")
        if isinstance(obs, dict) and obs.get("last_rejected") != expected:
            out.append(
                Violation("d", "$.last_rejected", f"not the verbatim rejections of the last step: {c}")
            )
    return out


def firewall_violations(episode: Episode) -> list[Violation]:
    out = [
        v
        for c in episode.calls
        for v in check_result(c.tool, c.raw, episode.truth, c.as_of, episode.log[: c.log_len])
    ]
    out += [Violation("d", "$", f"{c.tool}: {p}") for c in episode.calls for p in c.channels]
    return out + echo_violations(episode.calls)


def test_output_channels_beyond_one_text_block_are_caught() -> None:
    raw = json.dumps(fx.observation())
    text = SimpleNamespace(type="text", text=raw)
    assert output_channel_problems([text], json.loads(raw), raw) == ()
    assert output_channel_problems([text, SimpleNamespace(type="text", text="seed 918273")], None, raw)
    assert output_channel_problems([text], {**json.loads(raw), "seed": fx.SEED}, raw)


def _echo_calls(observed_action: dict) -> list[Call]:
    sent = [{"type": "divert"}, {"type": "admit", "patient": "P050", "zone": "fast_track"}]
    obs = fx.observation()
    obs["last_rejected"][0]["action"] = observed_action
    return [
        Call("step", {"actions": sent}, json.dumps(fx.step_result()), fx.TICK, 0),
        Call("observe", {}, json.dumps(obs), fx.TICK, 0),
    ]


def test_echo_of_the_sent_action_passes_and_an_altered_echo_is_caught() -> None:
    action = {"type": "admit", "patient": "P050", "zone": "fast_track"}
    assert echo_violations(_echo_calls(action)) == []
    assert "d" in rules_of(echo_violations(_echo_calls({**action, "seed": fx.SEED})))


@pytest.fixture(scope="module")
def episodes() -> list[Episode]:
    return [play(seed) for seed in SEEDS]


def _rule(episodes: list[Episode], rule: str) -> list[tuple[int, Violation]]:
    return [(ep.seed, v) for ep in episodes for v in firewall_violations(ep) if v.rule == rule]


def test_a_no_future_arrival_or_unannounced_event(episodes: list[Episode]) -> None:
    for ep in episodes:
        assert any(t > 0 for t in ep.truth.arrivals.values()), "nothing in the future to protect"
        assert {"staff_sickness", "ct_breakdown"} <= {e.kind for e in ep.truth.events}
        assert ep.calls[-1].as_of == 143, "the episode must reach the end so every event is covered"
    assert _rule(episodes, "a") == []


def test_b_no_seed_rng_dice_log_or_score(episodes: list[Episode]) -> None:
    assert _rule(episodes, "b") == []
    texts = {next(c.raw for c in ep.calls if c.tool == "rules") for ep in episodes}
    assert len(texts) == 1, "the rules text differs between seeds, so it can carry per-seed data"


def test_c_warnings_only_announced_exact_tick_and_lead_time(episodes: list[Episode]) -> None:
    for ep in episodes:
        for e in ep.world.events:  # the generator must use the rulebook's lead times
            assert e.warning_ticks == WARNING_LEAD.get(e.kind, 0), e
        first_seen: dict[tuple[str, int], int] = {}
        for c in ep.calls:
            if c.tool == "observe":
                for w in json.loads(c.raw)["warnings"]:
                    first_seen.setdefault((w["event"], w["start_tick"]), c.as_of)
        expected = {
            (e.kind, e.start_tick): e.start_tick - WARNING_LEAD[e.kind]
            for e in ep.truth.events
            if e.kind in WARNING_LEAD
        }
        assert first_seen == expected
    assert _rule(episodes, "c") == []


def test_d_results_match_contracts_exactly(episodes: list[Episode]) -> None:
    for ep in episodes:
        assert {c.tool for c in ep.calls} == set(TOOLS)
    assert _rule(episodes, "d") == []


def test_e_rejections_reasons_and_episode_over(episodes: list[Episode]) -> None:
    for ep in episodes:
        steps = [c for c in ep.calls if c.tool == "step"]
        by_tick = dict(enumerate(json.loads(c.raw) for c in steps[:-1]))  # one step per tick, in order
        for probe in ep.policy.probes:
            result = by_tick[probe.tick]["results"][probe.index]
            assert result == {"index": probe.index, "ok": False, "reason": probe.reason}, probe
        assert {p.reason for p in ep.policy.probes} == set(REASONS), "every CONTRACTS reason exercised"
        assert echo_violations(ep.calls) == []
        assert json.loads(steps[-1].raw) == {"error": "episode_over"}
        final = json.loads(ep.calls[-2].raw)
        assert final["finished"] is True and final["ticks_left"] == 0


def test_view_not_explained_by_the_log_is_caught(episodes: list[Episode]) -> None:
    ep = episodes[0]
    call = next(
        c
        for c in ep.calls
        if c.tool == "observe" and (o := json.loads(c.raw))["waiting"] and o["beds"][-1]["patient"] is None
    )
    log = ep.log[: call.log_len]
    obs = json.loads(call.raw)
    assert past_log_violations(obs, log, "$") == []
    covert = copy.deepcopy(obs)
    covert["totals"]["faints"] += 1  # a future count in a legitimate field
    extra_waiting = copy.deepcopy(obs)
    extra_waiting["waiting"].append(dict(obs["waiting"][0], id="P9998"))
    extra_bed = copy.deepcopy(obs)
    extra_bed["beds"][-1]["patient"] = obs["waiting"][0]["id"]
    for view in (covert, extra_waiting, extra_bed):
        assert "a" in rules_of(past_log_violations(view, log, "$"))


def test_mcp_results_equal_the_sim_results_and_leak_nothing(episodes: list[Episode]) -> None:
    _server_stack()
    via_mcp = play(SEEDS[0], via_mcp=True)
    assert firewall_violations(via_mcp) == []
    assert [json.loads(c.raw) for c in via_mcp.calls] == [json.loads(c.raw) for c in episodes[0].calls]


def test_e_call_cap_reached_leaks_nothing() -> None:
    engine, world_mod = _sim_stack()
    server, fastmcp = _server_stack()
    sim = engine.Simulation(world_mod.generate_world(SEEDS[0]))
    host = server.ToolHost(sim, _handbook())

    async def run() -> list[str]:
        async with fastmcp.Client(server.build_server(host)) as client:
            for _ in range(server.CALL_CAP):
                await client.call_tool("observe", {})
            return [
                (await client.call_tool(tool, args)).content[0].text
                for tool, args in (
                    ("rules", {}),
                    ("observe", {}),
                    ("step", {"actions": [{"type": "divert"}]}),
                )
            ]

    for raw in asyncio.run(run()):
        assert json.loads(raw) == {"error": "call_cap_reached"}
    assert sim.tick == 0, "a capped step must not advance the sim"


def test_exactly_the_contracts_tools() -> None:
    engine, world_mod = _sim_stack()
    server, fastmcp = _server_stack()
    host = server.ToolHost(engine.Simulation(world_mod.generate_world(SEEDS[0])), "")

    async def names() -> list[str]:
        async with fastmcp.Client(server.build_server(host)) as client:
            return sorted(t.name for t in await client.list_tools())

    assert asyncio.run(names()) == sorted(TOOLS), "a new tool must be added to the firewall checks first"


def _leak_future_arrival(obs: dict, state: Any) -> None:
    spec = next(p for p in state.world.patients if p.arrival_tick > obs["tick"])
    obs["waiting"].append(
        {
            "id": spec.id,
            "esi": spec.esi,
            "arrived_tick": spec.arrival_tick,
            "waited_ticks": 0,
            "needs_ct": False,
        }
    )


def _leak_unannounced_event(obs: dict, state: Any) -> None:
    ct = next(e for e in state.world.events if e.kind == "ct_breakdown")
    obs["warnings"].append({"event": ct.kind, "start_tick": ct.start_tick})


def _leak_next_arrivals_as_a_total(obs: dict, state: Any) -> None:
    obs["totals"]["faints"] = sum(p.arrival_tick == obs["tick"] + 1 for p in state.world.patients)


def _leak_sick_call_countdown(obs: dict, state: Any) -> None:
    sick = next(e for e in state.world.events if e.kind == "staff_sickness")
    obs["staff"][0]["ticks_until_change"] = max(0, sick.start_tick - obs["tick"])


def _leak_seed(obs: dict, state: Any) -> None:
    obs["seed"] = state.world.seed


def _leak_score(obs: dict, state: Any) -> None:
    obs["totals"]["score"] = 71.2


@pytest.mark.parametrize(
    ("leak", "rule"),
    [
        (_leak_future_arrival, "a"),
        (_leak_unannounced_event, "a"),
        (_leak_next_arrivals_as_a_total, "a"),
        (_leak_sick_call_countdown, "d"),
        (_leak_seed, "b"),
        (_leak_score, "b"),
    ],
    ids=["future_arrival", "unannounced_event", "covert_total", "sick_call_countdown", "seed", "score_value"],
)
def test_episode_mutation_makes_the_suite_fail(
    leak: Callable[[dict, Any], None], rule: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine, _ = _sim_stack()
    view = engine.build_observation

    def leaky(state: Any, tick: int, finished: bool) -> dict:
        obs = view(state, tick, finished)
        leak(obs, state)
        return obs

    monkeypatch.setattr(engine, "build_observation", leaky)
    violations = firewall_violations(play(SEEDS[0], ticks=3))
    assert rule in rules_of(violations)


# --- (f) the agent image holds no sim code, seed, config or scorer (skip until #58) --------------

MAIN_COPY_ALLOWED = re.compile(r"(workspace/[\w./-]+|ward)")
MAIN_NODE_COPY_ALLOWED = frozenset({"/usr/local/bin/node", "/usr/local/lib/node_modules"})
HIDDEN_MARKERS = (
    "ED72_SEED",
    "ED72_CONFIG",
    "ed72_sim",
    "events.jsonl",
    "/var/lib/ed72",
    "collect.py",
    "scoring",
)


def _instructions(dockerfile: str) -> list[tuple[str, list[str]]]:
    joined = re.sub(r"\\\n", " ", dockerfile)
    rows = [
        line.split() for line in joined.splitlines() if line.strip() and not line.lstrip().startswith("#")
    ]
    return [(row[0].upper(), row[1:]) for row in rows]


def _service_block(compose: str, name: str) -> str:
    """The lines under `name:` inside `services:`, at any indentation (stdlib only, no YAML parser)."""
    lines = compose.splitlines()
    start = next((i for i, line in enumerate(lines) if line.strip() == "services:"), None)
    assert start is not None, "docker-compose.yaml has no services: key"
    head = next(
        (i for i in range(start + 1, len(lines)) if re.fullmatch(rf"\s+{name}:\s*(#.*)?", lines[i])), None
    )
    assert head is not None, f"docker-compose.yaml has no {name} service"
    indent = len(lines[head]) - len(lines[head].lstrip())
    block = []
    for line in lines[head + 1 :]:
        if line.strip() and len(line) - len(line.lstrip()) <= indent:
            break
        block.append(line)
    return "\n".join(block)


def test_f_main_image_has_no_sim_seed_config_or_scorer() -> None:
    dockerfile = ENVIRONMENT / "Dockerfile"
    compose = ENVIRONMENT / "docker-compose.yaml"
    if not dockerfile.exists() or not compose.exists():
        pytest.skip("needs the Harbor layout ed72/environment/Dockerfile and docker-compose.yaml (#58)")
    stages: dict[str, str] = {}
    for op, args in _instructions(dockerfile.read_text(encoding="utf-8")):
        if op == "FROM" and len(args) == 3 and args[1].upper() == "AS":
            stages[args[2]] = args[0]
        if op in ("COPY", "ADD"):
            sources = [a for a in args if not a.startswith("--")][:-1]
            stage = next((a.split("=", 1)[1] for a in args if a.startswith("--from=")), None)
            if stage is not None:
                # The OpenCode preinstall (#89) may take only the Node runtime from an official node image.
                assert stages.get(stage, "").startswith("node:"), (
                    f"main image copies from a non-node stage: {args}"
                )
                for src in sources:
                    assert src in MAIN_NODE_COPY_ALLOWED, f"main image copies {src!r} from the node stage"
                continue
            assert not any(a.startswith("--from") for a in args), (
                f"main image copies from another stage: {args}"
            )
            for src in sources:
                assert MAIN_COPY_ALLOWED.fullmatch(src), (
                    f"main image copies {src!r}; only workspace/ and ward"
                )
        if op in ("ENV", "ARG", "RUN"):
            text = " ".join(args)
            assert not any(m in text for m in HIDDEN_MARKERS), (
                f"main image {op} mentions hidden state: {text}"
            )
    main = _service_block(compose.read_text(encoding="utf-8"), "main")
    assert not any(m in main for m in (*HIDDEN_MARKERS, "hospital/", "/evidence")), main
    for path in [ENVIRONMENT / "ward", *sorted((ENVIRONMENT / "workspace").rglob("*"))]:
        if path.is_file():
            text = path.read_text(encoding="utf-8", errors="replace")
            assert not any(m in text for m in ("ed72_sim", "ED72_SEED", "ED72_CONFIG")), path
