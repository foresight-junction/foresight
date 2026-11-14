# kostiantyn/harness-preinstall-opencode

## Goal
Make `harbor run -p ed72 -a opencode -m <model>` work with Harbor's default 360 s agent-setup limit (#17, #22).

## Files owned
ed72/environment/Dockerfile (the agent `main` image).

## Status
- Done: node 22 + `opencode-ai@1.19.5` preinstalled. Harbor's `is_requested_version_installed` then skips its apt/nvm/npm install (any version counts when none is pinned).
- Verified: `docker build` OK; `opencode --version` = 1.19.5 inside the image (Harbor's own check command); stdbuf and ward present.

## Handoff
Done. Test: after merge, plain `harbor run -p ed72 -a opencode -m <model>` with no setup multiplier; agent setup should take seconds. Gemini needs `GOOGLE_GENERATIVE_AI_API_KEY` in the agent env (not GEMINI_API_KEY).
