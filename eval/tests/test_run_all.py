import json
import os
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
STOP_EARLY = "ed72_baselines.harbor_agent:StopEarlyAgent"
REQUIRED_FILES = (
    "ed72/task.toml",
    "ed72/solution/solve.sh",
    "ed72/solution/reference.py",
    "ed72/solution/policy.py",
    "ed72/environment/ward",
    "eval/baselines/ed72_baselines/harbor_agent.py",
    "eval/baselines/ed72_baselines/ward_driver.py",
    "eval/manifest.py",
    "eval/summarise.py",
)

# MOCK: all external commands are replaced inside a temporary repo, enabled by USE_MOCKS=1.
MOCK_TOOL = r"""#!/usr/bin/env bash
set -eu
[ "${USE_MOCKS:-}" = 1 ] || exit 99
tool="${0##*/}"
printf '%s\t' "$tool" "$@" >> "${MOCK_CALLS:-calls.tsv}"
printf '\n' >> "${MOCK_CALLS:-calls.tsv}"
case "$tool" in
  date) echo 20261119-090000; exit 0 ;;
  docker) exit 0 ;;
  uv)
    script="" action="" target="" out=""
    args=("$@")
    for ((i=0; i<${#args[@]}; i++)); do
      case "${args[i]}" in
        */manifest.py|*/summarise.py) script="${args[i]}"; action="${args[i+1]}" ;;
        plan|write) target="${args[i+1]}" ;;
        --out) out="${args[i+1]}" ;;
      esac
    done
    if [[ "$script" = */manifest.py ]]; then
      if [ "$action" = plan ] && [ -f fail-plan ]; then exit 29; fi
      if [ "$action" = write ] && [ -f fail-manifest ]; then exit 31; fi
      filename=manifest.json
      if [ "$action" = plan ]; then filename=plan.json; fi
      printf '{"seed": "%s"}\n' "${ED72_SEED:-3101}" > "$target/$filename"
    fi
    if [[ "$script" = */summarise.py ]]; then
      if [ -f fail-summary-without-report ]; then exit 1; fi
      if [ -f crash-during-summary ]; then
        printf '# Mock evaluation' > "$out"
        exit 1
      fi
      printf '# Mock evaluation report\n\nSeed: %s\n' "${ED72_SEED:-3101}" > "$out"
      if [ -f fail-summary ]; then exit "$(cat fail-summary)"; fi
      if [ -f fail-baseline-summary ] && [ "${action##*/}" = "$(cat fail-baseline-summary)" ]; then
        exit 3
      fi
    fi
    exit 0 ;;
esac
agent="" job="" output="" dry=0
args=("$@")
for ((i=0; i<${#args[@]}; i++)); do
  case "${args[i]}" in
    -a|--agent) agent="${args[i+1]}" ;;
    --job-name) job="${args[i+1]}" ;;
    -o) output="${args[i+1]}" ;;
    --dry-run) dry=1 ;;
    --version) echo 'Harbor 0.26.0'; exit 0 ;;
  esac
done
if [ "$agent" = ed72_baselines.harbor_agent:StopEarlyAgent ]; then
  printf '%s\n' "${PYTHONPATH:-}" >> pythonpaths.txt
fi
if [ "$dry" = 1 ] && [ -f fail-preflight ] && [ "$agent" = "$(cat fail-preflight)" ]; then
  exit 17
fi
if [ "$dry" = 0 ]; then
  if [ -f fail-job ] && [ "$job" = "$(cat fail-job)" ]; then exit 23; fi
  mkdir -p "$output/$job"
  printf '%s\n' "${ED72_SEED:-3101}" > "$output/$job/trial-seed.txt"
fi
"""


