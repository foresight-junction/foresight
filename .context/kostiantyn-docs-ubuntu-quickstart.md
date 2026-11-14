# Branch: kostiantyn/docs-ubuntu-quickstart

- **Issue:** #25
- **Owner:** kostiantyn
- **Agent:** kostiantyn-codex-wsl
- **Parent branch:** main
- **Created:** Sat 22:48

## Goal
Give Windows users the shortest complete Ubuntu/WSL path to one Gemini run or the full evaluation. Requested directly by Kostya after a Docker settings restart interrupted his adhoc trial.

## Files and folders I own
- `README.md`
- `.context/kostiantyn-docs-ubuntu-quickstart.md`

## Don't touch
- Simulator, scorer, tools, runner, contracts, release campaign artifacts and other owners' context files.

## Contracts used or changed
- Uses existing Gemini key mapping, Harbor 0.26.0 and OpenCode 1.19.5. No contract changes.

## Status
- [x] Document Ubuntu tools, Docker integration, hidden key prompt, one trial, full evaluation and output locations.
- [x] Correct stale README claims that the runner skips stop-early.
- [x] Bash syntax, relative links, make dry runs and installed Harbor flags checked.
- [x] noslop: clean. Codex /review found no defects; Claude cross-review: LGTM.
- [x] Ubuntu adhoc retry completed: reward 0.372550, zero exceptions, ended tick_143, 153 tool calls, Harbor cost $0.60507915.
- [x] Full keyless Ubuntu runner passed on seed 42: reference 0.940221, do-nothing 0.000000, stop-early 0.058304. All three trials have zero errors.

## Decisions and notes
- Separate docs-only helper for #25; parent task ownership and final campaign remain with Yehor. No merge authorized.
- The adhoc seed-42 retry uses a separate Linux clone at frozen commit 9f3bdbb and separate output folders. It does not add trials to the final campaign.
- No new dependencies in the repository. Ubuntu needs make for the existing Makefile.

## Handoff
- Done: README quickstart and baseline description updated, reviewed by Claude and Codex. PR #125 is ready for Yehor; initial CI passed. The adhoc Gemini trial and all three keyless baselines completed in Ubuntu. Key whitespace is stripped after a pasted carriage return caused a pre-model config error; failed logs were redacted.
- Next: Yehor may integrate the docs-only PR. No merge authorized. Worktree is free after this validation update is pushed.
- Test: three extracted README Bash blocks and eval/run_all.sh pass bash -n; all relative README links resolve; make eval-baselines passed in Ubuntu. Gemini job ubuntu-gemini-seed42-20261114-225045 is copied to Desktop/ed72-runs with a valid reward and report. The final paid matrix was not launched.
