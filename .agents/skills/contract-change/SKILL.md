---
name: contract-change
description: The only allowed way to add or change an API route, request/response shape, shared type, DB table, env var or port. Use before touching docs/CONTRACTS.md, backend/app/schemas.py or frontend/src/types.ts.
---

# contract-change

Contracts let the frontend and backend agents work in parallel. A silent change breaks someone else's work, sometimes hours later.

## 1. Prefer additive changes
- **OK without discussion:** adding a new route, adding a new **optional** field, adding an env var.
- **Needs agreement:** renaming or removing anything, changing a type, making a field required, changing the meaning of a field.

## 2. Announce it
Comment on the pinned **Contracts** issue (#1):
```bash
gh issue comment 1 --body "[<agent id>] contract change: <what>. Why: <why>. Breaking: yes/no. Affects: <areas>"
```
For a **breaking** change, wait for a human (or the owners of the affected areas) to reply before going on. Meanwhile, work on something else.

## 3. Make it a tiny separate PR
Do it on its own branch (`scripts/wt.sh new <owner> <area> contract-<name> -i 1`), changing only:
- `docs/CONTRACTS.md`
- `backend/app/schemas.py` (Pydantic models)
- `frontend/src/types.ts` (TypeScript types)
- a stub or mock route if it's new, so others can build against it straight away

Open the PR with `ship-pr`, labelled `contract`, and ask your human to merge it quickly.

## 4. After it merges
```bash
gh issue comment 1 --body "[<agent id>] merged: <pr url>. Everyone: git fetch && git rebase origin/main"
```
