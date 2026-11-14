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

## 5. Merge (AGENTS.md golden rule 8)
Merge your own PR as soon as CI is green and the gates in step 2 hold:
```bash
gh pr checks <n> --watch        # wait for green; fix and push if red
gh pr merge <n> --merge         # never --delete-branch, never --admin to skip a red check
git fetch origin && gh run list --branch main --limit 1   # main must stay green
```
- Helper branches: merge into the parent branch the same way (`--base <parent>` PRs).
- Another task's PR: merge it only when its owner asked for that on the issue or PR.
- If `main` goes red after your merge, fix it or `git revert -m 1 <merge sha>` and push at once.
- Then comment on your issue: `[<agent id>] merged: <pr url>`, and on #1 if other lanes must rebase. Keep going on the next slice or claim a new task.
