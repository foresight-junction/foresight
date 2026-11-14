# Branch: leonardodadenchik/fe-pixel-viewer--claude-1c

- **Issue:** #97
- **Owner:** leonardodadenchik
- **Agent:** leonardodadenchik-claude-1c (sprites helper for lead leonardodadenchik-claude-1)
- **Parent branch:** leonardodadenchik/fe-pixel-viewer
- **Created:** Sat 19:59

## Goal
All pixel art for the ED-72 replay viewer, drawn in code: tiles, beds, CT, patients, staff, effects,
a bitmap font, and a `/gallery.html` review page showing every state animated.

## Files and folders I own
- `frontend/src/render/sprites.ts` (contract functions), `frontend/src/render/palette.ts`
- `frontend/src/render/art/**` (pixmap, font, tiles, furniture, people, icons, effects)
- `frontend/src/render/sprites.test.ts`, `frontend/gallery.html`, `frontend/src/gallery.ts`

## Don't touch
- `src/world/**`, `src/render/renderer.ts` (1b), `src/game/**` (1d), `src/ui/**` (1e), `src/replay/**` (lead)

## Contracts used or changed
- Keeps `drawTile`, `drawBed`, `drawCt`, `drawPatient`, `drawStaff`, `drawEffect` signatures.
- Added exports: `drawWallFace(ctx, x, y, height = 32)`, `drawText(ctx, text, x, y, color, outline?)`,
  `drawTextCentered`, `measureText`, `FONT_HEIGHT`, `drawIcon(ctx, kind, x, y, {variant, flip})`,
  `iconSize`, `ICON_KINDS`, `drawEsiBadge(ctx, esi, x, y)`, `drawProp(ctx, "chair"|"plant"|"desk"|"sofa"|"coffee", x, y)`,
  `drawMonitor(ctx, x, y, frame, alarm)`.

## Status
- [x] Pixmap + palette + cached offscreen sprites
- [x] Tiles (zone floors, 3/4 wall cap + face, door, void), beds, CT (broken: lamp, smoke, sparks, hazard tape)
- [x] Chibi people 12x16: walk (4 frames), idle breathing, blink, per-id phase, tired/exhausted/fainted/resting/sick
- [x] Effects for all 12 kinds, 3x5 font, gallery, tests

## Decisions and notes
- Sat: in-bed patients draw with (p.x, p.y) = bed top-left. The playback stub uses `y: at.y + 4`; that
  shifts the patient 4 px down on the bed, so playback should pass the bed's top-left.
- Sat: waiting patients that are not moving are drawn sitting (chairs from `drawProp("chair")` fit under them).
- Sat: staff cell sprites are 12 wide at x+2; a floating ESI badge (9x9) sits ~9 px above each patient.
- Sat: agency staff wear an orange hi-vis vest (lead direction); patients show ESI as wristband + badge,
  ESI 1 also gets a pulsing red ring.
- Sat: `drawWallFace` draws a 16-wide face of `height` px (default 32 = two tile rows) below a wall cap.
- No new dependencies.

## Handoff
- Done: everything above, pushed. Test: `cd frontend && pnpm lint && pnpm build && pnpm test`,
  then `pnpm dev` and open `/gallery.html` (zoom selector up to 8x, pause checkbox).
- Not done: hair-style variety (one shape, 7 colours); props are only placed if the map agent uses them.
