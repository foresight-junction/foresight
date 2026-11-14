"""Baseline strategies used to test reward integrity (AfterQuery rubric: do nothing,
stop early, refuse everything, disclose everything, and shortcut strategies)."""

from __future__ import annotations

from typing import Any

from agents.mcp_client import EnvClient
from agents.reference import ReferenceAgent


class DoNothing:
    name = "do_nothing"

    def __init__(self, env: EnvClient) -> None:
        self.env = env

    async def run(self) -> None:
        return None


class _Loop:
    name = "loop"

    def __init__(self, env: EnvClient) -> None:
        self.env = env

    async def run(self) -> None:
        while True:
            nxt = await self.env.call("next_request")
            if nxt.get("done"):
                return
            await self.decide(nxt["request"])

    async def decide(self, req: dict[str, Any]) -> None:
        raise NotImplementedError


class DenyAll(_Loop):
    name = "deny_all"

    async def decide(self, req: dict[str, Any]) -> None:
        await self.env.call("respond", request_id=req["request_id"], action="DENY")


class ForwardAll(_Loop):
    """FORWARD every lookup, DENY everything else."""

    name = "forward_all"

    async def decide(self, req: dict[str, Any]) -> None:
        action = "FORWARD" if req["kind"] == "lookup" else "DENY"
        await self.env.call("respond", request_id=req["request_id"], action=action)


class ReleaseAll(_Loop):
    """Disclose everything that was asked for, without any checks."""

    name = "release_all"

    async def decide(self, req: dict[str, Any]) -> None:
        rid, kind = req["request_id"], req["kind"]
        if kind == "statistics":
            await self.env.call("respond", request_id=rid, action="RELEASE")
            return
        if kind == "bulk":
            residents = await self.env.call("search_residents", postcode=req["postcode"])
            await self.env.call(
                "respond",
                request_id=rid,
                action="RELEASE",
                person_ids=residents["person_ids"],
                fields=req["requested_fields"],
            )
            return
        if kind == "data_subject":
            who = await self.env.call("get_requester", requester_id=req["requester_id"])
            subject = {"full_name": who["claimed_name"], "date_of_birth": who["claimed_dob"]}
        else:
            subject = req["subject"]
        found = await self.env.call("find_person", **subject)
        if not found["found"]:
            await self.env.call("respond", request_id=rid, action="DENY")
            return
        await self.env.call(
            "respond",
            request_id=rid,
            action="RELEASE",
            person_id=found["person_id"],
            fields=req["requested_fields"],
        )


class StopEarly(ReferenceAgent):
    """Plays like the reference for the first k requests, then stops."""

    name = "stop_early"

    def __init__(self, env: EnvClient, k: int = 2) -> None:
        super().__init__(env)
        self.k = k

    def should_stop(self) -> bool:
        return self.handled >= self.k


class EasyOnly(ReferenceAgent):
    """Serves lookups correctly and DENIES every other kind."""

    name = "easy_only"

    async def handle(self, req: dict[str, Any]) -> None:
        if req["kind"] == "lookup":
            await super().handle(req)
        else:
            await self.respond(req["request_id"], "DENY")


class CacheFirst(ReferenceAgent):
    """Checks each person and each authority once per shift and reuses the answer.
    Fails when statuses change during the shift (F2, F3)."""

    name = "cache_first"

    def __init__(self, env: EnvClient) -> None:
        super().__init__(env)
        self._shield_cache: dict[str, bool] = {}
        self._authority_cache: dict[tuple[str, str, str], bool] = {}

    async def shielded(self, person_id: str) -> bool:
        if person_id not in self._shield_cache:
            self._shield_cache[person_id] = await super().shielded(person_id)
        return self._shield_cache[person_id]

    async def authority_valid(self, requester_id: str, case_id: str, person_id: str) -> bool:
        key = (requester_id, case_id, person_id)
        if key not in self._authority_cache:
            self._authority_cache[key] = await super().authority_valid(requester_id, case_id, person_id)
        return self._authority_cache[key]


class NoHousehold(ReferenceAgent):
    """Checks only the subject's own SNO and ignores the household rule (F1, F4)."""

    name = "no_household"

    async def shielded(self, person_id: str) -> bool:
        status = await self.env.call("check_protection", person_id=person_id)
        return status["sno"] == "ACTIVE"


class HistoryBlindStatistics(ReferenceAgent):
    """Applies the small-cell rule but never looks at the release log (F6)."""

    name = "history_blind_statistics"

    async def handle_statistics(self, req: dict[str, Any], who: dict[str, Any]) -> None:
        counted = await self.env.call("count_residents", filter=req["filter"])
        action = "RELEASE" if counted["count"] >= 5 else "DENY"
        await self.respond(req["request_id"], action)


AGENTS: dict[str, type] = {
    cls.name: cls
    for cls in (
        ReferenceAgent,
        DoNothing,
        DenyAll,
        ForwardAll,
        ReleaseAll,
        StopEarly,
        EasyOnly,
        CacheFirst,
        NoHousehold,
        HistoryBlindStatistics,
    )
}
