import json
import sys
from importlib import import_module
from pathlib import Path
from time import perf_counter

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[6]))
invalid_actions = import_module("eval.probes.invalid_actions").invalid_actions
collect = import_module("collect")
engine = import_module("ed72_sim.engine")
world = import_module("ed72_sim.world")

# #22 currently gives collect 60 seconds; require at least 6x headroom.
COLLECT_BUDGET_SECONDS = 10.0


@pytest.mark.parametrize("steps", [1, 144])
def test_episode_replay_tail_score_and_report_fit_collect_budget(tmp_path: Path, steps: int) -> None:
    log = tmp_path / "events.jsonl"
    sim = engine.Simulation(world.generate_world(42), log_path=log)
    for _ in range(steps):
        sim.step(invalid_actions(sim.observe()))
    start = perf_counter()
    report = collect.collect(42, log, tmp_path / "report.json")
    elapsed = perf_counter() - start
    assert report["reward"] == 0
    assert report["ended"] == ("tick_143" if steps == 144 else "agent_stopped")
    assert json.loads((tmp_path / "report.json").read_text()) == report
    assert elapsed < COLLECT_BUDGET_SECONDS, f"collect took {elapsed:.3f}s; budget is 10s"
