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


@pytest.fixture(autouse=True)
def _hermetic_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Fixture trials record the relative task path "ed72"; keep it from resolving to the real task dir.
    monkeypatch.setattr(summarise, "REPO_ROOT", tmp_path / "no-repo")
    monkeypatch.delenv("ED72_SEED", raising=False)


def _manifest(
    job_dir: Path,
    seed: int | None = 42,
    config: str = "c" * 64,
    instr: str = "i" * 64,
    reference: str = "r" * 64,
) -> None:
    # MOCK: hand-written manifest.json, same keys as eval/manifest.py write_manifest.
    data = {
        "seed": seed,
        "config_sha256": config,
        "instruction_sha256": instr,
        "task_sha256": "t" * 64,
        "reference_sha256": reference,
        "source_commit": "5" * 40,
        "source_dirty": False,
    }
    (job_dir / "manifest.json").write_text(json.dumps(data))


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
    for job in root.iterdir():
        _manifest(job)
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
    assert (
        "- opencode `gemini/gemini-3.8-flash` seed 42 config cccccccc instruction iiiiiiii task tttttttt reference rrrrrrrr source 55555555: +0.587"
        in text
    )
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
    assert (
        "| reference (oracle) | - | unknown | unknown | unknown | unknown | unknown | unknown | 1 | 0 | 1.000 |"
        in text
    )


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
    assert summarise.main([str(root), "--out", str(tmp_path / "summary.md")]) == 3


def test_main_fails_when_a_trial_has_no_reward(jobs: Path, tmp_path: Path) -> None:
    out = tmp_path / "summary.md"
    assert summarise.main([str(jobs), "--out", str(out)]) == 3
    assert out.is_file()


def _write_task(root: Path, name: str, seed: int, instruction: str, config: str) -> Path:
    # MOCK: minimal Harbor task dir with only the files manifest.py reads.
    task = root / name
    (task / "environment" / "hospital" / "config").mkdir(parents=True)
    (task / "environment" / "docker-compose.yaml").write_text(
        "\n".join(["services:", "  hospital:", "    environment:", f'      ED72_SEED: "{seed}"', ""])
    )
    (task / "environment" / "hospital" / "config" / "default.json").write_text(config)
    (task / "instruction.md").write_text(instruction)
    return task


def test_manifest_cli_records_seed_and_hashes(tmp_path: Path) -> None:
    manifest = summarise.manifest
    task = _write_task(tmp_path, "ed72-s7", 7, "play well", "{}")
    job = tmp_path / "job"
    assert manifest.main([str(job), "--task", str(task), "--harbor-version", "0.26.0"]) == 0
    data = json.loads((job / "manifest.json").read_text())
    assert data["seed"] == 7 and data["harbor_version"] == "0.26.0"
    assert data["instruction_sha256"] == manifest.sha256_file(task / "instruction.md")
    assert data["config_sha256"] == manifest.sha256_file(
        task / "environment" / "hospital" / "config" / "default.json"
    )


def test_seed_falls_back_to_task_name_and_default(tmp_path: Path) -> None:
    manifest = summarise.manifest
    bare = tmp_path / "ed72"
    bare.mkdir()
    named = tmp_path / "ed72-s9"
    named.mkdir()
    assert manifest.task_facts(bare)["seed"] == 42
    assert manifest.task_facts(named)["seed"] == 9
    assert manifest.task_facts(tmp_path)["seed"] is None


def test_no_pooling_across_seed_instruction_or_missing_provenance(tmp_path: Path) -> None:
    root = tmp_path / "jobs"
    cfg = "c" * 64
    runs = [
        # job, agent, model, reward, seed, instruction
        ("ref-s1", "oracle", None, 0.9, 1, "a"),
        ("ref-s2", "oracle", None, 0.7, 2, "a"),
        ("agent-s1", "opencode", ("g", "m"), 0.5, 1, "a"),
        ("agent-s2", "opencode", ("g", "m"), 0.2, 2, "a"),
        ("agent-s1-prompt-b", "opencode", ("g", "m"), 0.6, 1, "b"),
    ]
    for job, agent, model, reward, seed, instr in runs:
        _trial(root, job, f"ed72__{job}", agent, reward=reward, model=model, report=_report(reward))
        _manifest(root / job, seed=seed, config=cfg, instr=instr * 64)
    _trial(root, "agent-old", "ed72__old", "opencode", reward=0.1, model=("g", "m"), report=_report(0.1))

    trials = [summarise.load_trial(d) for d in summarise.find_trial_dirs([root])]
    rows = summarise.build_rows([t for t in trials if t])
    agent_rows = [r for r in rows if r.policy == "opencode"]
    assert len(agent_rows) == 4 and all(r.runs == 1 for r in agent_rows)
    unknown = [r for r in agent_rows if r.seed == "unknown"]
    assert len(unknown) == 1 and unknown[0].config == "unknown" and unknown[0].mean == pytest.approx(0.1)

    gaps = summarise._gaps(rows)
    assert len(gaps) == 2
    assert any("seed 1 " in g and "aaaaaaaa" in g and g.endswith("+0.400") for g in gaps)
    assert any("seed 2 " in g and g.endswith("+0.500") for g in gaps)
    # Prompt b has no matching reference row, and the unknown row has no seed: neither gets a gap.
    assert not any("bbbbbbbb" in g or "unknown" in g for g in gaps)


