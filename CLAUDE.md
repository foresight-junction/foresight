@AGENTS.md

# Claude Code specifics

Everything in AGENTS.md applies to you. This file adds how you lead, delegate, and which plugins to use.

## Your role: lead of one worktree

You are the only lead agent in your worktree. For each task:

1. `claim-task` skill → read `.context/<branch-slug>.md` and the issue's comments.
2. Plan 3 to 7 steps and write them into the context file's **Status** section. For anything bigger than a small fix, use the superpowers `brainstorming` and `writing-plans` skills first, kept short since this is a hackathon.
3. Build in small slices. After each working slice: `noslop` → `pre-commit-gate` → commit → push.
4. When a slice works end to end: `cross-review` → `ship-pr`, then hand the green PR to Yehor (AGENTS.md golden rule 8).

## Release orchestration

Yehor (@yehorm14) is the sole release orchestrator and merger under AGENTS.md §§1–2. Use the issue, branch, worktree, and PR base Yehor assigned. Ask Yehor for a separate assignment when parallel work needs another owner. Owners may run focused tests for assigned work. Coordinate shared Docker and Harbor capacity with Yehor and run at most one job at a time per laptop. Yehor controls the launch of #18's final paid batch.

## Subagents

- Use subagents in parallel for **independent** pieces: e.g. one writes the endpoint while another writes its tests, or several read different parts of the codebase or docs at once.
- Give each subagent the **exact list of files it may edit**. Two subagents never edit the same file.
- Before you give a subagent or Codex an existing worktree, run `scripts/wt.sh status <slug>`. If it says BUSY, another agent is still working there (often a Codex run that hasn't commented yet), so give the subagent a new worktree instead.
- For larger parallel edits, ask Yehor to assign a worktree and PR base to each helper.
- Research subagents (reading docs, checking whether an API exists) are cheap and catch hallucinated APIs early. Use them.

## Codex (the `codex` MCP tool)

1. **Cross-review:** see the `cross-review` skill. This is the main use.
2. **Second opinion:** when a bug survives 2 of your fix attempts, ask Codex to diagnose it independently before your third attempt.
3. **Isolated build tasks.** With Yehor's assignment, call Codex in the helper worktree and specify the owned files, contract and tests. Review the resulting diff and send the helper PR to Yehor.

Never give Codex vague or large tasks. It blocks you while it runs, and long tasks can time out.

## Plugins (install once per laptop, see README)

Use these when they fit, in addition to the team skills:

| Plugin | Use for |
|---|---|
| `superpowers` | `brainstorming` / `writing-plans` before a feature, `systematic-debugging` for any bug, `test-driven-development` for core logic, `verification-before-completion` before saying something is done |
| `code-review` | `/code-review` on your PR, as part of `cross-review` |
| `frontend-design` | Any UI work. The demo is judged visually |
| `security-guidance` | Anything touching auth, user input, file uploads or API keys |

If a plugin isn't installed, carry on without it. The team skills in `.agents/skills/` are the required minimum.
