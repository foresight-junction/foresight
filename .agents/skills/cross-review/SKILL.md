---
name: cross-review
description: Get an independent code review from the other AI model (Claude reviews Codex's work, Codex reviews Claude's) before opening a PR, and for a second opinion when a bug survives two fix attempts.
---

# cross-review

Two different models catch different mistakes. The reviewer is always **the other model**, never yourself.

## 1. Prepare the diff
```bash
git fetch origin
git diff origin/main...HEAD > /tmp/review-$(git rev-parse --short HEAD).diff
```
(For a helper branch, diff against its parent branch instead of `origin/main`.)

## 2. Ask the other model

Use this prompt, filling in the brackets:

> You are reviewing a hackathon PR. Task: [one line from the issue]. Contracts are in docs/CONTRACTS.md.
> Review the diff for, in order: (1) bugs and broken logic, (2) security problems (secrets, injection, unsafe input handling), (3) mismatches with docs/CONTRACTS.md, (4) calls to APIs or functions that may not exist, (5) AI slop (swallowed errors, dead code, needless abstraction).
> List only real problems, most serious first, with file:line and a one-line fix. Skip style preferences. If there are none, say "LGTM".

- **If you are Claude:** call the `codex` MCP tool with the prompt and the diff (or point it at the diff file, with `cwd` set to this worktree and read-only intent). Also run `/code-review` if the plugin is installed.
  If the `codex` MCP tool is not connected, run the Codex CLI non-interactively in a read-only sandbox, with the diff on stdin (it is appended to the prompt):
  `codex exec -s read-only -C "$(pwd)" "<prompt>" < /tmp/review-<hash>.diff`
- **If you are Codex:** run
  `claude -p "<prompt>" < /tmp/review-<hash>.diff`
  and use `/review` as well.

## 3. Triage
- **Fix:** bugs, security problems, contract mismatches, non-existent APIs.
- **Consider:** slop findings. Fix them if it's quick.
- **Ignore:** style preferences and "consider adding X" suggestions that aren't needed for the demo.
- If you disagree with a finding, write one line saying why in the PR body.

## 4. Limit
At most **2 review rounds** per PR. After that, ship and note any open points in the PR body.

## Second-opinion mode (stuck on a bug)
Send the other model: the error output, the relevant files, and what you've already tried. Ask it to diagnose before suggesting a fix. Don't let it edit your worktree. Apply the fix yourself.
