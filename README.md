# ED-72: three days in an understaffed emergency department

The agent runs a fictional hospital emergency department for 72 hours: 144 decision rounds of 30 minutes each. Patients keep arriving, there are never enough doctors and nurses to staff every bed, staff get tired, the CT breaks, a flu wave and a bus crash hit, and the budget runs out if the agent overspends. We chose an emergency department because good play there is easy to define (fewer deaths, faster care, rested staff, budget kept) and hard to fake. The score puts patient outcomes first (60 of 100 points), then timeliness, staff wellbeing and budget. The task tests 144 dependent decisions whose costs show up hours or days later, not one-shot tool use.

A [Harbor](https://github.com/laude-institute/harbor) task for the Junction 2026 AfterQuery challenge "Break the Agent". All patients, staff and events are synthetic and generated from a seed.

| | |
|---|---|
| **Agent's job** | Admit patients to beds, staff the zones, rotate rest, buy agency staff, repair the CT, divert ambulances. 144 ticks, up to 50 actions per tick |
| **Interface** | Three MCP tools on the `hospital` sidecar: `rules`, `observe`, `step(actions)`. The `ward` CLI calls the same functions |
| **Reward** | `Score / 100` in [0, 1], computed from the hospital's event log. No LLM judge |
| **Result** | Reference 0.990, Gemini 3.8 Flash 0.812, do-nothing 0.000 (seed 42, arrival mean 3.0). Every scripted shortcut scores 0.727 or less |

Rules: [`docs/ED_Management_Simulator_RU.md`](docs/ED_Management_Simulator_RU.md) (the rulebook, in Russian) and its English summary [`docs/SPEC.md`](docs/SPEC.md). Tool and score shapes: [`docs/CONTRACTS.md`](docs/CONTRACTS.md). Evaluation: [`docs/EVAL.md`](docs/EVAL.md). Demo script: [`docs/DEMO.md`](docs/DEMO.md).

## Run it

You need Docker (running) and [uv](https://docs.astral.sh/uv/). Harbor 0.26.0 runs through `uvx`, so it needs no separate install. From the repo root:

```bash
alias harbor='uvx --python 3.12 --from harbor==0.26.0 harbor'

harbor run -p ed72 -a oracle          # reference policy (ed72/solution/), about 0.99
harbor run -p ed72 -a nop             # do nothing, scores 0
```

To run a model through OpenCode, use the command from our Gemini calibration run. OpenCode's Google provider reads the key as `GOOGLE_GENERATIVE_AI_API_KEY`, so the command maps it. Harbor fills `${...}` from your shell, so the key never appears on the command line:

```bash
export GEMINI_API_KEY=...
harbor run -p ed72 -a opencode -m gemini/gemini-3.8-flash \
  --ae 'GOOGLE_GENERATIVE_AI_API_KEY=${GEMINI_API_KEY}' --ak version=1.19.5
```

For other providers, export that provider's key and point `--ae` at the variable OpenCode reads:

| Model prefix | Key you export | Variable OpenCode reads |
|---|---|---|
| `gemini/` or `google/` | `GEMINI_API_KEY` | `GOOGLE_GENERATIVE_AI_API_KEY` |
| `anthropic/` | `ANTHROPIC_API_KEY` | `ANTHROPIC_API_KEY` |
| `openai/` | `OPENAI_API_KEY` | `OPENAI_API_KEY` |

Only Gemini has been run end to end.

To run the whole evaluation in one command, set `ED72_MODEL` (for example `gemini/gemini-3.8-flash`) and the matching key in `.env` (copy `.env.example`). `eval/run_all.sh` picks the key and the mapping from the model prefix:

```bash
make eval              # reference, do-nothing, then 3 OpenCode runs on $ED72_MODEL, seed 42
make eval-baselines    # reference and do-nothing only, no API key needed
make eval-summary      # rebuild eval/results/summary.md from the latest run
```

`make eval` pins OpenCode 1.19.5. It writes each job under `eval/results/jobs/<run id>/` and the results table to `eval/results/summary.md`. Stop-early is not a Harbor agent, so `make eval` prints a SKIP line for it. Stop-early and the other scripted baselines run in process:

```bash
(cd eval/baselines && PYTHONPATH=../../ed72/environment/hospital uv run python -m ed72_baselines.table 1 2 3 4 5)
```

The first build of the agent image takes about 14 minutes because it preinstalls OpenCode. After that, agent setup takes seconds.

**What a run produces.** Each trial directory holds:

| File | Contents |
|---|---|
| `verifier/reward.txt` | One number in [0, 1]: `score / 100`. `0` on any verifier error |
| `verifier/score_full.json` | The full score object: `O`, `T`, `W`, `B`, spend, totals, one entry per patient, failure counts, `ended` |
| `artifacts/evidence/report.json` | The same object as written inside the `hospital` container |
| `agent/trajectory.json` | The agent's tool calls (agent runs only) |

## What the agent faces

The episode starts at 08:00 on day 1 and always runs all 144 ticks, to 08:00 on day 4.

- **Department:** 17 beds in three zones (Resus 3, Acute 8, Fast-track 6), an unlimited waiting room, one CT and a rest room. ESI 1 patients can only be treated in Resus, and patients never move between zones.
- **Patients:** severity ESI 1 (critical) to 5, shown on arrival, about 3 per tick with a daily peak around 15:00 (477 arrived on seed 42 at arrival mean 3.0). A waiting ESI 1 has a 15% chance of dying every tick. An ESI 3 left waiting more than 6 ticks can become ESI 2. About half of ESI 1 and 2 patients need the CT.
- **Staff:** 6 doctors and 9 nurses. Covering all 17 beds needs 8 doctors and 9 nurses, so some beds are always uncovered, and only covered beds make treatment progress. Fatigue builds on shift and falls in the rest room. Above 60 a person counts as 0.6; at 90 they faint and are out for 10 ticks.
- **Money:** budget €12 000, hard limit €24 000. Agency doctor €900, agency nurse €350 (they arrive after 4 ticks and leave 16 ticks later), CT repair €2 000. Diversion is free and lasts 4 ticks, but turns away 70% of arrivals, and diverted patients still count against the score.
- **Events:** staff sickness and a CT breakdown (no warning), a flu wave (10 ticks' warning) and a bus crash (8 ticks' warning). Start ticks are drawn by the seed inside fixed windows.

The three tools, served at `http://hospital:8000/mcp` (CONTRACTS "Tools (v1)"):

| Tool | What it does |
|---|---|
| `rules` | Returns the agent-visible rulebook ([`HANDBOOK.md`](ed72/environment/workspace/HANDBOOK.md)), including every hazard rate and the score formula |
| `observe` | Returns the current state: time, budget, waiting patients, beds, staff, CT, warnings, diversion, running totals, last tick's rejected actions |
| `step(actions)` | Applies up to 50 actions (`admit`, `assign`, `agency`, `repair`, `divert`), runs the tick and returns per-action results plus the next observation. `step([])` passes a tick |

OpenCode lists them as `hospital_rules`, `hospital_observe` and `hospital_step`. Every call counts toward a 500-call cap; a full episode needs 144 `step` calls. There is no reset, no undo and no seed endpoint. Invalid actions are rejected with a reason and change nothing.

## Why it is hard

The department is understaffed by design. 6 doctors and 9 nurses cannot cover 17 beds (that needs 8 and 9), so every tick the agent decides which beds go uncovered and who waits. Most costs land late. Fatigue builds over days until staff faint together. An ESI 3 left waiting can become ESI 2 after 6 ticks. A broken CT stops CT patients halfway through treatment for up to 16 ticks unless the agent pays for a repair. Two events come with a warning (flu wave, bus crash) and two do not (staff sickness, CT breakdown), so the agent has to both prepare and react. Resus is the only zone that can treat ESI 1 and patients never change zone, so a light patient placed in Resus can block the next critical arrival hours later. Everything needed to play well is in the handbook and the observation; only the future is hidden (SPEC §8).

The ablations show these levers matter. Removing one skill from a reference-style policy costs points on seeds 1–3: no rest rotation **−42.5**, no Resus reservation for critical patients **−20.5** ([#36](https://github.com/xand1ex999/guinness/issues/36)).

## How it is scored

```
Score  = 60·O + 20·T + O·(10·W + 10·B)        reward = Score / 100  →  /logs/verifier/reward.txt
```

| Part | Weight | Measures |
|---|---|---|
| **O**, outcome | 60 | `1 − weighted loss / total weight` over every patient who arrived (weights 10/5/2/1/0.5 for ESI 1–5). Loss: discharged 0; still in a bed at the end with at least one covered tick 0.3; diverted 0.75; died, left, never admitted or never covered 1 |
| **T**, timeliness | 20 | Weighted share of patients whose first *covered* bed tick met the target (0/1/4/8/12 ticks for ESI 1–5) |
| **W**, staff wellbeing | 10 × O | `max(0, 1 − share of on-shift staff-ticks above fatigue 60 − 0.05 × faints)` |
| **B**, budget | 10 × O | 1 up to €12 000, then linear to 0 at €24 000 |

W and B are multiplied by O, so rested staff and saved money are worth nothing if patients die. Do-nothing scores exactly 0.

**How the number is produced.** Every tool call is written to an append-only event log inside the `hospital` container (`/var/lib/ed72/events.jsonl`). When the agent stops, [`collect.py`](ed72/environment/hospital/collect.py) rebuilds the world from the seed, replays the logged actions, runs any remaining ticks with no actions, scores, and writes `/evidence/report.json`. The verifier ([`tests/test.sh`](ed72/tests/test.sh)) reads only that report and writes the reward, or 0 on any error. The scorer is in `ed72/environment/hospital/ed72_sim/scoring/`. Full rules: SPEC §6 and CONTRACTS "Score object".

## Reward integrity

- **Nothing to read or forge in the agent's container.** It holds only the handbook, the `ward` CLI and OpenCode (`ed72/environment/Dockerfile`). The simulator, the seed (`ED72_SEED`, set only on the `hospital` service) and the scorer live in the `hospital` sidecar. `ed72/task.toml` sets `environment_mode = "separate"` with a collect hook inside `hospital`. We don't use shared mode because an early spike showed a root agent could forge the reward in it.
- **No back door.** Besides MCP there is only `GET /health`: no reset, undo, seed, ground-truth or finalise endpoint.
- **Stopping does not end the episode.** If the agent stops, hits the call cap or times out, the remaining ticks run with no actions while patients keep arriving and dying. The score object's `ended` field records `tick_143`, `agent_stopped` or `call_cap`.
- **Shortcuts are played and must lose.** Scripted policies each try one trick through the same tools. A CI test checks that do-nothing scores exactly 0, stop-early scores below the reactive proxy, the proxy scores below the reference, every exploit scores below the reference, and the same seed and actions give the same score (`ed72/environment/hospital/ed72_sim/scoring/tests/test_baselines.py`). Scores out of 100, seeds 1–5 ([`docs/TUNING.md`](docs/TUNING.md)):

<!-- Difficulty-dependent: these ranges come from docs/TUNING.md and change if the SPEC §7 knobs are retuned. -->
| Policy | Score | | Policy | Score |
|---|---|---|---|---|
| Reference | 96.8–99.7 | | Divert all ambulances | 43.0–47.9 |
| Rest everyone in quiet periods | 55.8–72.7 | | Admit only light patients | 11.3–13.5 |
| Reactive proxy (typical play) | 57.8–67.2 | | Fill every bed at the last tick | 2.5 or less |
| Spend to the limit | 53.4–63.7 | | Stop after 12 ticks | 5.7 or less |
| Severity-first heuristic | 43.1–60.8 | | Admit without staff, or do nothing | 0 |

- **Leak tests** check every tool result in a scripted episode for future arrivals, unannounced events, the seed, dice values and score values. They also check that the `main` image copies no sim code, seed or scorer ([#31](https://github.com/xand1ex999/guinness/issues/31), `ed72/environment/hospital/tests/test_firewall.py`).
- **Red team.** [Round 1](docs/REDTEAM.md) tried forged score reports, injected log lines, writing `reward.txt` from the agent side, malformed and 1000-action payloads, and stopping early. None changed the reward. SPEC §11 lists the shortcuts we expect judges to try first and the rule that stops each.

## Results

<!-- Difficulty-dependent: the seed-42 rewards below, the Result row in the summary table at the top and the gap figures change if the SPEC §7 knobs are retuned and the runs are repeated. -->
| Run (seed 42, arrival mean 3.0, Harbor 0.26.0) | Reward | Evidence |
|---|---:|---|
| Reference (`-a oracle`) | 0.989617 | [#17](https://github.com/xand1ex999/guinness/issues/17); the in-process score is identical |
| OpenCode + Gemini 3.8 Flash | **0.811712** | [Run log: trajectory, score report, reward](eval/results/2026-11-14-gemini-seed42/README.md) |
| Do-nothing (`-a nop`) | 0.000000 | [#17](https://github.com/xand1ex999/guinness/issues/17) |

**What the numbers say.** All runs here used arrival mean 3.0 per tick. The gap on seed 42 is 0.178 reward (17.8 points), and almost all of it is patient outcome. Gemini kept staff rested (W = 1, no faints) and spent €8 800 of the €12 000 budget (B = 1), so it lost nothing on wellbeing or money. It lost on O (0.833 against the reference's 0.997) and T (0.726 against 0.959). The seed fixes the arrivals, so both runs saw the same 477 patients. The reference discharged 474 of them with no deaths. Gemini discharged 426, and 13 patients died, all of them ESI 1. Only 3 of the 20 ESI 1 patients got a covered bed on time, against 16 for the reference. The Gemini run played all 144 ticks with zero Harbor exceptions.

This is one model (Gemini 3.8 Flash), one trial, one seed, at arrival mean 3.0. The repeated-run, multi-seed matrix is tracked in [#18](https://github.com/xand1ex999/guinness/issues/18). Until it lands, the measured gap is Gemini on seed 42 at arrival mean 3.0, not a mean across models or seeds.

## Model decisions

In the seed-42 run at arrival mean 3.0, Gemini read the handbook, wrote a Python policy (`/app/run_ed.py`), checked that it compiled, and ran it once for all 144 ticks through the public MCP tools (148 calls). Two decisions in that policy account for most of the lost points. The evidence is in the [trajectory](eval/results/2026-11-14-gemini-seed42/trajectory.json) and the [score report](eval/results/2026-11-14-gemini-seed42/score_full.json).

1. **It staffed Resus with agency workers who had already left.** The policy filled each zone with agency staff first, then permanent staff for whatever was still needed, and sent everyone else to rest. To skip unavailable staff it checked for status names it guessed (`ordered`, `departed`), but the observation uses `agency_ordered` and `agency_left`. So after the agency contracts ended, the policy kept assigning those workers. At tick 121 (day 3, 20:30) it sent AD1, AN1 and AN2 to Resus, and all three were rejected with `staff_unavailable`. The plan had counted those workers toward Resus's need, so it assigned no permanent staff there. P424, an ESI 1 admitted to Resus at tick 120, never got a covered tick and died. P436 (ESI 1, admitted at tick 123) died the same way. On the same seed, the reference covered both on their arrival tick and discharged them. The score report counts 8 deaths in beds that had a patient but no staff covering them (F7, "admits to beds it cannot cover"). The agent had what it needed to avoid this. HANDBOOK §3 says agency staff leave 16 ticks after arrival and that departed agency staff cannot be assigned. Every staff entry in the observation has `status` and `ticks_until_change`. HANDBOOK §6 says to check `last_rejected` before the next tick. The policy printed each rejection to stderr and repeated the same assignments every tick until the end.
2. **It kept no Resus bed in reserve.** When Acute was full, the policy put ESI 2 patients into Resus as soon as one Resus bed was free. The reference keeps one Resus bed free for the next ESI 1. Five ESI 1 patients died in the waiting room without ever being admitted (P070, arrived at tick 14; P234, tick 62; P360 and P362, tick 104; P441, tick 124), and Resus is the only zone that could have treated them. The run log does not show Resus occupancy at those ticks, so we cannot pin each death on this rule. It is the lever the ablation prices at −20.5 points. HANDBOOK §2 states the zone rule (only Resus takes ESI 1, no transfers) and §4 the 15% death risk per waiting tick.

The agent's final message said its staffing "ensured emergency coverage", while the observation it had just read showed 13 deaths. It never compared its policy against the running totals during the episode.

## Repository map

| Path | What is there |
|---|---|
| `ed72/` | The Harbor task: `instruction.md`, `task.toml`, `environment/`, `tests/`, `solution/`. `harbor run -p ed72` points here |
| `ed72/environment/workspace/HANDBOOK.md` | The agent-visible rules |
| `ed72/environment/hospital/` | Simulator (`ed72_sim/`), scorer (`ed72_sim/scoring/`), MCP server (`server.py`), `collect.py`, tests |
| `ed72/solution/` | The reference policy, public tools only |
| `eval/` | `run_all.sh` (behind `make eval`), `summarise.py`, scripted baselines in `baselines/`, results in `results/` |
| `docs/` | Rulebook, SPEC, CONTRACTS, EVAL, TUNING, REDTEAM, demo script `DEMO.md` |

## Development

```bash
uvx ruff format . && uvx ruff check --fix .
(cd ed72/environment/hospital && uv run --with pytest pytest -q)
```

The team workflow (one issue, one branch, one worktree per task) is in [`AGENTS.md`](AGENTS.md).
