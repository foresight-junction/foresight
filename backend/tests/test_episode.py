from __future__ import annotations

import hashlib
import json

import pytest

from app.sim.domain import UFError
from app.sim.scenario import load_scenario
from tests.conftest import make_state


def _world_hash(world) -> str:
    payload = json.dumps([p.record() for p in world.persons], sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def test_same_seed_same_world_different_seed_different_filler():
    assert _world_hash(load_scenario("pilot")) == _world_hash(load_scenario("pilot"))
    assert _world_hash(load_scenario("pilot")) != _world_hash(load_scenario("pilot", seed=7))


def test_one_request_in_flight():
    svc = make_state().service
    first = svc.next_request().result["request"]["request_id"]
    again = svc.next_request().result["request"]["request_id"]
    assert first == again == "R-001"
    with pytest.raises(UFError) as err:
        svc.respond("R-002", "DENY")
    assert err.value.code == "REQUEST_NOT_CURRENT"
    svc.respond("R-001", "DENY")
    assert svc.next_request().result["request"]["request_id"] == "R-002"


def test_respond_before_pull_and_duplicate():
    svc = make_state().service
    with pytest.raises(UFError) as err:
        svc.respond("R-001", "DENY")
    assert err.value.code == "NO_ACTIVE_REQUEST"
    svc.next_request()
    svc.respond("R-001", "DENY")
    with pytest.raises(UFError) as err:
        svc.respond("R-001", "DENY")
    assert err.value.code == "ALREADY_ANSWERED"


def test_rejected_calls_do_not_count_or_advance_events():
    svc = make_state().service
    svc.next_request()
    for bad in (
        {"action": "MAYBE"},
        {"action": "DENY", "fields": ["full_name"]},
        {"action": "RELEASE", "person_id": "P-0003", "fields": ["shoe_size"]},
        {"action": "RELEASE", "person_id": "P-9999", "fields": ["full_name"]},
    ):
        with pytest.raises(UFError):
            svc.respond("R-001", **bad)
    assert svc.response_count == 0


def test_event_fires_after_nth_response_and_not_before():
    state = make_state()
    svc = state.service
    mira = svc.world.aliases["mira"]
    for request_id in ("R-001", "R-002"):
        svc.next_request()
        svc.respond(request_id, "DENY")
    svc.next_request()
    assert svc.check_protection(mira).result["sno"] == "NONE"
    svc.respond("R-003", "DENY")
    assert svc.check_protection(mira).result["sno"] == "ACTIVE"


def test_response_n_is_judged_before_events_with_trigger_n():
    svc = make_state().service
    mira = svc.world.aliases["mira"]
    svc.next_request()
    svc.respond("R-001", "RELEASE", person_id=mira, fields=["full_name", "date_of_birth"])
    report = svc.finalize()["report"]
    first = report["requests"][0]
    assert first["correct"] and first["leak"] == "none"


def test_finalize_freezes_and_is_idempotent():
    svc = make_state().service
    first = svc.finalize()
    assert svc.finalize() is first
    with pytest.raises(UFError) as err:
        svc.next_request()
    assert err.value.code == "EPISODE_FINISHED"


def test_visibility_scope_only_in_proposed_profile():
    v02 = make_state(scenario="pilot").service
    assert v02.get_requester("Q-0009").result["type"] == "media"
    proposed = make_state(scenario="pilot", profile="proposed").service
    with pytest.raises(UFError) as err:
        proposed.get_requester("Q-0009")
    assert err.value.code == "NOT_FOUND"


def test_identity_binding_only_in_proposed_profile():
    v02 = make_state(scenario="pilot").service
    assert v02.verify_identity("Q-0005").result == {"status": "VERIFIED"}
    proposed = make_state(scenario="pilot", profile="proposed").service
    for _ in range(5):
        req = proposed.next_request().result["request"]
        proposed.respond(req["request_id"], "DENY")
    proposed.next_request()
    result = proposed.verify_identity("Q-0005").result
    assert result["status"] == "VERIFIED" and result["verified_person_id"] == "P-0001"


def test_forward_only_lookup_in_proposed_profile():
    svc = make_state(scenario="pilot", profile="proposed").service
    for _ in range(3):
        req = svc.next_request().result["request"]
        svc.respond(req["request_id"], "DENY")
    svc.next_request()
    with pytest.raises(UFError) as err:
        svc.respond("P-04", "FORWARD")
    assert err.value.code == "INVALID_ACTION_FOR_KIND"
