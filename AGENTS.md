# AGENTS.md

Read this whole file before doing anything. It applies to every agent (Claude Code, Codex, their subagents) and every human on the team. About 10 agents work on this repo at once from 4 laptops, so these rules exist to stop agents overwriting each other, breaking `main`, or shipping slop.

## 1. Project

- **Name / one-liner:** **Custodian.** An RL environment where an agent works one shift as the data custodian of a registry holding records about vulnerable people, and must decide who gets which fields.
- **Junction challenge:** Break the Agent (AfterQuery). Deadline **Sun 15 Nov 10:00**.
- **Read these before any task:** `docs/CHALLENGE.md` (brief, rubric, required stack), `docs/SPEC.md` (the environment), `docs/CONTRACTS.md` (tool and score shapes, who owns which folder), `docs/PLAN.md` (lanes, timeline, tasks).
- **Stack:** a Harbor task in `custodian/`. Python 3.12 with uv. A `registry` sidecar container holds the simulator, the scorer and the tool server (MCP). The agent harness is OpenCode. Docker is required. There is no frontend and no web backend.
- **Run it:**
  - Reference run: `harbor run -p custodian -a oracle`
  - Do-nothing baseline: `harbor run -p custodian -a nop`
  - Agent run: `harbor run -p custodian -a opencode -m <provider/model>`
  - Everything judges will rerun: `make eval`
- **Integrator** (the human who merges PRs into `main`): TODO (lane D owner)
- **Team:** one lane per person. Lanes are defined in `docs/PLAN.md`.

| Person | Lane | Label | Agents (ids) |
|---|---|---|---|
| TODO | A. World and tools | `area:env` | TODO |
| TODO | B. Reward and integrity | `area:reward` | TODO |
| TODO | C. Reference and experiments | `area:ref` | TODO |
| TODO | D. Harness, repro and story | `area:harness`, `area:train` | TODO |

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

- **Labels:** status (`todo`, `doing`, `review`, `blocked`), area (`area:env`, `area:reward`, `area:ref`, `area:harness`, `area:train`, `area:docs`), priority (`p0` thin slice by Sat 16:00, `p1` needed to submit, `p2` only if time), plus `contract`.
- **Issue titles** start with a task code from `docs/PLAN.md`, e.g. `[env] A2: Sim core`. Take `p0` before `p1`, and never start a `p2` while a `p0` in your lane is open.
- **Create the board:** `scripts/bootstrap-board.sh` (once, by a human).
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
scripts/wt.sh new <owner> <area> <task> -i <issue>   # e.g. scripts/wt.sh new yehor env world -i 3
scripts/wt.sh new <owner> <area> <task> <agent>      # helper branch off an existing task, e.g. for Codex
scripts/wt.sh list
scripts/wt.sh board
scripts/wt.sh done <slug>                            # removes the folder, keeps the branch
```

**Branch names:** `<owner>/<area>-<task>`, lowercase, hyphens only, e.g. `yehor/env-world`.
Helper branches add `--<agent>`: `yehor/env-world--codex`. They are PR'd into their parent branch, never into `main`.

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

**Python (everything in this repo)**
- `uvx ruff format . && uvx ruff check --fix .`
- Type hints on every function. `snake_case`. Standard library first: the registry image should stay small and build fast.
- Simulator and scorer are pure and deterministic: all randomness comes from one seeded `random.Random` passed in, never the global `random`, never wall-clock time, never the network.
- Core logic (world, sim, scorer) gets pytest tests in the same PR. Use the `test-driven-development` skill for the scorer.
- Shell scripts Harbor runs (`tests/test.sh`, `solution/solve.sh`) use absolute paths and `set -u`.

**Commits** (Conventional Commits):

```
<type>(<area>): <what changed, present tense, under 60 chars>

Refs #<issue>
Agent: <agent id>
```

Types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`. Example: `feat(env): add verify_requester tool`

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


## 10. Rules for this challenge (they override habits from web projects)

Judges rerun our code and spend 15 minutes trying to cheat the reward. These rules protect the score.

1. **Nothing that reveals the answer goes into the agent's container.** The `main` image holds the handbook and the `desk` CLI only. Seeds, ground truth, the event log, sim source and the scorer live in the `registry` image.
2. **The reward is computed from the registry's event log only.** Never from files the agent can write. No LLM judge anywhere in the reward.
3. **No hidden rules.** A rule the scorer applies must be written in `HANDBOOK.md` in the same PR. If the agent cannot find out, it is unfair, and unfair difficulty scores zero on 30 points.
4. **The reference policy uses only the public tools.** It never reads the seed or ground truth. If it cannot decide a ticket, fix the environment.
5. **These must hold after every merge:** reference >= 0.9, do-nothing = 0, deny-all / approve-all / escalate-all / random <= 0.05, same seed and actions give the same score. Any PR touching `scoring/`, tickets or tool behaviour pastes the baseline table in its description.
6. **`tests/test.sh` always writes a number** to `/logs/verifier/reward.txt`, 0 on any error.
7. **Synthetic data only.** Invented names and records. Never copy real personal data into the repo, a prompt or a test.
8. **Rules freeze Sat 21:00.** After that: bug fixes and knob tuning only. No code changes after Sun 09:00.
9. **Don't force the gap.** If the agent does well, raise difficulty through the knobs in `docs/SPEC.md` section 7. No trick wording, no impossible deadlines, no broken tools.
10. **Model keys** come from the environment (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`). Agent runs cost real money: lane C runs the full matrix, others run one seed.