@dataclass
class Runner:
    root: Path
    bash: str
    env: dict[str, str]

    def run(self, mode: str = "baselines", **env: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                self.bash,
                "-c",
                'export PATH="$PWD/mock-bin:$PATH"; exec bash eval/run_all.sh "$@"',
                "test",
                mode,
            ],
            check=False,
            cwd=self.root,
            env=self.env | env,
            capture_output=True,
            text=True,
            timeout=30,
        )

    def calls(self) -> list[list[str]]:
        path = self.root / "calls.tsv"
        return (
            [line.rstrip("\t").split("\t") for line in path.read_text().splitlines()] if path.exists() else []
        )

    def harbor_calls(self, *, dry: bool) -> list[list[str]]:
        return [
            call
            for call in self.calls()
            if call[0] in {"uvx", "harbor"} and "run" in call and ("--dry-run" in call) == dry
        ]

    def script_calls(self, name: str) -> list[list[str]]:
        return [
            call for call in self.calls() if call[0] == "uv" and any(arg.endswith(f"/{name}") for arg in call)
        ]

    def manifest_calls(self, action: str) -> list[list[str]]:
        return [call for call in self.script_calls("manifest.py") if action in call]


@pytest.fixture
def runner(tmp_path: Path) -> Runner:
    git_bash = Path("C:/Program Files/Git/bin/bash.exe")
    bash = str(git_bash) if os.name == "nt" and git_bash.exists() else shutil.which("bash")
    if bash is None:
        pytest.skip("runner integration tests need bash")
    root = tmp_path / "repo with spaces"
    (root / "eval").mkdir(parents=True)
    (root / "eval/run_all.sh").write_text((REPO / "eval/run_all.sh").read_text(), newline="\n")
    for name in REQUIRED_FILES:
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("# MOCK: existence-only runner prerequisite, enabled by USE_MOCKS.\n")
    tools = root / "mock-bin"
    tools.mkdir()
    for name in ("date", "docker", "uv", "uvx", "harbor"):
        tool = tools / name
        tool.write_text(MOCK_TOOL, newline="\n")
        tool.chmod(0o755)
    env = {
        key: value
        for key, value in os.environ.items()
        if key
        not in {
            "HARBOR",
            "ED72_MODEL",
            "ED72_SEED",
            "GEMINI_API_KEY",
            "OPENAI_API_KEY",
            "ANTHROPIC_API_KEY",
            "PYTHONPATH",
            "MOCK_CALLS",
        }
    }
    env["USE_MOCKS"] = "1"
    return Runner(root, bash, env)


def _option(call: list[str], name: str) -> str:
    return call[call.index(name) + 1]


@pytest.mark.parametrize("missing", REQUIRED_FILES)
def test_missing_prerequisite_fails_before_running_any_jobs(runner: Runner, missing: str) -> None:
    (runner.root / missing).unlink()
    result = runner.run()
    assert result.returncode != 0, result.stdout + result.stderr
    assert not runner.harbor_calls(dry=False)
    assert Path(missing).name in result.stderr
    assert not (runner.root / "eval/results").exists()


@pytest.mark.parametrize("agent", ["oracle", "nop", STOP_EARLY, "opencode"])
def test_rejected_harbor_configuration_fails_before_any_job(runner: Runner, agent: str) -> None:
    (runner.root / "fail-preflight").write_text(agent)
    runner.env.update(ED72_MODEL="gemini/gemini-3.8-flash", GEMINI_API_KEY="mock")
    result = runner.run("all")
    assert result.returncode != 0, result.stdout + result.stderr
    assert not runner.harbor_calls(dry=False)


@pytest.mark.parametrize("model", [None, "gemini/gemini-3.8-flash", "unsupported/model"])
def test_missing_or_unsupported_model_credentials_fail_before_jobs(runner: Runner, model: str | None) -> None:
    if model is not None:
        runner.env["ED72_MODEL"] = model
    result = runner.run("all")
    assert result.returncode != 0, result.stdout + result.stderr
    assert not runner.harbor_calls(dry=False)


def test_baselines_preflight_and_run_all_three_policies_without_keys(runner: Runner) -> None:
    result = runner.run()
    assert result.returncode == 0, result.stdout + result.stderr
    preflight = runner.harbor_calls(dry=True)
    jobs = runner.harbor_calls(dry=False)
    assert [_option(call, "-a") for call in preflight] == ["oracle", "nop", STOP_EARLY]
    assert [_option(call, "--job-name") for call in jobs] == ["reference", "do-nothing", "stop-early"]
    calls = runner.calls()
    assert max(calls.index(call) for call in preflight) < min(calls.index(call) for call in jobs)
    pythonpaths = (runner.root / "pythonpaths.txt").read_text().splitlines()
    assert len(pythonpaths) == 2
    assert all(Path(value.split(os.pathsep)[0]) == runner.root / "eval/baselines" for value in pythonpaths)
    assert "SKIP" not in result.stderr


