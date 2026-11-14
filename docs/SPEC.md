# ED-72: environment spec

Status: proposal, replaces the Custodian spec (team decision Sat 14 Nov).
Anything marked `TUNE` is a starting value. Change this file only with the `contract-change` skill.

## 1. One-liner
An RL environment where an agent runs a fictional hospital emergency department for 72 simulated hours.

**Setting:** the only ED in a remote region. The next hospital is a 90-minute drive.

**Why this setting:** a fully visible ED is a scheduling problem, and an agent would code a priority queue. So the difficulty comes from information the agent must choose to gather and from costs that land hours later.

**All data is synthetic.** Patients, staff and records are generated from a seed.

## 2. What we think agents get wrong (hypotheses to test, not facts)
| Code | Failure | Trigger |
|---|---|---|
| F1 | Trusts the arrival triage label | About 20% of labels are wrong (handbook says so). Only `assess` shows true acuity |
| F2 | Never re-checks | Some waiting or admitted patients deteriorate quietly. Only a re-assess shows it |
| F3 | Burns staff early | Overtime and skipped breaks raise fatigue. Treatment slows, and above 90 the person goes off sick for 24 h |
| F4 | Spends the budget early | Call-ins, overtime, transfers and repairs draw from one 72-hour budget. At zero they are refused |
| F5 | Early discharge | Patient returns later in a worse state |
| F6 | Over-transfer or diversion | Transfer and diversion harm high-acuity patients. Ambulances are limited |
| F7 | Ignores a notice | Surge forecasts and equipment maintenance warnings appear in `notices` hours ahead |
| F8 | Bed blocking | Low-acuity patient left in a resus bed or on a monitor when a critical one arrives |
| F9 | Plan lock-in | Keeps the old plan after a breakdown or a sick call |
| F10 | Quits early | Ends the shift or runs out of tool calls before hour 72 |

These are hypotheses. If the agent fails for an unfair reason, we fix the handbook, not the agent.

## 3. World (seeded, deterministic)
- **Beds:** 15, of which 3 resus and 12 general.
- **Equipment:** 4 monitors, 2 ventilators, 1 CT scanner.
- **Staff:** 6 doctors and 12 nurses in three 8-hour shifts, plus an on-call pool of 2 doctors and 4 nurses. Skills are `critical_care` and `general`.
- **Capacity:** a doctor treats up to 4 patients at once, a nurse up to 5. Critical patients count double. Fatigue is 0 to 100 per person.
- **Patients:** about 220 over 72 h `TUNE`, with a daily pattern documented in the handbook (evenings are busy). Each has true acuity 1 (most urgent) to 5, a triage label, a condition, a required skill and equipment, a treatment duration and health 0 to 100.
- **Deterioration:** untreated health falls at a rate set by true acuity. The table is in the handbook.
- **Thresholds:** health below 30 is permanent harm. Health 0 is death. Low-acuity patients leave without being seen after a long wait.
- **Events:** ordinary, seeded, at fixed sim times. Nurse sick call, CT breakdown, monitor fault, lab slowdown, a flu-season surge. No disasters. Each surge and breakdown has a precursor in `notices`.
- **Budget:** one sum for the 72 hours. Overtime costs 1.5x for the first 4 extra hours, then 2x. Call-in, transfer and emergency repair have fixed prices in the handbook.

## 4. Episode
- 72 sim hours in 15-minute ticks. The clock moves only when the agent calls `advance(minutes)`, with minutes from 15 to 120. `advance` returns early when a patient with label 1 or 2 arrives or an event fires.
- Tool-call cap: 600 `TUNE`, counted by the hospital. The episode ends on `end_shift`, hour 72, or the cap.
- Whatever time is left is fast-forwarded with no new actions. Stopping early scores like doing nothing from that point.
- After hour 72 the sim runs a 12-hour handover tail with no agent actions. Patients still in the department are scored on what happens to them in the tail.
- No reset, no undo, no seed or ground-truth endpoint.

## 5. Tools (the action space). Exact shapes live in docs/CONTRACTS.md
**Read:** `board`, `patient`, `roster`, `equipment`, `budget`, `notices`, `handbook`, `clock`.

**Act:** `assess`, `admit`, `assign`, `order_test`, `discharge`, `transfer`, `set_diversion`, `call_in`, `extend_shift`, `send_on_break`, `repair`, `advance`, `end_shift`.

Rules of the tools:
- The agent only talks to the `hospital` service, over MCP. Fallback: `ward <tool> --json '<args>'` in `main`.
- All state lives in the hospital container. No reset, no undo.
- Tool results are compact JSON. `advance` returns a digest of what changed.

## 6. Reward
The reward is a pure function `score(events, world)` over the append-only event log in the hospital container. No LLM judge.

