# Evaluation and model setup

How ED-72 is run, how the judges' runs map to commands, and how we check and tune the score gap. Rules: `docs/ED_Management_Simulator_RU.md`. Names and shapes: `docs/SPEC.md` and `docs/CONTRACTS.md`.

## 1. Harness

- A Harbor task in `ed72/`, run by the OpenCode agent.
- Tools (`rules`, `observe`, `step`) reach the agent over MCP (streamable-http). `task.toml` declares the server under `[[environment.mcp_servers]]`. The `hospital` sidecar serves it at `http://hospital:8000/mcp`.
- Fallback if MCP fails in OpenCode: `ward <tool> --json '<args>'` inside `main`.
- `main` holds only `HANDBOOK.md` and `ward`. The sim, seed and scorer live in `hospital`.
- Verifier: `environment_mode = "separate"` plus a `[[verifier.collect]]` hook. The hook finalises inside `hospital` and writes `/evidence/report.json`, declared as a sidecar artifact.
- `tests/test.sh` reads only that file. It always writes a number to `/logs/verifier/reward.txt`, and writes 0 on any error.
- Why: Kostiantyn's spike showed that a root agent can forge the reward in shared mode. There is no finalise HTTP endpoint for the agent to call.
- Risk: OpenCode installs over npm at setup. `main` needs internet, or OpenCode must be preinstalled in the image.

## 2. Run budget

| Setting | Value |
|---|---|
| Agent timeout | 3600 s (TUNE, to be measured by issue #37; was 1800 s) |
| Tool-call cap | 500 (TUNE), counted by `hospital` |
| Target per run | 144 to 250 tool calls |
| `step` calls | 144 per episode, one per 30-minute tick, plus a few `rules` and `observe` |

- Every call to `rules`, `observe` and `step` counts toward the cap. A full episode needs 144 `step` calls, so the cap leaves about 350 calls for `observe` and retries.
- Tool results are compact JSON. `step` returns the next observation, so most ticks need one call.
- The episode ends after tick 143. If the agent stops early, hits the call cap or times out, the remaining ticks run with no actions.

## 3. The judge runs

| Run | Command | Expected score |
|---|---|---|
| Reference | `harbor run -p ed72 -a oracle` | Clearly the highest of all runs |
| Agent, 3 runs | `harbor run -p ed72 -a opencode -m <provider/model> --api-key-name <KEY> --ae '<OPENCODE_KEY>=${<KEY>}' --ak version=1.19.5 -k 3` (key table in README "How to run it") | To be measured. Gap = reference minus agent mean |
| Do-nothing | `harbor run -p ed72 -a nop` | 0 |
| Stop-early | Scripted baseline in `eval/`: plays the reactive proxy for 12 ticks, then stops | Low. Below the reactive proxy |

Expected order: reference, then reactive proxy, then stop-early, then do-nothing at 0.

`make eval` runs all of the above.

## 4. Run matrix

- Lane C: 3 seeds x 3 runs x up to 3 models. One model each from Anthropic, OpenAI and Google, the strongest we have keys for.
- Held-out seeds are also reported (SPEC section 12), so a result is not an artefact of the three shipped seeds.
- Other lanes: one seed, one model.
- Model ids are passed as `<provider/model>`. We choose them at the 18:00 checkpoint, from the keys the team has.
- Keys come from the environment: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`.
- Reported per model and seed: mean and range of the reward.
- Also reported: O, T, W, B, deaths, faints, and failure counts F1 to F10, all from `score_full.json`. These do not affect the reward.

## 5. Baseline policies

Reward = score / 100, where Score = 60·O + 20·T + O·(10·W + 10·B). There is no normalisation, no anchor and no planner. A baseline's reward is directly comparable to an agent's.

- All baselines are scripted agents. They play through the same tools as an agent and are scored by the same scorer.
- Same seed plus same actions gives the same score.
- Implementation: `eval/baselines/`. CI test: `ed72/environment/hospital/ed72_sim/scoring/tests/test_baselines.py` (issue #12).

Built-in baselines (rulebook section 12):

| Policy | How it plays | Expected rank |
|---|---|---|
| Reference | Admits by severity and keeps resus beds free for critical patients. Sends light cases to fast-track. Staffs each zone from the least tired people, which rotates rest. Orders agency staff when a warning is about 9 ticks away. Repairs the CT at once. Keeps staff on shift when a surge is near | 1 |
| Reactive proxy | Scripted stand-in for typical model play. Admits first come first served into the first free bed, so light cases fill resus. Keeps staff at fixed posts until fatigue reaches 85, so they faint together. Orders agency staff only when the queue reaches 10. Ignores warnings | 2 |
| Stop-early | Plays the reactive proxy for 12 ticks, then stops acting | 3 |
| Do-nothing | Never acts | 4, score 0 |

Exploit baselines (rulebook section 13). Each tries one shortcut and must lose to the reference:

| Policy | How it plays | Why it fails |
|---|---|---|
| Divert-all | Diverts all the time | Each diverted patient loses 0.7 of its weight and is late. O is capped near 0.51 and T near 0.3, so about 47 points at best |
| Rest-everyone-in-quiet-periods | Sends all staff to rest when the department is quiet | W is worth at most 10 x O. Uncovered beds stall and ESI 1 patients face 10 to 15% death risk per tick |
| Admit-light-only | Admits only ESI 4 and 5 | ESI 1 and 2 carry about 51% of the outcome weight, so O is capped near 0.49 |
| Admit-without-coverage | Fills beds with no staff assigned | Timeliness counts only from the first covered tick. Uncovered ESI 1 and 2 beds carry a death risk every tick |
| Fill-beds-at-the-last-tick | Admits the whole queue at tick 143 | The 0.3 end loss applies only to patients with at least one covered tick. The rest lose 1 |
| Spend-to-the-limit | Spends up to €24 000 on agency staff and repairs | B falls to 0, up to 10 points lost, with no matching gain in O |

CI-tested properties:

- Do-nothing scores exactly 0.
- Stop-early < reactive proxy < reference on every shipped seed.
- Divert-all < reference, and about 47 points or less.
- Every exploit baseline < reference.
- Same seed plus same actions gives the same score.
- `test.sh` always writes a number.

## 6. If the gap is too small or too large

Use only the knobs in SPEC section 7:

- arrival rate and daily cycle
- flu-wave severity mix
- event windows
- warning lead time, or a window instead of an exact start tick
- budget size
- W weights
- overlapping events
- hidden deterioration, only if it stays inferable from the observation

Agent too strong (gap near zero): raise difficulty through the knobs.

Agent too weak (score near zero): check that the handbook documents every rule and that the reference still uses public tools only. Then lower difficulty.

Never use trick wording, hidden rules, impossible timing or broken tools.

After every change, the reference must stay clearly above every baseline. Paste the baseline table in the PR.

## 7. Tiebreaker (P2)

Only after the rules freeze (Sat 22:00). Fine-tune a small open model (about 4B parameters) with supervised fine-tuning on reference-policy trajectories, on Modal. Show before and after on one held-out seed, with the same harness.
