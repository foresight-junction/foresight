# Branch: yehor/harness-harbor-spike

- **Issue:** #21
- **Agent:** yehor-codex-1
- **Parent branch:** main

## Goal

Run OpenCode against a stub hospital MCP server in Harbor and record the transport, reward, and log locations for #22, #5, and #11.

## Files and folders I own

- `docs/HARBOR-NOTES.md`
- `.context/yehor-harness-harbor-spike.md`

## Don't touch

- ED-72 task packaging (#22), tool server and CLI (#5), and verifier implementation (#11).

## Contracts used or changed

- Testing the existing streamable HTTP endpoint and separate-verifier artifact contract with temporary fixtures.

## Handoff

Docker Desktop is running. The temporary fixture defines one MCP ping tool with a sidecar-owned count. The verifier checks the collected report for exactly one ping. Oracle scored 1 and nop scored 0 using Harbor 0.25.0 in separate mode. See `docs/HARBOR-NOTES.md`. Run one Gemini-backed OpenCode trial once `GEMINI_API_KEY` is available in the ignored worktree `.env`.
