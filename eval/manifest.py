"""Run identity for ED-72 eval jobs: seed, config, instruction, model, agent, Harbor version.

Harbor 0.26.0 records, per trial, `result.json` with `task_id.path` (a LocalTaskId, the path
given to `harbor run -p`), `task_checksum`, `config.task.path`, `config.agent` and
`agent_info`. It does not record the seed or config the hospital ran with: ED72_SEED lives in
`<task>/environment/docker-compose.yaml` and ED72_CONFIG (optional) is read by the hospital
server. The score object (CONTRACTS v1) has no seed either. So this module reads those facts
from the task dir used, and `write_manifest` freezes them into `<job dir>/manifest.json` at run
time, which is more reliable than re-deriving them later from a task dir that may have changed.

CLI (the runner calls it once per job, after `harbor run`):

    python eval/manifest.py JOB_DIR --task ed72 [--harbor-version 0.26.0] [--seed N]
"""

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

MANIFEST_NAME = "manifest.json"
DEFAULT_CONFIG = Path("environment/hospital/config/default.json")
DEFAULT_SEED = 42  # the bare `ed72` task, see environment/docker-compose.yaml

_SEED_ENV = re.compile(r"""ED72_SEED["']?\s*[:=]\s*["']?(\d+)""")
_CONFIG_ENV = re.compile(r"""ED72_CONFIG["']?\s*[:=]\s*["']?([^\s"']+)""")
_TASK_SEED = re.compile(r"^ed72-s(\d+)$")


def sha256_file(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def _read_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    data = json.loads(path.read_text())
    return data if isinstance(data, dict) else None


def resolve_task_dir(task_path: str | None, repo_root: Path) -> Path | None:
    if not task_path:
        return None
    p = Path(task_path)
    candidate = p if p.is_absolute() else repo_root / p
    return candidate if candidate.is_dir() else None


def task_facts(task_dir: Path) -> dict:
    """Seed, config path+hash and instruction hash read from a Harbor task dir. Missing means None."""
    compose_path = task_dir / "environment" / "docker-compose.yaml"
    compose = compose_path.read_text() if compose_path.is_file() else ""
    seed_match = _SEED_ENV.search(compose)
    if seed_match:
        seed: int | None = int(seed_match.group(1))
    elif task_dir.name == "ed72":
        seed = DEFAULT_SEED
    else:
        by_name = _TASK_SEED.match(task_dir.name)
        seed = int(by_name.group(1)) if by_name else None
    config_match = _CONFIG_ENV.search(compose)
    config_rel = Path(config_match.group(1)) if config_match else DEFAULT_CONFIG
    config_file = config_rel if config_rel.is_absolute() else task_dir / config_rel
    return {
        "task_path": str(task_dir),
        "seed": seed,
        "config_file": str(config_rel),
        "config_sha256": sha256_file(config_file),
        "instruction_sha256": sha256_file(task_dir / "instruction.md"),
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
    for path in (trial_dir / MANIFEST_NAME, trial_dir.parent / MANIFEST_NAME):
        data = _read_json(path)
        if data is not None:
            return data
    return None


def write_manifest(
    job_dir: Path,
    task_dir: Path,
    *,
    harbor_version: str | None = None,
    seed: int | None = None,
    model: str | None = None,
    agent: str | None = None,
) -> Path:
    """Write `<job_dir>/manifest.json`. `seed` overrides the task dir (e.g. a runner-set ED72_SEED)."""
    facts = task_facts(task_dir)
    if seed is not None:
        facts["seed"] = seed
    manifest = {
        **facts,
        "model": model,
        "agent": agent,
        "harbor_version": harbor_version,
        "source": "write_manifest",
    }
    job_dir.mkdir(parents=True, exist_ok=True)
    out = job_dir / MANIFEST_NAME
    out.write_text(json.dumps(manifest, indent=2) + "\n")
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("job_dir", type=Path)
    parser.add_argument("--task", type=Path, required=True, help="the task dir passed to harbor run -p")
    parser.add_argument("--harbor-version")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--model")
    parser.add_argument("--agent")
    args = parser.parse_args(argv)
    if not args.task.is_dir():
        print(f"manifest: task dir not found: {args.task}", file=sys.stderr)
        return 2
    out = write_manifest(
        args.job_dir,
        args.task,
        harbor_version=args.harbor_version,
        seed=args.seed,
        model=args.model,
        agent=args.agent,
    )
    print(f"manifest: wrote {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
