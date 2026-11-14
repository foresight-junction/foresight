"""MCP client used by the reference agent and baselines. Agents talk to the environment
only through MCP tools; this package must never import the server (`app`)."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from fastmcp import Client


class ToolCallError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


class EnvClient:
    def __init__(self, target: Any, pace: float = 0.0) -> None:
        self._client = Client(target)
        self._pace = pace
        self.calls = 0
        self.transcript: list[dict[str, Any]] = []

    async def __aenter__(self) -> EnvClient:
        await self._client.__aenter__()
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self._client.__aexit__(*exc)

    async def list_tools(self) -> list[str]:
        return [t.name for t in await self._client.list_tools()]

    async def call(self, tool: str, **args: Any) -> dict[str, Any]:
        args = {k: v for k, v in args.items() if v is not None}
        result = await self._client.call_tool(tool, args, raise_on_error=False)
        self.calls += 1
        if self._pace:
            await asyncio.sleep(self._pace)
        if result.is_error:
            text = result.content[0].text if result.content else "{}"
            try:
                error = json.loads(text)["error"]
            except (ValueError, KeyError, TypeError):
                error = {"code": "UNKNOWN", "message": text}
            self.transcript.append({"tool": tool, "args": args, "error": error})
            raise ToolCallError(error["code"], error["message"])
        data = result.structured_content
        if data is None:
            data = json.loads(result.content[0].text)
        self.transcript.append({"tool": tool, "args": args, "result": data})
        return data
