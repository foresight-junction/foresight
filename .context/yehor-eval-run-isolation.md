# yehor/eval-run-isolation

- **Owner:** Yehor
- **Agent:** yehor-codex-1
- **Base:** main
- **Issue:** #155

## Goal

Keep simultaneous evaluation runs and their reports in distinct directories.

## Files I own

`eval/run_all.sh`, `eval/tests/test_run_all.py`, the run output location in `docs/EVAL.md`, and
the generated summary staging pattern in `.gitignore`.

## Don't touch

Harbor arguments, manifest and summary schemas, or published campaign artifacts.

## Handoff

Each invocation reserves a timestamped directory with a random suffix before manifest planning.
The runner writes its report there and atomically publishes a copy at `eval/results/summary.md`.
Same-second fake-Harbor runs verify that plans, manifests, job files and reports keep their seeds.
Run `bash -n eval/run_all.sh` and `uv run --project eval --with pytest pytest -q eval/tests`.
