# Branch: kostiantyn/harness-harborignore

- **Issue:** #22
- **Owner:** kostiantyn
- **Agent:** kostiantyn-claude-3 (lead)
- **Parent branch:** main
- **Created:** Sat 16:56

## Goal
Keep Harbor from rejecting the task after the solution tests ran (#22 P1 from review #88): `ed72/solution/.harborignore` excludes `.venv/`, `__pycache__/`, `.pytest_cache/`. Allowed by Kostiantyn under the final stop (freeze rule a).

## Files and folders I own
- `ed72/solution/.harborignore`, `ed72/solution/tests/test_harborignore.py`

## Don't touch
- Everything else (final stop, #1 16:29)

## Contracts used or changed
Anything from docs/CONTRACTS.md this branch depends on or changes.
- None.

## Status
- [x] `.harborignore` verified with Harbor 0.26.0 `TaskFileFilter`: `.venv/bin/python3` excluded, `solve.sh` kept
- [x] regression test

## Decisions and notes
Short and dated: why we chose X, new dependencies and why, gotchas.
- Sat 16:40: Kostiantyn allowed this one fix in chat ("Allow the fix"); #83 stays deferred and documented.

## Handoff
Done / not done / how to test. Keep this current: another agent may pick it up.
- Done. Test: `cd ed72/solution && uv run --with pytest pytest -q`, then `make eval-baselines` still runs. The integrator merges.
