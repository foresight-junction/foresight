# Plan: four lanes, Sat 14:15 to Sun 10:00

Task board = GitHub Issues (`scripts/wt.sh board`). This file is the map; the issues are the truth. `scripts/bootstrap-board.sh` creates any issue whose code is missing.

## Where we stand (Sat 14 Nov, 14:15)
- The idea changed to **ED-72** (`docs/SPEC.md`). Custodian is dropped. The pivot is tracked in #28.
- Kostiantyn's branch `origin/kostiantyn/env-unfindable-slice` is reused for Harbor packaging only: `task.toml`, `collect.py`, `start.sh`, `tests/verify.py` and the test patterns. The Unfindable sim itself is not used.
- Issues #3 to #27 already exist with the same task codes. They need retitling to the meanings below.
- `main` still has only the agent kit. **No product code.**

## Lanes
| Lane | Label | Owns | Rubric it carries |
|---|---|---|---|
| **A. World and tools** | `area:env` | ED world: seeded patients, staff, beds, equipment, events. Sim, tool server, HANDBOOK | Meaningful difficulty (30) |
| **B. Reward and integrity** | `area:reward` | Scorer (M1 to M4), verifier, trivial-policy anchors, red-team | Reward integrity (25) |
| **C. Reference and experiments** | `area:ref` | Reference policy, agent runs, failure analysis | The gap (30) + the explanation half of difficulty |
| **D. Harness, repro and story** | `area:harness` | Harbor packaging, one-command eval, CI, README, demo, submission, stretch | Craft (15) + tiebreaker |

Fill in names in AGENTS.md section 1. D is also the integrator (merges PRs).

## Timeline
| When | Milestone | Proof |
|---|---|---|
| 14:15 to 18:00 | **Thin slice.** 24 sim hours, beds + staff + deterioration + `assess`, scorer M1 and M2, reference, one OpenCode run | `oracle` >= 0.9, `nop` = 0, one OpenCode run finishes |
| **18:00** | **Calibration checkpoint.** First real agent score. Gap or no gap? | Score + trajectory posted on issue |
| 18:00 to 22:00 | Full rules: fatigue, budget, equipment, events, M3, M4, anchors in CI, red-team round 1 at 19:00, one-command eval | All trivial policies <= 0.05 |
| **22:00** | **Rules freeze.** Tag `v1-rules`. Only bug fixes and knob tuning after this | Tag exists |
| 22:00 to 01:00 | Run matrix, failure analysis, red-team round 2 (23:30), README | `eval/results/summary.md` |
| 01:00 to 02:00 | Fresh-clone dry run on another laptop, demo script. Stretch only if all above is green | Fresh clone reproduces the table |
| Sun 08:00 to 10:00 | Demo video, submission. No code changes after 09:00 | Submitted |

**If the 18:00 run shows no gap:** lane A raises difficulty with the knobs in SPEC section 7. ED knobs: a higher share of wrong triage labels, more quiet deteriorations, a tighter budget, more patients or a heavier evening pattern, earlier or overlapping events. Lane C reruns. Decide by 19:00. Do not add trick wording or hide information to force a gap: that scores zero on 30 points.

## Tasks
P0 = needed for the thin slice. P1 = needed to submit. P2 = only if time.

### A. World and tools (`area:env`)
- **A1 P0** World generator: seeded patients (true acuity, label, condition, needs, duration), staff roster with skills and shifts, beds, equipment, event schedule.
- **A2 P0** Sim core: 15-minute tick loop, deterioration, treatment progress, event log, thin-slice tools (`board`, `patient`, `roster`, `assess`, `admit`, `assign`, `discharge`, `advance`, `clock`, `end_shift`).
- **A3 P0** Tool server: MCP streamable-http + `ward` CLI + `/health`.
- **A4 P1** Rules round 2: fatigue and sick-out, budget and overtime pricing, equipment and repairs, transfers and diversion, early-discharge returns, seeded events with notices.
- **A5 P1** HANDBOOK.md + instruction.md: every rate table and scored rule written down.
- **A6 P1** Difficulty config: one file of knobs, tuned with lane C.
- **A7 P2** Extra event types and a second hospital layout.

### B. Reward and integrity (`area:reward`)
- **B1 P0** Scorer: per-patient harm, modules M1 Outcome and M2 Timeliness, anchors, floor planner, normalisation. Pure function over the event log, unit tested (TDD).
- **B2 P0** Verifier: `collect.py` in the hospital container writes `/evidence/report.json`; `tests/test.sh` reads it and always writes a number; Harbor separate mode.
- **B3 P1** Trivial-policy anchors as scripted agents (do-nothing, FCFS by label, discharge-all, transfer-all, divert-all, call-in-everyone, random) + a CI test that each scores <= 0.05.
- **B4 P1** Red-team round 1 (19:00): 15 minutes, by someone who did not write the scorer. Log in docs/REDTEAM.md.
- **B5 P1** Red-team round 2 (23:30) after rules freeze, plus a regression test per finding.
- **B6 P1** Modules M3 Disposition and M4 Continuity (12-hour handover tail).

### C. Reference and experiments (`area:ref`)
- **C1 P0** Reference policy: `ed72/solution/`, public tools only, >= 0.9.
- **C2 P0** First OpenCode run at 18:00 on the thin slice. Post score and trajectory.
- **C3 P1** Run matrix: 3 seeds x 3 runs x up to 3 models, with mean and range.
- **C4 P1** Failure analysis by F1..F10 and by module: three trajectory excerpts, one chart. docs/FINDINGS.md.
- **C5 P1** Fairness audit: for each agent mistake, confirm the needed info was reachable. Fix the handbook where it was not.

### D. Harness, repro and story (`area:harness`)
- **D1 P0** Harbor spike: mostly done on Kostiantyn's branch (`docs/unfindable/SPIKE_S0_RESULTS.md`). Remaining: one real OpenCode model run against a stub hospital sidecar.
- **D2 P0** Task skeleton `ed72/`: copy the packaging from `origin/kostiantyn/env-unfindable-slice:harbor/unfindable/` (`task.toml` with separate mode, collect hook, compose healthcheck).
- **D3 P1** One-command eval: `make eval` runs reference, nop, stop-early (reference to hour 24 then `end_shift`), 3 agent runs, writes summary.md.
- **D4 P1** CI for the new layout: ruff + pytest on `ed72_sim` and the scorer, plus the anchors test.
- **D5 P1** README, 10-minute demo script, demo video, submission form.
- **D6 P2** Three seeds as three task folders + check the images build on x86 and ARM.
- **D7 P2** Stretch (`area:train`): fine-tune a small open model (about 4B) on reference trajectories on Modal, show before and after on one held-out seed.

## Standing rules for this challenge (also in AGENTS.md section 10)
1. Nothing that reveals the answer goes into the agent's container.
2. No randomness without the seed, no wall-clock time, no network, no LLM inside the sim or the scorer.
3. A new scoring rule or sim rate needs a handbook line in the same PR.
4. Any PR that touches scoring pastes the baseline table (reference, do-nothing, FCFS by label, discharge-all, transfer-all, divert-all, call-in-everyone, random).
5. Synthetic data only.
