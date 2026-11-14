# GEMINI.md

Before doing anything, read `AGENTS.md` in full and follow it. It applies to you exactly as it does to Claude Code and Codex. This file only adds what is specific to Gemini CLI.

## Your role
- Same as any lead agent: one issue, one branch, one worktree (`scripts/wt.sh new <owner> <area> <task> -i <issue>`). Pick tasks in the order of issue #39, with wave 0 (#41) first, as AGENTS.md section 4 says.
- Your agent id is `<owner>-gemini-<n>`, e.g. `yehor-gemini-1`. Start every issue comment and commit trailer with it.

## Skills
The team skills are in `.agents/skills/<name>/SKILL.md`. Gemini CLI does not load them for you, so when AGENTS.md section 3 says a skill applies, open that file and follow its steps in order:

| When | Read and follow |
|---|---|
| Starting any task | `.agents/skills/claim-task/SKILL.md` |
| After writing code or text | `.agents/skills/noslop/SKILL.md` |
| Before every commit | `.agents/skills/pre-commit-gate/SKILL.md` |
| Before every PR | `.agents/skills/cross-review/SKILL.md` |
| Opening a PR | `.agents/skills/ship-pr/SKILL.md` |
| Changing anything in `docs/CONTRACTS.md` | `.agents/skills/contract-change/SKILL.md` |

## Cross-review
Your reviewer is Claude or Codex, never yourself. Use the commands under "If you are Gemini" in the cross-review skill.
