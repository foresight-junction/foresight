# Branch: mykhailo/harness-seeds-prep

- **Issue:** #26 (D6: validate generated release seeds, x86/ARM Harbor runs)
- **Owner:** mykhailo
- **Agent:** mykhailo-claude-1 (lead), mykhailo-claude-1t (subagent)
- **Parent branch:** main

## Goal
Prepare the seed generator and its checks. Yehor (sole merger/orchestrator) freezes the revision; only then are `ed72-s*` folders generated. No `ed72-s*` folders are committed on this branch.

## Files I own
`scripts/make_seeds.sh`, `scripts/test_make_seeds.sh`, this file.

## Status
- [x] make_seeds.sh handles literal `"N"` and override `"${ED72_SEED:-N}"` (PR #112) ED72_SEED forms; fails on missing, duplicate or other values
- [x] `--report`: markdown table (default seed, task name, content SHA-256, source commit, Harbor oracle and nop commands) plus the ed72 row
- [x] Tests cover both forms, `--check`, `--report`, bad lines
- [ ] After the freeze: Yehor runs `scripts/make_seeds.sh`, `--report`, and the oracle/nop runs on x86 and ARM

## Decisions and notes
- Report hash: SHA-256 of sorted "file-hash  path" lines; skips `.harborignore` patterns, `__pycache__`, `*.pyc`, `*.tmp`, `.DS_Store`.
- Source commit gets `+dirty` when `ed72/` has uncommitted changes.

## Handoff
Done: generator and report. Not done: generating folders and Harbor runs (after freeze).
Test: `bash scripts/test_make_seeds.sh`; `scripts/make_seeds.sh --report` (writes nothing).
