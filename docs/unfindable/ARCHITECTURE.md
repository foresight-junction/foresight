# Unfindable — Architecture

Status: the vertical slice is implemented (2026-11-13). §0 describes what exists now. §1–§10 are the original audit proposal, kept for traceability. Source of truth: `SPEC.md` v0.2. Unapproved deviations are listed in `SPEC_CHANGE_PROPOSALS.md`.

## 0. Implemented architecture (vertical slice)

Five layers, each with one job and a one-way dependency on the layers below it:

```
 ┌──────────────── Frontend (frontend/, React + R3F) ─────────────────┐
 │ 3D office, avatar, timeline, inspector, score, summary              │
 │ reads ONLY /observe/* with a spectator token; no write path         │
 └───────────────▲───────────────────────────────────────────────────┘
                 │ SSE (one-way)
 ┌───────────────┴──────── Observability (app/sim/observe.py, app/routers/observe.py) ┐
 │ typed events (EVENT_SCHEMA.md), server-side masking, history + stream             │
 └───────────────▲───────────────────────────────────────────────────────────────────┘
                 │ emit only
 ┌───────────────┴──────── Agent interface (app/mcp_server.py) ─────────┐   agents/ (reference,
 │ 13 MCP tools over Streamable HTTP at /mcp, input validation,         │◀── baselines, CLI): MCP
 │ fixed error catalog, no correctness feedback                         │    client only
 └───────────────▲──────────────────────────────────────────────────────┘
                 │ calls
 ┌───────────────┴──────── Core simulation (app/sim/) ─────────────────────────────────┐
 │ scenario.py  deterministic world (seed, Faker fi_FI, linter)                         │
 │ store.py     SQLite state: persons, SNO, requesters, cases, responses, release log   │
 │ episode.py   one request in flight, atomic respond, events after the Nth response   │
 │ policy.py    pure oracle: shielded, truth per kind, R6, lawful recipient, profiles  │
 └───────────────▲──────────────────────────────────────────────────────────────────────┘
                 │ reads ledger
 ┌───────────────┴──────── Evaluation (app/sim/evaluator.py, app/routers/admin.py) ─────┐
 │ correctness, critical/minor leak detection, score (spec v0.2 §6), failure tags,      │
 │ POST /admin/finalize (verifier token) → reward + report; freezes the episode        │
 └──────────────────────────────────────────────────────────────────────────────────────┘
```

**Boundaries:**
- **Agent ↔ environment:** MCP only. The `agents/` package never imports `app` (checked by a test).
- **Simulation → observability:** one-way `emit`. Turning observation off leaves reward unchanged (tested).
- **Observability → frontend:** read-only, token-protected, masked on the server (initials and IDs only). Tested: no raw name, date of birth, address, phone, email, employer or school appears in the stream, even during a leak.
- **Evaluator → outside:** only through `/admin/finalize`, gated by the verifier token. The ledger table never reaches a tool or event (hidden-key scan test).
- **Spectator stream vs agent:** the stream carries hidden state changes and, in live-reveal mode, correctness. It must never be reachable by the agent. In Harbor runs, set `UF_OBSERVE=0` and `UF_LIVE_REVEAL=0`.

**Hosting:** FastAPI app (`app/main.py`, matching the repo template) with the FastMCP app mounted at `/`, serving `/mcp`. Extra routes: `/health`, `/observe/*`, `/admin/*`. One process, one episode at a time; `/admin/reset` starts a new one.

**Unapproved proposals** are switches in `SpecProfile` (`v0.2` default, `proposed` with all of them on). Approving one means changing a default, not rewriting code.

**Harbor evaluation path (from Spike S0, see `SPIKE_S0_RESULTS.md`):**
- The verifier runs in `separate` mode.
- The reward is produced inside the `unfindable` sidecar by a `[[verifier.collect]]` hook after `main` stops, and handed to the verifier as a sidecar artifact.
- The verifier no longer calls `/admin/finalize` over the network as §3 originally proposed: in shared mode that path was forged in a real run.

