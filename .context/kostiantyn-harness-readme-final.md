# Branch: kostiantyn/harness-readme-final

- **Issue:** #25
- **Owner:** kostiantyn
- **Agent:** kostiantyn-claude-3 (lead)
- **Parent branch:** main
- **Created:** Sat 18:14

## Goal
A short README that meets every AfterQuery requirement (what the agent does, why it is hard, how it is scored, how to run, a Harbor run log with score), concept first, no placeholders. Asked for by Kostiantyn.

## Files and folders I own
- `README.md`

## Don't touch
- Everything else (final stop: docs only)

## Contracts used or changed
Anything from docs/CONTRACTS.md this branch depends on or changes.
- None.

## Status
- [x] README rewritten (115 lines, was 179 with invisible HUMAN placeholders); every number checked against HANDBOOK.md, docs/TUNING.md, docs/REDTEAM.md, #36 and eval/results/2026-11-14-gemini-seed42/; all relative links resolve

## Decisions and notes
Short and dated: why we chose X, new dependencies and why, gotchas.
- Sat 18:30: added an honest 'Known limits' section (one model run, levers worth ~0 in ablations, stop-early not through Harbor). Demo video link goes in when Yehor has it.

## Handoff
Done / not done / how to test. Keep this current: another agent may pick it up.
- Done. Not done: the video link and #18 matrix numbers (update the Results table when #18 posts). Review: render on GitHub and check the tables.
