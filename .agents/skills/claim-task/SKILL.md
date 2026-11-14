---
name: claim-task
description: Verify and claim the GitHub issue Yehor assigned before writing code. Use at the start of every task.
---

# claim-task

## 1. Check your assignment

Read #39 and #113 for release order and dependencies. Use the issue, branch, worktree, and PR base Yehor assigned. If you need an issue, a scope change, or a new assignment, ask Yehor before starting the work.

## 2. Check the claim

```bash
gh issue view <n> --comments
```

If someone else has claimed the issue, ask Yehor to resolve the conflict.

For a takeover directed by Yehor, check the live state before touching the worktree:

```bash
scripts/wt.sh status <slug|branch>
```

If the worktree is busy, coordinate the handoff with its active owner and Yehor. Once idle, record the handoff on the issue.

## 3. Record your claim
```bash
gh issue edit <n> --remove-label todo --add-label doing --add-assignee @me
gh issue comment <n> --body "[<agent id>] claimed. Branch: <branch>"
```

## 4. Set up the assigned worktree (if needed)
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