**Differences from the §1–§10 proposal:**
- `/health` instead of `/healthz`, to match the existing `docs/CONTRACTS.md`.
- Observation `seq` increases across episodes (one bus per process), so clients can de-duplicate across resets.
- The scenario format is JSON instead of YAML, to avoid adding a dependency.

## 1. What we are building

The research question:

> Can an LLM agent that has full read access to sensitive records make correct disclosure decisions over a long shift in which permissions change, without over-refusing?

The product is an MCP environment (tools plus a hidden state machine), a policy oracle that computes ground truth, an evaluator that scores disclosures, a deterministic reference agent, baselines, and Harbor packaging.

## 2. Threat-model decision (audit item A)

Two evaluation objectives are possible:

| | Option A — decision benchmark: the agent can read sensitive records | Option B — technical prevention: the agent cannot read protected values |
|---|---|---|
| What is measured | The agent's disclosure decisions | The system's access control. The agent becomes irrelevant to protection, because every agent scores perfectly on it |
| Realism | Matches a real clerk with register access | A clerk who cannot see addresses cannot serve banks, police or the data subject |
| AfterQuery rubric | "The information and tools needed to do better are available" — satisfied | The gap would come from withheld information, which scores 0 on meaningful difficulty |
| Disclosure channel | Only `respond` | Only `respond` |

**Recommendation: Option A (confidence 90%).** It is the only option that measures the agent.

Consequences:
- Reading is not disclosure. A disclosure is exactly the structured payload of an accepted `respond`.
- `respond` has no free-text field. Every disclosure is therefore a set of (person, field) pairs or a statistics release, and can be checked by a machine.
- An optional, unscored "over-access" metric (the agent read fields it never needed) can be added later (N9). It is not part of the MVP.

### 2.1 Access matrix

| Actor | Can read | Can write | Never sees |
|---|---|---|---|
| Evaluated agent (main container, MCP only) | Policy, pulled requests, current person records, households, SNO status, authority checks, counts, its own release log | `respond`, once per request | `identity_ok` flags, scenario labels (trap, abuser, persuasion), future requests and requesters, event schedule, truth snapshots, population snapshots, seed, verifier token |
| Simulated requester | Only what `respond` disclosed | — | Everything else |
| Server runtime (sidecar) | Everything | State, events, release log, truth ledger | — |
| Evaluator (sidecar, after the episode, token-gated) | Everything, including the truth ledger and snapshots | Report, reward | — |
| Verifier script (`tests/`, uploaded after the run) | `/admin/finalize` response | `/logs/verifier/reward.json` | — |

## 3. Topology

```
Harbor task
┌─────────────────────────── main container ───────────────────────────┐
│  OpenCode agent (shell, filesystem)        tests/test.sh (after run) │
└───────────────┬───────────────────────────────────────┬──────────────┘
                │ MCP streamable-http                    │ POST /admin/finalize
                │ http://unfindable:8000/mcp             │ header X-Verifier-Token
┌───────────────▼───────────────────────────────────────▼──────────────┐
│ sidecar "unfindable" (own image, own filesystem, own environment)    │
│                                                                      │
│   FastMCP tools ──▶ EpisodeService ──▶ StateStore (SQLite)            │
│                         │                   ▲                        │
│                         ▼                   │                        │
│                    PolicyOracle        EventScheduler                │
│                         │                                            │
│                    TruthLedger ──▶ Evaluator ──▶ report + reward     │
│                                                                      │
│   JSONL trajectory log (sidecar volume only)                         │
└──────────────────────────────────────────────────────────────────────┘
```

Evidence from the Harbor docs (docs.harborframework.com):
- MCP servers are declared in `task.toml` as `[[environment.mcp_servers]]` with `transport = "streamable-http"` and a `url`.
- MCP servers "can be implemented as services in the docker-compose.yaml file". The `main` service is reserved for the agent; sidecars are reached by service name.
- The verifier runs `tests/test.sh`, which is uploaded after the agent finishes, and must write `/logs/verifier/reward.txt` or `reward.json`.

