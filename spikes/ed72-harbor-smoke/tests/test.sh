#!/bin/bash
set -u
mkdir -p /logs/verifier
printf '0\n' > /logs/verifier/reward.txt
python - <<'PY'
import json
from pathlib import Path

source = Path("/evidence/report.json")
report = json.loads(source.read_text(encoding="utf-8"))
Path("/logs/verifier/score_full.json").write_text(json.dumps(report), encoding="utf-8")
Path("/logs/verifier/reward.txt").write_text(str(report["reward"]) + "\n", encoding="utf-8")
PY
