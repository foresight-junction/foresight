---
name: claim-task
description: Find, claim or create the GitHub issue for a piece of work before writing any code, so no two of the ~10 agents work on the same thing. Use at the start of every task.
---

# claim-task

## 1. Look at the board
```bash
gh issue list --state open --limit 50
```

## 2. Pick or create the issue
- **Given an issue number:** use it.
- **Picking yourself:** choose a `todo` issue in your area that nobody has claimed. Prefer whatever unblocks others (contracts, shared types, API stubs).
- **No issue exists for your work:** create one.
  ```bash
  gh issue create --title "[<area>] <short task>" --label "todo,area:<area>" \
    --body "Goal: <1-2 lines>\nDone when: <how to test it>"
  ```

## 3. Check nobody else has it
```bash
gh issue view <n> --comments
```
If another agent's `claimed` comment is already there, **stop and pick a different issue**. The earliest claim wins.

## 4. Claim it
```bash
gh issue edit <n> --remove-label todo --add-label doing --add-assignee @me
gh issue comment <n> --body "[<agent id>] claimed. Branch: <branch>"
```

## 5. Set up the worktree (if you don't have one for this task yet)
```bash
scripts/wt.sh new <owner> <area> <task> -i <n>
```
Then work from that folder. Fill in the context file's **Goal**, **Files I own** and **Don't touch** sections before writing code.

## When blocked
```bash
gh issue edit <n> --remove-label doing --add-label blocked
gh issue comment <n> --body "[<agent id>] blocked on <what>, needs <who/what>"
```
Then comment on the blocking task's issue too.
