import asyncio
import json
import sys

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

URL = sys.argv[1] if len(sys.argv) > 1 else "http://unfindable:8000/mcp"


async def main() -> None:
    async with streamable_http_client(URL) as (read, write):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            tools = await session.list_tools()
            result = await session.call_tool("ping", {})
            texts = [c.text for c in result.content if getattr(c, "type", "") == "text"]
            print(
                json.dumps(
                    {
                        "server": init.server_info.name,
                        "tools": [t.name for t in tools.tools],
                        "ping_result": texts,
                        "structured": result.structured_content,
                        "is_error": result.is_error,
                    }
                )
            )


asyncio.run(main())
