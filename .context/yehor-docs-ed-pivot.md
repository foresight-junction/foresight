# Branch: yehor/docs-ed-pivot

- **Issue:** #28
- **Owner:** yehor
- **Agent:** yehor-claude-1 (lead), subagents 1a to 1d
- **Parent branch:** main
- **Created:** Sat 14:15

## Goal
Replace the Custodian idea with ED-72 (Emergency Department simulator, 72 sim hours) in every spec doc, including the scoring modules and the model and harness setup. Works when no doc on the branch describes Custodian and SPEC, CONTRACTS, PLAN and EVAL agree on names, tools and score shape.

## Files and folders I own
- `AGENTS.md` (sections 1, 4, 10 only)
- `docs/CHALLENGE.md`, `docs/SPEC.md`, `docs/CONTRACTS.md`, `docs/PLAN.md`, `docs/EVAL.md` (new)
- `scripts/bootstrap-board.sh`

## Don't touch
- `.agents/skills/`, `scripts/wt.sh`, `CLAUDE.md`
- Anything on `kostiantyn/env-unfindable-slice`

## Contracts used or changed
- `docs/CONTRACTS.md` is rewritten in full. Announced on issue #1. No product code on `main` depends on the old one.

## Status
- [x] Read earlier chats, research deep dive and Kostiantyn's Harbor spike
- [x] Issue #28 claimed, worktree created
- [x] Shared design brief written (names, tools, scoring modules, harness)
- [ ] Docs rewritten by four subagents, one file set each
- [ ] Consistency check across docs, noslop, commit, push
- [ ] Draft PR, retitle issues #3 to #27 after the team confirms

## Decisions and notes
- Sat 14:15. Only patient outcomes are scored. Fatigue, budget and bed use act through outcomes, so judges have no side metric to pump.
- Sat 14:15. Reward is normalised between the best trivial policy (anchor) and a full-information planner (floor), both replayed on the same seed inside the hospital container.
- Sat 14:15. A 12-hour handover tail after hour 72 is scored, so burning staff and budget in the last hours does not pay.
- Sat 14:15. Verifier uses Harbor separate mode plus a collect hook. Kostiantyn's spike showed a root agent can forge the reward in shared mode.
- Sat 14:15. The gap must come from information the agent chooses to gather (wrong triage labels, quiet deterioration, notices), because a fully visible ED is a scheduling problem an agent can code.

## Handoff
- Done: see Status.
- Merged as PR #29 (24f6abf). Issues #3 to #27 were retitled from the `mk` calls in `scripts/bootstrap-board.sh` after the merge, and B6 moved to p1.
- How to test: `grep -ri custodian AGENTS.md docs scripts` returns nothing; `bash -n scripts/bootstrap-board.sh` passes.
