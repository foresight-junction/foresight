"""MOCK: one-tick MCP fixture for the Harbor transport smoke test."""

import json
from pathlib import Path
from typing import Any

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

mcp = FastMCP("hospital")
state_path = Path("/app/smoke-state.json")
calls: list[str] = []
tick = 0
state_path.write_text("[]", encoding="utf-8")


def record(tool: str) -> None:
    calls.append(tool)
    state_path.write_text(json.dumps(calls), encoding="utf-8")


def observation() -> dict[str, Any]:
    return {
        "tick": tick,
        "clock": "Day 1 08:30" if tick else "Day 1 08:00",
        "ticks_left": 144 - tick,
        "finished": False,
        "budget": {"spent": 0, "budget": 12000, "hard_limit": 24000},
        "waiting": [],
        "beds": [],
        "staff": [],
        "ct": {"working": True, "down_ticks_left": 0},
        "warnings": [],
        "diversion": {"active": False, "ticks_left": 0},
        "totals": {"discharged": 0, "deaths": 0, "left": 0, "diverted": 0, "faints": 0},
        "last_rejected": [],
    }


@mcp.tool
def rules() -> dict[str, str]:
    record("rules")
    return {"text": "For this smoke test, observe the hospital and submit one empty batch."}


@mcp.tool
def observe() -> dict[str, Any]:
    record("observe")
    return observation()


@mcp.tool
def step(actions: list[dict[str, Any]]) -> dict[str, Any]:
    global tick
    if actions or tick:
        raise ValueError("The smoke test accepts one empty action batch.")
    tick += 1
    record("step")
    return {"results": [], "observation": observation()}


@mcp.custom_route("/health", methods=["GET"])
async def health(request: Request) -> JSONResponse:
    return JSONResponse({"ok": True})


if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8000, path="/mcp")
