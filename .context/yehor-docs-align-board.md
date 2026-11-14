# Branch: yehor/docs-align-board

- **Issue:** #40
- **Owner:** yehor
- **Agent:** yehor-claude-2
- **Parent branch:** main
- **Created:** Sat 16:25

## Goal
AGENTS.md, the skills and GEMINI.md agree with Kostiantyn's latest board update, #41 (W0): the RU rulebook governs the game, SPEC section 9 harness stays, docs and issues are being realigned in #41. Gemini CLI agents follow AGENTS.md too.

## Files and folders I own
- `AGENTS.md` (sections 1 and 4), `GEMINI.md` (new)
- `.agents/skills/pre-commit-gate/SKILL.md` (step 6: rule changes are recorded in SPEC, as #41 asks), `.agents/skills/cross-review/SKILL.md` (Gemini line), `.agents/skills/claim-task/SKILL.md` (read #39 first)

## Don't touch
- `docs/` content, the issue board (Kostiantyn owns it)

## Contracts used or changed
- None.

## Status
- [x] Issue #40, branch from main at e7db0e2
- [ ] AGENTS.md, skills, GEMINI.md aligned with #39
- [ ] Cross-check docs, skills, #39 and issue bodies agree; PR; merge; correct the #1 and #2 notes

## Decisions and notes
- Sat 16:25. Yehor asked to stay consistent with Kostiantyn's most recent updates. #39 (14:15) still names SPEC as the source of truth, but #41 (14:20, wave 0) accepts the RU rulebook and realigns the docs and board. #41 is the latest, so the rulebook stays the source of truth; AGENTS.md now points to #41 and limits early work to the issues #41 lists as consistent. A first draft of this branch went the other way and was rewritten before any push.

## Handoff
- How to test: `grep -rn "source of truth\|#41" AGENTS.md GEMINI.md .agents/skills` names the rulebook as the source of truth and #41 as the realignment.
