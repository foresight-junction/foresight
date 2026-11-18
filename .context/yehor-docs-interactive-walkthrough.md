# yehor/docs-interactive-walkthrough

- **Issue:** #152
- **Owner:** Yehor
- **Agent:** yehor-codex-1
- **Parent branch:** main

## Goal

Explain ED-72 through three interactive moments from the saved seed-42 replays.

## Files I own

- `frontend/walkthrough.html`, `frontend/src/walkthrough.ts`, and `frontend/src/walkthrough.css`
- Walkthrough entry in the Vite build and a README link

## Don't touch

- The simulator, scoring, published artifacts, or Pages deployment workflow

## Handoff

The TypeScript walkthrough and README link are complete. Run pnpm lint, pnpm build, and pnpm test in frontend. Chrome verified all three chapters, the exact full-viewer rejection state, a narrow viewport, and the no-Canvas fallback under /foresight/. The GitHub Pages deployment is tracked separately.
