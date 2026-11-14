"""The Harbor adapter stages public policy code and stops after exactly twelve ticks."""

import asyncio
import json
import subprocess
import tomllib
from pathlib import Path
from types import SimpleNamespace

import pytest
from ed72_baselines.client import run_episode
from ed72_baselines.harbor_agent import StopEarlyAgent
from ed72_baselines.policies import StopEarly
from ed72_baselines.ward_driver import WardClient
from fake_client import FakeClient
from harbor.environments.base import ExecResult
from harbor.models.agent.context import AgentContext
from harbor.models.task.config import MCPServerConfig, TaskOS
from harbor.trial.trial import Trial


def test_ward_transport_preserves_existing_policy_and_stops(monkeypatch: pytest.MonkeyPatch) -> None:
    # MOCK: replace the ward subprocess with the existing synthetic public-tool fixture.
    hospital = FakeClient()
    expected = FakeClient()
    run_episode(expected, StopEarly())

    def ward(command: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        assert kwargs["check"] is False
        assert command[0] == "ward"
        tool, arguments = command[1], json.loads(command[3])
        response = hospital.step(arguments["actions"]) if tool == "step" else getattr(hospital, tool)()
        return subprocess.CompletedProcess(command, 0, stdout=json.dumps(response))

    monkeypatch.setattr(subprocess, "run", ward)
    assert run_episode(WardClient(), StopEarly()) == 14
    assert hospital.steps == expected.steps
    assert hospital.tick == 12
    assert not hospital.finished


@pytest.mark.parametrize("response", [{"error": "call_cap"}, {"results": [{"ok": False, "reason": "bad"}]}])
def test_ward_errors_fail_the_agent(response: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    # MOCK: a public-tool failure must not become a successful partial baseline.
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess([], 0, stdout=json.dumps(response)),
    )
    with pytest.raises(RuntimeError):
        WardClient().step([])


def test_ward_nonzero_exit_keeps_the_tool_error(monkeypatch: pytest.MonkeyPatch) -> None:
    # MOCK: ward prints public-tool errors to stderr and exits nonzero.
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess([], 1, stdout="", stderr='{"error":"call_cap"}'),
    )
    with pytest.raises(RuntimeError, match="call_cap"):
        WardClient().observe()


class Environment:
    """MOCK: records Harbor's file staging and command execution without Docker."""

    def __init__(self, return_code: int = 0) -> None:
        self.return_code = return_code
        self.uploads: list[tuple[Path, str]] = []
        self.commands: list[str] = []

    async def upload_file(self, source_path: Path, target_path: str) -> None:
        assert source_path.is_file()
        self.uploads.append((source_path, target_path))

    async def exec(self, command: str) -> ExecResult:
        self.commands.append(command)
        return ExecResult(return_code=self.return_code, stdout="public tool calls", stderr=None)


def test_agent_stages_no_simulator_and_logs_execution(tmp_path: Path) -> None:
    agent = StopEarlyAgent(logs_dir=tmp_path)
    env = Environment()
    asyncio.run(agent.setup(env))
    asyncio.run(agent.run("", env, AgentContext()))
    assert {p.name for p, _ in env.uploads} == {
        "__init__.py",
        "client.py",
        "policies.py",
        "exploits.py",
        "ward_driver.py",
    }
    assert all("sim_client" not in p.read_text() for p, _ in env.uploads)
    assert env.commands[-1] == "PYTHONPATH=/tmp/ed72-stop-early python -m ed72_baselines.ward_driver"
    assert (tmp_path / "stop_early.txt").read_text() == "public tool calls"


def test_agent_accepts_the_real_task_mcp_configuration(tmp_path: Path) -> None:
    task = Path(__file__).resolve().parents[3] / "ed72" / "task.toml"
    servers = tomllib.loads(task.read_text())["environment"]["mcp_servers"]
    agent = StopEarlyAgent(
        logs_dir=tmp_path, mcp_servers=[MCPServerConfig.model_validate(s) for s in servers]
    )
    # MOCK: only the container/process boundary; use Harbor's real capability validation.
    trial = SimpleNamespace(
        agent=agent,
        user_agent=None,
        agent_environment=SimpleNamespace(os=TaskOS.LINUX),
        config=SimpleNamespace(agent=SimpleNamespace(name="stop_early", skills=[], mcp_servers=[])),
        _effective_skills_dir=None,
    )
    Trial._validate_agent_capabilities(trial)


def test_execution_failure_is_a_harbor_exception(tmp_path: Path) -> None:
    agent = StopEarlyAgent(logs_dir=tmp_path)
    with pytest.raises(RuntimeError, match="policy failed"):
        asyncio.run(agent.run("", Environment(return_code=1), AgentContext()))
