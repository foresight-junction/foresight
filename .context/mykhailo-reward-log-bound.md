# Branch: mykhailo/reward-log-bound

- **Issue:** #14
- **Owner:** mykhailo
- **Agent:** mykhailo-claude-1m
- **Parent branch:** main

## Goal
Bound the bytes a refused tool call adds to the event log without changing replay or reward.

## Files and folders I own
- ed72/environment/hospital/server.py, tests/test_log_bounds.py, docs/REDTEAM.md (append only)

## Don't touch
- engine, scorer, collect.py, CONTRACTS

## Contracts used or changed
- Tools v1, Event log: unchanged (post-cap lines keep their shape, args is `{}`).

## Status
- [x] Sanitise refused step args; `args: {}` past the cap
- [x] Tests, REDTEAM note
- [x] Round 2 dispositions: successful steps now pass only CONTRACTS fields to the sim (fixes 4 MiB lines and N5)

## Decisions and notes
- Past-cap lines keep one line per call so `tool_calls` stays len(agent lines).

## Handoff
Done. Test: `cd ed72/environment/hospital && uv run --python 3.12 --with pytest pytest -q`.
