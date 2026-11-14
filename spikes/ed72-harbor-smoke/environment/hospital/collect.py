import json
from pathlib import Path

report = Path("/evidence/report.json")
report.parent.mkdir(exist_ok=True)
calls = json.loads(Path("/app/smoke-state.json").read_text(encoding="utf-8"))
passed = calls == ["rules", "observe", "step"]
reward = int(passed)
report.write_text(
    json.dumps(
        {
            "reward": reward,
            "score": 100 * reward,
            "O": reward,
            "T": reward,
            "W": reward,
            "B": reward,
            "spend": 0,
            "totals": {
                "arrived": 0,
                "discharged": 0,
                "in_bed_end": 0,
                "diverted": 0,
                "died": 0,
                "left": 0,
                "never_admitted": 0,
                "faints": 0,
            },
            "patients": [],
            "failures": {f"F{i}": 0 for i in range(1, 11)},
            "ticks_with_actions": 0,
            "tool_calls": len(calls),
            "ended": "agent_stopped",
            "smoke_calls": calls,
        }
    ),
    encoding="utf-8",
)
