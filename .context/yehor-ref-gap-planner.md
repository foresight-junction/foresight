# Branch: yehor/ref-gap-planner

- **Issue:** #69
- **Owner:** yehor
- **Agent:** lead
- **Parent branch:** main
- **Created:** Sat 21:57

## Goal
Give ED-72 a real model gap: Kimi K3.1 Pro scored 0.9876 against the oracle's 0.9896 at arrival mean 3.0. Move the default to 4.0 and make the reference plan for scarce doctor time. Works when the reference stays above 88 on seeds 42 and 1–5 and a model run lands clearly below it.

## Files and folders I own
- `ed72/solution/policy.py`
- `ed72/environment/hospital/ed72_sim/constants.py` (`ARRIVAL_MEAN` only), `ed72/environment/hospital/config/default.json`
- `ed72/environment/workspace/HANDBOOK.md` (the arrival mean in section 5 only)
- `docs/TUNING.md` (the update section), the reference and arrival lines in `docs/SPEC.md` and `docs/EVAL.md`

## Don't touch
- Scorer, tools, observation, event log, other knobs.

## Contracts used or changed
- None changed. `arrival_mean` is a SPEC section 7 knob.

## Status
- [x] Found the cause: fatigue and budget never bind at 3.0 (max fatigue 31, spend €7 000)
- [x] Reference keeps staff fresh and hires on backlog
- [x] Default 4.0 in constants, config, handbook, SPEC; baseline table in `docs/TUNING.md`
- [ ] One model run at 4.0 (needs the model key, which the agent session did not have)
- [ ] Kostiantyn's decision on the value; README results table re-measured after it

## Decisions and notes
- Sat 22:40: 4.0 over 3.8. The reference holds 92.0 (84–95) on twelve seeds at 4.0 and the previous reference drops to 60.6; at 4.2 the reference itself starts losing seeds.
- Sat 22:40: warning-based hiring stays, so the existing reference tests are unchanged.
- No new dependency.

## Handoff
- Done: policy, default, handbook, docs, tests green in every uv project.
- Not done: a model run at 4.0; README results (oracle, Gemini) still describe 3.0 runs except where the PR says otherwise.
- Test: `cd ed72/solution && uv run --with pytest pytest -q`; `cd ed72/environment/hospital && uv run --with pytest pytest -q`; `make eval-baselines`; agent run: `harbor run -p ed72 -a opencode -m <provider/model>`.
