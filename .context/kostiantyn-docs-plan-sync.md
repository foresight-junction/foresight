# Branch: kostiantyn/docs-plan-sync

- **Issue:** #41
- **Owner:** kostiantyn
- **Agent:** kostiantyn-claude-3 (lead)
- **Parent branch:** main
- **Created:** Sat 15:41

## Goal
Add A10 (#67) and C7 (#69) to PLAN.md, and make board-check check 6 read the agent-visible HANDBOOK.md. Done when `scripts/board-check.sh origin/main` passes checks 2 and 6.

## Files and folders I own
- 

## Don't touch
- 

## Contracts used or changed
Anything from docs/CONTRACTS.md this branch depends on or changes.
- 

## Status
- [x] PLAN.md: A10, C7
- [x] board-check check 6 reads `ed72/environment/workspace/HANDBOOK.md` at the ref (A5 #7 and B6 #15 are closed, so their issue bodies no longer apply)

## Decisions and notes
Short and dated: why we chose X, new dependencies and why, gotchas.
- 

## Handoff
Done / not done / how to test. Keep this current: another agent may pick it up.
- Done: see Status. Merging is the integrator's job (kostiantyn-claude-4).
- Test: `bash -n scripts/board-check.sh && scripts/board-check.sh origin/main`; check 6 prints six ok lines.
