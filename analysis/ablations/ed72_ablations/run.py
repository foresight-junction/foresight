"""Run the stand-in policy and each single-lever ablation in process and print a markdown table.

Usage: python -m ed72_ablations.run [--seeds 1 2 3] [--config PATH] [--json PATH]
                                    [--policy standin|reference] [--reference-dir PATH]

`--policy reference` adds one row: the #16 reference (`ed72_reference.ReferencePolicy` from
ed72/solution/, or --reference-dir) played unablated. The levers exist only in the stand-in.

The simulator is stdlib-only, so it is imported by putting ed72/environment/hospital on sys.path
rather than as a path dependency (that project also pulls in fastmcp for the tool server).
"""

import argparse
import importlib
import json
import statistics
import sys
from collections.abc import Callable
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
HOSPITAL = REPO / "ed72" / "environment" / "hospital"
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
if frozenset(LEVERS) != ALL_LEVERS:
    raise RuntimeError("run.LEVERS and standin.ALL_LEVERS disagree")

# A policy maps an observation to actions; None means it stops acting (the rest runs with no actions).
Policy = Callable[[dict], list[dict] | None]
REFERENCE_ROW = "reference (unablated, #16)"


def variants() -> dict[str, frozenset[str]]:
    """Full, then the five skill ablations, then F6, which adds a harmful habit instead of removing a skill."""
    out = {"full": ALL_LEVERS}
    for lever in LEVERS[:-1]:
        out[f"no {lever} ({CODES[lever]})"] = ALL_LEVERS - {lever}
    out["adds panic divert (F6)"] = ALL_LEVERS - {"no_panic_divert"}
    return out


def load_reference(directory: Path) -> Callable[[], Policy]:
    if not (directory / "ed72_reference.py").exists():
        raise SystemExit(f"no #16 reference at {directory} (ed72_reference.py missing)")
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))
    module = importlib.import_module("ed72_reference")
    return lambda: module.ReferencePolicy().act


def play(policy: Policy, seed: int, config_path: str | None = None) -> tuple[dict, list[list[dict]]]:
    """One full episode. Returns the score object and the action list sent at each tick."""
    sim = Simulation(generate_world(seed, load_config(config_path)))
    trace = []
    while True:
        obs = sim.observe()
        if obs["finished"]:
            break
        actions = policy(json.loads(json.dumps(obs)))  # a copy, as the agent would get over MCP
        if actions is None:
            sim.run_to_end()
            break
        trace.append(actions)
        sim.step(actions)
    return score(sim.events), trace


def run(
    seeds: list[int], config_path: str | None, reference: Callable[[], Policy] | None = None
) -> dict[str, dict]:
    makers: dict[str, Callable[[], Policy]] = {
        name: (lambda levers=levers: StandInPolicy(levers)) for name, levers in variants().items()
    }
    if reference is not None:
        makers[REFERENCE_ROW] = reference
    results = {}
    for name, make in makers.items():
        per_seed = {}
        for seed in seeds:
            s, _ = play(make(), seed, config_path)
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
    parser.add_argument("--policy", choices=("standin", "reference"), default="standin")
    parser.add_argument("--reference-dir", default=str(REPO / "ed72" / "solution"))
    args = parser.parse_args(argv)
    reference = load_reference(Path(args.reference_dir)) if args.policy == "reference" else None
    results = run(args.seeds, args.config, reference)
    print(table(results, args.seeds))
    if args.json:
        Path(args.json).write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
