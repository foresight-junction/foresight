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
- [ ] Agents 1a–1e on helper branches
- [ ] Merge helpers, check in browser, PR

## Decisions and notes
- Sat 20:05. Vite + TypeScript + Canvas 2D, no game engine: small, fast to build, no new runtime deps. Dev deps typescript, vite, vitest only.
- Sat 20:05. All art drawn in code; no image assets, so nothing copied.

## Handoff
- Done: skeleton runs end to end (`pnpm --dir frontend dev`).
- How to test: `pnpm --dir frontend install && pnpm --dir frontend lint && pnpm --dir frontend build && pnpm --dir frontend test`.
- Regenerate a replay: `PYTHONPATH="ed72/environment/hospital:ed72/solution" uv run --no-project --python 3.12 python frontend/tools/export_replay.py --policy reference --seed 42` (on Windows use `;` in PYTHONPATH).
