# Branch: leonardodadenchik/fe-pixel-viewer

- **Issue:** #97
- **Owner:** leonardodadenchik
- **Agent:** leonardodadenchik-claude-1 (lead, orchestrator)
- **Parent branch:** main
- **Created:** Sat 19:55

## Goal
A top-down 2D pixel replay of one ED-72 episode in `frontend/`, showing every choice the AI made and what followed. Works when `pnpm dev` plays the reference and the Gemini replay tick by tick with walking patients and staff, effects, and a side panel of the AI's actions.

## Files and folders I own
- `frontend/` (whole folder). Helper branches own parts, see below.

## Don't touch
- Everything outside `frontend/`: sim, scorer, tools, task, docs, contracts. The viewer only reads the sim in-process through `frontend/tools/export_replay.py`.

## Contracts used or changed
- Reads CONTRACTS v1 Observation, Action, ActionResult and Event log shapes. Changes none.

## Helper branches (merged into this branch by the lead)
| Agent | Branch suffix | Owns |
|---|---|---|
| 1a data | `--claude-1a` | `frontend/tools/**`, `frontend/public/replays/**` |
| 1b map + renderer | `--claude-1b` | `frontend/src/world/**`, `frontend/src/render/renderer.ts`, `frontend/src/render/camera.ts` |
| 1c sprites | `--claude-1c` | `frontend/src/render/sprites.ts`, `frontend/src/render/palette.ts`, `frontend/src/render/art/**` |
| 1d playback | `--claude-1d` | `frontend/src/game/**` |
| 1e HUD | `--claude-1e` | `frontend/src/ui/**`, `frontend/src/style.css` |
| lead | this branch | `frontend/src/main.ts`, `frontend/src/replay/**`, `frontend/index.html`, `frontend/package.json`, configs |

## Status
- [x] Issue #97, skeleton with types, frame contract and working stubs; reference replay seed 42
- [x] Agents 1a–1e on helper branches, all merged (Sat 20:5x)
- [x] Merge helpers, integration fixes (route(), bed offset, wall face), browser check
- [x] Full-screen stage, compact map, spread seating, ambulance runs, 0.25x-16x speeds
- [x] Live mode: frontend/tools/live + `?live=1`, runs auto-saved; Gemini smoke-tested live
- [ ] PR to main (owner asked to push and merge)

## Decisions and notes
- Sat 20:05. Vite + TypeScript + Canvas 2D, no game engine: small, fast to build, no new runtime deps. Dev deps typescript, vite, vitest only.
- Sat 20:05. All art drawn in code; no image assets, so nothing copied.
- Sat 21:05. Map compacted 48x28 -> 37x23 tiles and the canvas fills the stage (integer backing zoom, CSS fit), so sprites show ~30% bigger and rooms look full. Waiting patients take a free chair picked by id (spread over the room), standing room only once all 21 chairs are taken. `?tick=N` opens a replay at tick N.
- Sat 21:15. Ambulance runs: ESI 1-2 and bus-crash arrivals come by ambulance (Frame.vehicles). It reverses into the bay from the top edge, opens its rear doors at PHASE.next, lets riders out one by one, drives off; two ambulances when more than 3 riders. Sirens flash and wash the bay red/blue at night. `?tick=12.45` opens part-way through a tick.
- Sat 22:10. Live mode: frontend/tools/live (helper 1f) runs the real hospital MCP server locally with a recorder; Gemini (or a scripted policy) plays through MCP; ticks stream over SSE (/live proxied by Vite) into a growing Replay (`?live=1`). Runs auto-save to public/replays/runs/ (gitignored), open with `?replay=runs/<file>`. Speeds 0.25x-16x.
- Sat 22:35. Seeds: replays exported for seeds 42, 7, 1234 under the current rules (main raised load to 4.0); HUD has a seed picker. Live mode has a New run form (seed + agent) -> POST /live/start; serve.py runs any number of episodes. test_gemini_matches_real_run skipped: the Harbor run used the old rules.
- Sat 23:05. Live agents: gemini, kimi (Verda Inference, kimi-k3-1-pro, effort low), claude (anthropic SDK, claude-opus-5-5, effort medium, cached handbook, structured outputs, fallbacks "default"); shared prompt and parsing in llm.py. Keys: GEMINI_API_KEY, VERDA_INFERENCE_API_KEY, ANTHROPIC_API_KEY or CLAUDE_API_KEY; --env-file repeatable. Gemini script replays relabelled "script (replayed)". Smoke-tested: Kimi ~8 s/tick, Claude ~14 s/tick.

## Handoff
- Done: replay viewer (`pnpm --dir frontend dev`, then `?replay=<file>`) and live mode (`?live=1` with `frontend/tools/live/serve.py` running, see its README). Not done: a clean full Gemini live run to ship as a replay (the first one crashed at tick 116 on a console encoding bug, now fixed).
- How to test: `pnpm --dir frontend install && pnpm --dir frontend lint && pnpm --dir frontend build && pnpm --dir frontend test`.
- Live backend tests: `PYTHONPATH="ed72/environment/hospital;ed72/solution;eval/baselines;frontend/tools/live" uv run --no-project --python 3.12 --with pytest --with fastmcp==4.2.0 --with mcp==2.3.0 python -m pytest -q frontend/tools/live/tests`.
- Regenerate a replay: `PYTHONPATH="ed72/environment/hospital:ed72/solution" uv run --no-project --python 3.12 python frontend/tools/export_replay.py --policy reference --seed 42` (on Windows use `;` in PYTHONPATH).
