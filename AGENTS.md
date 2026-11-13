# AGENTS.md

Read this whole file before doing anything. It applies to every agent (Claude Code, Codex, their subagents) and every human on the team. About 10 agents work on this repo at once from 4 laptops, so these rules exist to stop agents overwriting each other, breaking `main`, or shipping slop.

## 1. Project

- **Name / one-liner:** TODO (fill in at kickoff)
- **Junction challenge:** TODO
- **Stack:** React + TypeScript (Vite) in `frontend/`, FastAPI (Python 3.12, uv) in `backend/`. TODO: confirm at kickoff.
- **Run it:**
  - Frontend: `cd frontend && pnpm dev` (http://localhost:5173)
  - Backend: `cd backend && uv run uvicorn app.main:app --reload --port 8000`
- **Integrator** (the human who merges PRs into `main`): TODO
- **Team:**

| Person | Areas | Agents (ids) |
|---|---|---|
| yehor | TODO | yehor-claude-1, yehor-codex-1 |
| TODO | TODO | TODO |
| TODO | TODO | TODO |
| TODO | TODO | TODO |

## 2. Golden rules

1. **One task = one GitHub issue = one branch = one worktree = one lead agent.** Never work on `main`. Never let two agents work in the same worktree.
2. **Claim before you code.** Use the `claim-task` skill. If the issue is already claimed, pick another one.
3. **Stay inside the files your task owns** (listed in your branch context file). To change a file another task owns, comment on that task's issue first.
4. **Contracts are sacred.** Anything in `docs/CONTRACTS.md` changes only through the `contract-change` skill.
5. **Commit small and often:** every time something works, and at least every 30 minutes. Every commit goes through the `pre-commit-gate` skill. Push after each commit.
6. **Get into `main` early:** open a PR (the `ship-pr` skill) as soon as a slice works end to end. Aim for under 300 changed lines per PR and at least one merge every 2 hours per task.
7. **No secrets in git.** Keys go in `.env` (gitignored). Add the variable name to `.env.example`.
8. **Agents never merge into `main`, force-push, delete branches, or rewrite history** on shared branches. Humans merge.
9. **Demo first.** Mock or hardcode before building real infrastructure. Happy path before edge cases. Label every mock clearly (section 7).
10. **Don't guess APIs.** Before using a library function, check that it exists in the installed version (read the package source or docs). Hallucinated APIs are the most common cause of lost time.

## 3. Skills (shared by every agent)

Team skills live in `.agents/skills/` (Codex reads them there; `.claude/skills` points to the same folder for Claude). **Use them every time they apply. They aren't optional.**

| Skill | Use it when |
|---|---|
| `claim-task` | Starting any work: find, claim, or create the issue |
| `noslop` | After writing any code or user-facing text, before committing |
| `pre-commit-gate` | Before **every** commit |
| `cross-review` | Before every PR, and when stuck on a bug after 2 failed fixes |
| `ship-pr` | When a slice works and should go into `main` (or into your parent branch) |
| `contract-change` | Before changing an API route, data shape, env var, or anything in `docs/CONTRACTS.md` |

Tool-specific extras are in `CLAUDE.md` (Claude) and section 9 (Codex).

## 4. Task board: GitHub Issues

All 10 agents are on different laptops, so **GitHub Issues is the single source of truth** for who is doing what.

- **Labels:** status (`todo`, `doing`, `review`, `blocked`), area (`area:fe`, `area:api`, `area:data`, `area:ai`, `area:infra`, `area:docs`), plus `contract`.
- **See the board:** `scripts/wt.sh board`
- **Messages between agents** are issue comments. Start every comment with your agent id: `[yehor-claude-1] ...`. To reach another task, comment on **its** issue.
- **Check for messages** on your issue at the start of each work session and before each PR: `gh issue view <n> --comments`.
- Issue **#1 "Contracts"** is pinned. Contract proposals go there.

## 5. Worktrees and branches

Folder layout on each laptop:

```
~/Dev/Hackathons/Junction/        (Yehor's laptop; any folder works, same shape)
  <repo>/                  main checkout. Stays on main. Only for pulling and merging.
  <repo>--<slug>/          one worktree per task (made by scripts/wt.sh)
```

Always create worktrees with the script, so the branch, context file and issue link are set up:

```bash
scripts/wt.sh init                                   # once per laptop, after cloning
scripts/wt.sh new <owner> <area> <task> -i <issue>   # e.g. scripts/wt.sh new yehor api auth -i 12
scripts/wt.sh new <owner> <area> <task> <agent>      # helper branch off an existing task, e.g. for Codex
scripts/wt.sh list
scripts/wt.sh board
scripts/wt.sh done <slug>                            # removes the folder, keeps the branch
```

**Branch names:** `<owner>/<area>-<task>`, lowercase, hyphens only, e.g. `yehor/api-auth`.
Helper branches add `--<agent>`: `yehor/api-auth--codex`. They are PR'd into their parent branch, never into `main`.

**Agent ids:** `<owner>-<tool>-<n>`, e.g. `yehor-claude-1`. Subagents add a letter: `yehor-claude-1a`.

## 6. Branch context file

Every branch has `.context/<branch-slug>.md` (created by `wt.sh`). It is committed with the branch, so teammates and later agents can pick up the work.

- **Read it** before starting work in a worktree.
- **Update it** when you finish a step, make a decision, add a dependency, or change scope.
- **Keep it short:** it's a handover note, not a diary. The **Handoff** section must always say what's done, what's next, and how to test it.

The file name is unique per branch, so these files never conflict on merge.

## 7. Code conventions

**General**
- Write the simplest code that works. Match the style of the code around you. Search the codebase before writing a helper, because it may already exist.
- Comments explain *why*, never *what*. No commented-out code.
- No new dependency without a one-line reason in your context file.
- Env vars: `UPPER_SNAKE_CASE`, all listed in `.env.example`.
- **Mocks:** any fake data or stubbed call gets a `MOCK:` comment and lives behind one flag (`USE_MOCKS=1` in `.env`), so the demo can switch to real data in one place.
- Errors: fail loudly in development. Don't swallow exceptions or return fake success.

**Backend (Python)**
- `uvx ruff format . && uvx ruff check --fix .`
- Type hints on every function. `snake_case`.
- Routes in `backend/app/routers/<area>.py`. Pydantic models in `backend/app/schemas.py`.
- All LLM calls go through `backend/app/llm.py`, so models, keys and prompts live in one place.

**Frontend (TypeScript)**
- Components in `frontend/src/components/` as `PascalCase.tsx`. Hooks in `frontend/src/hooks/useThing.ts`.
- All backend calls go through `frontend/src/api.ts`. Shared types live in `frontend/src/types.ts`, mirroring `docs/CONTRACTS.md`.
- `pnpm lint && pnpm prettier --write .`

**Commits** (Conventional Commits):

```
<type>(<area>): <what changed, present tense, under 60 chars>

Refs #<issue>
Agent: <agent id>
```

Types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`. Example: `feat(api): add POST /events endpoint`

## 8. Definition of done

A task is done only when:
- [ ] `pre-commit-gate` passes, and CI is green on the PR
- [ ] The demo path for this feature works by hand
- [ ] `cross-review` is done and real issues are fixed
- [ ] The context file's **Handoff** section is up to date
- [ ] The PR is open with `Closes #<issue>`, and the issue is labelled `review`

## 9. If you are Codex

- Skills are in `.agents/skills/`. Invoke one by name (e.g. `$pre-commit-gate`) or let it trigger from its description.
- Use `/review` on your diff before shipping, in addition to `cross-review`.
- If Claude called you through MCP, do only the task you were given, in the folder you were given (`cwd`). Don't claim other issues, open PRs to `main`, or edit outside that folder. Finish with a short summary: files changed, what you ran, and anything left undone.
