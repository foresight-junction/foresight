---
name: pre-commit-gate
description: Required checks before every git commit in this repo. Use whenever you are about to commit, or are asked to commit, save progress or push.
---

# pre-commit-gate

Run these steps in order. If any step fails, fix the problem and start again from step 1. Never use `--no-verify` and never skip a step.

## 1. Check what's staged
```bash
git add -A
git status --short
git diff --staged --stat
```
- Every changed file must be one your task owns (see `.context/<branch-slug>.md`). Unstage anything else with `git restore --staged <file>` and comment on the owning task's issue instead.
- Nothing generated or local should be staged: `.venv`, `__pycache__`, `.env`, `.DS_Store`, large data files, Harbor run output.

## 2. Secrets scan
```bash
git diff --staged | grep -nEi '(sk-[a-z0-9_-]{16,}|sk-ant-[a-z0-9_-]{16,}|ghp_[a-z0-9]{20,}|AKIA[0-9A-Z]{16}|(api[_-]?key|secret|password|token)["'"'"' ]*[:=] *["'"'"'][^"'"'"' ]{8,})'
```
Any match → **stop**. Move the value to `.env`, add the name to `.env.example`, and unstage.

## 3. noslop
Run the `noslop` skill on the staged changes.

## 4. Format and lint (only for the parts you changed)
- Python, from the repo root (settings in `ruff.toml` and each project's `pyproject.toml`):
  `uvx ruff format . && uvx ruff check --fix .`
- Frontend: `cd frontend && pnpm prettier --write src && pnpm lint`

Re-stage after formatting: `git add -A`.

## 5. It still runs
- For every folder you changed that has its own `pyproject.toml` (today `backend/`; later `ed72/environment/hospital/`, `eval/`, `analysis/`, `training/`):
  `cd <folder> && uv run --with pytest pytest -q` (exit code 5 means no tests were collected, which is fine).
- Frontend: `cd frontend && pnpm build && pnpm test`
- For every changed `.sh` file: `bash -n <file>`.

## 6. Contracts
If you changed a tool name or its args/result shape, the score object, an event-log line, an env var or a port: `docs/CONTRACTS.md` must be updated **in this same commit**, and you must have followed the `contract-change` skill. If not, stop and do that first.

If you changed a rule the scorer applies or a sim rate, the agent-visible rules (`HANDBOOK.md` or the rules tool) and `docs/SPEC.md` must be updated in the same PR (AGENTS.md rule 10.3).

## 7. Context file
Update `.context/<branch-slug>.md` (Status, and any new decisions) and stage it.

## 8. Commit and push
```bash
git commit -m "<type>(<area>): <summary>" -m "Refs #<issue>" -m "Agent: <your agent id>"
git push -u origin HEAD
```
