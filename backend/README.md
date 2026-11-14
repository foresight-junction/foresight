# Unfindable backend

MCP environment, simulation, evaluator and spectator stream for the Unfindable benchmark. Design documents: `../docs/unfindable/`.

## Setup

With uv (as in CI):

```bash
uv sync
```

Without uv (Windows example):

```bash
py -3.13 -m venv .venv
.venv/Scripts/python -m pip install fastapi "uvicorn[standard]" "fastmcp>=2.12,<3" faker pydantic httpx pytest pytest-asyncio
```

## Run the server

```bash
Copy `.env.example` to `.env`, then run:

```bash
uv run uvicorn app.main:app --port 8000 --env-file .env
```
```

| URL | What |
|---|---|
| `http://localhost:8000/mcp` | MCP Streamable HTTP endpoint for agents |
| `http://localhost:8000/health` | `{"ok": true}` |
| `GET /observe/history?token=…`, `GET /observe/stream?token=…` | Spectator events (SSE) for the 3D frontend |
| `POST /admin/finalize` (header `X-Verifier-Token`) | Evaluator: freeze the episode, return reward and report |
| `POST /admin/reset` (header `X-Verifier-Token`) | Operator: start a new episode `{"scenario": "slice" \| "pilot", "profile": "v0.2" \| "proposed"}` |

Settings come from environment variables; see `.env.example`. Its token values are local placeholders. Set private values for shared environments. For Harbor evaluation runs set `UF_OBSERVE=0` and `UF_LIVE_REVEAL=0`.

## Connect an agent

Any MCP client that supports Streamable HTTP can connect to `http://localhost:8000/mcp`. To run the built-in agents:

```bash
uv run python -m agents.run --agent reference --url http://localhost:8000/mcp --reset pilot --pace 0.4 --finalize
```

Agents: `reference`, `do_nothing`, `deny_all`, `forward_all`, `release_all`, `stop_early`, `easy_only`, `cache_first`, `no_household`, `history_blind_statistics`.

## Run the evaluator

```bash
curl -X POST -H "X-Verifier-Token: $UF_VERIFIER_TOKEN" http://localhost:8000/admin/finalize
```

## Tests

```bash
uv run pytest -q
uvx ruff check .
```
