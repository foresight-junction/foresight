import importlib.util
import json
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve().parent


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


summarise = _load("summarise_for_manifest", _HERE.parent / "summarise.py")
helpers = _load("test_summarise_helpers", _HERE / "test_summarise.py")
manifest = summarise.manifest


@pytest.fixture(autouse=True)
def _hermetic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(summarise, "REPO_ROOT", tmp_path / "no-repo")
    monkeypatch.delenv("ED72_SEED", raising=False)


def _task(root: Path, seed_line: str, name: str = "ed72") -> Path:
    # MOCK: minimal Harbor task dir with the files manifest.py hashes.
    task = root / name
    (task / "environment" / "hospital" / "config").mkdir(parents=True)
    (task / "environment" / "docker-compose.yaml").write_text(
        f"services:\n  hospital:\n    environment:\n      {seed_line}\n"
    )
    (task / "environment" / "hospital" / "config" / "default.json").write_text("{}")
    (task / "instruction.md").write_text("play")
    (task / "solution").mkdir()
    (task / "solution" / "policy.py").write_text("print(1)")
    return task


def _seed(task: Path) -> tuple[int | None, str]:
    facts = manifest.task_facts(task)
    return facts["seed"], facts["seed_source"]


def test_seed_host_override_default_and_literal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    interp = _task(tmp_path / "a", 'ED72_SEED: "${ED72_SEED:-42}"')
    literal = _task(tmp_path / "b", 'ED72_SEED: "42"')
    assert _seed(interp) == (42, "compose_default")
    assert _seed(literal) == (42, "compose_literal")
    monkeypatch.setenv("ED72_SEED", "7")
    assert _seed(interp) == (7, "host_env")
    # A literal compose seed ignores the host variable in Docker, so the manifest must say 42.
    assert _seed(literal) == (42, "compose_literal")
    # No seed line: compose cannot interpolate the host value, so the folder name decides.
    assert _seed(_task(tmp_path / "c", "X: 1", name="ed72-s9")) == (9, "task_name")
    monkeypatch.delenv("ED72_SEED")
    assert _seed(_task(tmp_path / "d", "X: 1", name="ed72-s9")) == (9, "task_name")
    assert _seed(_task(tmp_path / "e", "X: 1", name="other")) == (None, "unknown")


def test_reference_hash_tracks_solution_only(tmp_path: Path) -> None:
    task = _task(tmp_path, 'ED72_SEED: "1"')
    before = manifest.task_facts(task)
    (task / "solution" / "policy.py").write_text("print(2)")
    after = manifest.task_facts(task)
    assert before["reference_sha256"] != after["reference_sha256"]
    assert before["task_sha256"] != after["task_sha256"]
    assert before["instruction_sha256"] == after["instruction_sha256"]
    (task / "solution" / "__pycache__").mkdir()
    (task / "solution" / "__pycache__" / "x.pyc").write_text("junk")
    assert manifest.task_facts(task)["reference_sha256"] == after["reference_sha256"]


def test_manifest_v2_fields_and_no_secret_values(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "secret123")
    task = _task(tmp_path, 'ED72_SEED: "${ED72_SEED:-42}"')
    job = tmp_path / "job"
    out = manifest.write_manifest(
        job,
        task,
        harbor_version="0.26.0",
        model="gemini/m",
        agent="opencode",
        repeat=2,
        ak=["version=1.19.5"],
        ae=["GOOGLE_GENERATIVE_AI_API_KEY=secret123"],
        budget={"max_cost_usd": "5"},
    )
    text = out.read_text()
    assert "secret123" not in text
    data = json.loads(text)
    assert data["schema"] == 2 and data["repeat"] == 2 and data["attempt"] == "job-r2"
    assert data["agent_env_names"] == ["GOOGLE_GENERATIVE_AI_API_KEY"]
    assert data["agent_option_names"] == ["version"]
    assert data["budget"] == {"max_cost_usd": "5"}
    assert data["runtime"]["harbor"] == "0.26.0" and data["runtime"]["python"]
    assert data["reference_sha256"] and data["task_sha256"] and "source_commit" in data


