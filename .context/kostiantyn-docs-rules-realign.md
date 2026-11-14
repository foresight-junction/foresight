# Branch: kostiantyn/docs-rules-realign

- **Issue:** #41
- **Owner:** kostiantyn
- **Agent:** kostiantyn-claude-1 (lead), Sonnet subagents for EVAL/PLAN and issue updates
- **Parent branch:** main (e7db0e2)
- **Created:** 2026-11-14

## Goal
Make SPEC, CONTRACTS, EVAL, PLAN and the issue board describe the game in `docs/ED_Management_Simulator_RU.md`, which AGENTS.md §1 (PR #38) names the source of truth. Done when PR #43 merges and the grep in #41's acceptance criteria returns only intended matches.

## Files and folders I own
- `docs/SPEC.md`, `docs/CONTRACTS.md` (via contract-change, announced on #1), `docs/EVAL.md`, `docs/PLAN.md`
- This context file

## Don't touch
- `docs/ED_Management_Simulator_RU.md` (Denys's; decisions go in SPEC §12)
- `AGENTS.md` (Yehor, #40; asked him there to update line 116)
- Anything under `ed72/`, `backend/`, `.agents/skills/`

## Contracts used or changed
- CONTRACTS v1: tools `rules`, `observe`, `step(actions)`; Action, ActionResult, Observation, event log, score object. Breaking for v0, which nothing implements. Announced on #1.

## Status
- [x] Claimed #41, announced on #1
- [x] SPEC and CONTRACTS rewritten (c5920fb), draft PR #43
- [x] EVAL and PLAN rewritten (376491b); additive log/scorer details from kostiantyn-claude-2 folded into CONTRACTS (5b37499), announced on #1
- [x] Affected issues commented and updated (bodies edited where unclaimed; #3, #4, #10, #11, #32 claimed by kostiantyn-claude-2, comment only); #33 closed as not planned; #34, #36 retitled; #39 updated
- [x] PR #43 marked ready for review; merge is a human step

## Decisions and notes
- 2026-11-14: All rulebook [Proposed] rules adopted as defaults (AGENTS.md §1 already says build them). Both §13 exploit fixes adopted. Missing numbers set as TUNE in SPEC §12 (arrivals 1.5/tick ±50% peak 15:00; flu mix 40/35/25; W a=1.0, b=0.05; linear budget curve).
- 2026-11-14: Agent interface = MCP `rules`/`observe`/`step`, cap 500 calls, so OpenCode makes about one call per tick.
- 2026-11-14: Simulator location settled as `ed72/environment/hospital/`; `backend/app/edsim/` is not used.

## Handoff
- Done: see Status.
- Next: lane owners review PR #43 (tool shapes A, score B, baselines C); a human merges; then post the merge notice on #1. Yehor to align AGENTS.md line 116 (asked on #40).
- How to test: `grep -n -E "advance\(|M1|M2|H_anchor|H_floor|wrong triage" docs/SPEC.md docs/CONTRACTS.md docs/EVAL.md docs/PLAN.md` returns nothing.
