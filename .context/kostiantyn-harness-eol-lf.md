# Branch: kostiantyn/harness-eol-lf

- **Issue:** #22
- **Owner:** kostiantyn
- **Agent:** kostiantyn-claude-3 (lead)
- **Parent branch:** main
- **Created:** Sat 16:00

## Goal
`.gitattributes` forcing LF in working trees, so `harbor run -p ed72` from a Windows checkout (core.autocrlf=true) doesn't copy CRLF scripts into the Linux images (#22, 15:58).

## Files and folders I own
- 

## Don't touch
- 

## Contracts used or changed
Anything from docs/CONTRACTS.md this branch depends on or changes.
- 

## Status
- [x] `.gitattributes`: `* text=auto eol=lf`, explicit LF for *.sh, `ed72/environment/ward`, Dockerfile; binaries marked
- [x] Verified: all committed blobs are already LF (no renormalize diff); re-checked-out scripts have 0 CR with autocrlf=true

## Decisions and notes
Short and dated: why we chose X, new dependencies and why, gotchas.
- 

## Handoff
Done / not done / how to test. Keep this current: another agent may pick it up.
- Done. Existing Windows worktrees keep their CRLF copies until refreshed (see PR body).
- Test: on Windows, `git ls-files --eol ed72/environment/ward` shows `w/lf` after refreshing.
