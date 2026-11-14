from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from app.sim.domain import Person

TOOL_DEPARTMENT: dict[str, str] = {
    "next_request": "reception",
    "get_policy": "reception",
    "get_requester": "identity",
    "verify_identity": "identity",
    "find_person": "registry",
    "get_person": "registry",
    "search_residents": "registry",
    "get_household": "protection",
    "check_protection": "protection",
    "verify_authority": "authority",
    "count_residents": "statistics",
    "get_release_log": "statistics",
    "respond": "decision",
}

SAFE_ARG_KEYS = frozenset(
    {
        "request_id",
        "requester_id",
        "person_id",
        "case_id",
        "postcode",
        "action",
        "fields",
        "organization",
        "filter",
    }
)


def initials(full_name: str | None) -> str:
    if not full_name:
        return "?"
    return "".join(f"{part[0].upper()}." for part in full_name.split() if part)


def person_ref(person: Person) -> dict[str, str]:
    return {"id": person.person_id, "initials": initials(person.full_name)}


def summarize_args(tool: str, args: dict[str, Any]) -> dict[str, Any]:
    summary = {k: v for k, v in args.items() if k in SAFE_ARG_KEYS and v is not None}
    if tool == "find_person":
        summary["name_initials"] = initials(args.get("full_name"))
    if args.get("person_ids") is not None:
        summary["person_count"] = len(args["person_ids"])
    return summary


class ObservationBus:
    """One-way spectator stream. Only the server writes to it; nothing reads it back
    into state, truth or reward. seq keeps increasing across episodes so clients can
    de-duplicate; a new EPISODE_STARTED tells them to reset."""

    def __init__(self, enabled: bool) -> None:
        self.enabled = enabled
        self.episode_id = ""
        self.history: list[dict[str, Any]] = []
        self._subscribers: set[asyncio.Queue[dict[str, Any]]] = set()
        self._seq = 0

    def new_episode(self, episode_id: str) -> None:
        self.episode_id = episode_id
        self.history = []

    def emit(
        self,
        event_type: str,
        *,
        visibility: str,
        request_id: str | None = None,
        response_index: int = 0,
        department: str | None = None,
        tool: str | None = None,
        call_id: str | None = None,
        display: dict[str, Any] | None = None,
    ) -> None:
        if not self.enabled:
            return
        self._seq += 1
        event = {
            "v": 1,
            "seq": self._seq,
            "ts": datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "episode_id": self.episode_id,
            "type": event_type,
            "visibility": visibility,
            "request_id": request_id,
            "response_index": response_index,
            "department": department,
            "tool": tool,
            "call_id": call_id,
            "display": display or {},
        }
        self.history.append(event)
        for queue in list(self._subscribers):
            queue.put_nowait(event)

    def since(self, after_seq: int) -> list[dict[str, Any]]:
        return [e for e in self.history if e["seq"] > after_seq]

    def subscribe(self) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[dict[str, Any]]) -> None:
        self._subscribers.discard(queue)