def test_cli_plan_then_write(tmp_path: Path) -> None:
    task = _task(tmp_path, 'ED72_SEED: "${ED72_SEED:-42}"')
    root = tmp_path / "jobs"
    args = [
        "plan",
        str(root),
        "--task",
        str(task),
        "--entry",
        "job=agent,policy=opencode,model=g/m,repeats=3",
    ]
    assert manifest.main(args) == 0
    plan = json.loads((root / "plan.json").read_text())
    assert [(e["repeat"], e["seed"]) for e in plan["entries"]] == [(1, "42"), (2, "42"), (3, "42")]
    assert manifest.main(args) == 2  # a plan is written once
    assert manifest.main(["write", str(root / "agent"), "--task", str(task), "--repeat", "1"]) == 0


def test_v1_manifest_still_loads(tmp_path: Path) -> None:
    root = tmp_path / "jobs"
    d = helpers._trial(root, "j", "ed72__a", "oracle", reward=1.0, report=helpers._report(1.0))
    (root / "j" / "manifest.json").write_text(
        json.dumps({"seed": 3, "config_sha256": "c" * 64, "instruction_sha256": "i" * 64})
    )
    trial = summarise.load_trial(d)
    assert trial is not None and (trial.seed, trial.config) == ("3", "cccccccc")


def _plan(root: Path, entries: list[dict]) -> dict:
    manifest.write_plan(root, entries)
    return manifest.load_plan(root)


def _mk(root: Path, job: str, agent: str, reward: float | None, suffix: str = "", **kw) -> None:
    model = ("g", "m") if agent == "opencode" else None
    helpers._trial(root, job, f"ed72__{job}{suffix}", agent, reward=reward, model=model, **kw)
    (root / job / "manifest.json").write_text(json.dumps({"seed": 42}))


def _entries() -> list[dict]:
    agent = {"job": "agent", "policy": "opencode", "model": "g/m", "seed": 42}
    return [
        {"job": "reference", "policy": "oracle", "seed": 42},
        *[{**agent, "repeat": i} for i in (1, 2, 3, 4)],
    ]


def test_completeness_missing_failed_timeout_unplanned(tmp_path: Path) -> None:
    root = tmp_path / "jobs"
    plan = _plan(root, _entries())
    _mk(root, "reference", "oracle", 0.9, report=helpers._report(0.9))
    _mk(root, "agent", "opencode", 0.5, "a", report=helpers._report(0.5))
    _mk(root, "agent", "opencode", 0.1, "b", report=helpers._report(0.1, ended="timeout"))
    _mk(root, "agent", "opencode", None, "c", exception="AgentTimeoutError")
    _mk(root, "extra", "nop", 0.0, report=helpers._report(0.0))
    trials = [summarise.load_trial(d) for d in summarise.find_trial_dirs([root])]
    comp = summarise.completeness(plan, [t for t in trials if t])
    assert (comp.planned, comp.matched) == (5, 4)
    assert [e["repeat"] for e in comp.missing] == [4]
    assert [t.name for t in comp.failed] == ["ed72__agentc"]
    assert [t.name for t in comp.timed_out] == ["ed72__agentb"]
    assert [t.job for t in comp.unplanned] == ["extra"]
    assert comp.incomplete


def test_summarise_exits_nonzero_when_incomplete(tmp_path: Path) -> None:
    root = tmp_path / "jobs"
    _plan(root, _entries()[:2])
    _mk(root, "reference", "oracle", 0.9, report=helpers._report(0.9))
    out = tmp_path / "s.md"
    assert summarise.main([str(root), "--out", str(out)]) == 4
    text = out.read_text()
    assert "## Completeness" in text and "INCOMPLETE" in text and "Missing" in text
    assert summarise.main([str(root), "--out", str(out), "--allow-incomplete"]) == 0


def test_summarise_complete_plan_exits_zero(tmp_path: Path) -> None:
    root = tmp_path / "jobs"
    _plan(root, _entries()[:1])
    _mk(root, "reference", "oracle", 0.9, report=helpers._report(0.9))
    assert summarise.main([str(root), "--out", str(tmp_path / "s.md")]) == 0


def test_plan_with_no_finished_trials_is_incomplete_not_empty_error(tmp_path: Path) -> None:
    root = tmp_path / "jobs"
    _plan(root, _entries()[:1])
    assert summarise.main([str(root), "--out", str(tmp_path / "s.md")]) == 4


