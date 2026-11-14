# yehor/docs-sole-orchestrator

## Goal

Issue #117 records Yehor's sole orchestration and merge authority for the #113 release plan.

## Files I own

- `AGENTS.md`
- `CLAUDE.md`
- `GEMINI.md`
- `.agents/skills/claim-task/SKILL.md`
- `.agents/skills/ship-pr/SKILL.md`
- `docs/PLAN.md`
- This context file

## Don't touch

Runtime code, contracts, existing issue scope, and other branches or context files.

## Status

- Based on current main at `3c02ee7`.
- Independent GPT-6.1 Sol review used Yehor's selected model. Clarified assignment precedence and preserved owners' ability to run focused tests.

## Handoff

The policy now agrees across AGENTS.md, CLAUDE.md, GEMINI.md, claim-task, ship-pr and PLAN.md. Run `git diff --check` and verify merge authority, assigned PR bases and the #18 launch gate in those files. Yehor handles merge after CI.
