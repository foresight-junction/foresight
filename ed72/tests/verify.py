"""Verifier: turn /evidence/report.json into /logs/verifier/reward.txt.

Reads only the report artifact (collected from the hospital container). Any problem
writes 0 and exits non-zero, so a forged or truncated report cannot score.
"""

import json
import math
import sys
from pathlib import Path

REPORT_PATH = Path("/evidence/report.json")
REWARD_PATH = Path("/logs/verifier/reward.txt")
FULL_PATH = Path("/logs/verifier/score_full.json")
TOLERANCE = 1e-3


def number(report: dict, key: str, low: float = 0.0, high: float = 1.0) -> float:
    value = report[key]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{key} is not a number")
    if not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f"{key}={value} is outside [{low}, {high}]")
    return float(value)


def validate(report: object) -> float:
    if not isinstance(report, dict):
        raise TypeError("report is not a JSON object")
    reward = number(report, "reward")
    total = number(report, "score", 0.0, 100.0)
    o, t, w, b = (number(report, key) for key in ("O", "T", "W", "B"))
    if abs(reward - total / 100) > TOLERANCE:
        raise ValueError(f"reward {reward} does not match score {total}")
    expected = 60 * o + 20 * t + o * (10 * w + 10 * b)
    if abs(total - expected) > TOLERANCE:
        raise ValueError(f"score {total} does not match components {expected}")
    return reward


def run(report_path: Path, reward_path: Path, full_path: Path) -> int:
    reward_path.parent.mkdir(parents=True, exist_ok=True)
    reward_path.write_text("0\n", encoding="utf-8")
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
        reward = validate(report)
    except (OSError, ValueError, TypeError, KeyError) as error:
        print(f"Invalid report: {error}", file=sys.stderr)
        return 1
    full_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    reward_path.write_text(f"{reward:.6f}\n", encoding="utf-8")
    print(f"reward={reward:.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run(REPORT_PATH, REWARD_PATH, FULL_PATH))
