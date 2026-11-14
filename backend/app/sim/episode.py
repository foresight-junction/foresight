from __future__ import annotations

import re
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any

from app.sim import evaluator, policy
from app.sim.domain import (
    RELEASABLE_FIELDS,
    Action,
    Kind,
    Request,
    UFError,
)
from app.sim.evaluator import Assessment, Response
from app.sim.observe import (
    TOOL_DEPARTMENT,
    ObservationBus,
    initials,
    person_ref,
    summarize_args,
)
from app.sim.policy import SpecProfile, Truth
from app.sim.scenario import World
from app.sim.store import Store

PERSON_ID_RE = re.compile(r"^P-\d{4}$")
REQUESTER_ID_RE = re.compile(r"^Q-\d{4}$")
CASE_ID_RE = re.compile(r"^C-\d{3}$")
POSTCODE_RE = re.compile(r"^\d{5}$")
SINGLE_PERSON_KINDS = (Kind.LOOKUP, Kind.AUTHORITY, Kind.DATA_SUBJECT)


@dataclass
class ToolOutcome:
    result: dict[str, Any]
    semantic: list[dict[str, Any]] = field(default_factory=list)
    post: list[dict[str, Any]] = field(default_factory=list)


def _truth_dict(truth: Truth) -> dict[str, Any]:
    data = asdict(truth)
    data["fields"] = sorted(truth.fields)
    data["person_ids"] = sorted(truth.person_ids)
    data["population"] = sorted(truth.population)
    data["isolated_groups"] = [sorted(g) for g in truth.isolated_groups]
    data["filter"] = dict(truth.filter) if truth.filter else None
    return data


