# Branch: mykhailo/harness-seeds

- **Issue:** #26
- **Owner:** mykhailo
- **Agent:** mykhailo-claude-1h
- **Parent branch:** main
- **Created:** Sat 15:15

## Goal
`scripts/make_seeds.sh` stamps `ed72-s1..s3` from the `ed72/` task template so judges can rerun on several seeds. Only `ED72_SEED` (hospital service) and the task `name` differ.

## Files and folders I own
- `scripts/make_seeds.sh`, `scripts/test_make_seeds.sh`, this file

## Don't touch
- `ed72/` (packaging, #22)

## Contracts used or changed
- None. Assumes the layout on `origin/yehor/harness-task-skeleton`: `ed72/environment/docker-compose.yaml` with one `ED72_SEED:` line, `ed72/task.toml` with `name =` under `[task]`.

## Status
- [x] Script with `--check`, idempotent, bash 3.2 / BSD safe (awk + temp file, no `sed -i`)
- [x] Test against a fixture; shellcheck clean
- [ ] Run for real once `ed72/` lands on main, commit the three folders

## Decisions and notes
- Name stamped as `<name>-s<N>` on the `name =` line inside `[task]` only (the mcp server `name =` is untouched).
- `ED72_ROOT` env var overrides the repo root (tests).

## Handoff
Done: script and test. Not done: generating the folders (template not on main yet). Test: `bash scripts/test_make_seeds.sh`. CI: `scripts/make_seeds.sh --check`.
