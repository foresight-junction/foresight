# Branch: yehor/harness-eval-repro

- **Issue:** #23
- **Owner:** yehor
- **Agent:** lead
- **Parent branch:** main
- **Created:** Sat 19:33

## Goal
Use the preinstalled OpenCode with the default Harbor runner and pass Gemini authentication under the name OpenCode reads.

## Files
`eval/run_all.sh`, `Makefile`, `.env.example` and the host runner rows in `docs/CONTRACTS.md`. The README and demo changes are limited to matching run commands.

## Handoff
Harbor 0.26.0 detects the installed OpenCode version. Verified Gemini, Google, Anthropic and OpenAI argument forwarding with placeholder keys, Harbor 0.26 dry-run scheduling and the seven existing eval tests. Full paid trials remain with the assigned runner. #83 remains deferred.
