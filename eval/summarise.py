"""Summarise Harbor job directories into eval/results/summary.md.

Harbor 0.25.0 layout, checked against harbor/models/trial/paths.py and real jobs from the #21 spike:

    <jobs>/<job_name>/result.json                        job totals (not read here)
    <jobs>/<job_name>/<trial>/config.json                has "trial_name"
    <jobs>/<job_name>/<trial>/result.json                TrialResult, written when the trial ends
    <jobs>/<job_name>/<trial>/verifier/reward.txt        reward number
    <jobs>/<job_name>/<trial>/verifier/score_full.json   score object (CONTRACTS v1)
    <jobs>/<job_name>/<trial>/artifacts/evidence/report.json   same object, collected from hospital

Usage: python eval/summarise.py [JOBS_DIR ...] [--out PATH]
"""

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path
from statistics import mean

sys.path.insert(0, str(Path(__file__).resolve().parent))
import manifest

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_JOBS = REPO_ROOT / "eval" / "results" / "jobs"
DEFAULT_OUT = REPO_ROOT / "eval" / "results" / "summary.md"

POLICY_LABELS = {"oracle": "reference (oracle)", "nop": "do-nothing (nop)"}
COMPONENTS = ("O", "T", "W", "B")
UNKNOWN = "unknown"


@dataclass
class Trial:
    job: str
    name: str
    policy: str
    model: str
    seed: str
    config: str
    instruction: str
    reward: float | None
    error: str | None
    report: dict | None
    task: str = UNKNOWN
    reference: str = UNKNOWN
    source: str = UNKNOWN
    drift: tuple[str, ...] = ()


def find_trial_dirs(roots: list[Path]) -> list[Path]:
    found: set[Path] = set()
    for root in roots:
        for config in root.rglob("config.json"):
            data = manifest.read_json_object(config)
            if data is not None and "trial_name" in data:
                found.add(config.parent)
    return sorted(found)


def _report(trial_dir: Path) -> dict | None:
    for path in (
        trial_dir / "verifier" / "score_full.json",
        trial_dir / "artifacts" / "evidence" / "report.json",
    ):
        data = manifest.read_json_object(path)
        if data is not None:
            return data
    for path in sorted((trial_dir / "artifacts").rglob("report.json")):
        data = manifest.read_json_object(path)
        if data is not None:
            return data
    return None


def _reward(result: dict, trial_dir: Path) -> float | None:
    verifier = result.get("verifier_result")
    if verifier is not None and not isinstance(verifier, dict):
        raise ValueError("invalid verifier_result in result.json")
    rewards = verifier.get("rewards") if verifier is not None else None
    if rewards is not None and not isinstance(rewards, dict):
        raise ValueError("invalid verifier rewards in result.json")
    if rewards is not None and "reward" in rewards:
        value = rewards["reward"]
        source = "result.json"
    else:
        reward_txt = trial_dir / "verifier" / "reward.txt"
        if not reward_txt.is_file():
            return None
        source = "verifier/reward.txt"
        try:
            value = reward_txt.read_text().strip()
        except (OSError, UnicodeError) as exc:
            raise ValueError(f"could not read reward from {source}: {exc}") from exc

    error = f"invalid reward in {source} (expected a finite number in [0, 1])"
    try:
        reward = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(error) from exc
    if isinstance(value, bool) or not 0.0 <= reward <= 1.0:
        raise ValueError(error)
    return reward


def _model(result: dict) -> str:
    info = (result.get("agent_info") or {}).get("model_info")
    if info and info.get("name"):
        return f"{info['provider']}/{info['name']}" if info.get("provider") else info["name"]
    agent = (result.get("config") or {}).get("agent") or {}
    return agent.get("model_name") or "-"


def _policy(result: dict) -> str:
    name = result["agent_info"]["name"]
    return POLICY_LABELS.get(name, name)


