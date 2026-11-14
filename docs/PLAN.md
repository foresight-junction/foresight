# Plan: four lanes, Sat 12:00 to Sun 10:00

Task board = GitHub Issues (`scripts/wt.sh board`). This file is the map; the issues are the truth. Create the issues with `scripts/bootstrap-board.sh`.

## Where we stand (Sat 14 Nov, 12:00)
- `main`: agent kit only (AGENTS.md, CLAUDE.md, 6 skills, wt.sh, CI). **No product code.**
- `research`: challenge briefs, shortlist, AfterQuery deep dive.
- No issues, no task branches yet.
- Chosen: **Break the Agent (AfterQuery)**, environment **Custodian** (`docs/SPEC.md`).

## Lanes
| Lane | Label | Owns | Rubric it carries |
|---|---|---|---|
| **A. World and tools** | `area:env` | Synthetic registry, tickets, sim, tool server, HANDBOOK | Meaningful difficulty (30) |
| **B. Reward and integrity** | `area:reward` | Scorer, verifier, trivial-policy anchors, red-team | Reward integrity (25) |
| **C. Reference and experiments** | `area:ref` | Reference policy, agent runs, failure analysis | The gap (30) + the explanation half of difficulty |
| **D. Harness, repro and story** | `area:harness` | Harbor packaging, one-command eval, CI, README, demo, submission, stretch | Craft (15) + tiebreaker |

Fill in names in AGENTS.md section 1. D is also the integrator (merges PRs).

## Timeline
| When | Milestone | Proof |
|---|---|---|
| 12:00 to 12:45 | **Kickoff.** Agree SPEC v0 + CONTRACTS v0. Ask mentors the 7 questions in CHALLENGE.md | Contracts issue closed |
| 12:45 to 16:00 | **Thin slice.** 10 tickets, 4 ticket types (F1, F2, F3, F4), 8 tools, scorer, reference | `oracle` >= 0.9, `nop` = 0, one OpenCode run finishes |
| **16:00** | **Calibration checkpoint.** First real agent score. Gap or no gap? | Score + trajectory posted on issue |
| 16:00 to 21:00 | Full ticket set (F5 to F10), anchors in CI, red-team round 1, one-command eval | All trivial policies <= 0.05 |
| **21:00** | **Rules freeze.** After this only bug fixes and knob tuning | Tag `v1-rules` |
| 21:00 to 00:00 | Run matrix (3 runs x models x seeds), failure analysis, red-team round 2, README | `eval/results/summary.md` |
| 00:00 to 02:00 | Demo script, dry run from a fresh clone on another laptop. Stretch goal only if all above is green | Fresh clone reproduces the table |
| Sun 08:00 to 10:00 | Demo video, final submission. No code changes after 09:00 | Submitted |

**If the 16:00 run shows no gap:** lane A raises difficulty with the knobs in SPEC section 7 (more cross-ticket cases, longer shift, messier ticket text). Lane C reruns. Decide by 18:00. Do not add trick wording or hide information to force a gap: that scores zero on 30 points.

## Tasks
P0 = needed for the thin slice. P1 = needed to submit. P2 = only if time.

### A. World and tools (`area:env`)
- **A1 P0** World generator: seeded synthetic people, fields by tier, guardians, consents, requesters, documents.
- **A2 P0** Sim core: ticket queue, clock and costs, event log, the 8 thin-slice tools.
- **A3 P0** Tool server: MCP (streamable-http) + `desk` CLI + `/health` + `/admin/finalise`.
- **A4 P1** Ticket types round 2: F5 stale consent, F6 mosaic, F8 injection, F9 policy change, warrants, subject access requests.
- **A5 P1** HANDBOOK.md + instruction.md: every scored rule written down and findable.
- **A6 P1** Difficulty config: one file of knobs, tuned with lane C.
- **A7 P2** Research export tickets (F7): `export` tool with generalisation levels.

### B. Reward and integrity (`area:reward`)
- **B1 P0** Scorer: ground truth per ticket, value, harm, anchors, normalisation, gate. Pure function over the event log, unit tested.
- **B2 P0** Verifier `tests/test.sh`: finalise, write `reward.txt`, always writes a number.
- **B3 P1** Trivial-policy anchors as scripted agents + a CI test that each scores <= 0.05.
- **B4 P1** Red-team round 1 (17:00): 15 minutes, by someone who did not write the scorer. Log in docs/REDTEAM.md.
- **B5 P1** Red-team round 2 (23:00) after rules freeze, plus a regression test per finding.
- **B6 P2** Export scorer: k-anonymity check + utility for F7.

### C. Reference and experiments (`area:ref`)
- **C1 P0** Reference policy: `solution/solve.sh`, public tools only, >= 0.9.
- **C2 P0** First agent run at 16:00 on the thin slice. Post score and trajectory.
- **C3 P1** Run matrix: 3 runs x 2 to 3 models x seeds, with mean and range.
- **C4 P1** Failure analysis: tie each lost point to F1..F10, three trajectory excerpts, one chart. docs/FINDINGS.md.
- **C5 P1** Fairness audit: for each agent mistake, confirm the needed info was reachable. Fix the handbook where it was not.

### D. Harness, repro and story (`area:harness`)
- **D1 P0** Harbor spike: install, hello-world with a sidecar, confirm OpenCode sees our tools. Decide MCP vs CLI.
- **D2 P0** Task skeleton: `custodian/` tree, task.toml, docker-compose with healthcheck, Dockerfiles.
- **D3 P1** One-command eval: `make eval` runs reference, nop, stop-early, 3 agent runs, writes summary.md.
- **D4 P1** CI for the new layout: ruff + pytest on sim and scorer.
- **D5 P1** README, 10-minute demo script, demo video, submission form.
- **D6 P2** Three seeds as three task folders + check the images build on x86 and ARM.
- **D7 P2** Stretch (`area:train`): fine-tune a small model on reference trajectories on Modal, show before and after.

## Standing rules for this challenge (also in AGENTS.md section 10)
1. Nothing that reveals the answer goes into the agent's container.
2. No randomness without the seed, no wall-clock time, no network, no LLM inside the sim or the scorer.
3. A new scoring rule needs a handbook line in the same PR.
4. Any PR that touches scoring pastes the baseline table (reference, nop, deny-all, approve-all, escalate-all, random).
5. Synthetic data only.
