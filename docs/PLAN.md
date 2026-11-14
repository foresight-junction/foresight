# Plan: four lanes, Sat 14:15 to Sun 10:00

Task board = GitHub Issues (`scripts/wt.sh board`). This file is the map; the issues are the truth. `scripts/bootstrap-board.sh` creates any issue whose code is missing.

## Where we stand (Sat 14 Nov, 14:15)
- The game is **ED-72**. The rules are the RU rulebook `docs/ED_Management_Simulator_RU.md` (PR #38), realigned into `docs/SPEC.md` and `docs/CONTRACTS.md` by #41 (PR #43). The pivot is tracked in #28.
- Execution order is the pinned issue #39, with wave labels `wave:0` to `wave:7`.
- Kostiantyn's branch `origin/kostiantyn/env-unfindable-slice` is reused for Harbor packaging only: `task.toml`, `collect.py`, `start.sh`, `tests/verify.py` and the test patterns. The Unfindable sim itself is not used.
- Issues #3 to #27 already exist with the same task codes. They need retitling to the meanings below.
- `main` still has only the agent kit. **Nothing under `ed72/` exists on main yet.**

## Lanes
| Lane | Label | Owns | Rubric it carries |
|---|---|---|---|
| **A. World and tools** | `area:env` | ED world: seeded patients, staff, beds, CT, events. Sim, tool server, HANDBOOK | Meaningful difficulty (30) |
| **B. Reward and integrity** | `area:reward` | Scorer (O, T, W, B), verifier, baselines, red-team | Reward integrity (25) |
| **C. Reference and experiments** | `area:ref` | Reference policy, agent runs, failure analysis | The gap (30) + the explanation half of difficulty |
| **D. Harness, repro and story** | `area:harness` | Harbor packaging, one-command eval, CI, README, demo, submission, stretch | Craft (15) + tiebreaker |

Fill in names in AGENTS.md section 1. One integrator, `kostiantyn-claude-4`, merges every PR into `main` in dependency order (AGENTS.md golden rule 8) and watches that `main`'s CI stays green.

## Timeline
| When | Milestone | Proof |
|---|---|---|
| 14:15 to 18:00 | **Thin slice.** Seeded world, 144-tick engine, `rules` / `observe` / `step`, scorer O and T, reference, one OpenCode run | `oracle` clearly above `nop`, `nop` = 0, one OpenCode run finishes |
| **18:00** | **Calibration checkpoint.** First real agent score. Gap or no gap? | Score + trajectory posted on issue |
| 18:00 to 22:00 | Full rules: fatigue, budget, events and warnings, W and B, baselines in CI, red-team round 1 at 19:00, one-command eval | Ordering test green: stop-early < reactive proxy < reference; do-nothing = 0 |
| **22:00** | **Rules freeze.** Tag `v1-rules`. Only bug fixes and knob tuning after this | Tag exists |
| 22:00 to 01:00 | Run matrix incl. held-out seeds, failure analysis, red-team round 2 (23:30), README | `eval/results/summary.md` |
| 01:00 to 02:00 | Fresh-clone dry run on another laptop, demo script. Stretch only if all above is green | Fresh clone reproduces the table |
| Sun 08:00 to 10:00 | Demo video, submission. No code changes after 09:00 | Submitted |

**If the 18:00 run shows no gap:** lane A raises difficulty with the knobs in SPEC section 7: arrival rate and daily cycle, flu-wave mix, event windows, shorter warning lead time, a tighter budget, W weights, overlapping events. Lane C reruns. Decide by 19:00. Do not add trick wording or hide information to force a gap: that scores zero on 30 points.

## Tasks
P0 = needed for the thin slice. P1 = needed to submit. P2 = only if time.

### A. World and tools (`area:env`)
- **A1 P0** Seeded world: beds R1-R3, A1-A8, F1-F6; staff D1-D6 and N1-N9; arrivals with a daily cycle, ESI mix and CT need; four events; separate random streams.
- **A2 P0** Engine: 144 ticks of 30 minutes, the 8-step tick order, admission rules, coverage, treatment, hazards, fatigue and fainting, event log, Python `observe` and `step`.
- **A3 P0** Tool server: MCP tools `rules`, `observe`, `step` + `ward` CLI + `/health` + 500-call cap.
- **A4 P1** Events and warnings (staff sickness, flu wave, CT breakdown, bus crash), agency staff, CT repair, diversion, the €24 000 hard limit, faint recovery.
- **A5 P1** HANDBOOK.md (English agent-visible rulebook, including the score formula) + instruction.md.
- **A6 P1** Difficulty config: one file of knobs with the SPEC section 7 and 12 TUNE values, tuned with lane C.
- **A7 P2** Extra event types and a second hospital layout.
- **A8 P1** (#31) Tool-output firewall tests: no tool output ever contains the future, the seed or a score.
- **A9 P1** (#32) Action-independent randomness: same seed gives the same arrivals and dice whatever the agent does.
- **A10 P0** (#67) Tune the difficulty values before the 22:00 freeze: one candidates table for Kostiantyn, then one PR that updates `config/default.json`, SPEC section 12, HANDBOOK.md and the baseline table together.

### B. Reward and integrity (`area:reward`)
- **B1 P0** Scorer: O, T, W, B and reward = score / 100. No anchors, no planner. Pure function over the event log, unit tested (TDD).
- **B2 P0** Verifier: `collect.py` in the hospital container runs the remaining ticks with no actions, scores, and writes `/evidence/report.json`; `tests/test.sh` reads it and always writes a number; Harbor separate mode.
- **B3 P1** Built-in baselines (reference, reactive proxy, stop-early, do-nothing) and exploit baselines (divert-all, rest-everyone, admit-light-only, admit-without-coverage, fill-beds-at-the-last-tick, spend-to-the-limit) + a CI test of the ordering.
- **B4 P1** Red-team round 1 (19:00): 15 minutes, by someone who did not write the scorer, using SPEC section 11. Log in docs/REDTEAM.md.
- **B5 P1** Red-team round 2 (23:30) after rules freeze, plus a regression test per finding.
- **B6 P1** End of episode: remaining ticks with no actions, outcome classes, and the `ended` field.
- **B8 P1** (#34) Exploit probes beyond the baselines, and scoring performance.
- **B9 P1** (#35) Confirm the SPEC section 12 decisions with Denys and his JavaScript prototype.

### C. Reference and experiments (`area:ref`)
- **C1 P0** Reference policy per rulebook section 12: `ed72/solution/`, public tools only, clearly above all baselines.
- **C2 P0** First OpenCode run at 18:00 on the thin slice. Post score and trajectory.
- **C3 P1** Run matrix: 3 seeds x 3 runs x up to 3 models, plus held-out seeds, with mean and range.
- **C4 P1** Failure analysis by F1..F10 (SPEC section 2) and by O, T, W, B: three trajectory excerpts, one chart. docs/FINDINGS.md.
- **C5 P1** Fairness audit: for each agent mistake, confirm the needed info was in HANDBOOK or the observation. Fix the handbook where it was not.
- **C6 P2** (#36) Reference ablations of the rulebook levers (F1 to F6): switch each lever off and measure the drop.
- **C7 P1** (#69) Difficulty sweep in `eval/tuning/` over the SPEC section 7 knobs; feeds A10.

### D. Harness, repro and story (`area:harness`)
- **D1 P0** Harbor spike: mostly done on Kostiantyn's branch (`docs/unfindable/SPIKE_S0_RESULTS.md`). Remaining: one real OpenCode model run against a stub hospital sidecar that serves `rules`, `observe` and `step`.
- **D2 P0** Task skeleton `ed72/`: copy the packaging from `origin/kostiantyn/env-unfindable-slice:harbor/unfindable/` (`task.toml` with separate mode, collect hook, compose healthcheck).
- **D3 P1** One-command eval: `make eval` runs reference, nop, stop-early (reactive proxy for 12 ticks, then stop), 3 agent runs, writes summary.md.
- **D4 P1** CI for the new layout: ruff + pytest on `ed72_sim` and the scorer, plus the baselines test.
- **D5 P1** README, 10-minute demo script, demo video, submission form.
- **D6 P2** Three seeds as three task folders + check the images build on x86 and ARM.
- **D7 P2** Stretch (`area:train`): fine-tune a small open model (about 4B) on reference trajectories on Modal, show before and after on one held-out seed.
- **D8 P1** (#37) Provider configuration and a measured run budget (timeout, call cap).

## Standing rules for this challenge (also in AGENTS.md section 10)
1. Nothing that reveals the answer goes into the agent's container.
2. No randomness without the seed, no wall-clock time, no network, no LLM inside the sim or the scorer.
3. A new scoring rule or sim rate needs a handbook line in the same PR.
4. Any PR that touches scoring pastes the baseline table (reference, reactive proxy, stop-early, do-nothing, and the exploit baselines).
5. Synthetic data only.
