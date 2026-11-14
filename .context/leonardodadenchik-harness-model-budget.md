# Branch: leonardodadenchik/harness-model-budget

- **Issue:** #37
- **Owner:** leonardodadenchik
- **Agent:** leonardodadenchik-claude-1 (lead)
- **Parent branch:** main
- **Created:** Sat 14:40

## Goal
Provider commands, a measured token, time and cost budget per ED-72 run, timeout and call-cap recommendations, and a go/no-go on preinstalling OpenCode. Works when the provider table has two rows verified by real runs and section 2–4 numbers come from a measured 24 h and 72 h run.

## Files and folders I own
- `eval/budget/` (measurements.md, estimate.py, obs_tokens.py, raw run JSON)
- `.env.example` (variable names only)
- A new section in `docs/HARBOR-NOTES.md` once #21 merges it (append only)

## Don't touch
- `ed72/task.toml`, `ed72/environment/Dockerfile` (#22): propose changes on #22
- `eval/` runner files (#23), `docs/CONTRACTS.md`

## Contracts used or changed
- Uses CONTRACTS v1 from PR #43 (`rules`/`observe`/`step`, cap 500, timeout 3600 s). Changes none.

## Status
- [x] #37 claimed, worktree made
- [x] Token size of v1 observations measured; per-run token and cost model (`eval/budget/`)
- [x] Provider table from the two real runs on record; pre-install recommendation
- [x] Harbor 0.26.0 opencode kwargs checked: skip_install, version reuse, opencode_config
- [x] OpenCode 1.19.5 compaction and prune behaviour read from source; system prompt sizes counted
- [ ] Docker on this laptop (installing); real 24 h and 72 h runs once #4, #5, #22 land
- [ ] Post recommendations on #18 and #22; section in docs/HARBOR-NOTES.md

## Decisions and notes
- Sat 15:00. Estimates assume one model turn per tick, 14k fixed context, 2.4k growth per tick. Base from the Verda Kimi run (13.5k prompt tokens per turn on Unfindable).
- Sat 15:00. tiktoken is used only by `obs_tokens.py` through `uv run --with tiktoken`; no pyproject, nothing installed in any image.

## Handoff
- Done: `eval/budget/measurements.md` (estimates), `estimate.py`, `obs_tokens.py`.
- Not done: every real measurement; no Docker on this laptop yet.
- How to test: `python eval/budget/estimate.py --compact-at 200000`; `uv run --no-project --python 3.12 --with tiktoken python eval/budget/obs_tokens.py`.
