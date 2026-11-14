# Branch: leonardodadenchik/fe-pixel-viewer--claude-1d

- **Issue:** #97
- **Owner:** leonardodadenchik
- **Agent:** leonardodadenchik-claude-1d (helper of leonardodadenchik-claude-1)
- **Parent branch:** leonardodadenchik/fe-pixel-viewer
- **Created:** Sat 19:59

## Goal
Playback and animation for the pixel replay viewer: turn a Replay into smooth Frames (walks, admissions,
discharges, deaths, faints, agency staff, effects) with instant seeking. Done when `pnpm lint && pnpm build && pnpm test` pass.

## Files and folders I own
- `frontend/src/game/**` (playback.ts, model.ts, motion.ts, paths.ts, fixture.ts, node-fs.d.ts, *.test.ts)

## Don't touch
- `src/replay/*` (lead), `src/world/**` (1b), `src/render/**` (1b/1c), `src/ui/**` (1e), `main.ts`

## Contracts used or changed
- Reads `Replay`/`ReplayTick` (`src/replay/types.ts`), produces `Frame` (`src/replay/frame.ts`). Neither changed.
- Playback public API unchanged. Added: `timelineMarkers(): TickMarkers[]`, `entityInfo(id): EntityInfo | null`.

## Status
- [x] Per-tick model with stable places (seats, beds, zone spots, rest spots, infirmary)
- [x] Walks, wind-up, overshoot, bob, death hold, faint spin, carry offstage, agency in/out, diverted turn-away
- [x] Effects, activeEvents, ct, diversion, zoneCoverage
- [x] Tests: fixture + reference replay invariants, motion unit tests, perf

## Decisions and notes
- Phase 0 of tick t is exactly obs(t) (what the AI saw); phase 1 is obs(t+1). So tick t+1's arrivals,
  diverted patients, event start/end and staff step-1 changes (agency arrive/leave, sick, back from faint)
  play in the second half of tick t. A seek always lands on what the HUD shows.
- Phase windows (model.ts `PHASE`): actions 0.04-0.35, treatment bars 0.15-0.45, outcomes 0.38+, death
  at 0.5 after a still hold and fades 0.62-0.95, faint spin 0.4-0.5, next-tick start 0.4, all walks end
  by 0.72. Effects live 1.2-2.5 ticks so they linger into the next tick.
- A staff member who faints stays lying where they fell until the next tick, then is carried offstage
  in its first 30%.
- Speed >= 8 drops the crowd stagger (`Leg.lag`); the plans are the same.
- Bus arrivals rush in tight and fast; flu arrivals spread out. Frame has no `source` field, so the
  renderer can't draw an ambulance; if wanted, the lead could add one to PatientEntity.
- `play()` at the very end restarts from tick 0.
- Paths: `paths.ts` has `const ROUTER: Router = lPath;` (MOCK L-shape). Switch to agent 1b's
  pathfinder with `import { route } from "../world/path";` + `const ROUTER: Router = route;`.
  Results are cached by endpoints and resolved lazily per leg, so loading never runs the router.
- No @types/node in the viewer: `node-fs.d.ts` declares the two `node:fs` calls the tests use.
- Extra test replay: `EXTRA_REPLAY=path/to/replay.json pnpm test` runs the invariants on any replay
  (I used a scratch "chaos" policy replay with 108 deaths, 19 faints, 22 diverted, 267 rejections).

## Handoff
- Done: everything above; `pnpm lint && pnpm build && pnpm test` green (26 tests).
- Not done: the `route()` switch (waits for 1b's `src/world/path.ts` at merge).
- Test: `cd frontend && pnpm test`; watch it with preview config `viewer-1d` (http://localhost:5174).
