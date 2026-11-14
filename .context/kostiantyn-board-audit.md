# Board audit, Sat 14 Nov ~14:50 UTC

By kostiantyn-claude-3 for #41 (board half). Sources: `gh issue list/view`, `gh pr list`, `git ls-remote`, `git log origin/<branch>`, and `scripts/board-check.sh`. The game rules come from `docs/ED_Management_Simulator_RU.md`; the docs come from PR #43 (head a8b1d6f).

Classes: **a** = consistent with the rulebook, **b** = needs rescoping, **c** = obsolete or done, **d** = a gap no issue covers.

## Open issues

| # | Code | Labels (status, prio, wave) | Assignee | Branch (last commit, UTC) | PR | Class | Notes |
|---|---|---|---|---|---|---|---|
| 2 | none | doing, no prio, no wave | xand1ex999 | kostiantyn/env-unfindable-slice (12:07) | none | c | Old Unfindable submission path, superseded by #21/#22. Has no claim comment. A human should close it |
| 3 | A1 | doing p0 w1 | xand1ex999 | kostiantyn/env-world (14:35) | #46 | a | |
| 4 | A2 | doing p0 w2 | xand1ex999 | kostiantyn/env-sim-core (14:35) | none | a | Body realigned 14:47. Owns all of `ed72_sim/`, which overlaps A1, A4, A7, B1, B3, B5, B6 |
| 5 | A3 | doing p0 w3 | mykhailo311 | mykhailo/env-tool-server (not pushed) | none | a | **Double claim:** mykhailo-claude-1 at 14:35, then kostiantyn-codex-5 announced it on #1 at 14:36 |
| 6 | A4 | todo p1 w4 | none | none | none | a | |
| 7 | A5 | doing p1 w5 | xand1ex999 | kostiantyn/env-handbook (not pushed) | none | a | Claimed by kostiantyn-codex-5. Body does not spell out reward = score/100, first covered tick, the 0.3 rule or €24 000 (check 6) |
| 8 | A6 | todo p1 w5→6 | none | none | none | a | Depends on #17, which moves to wave 5 |
| 9 | A7 | todo p2 w7 | none | none | none | a | |
| 10 | B1 | doing p0 w2 | xand1ex999 | kostiantyn/reward-scorer (14:35) | #47 | a | Body realigned 14:47 (O, T, W, B) |
| 11 | B2 | doing p0 w2→3 | xand1ex999 | kostiantyn/reward-verifier (14:35) | #45 | a | Depends on #22, which moves to wave 2 |
| 12 | B3 | todo p1 w4 | none | none | none | a | Reactive proxy, stop-early and the §13 exploit baselines |
| 13 | B4 | todo p1 w5 | none | none | none | b | Attack list still says discharge, transfer and negative advance. kostiantyn-claude-1 is fixing it |
| 14 | B5 | todo p1 w6 | none | none | none | a | |
| 15 | B6 | todo p1 w5 | none | none | none | a | Both §13 fixes |
| 16 | C1 | doing p0 w3→4 | xand1ex999 | kostiantyn/ref-policy (not pushed) | none | a | Claimed by kostiantyn-codex-5. Depends on #5 (wave 3) |
| 17 | C2 | todo p0 w4→5 | none | none | none | a | Depends on #16 |
| 18 | C3 | todo p1 w6 | none | none | none | a | |
| 19 | C4 | todo p1 w6→7 | none | none | none | a | Depends on #18 (wave 6) |
| 20 | C5 | todo p1 w6→8 | none | none | none | b | Example says "true acuity through assess". kostiantyn-claude-1 is fixing it |
| 21 | D1 | doing p0 w1 | yehorm14 | yehor/harness-harbor-spike (14:22) | none | a | |
| 22 | D2 | doing p0 w1→2 | yehorm14 | yehor/harness-task-skeleton (14:23) | none | a | Depends on #21 (wave 1) |
| 23 | D3 | todo p1 w5 | none | none | none | a | |
| 24 | D4 | review p1 w3 | yehorm14 | yehor/harness-ci (never pushed) | landed in #38 | c | Done in #38 per yehor-claude-2. Body still mentions an anchors test. Owner should close it |
| 25 | D5 | todo p1 w7→8 | none | none | none | a | Depends on #19 |
| 26 | D6 | todo p2 w7 | none | none | none | a | |
| 27 | D7 | todo p2 w7 | none | none | none | a | |
| 31 | A8 | todo p1 w4 | none | none | none | a | Old body layout (no "Files you own" line) |
| 32 | A9 | doing p0 w1 | xand1ex999 | kostiantyn/env-crn (14:40) | #44 | a | Body realigned 14:47 |
| 34 | B8 | todo p1 w5→6 | none | none | none | a | Depends on #15 (wave 5) |
| 35 | B9 | todo p0 w1 | none | none | none | a | §14 decisions, still waiting on Denys |
| 36 | C6 | todo p1 w6→7 | none | none | none | a | Depends on #8 |
| 37 | D8 | doing p1 w4 | leonardodadenchik | leonardodadenchik/harness-model-budget (not pushed) | none | b | Body still says `advance(minutes)`, 21 tools, 600 calls. A comment with the replacement lines is posted; waiting on the owner |
| 41 | W0 | review p0 w0 | xand1ex999 | kostiantyn/docs-rules-realign (14:39) | #43 | a | |

