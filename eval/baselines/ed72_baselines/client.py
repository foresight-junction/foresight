"""The public tool interface a baseline plays through, and the episode loop (CONTRACTS v1).

A baseline sees exactly what an agent sees: `rules`, `observe` and `step`. It never gets the seed,
the world or the event log (AGENTS.md section 10, rule 4).
"""

from typing import Any, Protocol

Action = dict[str, Any]
Observation = dict[str, Any]

TOOL_CALL_CAP = 500  # counted by the hospital (CONTRACTS v1)


class Client(Protocol):
    def rules(self) -> dict[str, Any]: ...

    def observe(self) -> Observation: ...

    def step(self, actions: list[Action]) -> dict[str, Any]: ...


class Policy(Protocol):
    name: str

    def act(self, obs: Observation) -> list[Action] | None:
        """Actions for this tick, or None to stop calling tools (the rest of the episode runs empty)."""
        ...


def run_episode(client: Client, policy: Policy) -> int:
    """Play until the episode finishes, the policy stops, or a tool returns an error. Returns tool calls."""
    client.rules()
    obs = client.observe()
    calls = 2
    while not obs["finished"] and calls < TOOL_CALL_CAP:
        actions = policy.act(obs)
        if actions is None:
            break
        response = client.step(actions)
        calls += 1
        if "error" in response:
            break
        obs = response["observation"]
    return calls
