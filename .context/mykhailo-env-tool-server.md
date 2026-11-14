# Branch: mykhailo/env-tool-server

- **Issue:** #5 (A3 tool server: MCP + ward CLI + /health)
- **Owner:** mykhailo
- **Agent:** mykhailo-claude-1
- **Parent branch:** main
- **Created:** Sat 14:35

## Goal
Expose the sim to the agent per CONTRACTS v1 (on `kostiantyn/docs-rules-realign`, #41): exactly three MCP tools `rules`, `observe`, `step(actions)` over streamable HTTP at `http://hospital:8000/mcp`, GET `/health`, a 500-call cap counted in the hospital, one event-log line per call, and the `ward` CLI in `main` calling the same tools. Done when `ward observe` from `main` returns an observation and an MCP client lists exactly the 3 tools.

## Files and folders I own
- `ed72/environment/hospital/server.py`
- `ed72/environment/hospital/mock_sim.py` (MOCK sim until #4 lands; not copied into the image)
- `ed72/environment/hospital/tests/test_server.py`, `ed72/environment/hospital/tests/test_ward.py`
- `ed72/environment/ward`
- `.context/mykhailo-env-tool-server.md`

## Don't touch
- `ed72/environment/hospital/ed72_sim/` and the hospital `pyproject.toml` (#3/#4, kostiantyn-claude-2)
- `collect.py`, `ed72/tests/` (#11), Dockerfiles, compose, `task.toml` (#22)

## Contracts used or changed
- Uses CONTRACTS v1: tools, Action/ActionResult/Observation shapes, call cap 500, `call_cap_reached` / `episode_over`, event-log agent lines, `/health`. No changes.

## Status
- [x] 1. Verified FastMCP 4.2.0 server and MCP SDK 2.3.0 client APIs (subagent mykhailo-claude-1a, ran real code)
- [x] 2. `ToolHost` core (cap, episode_over, refused-call logging) + MOCK sim + tests
- [x] 3. FastMCP wiring: 3 tools + /health, in-memory client test
- [x] 4. `ward` CLI (MCP client) + test against a live local server (subagent mykhailo-claude-1c)
- [x] 5a. Real wiring: `Simulation(generate_world(seed), EVENT_LOG_PATH)` (PR #48, #46). Checked in a throwaway merge: full 144-tick episode over MCP, replay of the logged steps gives the identical final observation.
- [ ] 5b. Needs `Simulation.record_call` (asked on #4) and HANDBOOK.md in the hospital image (#7, #22)
- [ ] 6. cross-review, ship-pr (after #46/#48 merge, so the PR is only my files)

## Decisions and notes
- 2026-11-14: Tool logic lives in a plain `ToolHost` class so it is testable without HTTP; FastMCP only wraps it.
- 2026-11-14: No pyproject of my own (the hospital one belongs to #4). Tests run with `uv run --with fastmcp==4.2.0 --with pytest pytest`. Asked #4 to add fastmcp to their pyproject.
- 2026-11-14: More than 50 actions: the extra ones get `bad_action`, so no new error code is needed.
- 2026-11-14: The sim owns the event log (`seq`, file at `constants.EVENT_LOG_PATH`, `step` lines). The server only adds lines for `rules`, `observe` and refused calls via `sim.record_call`. It truncates the log at startup, because a restarted server restarts the sim at tick 0.
- 2026-11-14: Refused `step` calls are logged with `result: {"error": ...}`; asked #11 to skip those in the replay.
- API gotchas: mcp 2.x client is `mcp.client.streamable_http.streamable_http_client(url)` yielding `(read, write)`; results are snake_case (`structured_content`). `@mcp.custom_route(path, methods=[...])`. FastMCP may reject non-localhost Host headers: pass `allowed_hosts` if Docker's `hospital` host is refused.

## Handoff
- Done: server.py (3 tools, /health, cap, refused-call logging), ward CLI, MOCK sim mirroring the real Simulation, 18 tests.
- Not done: `record_call` in the real sim (#4); HANDBOOK.md copied into the hospital image (#7 writes it, #22 packages it); `fastmcp==4.2.0` in the hospital pyproject; Harbor smoke from `main` (`ward observe`).
- How to test: `cd ed72/environment/hospital && uv run --python 3.12 --with fastmcp==4.2.0 --with mcp==2.3.0 --with pytest pytest -q tests`. Local server: `USE_MOCKS=1` uses the mock; without it, it needs `ed72_sim` from #46/#48.