Not yet confirmed: whether AfterQuery's harness setup allows compose sidecars, whether OpenCode supports streamable-http MCP, and whether sidecar state survives into the verifier step. These are question B4 and Spike S0.

## 4. Components and responsibilities

| Component | Responsibility | Depends on | Must not |
|---|---|---|---|
| `domain` | Pydantic models, enums, ID formats, field registry (releasable fields, LRF set) | — | Do I/O |
| `scenario` | Load scenario file, seeded generator (Faker `fi_FI`, pinned), linter for invariants | `domain` | Be importable by the agents package |
| `state` | SQLite schema, repositories, `EpisodeState` (cursor, response count), population snapshots | `domain` | Contain policy logic |
| `events` | Event-type registry; scheduler applies events after the Nth accepted response, inside that response's transaction | `state` | Use wall-clock time |
| `policy` (oracle) | Pure functions: `shielded`, `truth`, `entitlement`, `lawful_recipient`, `canonical_filter`, `nested`, `r6_check` | `domain`, read-only `state` | Read request free text; do I/O |
| `mcp_server` | FastMCP app, thin tool handlers, structural validation, error catalog, visibility scope, global lock, JSONL logging | all of the above | Return hidden fields; reveal correctness |
| `evaluator` | Correctness from the truth ledger, leak detection from disclosures, scoring, failure tagging F1–F9, report | `policy`, `state` | Run before finalize |
| `admin` | `/admin/finalize` (token, freeze, evaluate), `/healthz` | `evaluator` | Be exposed as an MCP tool |
| `agents` (separate package) | MCP client wrapper, reference agent, baselines, CLI | MCP client only | Import `core` or `server` |
| `harbor` | `task.toml`, compose file, Dockerfiles, `tests/test.sh` | — | Put secrets in the main image or environment |

## 5. Package layout

```
unfindable/
  pyproject.toml                    workspace, pinned lockfile
  packages/
    unfindable-core/                domain, scenario, state, events, policy, evaluator
    unfindable-server/              mcp_server, admin            (depends on core)
    unfindable-agents/              client, reference, baselines (MCP client only)
  scenarios/
    pilot.yaml                      11 requests
    shift-42.yaml                   44 requests
  harbor/
    task.toml
    environment/Dockerfile          main image: no core or server code
    environment/docker-compose.yaml sidecar "unfindable"
    environment/unfindable/Dockerfile
    tests/test.sh
  tests/
    unit/  contract/  integration/  isolation/  adversarial/
```

## 6. Request lifecycle

1. `next_request` — if the current request is unanswered, return it again. Otherwise advance the cursor, mark the next request as pulled, and return it. When the queue is empty, return `{"done": true}`.
2. Read tools — run under the global lock against the current state, after the visibility check.
3. `respond` — under the global lock, inside one SQLite `BEGIN IMMEDIATE … COMMIT`:
   1. Structural validation (see `MCP_CONTRACTS.md`). On failure: error, no state change, does not count as a response.
   2. `truth = oracle.truth(request, state_now, history_before)` is stored in the hidden truth ledger.
   3. `disclosures = handler.disclosures(response, state_now)` gives (person_id, field) pairs, or, for statistics, a hidden population snapshot.
   4. Persist the response, the disclosures, and a release-log entry if the action is RELEASE.
   5. `response_count += 1`.
   6. Apply every event with `trigger == response_count`, ordered by `event_id`.
   7. Commit and return `{"recorded": true, "response_index": n}`.
4. `/admin/finalize` — check the token, freeze the episode (every tool now returns `EPISODE_FINISHED`), evaluate, return the report.

**Invariant:** response n is judged on the state before the events with trigger n. Those events affect response n+1 and every later tool call.

## 7. Determinism

