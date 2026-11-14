#!/bin/sh
set -u

mkdir -p /logs/verifier
if ! python3 /tests/verify.py; then
  printf '0.0\n' > /logs/verifier/reward.txt
  exit 1
fi
