# Migration: Unfindable to the Emergency Department Management Simulator

Branch: `kostiantyn/env-ed-sim`, cut from `kostiantyn/env-unfindable-slice` at `57d26a7`. The Unfindable branch stays as it is, so nothing from the old environment is lost.

## 1. Repository audit (2026-11-14)

Starting state: the backend test suite passes (57 tests). Harbor 0.26.0 is in the root `.venv/`, Docker 28.4 is available, and the backend venv is `backend/.venv` (Python 3.13; `uv` is not on PATH on this laptop). The root `.env` (gitignored) holds `MOONSHOT_API_KEY` and `VERDA_INFERENCE_API_KEY`. The last recorded model run was OpenCode 1.19.5 with Verda Kimi K3.1 Pro, which scored 1.0 on the Unfindable task (logs in `.venv/harbor-jobs/verda-kimi/`).

| # | Area | Where | What it is today |
|---|---|---|---|
| 1 | Backend / simulation | `backend/app/sim/` | `EpisodeService`: a request-queue state machine (one request in flight, scheduled rule changes after the Nth response), backed by in-memory SQLite (`store.py`) |
| 2 | Entities and seeds | `sim/domain.py`, `sim/scenario.py`, `scenarios/*.json` | Persons, households, Safety Non-Disclosure Orders, requesters (bank, courier, police and so on), cases. JSON scenarios plus Faker, generated from a seed |
| 3 | MCP server | `app/mcp_server.py` | FastMCP 2.14.7 with 13 registry tools. One generic `run()` wrapper handles call IDs, start/finish events, error masking (`UFError` becomes a JSON `ToolError`) and logging. Mounted at `/mcp` (streamable HTTP) |
| 4 | Harbor task | `harbor/unfindable/` | Schema 1.4, separate verifier mode, a sidecar service `unfindable` (a copy of `backend/app`), `collect.py` calling `/admin/finalize` with a runtime-generated token, `verify.py` writing `/logs/verifier/reward.txt`, and an oracle `solution/` that runs the reference agent over MCP |
| 5 | OpenCode | Harbor `-a opencode` | Configured on the Harbor command line (`-m verda/kimi-k3-1-pro --base-url ... --api-key-name VERDA_INFERENCE_API_KEY --env-file .env`). The repo holds no OpenCode config files |
| 6 | Kimi config | root `.env` | Key names only, never committed. The command is recorded in `.context/kostiantyn-env-unfindable-slice.md` |
| 7 | Evaluation | `sim/evaluator.py`, `sim/policy.py` | Privacy oracle (`Truth`): per-request correctness, critical and minor leaks; reward = 0 on any critical leak |
| 8 | Reference agent | `backend/agents/reference.py` | Deterministic policy-following agent that uses only MCP (`EnvClient`) |
| 9 | Baselines | `backend/agents/baselines.py`, `agents/run.py` | do-nothing, deny-all, forward-all, release-all and shortcut agents; a CLI runner with `--reset` / `--finalize` through admin routes |
| 10 | Docker | `harbor/unfindable/environment/` | `main` agent container plus `unfindable` sidecar with a healthcheck; pinned pip versions |
| 11 | Tests | `backend/tests/` | Episode, MCP contract (exact tool set, no hidden keys), observation bus, policy, reward |
| 12 | Frontend | `frontend/` | React 19 + react-three-fiber 3D "office" with 7 departments, avatars, request folders, HUD (timeline, score, leak alerts, replay). Fed by `/observe/stream` (SSE) or a replay JSON file. Vitest for `applyEvent` |
| 13 | Docs | `README.md`, `backend/README.md`, `docs/CONTRACTS.md`, `docs/unfindable/*` (13 files) | All describe Unfindable |
| 14 | Old-domain terms | ~100 files | SNO, households, residents, bank/courier/police, disclosure and leaks appear in all of the above |

## 2. Migration inventory

**PRESERVED** (generic, kept as is):
- Harbor task skeleton: separate verifier, sidecar service, runtime verifier token, `collect.py` → `/evidence/*.json` artifact → `verify.py` → `/logs/verifier/reward.txt`, and `test.sh` writing a 0.0 fallback.
- `ObservationBus` (`sim/observe.py`): one-way spectator stream with seq numbers and history; the `/observe/history` and `/observe/stream` SSE routes.
- `/health`, `/admin/finalize`, `/admin/reset` with constant-time token checks.
- `agents/mcp_client.py` (`EnvClient`, works in-process and over HTTP) and the `agents/run.py` harness pattern.
- Test pattern: in-process FastMCP client (`run_agent`), an exact-tool-set contract test, and a hidden-keys leak test.
- CI workflow, ruff and pytest config, agent workflow kit, `scripts/wt.sh`.
- `spikes/s0-harbor/`: the transport and security spike. Its tests use generic names, so it stays as historical evidence.
- Frontend tooling: Vite, R3F, drei, zustand, vitest, the SSE and replay hooks, camera rig, labels and effects.

