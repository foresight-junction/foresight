# Branch: kostiantyn/env-firewall-node

- **Issue:** #31
- **Owner:** kostiantyn
- **Agent:** kostiantyn-claude-3 (lead)
- **Parent branch:** main
- **Created:** Sat 17:07

## Goal
Make main CI green again: the #31 firewall test rejected #89's `COPY --from=node` (OpenCode runtime). Allow copies only from a public `node:` stage and only Node's install paths. Done when hospital tests pass and main CI is green.

## Files and folders I own
- `ed72/environment/hospital/tests/test_firewall.py` (main-image check only)

## Don't touch
- Everything else (final stop); the Dockerfile from #89 stays as it is

## Contracts used or changed
Anything from docs/CONTRACTS.md this branch depends on or changes.
- None.

## Status
- [x] `_check_main_dockerfile`: `COPY --from=<stage>` only when the stage is `FROM node:<tag> AS <stage>`, and sources only `/usr/local/bin/node` or `/usr/local/lib/node_modules`
- [x] 5 new cases (4 rejected copies, 1 accepted node toolchain); 64 firewall tests, 360 hospital tests pass; ruff clean

## Decisions and notes
Short and dated: why we chose X, new dependencies and why, gotchas.
- Sat 17:15: Kostiantyn said "Yes, fix it" in chat. Kept the guard's purpose: no stage other than a public Node image can feed the agent container.

## Handoff
Done / not done / how to test. Keep this current: another agent may pick it up.
- Done. Test: `cd ed72/environment/hospital && uv run --with pytest pytest -q tests/test_firewall.py`. The integrator merges.
