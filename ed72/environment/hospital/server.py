"""Hospital tool server: the agent's only way into the sim (docs/CONTRACTS.md, Tools v1).

Three MCP tools over streamable HTTP at /mcp, plus GET /health. The `ward` CLI in
the main container calls the same tools. There is deliberately no reset, seed,
ground-truth or finalise endpoint: collect.py finishes the episode from the log.
"""

import os
import threading
from pathlib import Path
from typing import Any, Protocol

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

CALL_CAP = 500
MAX_ACTIONS = 50
HANDBOOK_PATH = Path(__file__).with_name("HANDBOOK.md")


class Sim(Protocol):
    """The ed72_sim.engine.Simulation surface the server uses. The sim owns the event log."""

    def observe(self) -> dict: ...

    def step(self, actions: list[dict]) -> dict: ...

    def record_call(self, tool: str, args: dict, result: dict) -> None: ...


class ToolHost:
    """Counts calls and enforces the cap; logs every call the sim does not log itself."""

    def __init__(self, sim: Sim, handbook: str) -> None:
        self.sim = sim
        self.handbook = handbook
        self.calls = 0
        self.lock = threading.Lock()

    def call(self, tool: str, args: dict[str, Any]) -> dict:
        with self.lock:
            self.calls += 1
            if self.calls > CALL_CAP:
                result = {"error": "call_cap_reached"}
            elif tool == "rules":
                result = {"text": self.handbook}
            elif tool == "observe":
                result = self.sim.observe()
            else:
                result = self._step(args["actions"])
                if "error" not in result:
                    return result
            # The observation follows from the log, so only errors are worth storing.
            self.sim.record_call(tool, args, result if "error" in result else {"ok": True})
            return result

    def _step(self, actions: list[dict]) -> dict:
        # Only what the sim applied reaches its log, so collect.py's replay stays exact.
        out = self.sim.step(actions[:MAX_ACTIONS])
        if "error" in out:
            return out
        extra = [{"index": i, "ok": False, "reason": "bad_action"} for i in range(MAX_ACTIONS, len(actions))]
        return {"results": out["results"] + extra, "observation": out["observation"]}


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
    def step(actions: list[Any]) -> dict:
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


def _fresh_log(path: str) -> Path:
    log_path = Path(path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    # A restarted server restarts the sim at tick 0, so the old log would no longer replay.
    log_path.write_text("", encoding="utf-8")
    return log_path


def _make_sim(seed: int) -> Sim:
    if os.environ.get("USE_MOCKS") == "1":
        from mock_sim import EVENT_LOG_PATH, MockSimulation  # MOCK: until #46/#48 land on main

        return MockSimulation(seed, _fresh_log(EVENT_LOG_PATH))
    from ed72_sim.constants import EVENT_LOG_PATH
    from ed72_sim.engine import Simulation
    from ed72_sim.world import generate_world

    return Simulation(generate_world(seed), _fresh_log(EVENT_LOG_PATH))


def main() -> None:
    sim = _make_sim(int(os.environ["ED72_SEED"]))
    host = ToolHost(sim, HANDBOOK_PATH.read_text(encoding="utf-8"))
    build_server(host).run(transport="streamable-http", host="0.0.0.0", port=8000, path="/mcp")


if __name__ == "__main__":
    main()
