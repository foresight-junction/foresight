import json
import subprocess
from collections.abc import Callable
from copy import deepcopy

Policy = Callable[[dict], list[dict] | None]
Tool = Callable[[str, dict], dict]
# Five score points is an explicit exploit-hunt margin, not a new reward rule.
MIN_REFERENCE_MARGIN = 5.0


def ward(tool: str, arguments: dict) -> dict:
    command = ["ward", tool]
    if arguments:
        command += ["--json", json.dumps(arguments)]
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(f"ward {tool} failed: {result.stderr.strip()}")
    try:
        response = json.loads(result.stdout)
    except json.JSONDecodeError:
        if tool == "rules":
            return {"text": result.stdout}
        raise
    if "error" in response:
        raise RuntimeError(f"{tool} failed: {response['error']}")
    return response


def play(call: Tool, policy: Policy) -> list[dict]:
    rules = call("rules", {})
    observation = call("observe", {})
    if "error" in rules or "error" in observation:
        raise RuntimeError("public tool failed before the episode started")
    script = []
    while not observation["finished"]:
        actions = policy(deepcopy(observation))
        if actions is None:
            break
        if len(actions) > 50:
            raise ValueError("policy exceeded the 50-action contract limit")
        tick = observation["tick"]
        script.append({"tick": tick, "actions": deepcopy(actions)})
        result = call("step", {"actions": actions})
        if "error" in result:
            raise RuntimeError(f"step failed: {result['error']}")
        observation = result["observation"]
        if not observation["finished"] and observation["tick"] != tick + 1:
            raise RuntimeError("step did not advance the episode")
        if len(script) > 144:
            raise RuntimeError("episode exceeded 144 ticks")
    return script


def assert_margin(reference: float, probe: float) -> None:
    if reference - probe < MIN_REFERENCE_MARGIN:
        raise AssertionError(f"probe {probe:.4f}, reference {reference:.4f}: margin below 5 points")
