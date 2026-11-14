# Branch: kostiantyn/docs-board-sync

- **Issue:** #41 (board half)
- **Owner:** kostiantyn
- **Agent:** kostiantyn-claude-3 (lead)
- **Parent branch:** main
- **Created:** Sat 14:48

## Goal
Make the board, #39 and `scripts/bootstrap-board.sh` tell the same story as the RU rulebook and PR #43. Done when `scripts/board-check.sh` shows only failures that need a human (listed in Handoff).

## Files and folders I own
- `scripts/board-check.sh` (new, read-only), `scripts/bootstrap-board.sh`
- `.context/kostiantyn-board-audit.md`, this file
- Wave labels and the #39 table (agreed with kostiantyn-claude-1, the #39/#41 owner)

## Don't touch
- Issue bodies, titles, closes: kostiantyn-claude-1 (split agreed Sat 14:52)
- `docs/SPEC.md`, `CONTRACTS.md`, `EVAL.md`, `PLAN.md` (PR #43), `docs/ED_Management_Simulator_RU.md`
- `AGENTS.md` until #43 merges and Yehor agrees on #40

## Contracts used or changed
- None changed. Reads PLAN.md codes from PR #43.

## Status
- [x] Audit: `.context/kostiantyn-board-audit.md`, summary on #41
- [x] Waves re-derived: 7 unclaimed relabelled, 3 claimed proposed (#22, #11, #16), #39 table edited
- [x] `scripts/board-check.sh` written and run
- [x] `scripts/bootstrap-board.sh` regenerated from the live board (31 codes, wave labels); `bash -n` and a stubbed parse pass; never run
- [ ] AGENTS.md §10 rule 5 + realignment line: separate PR after #43, after asking on #40

## Decisions and notes
- Sat 14:55: wave = 1 + highest hard dependency wave; "(stub)" and "agree with" deps are soft. Max wave is now 8.
- Sat 15:00: bootstrap bodies are copied verbatim from the live issues (banner included), so the script and the board match exactly. If bodies change, regenerate from `gh issue list --json` into quoted heredocs.
- No new issues: every rulebook item already has one (audit, "Gaps").

## Handoff
- Done: see Status.
- Needs humans: close #2 and #24; settle #5 double claim (mykhailo-claude-1 first); owners OK the #22/#11/#16 wave labels; merge order for the four PRs sharing the ed72_sim foundation commit (#44-#47).
- How to test: `scripts/board-check.sh origin/kostiantyn/docs-rules-realign` (read-only). `bash -n scripts/bootstrap-board.sh`.