class EpisodeService:
    """One shift. Owns the state machine: one request in flight, atomic responses,
    scheduled events applied right after the Nth accepted response (spec v0.2 §2,
    timing as formalised by proposal PC-4), and the hidden truth ledger."""

    def __init__(
        self,
        world: World,
        profile: SpecProfile,
        *,
        bus: ObservationBus,
        live_reveal: bool,
        episode_id: str,
    ) -> None:
        self.world = world
        self.profile = profile
        self.bus = bus
        self.live_reveal = live_reveal
        self.episode_id = episode_id
        self.store = Store(world)
        self.requests: list[Request] = list(world.requests)
        self.events = sorted(world.events, key=lambda e: (e.after, e.event_id))
        self._lock = threading.RLock()
        self._cursor = 0
        self._current: Request | None = None
        self._announced: set[str] = set()
        self._answered: dict[str, Assessment] = {}
        self._pulled_requesters: set[str] = set()
        self._response_count = 0
        self._dynamic_sno: set[str] = set()
        self._frozen = False
        self._final: dict[str, Any] | None = None
        self._call_seq = 0
        bus.new_episode(episode_id)
        self._emit(
            "EPISODE_STARTED",
            visibility="spectator",
            department="reception",
            display={
                "scenario": world.name,
                "total_requests": len(self.requests),
                "profile": profile.name,
            },
        )

    @property
    def response_count(self) -> int:
        return self._response_count

    @property
    def frozen(self) -> bool:
        return self._frozen

    def _emit(self, event_type: str, **kwargs: Any) -> None:
        kwargs.setdefault("request_id", self._current.request_id if self._current else None)
        kwargs.setdefault("response_index", self._response_count)
        self.bus.emit(event_type, **kwargs)

    def new_call_id(self) -> str:
        with self._lock:
            self._call_seq += 1
            return f"c-{self._call_seq:05d}"

    def tool_started(self, tool: str, call_id: str, args: dict[str, Any]) -> None:
        self._emit(
            "TOOL_CALL_STARTED",
            visibility="agent_observable",
            department=TOOL_DEPARTMENT[tool],
            tool=tool,
            call_id=call_id,
            display={"args_summary": summarize_args(tool, args)},
        )

    def tool_finished(
        self,
        tool: str,
        call_id: str,
        started: float,
        outcome: ToolOutcome | None,
        error_code: str | None,
    ) -> None:
        department = TOOL_DEPARTMENT[tool]
        for spec in outcome.semantic if outcome else []:
            event_type = spec.pop("type")
            spec.setdefault("department", department)
            spec.setdefault("tool", tool)
            spec.setdefault("call_id", call_id)
            self._emit(event_type, **spec)
        self._emit(
            "TOOL_CALL_COMPLETED",
            visibility="agent_observable",
            department=department,
            tool=tool,
            call_id=call_id,
            display={
                "ok": error_code is None,
                "error_code": error_code,
                "duration_ms": round((time.perf_counter() - started) * 1000, 2),
            },
        )
        for spec in outcome.post if outcome else []:
            event_type = spec.pop("type")
            spec.setdefault("department", "decision")
            self._emit(event_type, **spec)

    def _check_open(self) -> None:
        if self._frozen:
            raise UFError("EPISODE_FINISHED")

    @staticmethod
    def _require(value: Any, pattern: re.Pattern[str], arg: str) -> str:
        if not isinstance(value, str) or not pattern.match(value):
            raise UFError("INVALID_ARGUMENT", arg)
        return value

    def _person_or_404(self, person_id: Any) -> Any:
        pid = self._require(person_id, PERSON_ID_RE, "person_id")
        person = self.store.person(pid)
        if person is None:
            raise UFError("NOT_FOUND", "person_id")
        return person

    def _visible_requester(self, requester_id: Any) -> Any:
        rid = self._require(requester_id, REQUESTER_ID_RE, "requester_id")
        requester = self.store.requester(rid)
        if requester is None:
            raise UFError("NOT_FOUND", "requester_id")
        if self.profile.visibility_scope and rid not in self._pulled_requesters:
            raise UFError("NOT_FOUND", "requester_id")
        return requester

    def get_policy(self) -> ToolOutcome:
        with self._lock:
            self._check_open()
            doc = policy.policy_document(self.profile)
            return ToolOutcome(
                doc,
                semantic=[
                    {
                        "type": "POLICY_VIEWED",
                        "visibility": "agent_observable",
                        "display": {"version": doc["version"]},
                    }
                ],
            )

    def next_request(self) -> ToolOutcome:
        with self._lock:
            self._check_open()
            if self._current is None or self._current.request_id in self._answered:
                if self._cursor >= len(self.requests):
                    self._current = None
                    return ToolOutcome({"done": True})
                self._current = self.requests[self._cursor]
                self._cursor += 1
                self._pulled_requesters.add(self._current.requester_id)
            req = self._current
            semantic = []
            if req.request_id not in self._announced:
                self._announced.add(req.request_id)
                requester = self.store.requester(req.requester_id)
                subject = req.subject or {}
                semantic.append(
                    {
                        "type": "REQUEST_RECEIVED",
                        "visibility": "agent_observable",
                        "request_id": req.request_id,
                        "display": {
                            "kind": req.kind,
                            "requester": {"id": requester.requester_id, "type": requester.type},
                            "subject_initials": (
                                initials(subject["full_name"]) if subject.get("full_name") else None
                            ),
                            "requested_fields": list(req.requested_fields),
                            "position": req.position,
                            "total": len(self.requests),
                        },
                    }
                )
            return ToolOutcome({"request": req.public()}, semantic=semantic)

    def get_requester(self, requester_id: Any) -> ToolOutcome:
        with self._lock:
            self._check_open()
            requester = self._visible_requester(requester_id)
            return ToolOutcome(
                requester.public(),
                semantic=[
                    {
                        "type": "IDENTITY_VERIFICATION",
                        "visibility": "agent_observable",
                        "display": {
                            "requester": {"id": requester.requester_id, "type": requester.type},
                            "status": "LOOKED_UP",
                        },
                    }
                ],
            )

    def verify_identity(self, requester_id: Any) -> ToolOutcome:
        with self._lock:
            self._check_open()
            requester = self._visible_requester(requester_id)
            status = "VERIFIED" if requester.identity_ok else "FAILED"
            result: dict[str, Any] = {"status": status}
            if self.profile.identity_binding and requester.identity_ok:
                if requester.true_person_id:
                    result["verified_person_id"] = requester.true_person_id
                elif requester.true_staff_id:
                    result["verified_staff_id"] = requester.true_staff_id
                else:
                    result["verified_organization"] = requester.organization
            return ToolOutcome(
                result,
                semantic=[
                    {
                        "type": "IDENTITY_VERIFICATION",
                        "visibility": "agent_observable",
                        "display": {
                            "requester": {"id": requester.requester_id, "type": requester.type},
                            "status": status,
                        },
                    }
                ],
            )

    def find_person(self, full_name: Any, date_of_birth: Any) -> ToolOutcome:
        with self._lock:
            self._check_open()
            if not isinstance(full_name, str) or not 1 <= len(full_name.strip()) <= 120:
                raise UFError("INVALID_ARGUMENT", "full_name")
            try:
                date.fromisoformat(date_of_birth)
            except (TypeError, ValueError):
                raise UFError("INVALID_ARGUMENT", "date_of_birth") from None
            pid = self.store.find_person(full_name, date_of_birth)
            person = self.store.person(pid) if pid else None
            result = {"found": True, "person_id": pid} if pid else {"found": False}
            return ToolOutcome(
                result,
                semantic=[
                    {
                        "type": "PERSON_RECORD_ACCESSED",
                        "visibility": "agent_observable",
                        "display": {"person": person_ref(person) if person else None, "found": bool(pid)},
                    }
                ],
            )

    def get_person(self, person_id: Any) -> ToolOutcome:
        with self._lock:
            self._check_open()
            person = self._person_or_404(person_id)
            return ToolOutcome(
                person.record(),
                semantic=[
                    {
                        "type": "PERSON_RECORD_ACCESSED",
                        "visibility": "agent_observable",
                        "display": {"person": person_ref(person), "found": True},
                    }
                ],
            )

    def get_household(self, person_id: Any) -> ToolOutcome:
        with self._lock:
            self._check_open()
            person = self._person_or_404(person_id)
            members = self.store.household_members(person.person_id)
            refs = [person_ref(self.store.person(m)) for m in members]
            return ToolOutcome(
                {"household_id": person.household_id, "member_ids": members},
                semantic=[
                    {
                        "type": "HOUSEHOLD_CHECK",
                        "visibility": "agent_observable",
                        "display": {
                            "person": person_ref(person),
                            "household_id": person.household_id,
                            "members": refs,
                        },
                    }
                ],
            )

    def check_protection(self, person_id: Any) -> ToolOutcome:
        with self._lock:
            self._check_open()
            person = self._person_or_404(person_id)
            sno = "ACTIVE" if self.store.sno_active(person.person_id) else "NONE"
            return ToolOutcome(
                {"person_id": person.person_id, "sno": sno},
                semantic=[
                    {
                        "type": "PROTECTION_CHECK",
                        "visibility": "agent_observable",
                        "display": {"person": person_ref(person), "sno": sno},
                    }
                ],
            )

    def verify_authority(self, requester_id: Any, case_id: Any, person_id: Any) -> ToolOutcome:
        with self._lock:
            self._check_open()
            requester = self._visible_requester(requester_id)
            cid = self._require(case_id, CASE_ID_RE, "case_id")
            pid = self._require(person_id, PERSON_ID_RE, "person_id")
            ok, reason = policy.authority_check(self.store, requester.claimed_staff_id, cid, pid)
            result = {"status": "VALID"} if ok else {"status": "INVALID", "reason": reason}
            return ToolOutcome(
                result,
                semantic=[
                    {
                        "type": "AUTHORITY_CHECK",
                        "visibility": "agent_observable",
                        "display": {"case_id": cid, "status": result["status"], "reason": reason},
                    }
                ],
            )

    def search_residents(self, postcode: Any) -> ToolOutcome:
        with self._lock:
            self._check_open()
            pc = self._require(postcode, POSTCODE_RE, "postcode")
            ids = self.store.residents(pc)
            return ToolOutcome(
                {"postcode": pc, "person_ids": ids},
                semantic=[
                    {
                        "type": "RESIDENT_SEARCH",
                        "visibility": "agent_observable",
                        "display": {"postcode": pc, "count": len(ids)},
                    }
                ],
            )

    def count_residents(self, filter_: Any) -> ToolOutcome:
        with self._lock:
            self._check_open()
            canonical = policy.canonical_filter(filter_, self.store, self.profile)
            count = len(self.store.population(canonical))
            return ToolOutcome(
                {"filter": dict(canonical), "count": count},
                semantic=[
                    {
                        "type": "STATISTICS_QUERY",
                        "visibility": "agent_observable",
                        "display": {"filter": dict(canonical), "count": count},
                    }
                ],
            )

    def get_release_log(self, organization: Any = None) -> ToolOutcome:
        with self._lock:
            self._check_open()
            if organization is not None and (not isinstance(organization, str) or len(organization) > 120):
                raise UFError("INVALID_ARGUMENT", "organization")
            entries = self.store.release_entries(organization)
            return ToolOutcome(
                {"entries": entries},
                semantic=[
                    {
                        "type": "RELEASE_LOG_VIEWED",
                        "visibility": "agent_observable",
                        "display": {"entries": len(entries)},
                    }
                ],
            )

    def _validate_response(
        self,
        req: Request,
        action: Any,
        person_id: Any,
        fields: Any,
        person_ids: Any,
    ) -> Response:
        if action not in (Action.RELEASE, Action.DENY, Action.FORWARD):
            raise UFError("INVALID_ARGUMENT", "action")
        if action == Action.FORWARD and self.profile.forward_only_lookup and req.kind != Kind.LOOKUP:
            raise UFError("INVALID_ACTION_FOR_KIND")
        if action in (Action.DENY, Action.FORWARD):
            for name, value in (("person_id", person_id), ("fields", fields), ("person_ids", person_ids)):
                if value not in (None, [], ""):
                    raise UFError("INVALID_ARGUMENT", name)
            return Response(action=str(action))

        def checked_fields() -> tuple[str, ...]:
            if not isinstance(fields, list) or not fields:
                raise UFError("INVALID_ARGUMENT", "fields")
            if any(f not in RELEASABLE_FIELDS for f in fields):
                raise UFError("INVALID_FIELD", "fields")
            return tuple(sorted(set(fields)))

        if req.kind in SINGLE_PERSON_KINDS:
            if person_ids not in (None, []):
                raise UFError("INVALID_ARGUMENT", "person_ids")
            person = self._person_or_404(person_id)
            return Response(Action.RELEASE, person_id=person.person_id, fields=checked_fields())
        if req.kind == Kind.BULK:
            if person_id is not None:
                raise UFError("INVALID_ARGUMENT", "person_id")
            if not isinstance(person_ids, list):
                raise UFError("INVALID_ARGUMENT", "person_ids")
            if not person_ids and self.profile.bulk_empty_deny:
                raise UFError("INVALID_ARGUMENT", "person_ids")
            ids = set()
            for pid in person_ids:
                ids.add(self._person_or_404(pid).person_id)
            return Response(Action.RELEASE, fields=checked_fields(), person_ids=tuple(sorted(ids)))
        for name, value in (("person_id", person_id), ("fields", fields), ("person_ids", person_ids)):
            if value not in (None, []):
                raise UFError("INVALID_ARGUMENT", name)
        return Response(Action.RELEASE)

    def _truth_for(self, req: Request) -> Truth:
        requester = self.store.requester(req.requester_id)
        return policy.truth(self.store, self.profile, req, requester, self.store.stat_history())

    def respond(
        self,
        request_id: Any,
        action: Any,
        person_id: Any = None,
        fields: Any = None,
        person_ids: Any = None,
    ) -> ToolOutcome:
        with self._lock:
            self._check_open()
            if self._current is None:
                raise UFError("NO_ACTIVE_REQUEST")
            if request_id in self._answered:
                raise UFError("ALREADY_ANSWERED")
            if request_id != self._current.request_id:
                raise UFError("REQUEST_NOT_CURRENT")
            req = self._current
            response = self._validate_response(req, action, person_id, fields, person_ids)
            requester = self.store.requester(req.requester_id)
            truth = self._truth_for(req)
            index = self._response_count + 1
            assessment = evaluator.assess(
                self.store, req, requester, truth, response, index, self._dynamic_sno
            )
            applied = [e for e in self.events if e.after == index]
            with self.store.transaction():
                self.store.insert_response(
                    index,
                    req.request_id,
                    response.action,
                    response.person_id,
                    list(response.fields),
                    list(response.person_ids),
                )
                if response.action == Action.RELEASE:
                    self.store.insert_release(
                        index,
                        req.request_id,
                        requester.organization,
                        req.kind,
                        list(response.person_ids) or ([response.person_id] if response.person_id else []),
                        list(response.fields),
                        truth.filter if req.kind == Kind.STATISTICS else None,
                        truth.count if req.kind == Kind.STATISTICS else None,
                    )
                self.store.insert_ledger(
                    index,
                    req.request_id,
                    _truth_dict(truth),
                    assessment.to_dict(),
                    sorted(truth.population),
                )
                for event in applied:
                    self._apply_event(event)
            self._response_count = index
            self._answered[req.request_id] = assessment

            semantic: list[dict[str, Any]] = [
                {
                    "type": "DECISION_SUBMITTED",
                    "visibility": "agent_observable",
                    "request_id": req.request_id,
                    "response_index": index,
                    "display": {
                        "action": response.action,
                        "fields": list(response.fields),
                        "person_count": len(response.person_ids) or (1 if response.person_id else 0),
                        "response_index": index,
                    },
                }
            ]
            for event in applied:
                semantic.append(self._state_change_event(event, req.request_id, index))
            post: list[dict[str, Any]] = []
            if self.live_reveal:
                post.extend(self._reveal_events(req.request_id, index, assessment))
            return ToolOutcome({"recorded": True, "response_index": index}, semantic, post)

    def _apply_event(self, event: Any) -> None:
        if event.type == "sno_activated":
            self.store.activate_sno(event.person_id)
            self._dynamic_sno.add(event.person_id)
        elif event.type == "case_closed":
            self.store.close_case(event.case_id)
        elif event.type == "officer_reassigned":
            self.store.remove_officer(event.case_id, event.staff_id)
        else:
            raise ValueError(f"unknown event type {event.type}")

    def _state_change_event(self, event: Any, request_id: str, index: int) -> dict[str, Any]:
        person = self.store.person(event.person_id) if event.person_id else None
        department = "protection" if event.type == "sno_activated" else "authority"
        return {
            "type": "STATE_CHANGED",
            "visibility": "spectator",
            "request_id": request_id,
            "response_index": index,
            "department": department,
            "tool": None,
            "call_id": None,
            "display": {
                "change": event.type,
                "person": person_ref(person) if person else None,
                "case_id": event.case_id,
            },
        }

    def _all_assessments(self) -> list[Assessment]:
        rows: list[Assessment] = []
        for req in self.requests:
            if req.request_id in self._answered:
                rows.append(self._answered[req.request_id])
            else:
                requester = self.store.requester(req.requester_id)
                rows.append(
                    evaluator.assess(
                        self.store,
                        req,
                        requester,
                        self._truth_for(req),
                        None,
                        None,
                        self._dynamic_sno,
                    )
                )
        return rows

    def _reveal_events(self, request_id: str, index: int, assessment: Assessment) -> list[dict[str, Any]]:
        totals = evaluator.score(self._all_assessments(), len(self.requests))
        events: list[dict[str, Any]] = [
            {
                "type": "REWARD_UPDATED",
                "visibility": "evaluator_reveal",
                "request_id": request_id,
                "response_index": index,
                "tool": None,
                "call_id": None,
                "display": {
                    "score": totals["reward"],
                    "service": totals["service"],
                    "completion": totals["completion"],
                    "critical_leaks": totals["critical_leaks"],
                    "minor_leaks": totals["minor_leaks"],
                    "last": {
                        "request_id": request_id,
                        "correct": assessment.correct,
                        "leak": assessment.leak,
                    },
                },
            }
        ]
        if assessment.leak != "none":
            persons = [self.store.person(p) for p in assessment.leak_persons]
            events.append(
                {
                    "type": "PRIVACY_LEAK_DETECTED",
                    "visibility": "evaluator_reveal",
                    "request_id": request_id,
                    "response_index": index,
                    "tool": None,
                    "call_id": None,
                    "display": {
                        "severity": assessment.leak,
                        "persons": [person_ref(p) for p in persons if p],
                        "fields": list(assessment.leak_fields),
                    },
                }
            )
        return events

    def finalize(self) -> dict[str, Any]:
        with self._lock:
            if self._final is not None:
                return self._final
            self._frozen = True
            rows = self._all_assessments()
            totals = evaluator.score(rows, len(self.requests))
            report = {
                "episode_id": self.episode_id,
                "scenario": self.world.name,
                "seed": self.world.seed,
                "profile": self.profile.name,
                "requests": [r.to_dict() for r in rows],
                **totals,
            }
            self._final = {"reward": {k: v for k, v in totals.items() if k != "per_kind"}, "report": report}
            self._emit(
                "EPISODE_FINISHED",
                visibility="evaluator_reveal",
                department="decision",
                request_id=None,
                display={
                    "score": totals["reward"],
                    "service": totals["service"],
                    "completion": totals["completion"],
                    "critical_leaks": totals["critical_leaks"],
                    "minor_leaks": totals["minor_leaks"],
                    "answered": totals["answered"],
                    "total": totals["total"],
                    "requests": [
                        {
                            "request_id": r.request_id,
                            "kind": r.kind,
                            "agent_action": r.agent_action,
                            "correct": r.correct,
                            "leak": r.leak,
                        }
                        for r in rows
                    ],
                },
            )
            return self._final
