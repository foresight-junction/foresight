# Live mode for the pixel viewer

One ED-72 episode played in real time and streamed to the browser tick by tick.

- `serve.py` starts the real hospital MCP tool server (`ed72/environment/hospital/server.py`, imported,
  not copied) on `127.0.0.1:8000/mcp` over a seeded `Simulation`, plus an SSE feed on `127.0.0.1:8770`.
- `agent.py` plays through that MCP endpoint as an ordinary client: `rules`, `observe`, then one `step`
  per tick. The decider is Gemini (`gemini.py`, one REST call per tick) or a scripted policy.
- `recorder.py` sits between the tool server and the sim. Each finished tick becomes a `ReplayTick`,
  built the same way `export_replay.py` builds them, and goes out as a `LiveMessage`
  (`frontend/src/replay/types.ts`).

## Run

From the repository root in Bash on macOS, Linux, or WSL:

```bash
PYTHONPATH="ed72/environment/hospital:ed72/solution:eval/baselines:frontend/tools/live" \
  uv run --no-project --python 3.12 --with fastmcp==4.2.0 --with mcp==2.3.0 --with anthropic \
  python frontend/tools/live/serve.py --agent gemini --seed 42
```

`--with anthropic` is only needed for the Claude agent.

Then run the frontend dev server (`pnpm dev` in `frontend/`, which proxies `/live` to port 8770) and open its
URL with `?live=1`, e.g. `http://localhost:5173/?live=1` (Vite's default port).

| Option | Default | |
|---|---|---|
| `--agent` | `gemini` | `gemini`, `kimi`, `claude`, `reference` (ReferencePolicy) or `reactive` (ReactiveProxy); `llm` still means `gemini` |
| `--seed` | `42` | world seed; `ED72_CONFIG` picks a knob file as in the hospital image |
| `--gemini-model` | `gemini-3.8-flash` | needs `GEMINI_API_KEY`; the model of the team's Harbor calibration run |
| `--thinking-level` | `low` | Gemini `thinkingLevel`; higher is slower per tick |
| `--kimi-model` / `--kimi-effort` | `kimi-k3-1-pro` / `low` | Kimi on Verda Inference, needs `VERDA_INFERENCE_API_KEY`; effort `none`, `low`, `high` or `max` |
| `--claude-model` / `--claude-effort` | `claude-opus-5-5` / `medium` | Claude through the `anthropic` SDK, needs `ANTHROPIC_API_KEY`; effort `low` to `max` |
| `--min-tick-seconds` | 0 for models, 1 for scripted | minimum wall time per tick, so scripted play is watchable |
| `--mcp-port` / `--port` | `8000` / `8770` | MCP endpoint / SSE feed |
| `--env-file` | `<root>/.env` | `KEY=VALUE` lines; repeat for several files; real environment variables win |
| `--save-dir` | `frontend/public/replays/runs` | every run is saved here as a replay file, rewritten after each tick |
| `--no-save` | off | keep the run in memory only |

Each model agent is offered only when its key is set, and costs money: a full episode is 144 model calls.
All three share the prompt and reply parsing (`llm.py`): one stateless call per tick with the handbook as
the system prompt (Claude reads it from the prompt cache after the first tick), and JSON
`{thought, actions}` back. Claude also uses structured outputs and `fallbacks: "default"`, so a request
its safety classifiers decline is re-run on Anthropic's recommended fallback model.
The server keeps serving the finished replay after the episode; Ctrl+C stops it.

Every run is saved by default as `frontend/public/replays/runs/live-<agent>-seed<seed>-<date>-<time>.json`, a normal
replay file rewritten after each tick, so a crash or Ctrl+C keeps everything up to that tick. The folder is
gitignored. Open a saved run in the viewer with `?replay=runs/<file>` (serve.py prints the URL at start).
Any other MCP client (OpenCode, Claude Code) can connect to `http://127.0.0.1:8000/mcp` too, but every
`step` from any client advances the same episode.

## HTTP

- `GET /live/health` returns `{"ok": true, "agents": [...]}`, the agents a new run can use (each model only with its key).
- `POST /live/start` with `{"seed": 7, "agent": "gemini|kimi|claude|reference|reactive"}` starts a new episode (202). A run still
  playing is cut short and its saved file marked as stopped. Every open viewer gets the new run as a snapshot with
  a new `meta.live.run`. The viewer's **New run** form (seed, agent) in live mode sends this.
- `GET /live/stream` is `text/event-stream`, one `data: <json>` line per message and a `: ping` comment
  every 15 s. The first message is a `snapshot` (finished ticks, the current `head`, `final_obs` once
  done), then `status` (agent state changes), `step` (one finished tick plus the new head) and `done`
  (reward and score from the event log, and the final observation).

`meta.live.state` goes `starting` → `thinking` ⇄ `acting` → `done`. If the model fails for good (a 4xx,
or three ticks in a row without a usable reply) the state becomes `error` with `meta.live.error` set,
and the agent waits out the episode with empty steps so the replay stays complete. `done` keeps the
`error` field.

## Tests

```bash
PYTHONPATH="ed72/environment/hospital:ed72/solution:eval/baselines:frontend/tools/live" \
  uv run --no-project --python 3.12 --with pytest --with fastmcp==4.2.0 --with mcp==2.3.0 --with anthropic \
  python -m pytest -q frontend/tools/live/tests
```

After uv resolves the dependencies, the tests run without a model API key. The recorder test plays the reference policy through `ToolHost` and
checks every tick against `export_replay.export()`. Event `seq` numbers differ from the offline export
because the live log also holds the agent's `rules` and `observe` calls.
