# Branch: yehor/reward-baselines

- **Issue:** #12
- **Owner:** yehor
- **Agent:** yehor-claude-3b
- **Parent branch:** main
- **Created:** Sat 16:52

## Goal
Scripted baselines (rulebook §12) and exploit probes (§13) that play over the public tools only, plus the CI ordering test. Done when the score table is in the PR and the ordering test runs in CI.

## Files and folders I own
- `eval/baselines/` (stdlib-only uv project `ed72-baselines`)
- `ed72/environment/hospital/ed72_sim/scoring/tests/test_baselines.py`

## Don't touch
- `ed72/environment/hospital/` everything else (#4, #10, #11, #21, #22, #31), `ed72/solution/` (#16), `Makefile`, `eval/run_all.sh`, `eval/summarise.py` (#23)

## Contracts used or changed
- Uses CONTRACTS v1 (PR #43): `rules` / `observe` / `step(actions)`, Action, ActionResult, Observation, the 500-call cap, score object `score`. Changes nothing.
- Assumed sim/scorer API (same as collect.py on #11): `Simulation(generate_world(seed))`, `.observe()`, `.step(actions)`, `.run_to_end()`, `.events`; `ed72_sim.scoring.score(events)`.
- Assumed reference (#16): module `ed72_reference` in `ed72/solution/`, class `ReferencePolicy` with `act(obs) -> list[Action] | None`.

## Status
- [x] Client/Policy protocol + `run_episode` (`client.py`)
- [x] Built-ins: reactive_proxy, stop_early, do_nothing (`policies.py`)
- [x] Exploits: divert_all, rest_in_quiet_periods, admit_light_only, admit_without_coverage, fill_beds_at_last_tick, spend_to_limit, random (`exploits.py`)
- [x] Unit tests against MOCK fake client (27 pass)
- [x] Ordering test split into three tiers: sim only (runs on main now), needs scorer #47 (skips), needs reference #16 (skips)
- [x] Merged main after #44, #46, #48 landed; table unchanged on main + scorer overlay
- [ ] After #47 and #16 merge: rerun, add the reference row to the table

## Decisions and notes
- Sat 17:00: the reactive proxy returns staff from rest to their post at fatigue <= 30 (the rulebook fixes only the 85). Rest happens at observed fatigue >= 85, so with gains of 1.6 to 2.2 per tick nobody reaches 90: the proxy never faints in the real sim. W still drops to about 0.7 from time spent above 60.
- Exploit probes are `SeverityPolicy` plus one shortcut. SeverityPolicy is a simple honest player (severity-first, resus kept for ESI 1-2, demand-based least-tired staffing, repair within budget). It scores 97 to 99 on seeds 1-3, which suggests the default knobs are too easy (flag for #8).
- Divert-all measures 44.7 / 48.1 / 46.7, so the cap is 50 ("about 47").
- The hospital pyproject has `testpaths = ["tests"]`, so `pytest -q` there will not collect `ed72_sim/scoring/tests/`. So `eval/baselines/pyproject.toml` also lists that folder in its testpaths, and CI runs the ordering test from the baselines project (the test puts the hospital dir on sys.path). Asked #4 to add it to the hospital testpaths too; still `["tests"]` on main at Sat 17:25, so the workaround stays.
- Sat 17:15: Codex CLI cross-review found admit_light_only reserving beds for severe cases it then dropped; fixed (filter waiting first). admit_light_only now 10.6 / 13.0 / 12.4.
- Sat 17:25: #16 branch `kostiantyn/ref-policy` has only an empty context file, so `REFERENCE_MODULE = "ed72_reference"` is still a guess and the reference checks skip. `kostiantyn/env-difficulty` `config/default.json` equals the constants, so the table does not change.

## Handoff
- Done: baselines, unit tests, ordering test. PR #52 ready for review; Kostiantyn merges (after #47).
- Test: `cd eval/baselines && uv run --with pytest pytest -q`. On main today: 73 passed (27 unit + 46 sim-only ordering checks), 33 skipped (scorer not on main). With #47 overlaid: 82 passed, 24 skipped (reference).
- Table: `cd eval/baselines && PYTHONPATH=../../ed72/environment/hospital uv run python -m ed72_baselines.table 1 2 3` (needs the scorer).
- Next: when #16 lands, set `REFERENCE_MODULE` (and class name) in `test_baselines.py` to match, rerun, paste the table with the reference row.
