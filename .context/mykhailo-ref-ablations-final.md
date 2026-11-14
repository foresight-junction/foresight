# Branch: mykhailo/ref-ablations-final

- **Issue:** #36
- **Owner:** mykhailo
- **Agent:** mykhailo-claude-1o
- **Parent branch:** main

## Goal
Rerun the F1-F6 lever ablations at the shipped config (arrival_mean 4.0, seeds 42, 1, 2, 3) and document them.

## Files and folders I own
- analysis/ablations/**, this file

## Don't touch
- ed72/, docs/FINDINGS.md (kostiantyn-claude-1, #19)

## Status
- [x] Rerun on main 4b51656 with --policy reference
- [x] Compare stand-in vs reference (87.8 vs 92.5)
- [x] F3 lockstep check tightened to decision level (ESI 1-2 admits)
- [x] README tables and FINDINGS-section.md

## Decisions and notes
- Stand-in not retuned: 4.7 below the reference, still strong; its B is 1.000, the reference's 0.705.
- F1 ownership check stays at action-type level (admit sets differ in 86/432 ticks by design).
- F4 is noisy (-15.4 to +9.0 per seed), reported as inert on the mean.

## Handoff
Done: all of the above. Next: #19 owner pastes analysis/ablations/FINDINGS-section.md into docs/FINDINGS.md.
Test: cd analysis/ablations && uv run --python 3.12 --with pytest pytest -q (24 pass).
