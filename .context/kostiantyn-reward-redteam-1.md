# Branch: kostiantyn/reward-redteam-1

- **Issue:** #13
- **Owner:** kostiantyn
- **Agent:** kostiantyn-claude-2h
- **Parent branch:** main (stacked on batch-1 PRs #44-#48)
- **Created:** Sat 15:06

## Goal
Attack the reward as a judge would, using the real world, engine, scorer, `collect.py` and `verify.py`. Log every attempt in `docs/REDTEAM.md`; each attempt is a regression test.

## Files and folders I own
- `docs/REDTEAM.md`
- `ed72/environment/hospital/tests/test_redteam_round1.py`
- `.context/kostiantyn-reward-redteam-1.md`

## Don't touch
- Any code under `ed72/` outside the test file. Bugs are reported, not fixed.

## Contracts used or changed
- CONTRACTS v1 rejection reasons and event log. None changed.

## Status
- [x] Read SPEC 6, 8, 11, AGENTS 10 and the batch-1 code
- [x] Write greedy policy and variants, score on seeds 1-3
- [x] Attacks on actions, tick 143, refusals, collect.py, verify.py as tests
- [x] Static check of the agent container on the Harbor skeleton branch
- [x] docs/REDTEAM.md
- [ ] Tool, port and MCP attacks: pending #5

## Decisions and notes
- No exploit found, so no p0 issues and no xfail tests. Notes N1-N3 are in docs/REDTEAM.md.

## Handoff
Done: 80 attack tests, all green (193 in the whole hospital suite); REDTEAM.md with score table.
Not done: attempts 28-30 (need the tool server #5); rerun the table after any change to constants, patients, events or scoring.
Test: `cd ed72/environment/hospital && python -m pytest -q tests/test_redteam_round1.py`
