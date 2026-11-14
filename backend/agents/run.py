"""Run an agent against a running environment over MCP Streamable HTTP.

    python -m agents.run --agent reference --url http://localhost:8000/mcp --pace 0.6 --reset slice --finalize

--reset and --finalize call the operator/evaluator endpoints with UF_VERIFIER_TOKEN. They are
harness actions, not agent actions: the agent itself only ever uses MCP tools.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from urllib.parse import urlparse

import httpx

from agents.baselines import AGENTS
from agents.mcp_client import EnvClient


def _base_url(mcp_url: str) -> str:
    parsed = urlparse(mcp_url)
    return f"{parsed.scheme}://{parsed.netloc}"


async def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--agent", choices=sorted(AGENTS), default="reference")
    parser.add_argument("--url", default="http://localhost:8000/mcp")
    parser.add_argument("--pace", type=float, default=0.0, help="seconds to wait after each tool call")
    parser.add_argument("--reset", metavar="SCENARIO", help="start a fresh episode first")
    parser.add_argument("--profile", default=None, help="spec profile for --reset (v0.2 or proposed)")
    parser.add_argument("--finalize", action="store_true", help="finalize and print the reward")
    args = parser.parse_args(argv)

    base = _base_url(args.url)
    headers = {"X-Verifier-Token": os.environ.get("UF_VERIFIER_TOKEN", "")}
    if args.reset:
        r = httpx.post(
            f"{base}/admin/reset",
            json={"scenario": args.reset, "profile": args.profile},
            headers=headers,
            timeout=30,
        )
        r.raise_for_status()
        print("reset:", json.dumps(r.json()))

    async with EnvClient(args.url, pace=args.pace) as env:
        await AGENTS[args.agent](env).run()
        print(f"agent {args.agent} finished after {env.calls} tool calls")

    if args.finalize:
        r = httpx.post(f"{base}/admin/finalize", headers=headers, timeout=30)
        r.raise_for_status()
        print(json.dumps(r.json()["reward"], indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
