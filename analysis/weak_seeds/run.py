"""Where the ED-72 reference loses points on its weakest seeds. Stdlib only.

Usage: python analysis/weak_seeds/run.py [--seeds 42 1 2 3 4 5 11 ... 20] [--detail 2 ...]
                                         [--reference-dir PATH] [--config PATH]

Prints (1) the per-seed score table, then for each --detail seed the lost points split by
component, outcome, ESI, failure code and time bucket. Point loss per patient:
  O: (60 + 10*W + 10*B) * weight * loss / total_weight      (O multiplies the W and B terms)
  T: 20 * weight / total_weight for each patient not covered on time.
"""

import argparse
import importlib
import json
import statistics
import sys
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "ed72" / "environment" / "hospital"))

from ed72_sim import constants as c
from ed72_sim.config import load_config
from ed72_sim.engine import Simulation
from ed72_sim.scoring import score
from ed72_sim.world import generate_world

DEFAULT_SEEDS = [42, 1, 2, 3, 4, 5, *range(11, 21)]
HELD_OUT = range(11, 21)
LOSS = {
    "discharged": c.LOSS_DISCHARGED,
    "diverted": c.LOSS_DIVERTED,
    "in_bed_end": c.LOSS_IN_BED_COVERED,
}


def load_policy(directory: Path):
    sys.path.insert(0, str(directory))
    for name in ("policy", "reference", "ed72_reference"):
        sys.modules.pop(name, None)
    return importlib.import_module("ed72_reference").ReferencePolicy


def play(policy_cls, seed: int, config_path: str | None = None) -> tuple[Simulation, dict]:
    sim = Simulation(generate_world(seed, load_config(config_path)))
    policy = policy_cls()
    while True:
        observation = sim.observe()
        if observation["finished"]:
            break
        sim.step(policy.act(json.loads(json.dumps(observation))))
    return sim, score(sim.events)


def score_table(rows: dict[int, dict]) -> str:
    head = "| seed | score | O | T | W | B | spend | died | left | never adm. | diverted | faints |"
    lines = [head, "|" + "---|" * 12]
    for seed, s in rows.items():
        t = s["totals"]
        lines.append(
            f"| {seed} | {s['score']:.2f} | {s['O']:.3f} | {s['T']:.3f} | {s['W']:.3f} | {s['B']:.3f} "
            f"| {s['spend']} | {t['died']} | {t['left']} | {t['never_admitted']} | {t['diverted']} "
            f"| {t['faints']} |"
        )
    all_scores = [s["score"] for s in rows.values()]
    held = [s["score"] for k, s in rows.items() if k in HELD_OUT]
    lines.append("")
    lines.append(f"mean all seeds {statistics.mean(all_scores):.2f}, min {min(all_scores):.2f}")
    if held:
        lines.append(f"held-out 11-20 mean {statistics.mean(held):.2f}, min {min(held):.2f}")
    return "\n".join(lines)


def loss_points(s: dict) -> list[dict]:
    """Per patient: O points lost and T points lost."""
    pats = s["patients"]
    total_w = sum(c.OUTCOME_WEIGHT[p["esi"]] for p in pats)
    k_o = 60 + 10 * s["W"] + 10 * s["B"]
    out = []
    for p in pats:
        w = c.OUTCOME_WEIGHT[p["esi"]]
        if p["outcome"] in LOSS:
            loss = LOSS[p["outcome"]]
            if p["outcome"] == "in_bed_end" and p["first_covered_tick"] is None:
                loss = 1.0
        else:
            loss = 1.0
        out.append(p | {"o_pts": k_o * w * loss / total_w, "t_pts": 0 if p["on_time"] else 20 * w / total_w})
    return out


def breakdown(title: str, rows: list[dict], key: Callable[[dict], str | int | list[str]]) -> str:
    totals: dict[str | int, tuple[int, float, float]] = defaultdict(lambda: (0, 0.0, 0.0))
    for row in rows:
        group = key(row)
        for category in group if isinstance(group, list) else [group]:
            count, outcome_loss, timing_loss = totals[category]
            totals[category] = count + 1, outcome_loss + row["o_pts"], timing_loss + row["t_pts"]
    lines = [f"| {title} | patients | O pts lost | T pts lost |", "|---|---|---|---|"]
    for category, (count, outcome_loss, timing_loss) in sorted(totals.items()):
        lines.append(f"| {category} | {count} | {outcome_loss:.2f} | {timing_loss:.2f} |")
    return "\n".join(lines)


def bucket(tick: int) -> str:
    lo = tick // 12 * 12
    return f"{lo:03d}-{lo + 11:03d}"


def detail(seed: int, sim: Simulation, s: dict) -> str:
    rows = loss_points(s)
    ev = [e for e in sim.events if e["src"] == "sim" and e["event"] == "event_start"]
    spend_count = sum(e.get("event") == "spend" for e in sim.events)
    events = ", ".join(e["kind"] + "@" + str(e["t"]) for e in ev)
    w_pts = 10 * s["O"] * (1 - s["W"])
    b_pts = 10 * s["O"] * (1 - s["B"])
    o_pts = sum(r["o_pts"] for r in rows)
    t_pts = sum(r["t_pts"] for r in rows)
    out = [
        f"### Seed {seed}: {s['score']:.2f}",
        "",
        f"Events: {events}. Failures: {s['failures']}.",
        (
            f"Points lost: O {o_pts:.2f} (patients), T {t_pts:.2f}, W {w_pts:.2f}, B {b_pts:.2f}, "
            f"total {o_pts + t_pts + w_pts + b_pts:.2f} of 100."
        ),
        f"Spend events: {spend_count}, total {s['spend']}.",
        "",
        breakdown("outcome", rows, lambda r: r["outcome"]),
        "",
        breakdown("ESI", rows, lambda r: r["esi"]),
        "",
        breakdown("failure code", [r for r in rows if r["failure_codes"]], lambda r: r["failure_codes"]),
        "",
        breakdown("arrival ticks", rows, lambda r: bucket(r["arrived_tick"])),
        "",
    ]
    late = [r for r in rows if r["outcome"] in ("died", "left", "never_admitted", "in_bed_end")]
    late.sort(key=lambda r: -r["o_pts"])
    out.append("Largest patient losses:")
    out.append("")
    out.append("| patient | ESI | outcome | arrived | admitted | covered | failure codes | O pts |")
    out.append("|---|---|---|---|---|---|---|---|")
    for r in late[:8]:
        out.append(
            f"| {r['id']} | {r['esi']} | {r['outcome']} | {r['arrived_tick']} | {r['admitted_tick']} "
            f"| {r['first_covered_tick']} | {','.join(r['failure_codes'])} | {r['o_pts']:.2f} |"
        )
    return "\n".join(out)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--seeds", type=int, nargs="+", default=DEFAULT_SEEDS)
    ap.add_argument("--detail", type=int, nargs="*", default=[])
    ap.add_argument("--reference-dir", default=str(REPO / "ed72" / "solution"))
    ap.add_argument("--config", default=None)
    args = ap.parse_args(argv)
    policy_cls = load_policy(Path(args.reference_dir))
    runs = {seed: play(policy_cls, seed, args.config) for seed in args.seeds}
    print(score_table({k: v[1] for k, v in runs.items()}))
    for seed in args.detail:
        print()
        print(detail(seed, *runs[seed]))


if __name__ == "__main__":
    main()
