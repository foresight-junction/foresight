import importlib
import json
import sys
import types
from pathlib import Path
from typing import ClassVar

import pytest

HOSPITAL_DIR = Path(__file__).resolve().parents[1]


class FakeSimulation:
    """Test fake standing in for ed72_sim.engine (#3) until it merges."""

    instances: ClassVar[list["FakeSimulation"]] = []

    def __init__(self, world: object) -> None:
        self.world = world
        self.tick = 0
        self.events: list[dict] = []
        self.steps: list[list[dict]] = []
        self.ran_to_end = False
        FakeSimulation.instances.append(self)

    def step(self, actions: list[dict]) -> None:
        self.steps.append(actions)
        self.tick += 1

    def run_to_end(self) -> None:
        self.ran_to_end = True
        self.events.append({"event": "episode_end"})


@pytest.fixture
def collect_module(monkeypatch: pytest.MonkeyPatch):
    # Fakes for world.py (#3), engine.py (#3) and scoring/score.py (#4/#10), not yet on this branch.
    FakeSimulation.instances = []
    fakes = {
        "ed72_sim.world": {"generate_world": lambda seed: {"seed": seed}},
        "ed72_sim.engine": {"Simulation": FakeSimulation},
        "ed72_sim.scoring": {},
        "ed72_sim.scoring.score": {"score": lambda events: {"reward": 0.5, "n_events": len(events)}},
    }
    for name, attrs in fakes.items():
        module = types.ModuleType(name)
        module.__dict__.update(attrs)
        monkeypatch.setitem(sys.modules, name, module)
    monkeypatch.syspath_prepend(str(HOSPITAL_DIR))
    sys.modules.pop("collect", None)
    yield importlib.import_module("collect")
    sys.modules.pop("collect", None)


def write_log(path: Path, lines: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(line) for line in lines) + "\n", encoding="utf-8")


def step_line(tick: int, actions: list[dict]) -> dict:
    return {"seq": tick, "t": tick, "src": "agent", "tool": "step", "args": {"actions": actions}}


def test_replays_steps_in_order_and_writes_report(collect_module, tmp_path: Path) -> None:
    log = tmp_path / "events.jsonl"
    first, second = [{"type": "admit", "patient": "P001"}], [{"type": "discharge", "patient": "P001"}]
    write_log(log, [step_line(0, first), step_line(1, second)])
    out = tmp_path / "evidence" / "report.json"

    report = collect_module.collect(7, log, out)

    sim = FakeSimulation.instances[0]
    assert sim.world == {"seed": 7}
    assert sim.steps == [first, second]
    assert sim.ran_to_end
    assert report == {"reward": 0.5, "n_events": 1}
    assert json.loads(out.read_text(encoding="utf-8")) == report
    assert not list(out.parent.glob("*.tmp"))


def test_tick_mismatch_raises_and_writes_nothing(collect_module, tmp_path: Path) -> None:
    log = tmp_path / "events.jsonl"
    write_log(log, [step_line(0, []), step_line(5, [])])
    out = tmp_path / "report.json"

    with pytest.raises(ValueError, match="tick 5"):
        collect_module.collect(1, log, out)
    assert not out.exists()


def test_missing_log_means_zero_steps(collect_module, tmp_path: Path) -> None:
    out = tmp_path / "report.json"

    collect_module.collect(1, tmp_path / "absent.jsonl", out)

    sim = FakeSimulation.instances[0]
    assert sim.steps == []
    assert sim.ran_to_end
    assert out.exists()


def test_observe_rules_and_sim_lines_are_ignored(collect_module, tmp_path: Path) -> None:
    log = tmp_path / "events.jsonl"
    write_log(
        log,
        [
            {"seq": 0, "t": 0, "src": "sim", "event": "episode_start"},
            {"seq": 1, "t": 0, "src": "agent", "tool": "observe", "args": {}},
            {"seq": 2, "t": 0, "src": "agent", "tool": "rules", "args": {}},
            step_line(0, [{"type": "wait"}]),
        ],
    )

    collect_module.collect(1, log, tmp_path / "report.json")

    assert FakeSimulation.instances[0].steps == [[{"type": "wait"}]]


def test_corrupt_log_fails_loudly(collect_module, tmp_path: Path) -> None:
    log = tmp_path / "events.jsonl"
    log.write_text("not json\n", encoding="utf-8")

    with pytest.raises(json.JSONDecodeError):
        collect_module.collect(1, log, tmp_path / "report.json")


def test_refused_step_calls_are_not_replayed(collect_module, tmp_path: Path) -> None:
    log = tmp_path / "events.jsonl"
    refused = step_line(1, [{"type": "divert"}]) | {"result": {"error": "call_cap_reached"}}
    write_log(log, [step_line(0, []), refused])
    collect_module.collect(7, log, tmp_path / "report.json")
    assert FakeSimulation.instances[0].steps == [[]]
