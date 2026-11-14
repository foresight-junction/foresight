import asyncio

from agents.mcp_client import EnvClient
from agents.reference import ReferenceAgent


async def main() -> None:
    async with EnvClient("http://unfindable:8000/mcp") as environment:
        agent = ReferenceAgent(environment)
        await agent.run()
        print(f"reference finished after {agent.handled} requests and {environment.calls} tool calls")


if __name__ == "__main__":
    asyncio.run(main())
