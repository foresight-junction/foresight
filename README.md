# ED-72

A Harbor task for the Junction 2026 AfterQuery challenge "Break the Agent". An agent runs a fictional hospital emergency department for 72 simulated hours: 144 ticks of 30 minutes, one decision round per tick. All patients, staff and events are synthetic and generated from a seed.

<!-- HUMAN: write the opening paragraph (3-5 sentences). Points to cover:
- What the agent is asked to do, in plain words: keep patients alive and treated on time in an ED that is short of staff, for three days.
- Why an ED: triage under scarcity is a setting where good play is easy to define (fewer deaths, shorter waits) and hard to fake.
- What the score measures: patient outcomes first (60 of 100 points), then timeliness, staff wellbeing and budget.
- Why it matters for agents: 144 dependent decisions, delayed consequences and resources that run out over days, not one-shot tool use.
- Keep numbers out of this paragraph until the Results section is filled.
-->

Rules: [`docs/ED_Management_Simulator_RU.md`](docs/ED_Management_Simulator_RU.md) (the rulebook, in Russian) and its English summary [`docs/SPEC.md`](docs/SPEC.md). Tool and score shapes: [`docs/CONTRACTS.md`](docs/CONTRACTS.md). How it is evaluated: [`docs/EVAL.md`](docs/EVAL.md). Demo script: [`docs/DEMO.md`](docs/DEMO.md).

## What the agent has to do

Every tick the agent reads the department's state and sends a list of actions. The episode starts at 08:00 on day 1 and always runs all 144 ticks, to 08:00 on day 4 (SPEC §4).

- **Department:** 17 beds in three zones (Resus 3, Acute 8, Fast-track 6), an unlimited waiting area, one CT scanner and a rest room. ESI 1 patients can only be treated in Resus.
- **Patients:** ESI 1 to 5 (1 is most critical), shown on arrival. Arrivals follow a daily cycle with a peak around 15:00. About half of ESI 1 and 2 patients need the CT. A waiting ESI 1 has a 15% chance of dying each tick; an ESI 3 left waiting more than 6 ticks can become ESI 2.
- **Staff:** 6 doctors and 9 nurses. Covering all 17 beds would need 8 doctors and 9 nurses, so some beds are always uncovered, and only covered beds make progress. Fatigue rises on shift and falls in the rest room; above 60 a person counts as 0.6, and at 90 they faint and are out for 10 ticks.
- **Money:** a €12 000 budget, with spending allowed up to a hard limit of €24 000. Agency doctors cost €900, agency nurses €350, a CT repair €2 000. Diverting ambulances for 4 ticks is free but turns away 70% of arrivals.
- **Events:** staff sickness (no warning), a flu wave (10 ticks' warning), a CT breakdown (no warning) and a bus crash (8 ticks' warning). Start ticks are drawn by the seed inside fixed windows.

The agent has three MCP tools, served by the `hospital` sidecar at `http://hospital:8000/mcp` (CONTRACTS "Tools (v1)"):

| Tool | What it does |
|---|---|
| `rules` | Returns the agent-visible rulebook (`HANDBOOK.md`), including every hazard rate and the score formula |
| `observe` | Returns the current state: time, budget, waiting patients, beds, staff, CT, warnings, diversion, running totals, last tick's rejected actions |
| `step(actions)` | Applies up to 50 actions (`admit`, `assign`, `agency`, `repair`, `divert`), runs the tick and returns per-action results plus the next observation. `step([])` passes a tick |

