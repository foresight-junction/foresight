from collections.abc import Callable

# #12 owns the rulebook's 12-tick baseline; these probe other stopping points.
STOP_TICKS = (0, 1, 6, 24, 48, 72)


def stop_early(policy: Callable[[dict], list[dict]], tick: int) -> Callable[[dict], list[dict] | None]:
    if tick < 0:
        raise ValueError("stop tick must be nonnegative")

    def actions(observation: dict) -> list[dict] | None:
        return None if observation["tick"] >= tick else policy(observation)

    return actions