def _identity(trial_dir: Path, report: dict | None) -> dict[str, str]:
    """Seed, config hash and instruction hash of a trial; `unknown` when no source records them.

    Order: seed in the report (CONTRACTS v1 has none yet), then the job's manifest.json, then
    what manifest.derive() can read from the task dir Harbor recorded for the trial.
    """
    facts = manifest.load_manifest(trial_dir) or manifest.derive(trial_dir, REPO_ROOT)
    seed = report["seed"] if report and "seed" in report else facts.get("seed")

    def short(digest: str | None) -> str:
        return digest[:8] if digest else UNKNOWN

    commit = facts.get("source_commit")
    source = UNKNOWN if not commit else commit[:8] + ("+dirty" if facts.get("source_dirty") else "")
    drift = facts.get("drifted_fields") or (["identity"] if facts.get("identity_drift") else [])
    return {
        "seed": UNKNOWN if seed is None else str(seed),
        "config": short(facts.get("config_sha256")),
        "instruction": short(facts.get("instruction_sha256")),
        "task": short(facts.get("task_sha256")),
        "reference": short(facts.get("reference_sha256")),
        "source": source,
        "drift": tuple(drift),
    }


def load_trial(trial_dir: Path) -> Trial | None:
    """Return None for a trial that has not finished (Harbor writes result.json at the end)."""
    result = manifest.read_json_object(trial_dir / "result.json")
    if result is None:
        return None
    report = _report(trial_dir)
    exc = result.get("exception_info") or {}
    error = exc.get("exception_type")
    try:
        reward = _reward(result, trial_dir)
    except ValueError as reward_error:
        reward = None
        error = f"{error}: {reward_error}" if error else str(reward_error)
    if reward is None and error is None:
        error = "no reward"
    ident = _identity(trial_dir, report)
    return Trial(
        job=trial_dir.parent.name,
        name=result["trial_name"],
        policy=_policy(result),
        model=_model(result),
        seed=ident["seed"],
        config=ident["config"],
        instruction=ident["instruction"],
        task=ident["task"],
        reference=ident["reference"],
        source=ident["source"],
        drift=ident["drift"],
        reward=reward,
        error=error,
        report=report,
    )


def _fmt(value: float | None) -> str:
    return "-" if value is None else f"{value:.3f}"


def _mean_of(reports: list[dict], key: str) -> float | None:
    values = [float(r[key]) for r in reports if isinstance(r.get(key), int | float)]
    return mean(values) if values else None


def _mean_total(reports: list[dict], key: str) -> float | None:
    values = [
        float(r["totals"][key]) for r in reports if isinstance((r.get("totals") or {}).get(key), int | float)
    ]
    return mean(values) if values else None


@dataclass
class Row:
    policy: str
    model: str
    seed: str
    config: str
    instruction: str
    task: str
    reference: str
    source: str
    runs: int
    errors: int
    mean: float
    low: float
    high: float
    extras: dict[str, float | None]


def build_rows(trials: list[Trial]) -> list[Row]:
    groups: dict[tuple[str, ...], list[Trial]] = {}
    for t in trials:
        key: tuple[str, ...] = (
            t.policy,
            t.model,
            t.seed,
            t.config,
            t.instruction,
            t.task,
            t.reference,
            t.source,
        )
        if UNKNOWN in key[2:]:
            # Unknown provenance could hide a different seed, config or prompt, so each such trial stays alone.
            key += (t.job, t.name)
        groups.setdefault(key, []).append(t)
    rows = []
    for (policy, model, seed, config, instruction, task, reference, source, *_), group in groups.items():
        # A trial with no reward counts as 0, as Harbor's own mean metric does.
        rewards = [t.reward if t.reward is not None else 0.0 for t in group]
        reports = [t.report for t in group if t.report is not None]
        extras = {k: _mean_of(reports, k) for k in COMPONENTS}
        extras["died"] = _mean_total(reports, "died")
        extras["faints"] = _mean_total(reports, "faints")
        rows.append(
            Row(
                policy=policy,
                model=model,
                seed=seed,
                config=config,
                instruction=instruction,
                task=task,
                reference=reference,
                source=source,
                runs=len(group),
                errors=sum(1 for t in group if t.error is not None),
                mean=mean(rewards),
                low=min(rewards),
                high=max(rewards),
                extras=extras,
            )
        )
    rows.sort(
        key=lambda r: (
            -r.mean,
            r.policy,
            r.model,
            r.seed,
            r.config,
            r.instruction,
            r.task,
            r.reference,
            r.source,
        )
    )
    return rows


