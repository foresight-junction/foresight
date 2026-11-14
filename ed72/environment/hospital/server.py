"""Hospital tool server: the agent's only way into the sim (docs/CONTRACTS.md, Tools v1).

Three MCP tools over streamable HTTP at /mcp, plus GET /health. The `ward` CLI in
the main container calls the same tools. There is deliberately no reset, seed,
ground-truth or finalise endpoint: collect.py finishes the episode from the log.
"""

import json
import os
import threading
from pathlib import Path
from typing import Any, Protocol

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

CALL_CAP = 500
MAX_ACTIONS = 50
LOG_PATH = Path("/var/lib/ed72/events.jsonl")
HANDBOOK_PATH = Path(__file__).with_name("HANDBOOK.md")


class Sim(Protocol):
    events: list[dict]

    def observe(self) -> dict: ...

    def step(self, actions: list[dict]) -> dict: ...


class ToolHost:
    """Counts calls, enforces the cap and episode end, and writes the event log."""

    def __init__(self, sim: Sim, handbook: str, log_path: Path) -> None:
        self.sim = sim
        self.handbook = handbook
        self.log_path = log_path
        self.calls = 0
        self.seq = 0
        self.sim_events_logged = 0
        self.lock = threading.Lock()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("")
        self._flush_sim_events()

    def call(self, tool: str, args: dict[str, Any]) -> dict:
        with self.lock:
            self.calls += 1
            tick = self.sim.observe()["tick"]
            if self.calls > CALL_CAP:
                result = {"error": "call_cap_reached"}
            elif tool == "rules":
                result = {"text": self.handbook}
            elif tool == "observe":
                result = self.sim.observe()
            else:
                result = self._step(args["actions"])
            self._write(
                {"t": tick, "src": "agent", "tool": tool, "args": args, "result": _log_result(result)}
            )
            self._flush_sim_events()
            return result

    def _step(self, actions: list[dict]) -> dict:
        if self.sim.observe()["finished"]:
            return {"error": "episode_over"}
        out = self.sim.step(actions[:MAX_ACTIONS])
        extra = [{"index": i, "ok": False, "reason": "bad_action"} for i in range(MAX_ACTIONS, len(actions))]
        return {"results": out["results"] + extra, "observation": out["observation"]}

    def _flush_sim_events(self) -> None:
        for event in self.sim.events[self.sim_events_logged :]:
            self._write(event)
        self.sim_events_logged = len(self.sim.events)

    def _write(self, line: dict) -> None:
        self.seq += 1
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"seq": self.seq, **line}, separators=(",", ":")) + "\n")


def _log_result(result: dict) -> dict:
    # The observation is a pure function of the log, so only the decision-relevant part is stored.
    if "results" in result:
        return {"results": result["results"]}
    if "error" in result:
        return result
    return {"ok": True}


def build_server(host: ToolHost) -> FastMCP:
    mcp = FastMCP(
        "hospital", instructions="Run the ED for 144 ticks. Call `rules` first, then `step` once per tick."
    )

    @mcp.tool
    def rules() -> dict:
        """The department rules (HANDBOOK.md): zones, hazards, staff, costs, events and the score formula."""
        return host.call("rules", {})

    @mcp.tool
    def observe() -> dict:
        """The current observation. Uses no sim time, but counts toward the 500-call cap."""
        return host.call("observe", {})

    @mcp.tool
    def step(actions: list[dict]) -> dict:
        """Apply up to 50 actions in order, then advance one tick (30 min).

        Actions: {"type":"admit","patient":"P042","zone":"resus|acute|fast_track"},
        {"type":"assign","staff":"D3","to":"<zone>|rest"}, {"type":"agency","role":"doctor|nurse"},
        {"type":"repair"}, {"type":"divert"}. Pass [] to wait a tick. Returns per-action results
        and the next observation.
        """
        return host.call("step", {"actions": actions})

    @mcp.custom_route("/health", methods=["GET"])
    async def health(request: Request) -> JSONResponse:
        return JSONResponse({"ok": True})

    return mcp


def _make_sim(seed: int) -> Sim:
    if os.environ.get("USE_MOCKS") == "1":
        from mock_sim import MockSimulation  # MOCK: until #4 lands

        return MockSimulation(seed)
    raise SystemExit("The real ed72_sim is not wired yet (waiting on #4). Run with USE_MOCKS=1.")


def main() -> None:
    sim = _make_sim(int(os.environ["ED72_SEED"]))
    host = ToolHost(sim, HANDBOOK_PATH.read_text(encoding="utf-8"), LOG_PATH)
    build_server(host).run(transport="streamable-http", host="0.0.0.0", port=8000, path="/mcp")


if __name__ == "__main__":
    main()
