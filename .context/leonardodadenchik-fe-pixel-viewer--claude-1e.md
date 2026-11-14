# Branch: leonardodadenchik/fe-pixel-viewer--claude-1e

- **Issue:** #97
- **Owner:** leonardodadenchik
- **Agent:** leonardodadenchik-claude-1e (HUD, agent E)
- **Parent branch:** leonardodadenchik/fe-pixel-viewer
- **Created:** Sat 19:59

## Goal
The pixel replay viewer's side panel: explain every action the AI took each tick, what the sim did, the department state, and give timeline controls (transport, speed, scrubber, keyboard).

## Files and folders I own
- `frontend/src/ui/**` (hud.ts, hud.css, describe.ts, timeline.ts, scrubber.ts, describe.test.ts)
- `frontend/src/style.css` (page frame; keeps the #app, #stage, #game, #hud ids)

## Don't touch
- `frontend/src/replay/types.ts` (lead), `src/game/*` (1d), `src/render/*` (1b/1c), `src/world/*`, `main.ts`, replays (1a)

## Contracts used or changed
- Uses `Replay`/`ReplayTick` from `src/replay/types.ts` and the ActionResult reason enum and event log shapes from `docs/CONTRACTS.md`. Changes nothing.
- `mountHud(root, replay, playback, opts): Hud { update(); destroy() }`. Uses only Playback's public `tick, phase, playing, speed, tickCount, current(), seek(), play/pause/toggle, stepForward/Back`.

## Status
- [x] Header: picker, label, policy, seed, big reward, O/T/W/B bars with points
- [x] Clock, transport, speed 1-16x, keyboard
- [x] Canvas scrubber with event bands, diversion, markers, queue sparkline, hover tooltip, click/drag
- [x] AI decisions (plain English, ✓/✗ with reasons), What happened, Department status
- [x] Mistakes list (deaths, faints, walk-outs) with click-to-jump
- [x] Tests for describe.ts / timeline.ts (vitest)

## Decisions and notes
- Sat 20:30: tick label shows the raw tick (`tick 47 / 143`) so it matches the tick numbers in warnings and the mistakes list.
- No-op assigns (staff sent to where they already are) fold into one "Kept N staff where they were" line; more than 4 real moves in a tick are grouped per destination with fatigue. Rejected actions are never grouped.
- Status shows `obs` (the state the policy saw at the start of the tick). "cover N" is the zone capacity computed from SPEC §3 (min of doctor and nurse coverage, tired staff 0.6).
- Event bands use event_start..event_end (a repaired CT ends early); diversion bands come from `obs.diversion.active` plus ticks with `diverted` events.
- `update()` only rebuilds DOM when tick/playing/speed change; the scrubber repaints its canvas only when the playhead pixel moves.
- Space is ignored while a select/input is focused or when a focused button would handle it; mouse clicks blur the buttons.
- No new dependencies.

## Handoff
- Done: everything in Status. `cd frontend && pnpm lint && pnpm build && pnpm test` passes (23 tests).
- How to test: preview `viewer-1e` (http://localhost:5175). The reference replay has no deaths/rejections; to see those, mount a mutated replay from the console (import `/src/ui/hud.ts`, `/src/game/playback.ts`, `/src/world/layout.ts`).
- Not done: agency arrivals and staff returning from sickness are not called out in "What happened" (no event for them; would need an obs diff).
