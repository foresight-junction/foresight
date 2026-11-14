# Branch: kostiantyn/env-difficulty

- **Issue:** #8
- **Owner:** kostiantyn
- **Agent:** kostiantyn-claude-2i
- **Parent branch:** main

## Goal
One JSON file of difficulty knobs (SPEC §7) loaded via `ED72_CONFIG`. This PR adds the mechanism with today's values as defaults and changes no rule numbers; tuning waits for the reference (#16) and baselines (#12).

## Files I own
- `ed72/environment/hospital/ed72_sim/config.py`, `config/default.json`, `tests/test_config.py`
- `world.py` (accepts a config), `collect.py` (loads it), `tests/test_collect.py` (fake `generate_world` takes the new argument)

## Don't touch
- constants.py, engine.py, scoring/

## Contracts used or changed
- `ED72_CONFIG` (hospital only) already exists in CONTRACTS. No change.

## Status
- [x] Config dataclass and strict `load_config`
- [x] `generate_world(seed, config)` bit-identical with defaults
- [x] collect.py loads the config
- [x] default.json plus tests (147 pass)
- [ ] Server (#5) and HANDBOOK (#7) adopt the config (commented on both issues)

## Decisions and notes
- Knobs: arrival mean/amplitude/peak hour, flu and bus severity mix, per-event window/duration/warning, budget, hard limit. A file may override single event fields.
- W weights are not knobs yet: scoring/ is not mine.

## Handoff
Done: everything above. Next: #5 must build the world with `load_config(os.environ.get("ED72_CONFIG"))`; #7 must print the active values. Test: `cd ed72/environment/hospital && python -m pytest -q`.
