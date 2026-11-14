"""The live player: an MCP client of the hospital tool server, like any external agent would be.

It calls `rules` once, `observe`, then `step` once per tick until the episode is finished. The
decider (an LLM or a scripted policy) only ever sees what the tools return.
"""

import asyncio
import json
import sys
import time
from typing import Any, Protocol

from llm import ModelFatal
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from recorder import LiveRecorder


class Decider(Protocol):
    def start(self, handbook: str) -> None: ...

    def decide(
        self, obs: dict, last_actions: list[dict], last_results: list[dict]
    ) -> tuple[list[dict], str | None]: ...


class ScriptedDecider:
    """ReferencePolicy or ReactiveProxy: no thought, just the policy's actions."""

    def __init__(self, act: Any) -> None:
        self._act = act

    def start(self, handbook: str) -> None:
        return None

    def decide(
        self, obs: dict, last_actions: list[dict], last_results: list[dict]
    ) -> tuple[list[dict], str | None]:
        return self._act(obs) or [], None


async def _call(session: ClientSession, tool: str, args: dict) -> dict:
    result = await session.call_tool(tool, args)
    if result.is_error:
        raise RuntimeError(f"{tool} failed: {result.content[0].text if result.content else 'no detail'}")
    return result.structured_content or json.loads(result.content[0].text)


def _log(tick: int, actions: list[dict], results: list[dict], thought: str | None) -> None:
    rejected = sum(not r.get("ok") for r in results)
    line = f"tick {tick:3d}: {len(actions)} actions, {rejected} rejected"
    line = f"{line}  | {thought}" if thought else line
    # The model writes any Unicode ("≤"); a Windows console (cp1252) can't print all of it, and a
    # console line must never stop the episode, so unprintable characters become "?".
    enc = getattr(sys.stdout, "encoding", None) or "utf-8"
    print(line.encode(enc, errors="replace").decode(enc), flush=True)


async def play(url: str, recorder: LiveRecorder, decider: Decider, min_tick_seconds: float) -> None:
    failed: str | None = None
    async with streamable_http_client(url) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        rules = await _call(session, "rules", {})
        if "error" in rules:
            raise RuntimeError(f"rules: {rules['error']}")
        decider.start(rules["text"])
        obs = await _call(session, "observe", {})
        actions: list[dict] = []
        results: list[dict] = []
        while "error" not in obs and not obs["finished"]:
            started = time.monotonic()
            if failed is None:
                recorder.set_state("thinking")
                try:
                    # The decider blocks (HTTP, policy code); off the loop, the MCP session stays served.
                    actions, thought = await asyncio.to_thread(decider.decide, obs, actions, results)
                except ModelFatal as err:
                    failed = str(err)
                    recorder.set_state("error", failed)
            if failed is not None:
                actions, thought = [], f"(no decision: model unavailable, waiting out the episode: {failed})"
            await asyncio.sleep(max(0.0, min_tick_seconds - (time.monotonic() - started)))
            if failed is None:
                recorder.set_state("acting")
            recorder.set_thought(thought)
            out = await _call(session, "step", {"actions": actions})
            if "error" in out:
                # call_cap_reached or episode_over: the recorder runs out the rest.
                print(f"step refused: {out['error']}", flush=True)
                break
            results = out["results"]
            _log(obs["tick"], actions, results, thought)
            obs = out["observation"]
    recorder.finish()
