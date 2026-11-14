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
import json
import sys
from dataclasses import dataclass
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


def _read_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    data = json.loads(path.read_text())
    return data if isinstance(data, dict) else None


def find_trial_dirs(roots: list[Path]) -> list[Path]:
    found: set[Path] = set()
    for root in roots:
        for config in root.rglob("config.json"):
            data = _read_json(config)
            if data is not None and "trial_name" in data:
                found.add(config.parent)
    return sorted(found)


def _report(trial_dir: Path) -> dict | None:
    for path in (
        trial_dir / "verifier" / "score_full.json",
        trial_dir / "artifacts" / "evidence" / "report.json",
    ):
        data = _read_json(path)
        if data is not None:
            return data
    for path in sorted((trial_dir / "artifacts").rglob("report.json")):
        data = _read_json(path)
        if data is not None:
            return data
    return None


def _reward(result: dict, trial_dir: Path) -> float | None:
    rewards = (result.get("verifier_result") or {}).get("rewards") or {}
    if "reward" in rewards:
        return float(rewards["reward"])
    reward_txt = trial_dir / "verifier" / "reward.txt"
    if reward_txt.is_file():
        try:
            return float(reward_txt.read_text().strip())
        except ValueError:
            return None
    return None


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

    return {
        "seed": UNKNOWN if seed is None else str(seed),
        "config": short(facts.get("config_sha256")),
        "instruction": short(facts.get("instruction_sha256")),
    }


def load_trial(trial_dir: Path) -> Trial | None:
    """Return None for a trial that has not finished (Harbor writes result.json at the end)."""
    result = _read_json(trial_dir / "result.json")
    if result is None:
        return None
    report = _report(trial_dir)
    reward = _reward(result, trial_dir)
    exc = result.get("exception_info") or {}
    error = exc.get("exception_type")
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
    runs: int
    errors: int
    mean: float
    low: float
    high: float
    extras: dict[str, float | None]


def build_rows(trials: list[Trial]) -> list[Row]:
    groups: dict[tuple[str, ...], list[Trial]] = {}
    for t in trials:
        key: tuple[str, ...] = (t.policy, t.model, t.seed, t.config, t.instruction)
        if UNKNOWN in key[2:]:
            # Unknown provenance could hide a different seed, config or prompt, so each such trial stays alone.
            key += (t.job, t.name)
        groups.setdefault(key, []).append(t)
    rows = []
    for (policy, model, seed, config, instruction, *_), group in groups.items():
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
                runs=len(group),
                errors=sum(1 for t in group if t.error is not None),
                mean=mean(rewards),
                low=min(rewards),
                high=max(rewards),
                extras=extras,
            )
        )
    rows.sort(key=lambda r: (-r.mean, r.policy, r.model, r.seed, r.config, r.instruction))
    return rows


def _identity_key(r: Row) -> tuple[str, str, str] | None:
    """Rows are comparable only when seed, config and instruction are all known."""
    key = (r.seed, r.config, r.instruction)
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
            f"- {r.policy} `{r.model}` seed {r.seed} config {r.config} instruction {r.instruction}: "
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

    @property
    def incomplete(self) -> bool:
        return bool(self.missing or self.failed)


def _plan_entries(plan: dict | list) -> list[dict]:
    return plan if isinstance(plan, list) else list(plan.get("entries") or [])


def _entry_key(e: dict) -> tuple[str | None, str, str, str]:
    policy = POLICY_LABELS.get(e["policy"], e["policy"])
    seed = e.get("seed")
    return e.get("job"), policy, e.get("model") or "-", UNKNOWN if seed is None else str(seed)


def completeness(plan: dict | list, trials: list[Trial]) -> Completeness:
    """Match planned attempts to finished trials by (job, policy, model, seed); repeats are counted.

    An entry without a job matches that policy/model/seed in any job. Every planned attempt without
    a finished trial is `missing`, a matched trial with an error is `failed`, a matched trial that
    ended on `timeout` is also listed as `timed_out` (it stays `failed` too if Harbor recorded an
    exception, because #93 made any agent exception fail the evaluation), and a trial no entry claims
    is `unplanned`. Nothing is dropped.
    """
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
        timed_out=[t for t in matched if t.report and t.report.get("ended") == "timeout"],
        unplanned=free,
    )


def _completeness_lines(c: Completeness) -> list[str]:
    def entry(e: dict) -> str:
        return f"{e.get('job') or '*'}: {e['policy']} `{e.get('model') or '-'}` seed {e.get('seed')} repeat {e.get('repeat')}"

    def trial(t: Trial) -> str:
        return f"{t.job}/{t.name}: {t.policy} `{t.model}` seed {t.seed} ({t.error or 'ended timeout'})"

    out = [
        "",
        "## Completeness",
        "",
        f"Planned {c.planned}, matched {c.matched}, missing {len(c.missing)}, "
        f"failed {len(c.failed)}, timed out {len(c.timed_out)}, unplanned {len(c.unplanned)}. "
        + ("INCOMPLETE." if c.incomplete else "All planned attempts finished."),
    ]
    for title, items, fmt in (
        ("Missing (planned, no finished trial)", c.missing, entry),
        ("Failed (exception or no reward)", c.failed, trial),
        ("Timed out (ended=timeout; also failed if Harbor recorded an exception)", c.timed_out, trial),
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
        "Errors = trials where Harbor recorded an exception or no reward.",
        "Seed, Config (SHA-256 prefix of the hospital config) and Instruction (SHA-256 prefix of instruction.md)",
        "come from the job's manifest.json or the task dir; `unknown` rows are never pooled or compared.",
        "O, T, W, B, deaths and faints are means over runs with a report.json.",
        "",
        "| Policy | Model | Seed | Config | Instruction | Runs | Errors | Mean reward | Min | Max | O | T | W | B | Deaths | Faints |",
        "|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in rows:
        cells = [
            r.policy,
            f"`{r.model}`" if r.model != "-" else "-",
            r.seed,
            r.config,
            r.instruction,
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
        help="exit 0 even when a planned attempt is missing or failed (still listed in the summary)",
    )
    args = parser.parse_args(argv)
    roots: list[Path] = args.jobs or [DEFAULT_JOBS]
    missing = [r for r in roots if not r.is_dir()]
    if missing:
        print(f"summarise: not a directory: {', '.join(map(str, missing))}", file=sys.stderr)
        return 2
    loaded = [load_trial(d) for d in find_trial_dirs(roots)]
    trials = [t for t in loaded if t is not None]
    plans = [p for p in (manifest.load_plan(r) for r in roots) if p is not None]
    plan = [e for p in plans for e in _plan_entries(p)] if plans else None
    if not trials and plan is None:
        print(f"summarise: no finished Harbor trials under {', '.join(map(str, roots))}", file=sys.stderr)
        return 1
    sources = [
        str(r.resolve().relative_to(REPO_ROOT)) if r.resolve().is_relative_to(REPO_ROOT) else str(r)
        for r in roots
    ]
    comp = completeness(plan, trials) if plan is not None else None
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
            f"{len(comp.failed)} failed (use --allow-incomplete to accept)",
            file=sys.stderr,
        )
        return 4
    errors = [f"{t.job}/{t.name}: {t.error}" for t in trials if t.error is not None]
    if errors and not args.allow_incomplete:
        print(f"summarise: failed trials: {', '.join(errors)}", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
