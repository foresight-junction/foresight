# Unfindable — Observation event schema v1

Status: contract for the vertical slice. The backend (`backend/app/observe/`) emits these events; the frontend (`frontend/src/`) consumes them. A change to this file is a contract change.

## 1. Purpose and boundary

The observation stream is a **one-way, spectator-only** view of an episode. It exists for the live 3D demonstration and for trajectory analysis.

- It is **never** reachable through MCP and is never part of the agent's observation space.
- It has **no write path**. Nothing a spectator does can change state, truth or reward.
- It **never carries raw sensitive values**. Masking happens on the server, so the browser cannot leak what it never receives.
- It contains information the agent must not see while the episode runs: hidden state changes and, in live-reveal mode, correctness and leaks. That is why it sits behind a spectator token, and why it is disabled in Harbor runs (`UF_OBSERVE=0`).

## 2. Transport

| Endpoint | Purpose |
|---|---|
| `GET /observe/stream?token=<UF_SPECTATOR_TOKEN>` | Server-Sent Events. Each message is `event: observation` and `data: <one JSON event>`. A `: ping` comment is sent every 15 s |
| `GET /observe/history?token=<UF_SPECTATOR_TOKEN>&after_seq=<n>` | JSON array of all events with `seq > n`, for catch-up after a reconnect, or for replay |

- Token in the query string, because the browser `EventSource` API cannot set headers. This is acceptable only for a local demo; the token is a spectator secret, not the verifier token.
- A wrong or missing token returns `401` with no body detail.
- On connect, the client should call `history` with its last `seq` (0 initially), then attach to `stream` and drop duplicates by `seq`.

## 3. Envelope

```json
{
  "v": 1,
  "seq": 42,
  "ts": "2026-11-13T21:05:00.123Z",
  "episode_id": "ep-slice-0001",
  "type": "PROTECTION_CHECK",
  "visibility": "spectator",
  "request_id": "R-003",
  "response_index": 2,
  "department": "protection",
  "tool": "check_protection",
  "call_id": "c-0017",
  "display": { }
}
```

| Field | Type | Meaning |
|---|---|---|
| `v` | int | Schema version, always 1 |
| `seq` | int | Strictly increasing per episode, starting at 1 |
| `ts` | string | ISO 8601 UTC with milliseconds. For display only; never used in logic |
| `episode_id` | string | Episode identifier |
| `type` | EventType | See §4 |
| `visibility` | `"agent_observable"` \| `"spectator"` \| `"evaluator_reveal"` | Who could legitimately know this. `agent_observable`: the agent saw the same information in a tool result. `spectator`: hidden state, e.g. an event fired. `evaluator_reveal`: grading output |
| `request_id` | string \| null | The current request, if any |
| `response_index` | int | Accepted responses so far at emission time |
| `department` | Department \| null | Where the 3D avatar should be |
| `tool` | string \| null | MCP tool name, if the event comes from a tool call |
| `call_id` | string \| null | Links STARTED, semantic and COMPLETED events of one tool call |
| `display` | object | Type-specific safe metadata (§5) |

`Department` is one of: `reception`, `identity`, `registry`, `protection`, `authority`, `statistics`, `decision`.

**Implementation note:** `seq` increases for the lifetime of the server process, not per episode, so clients can de-duplicate across `/admin/reset`. A new `EPISODE_STARTED` with a different `episode_id` means the client should reset its episode state. `/observe/history` returns only the current episode's events.

## 4. Event types

| Type | Visibility | Department | Emitted when |
|---|---|---|---|
| `EPISODE_STARTED` | spectator | reception | Episode created |
| `REQUEST_RECEIVED` | agent_observable | reception | `next_request` returns a request for the first time |
| `TOOL_CALL_STARTED` | agent_observable | mapped from the tool (§6) | Any MCP tool call begins |
| `TOOL_CALL_COMPLETED` | agent_observable | mapped from the tool | Any MCP tool call ends, successfully or with an error code |
| `IDENTITY_VERIFICATION` | agent_observable | identity | `verify_identity` or `get_requester` completed |
| `PERSON_RECORD_ACCESSED` | agent_observable | registry | `find_person` or `get_person` completed |
| `RESIDENT_SEARCH` | agent_observable | registry | `search_residents` completed |
| `HOUSEHOLD_CHECK` | agent_observable | protection | `get_household` completed |
| `PROTECTION_CHECK` | agent_observable | protection | `check_protection` completed |
| `AUTHORITY_CHECK` | agent_observable | authority | `verify_authority` completed |
| `STATISTICS_QUERY` | agent_observable | statistics | `count_residents` completed |
| `RELEASE_LOG_VIEWED` | agent_observable | statistics | `get_release_log` completed |
| `POLICY_VIEWED` | agent_observable | reception | `get_policy` completed |
| `DECISION_SUBMITTED` | agent_observable | decision | `respond` accepted |
| `STATE_CHANGED` | spectator | protection or authority | A scheduled event was applied after a response |
| `REWARD_UPDATED` | evaluator_reveal | decision | After each accepted response, when live reveal is on (`UF_LIVE_REVEAL=1`) |
| `PRIVACY_LEAK_DETECTED` | evaluator_reveal | decision | A response disclosed something unentitled, when live reveal is on |
| `EPISODE_FINISHED` | evaluator_reveal | decision | Finalize ran; carries the final score |

