"""Run the stand-in policy and each single-lever ablation in process and print a markdown table.

Usage: python -m ed72_ablations.run [--seeds 1 2 3] [--config PATH] [--json PATH]

The simulator is stdlib-only, so it is imported by putting ed72/environment/hospital on sys.path
rather than as a path dependency (that project also pulls in fastmcp for the tool server).
"""

import argparse
import json
import statistics
import sys
from collections.abc import Callable
from pathlib import Path

HOSPITAL = Path(__file__).resolve().parents[3] / "ed72" / "environment" / "hospital"
if str(HOSPITAL) not in sys.path:
    sys.path.insert(0, str(HOSPITAL))

from ed72_sim.config import load_config
from ed72_sim.engine import Simulation
from ed72_sim.scoring import score
from ed72_sim.world import generate_world

from ed72_ablations.standin import ALL_LEVERS, StandInPolicy

# Display order: rulebook failure code order F1..F6.
LEVERS = ("resus_reservation", "rest_rotation", "warnings", "ct_repair", "agency", "no_panic_divert")
CODES = dict(zip(LEVERS, ("F1", "F2", "F3", "F4", "F5", "F6"), strict=True))
assert frozenset(LEVERS) == ALL_LEVERS

Policy = Callable[[dict], list[dict]]


def variants() -> dict[str, frozenset[str]]:
    out = {"full": ALL_LEVERS}
    for lever in LEVERS:
        out[f"no {lever} ({CODES[lever]})"] = ALL_LEVERS - {lever}
    return out


def play(policy: Policy, seed: int, config_path: str | None = None) -> tuple[dict, list[list[dict]]]:
    """One full episode. Returns the score object and the action list sent at each tick."""
    sim = Simulation(generate_world(seed, load_config(config_path)))
    trace = []
    while True:
        obs = sim.observe()
        if obs["finished"]:
            break
        actions = policy(obs)
        trace.append(actions)
        sim.step(actions)
    return score(sim.events), trace


def run(seeds: list[int], config_path: str | None) -> dict[str, dict]:
    results = {}
    for name, levers in variants().items():
        per_seed = {}
        for seed in seeds:
            s, _ = play(StandInPolicy(levers), seed, config_path)
            per_seed[seed] = {k: s[k] for k in ("score", "O", "T", "W", "B", "spend")} | {
                "died": s["totals"]["died"],
                "faints": s["totals"]["faints"],
                "diverted": s["totals"]["diverted"],
            }
        results[name] = {
            "mean": {
                k: statistics.mean(r[k] for r in per_seed.values()) for k in ("score", "O", "T", "W", "B")
            },
            "per_seed": per_seed,
        }
    return results


def table(results: dict[str, dict], seeds: list[int]) -> str:
    full = results["full"]["mean"]["score"]
    head = ["variant", "mean score", "O", "T", "W", "B", "delta vs full", *[f"seed {s}" for s in seeds]]
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for name, r in results.items():
        m = r["mean"]
        delta = "" if name == "full" else f"{m['score'] - full:+.2f}"
        cells = [name, f"{m['score']:.2f}", *(f"{m[k]:.3f}" for k in "OTWB"), delta]
        cells += [f"{r['per_seed'][s]['score']:.2f}" for s in seeds]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seeds", type=int, nargs="+", default=[1, 2, 3])
    parser.add_argument(
        "--config", default=None, help="difficulty config JSON (default: the built-in defaults)"
    )
    parser.add_argument("--json", default=None, help="also write the results to this JSON file")
    args = parser.parse_args(argv)
    results = run(args.seeds, args.config)
    print(table(results, args.seeds))
    if args.json:
        Path(args.json).write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