@pytest.mark.parametrize("provider", ["gemini", "google"])
def test_gemini_mapping_and_pinned_versions_are_forwarded(runner: Runner, provider: str) -> None:
    runner.env.update(ED72_MODEL=f"{provider}/gemini-3.8-flash", GEMINI_API_KEY="mock")
    (runner.root / ".env").write_text("GEMINI_API_KEY=\n")
    result = runner.run("all")
    assert result.returncode == 0, result.stdout + result.stderr
    for calls in (runner.harbor_calls(dry=True), runner.harbor_calls(dry=False)):
        agent = next(call for call in calls if _option(call, "-a") == "opencode")
        assert _option(agent, "-m") == f"{provider}/gemini-3.8-flash"
        assert _option(agent, "--api-key-name") == "GEMINI_API_KEY"
        assert _option(agent, "--ae") == "GOOGLE_GENERATIVE_AI_API_KEY=${GEMINI_API_KEY}"
        assert _option(agent, "--ak") == "version=1.19.5"
        assert "harbor==0.26.0" in agent
        assert "mock" not in agent
    agent_job = runner.harbor_calls(dry=False)[-1]
    assert _option(agent_job, "-k") == "3" and _option(agent_job, "-n") == "3"


@pytest.mark.parametrize(("failure", "value"), [("job", "do-nothing"), ("summary", "3"), ("summary", "4")])
def test_failed_job_or_summary_makes_runner_fail(runner: Runner, failure: str, value: str) -> None:
    (runner.root / f"fail-{failure}").write_text(value)
    result = runner.run()
    assert result.returncode != 0, result.stdout + result.stderr
    assert len(runner.harbor_calls(dry=False)) == 3
    assert any(
        call[0] == "uv" and any(arg.endswith("/summarise.py") for arg in call) for call in runner.calls()
    )
    assert ("do-nothing" if failure == "job" else "summary") in result.stderr
    (report,) = runner.root.glob("eval/results/jobs/*/summary.md")
    assert f"{report.parent.name}/summary.md" in result.stdout
    assert (runner.root / "eval/results/summary.md").read_bytes() == report.read_bytes()


@pytest.mark.parametrize("failure", ["fail-summary-without-report", "crash-during-summary"])
def test_missing_or_truncated_report_preserves_previous_summary(runner: Runner, failure: str) -> None:
    latest = runner.root / "eval/results/summary.md"
    latest.parent.mkdir()
    latest.write_text("Previous report\n")
    (runner.root / failure).touch()
    result = runner.run()
    assert result.returncode == 1, result.stdout + result.stderr
    assert "failed: summary" in result.stderr
    assert latest.read_text() == "Previous report\n"
    reports = list(runner.root.glob("eval/results/jobs/*/summary.md"))
    if failure == "crash-during-summary":
        (report,) = reports
        assert report.read_text() == "# Mock evaluation"
    else:
        assert not reports


def test_same_second_runs_keep_seed_artifacts_and_reports_separate(runner: Runner) -> None:
    seeds = (3101, 3102)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(runner.run, ED72_SEED=str(seed), MOCK_CALLS=f"calls-{seed}.tsv") for seed in seeds
        ]
        results = [future.result() for future in futures]

    job_roots = sorted(runner.root.glob("eval/results/jobs/20261119-090000-*"))
    assert len(job_roots) == 2
    reports = {}
    for job_root in job_roots:
        seed = int(json.loads((job_root / "plan.json").read_text())["seed"])
        assert seed not in reports
        for name in ("reference", "do-nothing", "stop-early"):
            job = job_root / name
            assert (job / "trial-seed.txt").read_text().strip() == str(seed)
            assert json.loads((job / "manifest.json").read_text())["seed"] == str(seed)
            assert (job / "harbor-exit-code.txt").read_text().strip() == "0"
        report = job_root / "summary.md"
        reports[seed] = report.read_bytes()
        assert reports[seed] == f"# Mock evaluation report\n\nSeed: {seed}\n".encode()
        result = results[seeds.index(seed)]
        assert result.returncode == 0, result.stdout + result.stderr
        assert job_root.name + "/summary.md" in result.stdout

    assert set(reports) == set(seeds)
    assert (runner.root / "eval/results/summary.md").read_bytes() in reports.values()
    assert not list(runner.root.glob("eval/results/.summary-*"))


