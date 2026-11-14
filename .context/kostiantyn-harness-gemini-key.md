# Branch: kostiantyn/harness-gemini-key

- **Issue:** #94
- **Owner:** kostiantyn
- **Agent:** kostiantyn-claude-6
- **Parent branch:** main
- **Created:** Sat 17:57

## Goal
One model-key flag shape for every provider in the judge-facing commands, so a Gemini (or Anthropic/OpenAI) run started from the README, docs/EVAL.md or `make eval` gets its key into OpenCode.

## Files and folders I own
- `eval/run_all.sh` (agent run block and provider table)
- `README.md` ("How to run it" only)
- `docs/EVAL.md` (section 3 agent row only)

## Don't touch
- `ed72/`, scoring, tools.

## Contracts used or changed
- None. Harness flags only; env var names in CONTRACTS are unchanged.

## Status
- [x] run_all.sh: provider table sets KEY_NAME and OPENCODE_KEY_NAME; every provider gets `--api-key-name KEY --ae 'OPENCODE_KEY=${KEY}'`
- [x] README: one generic model command plus a key table
- [x] EVAL.md: agent row shows the same flags

## Decisions and notes
- Sat 18:05: #93 had already fixed Gemini as a special case. This branch makes every provider use the same flags. For Gemini the expanded flags are byte-for-byte what #93 sends (and what the 0.811712 run on #17 used), so Gemini behaviour is unchanged.
- Harbor resolves `--ae NAME=${VAR}` from the host env (`harbor/utils/env.py` `resolve_env_vars`).
- Anthropic/OpenAI: the `--ae` is an identity mapping. Not run end to end (no keys here).

## Handoff
Done: the three files above. To test: `bash -n eval/run_all.sh`; `ED72_MODEL=gemini/gemini-3.8-flash make eval` with GEMINI_API_KEY in .env should reach the agent without ProviderAuthError.
