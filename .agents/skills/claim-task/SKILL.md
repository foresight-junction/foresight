---
name: claim-task
description: Find, claim or create the GitHub issue for a piece of work before writing any code, so no two of the ~10 agents work on the same thing. Use at the start of every task.
---

# claim-task

## 1. Look at the board
Read issue #39 first: it gives the execution order (waves) and each task's dependencies. Wave 0 (#41, realigning the docs and board to the rulebook) comes before everything; until it lands, take only issues #41 lists as already consistent.
```bash
gh issue view 39
gh issue list --state open --label todo --label wave:<N> --limit 50
```

## 2. Pick or create the issue
- **Given an issue number:** use it.
- **Picking yourself:** choose an unclaimed `todo` issue in your area from the lowest wave that still has one, `p0` before `p1`. Its dependencies must be merged, or the issue must say to stub them.
- **No issue exists for your work:** create one.
  ```bash
  gh issue create --title "[<area>] <short task>" --label "todo,area:<area>,wave:<N>" \
    --body "Goal: <1-2 lines>\nDone when: <how to test it>"
  ```
  Then add a row for it to the table in #39 (comment there if you can't edit it).

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
