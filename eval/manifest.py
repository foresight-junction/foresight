"""Run identity for ED-72 eval jobs (manifest schema 2): seed, hashes, runtime, model, repeat.

Harbor 0.26.0 records, per trial, `result.json` with `task_id.path`, `task_checksum`,
`config.agent` and `agent_info`. It does not record the seed or config the hospital ran with:
ED72_SEED lives in `<task>/environment/docker-compose.yaml` and ED72_CONFIG (optional) is read by
the hospital server. So this module freezes those facts into `<job dir>/manifest.json` at run
time, which is more reliable than re-deriving them later from a task dir that may have changed.
`plan.json` in the jobs root lists every planned attempt before the first trial runs.

CLI (see eval/MANIFEST.md for the exact runner calls):

    python eval/manifest.py plan JOB_ROOT --task ed72 --entry job=agent,policy=opencode,model=M,repeats=3
    python eval/manifest.py write JOB_DIR --task ed72 --harbor-version 0.26.0 --repeat 1 --model M

Secrets: only the NAMES of agent options and env vars are stored, never values.
"""

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

MANIFEST_NAME = "manifest.json"
PLAN_NAME = "plan.json"
SCHEMA = 2
DEFAULT_CONFIG = Path("environment/hospital/config/default.json")
DEFAULT_SEED = 42  # the bare `ed72` task, see environment/docker-compose.yaml

_SEED_ENV = re.compile(r"""ED72_SEED["']?\s*[:=]\s*["']?(\d+)""")
# `${ED72_SEED:-42}` (host-overridable, PR #112)
_SEED_INTERP = re.compile(r"""ED72_SEED["']?\s*[:=]\s*["']?\$\{ED72_SEED:?-(\d+)\}""")
_CONFIG_ENV = re.compile(r"""ED72_CONFIG["']?\s*[:=]\s*["']?([^\s"']+)""")
_TASK_SEED = re.compile(r"^ed72-s(\d+)$")
_SKIP_DIRS = {"__pycache__", ".git", ".venv", "node_modules", "jobs", "logs", ".pytest_cache", ".ruff_cache"}


