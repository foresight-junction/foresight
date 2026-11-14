#!/bin/bash
set -u

REWARD=/logs/verifier/reward.txt
mkdir -p /logs/verifier

if ! python3 /tests/verify.py; then
  printf '0\n' > "$REWARD"
  exit 1
fi

# verify.py wrote a number already; guard against an empty file anyway.
if [ ! -s "$REWARD" ]; then
  printf '0\n' > "$REWARD"
  exit 1
fi
