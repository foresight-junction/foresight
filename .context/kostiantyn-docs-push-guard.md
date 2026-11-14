# Branch: kostiantyn/docs-push-guard

- **Issue:** #41 (board half); also answers #23, #54 review, #67, #69
- **Owner:** kostiantyn
- **Agent:** kostiantyn-claude-3 (lead)
- **Parent branch:** main
- **Created:** Sat 15:19

## Goal
Close the push holes Codex found in `.claude/settings.json` (#54, #61), list the `make eval` env vars in CONTRACTS, and keep `scripts/board-check.sh` and `scripts/bootstrap-board.sh` matching the board. Done when PR #61 merges and `scripts/board-check.sh origin/main` passes checks 2 and 3.

## Files and folders I own
- `.claude/settings.json`, `.claude/hooks/no-push-from-main.sh`
- `scripts/board-check.sh`, `scripts/bootstrap-board.sh`
- `docs/CONTRACTS.md` env table rows `ED72_MODEL`, `HARBOR` (additive, announced on #1)

## Don't touch
- `.env.example` and `eval/`: #53 / #23 own the `make eval` block
- AGENTS.md and the skills: the integrator (kostiantyn-claude-4) owns the merge rules since #66

## Contracts used or changed
- CONTRACTS env table: + `ED72_MODEL`, + `HARBOR` (host only, additive). Announced on #1 at 15:2x.

## Status
- [x] Deny rules: pushes to main (`main`, `*:main`, `*:refs/heads/main`), `--mirror`, `--all`, `--prune`
- [x] PreToolUse hook `.claude/hooks/no-push-from-main.sh`: refuses any `git push` while the checkout is on main or master. It covers the bare `git push` that allow rules can't tell apart (Codex P1 on #61)
- [x] CONTRACTS env rows; main's `.env.example` block from #53 kept in the merge
- [x] board-check: counts completed tasks in check 2; ignores merged dependencies in check 3
- [x] bootstrap-board.sh: + A10 (#67), + C7 (#69)

## Decisions and notes
- Sat 15:35: a hook rather than more deny patterns, because deny rules match text and can't see which branch is checked out; `git push` with no arguments from main looks the same as from a task branch.
- Sat 15:25: kostiantyn-claude-4 is the only integrator (#66), so this branch is never self-merged.

## Handoff
- Done: everything in Status. Not done: nothing on this branch; merging is the integrator's job.
- How to test:
  - `python -c "import json;json.load(open('.claude/settings.json'))"`
  - Hook: in a repo on `main`, `echo '{"tool_input":{"command":"git push"}}' | bash .claude/hooks/no-push-from-main.sh` prints a deny decision; on a task branch it prints nothing.
  - `bash -n scripts/*.sh && scripts/board-check.sh origin/main` (checks 2 and 3 pass; the remaining failures are owner items).
