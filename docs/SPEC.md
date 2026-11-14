# ED-72: environment spec

Status: realigned to the game rules in `docs/ED_Management_Simulator_RU.md` (Denys, Sat 14 Nov), which `AGENTS.md` §1 names the source of truth (PR #38, issue #41). This file is the English summary plus the decisions the rulebook left open (§12). Where they disagree, the rulebook wins; fix this file. Anything marked `TUNE` is a starting value. Change this file only with the `contract-change` skill.

## 1. One-liner
An RL environment where an agent runs a fictional hospital emergency department for 72 simulated hours: every 30 minutes it decides which waiting patient gets a bed, where each doctor and nurse works or rests, and whether to spend money on agency staff, a CT repair or ambulance diversion (rulebook §1).

**All data is synthetic.** Patients, staff and events are generated from a seed. One seed gives every strategy the same patients, events and dice rolls, so scores are directly comparable (rulebook §1–§2).

**Why it is hard:** there are never enough staff to cover every bed, fatigue builds over days, two of the four events give a warning and two do not, and the costs of a bad decision (a blocked resus bed, a burnt-out shift, an unrepaired scanner) land hours later.

## 2. What we think agents get wrong (hypotheses to test, not facts)
| Code | Failure | Where it shows |
|---|---|---|
| F1 | Resus blocking: low-acuity patients put in the 3 resus beds, so an ESI 1 arrival has nowhere to go | ESI 1 deaths while resus holds ESI 3–5 |
| F2 | No rest rotation: staff kept on shift until fatigue 90, so many faint together | faints, fatigue > 60 coverage penalty |
| F3 | Ignores warnings: no preparation for the announced flu wave or bus crash | deaths and waits during those events |
| F4 | Leaves the CT broken, or never notices patients stuck at half treatment | CT-blocked beds |
| F5 | Overspends (agency staff, repairs) without saving patients, or underspends while patients die | B versus O |
| F6 | Diversion overuse: diverts while beds are free | diverted patients |
| F7 | Admits to beds it cannot cover | ESI 1–2 deaths on uncovered beds |
| F8 | Lets ESI 3 wait more than 6 ticks, so they become ESI 2 | upgrades |
| F9 | Plan lock-in after the unannounced sick call or CT breakdown | coverage gaps after those events |
| F10 | Stops acting before tick 143 | ticks without actions |

These are hypotheses for the failure analysis (C4). If the agent fails for an unfair reason, we fix the rules text the agent sees, not the agent.

## 3. World (rulebook §3–§7; seeded, deterministic)
- **Department:** 17 treatment beds in three zones plus an unlimited waiting area, 1 CT scanner and a rest room.

| Zone | Beds | Who may be treated there |
|---|---|---|
| Resus | 3 | ESI 1–5 (the only zone for ESI 1) |
| Acute | 8 | ESI 2 (+1 treatment tick), ESI 3–5 |
| Fast-track | 6 | ESI 3 (+1 treatment tick), ESI 4–5 |

- **Patients:** ESI 1–5 (1 most critical), known on arrival. Arrival mix 4/14/34/30/18%. Treatment 6/5/3/2/1 ticks. Target time to a bed 0/1/4/8/12 ticks. Outcome weight 10/5/2/1/0.5. Arrivals are Poisson with a daily cycle (peak around 15:00, low at night); new patients appear in the waiting area at the start of their tick. About half of ESI 1–2 patients need CT, which is decided and shown on arrival. Treatment stops halfway (rounded up) while the scanner is down. There is no discharge action: a bed frees only when treatment completes or the patient dies. An ESI 3 who waits too long can become ESI 2 and then follows every ESI 2 rule, with a new 50% CT roll, and is scored as ESI 2.
- **Staff:** 6 doctors and 9 nurses, all starting off shift in the rest room with fatigue 0. Covering all 17 beds would need 8 doctors and 9 nurses, so some beds are always uncovered. Staff are assigned to a zone or to rest; an assignment takes effect in the same tick and holds until changed.

| Zone | Beds per doctor | Beds per nurse |
|---|---|---|
| Resus | 1 | 1 |
| Acute | 3 | 2 |
| Fast-track | 4 | 3 |

  A zone treats at most the smaller of its doctor coverage and nurse coverage (fractional coverage rounds down). When more beds are occupied than covered, beds are covered by severity (ESI 1 first), then by admission time. Only covered beds progress.
- **Fatigue:** 0–100 per person. On shift in Acute or Fast-track +1.6 per tick, in Resus +2.2, resting −2.5 (never below 0). Above 60 a person counts as 0.6 for coverage. At 90 or more the person faints, is out for 10 ticks (recovering at the rest rate) and comes back to the rest room at about 65, needing a new assignment.
- **Agency staff:** ordered with `agency`; arrive 4 ticks later in the rest room with fatigue 0, stay 16 ticks; same fatigue and fainting rules.
- **Hazards** (rolled once per tick per patient they apply to, each patient from its own random stream):

| Situation | Chance per tick | Result |
|---|---|---|
| ESI 1 in the waiting area | 15% | death |
| ESI 2 waiting more than 1 tick | 4% | death |
| ESI 3 waiting more than 6 ticks | 8% | becomes ESI 2 |
| ESI 4–5 waiting more than 16 ticks | 8% | leaves |
| ESI 1 on a bed not covered this tick | 10% | death |
| ESI 2 on a bed not covered this tick | 3% | death |
| ESI 1–2 being treated in a zone whose average on-shift fatigue is above 60 | 1.5% | death |

  "Waiting more than n ticks" counts full ticks in the waiting area since arrival. A covered bed does not carry the uncovered-bed hazard and the fatigue hazard applies only to covered beds, so they never stack. ESI 3–5 on a bed carry no hazard. A patient admitted this tick does not roll the waiting hazard this tick. Hazards use fatigue as it was at the start of the tick.
- **Events:** four per episode, start tick drawn by the seed inside each window.

| Event | Start window (tick) | Warning | Effect |
|---|---|---|---|
| Staff sickness | 28–35 | none | 2 nurses (chosen by the seed) off sick for 20 ticks; a nurse on shift leaves at once and returns to rest with the fatigue she left with |
| Flu wave | 50–61 | 10 ticks ahead | +2 arrivals per tick for 6 ticks, mostly ESI 3–5 |
| CT breakdown | 66–75 | none | scanner down for 16 ticks unless repaired |
| Bus crash | 96–109 | 8 ticks ahead | 10 extra patients over 2 ticks (5 per tick): ESI 1 20%, ESI 2 30%, ESI 3 50% |

  A warning shows the event type and its exact start tick and stays visible until the event ends. While the CT is down the observation shows the remaining down ticks.
- **Budget:** €12 000. Spending above it is allowed up to a hard limit of €24 000 but lowers the budget score.

## 4. Episode (rulebook §2, §9)
- 144 ticks of 30 minutes, numbered 0–143. Tick 0 starts at 08:00 on day 1; the episode ends at 08:00 on day 4. The simulation always runs all 144 ticks.
- Each tick resolves in eight steps: (1) agency contracts end, sick and fainted staff whose time is up return to rest, ordered agency staff arrive; (2) events start or end, warnings appear; (3) this tick's arrivals are drawn, diversion applied, the rest join the waiting area; (4) the agent observes; (5) the agent's actions are validated and applied in order, rejected ones recorded; (6) coverage is computed, covered beds progress (unless waiting for CT), finished patients are discharged; (7) hazards are rolled; (8) fatigue changes, anyone at 90 or more faints. Because arrivals come before actions, an ESI 1 can be admitted in the tick it arrives, so a 0-tick target is reachable.
- An agent that stops acting does not end the episode: the remaining ticks still run with no new actions, staff stay where they were last assigned, and waiting patients keep facing their hazards. Stopping early scores like doing nothing from that point.
- After tick 143 the episode is scored. Patients still waiting count as never admitted; patients still in a bed count as a partial loss (§6).
- No reset, no undo, no seed or ground-truth endpoint. Same seed plus same actions always gives the same result.

## 5. Agent interface (rulebook §8, §10; exact shapes in docs/CONTRACTS.md)
The rulebook's policy interface is `policy(observation) → list of JSON actions`, one call per tick, so any model can sit behind it. Over MCP this becomes three tools:
- **`rules`**: the agent-visible rules (`HANDBOOK.md`), including hazard rates and the score formula. The rules are public; only the future is hidden.
- **`observe`**: the current observation (step 4 of the tick). Read-only.
- **`step(actions)`**: applies the action list in order (step 5), resolves the rest of the tick and the start of the next one, and returns a result per action plus the next observation. `step([])` passes a tick with no actions.

Actions (rulebook §8): `admit` a waiting patient to a zone with a free allowed bed; `assign` a staff member to a zone or to `rest`; `agency` (doctor €900, nurse €350); `repair` (€2 000, only while the CT is down; it returns 3 ticks after the order, or at its original time if sooner); `divert` (free; 70% of arrivals, including bus-crash patients, are turned away for 4 ticks; not while a diversion is active). `agency` and `repair` are refused if total spending would exceed €24 000. Admission is only from the waiting area; there are no transfers between zones. Staff can be reassigned every tick for free. Invalid actions are rejected with a reason, have no effect and no extra penalty, and the valid actions in the same list still apply.

The observation shows the whole current state and nothing of the future (rulebook §10): time, budget, every waiting patient, every bed, every staff member, the CT, warnings, diversion, running totals and the rejected actions of the last step.

## 6. Reward (rulebook §11, with the §13 fixes adopted in §12 below)
```
Score  = 60·O + 20·T + O·(10·W + 10·B)        in [0, 100]
reward = Score / 100                            in [0, 1], written to /logs/verifier/reward.txt
```
O, T, W and B are each in [0, 1], computed once at the end over every patient who arrived, including diverted ones.

- **O, outcome (60 points):** O = 1 − (weighted loss ÷ total weight), weights 10/5/2/1/0.5 for ESI 1–5 (an upgraded patient uses the highest ESI reached).

| How the episode ended for the patient | Loss |
|---|---|
| Discharged after treatment | 0 |
| Still in a bed at the end, with at least one covered tick | 0.3 |
| Still in a bed at the end, never covered | 1 |
| Diverted on arrival | 0.7 |
| Died, left, or never admitted | 1 |

- **T, timeliness (20 points):** the weighted share of patients whose first **covered** bed tick came within their target (0/1/4/8/12 ticks after arrival for ESI 1–5). Diverted and never-admitted patients count as late.
- **W, wellbeing (10 × O points):** `W = max(0, 1 − a · share − b · faints)`, where `share` is the share of on-shift staff-ticks with fatigue above 60 and `faints` is the number of faints. `a = 1.0`, `b = 0.05` (`TUNE`).
- **B, budget (10 × O points):** 1 if total spend ≤ €12 000, then linear to 0 at €24 000: `B = 1 − (spend − 12 000) / 12 000`, clipped to [0, 1].

W and B are multiplied by O so that treating nobody (fresh staff, no spending) cannot earn them. Anchor points: do nothing 0; perfect play 100; everyone treated on time with no rest and €24 000 spent 80.

The score is a pure function of the hospital's append-only event log (CONTRACTS "Event log"); rule numbers come from the simulator's constants. No LLM judge. `score_full.json` also carries per-patient outcomes, deaths, faints, spend and counts per failure code F1–F10 for the analysis; those do not change the reward.

## 7. Difficulty knobs (one config file, hospital side, via `ED72_CONFIG`)
Arrival rate and daily cycle, flu-wave severity mix, event windows, warning lead times (or a window instead of an exact tick), budget size, W weights, overlapping events, and a possible hidden-deterioration mode (only if it stays inferable from the observation). The reference must stay clearly above the baselines in EVAL after every change.

## 8. Fairness rules (30 points depend on these)
- Every rule the scorer uses and every rate table is written in the agent-visible `HANDBOOK.md` (served by `rules`). A scorer rule or rate without a handbook line is a bug.
- Everything needed for a good decision is in the observation; only the future (arrivals, unannounced events, dice rolls) is hidden.
- The reference policy uses only the public tools. It never reads the seed, the event log or the sim source.
- Reference policy (rulebook §12): admit by severity and keep resus beds free for critical patients; send light cases to Fast-track; staff each zone from the least tired people, which rotates rest automatically; order agency staff when a warning is about 9 ticks away; repair the CT at once; keep staff on shift when a surge is near. It lives in `ed72/solution/`.

## 9. Harbor layout
```
ed72/                         <- judges run: harbor run -p ed72 -a <agent>
  instruction.md              what the agent is told
  task.toml                   timeouts, [[environment.mcp_servers]], environment_mode = "separate",
                              [[verifier.collect]]
  environment/
    Dockerfile                main: HANDBOOK.md and the `ward` CLI only. NO sim code, NO seeds
    docker-compose.yaml       adds the `hospital` sidecar (http://hospital:8000, MCP at /mcp)
    workspace/HANDBOOK.md     agent-visible rules (English, from the rulebook)
    hospital/                 sidecar image
      ed72_sim/               world gen, tick engine, event log, MCP server
        scoring/              the scorer and the built-in baselines
  tests/test.sh               reads only /evidence/report.json, writes /logs/verifier/reward.txt
  solution/solve.sh           reference policy, public tools only
eval/                         run matrix, baselines, results/
analysis/                     failure analysis, charts
training/                     stretch goal only
```
The simulator lives in `ed72/environment/hospital/`. The earlier engine in `backend/app/edsim/` (branch `kostiantyn/env-ed-sim`) models a different game and is not used.

The `[[verifier.collect]]` hook runs `collect.py` inside `hospital` after the agent stops: it runs any remaining ticks with no actions, scores, and writes `/evidence/report.json`, declared as a sidecar artifact. There is no finalise HTTP endpoint. Separate mode is required because a spike showed a root agent can forge the reward in shared mode. `ED72_SEED` and `ED72_CONFIG` are set in the hospital sidecar only.

## 10. Judge runs mapped to commands
| Judge run | Command |
|---|---|
| Reference | `harbor run -p ed72 -a oracle` |
| Agent x3 | `harbor run -p ed72 -a opencode -m <provider/model> -k 3` |
| Do-nothing | `harbor run -p ed72 -a nop` |
| Stop-early | baseline in `eval/`: plays the reactive proxy for 12 ticks, then stops |
| All of it | `make eval` (one command, writes `eval/results/summary.md`) |

## 11. Shortcuts judges will try first (rulebook §13)
| Shortcut | Defence |
|---|---|
| Put a patient in a bed with no staff | Timeliness counts only from the first covered tick; uncovered ESI 1–2 beds carry a 10% / 3% death risk per tick |
| Fill every bed in the last tick | The 0.3 end loss applies only to patients with at least one covered tick; otherwise the loss is 1. Admitting to a covered bed at tick 143 does earn 0.3, as honest play would; the gain is capped by free covered beds (at most 17), and patients held back to fill late keep facing the waiting hazards and count late in T. CI checks that the `fill-beds-at-the-last-tick` baseline scores below the reference (#12) |
| Divert all the time | Each diverted patient loses 0.7 of its weight and is late; permanent diversion caps around 47 points, so the reference must clearly beat 47 |
| Spend up to €24 000 | B falls to 0 (up to 10 points); spending that saves more patients than it costs is good play, not an exploit |
| Everyone rests in quiet periods | W is worth at most 10 × O; uncovered beds stall and ESI 1 patients face 10–15% death risk per tick |
| Admit only light patients | ESI 1–2 carry about 51% of the outcome weight; leaving them caps O at about 0.49 |
| Do nothing or stop early | All 144 ticks still run; patients keep arriving and dying; do-nothing scores 0 |
| Spam invalid actions | Rejected with no effect |
| Memorise seeds | The agent never sees future arrivals or unannounced events; we also report held-out seeds |
| Read the simulator or forge the reward | Sim, seed and scorer are in the `hospital` container; the verifier runs in separate mode and reads only evidence written inside `hospital` |

## 12. Decisions on the rulebook's open items (rulebook §14)
Recorded for issue #41. "Adopted" means build it; `TUNE` values are tuned in A6 (#8) with lane C.

**Confirmed by Denys, the rulebook author, Sat 14 Nov 15:32 (issue #35).** Every "Adopted" row below stands as written. The `TUNE` rows stand as starting values until A6 (#8) sets the final numbers before the 22:00 rules freeze. There is no JavaScript prototype, so the rulebook's §14 instruction to check the [Proposed] rules against it is met by this confirmation. No row changed, so nothing in `docs/CONTRACTS.md` or HANDBOOK changes.

| Rulebook §14 item | Decision |
|---|---|
| Arrival rate and daily cycle | `TUNE`: mean 3.0 arrivals per tick, sinusoidal ±50% with the peak at 15:00 and the low at 03:00 (about 432 patients before events) |
| Flu-wave severity mix | `TUNE`: ESI 3 40%, ESI 4 35%, ESI 5 25% |
| W penalty weights and what "staff time" means | `TUNE`: a = 1.0 per unit share of on-shift staff-ticks above fatigue 60; b = 0.05 per faint; only on-shift ticks count |
| Budget curve above €12 000 | Adopted: straight line to 0 at €24 000 |
| Clock starts at 08:00, staff start at fatigue 0 | Adopted |
| Separate random streams for arrivals/events and for each patient's hazards | Adopted (issue #32) |
| Eight-step tick order (rulebook §9) | Adopted |
| Coverage priority by severity then admission time; fractional coverage rounds down | Adopted |
| CT need shown on arrival; no scanner queue; stop point at half treatment rounded up | Adopted |
| Upgraded ESI 3 follows ESI 2 rules and is scored as ESI 2 | Adopted |
| Fainted staff return at about 65; agency staff arrive at fatigue 0 in the rest room | Adopted |
| Diversion is free, cannot overlap itself and applies to bus-crash patients | Adopted |
| Repair only while the CT is down; back 3 ticks after the order or earlier | Adopted |
| Warnings show the exact start tick | Adopted (a window instead is a difficulty knob) |
| Diverted and never-admitted patients count as late in T | Adopted |
| §13 fix: timeliness from the first covered tick | Adopted |
| §13 fix: 0.3 end loss only with at least one covered tick | Adopted |
| Report scores on held-out seeds | Adopted |
