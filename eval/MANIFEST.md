# Run manifest and planned matrix (schema 2)

For the owner of `eval/run_all.sh`. `eval/manifest.py` is stdlib-only; call it with
`python3 "$REPO_ROOT/eval/manifest.py"` (or `uv run --no-project --python 3.12 python ...`).

## Calls, in order

1. **Before the first `harbor run`** (before any paid call), once per jobs root:

   ```bash
   python3 eval/manifest.py plan "$JOBS_DIR" --task "$TASK_DIR" \
     --entry "job=reference,policy=oracle" \
     --entry "job=do-nothing,policy=nop" \
     --entry "job=stop-early,policy=stop-early" \
     --entry "job=agent,policy=opencode,model=$ED72_MODEL,repeats=$AGENT_RUNS"
   ```

   Writes `$JOBS_DIR/plan.json`, one entry per planned attempt (`repeats=N` expands to repeat
   1..N). The seed defaults to the effective task seed (host `ED72_SEED`, else compose).
   Refuses to overwrite an existing plan (exit 2); the plan is written once. `policy` is the
   Harbor agent name as it appears in `agent_info.name` (`oracle`, `nop`, `opencode`, or the
   stop-early agent name); omit `model` for oracle/nop. If the plan call fails, abort the run.

2. **After each `harbor run` returns** (also when it failed, so the identity is kept):

   ```bash
   python3 eval/manifest.py write "$JOBS_DIR/$job" --task "$TASK_DIR" \
     --harbor-version 0.26.0 --agent opencode --model "$ED72_MODEL" --repeat 1 \
     --ak version="$OPENCODE_VERSION" --ae "$OPENCODE_KEY_NAME" \
     --budget max_cost_usd=5
   ```

   Writes `$JOBS_DIR/$job/manifest.json`. `--ak`/`--ae` store option and env **names only**
   (`NAME=value` is accepted and the value is dropped). One manifest per job; `-k 3` jobs use
   `--repeat 1` (the trials are matched to plan entries by count). Do not pass `--seed` unless
   the runner itself chose a seed; the host `ED72_SEED` is read automatically.

3. **Summarise** reads `plan.json` from the jobs root: `python3 eval/summarise.py "$JOBS_DIR"`.
   Exit 4 means a planned attempt is missing or failed (use `--allow-incomplete` only for a
   deliberate partial run); exit 3 means a failed trial with no plan.

## Seed semantics

`seed_source` is one of `host_env`, `compose_default`, `compose_literal`, `task_name`, `unknown`.
Host `ED72_SEED` takes effect only when compose interpolates it (`${ED72_SEED:-42}`, PR #112).
With a literal `ED72_SEED: "42"` Docker ignores the host value, so the manifest records the
literal (`compose_literal`) and never claims an override that did not happen.

## manifest.json fields

`schema`, `task_path`, `seed`, `seed_source`, `config_file`, `config_sha256`,
`instruction_sha256`, `task_sha256` (sorted file list and contents, minus `__pycache__`, `.git`,
`.venv`, `jobs`, `logs`, `*.pyc`), `reference_sha256` (same hash over `<task>/solution`),
`source_commit`, `source_dirty`, `model`, `agent`, `agent_option_names`, `agent_env_names`,
`repeat`, `attempt`, `budget`, `runtime` (`harbor`, `python`, `docker`; null when unavailable),
`harbor_version`, `written_at`, `source`. Schema 1 manifests (no `schema` key) still load.

## plan.json

`{"schema": 2, "created_at": ..., "entries": [{"job", "policy", "model", "seed", "repeat"}]}`.
`summarise.completeness(plan, trials)` matches trials to entries by (job, policy, model, seed),
counting repeats, and reports missing, failed, timed-out and unplanned trials. Nothing is dropped. A timed-out trial with a Harbor exception counts as failed (#93: any agent exception fails the evaluation).

## Frozen identity, drift, per-root completeness and exit codes

- `plan --task <dir>` freezes the source commit (+dirty) and the task/config/instruction/reference SHA-256 into `plan.json` (`identity`; an entry with its own `task` freezes it on the entry). The CLI calls above are unchanged.
- `write` finds the nearest `plan.json` above the job dir and records the **frozen** identity as the attempt's identity (`identity_source: plan`). What the task dir looks like after the run goes under `observed`; any difference sets `identity_drift: true` and lists `drifted_fields`. The planned identity is never replaced.
- `write --exit-code INT` stores Harbor's exit status as `harbor_exit_code`; without the flag, `<job dir>/harbor-exit-code.txt` is read if present.
- `summarise` matches each root's trials only against **that root's** plan (a root without a plan contributes all its trials as unplanned), then sums the totals. Identity drift and crashed attempts (planned, no finished trial, non-zero `harbor_exit_code`) count as failed and make it exit 4 unless `--allow-incomplete` is given.
- Rows and gaps are keyed on seed, config, instruction, task, reference and source; any `unknown` keeps a trial in its own row with no gap.
