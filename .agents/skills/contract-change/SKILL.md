---
name: contract-change
description: The only allowed way to add or change an ED-72 tool name or its args/result shape, the score object, an event-log line, an env var or a port. Use before touching docs/CONTRACTS.md or the Python types that implement a contract.
---

# contract-change

Contracts let lanes A, B, C and D work in parallel: tool shapes, the score object, event-log lines, env vars and ports. A silent change breaks someone else's work, sometimes hours later.

## 1. Prefer additive changes
- **OK without discussion:** adding a new tool, adding a new **optional** field, adding an env var.
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
- the code that implements the shape: the types in `ed72/environment/hospital/ed72_sim/`, and `frontend/src/replay/types.ts` if the replay viewer reads it
- the agent-visible rules (`HANDBOOK.md` or the rules tool), if the agent can see the change
- a stub tool or fixture returning the new shape, so other lanes can build against it straight away

Open the PR with `ship-pr`, labelled `contract`, and comment `ready to merge` on it (`ship-pr` step 5) once CI is green and nobody has objected on #1 for 15 minutes; the integrator merges it.

## 4. After it merges
```bash
gh issue comment 1 --body "[<agent id>] merged: <pr url>. Everyone: git fetch && git rebase origin/main"
```
