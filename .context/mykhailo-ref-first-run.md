# Branch: mykhailo/ref-first-run

- **Issue:** #17
- **Owner:** mykhailo
- **Agent:** mykhailo-claude-1 (lead), mykhailo-claude-1g (rehearsal)
- **Parent branch:** main
- **Created:** Sat 15:15

## Goal
Prove the full Harbor pipeline (real sim, tool server, collect, verifier, packaging) runs end to end
before the first model run: `nop` scores 0 and a scripted `ward` agent scores above 0.

## Files and folders I own
- `eval/results/` (rehearsal and run notes)
- `.context/mykhailo-ref-first-run.md`

## Don't touch
- `ed72/` on any real branch (integration fixes go to the owning issues as findings)
- `ed72/solution/` (lane C, #16)

## Contracts used or changed
- Uses Tools v1 (`rules`, `observe`, `step`) and the report shape read by `tests/verify.py`. Changes none.

## Status
- [x] Throwaway integration tree from main + #44 #45 #46 #47 #48 #5 #22 branches (detached, never pushed)
- [x] Placeholder HANDBOOK.md, instruction.md, rehearsal solve.sh in the throwaway tree only
- [x] `harbor run -a nop`: reward 0
- [x] `harbor run -a oracle` with the placeholder policy: reward 0.773134
- [ ] First OpenCode + Gemini run (needs GEMINI_API_KEY, 18:00)

## Decisions and notes
- Sat: Git for Windows checks out `ward`, `start.sh`, `test.sh` with CRLF; the rehearsal tree adds
  `.gitattributes` (`* text=auto eol=lf`). The real fix belongs to #22.
- The rehearsal policy is a placeholder, not #16's reference policy.
- One `ward` call takes about 3.5 s here: 144 ticks is about 8.5 min of tool latency.

## Handoff
- Done: `eval/results/rehearsal-2026-11-14.md` has commands, merged commits, rewards, glue findings.
- Next: OpenCode + Gemini run on the integration tree; rerun once #5/#45/#22/#7/#16 are on main.
- Test: rebuild the tree as in the note, then `harbor run -p ed72 -a nop` (expect 0).
