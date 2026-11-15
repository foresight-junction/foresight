# ED-72

An AI agent runs a fictional emergency department for three days. Every 30 minutes, it decides who gets a bed, which staff cover each zone, and who can take a break. A bed is only useful if someone can staff it. A doctor who works through the afternoon might faint during the night shift.

We built ED-72 for AfterQuery’s **Break the Agent** challenge at Junction 2026. We wanted to see whether an agent could make 144 decisions that hold up over a whole episode. The department has 17 beds, six doctors, nine nurses, a CT scanner, and a €12,000 budget. Patients arrive throughout the day. A flu wave or bus crash can fill the waiting room, and a broken CT can stall treatment. The agent can hire temporary staff, repair the scanner, or divert ambulances. Patients, staff, and events are synthetic.

[Watch a replay](#watch-a-replay) · [Run the benchmark](#reproduce-the-reported-results) · [See the scores](#reported-scores)

![ED-72 replay showing the hospital floor, waiting room, timeline, and score breakdown](docs/ed72-replay.png)

The scripted reference replay on seed 42, shown during the first night.

## Watch a replay

Use **Node.js 22** and **pnpm 10**, the versions used in CI. The viewer includes saved runs for the reference policy, a reactive baseline, and a replayed Gemini policy. It runs locally without Docker or a model key.

```bash
git clone https://github.com/xand1ex999/guinness.git
cd guinness/frontend
pnpm install --frozen-lockfile
pnpm dev
```

Open the URL Vite prints, usually `http://localhost:5173/`. Pick a replay, press play, or drag the timeline to see how the department changes. You can follow the beds, waiting room, staff, budget, and score breakdown from the same screen.

### Watch a new episode live

Keep Vite running. Install [uv](https://docs.astral.sh/uv/) and run this in a second terminal from the repository root. The scripted reference policy needs no key.

```bash
PYTHONPATH="ed72/environment/hospital:ed72/solution:eval/baselines:frontend/tools/live" \
  uv run --no-project --python 3.12 --with fastmcp==4.2.0 --with mcp==2.3.0 \
  python frontend/tools/live/serve.py --agent reference --seed 42
```

Add `?live=1` to the Vite URL. Use **New run** to choose a seed and agent. The live server saves replays under `frontend/public/replays/runs/` so you can reopen a run by adding `?replay=runs/<filename>` to your Vite URL. On Windows, run this command in WSL. The [live viewer guide](frontend/tools/live/README.md) also covers native Windows.

For a live model, set its key in the shell or in the repository root’s `.env`. Gemini uses `GEMINI_API_KEY`, Kimi uses `VERDA_INFERENCE_API_KEY`, and Claude uses `ANTHROPIC_API_KEY`. Add `--with anthropic` before `python` in the startup command to enable Claude. A live model calls its provider at every tick. The `reference` and `reactive` agents are free to run.

## Reproduce the reported results

The scored trials use Harbor with Docker Compose. Start Docker and install **Git, make, and uv**. The runner uses uv to launch Python 3.12 and Harbor 0.26.0. Set `GEMINI_API_KEY` in your shell or in the repository root’s gitignored `.env`. Copy [`.env.example`](.env.example) to `.env` if you need a template.

On Windows, use Ubuntu in WSL 2. Enable Ubuntu under Docker Desktop’s **Settings → Resources → WSL Integration**. In the Ubuntu terminal, install `git`, `make`, and [uv](https://docs.astral.sh/uv/), then check `docker info` and `docker compose version` before running the benchmark.

Run both commands from the repository root in a clean checkout.

```bash
git switch --detach 9f3bdbb9ddc24182b76b914874294fa5521c09be
ED72_SEED=3101 ED72_MODEL=gemini/gemini-3.8-flash make eval
```

`make eval` runs the reference policy, do-nothing, and stop-early before it starts three paid trials in parallel with OpenCode 1.19.5. Repeat in a clean checkout with seeds 3102 and 3103 for the rest of the Gemini subset. Model scores can vary across reruns. The published matrix also includes Kimi trials run separately through Verda. [Evaluated revision](https://github.com/xand1ex999/guinness/tree/9f3bdbb9ddc24182b76b914874294fa5521c09be) · [Final matrix and Harbor trial logs](https://github.com/xand1ex999/guinness/releases/tag/ed72-eval-20261115-002252)

For a keyless check at the pinned revision, run `ED72_SEED=3101 make eval-baselines`. The three baselines should score **95.86**, **0.00**, and **4.56** out of 100, respectively.

The runner writes `eval/results/summary.md` and keeps trial artifacts under `eval/results/jobs/`. In a trial directory, `verifier/reward.txt` holds the normalized reward, `verifier/score_full.json` has the score breakdown and patient outcomes, and model trials include `agent/trajectory.json`. The first Docker build can take several minutes. Each model trial has a 30-minute agent timeout. Check the **Completeness** section of the summary for six completed trials and zero failures. For a failed model trial, open its `exception.txt`. If Google reports `API_KEY_INVALID`, replace the key in `.env` with an active Gemini API key and check that an older shell variable is not overriding it. [Gemini API key setup](https://ai.google.dev/gemini-api/docs/api-key)

## How it works

The simulator is written in Python. Each seed fixes the patient arrivals and events. The agent sees the current state and can read the full rules in the [agent handbook](ed72/environment/workspace/HANDBOOK.md). It plays through three Model Context Protocol (MCP) tools.

| Tool | What it does |
| --- | --- |
| `rules` | Reads the handbook, including available actions and the scoring rules. |
| `observe` | Shows the queue, beds, staff, budget, event warnings, and rejected actions. |
| `step(actions)` | Applies up to 50 actions and advances the clock by 30 minutes. |

The TypeScript viewer draws saved replay files on a canvas. In live mode, a local Python server runs the same simulator and streams each completed tick to the browser with server-sent events. The live model agents choose actions one tick at a time. In the scored Harbor trials, OpenCode can write and run its own policy through the same public tools.

In Harbor, the agent container has the handbook and the `ward` CLI. The seed, simulator, event log, and scorer stay in a separate hospital container. After a trial, the collector rebuilds the episode from the seed and the hospital’s log. If the agent stops early, the remaining ticks run with empty actions and patients keep arriving. The verifier gets its reward from that replayed episode. [Tool contract](docs/CONTRACTS.md) · [Evaluation guide](docs/EVAL.md) · [Reward integrity report](docs/REDTEAM.md)

### Scoring

```text
Score = 60 × outcome + 20 × timeliness + outcome × (10 × staff wellbeing + 10 × budget)
Harbor reward = Score / 100
```

Patient outcome weights the sickest patients most heavily. Timeliness measures how soon a patient got a staffed bed. Staff wellbeing accounts for fatigue and faints, and the budget score falls once spending passes €12,000. The outcome multiplier limits the credit for keeping staff rested and saving money when patients go untreated.

## Reported scores

| Policy | Seed 3101 | Seed 3102 | Seed 3103 |
| --- | ---: | ---: | ---: |
| Reference | 95.86 | 96.02 | 94.21 |
| Do-nothing | 0.00 | 0.00 | 0.00 |
| Stop-early | 4.56 | 4.66 | 4.69 |
| Gemini 3.8 Flash, best completed run | 80.70 | 93.39 | 78.69 |
| Kimi K3.1 Pro, best completed run | 88.42 | 93.69 | 74.38 |

Scores are out of 100. On seed 3101, Gemini ranged from 8.19 to 80.70 over three completed trials. The final matrix shows every recorded attempt, including four Kimi timeouts with partial scores and one missing Kimi record. [Full results and logs](https://github.com/xand1ex999/guinness/releases/tag/ed72-eval-20261115-002252)

In an earlier calibration run, Gemini kept assigning agency staff to critical beds after their contracts had expired. The simulator rejected each assignment, but the policy kept treating those beds as staffed. Two critical patients the reference discharged never received a staffed bed in Gemini’s run. [Calibration run and score report](eval/results/2026-11-14-gemini-seed42/README.md)

## Repository guide

| Where | What is there |
| --- | --- |
| [`ed72/`](ed72/) | Harbor task, simulator, MCP server, scoring, tests, and reference policy |
| [`eval/`](eval/) | Runner, baseline policies, manifests, and result summaries |
| [`frontend/`](frontend/) | Browser replay viewer and local live server |
| [`docs/SPEC.md`](docs/SPEC.md) | Simulation rules, setup, and scoring specification |
| [`docs/DEMO.md`](docs/DEMO.md) | Demo walkthrough |

Run `pnpm test` from `frontend/` for the viewer tests. Run the simulator tests from the repository root.

```bash
(cd ed72/environment/hospital && uv run --with pytest pytest -q)
```

[MIT License](LICENSE)
