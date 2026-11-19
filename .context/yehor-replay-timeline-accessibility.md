# yehor/replay-timeline-accessibility

- **Owner:** Yehor
- **Agent:** yehor-codex-1a
- **Base:** 5108a97d5e112fdec99217b9ebbfa3e60e44a9dc
- **Issue:** #156

## Goal

Make the full viewer's timeline keyboard-accessible and keep its canvas visualization and direct seeking.

## Files I own

`frontend/src/ui/scrubber.ts`, `frontend/src/ui/hud.ts`, `frontend/src/ui/hud.css`, and this branch context.

## Don't touch

The walkthrough viewer, replay fixtures, and simulator contracts.

## Handoff

The native range uses the latest loaded tick as its maximum. Live updates refresh the canvas and range in place so focus stays on the same input. The focused timeline also supports Space, +/- and Shift+Left/Right.

Run `pnpm lint`, `pnpm build`, and `pnpm test` in `frontend/` (108 passed, 1 skipped). Chrome verified Tab focus, arrow and endpoint keys, accessible tick text, saved deep links, mouse and touch seeking, and focus retention during live growth. The live browser check streamed saved fixture ticks through the viewer's SSE route.
