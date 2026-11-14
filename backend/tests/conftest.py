from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from agents.mcp_client import EnvClient
from app.mcp_server import build_mcp
from app.settings import AppState, Settings


def make_state(
    scenario: str = "slice",
    profile: str = "v0.2",
    observe: bool = True,
    live_reveal: bool = True,
    seed: int | None = None,
) -> AppState:
    return AppState(
        Settings(
            scenario=scenario,
            seed=seed,
            profile=profile,
            observe=observe,
            live_reveal=live_reveal,
            spectator_token="s-test",
            verifier_token="v-test",
        )
    )


async def run_agent(state: AppState, agent_cls: type, **kwargs: Any) -> dict[str, Any]:
    async with EnvClient(build_mcp(state)) as env:
        await agent_cls(env, **kwargs).run()
    return state.service.finalize()


@pytest.fixture
def state_factory() -> Callable[..., AppState]:
    return make_state