**ADAPTED** (kept structure, new domain):
- `mcp_server.py`: same `run()` wrapper, new ED tools.
- `settings.py` / `AppState`: `ED_*` settings (difficulty, seed, horizon) and a new engine in place of `EpisodeService`.
- `schemas.py`, `docs/CONTRACTS.md`, `frontend/src/types.ts`: new event types and zones (through `contract-change`).
- `main.py`: app title and wiring.
- Harbor `task.toml`, `instruction.md`, sidecar Dockerfile and timeouts.
- `verify.py` stays generic (it reads `reward.reward`) and only needs renaming.
- Frontend scene: departments become ED zones (reception/triage, waiting, resus, acute, general, fast track, imaging, staff station, control room); avatars become patients and staff; the HUD becomes a dashboard.

**REPLACED** (old domain logic, new implementation):
- `sim/domain.py`, `scenario.py`, `store.py`, `policy.py`, `episode.py`, `evaluator.py` become the new `app/edsim/` engine and ED evaluator.
- `agents/reference.py` and `baselines.py` become the ED reference strategy and ED baselines.
- `scenarios/*.json` become difficulty configs in code, generated from a seed.
- Backend tests are rewritten for the ED domain.

**REMOVED** (no purpose in the new environment):
- Policy profiles (`v0.2` / `proposed`), amendments, `Truth`/leak logic, the release log, statistics small-cell rules, the Faker dependency (the engine uses stdlib RNG only), and `docs/unfindable/*` (archived on the Unfindable branch).
- Old frontend HUD pieces: `LeakAlerts`, `RequestInspector`, `RequestFolders`, `PersonGallery`.

## 3. Milestones

Each milestone leaves `main`-mergeable, tested code. The old environment keeps working until Milestone 2 replaces its wiring.

| Milestone | Phases | Delivers | Status |
|---|---|---|---|
| M1 | 2 + 4 | Architecture (`docs/ed/ARCHITECTURE.md`) and a standalone, deterministic simulation engine `backend/app/edsim/` with a Python action/observation API and unit tests. The old environment is untouched | **done** |
| M2 | 3 + 5 | MCP tool interface on the new engine, the ED evaluator (reward 0..1) and `/admin/finalize`. Old backend domain code removed. Needs approval of the scoring model in ARCHITECTURE §8 first | pending |
| M3 | 6 | Reference strategy plus 3 baselines over MCP, multi-seed results, reward calibration | pending |
| M4 | 7 | Harbor task `harbor/ed-sim/`, oracle/nop runs, an OpenCode + Kimi run | pending |
| M5 | 9 + 11 | Sweep of remaining old-domain code and docs, README, run logs | pending |
| M6 | 8 | 3D ED visualization on the real event stream | pending |
| — | 10 | Tests grow with every milestone; final full pass in M5 | ongoing |

## 4. Decisions that need approval before M2

| # | Decision | Options | Recommendation |
|---|---|---|---|
| D1 | Episode length versus LLM cost. A standard 72-hour run is about 200 patients and roughly 400–600 tool calls for an LLM agent | (a) Keep 72 hours at ~200 patients and raise Harbor's agent timeout to several hours; (b) keep 72 hours but lower arrivals to ~120 patients; (c) use 72 hours for scoring but allow a shorter `horizon_hours` for development runs | (a) for the benchmark plus (c) for development. Batch actions (`start_treatment`, list-valued `assign_staff` and `discharge_patient`) already keep calls per patient low |
| D2 | Scoring model (ARCHITECTURE §8): weighted geometric mean `O^0.35 · T^0.25 · F^0.20 · S^0.10 · B^0.10` | Accept as proposed; change weights; use an additive mean instead | Accept as a starting point, then recalibrate in M3 against baselines with any change justified |
| D3 | Granularity of control | (a) Micro: the agent places every patient (current design); (b) policy-level: the agent sets priorities and the engine dispatches | (a), because it matches the brief (assign staff, beds, equipment) and keeps the decisions inspectable |
| D4 | Where the evaluator runs | (a) Inside the sidecar behind `/admin/finalize` (current Harbor pattern); (b) a separate verifier container replaying an action log | (a), which reuses the working Harbor separate-verifier setup and keeps the agent unable to write the score |

## 5. Progress checklist

- [x] Phase 1: audit and inventory
- [x] Phase 2: architecture
- [ ] Phase 3: agent interaction (MCP): Python API done in M1, MCP in M2
- [x] Phase 4: engine and events
- [ ] Phase 5: evaluation and reward (raw ground-truth metrics recorded in M1; scoring proposal awaiting approval)
- [ ] Phase 6: reference and baselines
- [ ] Phase 7: Harbor
- [ ] Phase 8: frontend
- [ ] Phase 9: old-environment removal
- [ ] Phase 10: tests (engine tests done)
- [ ] Phase 11: docs
