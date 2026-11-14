# Contracts

Shared interfaces for the frontend, backend, and Harbor task. Change this file only through the `contract-change` skill (announce on issue #1 and open a small separate PR).

## Local URLs

| Service | URL |
|---|---|
| Frontend | http://localhost:5173 |
| Backend | http://localhost:8000 |

## HTTP API

| Method | Path | Request | Response | Access |
|---|---|---|---|---|
| GET | `/health` | none | `{ "ok": true }` | public |
| GET | `/observe/history?token={token}&after_seq={seq}` | none | `ObservationEvent[]` with `seq > after_seq` | spectator token |
| GET | `/observe/stream?token={token}` | none | Server-Sent Events named `observation`; each data field is an `ObservationEvent` JSON object | spectator token |
| POST | `/admin/finalize` | `X-Verifier-Token` header | `{ "reward": Reward, "report": object }` | verifier token |
| POST | `/admin/reset` | `X-Verifier-Token` header, `ResetRequest` JSON | `{ "episode_id": string, "scenario": string, "profile": string, "total_requests": number }` | verifier token |

`/admin/finalize` freezes the current episode. The result is stable if requested again. The agent must not call it; Harbor's evaluator does.

## MCP API

The MCP Streamable HTTP endpoint is `/mcp`. It exposes `get_policy`, `next_request`, `get_requester`, `verify_identity`, `find_person`, `get_person`, `search_residents`, `get_household`, `check_protection`, `verify_authority`, `count_residents`, `get_release_log`, and `respond`. Tool input and output fields are defined by the server's MCP tool schemas and `docs/unfindable/MCP_CONTRACTS.md`.

## Shared JSON shapes

```ts
type Visibility = 'agent_observable' | 'spectator' | 'evaluator_reveal'

type Department =
  | 'reception'
  | 'identity'
  | 'registry'
  | 'protection'
  | 'authority'
  | 'statistics'
  | 'decision'

type ObservationEvent = {
  v: 1
  seq: number // >= 1; increases across episodes
  ts: string // UTC ISO 8601 timestamp
  episode_id: string
  type: string // one of the event types in backend/app/schemas.py
  visibility: Visibility
  request_id: string | null
  response_index: number // >= 0
  department: Department | null
  tool: string | null
  call_id: string | null
  display: Record<string, unknown>
}

type Reward = {
  reward: number // 0..1
  service: number
  completion: number
  critical_leaks: number
  minor_leaks: number
  over_refusals: number
  answered: number
  total: number
}

type ResetRequest = {
  scenario?: string | null
  seed?: number | null
  profile?: string | null
}
```

The event version is `1`. Event names and their typed display payloads are mirrored in `backend/app/schemas.py`, `frontend/src/types.ts`, and `docs/unfindable/EVENT_SCHEMA.md`.

## Environment variables

| Name | Used by | Description |
|---|---|---|
| `OPENAI_API_KEY` | optional local model agent | OpenAI credentials for a model run |
| `ANTHROPIC_API_KEY` | optional local model agent | Anthropic credentials for a model run |
| `UF_SCENARIO` | backend | Initial scenario name; defaults to `slice` |
| `UF_SEED` | backend | Optional deterministic scenario seed |
| `UF_PROFILE` | backend | Policy profile; defaults to `v0.2` |
| `UF_OBSERVE` | backend | Enables or disables spectator events |
| `UF_LIVE_REVEAL` | backend | Controls evaluator-only reveal events during play |
| `UF_SPECTATOR_TOKEN` | backend and frontend | Required token for observe history and stream; set in local `.env` files |
| `UF_VERIFIER_TOKEN` | backend and Harbor verifier | Required token for evaluator-only admin routes; generated at runtime in Harbor |
| `UF_CORS_ORIGINS` | backend | Comma-separated allowed frontend origins |
| `VITE_BACKEND_URL` | frontend | Backend base URL; defaults to `http://localhost:8000` |
| `VITE_SPECTATOR_TOKEN` | frontend | Spectator token; set to the same local value as `UF_SPECTATOR_TOKEN` |