@pytest.mark.parametrize("mode", ["baselines", "all"])
def test_manifest_plan_precedes_jobs_and_covers_every_planned_repeat(runner: Runner, mode: str) -> None:
    runner.env.update(ED72_MODEL="gemini/gemini-3.8-flash", GEMINI_API_KEY="mock")
    result = runner.run(mode)
    assert result.returncode == 0, result.stdout + result.stderr
    (plan,) = runner.manifest_calls("plan")
    entries = [plan[index + 1] for index, arg in enumerate(plan) if arg == "--entry"]
    expected = [
        "job=reference,policy=oracle",
        "job=do-nothing,policy=nop",
        "job=stop-early,policy=stop_early",
    ]
    if mode == "all":
        expected.append("job=agent,policy=opencode,model=gemini/gemini-3.8-flash,repeats=3")
    assert entries == expected
    calls = runner.calls()
    assert calls.index(plan) < min(calls.index(call) for call in runner.harbor_calls(dry=False))


def test_manifest_plan_failure_prevents_harbor_jobs(runner: Runner) -> None:
    (runner.root / "fail-plan").touch()
    result = runner.run()
    assert result.returncode != 0, result.stdout + result.stderr
    assert len(runner.manifest_calls("plan")) == 1
    assert not runner.harbor_calls(dry=False)
    assert "planning failed" in result.stderr


def test_manifest_written_after_each_job_even_when_harbor_fails(runner: Runner) -> None:
    (runner.root / "fail-job").write_text("do-nothing")
    result = runner.run()
    assert result.returncode != 0, result.stdout + result.stderr
    writes = runner.manifest_calls("write")
    assert [_option(call, "--agent") for call in writes] == ["oracle", "nop", "stop_early"]
    calls = runner.calls()
    for job, write in zip(runner.harbor_calls(dry=False), writes, strict=True):
        name = _option(job, "--job-name")
        assert calls.index(job) < calls.index(write)
        assert write[write.index("write") + 1].endswith(f"/{name}")
        assert _option(write, "--repeat") == "1"
        assert _option(write, "--harbor-version") == "Harbor 0.26.0"
        (exit_file,) = runner.root.glob(f"eval/results/jobs/*/{name}/harbor-exit-code.txt")
        assert exit_file.read_text().strip() == ("23" if name == "do-nothing" else "0")


def test_manifest_write_failure_makes_runner_fail(runner: Runner) -> None:
    (runner.root / "fail-manifest").touch()
    result = runner.run()
    assert result.returncode != 0, result.stdout + result.stderr
    assert len(runner.manifest_calls("write")) == 3
    assert len(runner.harbor_calls(dry=False)) == 3
    assert len(runner.script_calls("summarise.py")) == 1
    assert "manifest" in result.stderr


@pytest.mark.parametrize("job", ["reference", "do-nothing", "stop-early"])
@pytest.mark.parametrize("failure", ["job", "baseline-summary"])
def test_baseline_failure_blocks_paid_runs_and_preserves_model_plan(
    runner: Runner, job: str, failure: str
) -> None:
    runner.env.update(ED72_MODEL="gemini/gemini-3.8-flash", GEMINI_API_KEY="mock")
    (runner.root / f"fail-{failure}").write_text(job)
    result = runner.run("all")
    assert result.returncode != 0, result.stdout + result.stderr
    jobs = runner.harbor_calls(dry=False)
    assert [_option(call, "--job-name") for call in jobs] == ["reference", "do-nothing", "stop-early"]
    (plan,) = runner.manifest_calls("plan")
    assert "job=agent,policy=opencode,model=gemini/gemini-3.8-flash,repeats=3" in plan
    summaries = runner.script_calls("summarise.py")
    assert len(summaries) == 4
    final = summaries[-1]
    script_index = next(index for index, arg in enumerate(final) if arg.endswith("/summarise.py"))
    assert final[script_index + 1] == plan[plan.index("plan") + 1]
    assert _option(final, "--out") == f"{final[script_index + 1]}/summary.md"
    assert "no model runs started" in result.stderr
