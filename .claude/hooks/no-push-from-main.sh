#!/usr/bin/env bash
# PreToolUse hook for Bash: refuse `git push` while the checkout is on main or master.
# Allow rules can't see the current branch, and a bare `git push` from main would skip PRs and CI
# (AGENTS.md golden rule 8). Reads the hook JSON on stdin; prints a deny decision or nothing.
input="$(cat)"
case "$input" in
  *'"command":"git push'* | *'"command": "git push'*) ;;
  *) exit 0 ;;
esac
branch="$(git symbolic-ref --short -q HEAD)"
case "$branch" in
  main | master)
    printf '%s\n' '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"git push from main is blocked: work in a task worktree (scripts/wt.sh new) and open a PR; the integrator merges."}}'
    ;;
esac
exit 0