def _identity_key(r: Row) -> tuple[str, ...] | None:
    """Rows are comparable only when seed, config, instruction, task, reference and source are known."""
    key = (r.seed, r.config, r.instruction, r.task, r.reference, r.source)
    return None if UNKNOWN in key else key


def _gaps(rows: list[Row]) -> list[str]:
    reference = POLICY_LABELS["oracle"]
    refs = {_identity_key(r): r.mean for r in rows if r.policy == reference and _identity_key(r)}
    lines = []
    for r in rows:
        key = _identity_key(r)
        if r.model == "-" or r.policy == reference or key is None or key not in refs:
            continue
        lines.append(
            f"- {r.policy} `{r.model}` seed {r.seed} config {r.config} instruction {r.instruction} "
            f"task {r.task} reference {r.reference} source {r.source}: "
            f"{refs[key] - r.mean:+.3f}"
        )
    return lines


@dataclass
class Completeness:
    planned: int
    matched: int
    missing: list[dict]
    failed: list[Trial]
    timed_out: list[Trial]
    unplanned: list[Trial]
    drifted: list[Trial] = field(default_factory=list)
    crashed: list[dict] = field(default_factory=list)

    @property
    def incomplete(self) -> bool:
        return bool(self.missing or self.failed or self.timed_out or self.drifted or self.crashed)

    def __add__(self, other: "Completeness") -> "Completeness":
        return Completeness(
            self.planned + other.planned,
            self.matched + other.matched,
            self.missing + other.missing,
            self.failed + other.failed,
            self.timed_out + other.timed_out,
            self.unplanned + other.unplanned,
            self.drifted + other.drifted,
            self.crashed + other.crashed,
        )


def _timed_out(trial: Trial) -> bool:
    return trial.report is not None and trial.report.get("ended") == "timeout"


def _plan_entries(plan: dict | list) -> list[dict]:
    return plan if isinstance(plan, list) else list(plan.get("entries") or [])


def _entry_key(e: dict) -> tuple[str | None, str, str, str]:
    policy = POLICY_LABELS.get(e["policy"], e["policy"])
    seed = e.get("seed")
    return e.get("job"), policy, e.get("model") or "-", UNKNOWN if seed is None else str(seed)


def completeness(
    plan: dict | list, trials: list[Trial], job_exit: dict[str, int | None] | None = None
) -> Completeness:
    """Match planned attempts to finished trials by (job, policy, model, seed); repeats are counted.

    An entry without a job matches that policy/model/seed in any job. Every planned attempt without
    a finished trial is `missing`, a matched trial with an error is `failed`, a matched trial that
    ended on `timeout` is listed as `timed_out` and makes the plan incomplete even with a reward.
    A timeout with an error is also listed as `failed`, and a trial no entry claims
    is `unplanned`. Nothing is dropped. This matches ONE root's plan against that root's trials; use
    `completeness_by_root` for several roots. A matched trial whose manifest flags identity drift is
    `drifted` and counts as failed. A planned entry with no finished trial whose job recorded a non-zero
    `harbor_exit_code` is `crashed` (also missing) and counts as failed.
    """
    job_exit = job_exit or {}
    entries = _plan_entries(plan)
    free = sorted(trials, key=lambda t: (t.job, t.name))
    matched: list[Trial] = []
    missing: list[dict] = []
    # Entries naming a job claim first, so a job-less entry cannot steal their trials.
    for e in sorted(entries, key=lambda e: (e.get("job") is None, e.get("repeat") or 0)):
        job, policy, model, seed = _entry_key(e)
        hit = next(
            (
                t
                for t in free
                if (job is None or t.job == job) and (t.policy, t.model, t.seed) == (policy, model, seed)
            ),
            None,
        )
        if hit is None:
            missing.append(e)
        else:
            free.remove(hit)
            matched.append(hit)
    return Completeness(
        planned=len(entries),
        matched=len(matched),
        missing=missing,
        failed=[t for t in matched if t.error is not None],
        drifted=[t for t in matched if t.drift],
        crashed=[e for e in missing if job_exit.get(e.get("job") or "")],
        timed_out=[t for t in matched if _timed_out(t)],
        unplanned=free,
    )


