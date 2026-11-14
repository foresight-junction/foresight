# Branch: leonardodadenchik/fe-pixel-viewer--claude-1b

- **Issue:** #97
- **Owner:** leonardodadenchik
- **Agent:** leonardodadenchik-claude-1b (helper of leonardodadenchik-claude-1)
- **Parent branch:** leonardodadenchik/fe-pixel-viewer
- **Created:** Sat 19:59

## Goal
Map (department floor plan) and renderer for the ED-72 pixel replay viewer: a readable, juicy top-down
3/4 hospital with walking routes, lighting, particles and live overlays.

## Files and folders I own
- `frontend/src/world/**` (layout.ts, path.ts, path.test.ts)
- `frontend/src/render/renderer.ts`, `camera.ts`, `particles.ts`

## Don't touch
- `src/render/sprites.ts` (1c), `src/game/**` (1d), `src/ui/**` (1e), `src/replay/**` and `main.ts` (lead)

## Contracts used or changed
- `Layout` interface and `buildLayout()` unchanged; MAP_COLS/MAP_ROWS now 48 x 28.
- New exports from layout.ts: `ROOMS`, `BUILDING`, `AMBULANCE_BAY`, `STREET_ROW`, `FURNITURE`, `LIGHTS`,
  `ZONE_LABEL`, `BEDS_PER_DOCTOR/NURSE`, `buildTiles()`, slot lists.
- New `src/world/path.ts`: `route(from, to): Point[]`, plus `findTilePath`, `tileOf`, `isWalkable`.
- `Renderer` keeps `constructor(canvas, layout)`, `resize()`, `render(frame, timeMs)`; adds `pick(x, y)` and
  a public `selected` id.

## Status
- [x] Floor plan, slots, furniture data
- [x] route() + vitest (connectivity, walls, distinct slots)
- [x] Renderer: static layer, 3/4 walls, props, overlays
- [x] Lighting, shadows, particles, shake/flash

## Decisions and notes
- Sat: Entity points are the top-left of a 16x16 cell; route() returns corner waypoints (tile top-left) then
  `to` exactly, never `from`. Furniture costs 25 per step so walkers go around beds/seats unless it is the goal.
- Sat: offstage is just past the right edge of the street: staff leave via the exit door and walk off-map.
- Sat: zone coverage pips: filled green = covered patient, filled red (blinking) = uncovered patient,
  green outline = staff could cover one more bed (min of doctor/nurse cover from SPEC §3), grey = no cover.
  Number after the pips is `frame.zoneCoverage`.
- Sat: walls use a private `wallFace()` placeholder (comment `swap to sprites.drawWallFace at merge`); the
  dark cap is `drawTile("wall")` clipped and darkened.
- Sat: outdoor ground (asphalt, sidewalk, grass, road), furniture, ambulance, EMERGENCY sign and the 3x5
  pixel font are drawn in renderer.ts, not sprites.ts.
- Juice triggers: new effects (keyed by kind/text/tile) spawn particles; death (effect or patient state
  "dead") shakes; bus_crash (activeEvents or event_start text containing "bus") shakes + flashes. A tick jump
  (seek) re-baselines without firing.

## Handoff
- Done: all of the above, lint/build/test green.
- How to test: `cd frontend && pnpm lint && pnpm build && pnpm test`; preview `viewer-1b` on :5172.
- Not done: zoom-punch (optional), dust puffs depend on playback setting `moving`.
