# ED-72: three days in an understaffed emergency department

**The idea.** The agent runs a fictional hospital emergency department for 72 hours: 144 decision rounds of 30 minutes each. Patients keep arriving, there are never enough doctors and nurses to staff every bed, people get tired, the CT breaks, a flu wave and a bus crash hit, and the money runs out if you panic. Good play is easy to define (fewer deaths, faster care, rested staff, budget kept) and hard to fake: every shortcut we could think of scores below honest play. It is a test of long-horizon decision-making under scarcity, not of one-shot tool use.

A [Harbor](https://github.com/laude-institute/harbor) task for the Junction 2026 AfterQuery challenge "Break the Agent". All patients, staff and events are synthetic and generated from a seed.

| | |
|---|---|
| **Agent's job** | Admit patients to beds, staff the zones, rotate rest, buy agency staff, repair the CT, divert ambulances. 144 ticks, up to 50 actions per tick |
| **Interface** | Three MCP tools on the `hospital` sidecar: `rules`, `observe`, `step(actions)`. Same functions via the `ward` CLI |
| **Reward** | `Score / 100` in [0, 1], computed from the hospital's event log. No LLM judge |
| **Result** | Reference 0.990, Gemini 3.8 Flash 0.812, do-nothing 0.000 (seed 42); every scripted shortcut ≤ 0.727 |

## Run it

Needs Docker (running) and [uv](https://docs.astral.sh/uv/). Harbor 0.26.0 runs through `uvx`.

```bash
alias harbor='uvx --python 3.12 --from harbor==0.26.0 harbor'

harbor run -p ed72 -a oracle          # reference policy (ed72/solution/), ~0.99
harbor run -p ed72 -a nop             # do nothing, scores 0

# A model through OpenCode. Tested with Gemini; OpenCode's Gemini provider needs the key under this name:
export GEMINI_API_KEY=...
harbor run -p ed72 -a opencode -m gemini/gemini-3.8-flash \
  --ae 'GOOGLE_GENERATIVE_AI_API_KEY=${GEMINI_API_KEY}' --ak version=1.19.5
```

Or the whole evaluation in one command. Set `ED72_MODEL` (`anthropic/…`, `openai/…` or `gemini/…`) and the matching key in `.env` (see `.env.example`); the script maps the key for each provider:

```bash
make eval              # reference, do-nothing and three OpenCode runs on seed 42
make eval-baselines    # reference and do-nothing only, no API key needed
```

Each trial writes `verifier/reward.txt` (one number), `verifier/score_full.json` (O, T, W, B, per-patient outcomes, failure counts) and `agent/trajectory.json`. The first build of the agent image takes about 14 minutes (it preinstalls OpenCode); after that, agent setup takes seconds.

## What the agent faces

- **Department:** 17 beds in three zones (Resus 3, Acute 8, Fast-track 6), an unlimited waiting room, one CT, a rest room. ESI 1 patients can only be treated in Resus, and patients never move between zones.
- **Patients:** severity ESI 1 (critical) to 5, shown on arrival, about 3 per tick with a daily peak around 15:00 (477 arrived on seed 42). A waiting ESI 1 has a 15% chance of dying every tick; an ESI 3 left waiting more than 6 ticks can become ESI 2; about half of ESI 1–2 need the CT.
- **Staff:** 6 doctors and 9 nurses. Covering all 17 beds needs 8 doctors and 9 nurses, so some beds are always uncovered, and only covered beds make treatment progress. Fatigue builds on shift and falls in the rest room; above 60 a person works at 0.6, at 90 they faint and are out for 10 ticks.
- **Money:** budget €12 000, hard limit €24 000. Agency doctor €900, agency nurse €350, CT repair €2 000. Diversion is free and lasts 4 ticks, but turns away 70% of arrivals, and diverted patients still count against you.
- **Events:** staff sickness and a CT breakdown (no warning), a flu wave (10 ticks' warning) and a bus crash (8 ticks' warning).

Everything needed to play well is in [`HANDBOOK.md`](ed72/environment/workspace/HANDBOOK.md) (served by `rules`) and in the observation. Only the future is hidden. Invalid actions are rejected with a reason and change nothing.

## Why it is hard

- **Scarcity every tick.** There are not enough staff to cover every bed, so each tick the agent chooses who goes untreated.
- **Delayed costs.** Fatigue builds over days and then whole shifts faint together. A light patient placed in Resus blocks the next critical arrival hours later. An ESI 3 left waiting gets worse.
- **Long horizon.** 144 dependent decisions; mistakes compound and cannot be undone.
- **Measured, not assumed.** Removing one skill from a reference-style policy costs points: no rest rotation **−42.5**, no Resus reservation for critical patients **−20.5** (seeds 1–3, [ablations, #36](https://github.com/xand1ex999/guinness/issues/36)).

## How it is scored

```
Score  = 60·O + 20·T + O·(10·W + 10·B)        reward = Score / 100  →  /logs/verifier/reward.txt
```

| Part | Weight | Measures |
|---|---|---|
| **O**, outcome | 60 | `1 − weighted loss / total weight` over every patient who arrived (weights 10/5/2/1/0.5 for ESI 1–5). Loss: discharged 0; still in bed at the end with care 0.3; diverted 0.7; died, left, never admitted or never covered 1 |
| **T**, timeliness | 20 | Weighted share of patients whose first *covered* bed tick met the target (0/1/4/8/12 ticks for ESI 1–5) |
| **W**, staff wellbeing | 10 × O | `max(0, 1 − share of on-shift staff-ticks above fatigue 60 − 0.05 × faints)` |
| **B**, budget | 10 × O | 1 up to €12 000, then linear to 0 at €24 000 |

W and B are multiplied by O, so rested staff and saved money are worth nothing if patients die. Do-nothing scores exactly 0.

**How the number is produced.** Every tool call is written to an append-only event log inside the `hospital` container. When the agent stops, [`collect.py`](ed72/environment/hospital/collect.py) rebuilds the world from the seed, replays the logged actions, runs any remaining ticks with no actions, and scores. A separate verifier container ([`tests/test.sh`](ed72/tests/test.sh)) reads only that report and writes the reward; it writes 0 on any error.

## Reward integrity

- **Nothing to read or forge in the agent's container.** It holds only the handbook, the `ward` CLI and OpenCode. The simulator, seed and scorer live in the `hospital` sidecar, and the verifier runs in Harbor's separate mode (an early spike showed shared mode lets a root agent forge the reward).
- **No back door.** Besides MCP there is only `GET /health`: no reset, undo, seed or finalise endpoint. Stopping early does not freeze the score; the remaining ticks run without the agent.
- **Shortcuts are played and must lose.** Scripted policies each try one trick through the same tools; a CI test checks they all score below the reference on every seed (scores out of 100, seeds 1–5):

| Policy | Score | | Policy | Score |
|---|---|---|---|---|
| Reference | 96.8–99.7 | | Divert all ambulances | 43.0–47.9 |
| Rest everyone in quiet periods | 55.8–72.7 | | Admit only light patients | 11.3–13.5 |
| Reactive proxy (typical play) | 57.8–67.2 | | Fill every bed at the last tick | ≤ 2.5 |
| Spend to the limit | 53.4–63.7 | | Stop after 12 ticks | ≤ 5.7 |
| Severity-first heuristic | 43.1–60.8 | | Admit without staff / do nothing | 0 |

- **Leak tests** check every tool output for the future, the seed or score values ([#31](https://github.com/xand1ex999/guinness/issues/31)). A [red team](docs/REDTEAM.md) tried 30 attacks: forged score reports, injected log lines, writing `reward.txt` from the agent side, malformed or 1000-action payloads, stopping early. None broke the reward; the three server-level checks still pending then are covered by the leak tests.

## Results

| Run (seed 42, Harbor 0.26.0) | Reward | Evidence |
|---|---:|---|
| Reference (`-a oracle`) | 0.989617 | [#17](https://github.com/xand1ex999/guinness/issues/17); identical to the in-process score |
| OpenCode + Gemini 3.8 Flash | **0.811712** | [run log: trajectory, score report, reward](eval/results/2026-11-14-gemini-seed42/README.md) |
| Do-nothing (`-a nop`) | 0.000000 | [#17](https://github.com/xand1ex999/guinness/issues/17) |

**What Gemini did.** It wrote a Python policy and played all 144 ticks through the public tools (148 calls, zero Harbor exceptions). It kept staff rested (W = 1, no faints) and spent €8 800 of the €12 000 budget (B = 1), but lost patients: of 477 arrivals, 426 were discharged, **13 died (8 of them in beds with no staff assigned)**, 9 left and 13 were never admitted (O = 0.833, T = 0.726). The reference keeps critical patients covered, which is where the 0.18 gap comes from.

## Known limits

- One model run so far; the multi-seed, multi-run matrix is in [#18](https://github.com/xand1ex999/guinness/issues/18).
- In the ablations, the event warnings, CT repair and agency staff are worth almost no points: the difficulty comes mainly from load, Resus reservation and rest rotation.
- `make eval` runs stop-early in-process, not through Harbor ([#83](https://github.com/xand1ex999/guinness/issues/83)).

## More

| Path | What |
|---|---|
| `ed72/` | The Harbor task: `instruction.md`, `task.toml`, `environment/`, `tests/`, `solution/` |
| `ed72/environment/hospital/` | Simulator (`ed72_sim/`), scorer (`ed72_sim/scoring/`), MCP server, `collect.py`, tests |
| `eval/` | `make eval` runner, baselines, results |
| [`docs/SPEC.md`](docs/SPEC.md), [`docs/CONTRACTS.md`](docs/CONTRACTS.md), [`docs/EVAL.md`](docs/EVAL.md), [`docs/TUNING.md`](docs/TUNING.md) | Rules, tool and score shapes, evaluation, difficulty tuning. Rulebook: [`docs/ED_Management_Simulator_RU.md`](docs/ED_Management_Simulator_RU.md) (Russian) |
| [`docs/DEMO.md`](docs/DEMO.md) | Demo walkthrough |

Tests: `(cd ed72/environment/hospital && uv run --with pytest pytest -q)`. Team workflow: [`AGENTS.md`](AGENTS.md).
