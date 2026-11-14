"""Play one policy against the in-process ED-72 simulator and write a replay for the pixel viewer.

The replay shape is frontend/src/replay/types.ts (Replay). Run from the repo root:

    PYTHONPATH=ed72/environment/hospital:ed72/solution \
      uv run --no-project --python 3.12 python frontend/tools/export_replay.py --policy reference --seed 42

The simulator is deterministic for a seed and a list of actions, so the replay is exactly what the
policy saw and did. The policy only ever sees observations, never the world or the seed.
"""

import argparse
import json
from collections.abc import Callable
from pathlib import Path

from ed72_sim.engine import Simulation
from ed72_sim.scoring import score
from ed72_sim.world import generate_world

TICKS = 144
OUT_DIR = Path(__file__).resolve().parent.parent / "public" / "replays"


def reference_policy() -> Callable[[dict], list[dict]]:
    from policy import ReferencePolicy

    return ReferencePolicy().actions


POLICIES: dict[str, tuple[str, Callable[[], Callable[[dict], list[dict]]]]] = {
    "reference": ("Reference policy (scripted)", reference_policy),
}


def export(policy_name: str, seed: int) -> dict:
    label, make = POLICIES[policy_name]
    act = make()
    sim = Simulation(generate_world(seed))
    ticks = []
    for _ in range(TICKS):
        obs = sim.observe()
        if obs["finished"]:
            break
        actions = act(obs)
        result = sim.step(actions)
        ticks.append({"tick": obs["tick"], "obs": obs, "actions": actions, "results": result["results"]})
    final_obs = sim.observe()
    sim.run_to_end()
    by_tick: dict[int, list[dict]] = {}
    for e in sim.events:
        if e.get("src") == "sim":
            by_tick.setdefault(e["t"], []).append(e)
    for t in ticks:
        t["events"] = by_tick.get(t["tick"], [])
    s = score(sim.events)
    return {
        "version": 1,
        "meta": {
            "name": f"{policy_name}-seed{seed}",
            "policy": policy_name,
            "label": label,
            "seed": seed,
            "reward": s["reward"],
            "score": s,
        },
        "ticks": ticks,
        "final_obs": final_obs,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", choices=sorted(POLICIES), default="reference")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    replay = export(args.policy, args.seed)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"{replay['meta']['name']}.json"
    out.write_text(json.dumps(replay, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size // 1024} KB, reward {replay['meta']['reward']:.3f})")


if __name__ == "__main__":
    main()
