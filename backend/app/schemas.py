from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

EventType = Literal[
    "EPISODE_STARTED",
    "REQUEST_RECEIVED",
    "TOOL_CALL_STARTED",
    "TOOL_CALL_COMPLETED",
    "IDENTITY_VERIFICATION",
    "PERSON_RECORD_ACCESSED",
    "RESIDENT_SEARCH",
    "HOUSEHOLD_CHECK",
    "PROTECTION_CHECK",
    "AUTHORITY_CHECK",
    "STATISTICS_QUERY",
    "RELEASE_LOG_VIEWED",
    "POLICY_VIEWED",
    "DECISION_SUBMITTED",
    "STATE_CHANGED",
    "REWARD_UPDATED",
    "PRIVACY_LEAK_DETECTED",
    "EPISODE_FINISHED",
]

Department = Literal["reception", "identity", "registry", "protection", "authority", "statistics", "decision"]


class ObservationEvent(BaseModel):
    """Mirror of docs/unfindable/EVENT_SCHEMA.md §3, used to validate emitted events."""

    v: Literal[1]
    seq: int = Field(ge=1)
    ts: str
    episode_id: str
    type: EventType
    visibility: Literal["agent_observable", "spectator", "evaluator_reveal"]
    request_id: str | None
    response_index: int = Field(ge=0)
    department: Department | None
    tool: str | None
    call_id: str | None
    display: dict[str, Any]


class ResetRequest(BaseModel):
    scenario: str | None = None
    seed: int | None = None
    profile: str | None = None
