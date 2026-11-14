# Branch: yehor/env-firewall

- **Issue:** #31 (A8 hidden-information firewall tests)
- **Owner:** yehor
- **Agent:** yehor-claude-3c
- **Parent branch:** main
- **Created:** Sat 16:52

## Goal
A test suite proving no `rules` / `observe` / `step` result leaks hidden state (future arrivals, unannounced events, dice, seed, score), plus mutation tests proving the checks bite. Done when the fixture tests pass now and the episode tests (a)-(f) run green once #4/#5/#22 merge.

## Files and folders I own
- `ed72/environment/hospital/tests/test_firewall.py`
- `ed72/environment/hospital/tests/firewall_checks.py` (deny-list, future values, warnings, hidden-event state, past-log consistency)
- `ed72/environment/hospital/tests/firewall_shapes.py` (exact CONTRACTS v1 shapes)
- `ed72/environment/hospital/tests/firewall_fixtures.py` (MOCK CONTRACTS-shaped results + truth)
- `ed72/environment/hospital/tests/firewall_policy.py` (scripted test-double policy with probes)
- `.context/yehor-env-firewall.md`

## Don't touch
- `ed72/environment/hospital/ed72_sim/`, `ed72/environment/hospital/pyproject.toml` (#4 / PR #46, #48, Kostiantyn)
- `ed72/environment/hospital/server.py`, `mock_sim.py`, `ward` (#5, Mykhailo)
- Dockerfiles, compose, `task.toml` (#22), `eval/` (#12, #23), `Makefile`

## Contracts used or changed
- Uses CONTRACTS v1 (merged in #43): the 3 tools, Observation, ActionResult reasons, `call_cap_reached` / `episode_over`, event-log `sim` lines. No changes.
- Assumed interfaces (posted on #4 and #5): `ed72_sim.world.generate_world(seed) -> World`; `ed72_sim.engine.Simulation(world)` with `.tick`, `.world`, `.events`, `.observe()`, `.step()`; `ed72_sim.engine.build_observation(state, tick, finished)` as the view function the mutation tests monkeypatch; World/PatientSpec/EventSpec field names from `model.py`. `server.ToolHost(sim, handbook)`, `server.build_server(host) -> FastMCP`, `server.CALL_CAP`.

## Status
- [x] 1. Claim #31, worktree, read CONTRACTS v1 and the sim/server branches
- [x] 2. Checker layer + fixture tests
- [x] 3. Mutation tests on fixtures (29 field mutations + 3 log mutations)
- [x] 4. Episode tests (a)-(f) + 5 episode mutations; skip today, all green on a scratch merge of sim-core + world + tool-server + task-skeleton
- [x] 5. Codex CLI cross-review (MCP down): 4 findings, all fixed
- [ ] 6. Draft PR; re-run once #46/#48/#5/#22 merge and drop the skips

## Decisions and notes
- 2026-11-14: The hospital uv project is not on main yet, so run from the worktree root: `uv run --with pytest pytest -q ed72/environment/hospital/tests`. Once #48 lands: `cd ed72/environment/hospital && uv run --with pytest pytest -q tests/test_firewall.py` (fastmcp must be in that pyproject or the episode tests skip).
- 2026-11-14: Episodes go through the real FastMCP server with the in-memory `fastmcp.Client`, and each result is checked as `content[0].text`, the exact text the agent sees.
- 2026-11-14: Added a past-log check: totals, waiting and bed occupants must follow from the sim's event log so far. A scratch leak that wrote next tick's arrival count into `totals.faints` passed every name, value and shape check and was caught only by this.
- 2026-11-14: The rules text is not value-checked (it names event kinds and example ids). The test checks instead that it is byte-identical across seeds, so it cannot carry per-seed data.
- 2026-11-14: The seed's digits are matched only for seeds >= 100000; the episodes use 918273 and 4071999.
- 2026-11-14: Codex review fixes: every MCP content block and `structured_content` is checked (only one JSON text block allowed); `last_rejected` must equal the previous step's rejections in observe results too; `ticks_until_change` must be null unless a public pending change exists; the compose `main` block is found at any indentation and its absence fails the test.
- Not covered: future information hidden in fatigue floats, or in the value of a legitimate countdown. The past-log check covers counts and ids only.

## Handoff
- Done: checkers, fixtures, policy, all tests. Today: 47 pass, 14 skip (episodes need #46/#48 + #5, (f) needs #22).
- Verified: on a scratch merge of `kostiantyn/env-sim-core` + `env-world` world.py + `mykhailo/env-tool-server` + `yehor/harness-task-skeleton`, all 61 firewall tests pass in about 2.3 s, and the whole hospital suite (109) passes. Two sim leaks injected by hand were caught.
- Next: once those merge, rerun and confirm no skips; wire into CI (#24) by making sure fastmcp is in the hospital pyproject.
- How to test: see Decisions above.