def completeness_by_root(
    roots: list[tuple[dict | list | None, list[Trial], dict[str, int | None]]],
) -> Completeness | None:
    """Per-root completeness, summed. A root without a plan contributes all its trials as unplanned.

    None when no root has a plan.
    """
    if all(plan is None for plan, _, _ in roots):
        return None
    total = Completeness(0, 0, [], [], [], [])
    for plan, trials, job_exit in roots:
        if plan is None:
            total += Completeness(0, 0, [], [], [], list(trials))
        else:
            total += completeness(plan, trials, job_exit)
    return total


def _completeness_lines(c: Completeness) -> list[str]:
    def entry(e: dict) -> str:
        return f"{e.get('job') or '*'}: {e['policy']} `{e.get('model') or '-'}` seed {e.get('seed')} repeat {e.get('repeat')}"

    def trial(t: Trial) -> str:
        return f"{t.job}/{t.name}: {t.policy} `{t.model}` seed {t.seed} ({t.error or 'ended timeout'})"

    def drift(t: Trial) -> str:
        return f"{t.job}/{t.name}: {', '.join(t.drift)}"

    out = [
        "",
        "## Completeness",
        "",
        f"Planned {c.planned}, matched {c.matched}, missing {len(c.missing)}, "
        f"failed {len(c.failed)}, timed out {len(c.timed_out)}, identity drift {len(c.drifted)}, "
        f"crashed {len(c.crashed)}, unplanned {len(c.unplanned)}. "
        + ("INCOMPLETE." if c.incomplete else "All planned attempts finished."),
    ]
    for title, items, fmt in (
        ("Missing (planned, no finished trial)", c.missing, entry),
        ("Failed (exception, missing reward, or invalid reward)", c.failed, trial),
        ("Timed out (ended=timeout; partial rewards retained)", c.timed_out, trial),
        ("Identity drift (task or source changed since plan; counts as failed)", c.drifted, drift),
        ("Crashed (missing, and harbor exited non-zero; counts as failed)", c.crashed, entry),
        ("Unplanned (not in plan.json)", c.unplanned, trial),
    ):
        if items:
            out += ["", f"{title}:", *[f"- {fmt(i)}" for i in items]]
    return out


