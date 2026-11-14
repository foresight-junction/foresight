"""Play one policy against the in-process ED-72 simulator and write a replay for the pixel viewer.

The replay shape is frontend/src/replay/types.ts (Replay); index.json (rewritten
on every run) is a list of ReplayIndexEntry for every replay in public/replays.
Run from the repo root (PYTHONPATH separator is ';' on Windows, ':' elsewhere):

    PYTHONPATH="ed72/environment/hospital;ed72/solution;eval/baselines" \
      uv run --no-project --python 3.12 python frontend/tools/export_replay.py --policy gemini --seed 42
    ... export_replay.py --all          # every shipped policy (SHIPPED) for the seed

The simulator is deterministic for a seed and a list of actions, so the replay is exactly what the
policy saw and did. The policy only ever sees observations, never the world or the seed.
"""

import argparse
import copy
import json
from collections.abc import Callable
from pathlib import Path

from ed72_sim.engine import Simulation
from ed72_sim.scoring import score
from ed72_sim.world import generate_world

TICKS = 144
OUT_DIR = Path(__file__).resolve().parent.parent / "public" / "replays"


class RecordingSim:
    """The observe/step surface a policy plays through; keeps what it saw, did and got back per tick."""

    def __init__(self, sim: Simulation) -> None:
        self.sim = sim
        self.ticks: list[dict] = []

    def observe(self) -> dict:
        return self.sim.observe()

    def step(self, actions: list[dict]) -> dict:
        obs = self.sim.observe()
        out = self.sim.step(actions)
        if "error" not in out:
            self.ticks.append(
                {
                    "tick": obs["tick"],
                    "obs": obs,
                    "actions": copy.deepcopy(actions),
                    "results": out["results"],
                }
            )
        return out


Act = Callable[[dict], list[dict] | None]


def play_act(act: Act, sim: RecordingSim) -> None:
    # A policy that returns None stops calling tools; the rest of the episode then runs with no
    # actions. Stepping [] gives the same sim events (so the same reward) and keeps one replay tick
    # per sim tick; only the score's agent-side fields (ended, tool_calls) differ.
    stopped = False
    obs = sim.observe()
    while not obs["finished"]:
        actions = None if stopped else act(obs)
        stopped = stopped or actions is None
        obs = sim.step(actions or [])["observation"]


def reference(sim: RecordingSim) -> None:
    from policy import ReferencePolicy

    play_act(ReferencePolicy().actions, sim)


def gemini(sim: RecordingSim) -> None:
    from gemini_policy.adapter import run_gemini

    run_gemini(sim)


def reactive(sim: RecordingSim) -> None:
    from ed72_baselines.policies import ReactiveProxy

    play_act(ReactiveProxy().act, sim)


def do_nothing(sim: RecordingSim) -> None:
    from ed72_baselines.policies import DoNothing

    play_act(DoNothing().act, sim)


# Order here is the order of index.json (reference first).
POLICIES: dict[str, tuple[str, Callable[[RecordingSim], None]]] = {
    "reference": ("Reference policy (scripted)", reference),
    "gemini": ("Gemini 3.8 Flash (its own script)", gemini),
    "reactive": ("Reactive proxy (typical model play)", reactive),
    "do-nothing": ("Do nothing", do_nothing),
}
# What --all writes. do-nothing is left out: its queue never empties, so the replay is about 1.6 MB,
# over the viewer's ~1.5 MB budget. `--policy do-nothing` still writes it and the index picks it up.
SHIPPED = ("reference", "gemini", "reactive")


def export(policy_name: str, seed: int) -> dict:
    label, play = POLICIES[policy_name]
    sim = Simulation(generate_world(seed))
    rec = RecordingSim(sim)
    play(rec)
    final_obs = sim.observe()
    sim.run_to_end()
    by_tick: dict[int, list[dict]] = {}
    for e in sim.events:
        if e.get("src") == "sim":
            by_tick.setdefault(e["t"], []).append(e)
    ticks = rec.ticks
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


def write_replay(replay: dict, out_dir: Path = OUT_DIR) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{replay['meta']['name']}.json"
    out.write_text(json.dumps(replay, separators=(",", ":")), encoding="utf-8")
    return out


def write_index(out_dir: Path = OUT_DIR) -> Path:
    """List every replay in out_dir as ReplayIndexEntry, in POLICIES order then by seed."""
    order = list(POLICIES)
    entries = []
    for path in out_dir.glob("*.json"):
        if path.name == "index.json":
            continue
        meta = json.loads(path.read_text(encoding="utf-8"))["meta"]
        entries.append(
            {
                "file": path.name,
                "label": meta["label"],
                "policy": meta["policy"],
                "seed": meta["seed"],
                "reward": meta["reward"],
            }
        )
    entries.sort(
        key=lambda e: (order.index(e["policy"]) if e["policy"] in order else len(order), e["seed"], e["file"])
    )
    index = out_dir / "index.json"
    index.write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8", newline="\n")
    return index


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", choices=list(POLICIES), default="reference")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--all", action="store_true", help="export every shipped policy for --seed")
    args = parser.parse_args()
    for name in SHIPPED if args.all else [args.policy]:
        replay = export(name, args.seed)
        out = write_replay(replay)
        print(f"wrote {out} ({out.stat().st_size // 1024} KB, reward {replay['meta']['reward']:.6f})")
    print(f"wrote {write_index()}")


if __name__ == "__main__":
    main()
