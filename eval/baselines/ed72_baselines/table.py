"""Print the baseline score table for the PR description (EVAL §5).

Usage, from eval/baselines/ with the hospital project importable:
    PYTHONPATH=../../ed72/environment/hospital uv run python -m ed72_baselines.table 1 2 3
"""

import sys

from ed72_baselines import BASELINES
from ed72_baselines.policies import SeverityPolicy
from ed72_baselines.sim_client import play_and_score

# The severity base is not a baseline, but it shows how far a simple honest player gets.
ROWS = BASELINES | {"severity_base": SeverityPolicy}


def main(seeds: list[int]) -> None:
    head = " | ".join(f"seed {s}" for s in seeds)
    print(f"| Policy | {head} | mean | deaths (mean) | faints (mean) |")
    print("|---|" + "---|" * (len(seeds) + 3))
    for name, make in ROWS.items():
        reports = [play_and_score(make(), seed) for seed in seeds]
        scores = [r["score"] for r in reports]
        deaths = sum(r["totals"]["died"] for r in reports) / len(reports)
        faints = sum(r["totals"]["faints"] for r in reports) / len(reports)
        cells = " | ".join(f"{s:.1f}" for s in scores)
        print(f"| {name} | {cells} | {sum(scores) / len(scores):.1f} | {deaths:.1f} | {faints:.1f} |")


if __name__ == "__main__":
    main([int(arg) for arg in sys.argv[1:]] or [1, 2, 3])
