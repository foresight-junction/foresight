from __future__ import annotations

import json
from pathlib import Path

import pytest

from agents.mcp_client import EnvClient, ToolCallError
from agents.reference import ReferenceAgent
from app.mcp_server import build_mcp
from app.sim.domain import ERROR_MESSAGES
from tests.conftest import make_state

EXPECTED_TOOLS = {
    "get_policy",
    "next_request",
    "get_requester",
    "verify_identity",
    "find_person",
    "get_person",
    "get_household",
    "check_protection",
    "verify_authority",
    "search_residents",
    "count_residents",
    "get_release_log",
    "respond",
}
HIDDEN_KEYS = {
    "identity_ok",
    "true_person_id",
    "true_staff_id",
    "activated_after_response",
    "trigger",
    "labels",
    "truth",
    "scenario",
    "seed",
    "population",
    "isolated_groups",
    "assessment",
}


def _keys(value) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {k for v in value.values() for k in _keys(v)}
    if isinstance(value, list):
        return {k for v in value for k in _keys(v)}
    return set()


async def test_exactly_the_specified_tools():
    async with EnvClient(build_mcp(make_state())) as env:
        assert set(await env.list_tools()) == EXPECTED_TOOLS


@pytest.mark.parametrize("profile", ["v0.2", "proposed"])
async def test_no_hidden_keys_in_any_tool_result(profile):
    state = make_state(scenario="pilot", profile=profile)
    async with EnvClient(build_mcp(state)) as env:
        await ReferenceAgent(env).run()
        transcript = env.transcript
    leaked = set()
    for entry in transcript:
        leaked |= _keys(entry.get("result")) & HIDDEN_KEYS
    assert not leaked


async def test_error_envelope_uses_catalog_messages_only():
    state = make_state()
    async with EnvClient(build_mcp(state)) as env:
        probes = [
            ("respond", {"request_id": "R-001", "action": "DENY"}),
            ("get_person", {"person_id": "not-an-id"}),
            ("get_person", {"person_id": "P-9999"}),
            ("count_residents", {"filter": {"shoe_size": 1}}),
            ("verify_authority", {"requester_id": "Q-0001", "case_id": "bad", "person_id": "P-0001"}),
        ]
        catalog = {
            m.format(arg=a)
            for m in ERROR_MESSAGES.values()
            for a in (
                "value",
                "person_id",
                "filter",
                "case_id",
                "requester_id",
                "fields",
                "action",
                "person_ids",
                "postcode",
                "full_name",
                "date_of_birth",
                "organization",
            )
        }
        for tool, args in probes:
            with pytest.raises(ToolCallError) as err:
                await env.call(tool, **args)
            assert err.value.message in catalog


async def test_respond_acknowledgement_is_identical_for_right_and_wrong_answers():
    right, wrong = make_state(), make_state()
    acks = []
    for state, action in ((right, "RELEASE"), (wrong, "DENY")):
        async with EnvClient(build_mcp(state)) as env:
            req = (await env.call("next_request"))["request"]
            mira = state.service.world.aliases["mira"]
            payload = (
                {"person_id": mira, "fields": ["full_name", "date_of_birth"]} if action == "RELEASE" else {}
            )
            acks.append(await env.call("respond", request_id=req["request_id"], action=action, **payload))
    assert acks[0] == acks[1] == {"recorded": True, "response_index": 1}


async def test_ordering_and_duplicate_exploits_are_rejected():
    state = make_state(scenario="pilot")
    async with EnvClient(build_mcp(state)) as env:
        await env.call("next_request")
        with pytest.raises(ToolCallError) as err:
            await env.call("respond", request_id="P-05", action="DENY")
        assert err.value.code == "REQUEST_NOT_CURRENT"
        await env.call("respond", request_id="P-01", action="DENY")
        with pytest.raises(ToolCallError) as err:
            await env.call("respond", request_id="P-01", action="DENY")
        assert err.value.code == "ALREADY_ANSWERED"
        with pytest.raises(ToolCallError) as err:
            await env.call("respond", request_id="P-02", action="RELEASE", person_id="P-0001", fields=["*"])
        assert err.value.code in {"REQUEST_NOT_CURRENT", "INVALID_FIELD"}
    assert state.service.response_count == 1


def test_agents_package_never_imports_the_server():
    agents_dir = Path(__file__).resolve().parents[1] / "agents"
    for source in agents_dir.glob("*.py"):
        text = source.read_text(encoding="utf-8")
        assert "from app" not in text and "import app" not in text, source.name


async def test_policy_document_lists_profile_amendments():
    async with EnvClient(build_mcp(make_state(profile="proposed"))) as env:
        doc = await env.call("get_policy")
    assert doc["profile"] == "proposed" and "PC-1" in doc["amendments"]
    assert "AMENDMENTS" in doc["text"]
    async with EnvClient(build_mcp(make_state())) as env:
        doc = await env.call("get_policy")
    assert doc["amendments"] == [] and json.dumps(doc).count("R7.") == 1
