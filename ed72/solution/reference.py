"""Run the reference policy through the same ward tools available to an agent."""

import json
import subprocess
from collections.abc import Callable

from policy import ReferencePolicy


def ward(tool: str, arguments: dict) -> dict:
    try:
        result = subprocess.run(
            ["ward", tool, "--json", json.dumps(arguments)], check=True, capture_output=True, text=True
        )
    except subprocess.CalledProcessError as error:
        detail = error.stderr.strip() or error.stdout.strip()
        raise RuntimeError(f"ward {tool} failed ({error.returncode}): {detail}") from error
    response = json.loads(result.stdout)
    if "error" in response:
        raise RuntimeError(f"ward {tool}: {response['error']}")
    return response


def play(call: Callable[[str, dict], dict] = ward) -> dict:
    call("rules", {})
    observation = call("observe", {})
    policy = ReferencePolicy()
    for _ in range(144):
        if observation["finished"]:
            return observation
        tick = observation["tick"]
        response = call("step", {"actions": policy.actions(observation)})
        if "error" in response:
            raise RuntimeError(f"step: {response['error']}")
        rejected = [r for r in response["results"] if not r["ok"]]
        if rejected:
            raise RuntimeError(f"Reference actions rejected: {rejected}")
        observation = response["observation"]
        if not observation["finished"] and observation["tick"] != tick + 1:
            raise RuntimeError("step did not advance exactly one tick")
    if not observation["finished"]:
        raise RuntimeError("Episode did not finish after 144 steps")
    return observation


if __name__ == "__main__":
    play()
