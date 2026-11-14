"""CLI: python -m ed72_analysis.report --run label=score_full.json[,events.jsonl] ... --out dir"""

import argparse
from pathlib import Path

from ed72_analysis import tables, trajectories
from ed72_analysis.loading import Run, parse_run_arg
from ed72_analysis.svg import failures_svg


def build_report(runs: list[Run]) -> str:
    parts = ["# ED-72 failure analysis report", "## Scores", tables.score_table(runs)]
    parts += ["## Failures by code", tables.failure_table(runs), "![failures](failures.svg)"]
    parts.append("## Outcomes by ESI")
    for r in runs:
        parts += [f"### {r.label}", tables.esi_table(r)]
    with_logs = [r for r in runs if r.events]
    if with_logs:
        parts.append("## Trajectory excerpts")
        for r in with_logs:
            parts += [f"### {r.label}", trajectories.excerpts_md(r.events, r.score)]
    return "\n\n".join(parts) + "\n"


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run", action="append", required=True, help="label=score_full.json[,events.jsonl]")
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args(argv)
    runs = [parse_run_arg(a) for a in args.run]
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "report.md").write_text(build_report(runs), encoding="utf-8")
    (args.out / "failures.svg").write_text(failures_svg(runs), encoding="utf-8")


if __name__ == "__main__":
    main()
