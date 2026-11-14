"""Harbor adapter; only public-tool policy code is staged in the agent container."""

from pathlib import Path

from harbor.agents.base import BaseAgent
from harbor.agents.capabilities import AgentCapabilities
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext


class StopEarlyAgent(BaseAgent):
    capabilities = AgentCapabilities(mcp_servers=True)

    @staticmethod
    def name() -> str:
        return "stop_early"

    def version(self) -> str:
        return "1.0.0"

    async def setup(self, environment: BaseEnvironment) -> None:
        result = await environment.exec(command="mkdir -p /tmp/ed72-stop-early/ed72_baselines")
        if result.return_code != 0:
            raise RuntimeError(f"Stop-early setup failed: {result.stderr or result.stdout}")
        source = Path(__file__).parent
        for name in ("__init__.py", "client.py", "policies.py", "exploits.py", "ward_driver.py"):
            await environment.upload_file(
                source_path=source / name,
                target_path=f"/tmp/ed72-stop-early/ed72_baselines/{name}",
            )

    async def run(self, instruction: str, environment: BaseEnvironment, context: AgentContext) -> None:
        result = await environment.exec(
            command="PYTHONPATH=/tmp/ed72-stop-early python -m ed72_baselines.ward_driver",
        )
        (self.logs_dir / "stop_early.txt").write_text((result.stdout or "") + (result.stderr or ""))
        if result.return_code != 0:
            raise RuntimeError(
                f"Stop-early policy failed ({result.return_code}): {result.stderr or result.stdout}"
            )