- Scenario = file + seed. The generator uses its own `random.Random(seed)` and a seeded Faker instance, with a pinned Faker version. Iteration is always sorted, and IDs come from generation order (`P-0001`).
- Each scenario has a fixed `as_of_date`, used for age bands and `moved_in_last_12m`. The wall clock is never used in logic.
- Events are keyed to the response count, not time.
- One request in flight at a time (PC-3): every agent sees the same state at the same request index.
- Golden hashes are tested: world hash, queue hash, reference trajectory hash, reference report.

## 8. Extensibility points

| To add | Where | Contract |
|---|---|---|
| A new request kind | `RequestKindHandler` registered by name | `schema`, `validate_response`, `truth`, `disclosures`, `entitlement`. The scorer picks up new kinds automatically |
| A new protection rule | `ShieldingRule` predicate list | `applies(person, state) -> bool`, e.g. a future "shared street address" rule |
| A new event type | `EventType` registry | `name`, params schema, `apply(state)` |
| A new scenario | YAML in `scenarios/` | Must pass the linter and give reference = 1.0 |
| A more sophisticated privacy attack | `policy` statistics module plus a new kind or dimension | New rule ID, oracle function, tests |
| New agents or models | `agents` package or a Harbor agent | Server unchanged |
| A new metric | `Metric(name, fn(EpisodeRecord))` | Appears in the report and `reward.json` |

## 9. Stack evaluation

| Choice | Verdict | Reason | Caveat |
|---|---|---|---|
| Python 3.12+ | Keep | Harbor and FastMCP are Python | — |
| FastMCP | Keep | Supports streamable HTTP (`transport="http"`, alias `"streamable-http"`), which matches Harbor's `streamable-http` | Pin the version; the API changed across major versions |
| SQLite | Keep | One process, transactions, easy counts; the team knows SQL | Lives only in the sidecar, never on a shared volume |
| Pydantic v2 | Keep | Validation plus JSON Schema for tool definitions | — |
| Faker `fi_FI` | Keep | Realistic Finnish names and addresses | Output can change between Faker versions: pin it and test a golden world hash |
| pytest | Keep | — | No extra test frameworks needed |
| Docker | Keep | Required for the Harbor compose sidecar | — |
| JSONL trajectory log | Keep | Append-only, easy to diff and annotate | Sidecar volume only |

No additional infrastructure is proposed. No Redis, Postgres, message queue or web UI. A lockfile tool (uv or pip-tools) is justified only for reproducibility.

## 10. Architectural decisions

| ID | Decision | Confidence | Evidence | What would force a change |
|---|---|---|---|---|
| AD-1 | Option A threat model | Decided (B1, 2026-11-13) | Rubric wording; realism | — |
| AD-2 | MCP server as a compose sidecar over streamable HTTP | 75% | Harbor docs on `mcp_servers` and compose sidecars | AfterQuery's harness forbids compose, or OpenCode lacks streamable-http. Fallback: stdio server in the main container, with weak isolation (T1–T3 become residual risks) |
| AD-3 | Python, FastMCP, SQLite, Pydantic | 90% | Mature, known libraries | — |
| AD-4 | One process, global lock, SQLite transactions | 90% | Simple and deterministic; one sidecar per episode | Running parallel episodes in one server (not needed) |
| AD-5 | One request in flight | Decided (B2, 2026-11-13) | Determinism; removes look-ahead ambiguity | — |
| AD-6 | Oracle as pure functions; truth snapshot at response time | 90% | Testable and reproducible | — |
| AD-7 | Reference agent independent of the oracle, MCP only | 90% | Two independent implementations cross-check each other; the rubric needs a reference run through the harness | B4: how the harness runs a team's reference agent |
| AD-8 | Verifier calls finalize with a token, which freezes the episode and returns `reward.json` | 65% | Harbor verifier docs | Verifier mode, sidecar state persistence, tamper risk T14, AfterQuery's scoring skeleton |
| AD-9 | Scenario = authored story beats + seeded filler | 80% | Needed for the storyline and traps | — |
| AD-10 | Scoring as in the spec, plus skipping empty kinds and a completion factor | Decided (B3, 2026-11-13) | Baseline math in `EVALUATION_DESIGN.md` §7 | — |
