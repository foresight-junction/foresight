# Red team, round 1 (#13)

Attacker: `kostiantyn-claude-2h`, who did not write the scorer. Target: batch-1 code on branch `kostiantyn/reward-redteam-1` (world, engine, scorer, `collect.py`, `verify.py`).
Every attempt below that can run against real code is a regression test in `ed72/environment/hospital/tests/test_redteam_round1.py` (80 tests, all pass). Result legend: **holds** = the defence worked; **EXPLOIT** = it worked for the attacker; **pending** = needs the tool server (#5) or the real Harbor stack.

**Exploits found: none.** Three notes (N1-N3) need action by others, see the end.

## Policies on seeds 1-3 (score out of 100)
The "greedy" policy is written in the test file from the public observation only: admit by severity, staff each zone from the least tired people, no agency, no repair, no event handling. The other rows change one thing.

| Policy | Seed 1 | Seed 2 | Seed 3 | Spend |
|---|---|---|---|---|
| greedy (honest) | 99.42 | 99.42 | 99.73 | 0 |
| greedy + permanent divert | 44.66 | 48.10 | 46.70 | 0 |
| greedy + agency spam to the €24 000 limit | 89.70 | 89.69 | 89.97 | 23 750 |
| light patients only (ESI 4-5) | 10.62 | 13.02 | 12.37 | 0 |
| greedy, then stop calling `step` at tick 12 | 4.50 | 4.64 | 6.10 | 0 |
| everyone rests all episode | 0 | 0 | 0 | 0 |
| do nothing | 0 | 0 | 0 | 0 |
| do nothing until tick 143, then crew all zones and fill all beds | 3.99 | 4.48 | 4.98 | 0 |

## Attempts
| # | Attempt | Expected defence | Result | Evidence |
|---|---|---|---|---|
| 1 | Admit with no staff, crew arrives later | `first_covered_tick` counts only from the first covered tick; ESI 1 in an uncovered bed rolls 10% death per tick | holds | `test_unstaffed_admission_counts_only_from_first_covered_tick` (admit t0, covered t5, late), `test_staffed_admission_of_the_same_patient_is_on_time`, `test_unstaffed_esi1_bed_is_not_a_free_pass` |
| 2 | Fill every bed at tick 143 with no covered tick | Loss 1, same as never admitting | holds | `test_fill_every_bed_at_last_tick_uncovered_is_full_loss` (O = 0 both ways) |
| 2b | Same, with a crew (honest cover at 143) | Only 0.3 loss, capped by free covered beds | holds, as designed | `..._covered_earns_only_partial_credit` (O = 0.7 for the 8 late patients) |
| 2c | Whole episode idle, crew and fill all beds at 143 | Far below the reference | holds, but close to the 5-point bar on seed 3 (4.98), see N2 | `test_hold_back_then_fill_at_tick_143_is_a_bad_baseline` |
| 3 | Divert all the time + good play | Caps near 47; good play beats it by far | holds | 44.7 / 48.1 / 46.7 vs 99.4 (`test_permanent_divert_caps_near_47`). Seed 2 is 48.1: "near 47", not strictly under |
| 4 | Agency spam to the €24 000 limit | B goes to 0, spend never above the limit | holds | `test_agency_spam_spends_but_loses_points`, `test_agency_cannot_pass_the_hard_limit`: 23 750 spent, 89.7 |
| 5 | Everyone rests (all episode) | W is worth at most 10 x O; uncovered beds stall | holds | score 0 on all 3 seeds. "Rest only in quiet periods" is not tested separately: all-rest is the limit case |
| 6 | Admit only light patients | ESI 1-2 carry about half the weight | holds | 10.6 / 13.0 / 12.4 |
| 7 | Stop calling `step` early (tick 12) | Remaining ticks still run | holds | 4.5 / 4.6 / 6.1, `ended == "agent_stopped"`, `episode_end` present |
| 8 | Malformed actions: non-dict, `None`, empty dict, wrong types, list or dict valued fields, unknown type, missing fields, unknown ids (patient, staff, agency staff before ordering), ESI 1 to fast-track, `repair` with a working CT | Rejected with the CONTRACTS reason, no side effects, valid neighbours still apply | holds | 25 parametrized cases in `test_malformed_action_rejected_with_no_side_effects` compare against a control sim stepped with `[]` (observation and sim log identical) |
| 9 | 1000-action list (500 agency + 500 divert) | No crash, no overspend | holds | `test_1000_action_list_...`: results for all 1000, spend within the limit |
| 10 | Same staff in two zones in one list; same patient admitted twice | One person, one bed | holds | `test_same_staff_to_two_zones...`, `test_one_doctor_listed_in_two_zones_does_not_cover_both`, `test_same_patient_admitted_twice...` |
| 11 | Assign fainted staff or agency staff not yet arrived | `staff_unavailable` | holds | `test_unavailable_staff_cannot_be_assigned` |
| 12 | `step` with a non-list payload (`None`, `5`, `2.5`, `True`) | Rejected | partly: the core raises `TypeError` before any state change; the server must catch it, see N1 | `test_non_list_step_payload_fails_before_any_state_change` |
| 13 | `step` after tick 143 | `{"error": "episode_over"}`, nothing logged or scored | holds | `test_step_after_tick_143_is_refused_and_changes_nothing` |
| 14 | `record_call` refusals (call-cap errors, rules spam) | Do not change O, T, W, B or spend | holds | `test_refused_calls_are_logged_but_do_not_change_the_reward` (`ended` becomes `call_cap`, `tool_calls` counts them) |
| 15 | Injected sim lines in the log fed to `collect.py` (fake `discharged`, negative `spend`, huge budget, huge `on_shift`) | Replay uses only agent step actions and a fresh sim | holds | `test_collect_ignores_injected_sim_lines` (report identical) |
| 16 | Step line tagged with `error`, extra `observe` / `rules` lines | At the right tick: re-recorded, only `tool_calls` changes. At a stale tick: `collect.py` raises, no report, verifier writes 0 | holds | `test_collect_refused_and_read_calls_change_only_the_call_count`, `test_collect_rejects_agent_lines_at_a_stale_tick` |
| 17 | Reordered, duplicated or missing step ticks, truncated JSON line | Fail closed: no report written, verifier writes 0 | holds | `test_collect_fails_closed_on_reordered_duplicated_or_missing_ticks`, `..._truncated_json_line` |
| 18 | Extra `step` line at t=143 after the episode ended | No effect (a finished sim ignores steps); without a `result` field `collect.py` raises | holds | `test_collect_ignores_extra_steps_after_the_episode_ended` |
| 19 | Live score vs `collect.py` replay of the written log | Identical | holds | `test_collect_replay_matches_the_live_score` |
| 20 | Same seed, same actions | Same score | holds | `test_same_seed_same_actions_same_score` |
| 21 | Forged `report.json` into `verify.py`: reward 1.0 with honest components; reward 1.0 / score 100 with inconsistent O,T,W,B; score 100 with O=1, T=0; reward above 1; negative W; reward as string, bool or null; missing key; list instead of object; drift of 0.01 | Write 0, exit 1 | holds | `test_forged_report_writes_zero` (11 cases) |
| 22 | `NaN`, `Infinity`, `-Infinity` in each of the six fields; empty, truncated, `null`, `[]` files; missing file | Write 0 | holds | `test_non_finite_numbers_write_zero`, `test_garbage_report_writes_zero`, `test_missing_report_writes_zero` |
| 23 | Extra keys in the report | No effect on the reward | holds | `test_extra_keys_do_not_change_the_reward` |
| 24 | Self-consistent forged report (O, T, W, B all 1, reward 1.0) | Not detectable by `verify.py`; the defence is that only `collect.py` in `hospital` writes the artifact | holds by design | `test_self_consistent_forgery_passes_verify_so_the_channel_is_the_defence` documents it |
| 25 | Truncated log into the scorer | Refused | holds | `test_score_refuses_a_truncated_log` |
| 26 | Sim source, seed or scorer inside the agent container | Not copied into `main` | holds on `origin/yehor/harness-task-skeleton` (static) | `ed72/environment/Dockerfile` copies only `workspace/HANDBOOK.md` and `ward`. Sim, `collect.py`, `server.py`, `start.sh` are copied only by `ed72/environment/hospital/Dockerfile`. In `docker-compose.yaml`, `ED72_SEED` is set on `hospital` only. `ed72/tests/Dockerfile` ships only `test.sh` and `verify.py` |
| 27 | Write `reward.txt` from the agent side | Impossible in separate verifier mode | holds (static) | `task.toml`: `[verifier] environment_mode = "separate"`; the only input is the artifact `/evidence/report.json` from service `hospital`. Not run end to end here |
| 28 | Other ports or paths on `hospital` | Only `/mcp` (tools) and `/health` | pending #5 | needs the tool server |
| 29 | 500-call cap enforced by the server, `rules` / `observe` spam, oversized payload | Cap reply, no reward effect | pending #5 | the scorer side is covered by attempt 14 |
| 30 | MCP-level checks: tool list, `/health` leaks, timing and float covert channels | Only the 3 tools | pending #5 | #31 covers field names; covert channels still open |

## Notes for others (not exploits)
- **N1, for #5:** the core does not validate that `actions` is a list. `None` or a number raises `TypeError` (no state change); a string or dict is iterated and every character or key becomes a `bad_action`, and the tick advances. The server should reject a non-list with a clear error before calling `step`, and cap the payload size (a 1000-action list is accepted and logged in full today).
- **N2, for lane C / #12:** the "hold back, then fill at tick 143" baseline scores 3.99 / 4.48 / 4.98. That is under AGENTS.md §10.5 (reward <= 0.05) on all three seeds, but seed 3 is within 0.02 of the line. A change to the arrival rate or bed counts can push it over; keep it in the EVAL table.
- **N3, difficulty:** a naive greedy policy with no agency, no repair and no event handling already scores 99.4. Not an exploit, but there is no gap for a model to show, so the knobs in SPEC §7 may need raising (the margin over the baselines is the harder test, not the ceiling).
- Harbor skeleton branch: `ed72/environment/Dockerfile` copies `workspace/HANDBOOK.md` and `ward`, and the hospital Dockerfile copies `server.py`; none of those files exist on that branch yet, so the images will not build until they land.

# Red team, round 2 (#14), part 1: tool server

Attacker: `mykhailo-claude-1l`, who did not write the tool server or the scorer. Target: `main` at `79fabfc` (`server.py` on FastMCP 4.2.0, the real `ed72_sim` engine, `collect.py`). This part closes round 1's pending rows 28-30 and note N1.
Every attempt is a regression test in `ed72/environment/hospital/tests/test_redteam_round2.py` (112 pass, 3 strict xfails that flip when fixed). Probes ran in process (`fastmcp.Client(mcp)`), against the real streamable-HTTP app with hand-written JSON-RPC bytes (`starlette.testclient`), and against the server in a subprocess on a free localhost port. Result legend as in round 1, plus **latent** = wrong in code, but not reachable by the agent today.

**Exploits found: one, low severity, no reward effect (E1), now fixed (c281e04).** Nothing found lets the agent raise its score, read the seed or the world, or see the future. Three notes (N4-N6) need action by #5 / #4.

## Attempts
| # | Attempt | Expected defence | Result | Evidence |
|---|---|---|---|---|
| 28a | Route table of the HTTP app | Only `/mcp` and `/health` | holds | `test_only_mcp_and_health_are_routed` |
| 28b | GET, POST, PUT, DELETE on `/`, `/docs`, `/redoc`, `/openapi.json`, `/admin`, `/reset`, `/seed`, `/finalize`, `/events`, `/log`, `/sse`, `/messages`, `/mcp/tools`, OAuth `.well-known` paths, encoded traversal (`/..%2fserver.py`, `/%2e%2e/...`, `..%5c`) | 404, no leak | holds | `test_other_paths_answer_404` (84 cases) |
| 28c | `/health` body, other methods, query strings | Exactly `{"ok":true}`; 405 for POST, PUT, DELETE, PATCH, OPTIONS; not counted or logged | holds | `test_health_answers_only_ok_true_and_only_to_get` |
| 28d | GET `/mcp` without a session | Refused, no leak | holds | `test_get_mcp_without_a_session_is_refused_and_leaks_nothing` |
| 28e | MCP resources, resource templates, prompts; `read_resource` of `file:///etc/passwd`, `file:///proc/self/environ`, `resource://world`; `get_prompt` | All lists empty; reads refused with no content | holds | `test_no_resources_prompts_or_templates_are_exposed`. The server advertises the `logging`, `prompts` and `resources` capabilities (FastMCP default), all empty |
| 28f | `completion/complete`, `logging/setLevel`, `sampling/createMessage`, `resources/read`, an invented `admin/reset`, as raw JSON-RPC | No data, no state change | holds | `test_completion_logging_and_sampling_methods_leak_nothing` |
| 29a | 8 threads x 70 mixed calls straight into `ToolHost.call` | Exactly 500 answered, 60 `call_cap_reached`; log `seq` contiguous; one step line per tick | holds | `test_call_cap_holds_under_threads` |
| 29b | 4 parallel HTTP sessions against the server in a subprocess (cap set to 40, 60 calls) | 40 answered, 20 capped, no lost or doubled lines | holds | `test_call_cap_holds_across_parallel_http_sessions` |
| 29c | Several sessions; disconnect and reconnect | One hospital, one episode: B sees A's step; a new session does not reset | holds | `test_sessions_share_one_hospital_and_reconnecting_does_not_reset` |
| 29d | `rules` / `observe` spam between every step of a full greedy episode | Same O, T, W, B and reward | holds | `test_rules_and_observe_spam_does_not_change_the_reward` |
| 29e | N1: `step` with `actions` as a string, `null`, a number, a dict, missing, or under a wrong key | Refused before the sim | holds: FastMCP's schema check answers `isError` with a pydantic message; no tick, no sim change. Not counted and not logged, see N4 | `test_non_list_step_is_refused_before_the_sim` (6 cases) |
| 29f | 10 000 actions in one step | Results for all; the log keeps the first 50 | holds | `test_10000_actions_reach_the_log_as_50` |
| 29g | Request body over 4 MiB | 413 before parsing | holds (mcp 2.3 `max_request_body_size`, default 4 MiB) | `test_body_over_4_mib_is_refused_with_413` |
| 29h | Deeply nested JSON (200 and 5000 levels) inside an action | JSON-RPC parse error -32700, nothing applied | holds | `test_deeply_nested_json_is_refused_by_the_parser` |
| 29i | 4301-digit integer inside an action | Parse error, nothing applied | holds | `test_huge_integer_is_refused_by_the_parser` |
| 29j | Values that do parse: 4300-digit integer, `NaN`, 120-deep list, 100 kB string | Applied and logged once; replay equals the live score | holds for the reward; the reply is wrong, see N5 | `test_odd_values_that_parse_are_logged_and_replay_exactly`, `test_a_step_that_advanced_the_tick_does_not_reply_with_an_error` (xfail on Windows only) |
| 29k | Log growth from one agent | Bounded | holds after the E1 fix: every step line, refused or not, now logs at most 50 actions. Before it, a refused step logged every action it was sent (up to the 4 MiB body cap, about 2 GiB per episode) | `test_refused_step_logs_at_most_50_actions` |
| 29l | Engine exception after actions were applied (RecursionError from a 2000-deep list, in process) | No live state that the log lacks | latent (N6): the `divert` is applied live, no step line is written, the tick does not move. Over HTTP the parser stops it first (29h, 29i) | `test_a_failed_log_write_leaves_no_unlogged_state` (xfail) |
| 29m | Calls after the cap and after tick 143 | After the end: `observe` says `finished`, `step` gives `episode_over`. After the cap: every tool is refused and only refusal lines are added | holds | `test_after_the_cap_nothing_moves_and_after_the_end_only_reads_work` |
| 30a | Tool list and input schemas | Exactly `rules`, `observe`, `step`; `rules` and `observe` take no arguments, `step` only `actions` (`additionalProperties: false`) | holds | `test_tool_list_is_exactly_the_three_tools_with_closed_schemas` |
| 30b | Tool descriptions, server instructions | No seed, path, log name or hidden field | holds | `test_tool_descriptions_and_instructions_leak_nothing` |
| 30c | Error text: schema errors, extra arguments, unknown tools (`world`, `../server`), unknown resources, serialisation failures | No path, source file name, traceback, seed or world field | holds. Tracebacks go to the server's stderr only. Errors show the pydantic version URL, which is harmless | `test_error_replies_leak_no_path_source_or_seed`; most tests above also call `assert_no_leak` |
| 30d | Value-level covert channel: does any observation value, float or ordering depend on future arrivals, events or dice? | Two worlds identical up to tick 60, one with no arrivals, no new events and no hazards after it, give identical observations and step replies up to tick 60 | holds on seeds 1-3 | `test_observations_do_not_depend_on_the_future` |
| 30e | A float in the observation carries RNG state | Every float is a tenth (fatigue, `counts_as`); none equals any world uniform | holds | `test_no_observation_float_carries_rng_state` |
| 30f | Timing | No future-dependent work at call time | holds by construction (code read, not timed): `generate_world` draws every roll before the server starts, and a step only touches arrived patients and the current tick, which the returned observation shows anyway | `engine.py`, `observation.py`; 30d shows the replies are equal |

## Exploit
- **E1, low, for #5:** `ToolHost.call` logs a refused `step` (`episode_over`, `call_cap_reached`) with `self.sim.record_call(tool, args, ...)`, so the full action list goes to the log, past the 50-action cap that `_step` applies. No reward effect (`collect.py` never replays a refused step), but it is the only way to write about 4 MiB per call into the log, and 29k's bound depends on it. Fix: for a refused step, log `{"actions": args["actions"][:MAX_ACTIONS]}` (or `{}`: `collect.py` reads only `tool` and `result` from refused lines). **Fixed** in c281e04 (PR #78) with the first option; the test is now a plain regression test.

## Notes for others (not exploits)
- **N4, for #5 (contract wording):** calls refused by FastMCP's schema check (non-list `actions`, extra arguments, unknown tool) never reach `ToolHost`, so they are not counted and not logged. CONTRACTS says "every call counts". No reward effect: they change nothing and reveal nothing. Either add "calls refused by schema validation are not counted" to CONTRACTS Tools v1, or count them in a FastMCP middleware; the wording change is enough.
- **N5, for #5 / #4:** a rejected action is echoed in full in `last_rejected`. When it holds a list about 100 to 190 levels deep, or `NaN`, the sim steps and logs correctly, but FastMCP cannot serialise the reply and answers `isError: true` ("Error serializing to JSON" or "non-finite float"). The agent sees an error for a tick that did advance. The depth limit is platform dependent: pydantic-core 2.50.4's Windows build stops below 100 levels, while on Linux (CI and the `python:3.12-slim` hospital image) the 120-deep reply serialises, so the depth test is xfail on `win32` only. Only an attacker can trigger it, but an agent that retries after an error would lose a tick. Fix: in `observation.py`, echo only `index`, `reason` and the action's `type`, or replace an action that fails `json.dumps(action, allow_nan=False)` with `"<unprintable>"`.
- **N6, for #4 (latent):** `Simulation.step` runs `apply_actions` (which changes state and emits sim lines) before `copy.deepcopy(actions)` and `json.dumps`. If either raises, the live sim has applied actions that no agent line records and the tick does not move, so the live run and the `collect.py` replay part ways. The HTTP parser blocks every input that triggers it today (depth, integer size), and a desync cannot raise the reward (the replay is an honest run of the logged actions), so this is defence in depth. Fix: build `logged = json.loads(json.dumps(actions, allow_nan=False))` before `apply_actions` and refuse the step with an error if that fails.