Closed since Friday: #28 and #30 (done), #33 B7 (not planned: the rulebook has no full-information planner), #40 (done). Merged PRs: #29, #38, #42.

## Gaps against the rulebook (class d)

Every item on the checklist is covered, so no new issue is needed:

- Agent interface (`rules`, `observe`, `step(actions)`, rejection reasons, 500-call cap): #5, with shapes in CONTRACTS v1.
- Timeout over 144 ticks: #11 and #15 (`ended=timeout`), #37 (measured budget).
- O/T/W/B scorer: #10.
- Reactive-proxy and stop-early baselines: #12.
- Both §13 fixes: #15 (scored) and #34 (probes).
- §14 decisions: SPEC §12 in PR #43, confirmed by #35.
- Agent-visible rules: #7.
- Engine location: settled as `ed72/environment/hospital/ed72_sim/` (SPEC §9, #1 news from kostiantyn-claude-2). `backend/app/edsim/` is not used.

## Process findings

1. **#5 is double-claimed.** mykhailo-claude-1 claimed it first (the earliest claim wins, AGENTS.md §4), so kostiantyn-codex-5 should stand down.
2. **Claims with no pushed branch:** #5, #7, #16, #37 and #24 (#24 landed in #38 instead).
3. **No branch has gone 2 hours without a commit** among the doing issues. The exceptions are #2's branch (12:07) and `research` (Fri).
4. **Branches with no issue:** `kostiantyn/env-ed-sim` (old engine, retired by the SPEC §9 decision), `kostiantyn/env-unfindable-slice` (#2's work, never linked) and `research` (prize notes). Only a human can delete branches.
5. **The same files on four branches:** one `ed72_sim` foundation commit (pyproject, constants.py, model.py, rng.py) is in PRs #44, #46, #47 and #45. Merge one first; the others then rebase onto main without conflicts on those files.
6. **Overlapping ownership:** #4 owns all of `ed72_sim/`, and the per-module tasks own subfolders. #11 and #15 both own `collect.py` (B6 says to coordinate). #13 and #14 share `docs/REDTEAM.md`, #17 and #18 share `eval/results`, and #19 and #20 share `docs/FINDINGS.md`. These pairs run one after the other, which is acceptable; #4's line should list only the engine files.
7. **Waves that contradict dependencies:** #22, #16, #34, #19 and #20 sat in the same wave as a dependency. The fix moves 10 issues (see #39).
8. **#2 and #24** are done or superseded but still open.
9. **AGENTS.md §10 rule 5** still lists the PR #29 baselines (FCFS-by-label, discharge-all, transfer-all, call-in-everyone, random). Rule 1 (main image: handbook and the `ward` CLI) matches SPEC §9.
10. **`scripts/bootstrap-board.sh`** still creates the PR #29 board (21 tools, M1 to M4, anchors) and has no A8, A9, B8, B9, C6, D8 or wave labels. Running it would duplicate those six. It is regenerated on this branch.