def test_manifest_derived_from_recorded_task_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    task = _write_task(tmp_path, "ed72-s5", 5, "hi", "{}")
    root = tmp_path / "jobs"
    d = _trial(root, "j", "ed72__a", "oracle", reward=1.0, report=_report(1.0))
    (d / "config.json").write_text(json.dumps({"trial_name": "ed72__a", "task": {"path": str(task)}}))
    trial = summarise.load_trial(d)
    assert trial is not None
    assert trial.seed == "5" and trial.config != "unknown" and trial.instruction != "unknown"


def test_unknown_provenance_trials_are_never_pooled_with_each_other(tmp_path: Path) -> None:
    root = tmp_path / "jobs"
    for job, reward in (("old-a", 0.1), ("old-b", 0.9)):
        _trial(root, job, f"ed72__{job}", "opencode", reward=reward, model=("g", "m"), report=_report(reward))
    trials = [summarise.load_trial(d) for d in summarise.find_trial_dirs([root])]
    rows = [r for r in summarise.build_rows([t for t in trials if t]) if r.seed == "unknown"]
    assert sorted(r.mean for r in rows) == pytest.approx([0.1, 0.9])
    assert all(r.runs == 1 for r in rows)


def _agent(root: Path, job: str, trial: str, reward: float, reference: str = "r" * 64) -> None:
    _trial(root, job, trial, "opencode", reward=reward, model=("g", "m"), report=_report(reward))
    _manifest(root / job, reference=reference)


def test_completeness_is_scoped_to_each_plan_root(tmp_path: Path) -> None:
    # Yehor's #120 case: A and B each plan one `agent` attempt; A has two trials, B none.
    entry = {"job": "agent", "policy": "opencode", "model": "g/m", "seed": 42}
    a, b = tmp_path / "a", tmp_path / "b"
    for root in (a, b):
        summarise.manifest.write_plan(root, [entry])
    _agent(a, "agent", "ed72__a1", 0.5)
    _agent(a, "agent", "ed72__a2", 0.6)
    per_root = [
        (
            summarise.manifest.load_plan(r),
            [t for t in map(summarise.load_trial, summarise.find_trial_dirs([r])) if t],
            {},
        )
        for r in (a, b)
    ]
    comp = summarise.completeness_by_root(per_root)
    assert (comp.matched, len(comp.missing), len(comp.unplanned)) == (1, 1, 1)
    assert summarise.main([str(a), str(b), "--out", str(tmp_path / "s.md")]) == 4


def test_missing_in_one_root_is_not_filled_by_another_roots_extra_trial(tmp_path: Path) -> None:
    # The P2 case: A plans a reference it never ran; B plans one and ran two.
    ref = {"job": "reference", "policy": "oracle", "seed": 42}
    a, b = tmp_path / "a", tmp_path / "b"
    summarise.manifest.write_plan(a, [ref])
    summarise.manifest.write_plan(b, [ref])
    for name in ("ed72__b1", "ed72__b2"):
        _trial(b, "reference", name, "oracle", reward=0.9, report=_report(0.9))
    _manifest(b / "reference")
    per_root = [
        (
            summarise.manifest.load_plan(r),
            [t for t in map(summarise.load_trial, summarise.find_trial_dirs([r])) if t],
            {},
        )
        for r in (a, b)
    ]
    comp = summarise.completeness_by_root(per_root)
    assert (comp.matched, len(comp.missing), len(comp.unplanned)) == (1, 1, 1)
    assert comp.missing[0]["job"] == "reference"


def test_rows_and_gaps_split_on_reference_identity(tmp_path: Path) -> None:
    root = tmp_path / "jobs"
    for job, ref_hash, reward in (("ref-r", "r" * 64, 0.9), ("ref-q", "q" * 64, 0.7)):
        _trial(root, job, f"ed72__{job}", "oracle", reward=reward, report=_report(reward))
        _manifest(root / job, reference=ref_hash)
    _agent(root, "agent", "ed72__x", 0.5, reference="r" * 64)
    rows = summarise.build_rows(
        [t for t in map(summarise.load_trial, summarise.find_trial_dirs([root])) if t]
    )
    assert len([r for r in rows if r.policy != "opencode"]) == 2
    gaps = summarise._gaps(rows)
    assert len(gaps) == 1 and "reference rrrrrrrr" in gaps[0] and gaps[0].endswith("+0.400")
