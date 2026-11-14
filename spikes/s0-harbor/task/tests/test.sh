#!/bin/bash
set -u

OUT_DIR=/logs/verifier
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR/reward.txt"
printf '{"reward": 0, "pings": 0}\n' > "$OUT_DIR/reward.json"

if ! /usr/local/bin/python3 /tests/verify.py; then
  printf '{"reward": 0, "pings": 0}\n' > "$OUT_DIR/reward.json"
fi

cat "$OUT_DIR/reward.json"
exit 0
