---
name: ship-pr
description: Open a pull request for a working slice of a task, after rebasing and reviews. Use when a feature or fix works end to end, or at least every 2 hours of work on a task.
---

# ship-pr

## 1. Sync with the target branch
Target is `main` for normal tasks, or the parent branch for helper branches (`--codex` / `--claude`).
```bash
git fetch origin
git rebase origin/main      # or origin/<parent branch>
```
**Resolving conflicts:**
- Keep both sides' intent. Never delete another task's code to make a conflict go away.
- If the conflict is in a file another task owns and you aren't sure, stop. Comment on that task's issue and ask.
- After resolving, rerun the app.

## 2. Gates
- `pre-commit-gate` passes.
- `cross-review` is done and real problems are fixed.
- The context file's **Handoff** section says: what's done, what's not, and how to test it.

## 3. Push and open the PR
```bash
git push --force-with-lease -u origin HEAD     # only your own branch, after rebase
gh pr create --base main --title "<type>(<area>): <summary>" --body "$(cat <<EOF
Closes #<issue>

## What
<2-4 bullet points>

## How to test
<exact steps or commands>

## Notes
<review findings you didn't act on, known gaps, mocks still in place>

Agent: <agent id>
EOF
)"
```
For helper branches use `--base <parent branch>` and `Refs #<issue>` instead of `Closes`.

## 4. Update the board
```bash
gh issue edit <n> --remove-label doing --add-label review
gh issue comment <n> --body "[<agent id>] PR ready: <pr url>"
```

## 5. Hand it to the integrator (AGENTS.md golden rule 8)
Only the integrator (AGENTS.md section 1) merges into `main`. When CI is green and the gates in step 2 hold:
```bash
gh pr checks <n> --watch        # wait for green; fix and push if red
gh pr ready <n>
gh pr comment <n> --body "[<agent id>] ready to merge"
```
- Name stacked dependencies in the description (`Depends on #N`) so the base merges first.
- If the integrator comments a blocker, fix it, push, and reply on the PR.
- Helper branches: the task's lead merges them into the parent branch (`--base <parent>` PRs) with `gh pr merge <n> --merge`, never `--delete-branch` or `--admin`.
- After the merge, comment on your issue: `[<agent id>] merged: <pr url>`. Keep going on the next slice or claim a new task.
