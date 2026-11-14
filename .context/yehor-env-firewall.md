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
- [x] 3. Mutation tests on fixtures
- [x] 4. Episode tests (a)-(f) + episode mutations
- [x] 5. Codex CLI cross-review (MCP down): 4 findings, all fixed
- [x] 6. Merged main (#46, #44, #48): episodes now run on the real sim; MCP-only tests still skip
- [ ] 7. Kostiantyn merges PR #56; the MCP tests switch on when #57 merges with fastmcp in the hospital pyproject

## Decisions and notes
- 2026-11-14: Run with `cd ed72/environment/hospital && uv run --with pytest pytest -q tests/test_firewall.py`.
- 2026-11-14: Episodes run on the real sim directly (`sim.observe()` / `sim.step()`, serialised with json.dumps). Through MCP, `test_mcp_results_equal_the_sim_results_and_leak_nothing` checks that the server returns the same results and adds no output channel. That test, the call cap and the tool list skip until #57 merges.
- 2026-11-14: fastmcp is in neither main's hospital pyproject nor #57. I asked on #57 for `dependencies = ["fastmcp==4.2.0"]`.
- 2026-11-14: The hand-written CONTRACTS fixtures stay: they pin the checks independently of the sim. The mock event-log fixture was replaced with a real episode log.
- 2026-11-14: A past-log check: totals, waiting and bed occupants must follow from the sim's event log so far. It catches future data written into a legitimate field, which the name, value and shape checks miss.
- 2026-11-14: Codex review fixes: every MCP content block and `structured_content` is checked; `last_rejected` must equal the previous step's rejections in observe results too; `ticks_until_change` must be null unless a public pending change exists; the compose `main` block is found at any indentation and its absence fails the test.
- 2026-11-14: The rules text is not value-checked (it names event kinds and example ids). The test checks instead that it is byte-identical across seeds. The seed's digits are matched only for seeds >= 100000 (the tests use 918273 and 4071999).
- Not covered: future information hidden in fatigue floats or in the value of a legitimate countdown.

## Handoff
- Done: everything in #31. Against the real sim on main: 55 firewall tests pass and 4 skip. Three need the #57 server plus fastmcp (MCP equals sim, call cap, exactly 3 tools); (f) needs the #58 packaging. No leaks found.
- Verified: on a scratch merge of main + #57 server + #58 packaging with fastmcp 4.2.0, all 59 firewall tests pass and the hospital suite (132) passes.
- Next: after #57 and #58 merge, rerun and confirm 0 skips. For the full 144-tick runs with #6 events, nothing changes: the episodes already run all 144 ticks.
- How to test: see Decisions above.
