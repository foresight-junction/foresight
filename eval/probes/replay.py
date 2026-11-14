from collections.abc import Callable
from copy import deepcopy


def replay(script: list[dict]) -> Callable[[dict], list[dict]]:
    by_tick = {entry["tick"]: deepcopy(entry["actions"]) for entry in script}
    if len(by_tick) != len(script):
        raise ValueError("script contains duplicate ticks")

    def actions(observation: dict) -> list[dict]:
        return deepcopy(by_tick.get(observation["tick"], []))

    return actions
