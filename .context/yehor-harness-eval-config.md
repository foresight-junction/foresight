# yehor/harness-eval-config

- **Owner:** Yehor
- **Agent:** yehor-codex-1
- **Base:** main
- **Issue:** #144

## Goal

Use the packaged default JSON inside the hospital container. Verify that stock benchmark scores hold and that a JSON override affects simulation and provenance.

## Files I own

`ed72/environment/hospital/Dockerfile`, `ed72/environment/hospital/tests/test_config.py`, `docs/CONTRACTS.md`.

## Don't touch

Published campaign artifacts.

## Handoff

The hospital image loads the same default JSON the manifest hashes. Hospital tests passed (480 passed and one expected failure). Keyless Harbor seed 3101 completed all three planned baselines with published score parity.
