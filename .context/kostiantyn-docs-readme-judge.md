# Branch: kostiantyn/docs-readme-judge

- **Issue:** #25
- **Owner:** kostiantyn
- **Agent:** kostiantyn-claude-6d
- **Parent branch:** kostiantyn/final
- **Created:** Sat 20:15

## Goal
A judge-ready README and demo script with no placeholders left.

## Files and folders I own
- `README.md`, `docs/DEMO.md`

## Don't touch
- Code, `eval/run_all.sh` (#95), SPEC §7 and TUNING (difficulty agent), HANDBOOK.

## Status
- [x] README: built on PR #96's layout (concept first), added back tools and outputs tables, filled every placeholder, fixed the stop-early claim (Codex finding on #96), added the model-key table that matches #95.
- [x] Model decisions from the Gemini seed-42 trajectory and score report, compared with the in-process reference on seed 42 (0 deaths, 474 discharged, €7 000, score 98.9617).
- [x] DEMO.md: hook, episode walkthrough (tick 121), results, close, submission note.

## Decisions and notes
- Took README content from PR #96, not a merge: #96 also adds two stray `uv.lock` files.
- Difficulty-dependent numbers are marked with `<!-- Difficulty-dependent ... -->` comments in README (shortcut table, Results). Also the summary-table Result row, the gap figures in "What the numbers say", and DEMO §1 and §7.
- `docs/EVAL.md` §3 still says `make eval` runs stop-early; it doesn't (no Harbor adapter, #83). Not mine to edit; reported to the orchestrator.

## Handoff
Done: README and DEMO. Test: `grep -nE 'HU[M]AN|TODO[(]' README.md docs/DEMO.md` prints nothing; every relative link resolves.
