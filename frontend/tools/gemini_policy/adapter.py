"""Run Gemini's own controller (run_ed.py, verbatim) against an in-process sim instead of the MCP server.

Only the transport changes. run_ed.py opens `streamable_http_client(url)` and a `ClientSession`, then
calls the `observe` and `step` tools. Here those two names point at an in-process session that answers
the same three tools the way ed72/environment/hospital/server.py does (`rules` returns the handbook,
`step` applies at most 50 actions and refuses the rest as `bad_action`). The controller's decision code
and its episode loop run unchanged.
"""

import asyncio
import contextlib
import importlib.util
import io
import json
import sys
import types
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any, Protocol, Self

SCRIPT = Path(__file__).with_name("run_ed.py")
HANDBOOK = Path(__file__).resolve().parents[3] / "ed72" / "environment" / "workspace" / "HANDBOOK.md"
MAX_ACTIONS = 50  # server.py MAX_ACTIONS


class Sim(Protocol):
    def observe(self) -> dict: ...

    def step(self, actions: list[dict]) -> dict: ...


class InProcessSession:
    """Stands in for mcp.ClientSession: same `initialize` and `call_tool`, answered by the sim."""

    def __init__(self, sim: Sim) -> None:
        self._sim = sim

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None

    async def initialize(self) -> None:
        return None

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> types.SimpleNamespace:
        if name == "rules":
            result = {"text": HANDBOOK.read_text(encoding="utf-8")}
        elif name == "observe":
            result = self._sim.observe()
        elif name == "step":
            result = self._step(list(arguments["actions"]))
        else:
            raise ValueError(f"unknown tool {name!r}")
        # Shaped like mcp's CallToolResult, which is all run_ed.py reads.
        return types.SimpleNamespace(
            structured_content=result, content=[types.SimpleNamespace(text=json.dumps(result))]
        )

    def _step(self, actions: list[dict]) -> dict:
        out = self._sim.step(actions[:MAX_ACTIONS])
        if "error" in out:
            return out
        extra = [{"index": i, "ok": False, "reason": "bad_action"} for i in range(MAX_ACTIONS, len(actions))]
        return {"results": out["results"] + extra, "observation": out["observation"]}


def _load_controller_module(sim: Sim) -> types.ModuleType:
    # run_ed.py imports mcp at the top; these stubs satisfy that import without the package.
    stubs = {
        "mcp": types.ModuleType("mcp"),
        "mcp.client": types.ModuleType("mcp.client"),
        "mcp.client.streamable_http": types.ModuleType("mcp.client.streamable_http"),
    }

    @contextlib.asynccontextmanager
    async def streamable_http_client(url: str) -> AsyncIterator[tuple[Sim, None]]:
        yield sim, None

    stubs["mcp"].ClientSession = lambda read, write: InProcessSession(read)  # type: ignore[attr-defined]
    stubs["mcp.client.streamable_http"].streamable_http_client = streamable_http_client  # type: ignore[attr-defined]
    saved = {name: sys.modules.get(name) for name in stubs}
    sys.modules.update(stubs)
    try:
        spec = importlib.util.spec_from_file_location("gemini_run_ed", SCRIPT)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        for name, old in saved.items():
            if old is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = old
    return module


def run_gemini(sim: Sim) -> str:
    """Play a whole episode with Gemini's controller. Returns what the script printed (stdout + stderr)."""
    module = _load_controller_module(sim)
    log = io.StringIO()
    with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
        asyncio.run(module.EDController().run())
    return log.getvalue()
