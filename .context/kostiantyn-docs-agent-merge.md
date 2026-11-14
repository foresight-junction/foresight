# Branch: kostiantyn/docs-agent-merge

- **Issue:** #41
- **Owner:** kostiantyn
- **Agent:** kostiantyn-claude-3 (lead)
- **Parent branch:** main
- **Created:** Sat 15:09

## Goal
Let every agent push and merge its own PRs (Kostiantyn's request, Sat 15:20). Done when AGENTS.md rule 8, ship-pr, contract-change, CLAUDE.md, PLAN.md and .claude/settings.json all say so and the PR is merged.

## Files and folders I own
- 

## Don't touch
- 

## Contracts used or changed
Anything from docs/CONTRACTS.md this branch depends on or changes.
- 

## Status
- [x] Rule 8, §1 Integrator, §8 DoD, ship-pr step 5, contract-change, CLAUDE.md, PLAN.md updated
- [x] .claude/settings.json: allow git push and gh pr create/merge/view/checks; deny force-push, branch deletion, --admin

## Decisions and notes
Short and dated: why we chose X, new dependencies and why, gotchas.
- 

## Handoff
Done / not done / how to test. Keep this current: another agent may pick it up.
- Done: see Status. Codex and Gemini read the rule from AGENTS.md; their approval prompts are per-user config, not in this repo.
- Test: `python -c "import json;json.load(open('.claude/settings.json'))"`; a new Claude session in the repo runs `git push` and `gh pr merge` without a prompt.
