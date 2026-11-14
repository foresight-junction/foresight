"""Play the existing stop-early policy inside main using the public ward CLI."""

import json
import subprocess
from typing import Any

from ed72_baselines.client import Action, Observation, run_episode
from ed72_baselines.policies import StopEarly


class WardClient:
    def call(self, tool: str, arguments: dict) -> dict[str, Any]:
        result = subprocess.run(
            ["ward", tool, "--json", json.dumps(arguments)],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"ward {tool} failed ({result.returncode}): {result.stderr or result.stdout}")
        response = json.loads(result.stdout)
        if "error" in response:
            raise RuntimeError(f"ward {tool}: {response['error']}")
        if tool == "step":
            rejected = [r for r in response["results"] if not r["ok"]]
            if rejected:
                raise RuntimeError(f"Stop-early actions rejected: {rejected}")
        return response

    def rules(self) -> dict[str, Any]:
        return self.call("rules", {})

    def observe(self) -> Observation:
        return self.call("observe", {})

    def step(self, actions: list[Action]) -> dict[str, Any]:
        return self.call("step", {"actions": actions})


if __name__ == "__main__":
    print(f"Stop-early finished after {run_episode(WardClient(), StopEarly())} public tool calls")
