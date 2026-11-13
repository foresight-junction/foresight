# Contracts

The source of truth for everything two parts of the app share. Change it only through the `contract-change` skill (announce on the pinned Contracts issue #1, then a small separate PR).

## Ports and URLs
| Service | Local URL |
|---|---|
| Frontend | http://localhost:5173 |
| Backend | http://localhost:8000 |

## API routes
| Method | Path | Request body | Response | Owner |
|---|---|---|---|---|
| GET | /health | none | `{ "ok": true }` | infra |

## Data shapes
Define shared types once here, then mirror them in `backend/app/schemas.py` and `frontend/src/types.ts`.

```ts
// example
type Example = {
  id: string;
  createdAt: string; // ISO 8601
};
```

## Environment variables
| Name | Used by | Description |
|---|---|---|
| OPENAI_API_KEY | backend | OpenAI key |
| ANTHROPIC_API_KEY | backend | Anthropic key |
