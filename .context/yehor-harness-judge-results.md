# Branch yehor/harness-judge-results

- Issue #25
- Base main at `7cda3cd`
- Scope `README.md`, `docs/DEMO.md`, and the screenshot used in the README

The README covers replay, live setup, and the pinned Harbor benchmark. The demo uses the bundled seed-42 replay and the published seeds 3101–3103 matrix. The screenshot is an actual browser capture from the bundled reference replay.

## Handoff

- Viewer build, lint, and tests passed. Chrome opened the saved replay and started and completed a new scripted episode through the live viewer. Simulator tests passed.
- All nine keyless baseline scores matched the release. The clean-checkout seed-3101 run reached the three Gemini trials, and Google rejected the credential for all three. Retry with a valid key before calling the paid reproduction verified.
- The Windows setup guidance from PR #125 is in the README. Publish this branch through a single documentation PR and add the public video URL when available.
