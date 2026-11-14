# Evaluation and model setup

How ED-72 is run, how the judges' runs map to commands, and how we check and tune the score gap.

## 1. Harness

- A Harbor task in `ed72/`, run by the OpenCode agent.
- Tools reach the agent over MCP (streamable-http). `task.toml` declares the server under `[[environment.mcp_servers]]`. The `hospital` sidecar serves it at `http://hospital:8000/mcp`.
- Fallback if MCP fails in OpenCode: `ward <tool> --json '<args>'` inside `main`.
- `main` holds only `HANDBOOK.md` and `ward`. The sim, seed and scorer live in `hospital`.
- Verifier: `environment_mode = "separate"` plus a `[[verifier.collect]]` hook. The hook finalises inside `hospital` and writes `/evidence/report.json`, declared as a sidecar artifact.
- `tests/test.sh` reads only that file. It always writes a number to `/logs/verifier/reward.txt`, and writes 0 on any error.
- Why: Kostiantyn's spike showed that a root agent can forge the reward in shared mode. There is no finalise HTTP endpoint for the agent to call.
- Risk: OpenCode installs over npm at setup. `main` needs internet, or OpenCode must be preinstalled in the image.

## 2. Run budget

| Setting | Value |
|---|---|
| Agent timeout | 1800 s (TUNE) |
| Tool-call cap | 600 (TUNE), counted by `hospital` |
| Target per run | 15 to 20 min wall time, 250 to 450 tool calls |
| `advance(minutes)` | 15 to 120; returns early on a label 1 or 2 arrival or an event |

- `advance` returns a digest of what changed. Tool results are compact JSON. This keeps the context small over 72 sim hours.
- The episode ends on `end_shift`, hour 72, or the tool-call cap.
- Remaining time is fast-forwarded with no actions. Then the 12-hour handover tail runs, also with no actions.

## 3. The six judge runs

| Run | Command | Expected score |
|---|---|---|
| Reference | `harbor run -p ed72 -a oracle` | >= 0.9 |
| Agent, 3 runs | `harbor run -p ed72 -a opencode -m <provider/model> -k 3` | To be measured. Gap = reference minus agent mean |
| Do-nothing | `harbor run -p ed72 -a nop` | 0 |
| Stop-early | Scripted baseline in `eval/`: plays the reference to hour 24, then ends the shift | About a third of the reference or less. Never more than playing to hour 24 then doing nothing |

`make eval` runs all of the above.

## 4. Run matrix

- Lane C: 3 seeds x 3 runs x up to 3 models. One model each from Anthropic, OpenAI and Google, the strongest we have keys for.
- Other lanes: one seed, one model.
- Model ids are passed as `<provider/model>`. We choose them at the 18:00 checkpoint, from the keys the team has.
- Keys come from the environment: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`.
- Reported per model and seed: mean and range of the reward.
- Also reported: harm per module M1 to M4, and failure counts F1 to F10, both from `score_full.json`. These do not affect the reward.

## 5. Baseline policies

Reward = clip((H_anchor - H) / (H_anchor - H_floor), 0, 1).

- H is total patient harm (M1 to M4) over all patients who arrived.
- H_anchor is the lowest H among the policies below, on the same seed.
- H_floor is the H of a full-information planner shipped in the `hospital` image.
- All of them are replayed inside `hospital` at scoring time. The sim is deterministic and fast.
- Staff fatigue, budget and bed use are never scored directly. Only patient outcomes are.

Each policy must score <= 0.05 (do-nothing exactly 0). These are CI-tested properties.

| Policy | What it does | Why it fails |
|---|---|---|
| Do-nothing | Never acts | Untreated patients deteriorate; the tail adds more harm |
| First-come-first-served by label | Treats in arrival order of the triage label | About 20% of labels are wrong, and quiet deteriorations are never re-checked (F1, F2) |
| Discharge-all | Discharges everyone to free beds | Unfinished patients return within hours at a worse acuity; the return counts against the same patient (F5) |
| Transfer-all | Sends everyone to the next hospital | 90-minute drive, health falls in transit, only 2 ambulances, each transfer costs budget (F6) |
| Divert-all | Refuses or diverts arrivals | A diverted patient is scored by the outcome of the 90-minute drive (F6) |
| Call-in-everyone | Calls in all on-call staff at once | Budget is spent early and then refused at zero (F4); no reserve for events |
| Random | Picks random legal actions | No coherent triage; high-acuity patients wait past the safe limit |

## 6. If the gap is too small or too large

Use only these knobs:

- share of wrong triage labels
- number and timing of quiet deteriorations
- patient volume and surge size
- budget size
- fatigue rates
- notice lead time
- tool-call cap and timeout

Agent too strong (gap near zero): raise difficulty through the knobs.

Agent too weak (score near zero): check that the handbook documents every rule and that the reference still uses public tools only. Then lower difficulty.

Never use trick wording, hidden rules, impossible timing or broken tools.

After every change, reference must stay >= 0.9. Paste the baseline table in the PR.

## 7. Tiebreaker (P2)

Only after the rules freeze (Sat 22:00). Fine-tune a small open model (about 4B parameters) with supervised fine-tuning on reference-policy trajectories, on Modal. Show before and after on one held-out seed, with the same harness.
