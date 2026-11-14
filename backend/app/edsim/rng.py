"""Seeded, named random streams.

Every distribution is built from `random.Random.random()` alone (inverse CDF and
Box-Muller), so a seed produces the same scenario on every Python version, not just on
versions whose `gauss`/`expovariate` internals happen to match.
"""

from __future__ import annotations

import hashlib
import math
import random
from collections.abc import Mapping, Sequence
from typing import TypeVar

T = TypeVar("T")


class Stream:
    def __init__(self, seed: int, name: str) -> None:
        digest = hashlib.sha256(f"{seed}:{name}".encode()).digest()
        self._rng = random.Random(int.from_bytes(digest[:8], "big"))

    def uniform(self, low: float = 0.0, high: float = 1.0) -> float:
        return low + (high - low) * self._rng.random()

    def integer(self, low: int, high: int) -> int:
        """Inclusive on both ends."""
        return min(high, low + int(self._rng.random() * (high - low + 1)))

    def chance(self, p: float) -> bool:
        return self._rng.random() < p

    def exponential(self, rate: float = 1.0) -> float:
        return -math.log(1.0 - self._rng.random()) / rate

    def normal(self) -> float:
        u1 = 1.0 - self._rng.random()
        u2 = self._rng.random()
        return math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)

    def lognormal_factor(self, sigma: float) -> float:
        """Multiplicative noise with median 1."""
        return math.exp(sigma * self.normal())

    def weighted(self, weights: Mapping[T, float]) -> T:
        items = list(weights.items())
        total = sum(w for _, w in items)
        target = self._rng.random() * total
        running = 0.0
        for item, weight in items:
            running += weight
            if target < running:
                return item
        return items[-1][0]

    def pick(self, items: Sequence[T]) -> T:
        return items[self.integer(0, len(items) - 1)]

    def sample(self, items: Sequence[T], k: int) -> list[T]:
        pool = list(items)
        chosen: list[T] = []
        for _ in range(min(k, len(pool))):
            chosen.append(pool.pop(self.integer(0, len(pool) - 1)))
        return chosen