def test_host_seed_ignored_when_compose_declares_no_seed(tmp_path: Path) -> None:
    assert manifest.resolve_seed(tmp_path / "custom", "services: {}\n", env={"ED72_SEED": "7"}) == (
        None,
        "unknown",
    )
    assert manifest.resolve_seed(tmp_path / "ed72-s2", "", env={"ED72_SEED": "7"}) == (2, "task_name")


def test_timeout_with_harbor_exception_is_listed_and_still_failed(tmp_path: Path) -> None:
    # #93: any agent exception fails the evaluation, even when a reward exists.
    root = tmp_path / "jobs"
    plan = _plan(root, _entries()[1:2])
    _mk(
        root,
        "agent",
        "opencode",
        0.4,
        "t",
        report=helpers._report(0.4, ended="timeout"),
        exception="AgentTimeoutError",
    )
    trials = [summarise.load_trial(d) for d in summarise.find_trial_dirs([root])]
    comp = summarise.completeness(plan, [t for t in trials if t])
    assert [t.name for t in comp.failed] == ["ed72__agentt"] == [t.name for t in comp.timed_out]
    assert summarise.main([str(root), "--out", str(tmp_path / "s.md")]) == 4


def test_plans_from_several_roots_are_merged(tmp_path: Path) -> None:
    a, b = tmp_path / "a", tmp_path / "b"
    _plan(a, _entries()[:1])
    _plan(b, _entries()[1:2])
    _mk(a, "reference", "oracle", 0.9, report=helpers._report(0.9))
    out = tmp_path / "s.md"
    assert summarise.main([str(a), str(b), "--out", str(out)]) == 4
    assert "Planned 2" in out.read_text()


def test_plan_freezes_identity_and_write_flags_drift(tmp_path: Path) -> None:
    task = _task(tmp_path, 'ED72_SEED: "42"')
    root = tmp_path / "jobs"
    manifest.write_plan(
        root, [{"job": "agent", "policy": "opencode", "model": "g/m", "seed": 42}], task_dir=task
    )
    frozen = manifest.load_plan(root)["identity"]
    assert frozen["reference_sha256"] and frozen["instruction_sha256"]

    manifest.write_manifest(root / "same", task)
    same = json.loads((root / "same" / "manifest.json").read_text())
    assert same["identity_source"] == "plan" and same["identity_drift"] is False

    (task / "solution" / "policy.py").write_text("print(2)")  # the reference changes mid-campaign
    manifest.write_manifest(root / "agent", task)
    data = json.loads((root / "agent" / "manifest.json").read_text())
    assert data["identity_drift"] is True and data["drifted_fields"] == ["task_sha256", "reference_sha256"]
    assert data["reference_sha256"] == frozen["reference_sha256"] != data["observed"]["reference_sha256"]

    helpers._trial(
        root, "agent", "ed72__agent", "opencode", reward=0.5, model=("g", "m"), report=helpers._report(0.5)
    )
    comp = summarise.completeness_by_root(
        [
            (
                manifest.load_plan(root),
                [t for t in map(summarise.load_trial, summarise.find_trial_dirs([root])) if t],
                {},
            )
        ]
    )
    assert [t.name for t in comp.drifted] == ["ed72__agent"] and comp.incomplete


def test_exit_code_flag_and_file_and_crash_counts_as_failed(tmp_path: Path) -> None:
    task = _task(tmp_path, 'ED72_SEED: "42"')
    root = tmp_path / "jobs"
    manifest.write_plan(
        root, [{"job": "agent", "policy": "opencode", "model": "g/m", "seed": 42}], task_dir=task
    )
    (root / "agent").mkdir(parents=True)
    (root / "agent" / manifest.EXIT_CODE_FILE).write_text("137\n")
    manifest.write_manifest(root / "agent", task)
    assert json.loads((root / "agent" / "manifest.json").read_text())["harbor_exit_code"] == 137
    manifest.write_manifest(root / "other", task, exit_code=0)
    assert json.loads((root / "other" / "manifest.json").read_text())["harbor_exit_code"] == 0
    assert summarise.main([str(root), "--out", str(tmp_path / "s.md")]) == 4
    assert "crashed 1" in (tmp_path / "s.md").read_text()
