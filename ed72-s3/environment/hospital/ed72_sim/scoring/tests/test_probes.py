import sys
from importlib import import_module
from importlib.util import find_spec
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[6]))
invalid_actions = import_module("eval.probes.invalid_actions").invalid_actions
play = import_module("eval.probes.runner").play
engine = import_module("ed72_sim.engine")
world = import_module("ed72_sim.world")
scorer = import_module("ed72_sim.scoring.score")


@pytest.mark.parametrize("seed", [1, 2, 3, 4, 5, 42])
def test_invalid_spam_changes_no_patient_outcome_or_reward(seed: int) -> None:
    idle = engine.Simulation(world.generate_world(seed))
    idle.run_to_end()
    spam = engine.Simulation(world.generate_world(seed))

    def call(tool: str, arguments: dict) -> dict:
        if tool == "rules":
            # MOCK: rules payload is unused in this invalid-action transport test.
            return {"text": "fixture"}
        return spam.observe() if tool == "observe" else spam.step(arguments["actions"])

    script = play(call, invalid_actions)
    assert len(script) == 144
    idle_report, spam_report = scorer.score(idle.events), scorer.score(spam.events)
    for key in ("reward", "score", "O", "T", "W", "B", "spend", "totals", "patients"):
        assert spam_report[key] == idle_report[key]
    assert spam_report["reward"] == 0
    steps = [event for event in spam.events if event["src"] == "agent"]
    assert all(len(event["result"]["results"]) == 50 for event in steps)
    assert all(not result["ok"] for event in steps for result in event["result"]["results"])


def test_stopping_and_foreign_seed_replay_stay_below_reference() -> None:
    if find_spec("policy") is None:
        pytest.skip("#16 reference not integrated yet")
    from eval.probes.measure import measure
    from eval.probes.runner import assert_margin

    rulebook = Path(__file__).resolve().parents[6] / "docs/ED_Management_Simulator_RU.md"
    for seed, scores in measure(rules_text=rulebook.read_text(encoding="utf-8")).items():
        for name, value in scores.items():
            if name == "reference" or (name == "replay_seed_1" and seed == 1):
                continue
            assert_margin(scores["reference"], value)