def sha256_file(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def tree_sha256(root: Path) -> str | None:
    """SHA-256 over sorted relative paths and file contents, skipping Harbor and Python artefacts."""
    if not root.is_dir():
        return None
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        rel = path.relative_to(root)
        if _SKIP_DIRS.intersection(rel.parts) or path.suffix == ".pyc":
            continue
        digest.update(rel.as_posix().encode() + b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def _read_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    data = json.loads(path.read_text())
    return data if isinstance(data, dict) else None


def _run(cmd: list[str], cwd: Path | None = None) -> str | None:
    if shutil.which(cmd[0]) is None:
        return None
    try:
        done = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=20, check=True)
    except (subprocess.SubprocessError, OSError):
        return None
    return done.stdout.strip()


def resolve_task_dir(task_path: str | None, repo_root: Path) -> Path | None:
    if not task_path:
        return None
    p = Path(task_path)
    candidate = p if p.is_absolute() else repo_root / p
    return candidate if candidate.is_dir() else None


def resolve_seed(task_dir: Path, compose: str, env: dict | None = None) -> tuple[int | None, str]:
    """Effective seed and its source.

    The host ED72_SEED only takes effect when the compose file interpolates it
    (`${ED72_SEED:-42}`). With a literal `ED72_SEED: "42"` Docker ignores the host value, so the
    literal wins and the source says so.
    """
    env = os.environ if env is None else env
    host = env.get("ED72_SEED", "").strip()
    interp = _SEED_INTERP.search(compose)
    if interp:
        if host.isdigit():
            return int(host), "host_env"
        return int(interp.group(1)), "compose_default"
    literal = _SEED_ENV.search(compose)
    if literal:
        return int(literal.group(1)), "compose_literal"
    # No seed line at all: compose has nothing to interpolate, so a host ED72_SEED never reaches the sim.
    by_name = _TASK_SEED.match(task_dir.name)
    if by_name:
        return int(by_name.group(1)), "task_name"
    if task_dir.name == "ed72":
        return DEFAULT_SEED, "compose_default"
    return None, "unknown"


def task_facts(task_dir: Path) -> dict:
    """Seed, config and instruction/task/reference hashes from a Harbor task dir. Missing means None."""
    compose_path = task_dir / "environment" / "docker-compose.yaml"
    compose = compose_path.read_text() if compose_path.is_file() else ""
    seed, seed_source = resolve_seed(task_dir, compose)
    config_match = _CONFIG_ENV.search(compose)
    config_rel = Path(config_match.group(1)) if config_match else DEFAULT_CONFIG
    config_file = config_rel if config_rel.is_absolute() else task_dir / config_rel
    return {
        "task_path": str(task_dir),
        "seed": seed,
        "seed_source": seed_source,
        "config_file": str(config_rel),
        "config_sha256": sha256_file(config_file),
        "instruction_sha256": sha256_file(task_dir / "instruction.md"),
        "task_sha256": tree_sha256(task_dir),
        "reference_sha256": tree_sha256(task_dir / "solution"),
    }


def source_facts(task_dir: Path) -> dict:
    commit = _run(["git", "rev-parse", "HEAD"], cwd=task_dir)
    status = _run(["git", "status", "--porcelain"], cwd=task_dir) if commit else None
    return {"source_commit": commit, "source_dirty": None if status is None else bool(status)}


def runtime_facts(harbor_version: str | None) -> dict:
    """Tool versions; None when a tool is unavailable, never a guess."""
    return {
        "harbor": harbor_version,
        "python": platform.python_version(),
        "docker": _run(["docker", "version", "--format", "{{.Client.Version}}"]),
    }


def trial_facts(trial_dir: Path) -> dict:
    """Facts Harbor recorded for one trial: task path, task checksum, agent, model."""
    result = _read_json(trial_dir / "result.json") or {}
    config = _read_json(trial_dir / "config.json") or {}
    task_id = result.get("task_id") or {}
    task_cfg = (result.get("config") or {}).get("task") or config.get("task") or {}
    agent_cfg = (result.get("config") or {}).get("agent") or (config.get("agent") or {})
    info = result.get("agent_info") or {}
    return {
        "task_path": task_id.get("path") or task_cfg.get("path"),
        "task_checksum": result.get("task_checksum"),
        "agent": info.get("name") or agent_cfg.get("name"),
        "model": agent_cfg.get("model_name"),
    }


def derive(trial_dir: Path, repo_root: Path) -> dict:
    """Best-effort manifest for a trial with no manifest.json: recorded facts, then task dir facts."""
    facts = trial_facts(trial_dir)
    task_dir = resolve_task_dir(facts["task_path"], repo_root)
    if task_dir is not None:
        facts = {**task_facts(task_dir), **{k: v for k, v in facts.items() if v is not None}}
        facts["task_path"] = str(task_dir)
    return {**facts, "source": "derived"}


def load_manifest(trial_dir: Path) -> dict | None:
    """Trial-level, then job-level manifest. Schema 1 manifests (no `schema` key) load unchanged."""
    for path in (trial_dir / MANIFEST_NAME, trial_dir.parent / MANIFEST_NAME):
        data = _read_json(path)
        if data is not None:
            return data
    return None


def _option_names(options: list[str] | None) -> list[str]:
    """`--ak version=1` and `--ae KEY=${KEY}` keep the name only: values may be keys."""
    return sorted({o.split("=", 1)[0] for o in options or [] if o})


def write_manifest(
    job_dir: Path,
    task_dir: Path,
    *,
    harbor_version: str | None = None,
    seed: int | None = None,
    model: str | None = None,
    agent: str | None = None,
    repeat: int | None = None,
    attempt: str | None = None,
    ak: list[str] | None = None,
    ae: list[str] | None = None,
    budget: dict | None = None,
) -> Path:
    """Write `<job_dir>/manifest.json` (schema 2). `seed` is an explicit runner override."""
    facts = task_facts(task_dir)
    if seed is not None:
        facts["seed"], facts["seed_source"] = seed, "host_env"
    manifest = {
        "schema": SCHEMA,
        **facts,
        **source_facts(task_dir),
        "model": model,
        "agent": agent,
        "agent_option_names": _option_names(ak),
        "agent_env_names": _option_names(ae),
        "repeat": repeat,
        "attempt": attempt or (f"{job_dir.name}-r{repeat}" if repeat is not None else job_dir.name),
        "budget": budget or {},
        "runtime": runtime_facts(harbor_version),
        "harbor_version": harbor_version,
        "written_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "source": "write_manifest",
    }
    job_dir.mkdir(parents=True, exist_ok=True)
    out = job_dir / MANIFEST_NAME
    out.write_text(json.dumps(manifest, indent=2) + "\n")
    return out


def write_plan(job_root: Path, entries: list[dict], *, force: bool = False) -> Path:
    """Write `<job_root>/plan.json` before any trial runs. Entry keys: job, policy, model, seed, repeat."""
    out = job_root / PLAN_NAME
    if out.exists() and not force:
        raise FileExistsError(f"{out} exists; a plan is written once, before the first trial")
    clean = []
    for e in entries:
        if not e.get("policy"):
            raise ValueError(f"plan entry needs a policy: {e}")
        clean.append(
            {
                "job": e.get("job"),
                "policy": e["policy"],
                "model": e.get("model") or "-",
                "seed": None if e.get("seed") is None else str(e["seed"]),
                "repeat": int(e.get("repeat") or 1),
            }
        )
    job_root.mkdir(parents=True, exist_ok=True)
    plan = {"schema": SCHEMA, "created_at": datetime.now(UTC).isoformat(timespec="seconds"), "entries": clean}
    out.write_text(json.dumps(plan, indent=2) + "\n")
    return out


def load_plan(job_root: Path) -> dict | None:
    return _read_json(job_root / PLAN_NAME)


def _parse_entry(text: str, default_seed: int | None) -> list[dict]:
    """`job=agent,policy=opencode,model=gemini/x,seed=42,repeats=3` becomes one entry per repeat."""
    fields = dict(part.split("=", 1) for part in text.split(","))
    repeats = int(fields.pop("repeats", fields.pop("repeat", 1)))
    if "seed" not in fields and default_seed is not None:
        fields["seed"] = str(default_seed)
    return [{**fields, "repeat": i} for i in range(1, repeats + 1)]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    plan = sub.add_parser("plan", help="write plan.json before the first harbor run")
    plan.add_argument("job_root", type=Path)
    plan.add_argument(
        "--entry", action="append", required=True, help="job=..,policy=..,model=..,seed=..,repeats=N"
    )
    plan.add_argument("--task", type=Path, help="task dir, to default each entry's seed")
    plan.add_argument("--force", action="store_true")
    write = sub.add_parser("write", help="write manifest.json after a harbor run")
    write.add_argument("job_dir", type=Path)
    write.add_argument("--task", type=Path, required=True)
    write.add_argument("--harbor-version")
    write.add_argument("--seed", type=int, help="explicit override; default is host ED72_SEED, then compose")
    write.add_argument("--model")
    write.add_argument("--agent")
    write.add_argument("--repeat", type=int)
    write.add_argument("--attempt")
    write.add_argument("--ak", action="append", help="agent kwarg NAME[=value]; only the name is stored")
    write.add_argument("--ae", action="append", help="agent env NAME[=value]; only the name is stored")
    write.add_argument("--budget", action="append", help="NAME=value, e.g. max_cost_usd=5")
    return parser


def main(argv: list[str] | None = None) -> int:
    args_in = list(sys.argv[1:] if argv is None else argv)
    # Schema 1 call `manifest.py JOB_DIR --task T` still means `write`.
    if args_in and args_in[0] not in ("plan", "write", "-h", "--help"):
        args_in.insert(0, "write")
    args = _build_parser().parse_args(args_in)
    if args.task is not None and not args.task.is_dir():
        print(f"manifest: task dir not found: {args.task}", file=sys.stderr)
        return 2
    if args.cmd == "plan":
        default_seed = task_facts(args.task)["seed"] if args.task else None
        entries = [e for text in args.entry for e in _parse_entry(text, default_seed)]
        try:
            out = write_plan(args.job_root, entries, force=args.force)
        except (FileExistsError, ValueError) as exc:
            print(f"manifest: {exc}", file=sys.stderr)
            return 2
        print(f"manifest: wrote {out} ({len(entries)} planned attempts)", file=sys.stderr)
        return 0
    budget = dict(b.split("=", 1) for b in args.budget or [])
    out = write_manifest(
        args.job_dir,
        args.task,
        harbor_version=args.harbor_version,
        seed=args.seed,
        model=args.model,
        agent=args.agent,
        repeat=args.repeat,
        attempt=args.attempt,
        ak=args.ak,
        ae=args.ae,
        budget=budget,
    )
    print(f"manifest: wrote {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
