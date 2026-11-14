import json
import math
import os
import sys

REWARD_PATH = "/logs/verifier/reward.txt"
EVIDENCE_PATH = "/evidence/finalize.json"


def write_reward(value: float) -> None:
    with open(REWARD_PATH, "w", encoding="utf-8") as reward_file:
        reward_file.write(f"{value:.6f}\n")


def main() -> int:
    os.makedirs(os.path.dirname(REWARD_PATH), exist_ok=True)
    write_reward(0.0)
    try:
        with open(EVIDENCE_PATH, encoding="utf-8") as evidence_file:
            result = json.load(evidence_file)
        score = result["reward"]["reward"]
        if isinstance(score, bool) or not isinstance(score, (int, float)):
            raise ValueError("evaluator reward is not numeric")
        score = float(score)
        if not math.isfinite(score) or not 0.0 <= score <= 1.0:
            raise ValueError("evaluator reward is outside [0, 1]")
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as error:
        print(f"Could not read a valid evaluator score: {error}", file=sys.stderr)
        return 1

    write_reward(score)
    print(f"reward={score:.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
