# Branch: yehor/harness-final-sweep

- **Issue:** #130
- **Owner:** yehor
- **Agent:** yehor-claude-21 (lead)
- **Parent branch:** main
- **Created:** Sun 05:50

## Goal
Small, safe fixes from the final sweep before the 09:00 freeze. No sim, scorer, tool, reference or difficulty change.

## Files I own
`.gitignore`, and comment or doc fixes outside the Codex doc-rename files listed on #1.

## Don't touch
AGENTS.md, README.md, docs/CONTRACTS.md, docs/DEMO.md, docs/ED_Management_Simulator_RU.md, docs/EVAL.md, docs/HARBOR-NOTES.md, docs/PLAN.md, docs/SPEC.md, ed72_sim/__init__.py, ed72_sim/constants.py, scoring/tests/test_probes.py, scripts/bootstrap-board.sh (Codex rename).

## Status
1. Done: `/jobs/` ignored. Harbor writes it for `harbor run` from the repo root, and `eval/manifest.py:144` counts untracked files as dirty.
2. Done: `/ed72/environment/hospital/uv.lock` ignored (uv recreates it; the team keeps dropping it, e022180).
3. Done: stale comments in test_firewall.py, test_baselines.py, eval/probes/README.md, ci.yml, wt.sh. A sweep agent checked HANDBOOK, instruction.md and solution/README against constants.py, default.json and server.py, and found no contradictions.

## Handoff
Test: `mkdir -p jobs/x && touch jobs/x/a && git status --porcelain` prints nothing for jobs/. Fresh clone of main 92dec88: `ED72_SEED=3101 make eval-baselines` gives 0.959 / 0.046 / 0.000.
