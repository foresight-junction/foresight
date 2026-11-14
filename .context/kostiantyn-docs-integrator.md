# kostiantyn/docs-integrator

## Goal
Make kostiantyn-claude-4 the single integrator that merges every PR into `main` (Kostiantyn's request, Sat ~15:40). Replaces the self-merge rule from PR #54.

## Files owned
AGENTS.md (section 1 Integrator line, golden rule 8, definition of done), .agents/skills/ship-pr/SKILL.md (step 5), .agents/skills/contract-change/SKILL.md (step 3), docs/PLAN.md (line 20).

## Status
- Done: all four files say only the integrator merges into `main`; owners mark PRs ready and comment `ready to merge`.
- Not changed: .claude/settings.json still allows `gh pr merge` (the integrator needs it; the rule is enforced by AGENTS.md).

## Handoff
Done. Test: `grep -rn "gh pr merge" AGENTS.md .agents` shows only the integrator rule and the helper-branch line.
