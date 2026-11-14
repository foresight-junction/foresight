import json
from pathlib import Path

import collect as collect_module
import pytest
from ed72_sim import constants as c
from ed72_sim.config import Config, load_config
from ed72_sim.engine import Simulation
from ed72_sim.scoring.score import score
from ed72_sim.world import generate_world
from sim_fixtures import advance

DEFAULT_JSON = Path(__file__).resolve().parents[1] / "config" / "default.json"


def write(tmp_path: Path, data: object) -> str:
    path = tmp_path / "cfg.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


def event_start(world, kind: str) -> int:
    return next(e.start_tick for e in world.events if e.kind == kind)


def test_default_json_equals_defaults() -> None:
    assert load_config(str(DEFAULT_JSON)) == Config() == load_config(None)


@pytest.mark.parametrize("seed", range(1, 6))
def test_default_config_world_is_unchanged(seed: int) -> None:
    assert generate_world(seed, Config()) == generate_world(seed)


def test_partial_override_keeps_other_defaults(tmp_path: Path) -> None:
    config = load_config(write(tmp_path, {"events": {"flu_wave": {"warning": 3}}}))
    assert config.events["flu_wave"] == {"window": (50, 61), "duration": 6, "warning": 3}
    assert config.events["bus_crash"] == Config().events["bus_crash"]


def test_higher_arrival_mean_adds_base_patients(tmp_path: Path) -> None:
    busy = generate_world(1, load_config(write(tmp_path, {"arrival_mean": 3.0})))
    base = lambda w: sum(p.source == "base" for p in w.patients)
    assert base(busy) > base(generate_world(1))


def test_moving_window_moves_start_tick(tmp_path: Path) -> None:
    config = load_config(write(tmp_path, {"events": {"bus_crash": {"window": [120, 125]}}}))
    start = event_start(generate_world(1, config), "bus_crash")
    assert 120 <= start <= 125
    assert event_start(generate_world(1), "bus_crash") < 120


def test_warning_changes_observation_timing(tmp_path: Path) -> None:
    def warnings_at(config: Config | None, tick: int) -> list[dict]:
        sim = Simulation(generate_world(1, config))
        advance(sim, tick)
        return sim.observe()["warnings"]

    start = event_start(generate_world(1), "flu_wave")
    config = load_config(write(tmp_path, {"events": {"flu_wave": {"warning": 2}}}))
    tick = start - 5
    assert any(w["event"] == "flu_wave" for w in warnings_at(None, tick))
    assert not any(w["event"] == "flu_wave" for w in warnings_at(config, tick))
    assert any(w["event"] == "flu_wave" for w in warnings_at(config, start - 1))


def test_flu_mix_changes_surge_patients(tmp_path: Path) -> None:
    config = load_config(write(tmp_path, {"flu_mix": {"3": 0.0, "4": 0.0, "5": 1.0}}))
    flu = [p for p in generate_world(1, config).patients if p.source == "flu"]
    assert flu and {p.esi for p in flu} == {5}


def test_budget_override_reaches_log_and_score(tmp_path: Path) -> None:
    config = load_config(write(tmp_path, {"budget": 100, "hard_limit": 300}))
    sim = Simulation(generate_world(1, config))
    sim.run_to_end()
    start = sim.events[0]
    assert (start["event"], start["budget"], start["hard_limit"]) == ("episode_start", 100, 300)
    spend = {"seq": 9999, "t": 5, "src": "sim", "event": "spend", "item": "repair", "amount": 200}
    assert score([*sim.events, spend])["B"] == 0.5


def test_collect_uses_config(tmp_path: Path) -> None:
    log = tmp_path / "absent.jsonl"
    default = collect_module.collect(1, log, tmp_path / "a.json")
    busy = collect_module.collect(
        1, log, tmp_path / "b.json", load_config(write(tmp_path, {"arrival_mean": 3.0}))
    )
    assert busy["totals"]["arrived"] > default["totals"]["arrived"]


BAD = [
    {"nope": 1},
    {"arrival_mean": "1.5"},
    {"arrival_mean": True},
    {"arrival_mean": -1},
    {"events": {"earthquake": {"window": [1, 2]}}},
    {"events": {"flu_wave": {"speed": 1}}},
    {"events": {"flu_wave": {"window": [50, 144]}}},
    {"events": {"flu_wave": {"window": [-1, 5]}}},
    {"events": {"flu_wave": {"window": [60, 50]}}},
    {"events": {"flu_wave": {"window": [50]}}},
    {"events": {"flu_wave": {"duration": 0}}},
    {"events": {"flu_wave": {"warning": -1}}},
    {"events": {"flu_wave": {"warning": 1.5}}},
    {"flu_mix": {"3": 0.5, "4": 0.4}},
    {"flu_mix": {"9": 1.0}},
    {"bus_mix": [1]},
    {"budget": 0},
    {"budget": -5, "hard_limit": 10},
    {"budget": 5000, "hard_limit": 4000},
    {"hard_limit": c.BUDGET - 1},
    {"hard_limit": c.BUDGET},
    {"arrival_amplitude": 1.01},
    {"arrival_amplitude": -0.1},
    [],
]


@pytest.mark.parametrize("bad", BAD, ids=[json.dumps(b) for b in BAD])
def test_invalid_config_raises(tmp_path: Path, bad: object) -> None:
    with pytest.raises(ValueError):
        load_config(write(tmp_path, bad))
