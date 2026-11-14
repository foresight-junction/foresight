"""Hospital-side measurement harness. Only the tool adapter touches simulator internals."""

import json
from pathlib import Path

from .invalid_actions import invalid_actions
from .replay import replay
from .runner import Policy, play
from .stop_early import STOP_TICKS, stop_early


def run_episode(seed: int, policy: Policy, rules_text: str) -> tuple[dict, list[dict]]:
    from ed72_sim.engine import Simulation
    from ed72_sim.scoring.score import score
    from ed72_sim.world import generate_world

    sim = Simulation(generate_world(seed))

    def call(tool: str, arguments: dict) -> dict:
        if tool == "rules":
            return {"text": rules_text}
        if tool == "observe":
            return sim.observe()
        if tool == "step":
            return sim.step(arguments["actions"])
        raise ValueError(f"unknown public tool: {tool}")

    script = play(call, policy)
    sim.run_to_end()
    return score(sim.events), script


def measure(
    seeds: tuple[int, ...] = (1, 2, 3, 4, 5, 42), rules_text: str | None = None
) -> dict[int, dict[str, float]]:
    from policy import ReferencePolicy

    if rules_text is None:
        handbook = Path(__file__).resolve().parents[2] / "ed72/environment/workspace/HANDBOOK.md"
        rules_text = handbook.read_text(encoding="utf-8")
    _, script = run_episode(1, ReferencePolicy().actions, rules_text)
    results = {}
    for seed in seeds:
        policies = {
            "reference": ReferencePolicy().actions,
            "invalid_spam": invalid_actions,
            "replay_seed_1": replay(script),
        }
        policies.update({f"stop_{tick}": stop_early(ReferencePolicy().actions, tick) for tick in STOP_TICKS})
        results[seed] = {
            name: run_episode(seed, policy, rules_text)[0]["score"] for name, policy in policies.items()
        }
    return results


if __name__ == "__main__":
    print(json.dumps(measure(), indent=2))
