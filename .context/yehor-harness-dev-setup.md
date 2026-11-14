# Branch: yehor/harness-dev-setup

- **Issue:** #30
- **Owner:** yehor
- **Agent:** yehor-claude-2 (lead), subagents 2a, 2b
- **Parent branch:** main
- **Created:** Sat 15:11

## Goal
Make the team workflow match the ED-72 layout so lanes can build fast. Works when no skill or script step names a folder that does not exist (`backend/`, `frontend/`, pnpm).

## Files and folders I own
- `.agents/skills/pre-commit-gate/SKILL.md`, `.agents/skills/contract-change/SKILL.md`, `.agents/skills/cross-review/SKILL.md` (subagent 2a)
- `scripts/wt.sh`, `.env.example` (new), `.gitignore` (subagent 2b)
- `.github/workflows/ci.yml` (subagent 2c, task D4 #24), `ruff.toml` (new) (lead)
- `AGENTS.md` (sections 1 and 7 only), `.context/yehor-docs-ed-pivot.md` (handoff line) (lead)
- `docs/ED_Management_Simulator_RU.md` (new, verbatim copy of Denys's rules doc) (lead)

## Don't touch
- `docs/` except the new rules doc, `scripts/bootstrap-board.sh`, the issue board (Kostiantyn sets it up)

## Contracts used or changed
- None changed. `.env.example` lists the env vars already in docs/CONTRACTS.md.

## Status
- [x] Issue #30 created and claimed, worktree made
- [x] Skills, wt.sh, .env.example, .gitignore retargeted by two Sonnet subagents
- [x] AGENTS.md says where Python lives and how to lint and test
- [x] Denys's rules doc added as docs/ED_Management_Simulator_RU.md; AGENTS.md names it the source of truth
- [x] Tooling supports both layouts: Kostiantyn's `backend/` + `frontend/` (branch `kostiantyn/env-ed-sim`) and SPEC's `ed72/`
- [x] CI simulated on this branch and on Kostiantyn's tree: ruff clean, backend 134 passed, bash -n ok
- [ ] Push, PR, squash-merge (Yehor OK'd, Sat 15:45)
- Realigning SPEC, CONTRACTS, PLAN, EVAL and the issues to the RU doc is left to Kostiantyn, who sets up the board

## Decisions and notes
- Sat 15:15. One uv project for sim, tools and scorer at `ed72/environment/hospital/`, matching docs/SPEC.md section 9. Other Python folders get their own pyproject if they need one.
- Sat 15:15. Cross-review is deferred for this PR at Yehor's request; it only changes workflow docs and scripts.

- Sat 15:30. Yehor: the team builds mainly from ED_Management_Simulator_RU.md. It conflicts with the PR #29 docs (30-min ticks vs 15, 17 beds vs 15, 5 actions vs ~20 tools, full observation vs hidden triage errors, W and B scored vs harm-only). AGENTS.md says the RU doc wins until the other docs are updated.

- Sat 15:45. CI moved into this branch (one PR, Refs #24). The local branch `yehor/harness-ci` was never pushed and is superseded.
- Sat 15:45. Root `ruff.toml` (line length 110, as in backend/pyproject.toml) excludes `spikes/` and `harbor/unfindable/`: all 21 lint errors and 16 format diffs on Kostiantyn's branch were there.
- Sat 15:45. Local pnpm 12 rejects Kostiantyn's lockfile (minimumReleaseAge: eslint 10.15.0, postcss 8.5.33, @eslint/config-array published Fri night). CI pins pnpm 10. Clears by itself about Sat 23:00 UTC.

## Handoff
- Done: see Status.
- How to test: `bash -n scripts/wt.sh`; `uvx ruff check . && uvx ruff format --check .` from the root; open a PR and CI runs ruff, pytest per uv project, bash -n and the frontend checks.
