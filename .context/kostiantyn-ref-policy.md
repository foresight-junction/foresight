# Branch: kostiantyn/ref-policy

- **Issue:** #16
- **Owner:** kostiantyn
- **Agent:** kostiantyn-codex-16
- **Parent branch:** main

## Goal
Deterministic 144-tick reference policy using only public ward tools.

## Files and folders I own
- ed72/solution/**
- .context/kostiantyn-ref-policy.md

## Don't touch
- Simulator, world, scorer, tool server, handbook, Dockerfiles and shared docs.

## Contracts used or changed
- Uses v1 rules(), observe(), step(actions), Observation and Action. No changes.

## Status
- [x] Policy, public runner and shared baseline API implemented and pushed.
- [x] 22 contract tests; canonical ordering and deterministic real-engine checks pass.
- [x] Claude LGTM and independent coordinating Codex review; PR #76 opened with baseline table.
- [ ] Attach actual Harbor triple-repeat proof, then integrator merges.

## Decisions and notes
- Standard library only. Fixtures stay in tests; production has no mock mode.
- Local repair/warning state prevents repeated purchases. Public prices/rates match the rulebook.
- Agency hires are capped by the two warning keys; maximum 8 hires. No production privileged imports.
- Accept legacy plain-text rules and approved JSON rules; observe/step require JSON.

## Handoff
- PR #76 at https://github.com/xand1ex999/guinness/pull/76; API ed72_reference.ReferencePolicy.act(obs), also policy.ReferencePolicy.actions(obs).
- Run `uv run --with pytest pytest -q` in ed72/solution. CPython 3.12 and 3.13 checks pass. Ruff, shell and secrets gates pass.
- Canonical baseline checks: 79 passed; combined hospital/canonical: 374 passed, 4 skipped. Shipped-seed reference scores 99.423 / 99.293 / 99.726, above every supplied exploit. Full table is in the PR.
- Real-engine seeds 1-5 each repeat three identical full score objects with zero rejected actions. Rewards .994228/.992931/.997263/.990893/.970795; nop is 0 throughout; max 26 actions, no faints, one death on seed 5.
- Root runs three real Harbor trials on immutable snapshots including reference 5264305 + #57 server + #58 packaging + #7 handbook. Await actual artifacts; fixture/in-process passes do not prove Harbor acceptance.
- #58 packaging and #77 tuning leads have the adapter/API handoff. Code work is complete; worktree is available after this handoff. Existing owners finish Harbor proof and integrator readiness; no new tasks per user steering.
- Literal `codex review --uncommitted` completed successfully: all 22 tests pass, no actionable defects. Coordinating Codex reviewer approved the final adapter; Claude final review was LGTM.
