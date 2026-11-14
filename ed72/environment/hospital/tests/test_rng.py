import hashlib
import math
import random

import pytest
from ed72_sim.rng import poisson, stream, weighted_choice

WEIGHTS = {"a": 1.0, "b": 2.0, "c": 0.5, "d": 0.0}


def draws(rng: random.Random, n: int = 50) -> list[float]:
    return [rng.random() for _ in range(n)]


def test_same_seed_and_name_give_the_same_sequence() -> None:
    assert draws(stream(5, "arrivals")) == draws(stream(5, "arrivals"))


def test_different_names_and_seeds_give_unrelated_sequences() -> None:
    base = draws(stream(5, "arrivals"))
    for other in (draws(stream(5, "events")), draws(stream(6, "arrivals"))):
        assert other != base
        assert other[:3] != base[:3]


def test_derivation_is_sha256_not_python_hash() -> None:
    digest = hashlib.sha256(b"9:patient:P001").digest()
    expected = random.Random(int.from_bytes(digest[:8], "big"))
    assert draws(stream(9, "patient:P001")) == draws(expected)


def test_pinned_stream_values() -> None:
    rng = stream(1, "arrivals")
    assert [rng.random() for _ in range(3)] == [0.0036909453739580877, 0.4509823939460873, 0.7923151619731889]


def test_pinned_poisson_values() -> None:
    rng = stream(7, "p")
    assert [poisson(rng, 1.5) for _ in range(10)] == [1, 0, 1, 3, 1, 0, 1, 1, 3, 2]


def test_pinned_weighted_choice_values() -> None:
    rng = stream(3, "w")
    picks = [weighted_choice(rng, WEIGHTS) for _ in range(10)]
    assert picks == ["b", "b", "b", "b", "a", "a", "b", "c", "c", "b"]


def test_poisson_zero_mean_is_zero() -> None:
    rng = stream(1, "z")
    assert [poisson(rng, 0.0) for _ in range(20)] == [0] * 20


@pytest.mark.parametrize("mean", [1.5, 3.0])
def test_poisson_sample_mean(mean: float) -> None:
    rng = stream(11, "mean")
    samples = [poisson(rng, mean) for _ in range(20_000)]
    assert abs(sum(samples) / len(samples) - mean) < 0.02 * mean


def test_weighted_choice_frequencies_follow_weights() -> None:
    rng = stream(12, "freq")
    n = 20_000
    picks = [weighted_choice(rng, WEIGHTS) for _ in range(n)]
    total = sum(WEIGHTS.values())
    for key, weight in WEIGHTS.items():
        assert abs(picks.count(key) / n - weight / total) < 0.01


def test_zero_weight_keys_are_never_chosen() -> None:
    rng = stream(13, "zero")
    assert "d" not in {weighted_choice(rng, WEIGHTS) for _ in range(5_000)}


def test_invalid_inputs_raise() -> None:
    rng = stream(1, "bad")
    with pytest.raises(ValueError):
        poisson(rng, -0.1)
    with pytest.raises(ValueError):
        weighted_choice(rng, {})
    with pytest.raises(ValueError):
        weighted_choice(rng, {"a": 0.0})
    with pytest.raises(ValueError):
        weighted_choice(rng, {"a": 2.0, "b": -1.0})


@pytest.mark.parametrize("mean", [math.inf, math.nan])
def test_poisson_rejects_non_finite_mean(mean: float) -> None:
    with pytest.raises(ValueError):
        poisson(stream(1, "x"), mean)


@pytest.mark.parametrize("bad", [math.inf, math.nan])
def test_weighted_choice_rejects_non_finite_weights(bad: float) -> None:
    with pytest.raises(ValueError):
        weighted_choice(stream(1, "x"), {"a": 1.0, "b": bad})
