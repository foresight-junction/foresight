# Unfindable — Visualization design

Status: design for the vertical slice. The 3D world is a **visual representation** of the real environment, driven only by the observation stream (`EVENT_SCHEMA.md`). It is not a navigation task: the agent never sees it and never acts through it.

## 1. Goals and non-goals

**Goals:**
- Judges can watch a real agent work a shift: requests arrive, the agent visits departments, checks protection, decides.
- Every animation is caused by a real backend event. There are no scripted moves.
- Polished, modern look, at 60 fps on a normal laptop.
- Clear visual difference between correct decisions, incorrect decisions and privacy leaks.

**Non-goals:**
- No input from the 3D scene back into the environment.
- No display of model reasoning. Only observable actions are shown.
- No raw sensitive values, ever. The server masks them before they leave.

## 2. Stack

| Choice | Why | Alternative considered |
|---|---|---|
| React + TypeScript + Vite | The team knows React; matches the repo template (`frontend/`, pnpm) | — |
| React Three Fiber (`@react-three/fiber`) | Three.js through React components; scene state follows React state naturally | Plain Three.js: more imperative code, harder to keep in sync with the event state |
| `@react-three/drei` | Ready helpers: camera controls, text, rounded boxes, environment lighting, HTML overlays | Writing these by hand |
| `zustand` | Small store that both the scene and the HUD read; the reducer applies events | React context: re-renders the whole canvas on every event |
| Native `EventSource` | Matches the SSE contract; no dependency | WebSocket: unnecessary for one-way data |

Babylon.js and PlayCanvas were considered and rejected: no benefit over R3F for this scale, and the team knows React.

## 3. Scene layout

A stylized, low-poly register office seen from an isometric-like orbit camera. Seven departments sit around a central hall; the Decision Room is at the far end, facing Reception.

```
            [ Statistics ]      [ Authority Desk ]
   [ Registry ]        ( central hall )        [ Protection Office ]
            [ Identity ]        [ Decision Room ]
                       [ Reception ]
```

Each department is a platform with:
- a floor tile in its own accent color and a floating label;
- a small prop that animates when its tools are used (document stack, scanner arch, shield, archive cabinets);
- a glow ring that pulses on `TOOL_CALL_STARTED` and settles on `TOOL_CALL_COMPLETED` (red flash if `ok = false`).

## 4. Actors and objects

| Object | Driven by | Behaviour |
|---|---|---|
| Agent avatar (rounded robot with a visor) | `department` of the latest tool event | Walks along a path to the target department with easing; idles with a slight bob |
| Request card (folder) | `REQUEST_RECEIVED` | Spawns at Reception, attaches to the avatar, travels with it, and is filed at the Decision Room on `DECISION_SUBMITTED` |
| Queue stack | `position` / `total` | Stack of pending folders at Reception that shrinks as requests are pulled |
| SNO shield | `PROTECTION_CHECK` with `sno = ACTIVE`; `STATE_CHANGED` `sno_activated` | Glowing shield over the person token at the Protection Office |
| Household | `HOUSEHOLD_CHECK` | Person tokens linked by light beams; a shielded household shares one dome |
| Decision stamp | `DECISION_SUBMITTED` | RELEASE / DENY / FORWARD stamp in neutral grey |
| Verdict | `REWARD_UPDATED.last` (live reveal only) | Stamp turns green (correct) or amber (incorrect) |
| Leak alarm | `PRIVACY_LEAK_DETECTED` | Red pulse and siren ring at the Decision Room; critical leaks also tint the scene red for 2 s |
| State change ripple | `STATE_CHANGED` | Ripple across the hall plus a timeline entry: "SNO issued (hidden from agent)" |

Without live reveal, decisions stay neutral until `EPISODE_FINISHED`, which colors them all at once in the shift summary.

## 5. HUD (React DOM overlay, not inside the canvas)

| Panel | Position | Content |
|---|---|---|
| Connection + episode bar | Top | Episode ID, scenario, connection state, progress `n / total` |
| Live event timeline | Right | Newest first; icon per type; spectator-only events marked "hidden from agent"; evaluator events marked "evaluator" |
| Request inspector | Left | Current request: kind, requester type, subject initials, requested field names, tool calls so far, decision |
| Score panel | Bottom-left | Score, service, completion, critical and minor leaks (live reveal only; otherwise "revealed at finalize") |
| Shift summary | Modal on `EPISODE_FINISHED` | Table of requests with decision, verdict and leak; final score |

## 6. Privacy in the demo

- The server sends initials and IDs only. Field values never reach the browser.
- A leak is shown as "critical leak: street_address of A.V. disclosed to private_person". The value itself is never shown.
- Labels make the visibility class explicit, so the audience can tell what the agent knew from what only the evaluator knows.

## 7. Modes

| Mode | Source | Use |
|---|---|---|
| Live | `/observe/stream` against a running backend | Demo with a real agent or the reference agent |
| Replay | A JSON array exported from `/observe/history` of a real run | Offline demo; tests. It is a recording of real events, not a script |

The frontend reads the backend URL and spectator token from `VITE_BACKEND_URL` and `VITE_SPECTATOR_TOKEN`.

## 8. Performance budget

- Primitives and instancing only; no heavy glTF models in the slice.
- One directional light with shadows, plus an environment preset.
- Event handling in the zustand reducer; scene components subscribe to narrow slices.
- Animation speed independent of event rate: the avatar queues targets and never teleports, except when more than 5 moves are pending (catch-up).