OpenCode lists them as `hospital_rules`, `hospital_observe` and `hospital_step` (seen in the #21 smoke run, `docs/HARBOR-NOTES.md`). Every call counts toward a 500-call cap; a full episode needs 144 `step` calls. A fallback CLI, `ward <tool> --json '<args>'`, calls the same functions from the agent container.

The observation shows current operating conditions and announced event warnings. There is no reset, no undo and no seed endpoint.

## Why it is hard

<!-- HUMAN: write this paragraph. Points to cover:
- Understaffed by design: 6 doctors and 9 nurses against the 8 and 9 needed to cover every bed, so the agent picks which beds go uncovered every tick.
- Costs land late: fatigue builds over days, an ESI 3 left waiting can upgrade after 6 ticks, and an unrepaired CT stops CT patients halfway through treatment for up to 16 ticks.
- Two of the four events give a warning (flu wave, bus crash) and two do not (staff sickness, CT breakdown), so the agent has to both prepare and react.
- Resus is the only zone for ESI 1, and there is no transfer between zones, so a light patient put in Resus can block the next critical arrival.
- Everything needed to play well is in the handbook and the observation; only the future is hidden (SPEC §8).
-->

## How to run it

Prerequisites:

- Docker, running.
- [uv](https://docs.astral.sh/uv/). Harbor 0.26.0 runs through `uvx`, no separate install.
- For agent runs only: one model key, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` or `GEMINI_API_KEY`. Export it in the shell for the `harbor run` commands below and set `ED72_MODEL` to the provider/model ID. For `make eval`, you can set both in `.env` using `.env.example`.

From the repo root:

```bash
alias harbor='uvx --python 3.12 --from harbor==0.26.0 harbor'

harbor run -p ed72 -a oracle                            # reference policy (ed72/solution/)
harbor run -p ed72 -a nop                               # do-nothing baseline, scores 0
harbor run -p ed72 -a opencode -m "$ED72_MODEL" --api-key-name "$KEY" \
  --ae "$OPENCODE_KEY=\${$KEY}" --ak version=1.19.5     # model run, see the table below
```

For a model run, export your provider's key, set `ED72_MODEL`, and set `KEY` and `OPENCODE_KEY` from this table. Harbor fills `${...}` from your shell, so the key itself never goes on the command line. Gemini is the provider we have run end to end; it needs the mapping because OpenCode's Google provider reads a different variable name.

| `ED72_MODEL` starts with | Key you export (`KEY`) | Variable OpenCode reads (`OPENCODE_KEY`) |
|---|---|---|
| `gemini/` or `google/` | `GEMINI_API_KEY` | `GOOGLE_GENERATIVE_AI_API_KEY` |
| `anthropic/` | `ANTHROPIC_API_KEY` | `ANTHROPIC_API_KEY` |
| `openai/` | `OPENAI_API_KEY` | `OPENAI_API_KEY` |

For example, for Gemini: `export KEY=GEMINI_API_KEY OPENCODE_KEY=GOOGLE_GENERATIVE_AI_API_KEY`. `make eval` does this mapping itself from `ED72_MODEL`.

Run the evaluation from the repository root:

```bash
make eval                # reference, do-nothing, and three OpenCode runs on seed 42
make eval-baselines      # reference and do-nothing, with no API key required
make eval-summary        # rebuild eval/results/summary.md from the latest run
```

`make eval` pins OpenCode 1.19.5 and writes each job under `eval/results/jobs/<run id>/`. The frozen build skips the Harbor stop-early adapter. [Harbor stop-early adapter (#83)](https://github.com/xand1ex999/guinness/issues/83). To rerun the scripted baselines in process, including stop-early, run:

```bash
(cd eval/baselines && PYTHONPATH=../../ed72/environment/hospital uv run python -m ed72_baselines.table 1 2 3 4 5)
```

**What a run produces.** Each trial directory holds:

| File | Contents |
|---|---|
| `verifier/reward.txt` | One number in [0, 1]: `score / 100`. `0` on any verifier error |
| `verifier/score_full.json` | The full score object: `O`, `T`, `W`, `B`, spend, totals, one entry per patient, failure counts, `ended` |
| `artifacts/evidence/report.json` | The same object as written inside the `hospital` container |
| `agent/trajectory.json` | The agent's tool calls (agent runs) |

## How it is scored

```
Score  = 60·O + 20·T + O·(10·W + 10·B)     in [0, 100]
reward = Score / 100                         written to /logs/verifier/reward.txt
```

| Part | Points | What it measures |
|---|---|---|
| O, outcome | 60 | `1 − weighted loss / total weight` over every patient who arrived, weights 10/5/2/1/0.5 for ESI 1-5. Loss is 0 for discharged, 0.3 for still in a bed at the end with at least one covered tick, 0.7 for diverted, 1 for died, left, never admitted, or in a bed that was never covered |
| T, timeliness | 20 | Weighted share of patients whose first **covered** bed tick came within target: 0/1/4/8/12 ticks for ESI 1-5 |
| W, wellbeing | 10 × O | `max(0, 1 − share of on-shift staff-ticks above fatigue 60 − 0.05 × faints)` |
| B, budget | 10 × O | 1 up to €12 000, then linear to 0 at €24 000 |

W and B are multiplied by O, so a department that treats nobody cannot collect them. Do-nothing scores 0.

The score is a pure function of the hospital's append-only event log (`/var/lib/ed72/events.jsonl` inside `hospital`). After the agent stops, `collect.py` rebuilds the world from the seed, replays the agent's `step` calls from the log, runs any remaining ticks with no actions, scores, and writes `/evidence/report.json` (`ed72/environment/hospital/collect.py`). The scorer is in `ed72/environment/hospital/ed72_sim/scoring/`. There is no LLM judge. The full rules are in SPEC §6 and CONTRACTS "Score object".

## Reward integrity

- **The answer is not in the agent's container.** The `main` image packages `HANDBOOK.md`, the `ward` CLI and the OpenCode runtime (`ed72/environment/Dockerfile`). The simulator, the seed (`ED72_SEED`, set only on the `hospital` service in `ed72/environment/docker-compose.yaml`) and the scorer live in the `hospital` sidecar.
- **The verifier cannot read agent-written files.** `ed72/task.toml` sets `environment_mode = "separate"` and a `[[verifier.collect]]` hook that runs `collect.py` inside `hospital`. `tests/test.sh` reads only `/evidence/report.json` from there. Shared mode is not used because a spike showed a root agent could forge the reward in it.
- **No admin back door.** The only HTTP endpoint besides MCP is `GET /health`. There is no finalise, reset, undo, seed or ground-truth endpoint.
- **Tool outputs are tested for leaks** (#31, `ed72/environment/hospital/tests/test_firewall.py`). Every tool result in a scripted episode is checked for future arrivals, unannounced events, the seed, dice values and score values, against exact CONTRACTS shapes, and against what the event log so far can explain. A test also checks that the `main` image copies no sim code, seed, config or scorer.
- **Shortcuts are played as baselines and must lose** (#12, `eval/baselines/` and `ed72/environment/hospital/ed72_sim/scoring/tests/test_baselines.py`). Scripted policies try one shortcut each through the same tools: divert all the time, rest everyone in quiet periods, admit only ESI 4-5, admit without staff, fill every bed at the last tick, spend to the limit, and random play. A CI test checks that do-nothing scores exactly 0, that stop-early scores below the reactive proxy and the reactive proxy below the reference, that every exploit scores below the reference, and that the same seed and actions give the same score.
- **Stopping does not end the episode.** If the agent stops, hits the call cap or times out, the remaining ticks run with no actions while patients keep arriving and dying. The score object's `ended` field records whether the agent played to `tick_143`, left ticks unplayed (`agent_stopped`) or hit the call cap (`call_cap`).
- **Rejected actions do nothing.** Invalid actions return a reason and have no effect, so spamming them gains nothing.

The shortcuts we expect judges to try first, and the rule that stops each, are listed in SPEC §11.

[Round 1 red-team report](docs/REDTEAM.md) records the probes, their outcomes and the regression tests. Its pending checks are tracked in [#14](https://github.com/xand1ex999/guinness/issues/14).

## Results

The shipped Harbor task uses seed 42 and an arrival mean of 3.0 patients per tick. The oracle and nop calibration runs used Harbor 0.26.0 on commit `ca9031c`. [Run details and job paths](https://github.com/xand1ex999/guinness/issues/17).

| Policy | Harbor command | Seed | Reward |
|---|---|---:|---:|
| Reference (oracle) | `harbor run -p ed72 -a oracle` | 42 | 0.989617 |
| Do-nothing (nop) | `harbor run -p ed72 -a nop` | 42 | 0.000000 |
| OpenCode, Gemini 3.8 Flash | [Gemini command](#how-to-run-it) | 42 | 0.811712 |

The Gemini calibration completed tick 143 with zero Harbor exceptions. [Trajectory, score report and reward](eval/results/2026-11-14-gemini-seed42/README.md).

The reference scored exactly 0.989617 on seed 42 both in process and through Harbor. Across seeds 1–5, the reference averaged 98.4 points out of 100 (range 96.78–99.69). Stop-early scored below the reactive proxy on all five seeds, and the proxy averaged 61.8. Do-nothing scored zero on every seed, divert-all peaked at 47.93 points, and the highest-scoring shortcut peaked at 72.72. Every tested shortcut scored below the reference on every seed. [Per-seed tuning table](docs/TUNING.md).

<!-- HUMAN: interpret the model results once #18 posts per-seed means and ranges.
Include the held-out seeds when results are available. Link the model's Harbor
trajectory and reward for the submission.
-->

## Model decisions

[Failure analysis (#19)](https://github.com/xand1ex999/guinness/issues/19) is pending model trajectories.

<!-- HUMAN: write this paragraph after #19. Points to cover:
- The two or three most consequential decisions, supported by the trajectory and score report. SPEC §2 lists the hypotheses F1-F10, for example F1 (light patients block Resus), F2 (no rest rotation), F3 (warnings ignored).
- One concrete moment from a trajectory: the tick, what the agent did, what the reference did instead, and what it cost.
- For each mistake, where the agent could have seen the information it needed (handbook section or observation field), which is the fairness check in #20.
-->

## Repository map

| Path | What is there |
|---|---|
| `ed72/` | The Harbor task. `harbor run -p ed72` points here |
| `ed72/task.toml` | Timeouts, separate verifier mode, the collect hook, the MCP server |
| `ed72/instruction.md`, `ed72/environment/workspace/HANDBOOK.md` | What the agent is told and the agent-visible rules |
| `ed72/environment/Dockerfile`, `ed72/environment/docker-compose.yaml` | The `main` agent image and the `hospital` sidecar service |
| `ed72/environment/hospital/ed72_sim/` | Seeded world (`world.py`), tick engine (`engine.py`), actions, observation, random streams |
| `ed72/environment/hospital/ed72_sim/scoring/` | The scorer and the baseline ordering test |
| `ed72/environment/hospital/server.py`, `ed72/environment/ward` | MCP tool server and the `ward` fallback CLI |
| `ed72/environment/hospital/collect.py` | Finishes the episode and writes `/evidence/report.json` |
| `ed72/environment/hospital/tests/` | Simulator, scorer, verifier and firewall tests |
| `ed72/tests/` | `test.sh` and `verify.py`: read the report, write `reward.txt` |
| `ed72/solution/` | The reference policy, public tools only |
| `eval/` | `run_all.sh`, `summarise.py`, `results/`, and the scripted baselines in `baselines/` |
| `docs/` | Rulebook, SPEC, CONTRACTS, EVAL, PLAN, CHALLENGE, Harbor notes, and the demo script `DEMO.md` |
| `scripts/` | Team tooling: `wt.sh` for worktrees, board scripts |

## Development

Lint and tests, from the repo root and inside each Python project you changed:

```bash
uvx ruff format . && uvx ruff check --fix .
(cd ed72/environment/hospital && uv run --with pytest pytest -q)
```

The team workflow (one issue, one branch, one worktree per task) is in [`AGENTS.md`](AGENTS.md).
