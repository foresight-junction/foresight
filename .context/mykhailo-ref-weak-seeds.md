# Branch: mykhailo/ref-weak-seeds

- **Issue:** #106
- **Owner:** mykhailo
- **Agent:** mykhailo-claude-1q (subagent of mykhailo-claude-1)
- **Parent branch:** main

## Goal
Analysis of where the unmodified reference loses points on weak seeds, plus proposals (not applied) for its owner. No edit to ed72/solution/.

## Files and folders I own
- analysis/weak_seeds/**, this file

## Don't touch
- ed72/solution/ (kostiantyn-codex-16), ed72/environment/

## Contracts used or changed
- none

## Status
- [x] Reproduce per-seed numbers (42, 1-5, 11-20): matches #103 (seed 2 = 88.6, held-out min 84.4 on seed 11)
- [x] Breakdown of weak seeds 11, 2, 19 (run.py --detail)
- [x] Scratch experiments outside the repo; proposals P1, P2 validated on seeds 21-50 and 100-139
- [x] README + proposals.patch

## Decisions and notes
- Simulator needs Python 3.12: run with `uv run --python 3.12 python analysis/weak_seeds/run.py`.
- Findings: loss is ESI 4-5 queue after the bus crash (ticks 96-143). Seed 2: staff rest en masse at ticks 120-132 because the wide plan only runs for uncovered ESI 1-2. Seed 11: doctors reach fatigue 80+, W loss.
- Proposals: P1 widen plan (cap 60) when >=3 uncovered; P2 LAST_HIRE_TICK 135 to 115 (only safe with P1).

## Handoff
Done: analysis, proposals with before/after on 16 + 30 + 40 seeds. Next: the reference owner decides on proposals.patch (needs a pin before #18). Test: `uv run --python 3.12 python analysis/weak_seeds/run.py --detail 2 11`.
