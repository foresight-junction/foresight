# Branch: yehor/harness-eval-repro

- **Issue:** #23
- **Owner:** yehor
- **Agent:** lead
- **Parent branch:** main
- **Created:** Sat 19:33

## Goal
Use the preinstalled OpenCode with the default Harbor runner and pass Gemini authentication under the name OpenCode reads.

## Files
`eval/run_all.sh`, `Makefile`, `.env.example` and the host runner rows in `docs/CONTRACTS.md`.

## Handoff
Harbor 0.26.0 detects the installed OpenCode version. Tests should check argument forwarding for all three provider families and verify Gemini with a placeholder credential using Harbor dry-run. Full paid trials remain with the assigned runner. #83 remains deferred.
