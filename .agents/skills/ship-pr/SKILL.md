---
name: ship-pr
description: Open a pull request for a working slice of a task, after rebasing and reviews. Use when a feature or fix works end to end, or at least every 2 hours of work on a task.
---

# ship-pr

## 1. Sync with the target branch
Set `assigned_base` to the PR base Yehor assigned.
```bash
git fetch origin
git rebase "origin/$assigned_base"
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
gh pr create --base "$assigned_base" --title "<type>(<area>): <summary>" --body "$(cat <<EOF
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
For helper branches use `Refs #<issue>` in the PR body. The PR into `main` carries `Closes #<issue>`.

## 4. Update the board
```bash
gh issue edit <n> --remove-label doing --add-label review
gh issue comment <n> --body "[<agent id>] PR ready: <pr url>"
```

## 5. Hand off to Yehor

- Confirm CI is green and the gates in step 2 hold. Mark a draft ready with `gh pr ready <n>`.
- Name stacked dependencies in the description (`Depends on #N`) so the base merges first.
- Fix or respond to review findings, then comment `[<agent id>] ready to merge`.
- Yehor directs merges in dependency order under AGENTS.md golden rule 8. This applies to helper and integration PRs as well. Any merge or auto-merge requires his explicit direction.
- After the merge, comment on your issue with `[<agent id>] merged: <pr url>`. Ask Yehor for the next assignment.
