# Branch: kostiantyn/ref-policy

- **Issue:** #16
- **Owner:** kostiantyn
- **Agent:** kostiantyn-codex-16
- **Parent branch:** main

## Goal
Deterministic 144-tick reference policy using the public ward tools, with tested admission, staffing and event preparation.

## Files and folders I own
- ed72/solution/**
- .context/kostiantyn-ref-policy.md

## Don't touch
- Simulator, world, scorer, tools/server, handbook, Dockerfiles and shared docs.

## Contracts used or changed
- Uses v1 rules(), observe(), step(actions), Observation and Action. No changes.

## Status
- [x] Confirm claim and create isolated worktree through wt.sh.
- [x] Implement deterministic decisions and public ward runner.
- [x] Test fixtures and independent real-engine integration.
- [ ] Run noslop, gates, Claude/Codex reviews, push and open PR.

## Decisions and notes
- 14 Nov: owner authorizes starting with stub dependencies; full integration acceptance stays in scope.
- Standard library only. Test fixtures are test-only and never served by production code.
- Track issued CT repair and warning hires locally because the public observation has no pending repair flag.
- Upstream world/engine/scorer are read-only inputs to independent integration checks, never production imports.

## Handoff
- Implemented public ward runner, weighted staffing/admission policy, one-shot warning hires and CT repair.
- 20 contract tests pass; own solution uv project makes CI discover them. Run `uv run --with pytest pytest -q` in ed72/solution (or `python -m unittest discover -s tests -v` there).
- Real integration (read-only engine bd3daf8, world a999ab2, scorer ba5e0f5): seeds 1-5, three identical score objects each, no rejected actions. Rewards 0.994228 / 0.992931 / 0.997263 / 0.990893 / 0.970795; nop is 0 throughout. Max 26 actions; no faints; one death on seed 5.
- Claude round 1: reserve one Resus bed, name/source public constants, preserve ward process diagnostics and add tests; fixed. The >50-action finding is unreachable for this policy's 15 permanent + at most 8 hired staff and 17 beds (maximum 45 including purchases); retained loud guard. Claude's lead-id objection was mistaken: lead is Codex 16.
- Independent Codex review by root found no substantive defects. Claude final review: LGTM; low-risk timeout/encoding suggestions deferred.
- Harbor oracle triple-repeat and the canonical reactive/stop-early/divert baseline comparison remain pending packaging/integration. Do not treat fixture passes as those acceptance checks.