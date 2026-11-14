# Branch: leonardodadenchik/reward-rulebook-confirm

- **Issue:** #35
- **Owner:** leonardodadenchik (Denys)
- **Agent:** leonardodadenchik-claude-1 (lead)
- **Parent branch:** main
- **Created:** Sat 15:33

## Goal
Record Denys's confirmation of the SPEC §12 decisions so #10, #15, #6 and #7 can build on them. Done when SPEC §12 says the rows are confirmed and the PR is merged.

## Files and folders I own
- `docs/SPEC.md` §12 (confirmation note only)

## Don't touch
- `docs/ED_Management_Simulator_RU.md`, `docs/CONTRACTS.md`, HANDBOOK, any code

## Contracts used or changed
- None. Every SPEC §12 row is confirmed unchanged.

## Status
- [x] Denys confirmed all 15 Adopted rows and the 3 TUNE starting values (Sat 15:32)
- [x] Decision posted on #35; yehor-codex-3 told
- [x] SPEC §12 note
- [ ] PR, news on #1

## Decisions and notes
- Sat 15:32. No JavaScript prototype exists (Denys). Prototype parity dropped; his confirmation replaces it.
- Sat 15:32. TUNE values stay starting values; final numbers come from A6 (#8) before the 22:00 freeze.

## Handoff
- Done: SPEC §12 confirmation note.
- How to test: read SPEC §12; `git diff origin/main -- docs/SPEC.md` shows only the note.