def render(trials: list[Trial], sources: list[str], pending: int, comp: Completeness | None = None) -> str:
    rows = build_rows(trials)
    out = [
        "# ED-72 eval summary",
        "",
        "Written by `eval/summarise.py` from Harbor job directories: " + ", ".join(f"`{s}`" for s in sources),
        "",
        f"{len(trials)} finished trials" + (f", {pending} still running (left out)" if pending else "") + ".",
        "Reward = score / 100 (SPEC section 6). A trial with no reward counts as 0.",
        "Errors = trials with a Harbor exception, a missing reward, or an invalid reward.",
        "Seed, Config (SHA-256 prefix of the hospital config), Instruction (of instruction.md), Task (of the task dir),",
        "Reference (of solution/) and Source (git commit, +dirty) come from the job's manifest.json or the task dir;",
        "rows differing in any of them are separate, and `unknown` rows are never pooled or compared.",
        "O, T, W, B, deaths and faints are means over runs with a report.json.",
        "",
        "| Policy | Model | Seed | Config | Instruction | Task | Reference | Source | Runs | Errors | Mean reward | Min | Max | O | T | W | B | Deaths | Faints |",
        "|---|---|---|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in rows:
        cells = [
            r.policy,
            f"`{r.model}`" if r.model != "-" else "-",
            r.seed,
            r.config,
            r.instruction,
            r.task,
            r.reference,
            r.source,
            str(r.runs),
            str(r.errors),
        ]
        cells += [_fmt(r.mean), _fmt(r.low), _fmt(r.high)]
        cells += [_fmt(r.extras[k]) for k in (*COMPONENTS, "died", "faints")]
        out.append("| " + " | ".join(cells) + " |")
    gaps = _gaps(rows)
    if gaps:
        out += ["", "## Gap (reference minus agent mean)", "", *gaps]
    if comp is not None:
        out += _completeness_lines(comp)
    out += [
        "",
        "## Trials",
        "",
        "| Job | Trial | Policy | Model | Reward | Ended | Error |",
        "|---|---|---|---|---:|---|---|",
    ]
    for t in sorted(trials, key=lambda t: (t.job, t.name)):
        ended = str(t.report.get("ended", "-")) if t.report else "-"
        out.append(
            f"| {t.job} | {t.name} | {t.policy} | {t.model} | {_fmt(t.reward)} | {ended} | {t.error or '-'} |"
        )
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("jobs", nargs="*", type=Path, help=f"Harbor jobs dirs (default {DEFAULT_JOBS})")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument(
        "--allow-incomplete",
        action="store_true",
        help="exit 0 even when attempts are incomplete or failed (still listed in the summary)",
    )
    args = parser.parse_args(argv)
    roots: list[Path] = args.jobs or [DEFAULT_JOBS]
    missing = [r for r in roots if not r.is_dir()]
    if missing:
        print(f"summarise: not a directory: {', '.join(map(str, missing))}", file=sys.stderr)
        return 2
    loaded: list[Trial | None] = []
    per_root = []
    seen: set[Path] = set()
    for r in roots:
        dirs = [d for d in find_trial_dirs([r]) if d not in seen]
        seen.update(dirs)
        root_trials = [load_trial(d) for d in dirs]
        loaded += root_trials
        plan = manifest.load_plan(r)
        job_exit = {
            e["job"]: (manifest.read_json_object(r / e["job"] / manifest.MANIFEST_NAME) or {}).get(
                "harbor_exit_code"
            )
            for e in _plan_entries(plan or {})
            if e.get("job")
        }
        per_root.append((plan, [t for t in root_trials if t is not None], job_exit))
    trials = [t for t in loaded if t is not None]
    comp = completeness_by_root(per_root)
    if not trials and comp is None:
        print(f"summarise: no finished Harbor trials under {', '.join(map(str, roots))}", file=sys.stderr)
        return 1
    sources = [
        str(r.resolve().relative_to(REPO_ROOT)) if r.resolve().is_relative_to(REPO_ROOT) else str(r)
        for r in roots
    ]
    text = render(trials, sources, pending=len(loaded) - len(trials), comp=comp)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text)
    print(text, end="")
    print(f"summarise: wrote {args.out}", file=sys.stderr)
    if comp is None:
        print("summarise: no plan.json, so missing attempts cannot be detected", file=sys.stderr)
    elif comp.incomplete and not args.allow_incomplete:
        print(
            f"summarise: INCOMPLETE: {len(comp.missing)} planned attempts missing, "
            f"{len(comp.failed)} failed, {len(comp.timed_out)} timed out, "
            f"{len(comp.drifted)} identity drift, "
            f"{len(comp.crashed)} crashed (use --allow-incomplete to accept)",
            file=sys.stderr,
        )
        return 4
    errors = [
        f"{t.job}/{t.name}: {t.error or 'ended timeout'}"
        for t in trials
        if t.error is not None or _timed_out(t)
    ]
    if errors and not args.allow_incomplete:
        print(f"summarise: incomplete or failed trials: {', '.join(errors)}", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
