# Branch: yehor/harness-agent-comms

- **Issue:** #50
- **Owner:** yehor
- **Agent:** yehor-claude-4
- **Parent branch:** main
- **Created:** Sat 17:00

## Goal
Agents can check in one command whether a worktree or task is in use before handing it over, and a short comment format plus `wt.sh inbox` gets messages to them fast.

## Files and folders I own
- `scripts/wt.sh` (new `status` and `inbox` commands)
- AGENTS.md §4 (messages) and §5 (command list), CLAUDE.md subagents bullet, `.agents/skills/claim-task/SKILL.md`

## Don't touch
- Everything else

## Contracts used or changed
- None. `WT_IDLE_MIN` is a local knob for the dev script (like `SKIP_INSTALL`), not a service env var.

## Status
- [x] `wt.sh status`, `wt.sh status <slug|branch>`, `wt.sh inbox <id>`
- [x] Rules in AGENTS.md, CLAUDE.md, claim-task
- [ ] PR merged by a human

## Decisions and notes
- Sat 17:15: BUSY = a live process with cwd in the worktree, or a commit, push or uncommitted edit within 30 min. Busy exits 1, so scripts can gate on it.
- Inbox narrows with GitHub search (`in:comments`) first: ~2 s instead of ~11 s for fetching every open issue's comments.
- Processes come from `lsof -d cwd`, so they're only visible on the same laptop. For other laptops, status shows only the pushed tip and comments, and says so.

## Handoff
- Done: everything above, tested by hand against live worktrees (correctly flagged yehor-reward-baselines BUSY while another agent ran pytest there, and mykhailo/env-tool-server from another laptop via its 2-minute-old push).
- Test: `scripts/wt.sh status`, `scripts/wt.sh status <slug>; echo $?`, `scripts/wt.sh inbox yehor-claude-3a`.
