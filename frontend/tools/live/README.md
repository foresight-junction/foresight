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

From the worktree root (the PYTHONPATH separator is `;` on Windows, `:` elsewhere):

```bash
PYTHONPATH="ed72/environment/hospital;ed72/solution;eval/baselines;frontend/tools/live" \
  uv run --no-project --python 3.12 --with fastmcp==4.2.0 --with mcp==2.3.0 \
  python frontend/tools/live/serve.py --agent llm --seed 42
```

Then run the frontend dev server (`pnpm dev` in `frontend/`, which proxies `/live` to port 8770) and open its
URL with `?live=1`, e.g. `http://localhost:5170/?live=1`.

| Option | Default | |
|---|---|---|
| `--agent` | `llm` | `llm` (Gemini), `reference` (ReferencePolicy) or `reactive` (ReactiveProxy) |
| `--seed` | `42` | world seed; `ED72_CONFIG` picks a knob file as in the hospital image |
| `--model` | `gemini-3.8-flash` | the model of the team's Harbor calibration run |
| `--thinking-level` | `low` | Gemini `thinkingLevel`; higher is slower per tick |
| `--min-tick-seconds` | 0 for llm, 1 for scripted | minimum wall time per tick, so scripted play is watchable |
| `--mcp-port` / `--port` | `8000` / `8770` | MCP endpoint / SSE feed |
| `--env-file` | `<root>/.env` | `KEY=VALUE` lines; real environment variables win |
| `--save-dir` | `frontend/public/replays/runs` | every run is saved here as a replay file, rewritten after each tick |
| `--no-save` | off | keep the run in memory only |

`--agent llm` needs `GEMINI_API_KEY` and costs money: a full episode is 144 model calls.
The server keeps serving the finished replay after the episode; Ctrl+C stops it.

Every run is saved by default as `frontend/public/replays/runs/live-<agent>-seed<seed>-<date>-<time>.json`, a normal
replay file rewritten after each tick, so a crash or Ctrl+C keeps everything up to that tick. The folder is
gitignored. Open a saved run in the viewer with `?replay=runs/<file>` (serve.py prints the URL at start).
Any other MCP client (OpenCode, Claude Code) can connect to `http://127.0.0.1:8000/mcp` too, but every
`step` from any client advances the same episode.

## HTTP

- `GET /live/health` returns `{"ok": true}`.
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
PYTHONPATH="ed72/environment/hospital;ed72/solution;eval/baselines;frontend/tools/live" \
  uv run --no-project --python 3.12 --with pytest --with fastmcp==4.2.0 --with mcp==2.3.0 \
  python -m pytest -q frontend/tools/live/tests
```

They need no network or key. The recorder test plays the reference policy through `ToolHost` and
checks every tick against `export_replay.export()`. Event `seq` numbers differ from the offline export
because the live log also holds the agent's `rules` and `observe` calls.
