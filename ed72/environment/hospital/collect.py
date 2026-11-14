"""Verifier collect hook: replay the agent's logged steps, score, write the report.

Runs inside the hospital container (Harbor [[verifier.collect]]). The live event log
is only read; the replay uses a fresh Simulation so nothing here can alter it.
"""

import json
import os
from pathlib import Path

from ed72_sim.config import Config, load_config
from ed72_sim.constants import EVENT_LOG_PATH
from ed72_sim.engine import Simulation
from ed72_sim.scoring.score import score
from ed72_sim.world import generate_world

REPORT_PATH = "/evidence/report.json"


def read_agent_lines(log_path: Path) -> list[dict]:
    # A missing log means the agent never acted: the episode runs with no actions.
    if not log_path.exists():
        return []
    with log_path.open(encoding="utf-8") as log_file:
        lines = [json.loads(raw) for raw in log_file if raw.strip()]
    return [ln for ln in lines if ln.get("src") == "agent"]


def collect(seed: int, log_path: Path, out_path: Path, config: Config | None = None) -> dict:
    sim = Simulation(generate_world(seed, config))
    for line in read_agent_lines(log_path):
        if line["t"] != sim.tick:
            raise ValueError(f"log line at tick {line['t']} but replay is at tick {sim.tick}")
        # Only a successful step resolves a tick. observe, rules and refused calls (call cap, episode
        # over) are re-recorded so ended and tool_calls match the live run.
        if line["tool"] == "step" and "error" not in line["result"]:
            sim.replay_step(line["args"]["actions"])
        else:
            sim.record_call(line["tool"], line["args"], line["result"])
    sim.run_to_end()
    report = score(sim.events)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = out_path.with_name(out_path.name + ".tmp")
    tmp_path.write_text(json.dumps(report), encoding="utf-8")
    os.replace(tmp_path, out_path)
    return report


def main() -> None:
    config = load_config(os.environ.get("ED72_CONFIG"))
    report = collect(int(os.environ["ED72_SEED"]), Path(EVENT_LOG_PATH), Path(REPORT_PATH), config)
    print(json.dumps({"reward": report["reward"]}))


if __name__ == "__main__":
    main()
