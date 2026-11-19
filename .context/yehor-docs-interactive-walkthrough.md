# yehor/docs-interactive-walkthrough

- **Issue:** #152
- **Owner:** Yehor
- **Agent:** yehor-codex-1
- **Parent branch:** main

## Goal

Explain ED-72 through three interactive moments from the saved seed-42 replays.

## Files I own

- `frontend/walkthrough.html`, `frontend/src/walkthrough.ts`, and `frontend/src/walkthrough.css`
- Walkthrough entry in the Vite build and the README introduction and replay preview

## Don't touch

- The simulator, scoring, published artifacts, or Pages deployment workflow

## Handoff

The walkthrough plays and scrubs three saved seed-42 clips. The README includes
a short animation captured from the production build and links to local setup.

Run `pnpm lint`, `pnpm build`, and `pnpm test` in `frontend/`. Chrome verified
the clips, keyboard timeline, full-viewer link, 390 px layout, and Canvas fallback
on a production build served under `/foresight/`.

Pages is disabled on the organization repository. Once #132 deploys the viewer,
the README link and preview can point directly to the published walkthrough.
