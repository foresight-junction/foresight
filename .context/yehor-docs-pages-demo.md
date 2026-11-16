# One-click ED-72 replay demo

- **Issue:** #132
- **Branch:** `yehor/docs-pages-demo`, based on `main`
- **Goal:** Open the saved Gemini seed 42 replay at tick 59 from GitHub.
- **Files:** Pages workflow, README link, and decision-panel caption and rejection text.

## Handoff

Enable GitHub Actions as the Pages source in the repository settings before merging.
Once Pages deploys, open the README demo link in a signed-out browser. It should
load Gemini seed 42, paused at tick 59, and explain the four rejected assignments.
Set the repository About website to that same URL after verifying public access.

Check the frontend with `pnpm lint`, `pnpm build`, and `pnpm test` from `frontend/`.
