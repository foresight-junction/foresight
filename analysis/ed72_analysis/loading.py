"""Run inputs: a labelled score_full.json and an optional event log."""

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Run:
    label: str
    score: dict
    events: list[dict] = field(default_factory=list)

    @property
    def group(self) -> str:
        """`opus/seed1` -> `opus`: runs of one model are averaged together."""
        return self.label.split("/", 1)[0]


def parse_run_arg(arg: str) -> Run:
    """Parse `<label>=<score_full.json>[,<events.jsonl>]`."""
    label, sep, paths = arg.partition("=")
    if not sep or not label or not paths:
        raise ValueError(f"bad --run {arg!r}: expected label=score.json[,events.jsonl]")
    score_path, _, events_path = paths.partition(",")
    score = json.loads(Path(score_path).read_text(encoding="utf-8"))
    events = load_events(Path(events_path)) if events_path else []
    return Run(label, score, events)


def load_events(path: Path) -> list[dict]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]
