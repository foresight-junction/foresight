# Branch: yehor/harness-readme

- **Issue:** #25
- **Owner:** yehor
- **Agent:** yehor-claude-3e
- **Parent branch:** main
- **Created:** Sat 17:20

## Goal
A factual README skeleton ordered for a judge, and a 10-minute demo script with recording and submission checklists (`docs/DEMO.md`). A human writes the core paragraphs (issue #25: "a human writes the core paragraphs").

## Files and folders I own
- `README.md`
- `docs/DEMO.md`

## Don't touch
- `eval/`, `ed72/`, every other file in `docs/`

## Contracts used or changed
- Uses: CONTRACTS v1 tools, score object, event-log lines; SPEC §3-§6, §11; EVAL §3-§5. Changes none.

## Status
- [x] Claimed early at Yehor's request; deps #18, #19, #14 not done
- [x] README skeleton: task, how to run, scoring, why you can't cheat, results table (empty), repo map, HUMAN slots
- [x] docs/DEMO.md: timed segments, recording checklist, submission checklist
- [ ] Human fills the HUMAN slots (README: opening, why it is hard, results reading, what agents get wrong; DEMO: hook, close)
- [x] Verified calibration and baseline results, current run commands and artifact-based demo walkthrough
- [ ] Add the model trajectory link and the model results and findings as #17–#19 land

## Decisions and notes
- Sat 17:30: merged main after #45, #47, #52, #53, #56, #60, #63 merged; their markers removed. Still open: #57 (server.py, ward), #58 (task.toml, Dockerfiles, compose), #16 (solution/), #7 (HANDBOOK, instruction.md).
- Sat: paths that are only in open PRs are marked "(lands with #N)". Checked on these branches: #45 collect.py/tests, #47 scoring/, #52 eval/baselines, #53 Makefile/eval, #56 firewall tests, #57 server.py/ward, #58 task.toml/Dockerfiles/compose, #60 HARBOR-NOTES. `ed72/solution/` (#16) and `HANDBOOK.md`/`instruction.md` (#7) have no PR yet.
- Sat: Harbor 0.25.0 flags `-p -a -m -k -o -n` and agents `oracle`, `nop`, `opencode` checked with `harbor run --help`. #60 used Harbor 0.26.0; README follows #53's pin.
- Sat: `eval/run_all.sh` expects `eval/baselines/ed72_baselines/harbor_agent.py` for stop-early; not on main yet, so run_all skips stop-early.
- Sat: the event log is not collected as a trial artifact in #58's task.toml, so DEMO segment 4 needs a decision (TODO(demo)).
- Sat: docs/CHALLENGE.md "Starting points" still describes the old game (15 beds, `assess`, 8+13 tools, M1-M4 harm). README follows SPEC and the rulebook.

## Handoff
- Draft PR #70 is synced with frozen main (474829a). The README links the verified oracle/nop calibration and the five-seed tuning table. The demo uses the trajectory and verifier report collected by Harbor.
- Yehor writes the hand-authored slots, then times and records the playthrough and submits it. Model results, a Harbor model-log link and failure analysis are pending #17–#19. #83 tracks the missing Harbor stop-early adapter.
- Verify the calibration with `make eval-baselines`. Check the remaining author slots with `rg -n 'HUMAN:|TODO\(' README.md docs/DEMO.md`.
