# Branch: yehor/harness-dev-setup

- **Issue:** #30
- **Owner:** yehor
- **Agent:** yehor-claude-2 (lead), subagents 2a, 2b
- **Parent branch:** main
- **Created:** Sat 15:11

## Goal
Make the team workflow match the ED-72 layout so lanes can build fast. Works when no skill or script step names a folder that does not exist (`backend/`, `frontend/`, pnpm).

## Files and folders I own
- `.agents/skills/pre-commit-gate/SKILL.md`, `.agents/skills/contract-change/SKILL.md`, `.agents/skills/cross-review/SKILL.md` (subagent 2a)
- `scripts/wt.sh`, `.env.example` (new), `.gitignore` (subagent 2b)
- `AGENTS.md` (sections 1 and 7 only), `.context/yehor-docs-ed-pivot.md` (handoff line) (lead)

## Don't touch
- `docs/`, `scripts/bootstrap-board.sh`, `.github/workflows/ci.yml` (that is #24 on `yehor/harness-ci`)

## Contracts used or changed
- None changed. `.env.example` lists the env vars already in docs/CONTRACTS.md.

## Status
- [x] Issue #30 created and claimed, worktree made
- [x] Skills, wt.sh, .env.example, .gitignore retargeted by two Sonnet subagents
- [x] AGENTS.md says where Python lives and how to lint and test
- [ ] PR, merge (Yehor authorised merging this PR)

## Decisions and notes
- Sat 15:15. One uv project for sim, tools and scorer at `ed72/environment/hospital/`, matching docs/SPEC.md section 9. Other Python folders get their own pyproject if they need one.
- Sat 15:15. Cross-review is deferred for this PR at Yehor's request; it only changes workflow docs and scripts.

## Handoff
- Done: see Status.
- How to test: `bash -n scripts/wt.sh`; `grep -rnE 'backend/|frontend/|pnpm' .agents/skills scripts AGENTS.md` returns nothing.
