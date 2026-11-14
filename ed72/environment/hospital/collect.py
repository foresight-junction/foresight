"""Verifier collect hook: replay the agent's logged steps, score, write the report.

Runs inside the hospital container (Harbor [[verifier.collect]]). The live event log
is only read; the replay uses a fresh Simulation so nothing here can alter it.
"""

import json
import os
from pathlib import Path

from ed72_sim.constants import EVENT_LOG_PATH
from ed72_sim.engine import Simulation
from ed72_sim.scoring.score import score
from ed72_sim.world import generate_world

REPORT_PATH = "/evidence/report.json"


def read_step_lines(log_path: Path) -> list[dict]:
    # A missing log means the agent never acted: the episode runs with no actions.
    if not log_path.exists():
        return []
    lines = []
    with log_path.open(encoding="utf-8") as log_file:
        for raw in log_file:
            if raw.strip():
                lines.append(json.loads(raw))
    return [ln for ln in lines if ln.get("src") == "agent" and ln.get("tool") == "step"]


def collect(seed: int, log_path: Path, out_path: Path) -> dict:
    sim = Simulation(generate_world(seed))
    for line in read_step_lines(log_path):
        if line["t"] != sim.tick:
            raise ValueError(f"log step at tick {line['t']} but replay is at tick {sim.tick}")
        sim.step(line["args"]["actions"])
    sim.run_to_end()
    report = score(sim.events)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = out_path.with_name(out_path.name + ".tmp")
    tmp_path.write_text(json.dumps(report), encoding="utf-8")
    os.replace(tmp_path, out_path)
    return report


def main() -> None:
    report = collect(int(os.environ["ED72_SEED"]), Path(EVENT_LOG_PATH), Path(REPORT_PATH))
    print(json.dumps({"reward": report["reward"]}))


if __name__ == "__main__":
    main()