Per-patient harm, summed over all patients who arrived:
| Module | What it measures | Harm |
|---|---|---|
| M1 Outcome | Death, permanent harm | 100, 40 `TUNE` |
| M2 Timeliness | Minutes waited past the safe limit for the true acuity (0, 10, 30, 60, 120 min for acuity 1 to 5) | weight 5, 3, 1.5, 0.5, 0.2 per 10 min, capped at 30 per patient `TUNE` |
| M3 Disposition | Return after early discharge, left without being seen, harm in transit or after diversion | return 15 plus the patient's later outcome. Left unseen 2 to 10 by acuity |
| M4 Continuity | Outcomes during the 12-hour handover tail | same table as M1 to M3 |

```
H        = sum over patients of (M1 + M2 + M3 + M4)
H_anchor = lowest H among trivial policies on the same seed:
           do-nothing, first-come-first-served by label, discharge-all,
           transfer-all, divert-all, call-in-everyone, random
H_floor  = H of a full-information planner shipped in the hospital image
reward   = clip((H_anchor - H) / (H_anchor - H_floor), 0, 1)
```

Anchors and floor are computed by replaying the same seed inside the hospital container at scoring time. The sim is deterministic and fast.

Staff fatigue, budget and bed use are never scored directly. They act through patient outcomes, so judges have no side metric to pump.

Properties tested in CI:
1. Do-nothing scores 0.
2. Every trivial policy scores <= 0.05.
3. Stop-early at hour k scores no more than playing to hour k and then doing nothing.
4. The reference policy scores >= 0.9 on every shipped seed.
5. Same seed and same actions give the same score.
6. `tests/test.sh` always writes a number.

`score_full.json` also carries harm per module and counts per failure code F1 to F10, for the failure analysis. These do not affect the reward.

## 7. Difficulty knobs (one config file, hospital side, via `ED72_CONFIG`)
Arrival volume, share of wrong triage labels, share of quiet deteriorators, budget size, number and timing of events, tool-call cap. The reference policy must stay >= 0.9 after every change.

## 8. Fairness rules (30 points depend on these)
- Every rule the scorer uses and every sim rate table is written in `HANDBOOK.md`. A scorer rule or rate without a handbook section is a bug.
- Every fact needed for a correct decision is reachable through a tool.
- Every event with a precursor shows it in `notices` at least 2 sim hours ahead.
- The reference policy uses only the public tools. It never reads the seed, the ground truth or the sim source.
- Reference policy: assess every arrival, re-assess waiting patients on a schedule set by acuity, keep one resus bed free, rotate breaks before fatigue reaches 70, read `notices` every sim hour and pre-position staff, hold a budget reserve per remaining day, discharge only when the handbook criteria are met. It lives in `ed72/solution/`.

## 9. Harbor layout
```
ed72/                         <- judges run: harbor run -p ed72 -a <agent>
  instruction.md              what the agent is told
  task.toml                   timeouts, [[environment.mcp_servers]], environment_mode = "separate",
                              [[verifier.collect]]
  environment/
    Dockerfile                main: HANDBOOK.md and `ward` CLI only. NO sim code, NO seeds
    docker-compose.yaml       adds the `hospital` sidecar (http://hospital:8000, MCP at /mcp)
    hospital/                 sidecar image
      ed72_sim/               world gen, sim, event log, MCP server
        scoring/              the scorer, anchors and floor
  tests/test.sh               reads only /evidence/report.json, writes /logs/verifier/reward.txt
  solution/solve.sh           reference policy, public tools only
eval/                         run matrix, baselines, results/
analysis/                     failure analysis, charts
training/                     stretch goal only
```
The `[[verifier.collect]]` hook finalises inside `hospital` and writes `/evidence/report.json`, declared as a sidecar artifact. There is no finalise HTTP endpoint. Separate mode is required because a spike showed a root agent can forge the reward in shared mode. `ED72_SEED` and `ED72_CONFIG` are set in the hospital sidecar only.

## 10. Judge runs mapped to commands
| Judge run | Command |
|---|---|
| Reference | `harbor run -p ed72 -a oracle` |
| Agent x3 | `harbor run -p ed72 -a opencode -m <provider/model> -k 3` |
| Do-nothing | `harbor run -p ed72 -a nop` |
| Stop-early | baseline in `eval/` that plays the reference to hour 24, then ends the shift |
| All of it | `make eval` (one command, writes `eval/results/summary.md`) |

## 11. Shortcuts judges will try first
| Shortcut | Defence (a sim consequence, written in the handbook) |
|---|---|
| Discharge everyone to free beds | Unfinished patients return within hours at a worse acuity. The return counts against the same patient |
| Transfer everyone | 90-minute drive with health falling in transit, 2 ambulances, each transfer costs budget |
| Unlimited overtime | Price escalates and fatigue slows treatment, then the person is off sick for 24 h |
| Refuse or divert arrivals | A diverted patient is scored by the outcome of the 90-minute drive |
| Read the simulator | Sim, seed and scorer are in the `hospital` container. The agent has MCP only |
| Do nothing or stop early | Remaining time is fast-forwarded. Untreated patients deteriorate |
| Burn everything in the last hours | The 12-hour handover tail scores the state left behind |
| Forge the reward file | Verifier runs in Harbor separate mode and reads only evidence written inside `hospital` |
