import importlib.util
import json
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "summarise", Path(__file__).resolve().parent.parent / "summarise.py"
)
summarise = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(summarise)


def _report(reward: float, ended: str = "tick_143", seed: int | None = None) -> dict:
    # MOCK: synthetic CONTRACTS v1 score object, not produced by the real scorer.
    report = {
        "reward": reward,
        "score": reward * 100,
        "O": reward,
        "T": 0.5,
        "W": 0.8,
        "B": 1.0,
        "totals": {"died": 2, "faints": 1},
        "ended": ended,
    }
    if seed is not None:
        report["seed"] = seed
    return report


def _trial(
    jobs: Path,
    job: str,
    trial: str,
    agent: str,
    *,
    reward: float | None,
    model: tuple[str, str] | None = None,
    report: dict | None = None,
    report_in_artifacts: bool = False,
    reward_txt_only: bool = False,
    exception: str | None = None,
    finished: bool = True,
) -> Path:
    """MOCK: write a Harbor 0.25.0 trial dir shaped like the #21 spike output, without running Harbor."""
    d = jobs / job / trial
    (d / "verifier").mkdir(parents=True)
    (d / "artifacts" / "evidence").mkdir(parents=True)
    (jobs / job / "config.json").write_text(json.dumps({"job_name": job}))
    (d / "config.json").write_text(json.dumps({"trial_name": trial, "task": {"path": "ed72"}}))
    if not finished:
        return d
    result = {
        "trial_name": trial,
        "config": {"agent": {"name": agent, "model_name": "/".join(model) if model else None}},
        "agent_info": {
            "name": agent,
            "version": "1.0.0",
            "model_info": {"provider": model[0], "name": model[1]} if model else None,
        },
        "verifier_result": None,
        "exception_info": None,
    }
    if reward is not None and not reward_txt_only:
        result["verifier_result"] = {"rewards": {"reward": reward}}
    if reward is not None:
        (d / "verifier" / "reward.txt").write_text(f"{reward}\n")
    if exception:
        result["exception_info"] = {"exception_type": exception}
    (d / "result.json").write_text(json.dumps(result))
    if report is not None:
        target = (
            d / "artifacts" / "evidence" / "report.json"
            if report_in_artifacts
            else d / "verifier" / "score_full.json"
        )
        target.write_text(json.dumps(report))
    return d


@pytest.fixture
def jobs(tmp_path: Path) -> Path:
    root = tmp_path / "jobs"
    _trial(root, "ed72-oracle", "ed72__a", "oracle", reward=0.92, report=_report(0.92))
    _trial(root, "ed72-nop", "ed72__b", "nop", reward=0.0, report=_report(0.0, ended="agent_stopped"))
    model = ("gemini", "gemini-3.8-flash")
    _trial(root, "ed72-agent", "ed72__c1", "opencode", reward=0.6, model=model, report=_report(0.6))
    _trial(root, "ed72-agent", "ed72__c2", "opencode", reward=0.4, model=model, report=_report(0.4))
    _trial(
        root, "ed72-agent", "ed72__c3", "opencode", reward=None, model=model, exception="AgentTimeoutError"
    )
    return root


def _rows(root: Path) -> dict[str, summarise.Row]:
    trials = [summarise.load_trial(d) for d in summarise.find_trial_dirs([root])]
    return {r.policy: r for r in summarise.build_rows([t for t in trials if t is not None])}


def test_groups_by_policy_and_counts_errors_as_zero(jobs: Path) -> None:
    rows = _rows(jobs)
    assert set(rows) == {"reference (oracle)", "do-nothing (nop)", "opencode"}
    agent = rows["opencode"]
    assert agent.model == "gemini/gemini-3.8-flash"
    assert (agent.runs, agent.errors) == (3, 1)
    assert agent.mean == pytest.approx((0.6 + 0.4 + 0.0) / 3)
    assert (agent.low, agent.high) == (0.0, 0.6)
    assert agent.extras["O"] == pytest.approx(0.5)
    assert agent.extras["died"] == pytest.approx(2.0)
    assert rows["reference (oracle)"].mean == pytest.approx(0.92)


def test_render_orders_by_mean_and_reports_gap(jobs: Path) -> None:
    trials = [summarise.load_trial(d) for d in summarise.find_trial_dirs([jobs])]
    text = summarise.render([t for t in trials if t], ["jobs"], pending=0)
    table = [line for line in text.splitlines() if line.startswith("| ") and "Policy" not in line]
    assert table[0].startswith("| reference (oracle) |")
    assert table[1].startswith("| opencode | `gemini/gemini-3.8-flash` |")
    assert table[2].startswith("| do-nothing (nop) |")
    assert "- opencode `gemini/gemini-3.8-flash` seed -: +0.587" in text
    assert (
        "| ed72-agent | ed72__c3 | opencode | gemini/gemini-3.8-flash | - | - | AgentTimeoutError |" in text
    )


def test_unfinished_trial_is_left_out(tmp_path: Path) -> None:
    root = tmp_path / "jobs"
    _trial(root, "ed72-oracle", "ed72__a", "oracle", reward=1.0, report=_report(1.0))
    _trial(root, "ed72-oracle", "ed72__b", "oracle", reward=None, finished=False)
    out = tmp_path / "summary.md"
    assert summarise.main([str(root), "--out", str(out)]) == 0
    text = out.read_text()
    assert "1 finished trials, 1 still running (left out)." in text
    assert "| reference (oracle) | - | - | 1 | 0 | 1.000 |" in text


def test_reward_txt_and_artifact_report_fallbacks(tmp_path: Path) -> None:
    root = tmp_path / "jobs"
    d = _trial(
        root,
        "ed72-oracle",
        "ed72__a",
        "oracle",
        reward=0.75,
        report=_report(0.75, seed=7),
        report_in_artifacts=True,
        reward_txt_only=True,
    )
    trial = summarise.load_trial(d)
    assert trial is not None
    assert trial.reward == pytest.approx(0.75)
    assert trial.seed == "7"
    assert trial.report is not None and trial.report["O"] == pytest.approx(0.75)


def test_main_fails_loudly_without_trials(tmp_path: Path) -> None:
    empty = tmp_path / "jobs"
    empty.mkdir()
    assert summarise.main([str(empty), "--out", str(tmp_path / "s.md")]) == 1
    assert summarise.main([str(tmp_path / "missing"), "--out", str(tmp_path / "s.md")]) == 2


def test_rewarded_exception_counts_as_error(tmp_path: Path) -> None:
    root = tmp_path / "jobs"
    _trial(
        root,
        "ed72-agent",
        "ed72__a",
        "opencode",
        reward=0.3,
        report=_report(0.3),
        exception="AgentTimeoutError",
    )
    row = _rows(root)["opencode"]
    assert (row.runs, row.errors, row.mean) == (1, 1, pytest.approx(0.3))


def test_main_fails_when_a_trial_has_no_reward(jobs: Path, tmp_path: Path) -> None:
    out = tmp_path / "summary.md"
    assert summarise.main([str(jobs), "--out", str(out)]) == 3
    assert out.is_file()