**Ordering guarantees (per tool call):**
1. `TOOL_CALL_STARTED`
2. Zero or one semantic event (`PROTECTION_CHECK`, …)
3. For `respond` only: `DECISION_SUBMITTED`, then any `STATE_CHANGED` events triggered by this response
4. `TOOL_CALL_COMPLETED`
5. For `respond` with live reveal: `REWARD_UPDATED`, then `PRIVACY_LEAK_DETECTED` if any

## 5. Display payloads

**Masking rules (enforced on the server):**
- A person is always a `PersonRef`: `{"id": "P-0007", "initials": "A.V."}`. Never a full name, date of birth, address, phone, email, employer or school.
- Field lists contain field **names** only, never values.
- Requesters appear as `{"id": "Q-0002", "type": "private_person"}`, with no claimed name.

| Type | `display` fields |
|---|---|
| `EPISODE_STARTED` | `scenario`, `total_requests`, `profile` |
| `REQUEST_RECEIVED` | `kind`, `requester: {id, type}`, `subject_initials` (or null), `requested_fields: [names]`, `position` (1-based), `total` |
| `TOOL_CALL_STARTED` | `args_summary` (IDs and field names only) |
| `TOOL_CALL_COMPLETED` | `ok`, `error_code` (or null), `duration_ms` |
| `IDENTITY_VERIFICATION` | `requester: {id, type}`, `status` (`VERIFIED` \| `FAILED` \| `LOOKED_UP`) |
| `PERSON_RECORD_ACCESSED` | `person`: PersonRef or null, `found`: bool |
| `RESIDENT_SEARCH` | `postcode`, `count` |
| `HOUSEHOLD_CHECK` | `person`: PersonRef, `household_id`, `members`: [PersonRef] |
| `PROTECTION_CHECK` | `person`: PersonRef, `sno`: `ACTIVE` \| `NONE` |
| `AUTHORITY_CHECK` | `case_id`, `status`, `reason` (or null) |
| `STATISTICS_QUERY` | `filter` (canonical), `count` |
| `RELEASE_LOG_VIEWED` | `entries` (count) |
| `POLICY_VIEWED` | `version` |
| `DECISION_SUBMITTED` | `action`, `fields: [names]`, `person_count`, `response_index` |
| `STATE_CHANGED` | `change`: `sno_activated` \| `case_closed` \| `officer_reassigned`, `person` (PersonRef or null), `case_id` (or null) |
| `REWARD_UPDATED` | `score`, `service`, `completion`, `critical_leaks`, `minor_leaks`, `last: {request_id, correct, leak: none \| minor \| critical}` |
| `PRIVACY_LEAK_DETECTED` | `severity`: `minor` \| `critical`, `persons: [PersonRef]`, `fields: [names]` |
| `EPISODE_FINISHED` | `score`, `service`, `completion`, `critical_leaks`, `minor_leaks`, `answered`, `total`, `requests: [{request_id, kind, agent_action, correct, leak}]` |

## 6. Tool → department mapping

| Department | Tools |
|---|---|
| reception | `next_request`, `get_policy` |
| identity | `get_requester`, `verify_identity` |
| registry | `find_person`, `get_person`, `search_residents` |
| protection | `get_household`, `check_protection` |
| authority | `verify_authority` |
| statistics | `count_residents`, `get_release_log` |
| decision | `respond` |

## 7. Invariants (tested)

- `seq` is gap-free and strictly increasing within an episode.
- Every `TOOL_CALL_STARTED` has exactly one `TOOL_CALL_COMPLETED` with the same `call_id`.
- No event contains a key or value from the forbidden list: raw names, dates of birth, street addresses, phones, emails, employers, schools, `identity_ok`, `truth`, `trigger`, `label`, `seed`.
- `evaluator_reveal` events appear only when live reveal is enabled, or at finalize.
- Turning the stream off changes nothing in state, truth or reward. Tested by comparing reports with `UF_OBSERVE=0` and `1`.
