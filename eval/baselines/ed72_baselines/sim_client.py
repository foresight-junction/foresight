"""Adapter that plays a baseline against the real sim in-process and scores it.

Needs ed72/environment/hospital on sys.path (issues #4 and #10). The interface assumed here is the
one collect.py (#11) uses: Simulation(generate_world(seed)), .observe(), .step(actions),
.run_to_end(), .events, and the pure scorer score(events). The policy only ever sees the Client
methods; the seed and the world stay on this side.
"""

from typing import Any

from ed72_baselines.client import Action, Observation, Policy, run_episode


class SimClient:
    def __init__(self, seed: int) -> None:
        from ed72_sim.engine import Simulation
        from ed72_sim.world import generate_world

        self._sim = Simulation(generate_world(seed))

    def rules(self) -> dict[str, Any]:
        return {"text": ""}  # baselines do not read the handbook

    def observe(self) -> Observation:
        return self._sim.observe()

    def step(self, actions: list[Action]) -> dict[str, Any]:
        return self._sim.step(actions)

    def finish(self) -> list[dict]:
        """Run the remaining ticks with no actions, as collect.py does, and return the event log."""
        self._sim.run_to_end()
        return self._sim.events


def play(policy: Policy, seed: int) -> list[dict]:
    client = SimClient(seed)
    run_episode(client, policy)
    return client.finish()


def play_and_score(policy: Policy, seed: int) -> dict:
    from ed72_sim.scoring import score

    return score(play(policy, seed))
