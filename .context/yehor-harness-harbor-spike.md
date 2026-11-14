# Branch: yehor/harness-harbor-spike

- **Issue:** #21
- **Agent:** yehor-codex-1
- **Parent branch:** main

## Goal

Run OpenCode against a stub hospital MCP server in Harbor and record the transport, reward, and log locations for #22, #5, and #11.

## Files and folders I own

- `docs/HARBOR-NOTES.md`
- `spikes/ed72-harbor-smoke/`
- `.context/yehor-harness-harbor-spike.md`

## Don't touch

- ED-72 task packaging (#22), tool server and CLI (#5), and verifier implementation (#11).

## Contracts used or changed

- Testing the existing streamable HTTP endpoint and separate-verifier artifact contract with a standalone one-tick fixture.

## Handoff

OpenCode 1.19.5 with Gemini 3.8 Flash called `rules`, `observe`, and `step` in order on Harbor 0.26.0. The separate verifier wrote 1.0 from the collected sidecar report.

Reproduce from `spikes/ed72-harbor-smoke/` using the command in `docs/HARBOR-NOTES.md`. The packaging owners can use streamable HTTP as the primary transport. The full-simulator calibration belongs to #17.
