"""Named random substreams derived from (seed, name), so luck is a property of the seed.

Naming scheme:
- stream(seed, "arrivals"): base Poisson arrivals and the ESI of every arrival
- stream(seed, "events"): event start ticks and which nurses fall sick
- stream(seed, f"patient:{pid}"): every per-patient draw (CT need, diversion roll, upgrade CT roll,
  hazard uniforms), consumed in a fixed order at world generation

Rule: every per-patient random quantity is drawn at world generation or from that patient's own
substream. No draw during play may come from a stream shared across patients or from a stream whose
position depends on agent actions.

Distributions use only Random.random(), so results do not depend on how a Python version implements
gauss, expovariate or choices.
"""

import hashlib
import math
import random


def stream(seed: int, name: str) -> random.Random:
    digest = hashlib.sha256(f"{seed}:{name}".encode()).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


def poisson(rng: random.Random, mean: float) -> int:
    """Knuth's method; fine for the small means (< 5) this sim uses."""
    limit = math.exp(-mean)
    count = 0
    product = rng.random()
    while product > limit:
        count += 1
        product *= rng.random()
    return count


def weighted_choice[T](rng: random.Random, weights: dict[T, float]) -> T:
    """Pick a key with probability proportional to its weight, in the dict's key order."""
    target = rng.random() * sum(weights.values())
    cumulative = 0.0
    for key, weight in weights.items():
        cumulative += weight
        if target < cumulative:
            return key
    return next(reversed(weights))
