# Branch: yehor/ref-matrix

- **Issue:** #18
- **Owner:** yehor
- **Agent:** lead
- **Parent branch:** main
- **Created:** Sat 17:32

## Matrix handoff

Run after the 22:00 rules freeze on Kostiantyn's laptop, with the models and budget agreed in #17, #18 and #37. The three attempts recorded so far in #17 used `474829a` and reached no model calls. One wrote a zero reward after a provider authentication error. Keep those attempts in the calibration record.

The latest main checked for this handoff is `083a723`. It includes #89, which installs OpenCode 1.19.5 in the agent image. Use Harbor 0.26.0 for this matrix. Its OpenCode installer checks the installed version first. The 0.25.0 version pinned by `make eval` still runs the cold install. Confirm the first successful run on the post-#89 image in #17 before expanding to the matrix.

### Prepare the tasks

Use Bash from a clean checkout of the agreed release revision. Stamp the three matrix seeds and any held-out seeds agreed with the runner. The generator replaces any existing generated folders for those seeds.

```bash
HARBOR_RUN=(uvx --python 3.12 --from harbor==0.26.0 harbor)
"${HARBOR_RUN[@]}" --version
scripts/make_seeds.sh 1 2 3
scripts/make_seeds.sh --check 1 2 3
REVISION=$(git rev-parse HEAD)
MATRIX_ROOT="eval/results/jobs/matrix-${REVISION:0:12}-$(date -u +%Y%m%dT%H%M%SZ)"
```

Set `SEED` to the generated task seed. Repeat the baselines once per seed, including each agreed held-out seed, and reuse that seed's task for all model runs.

```bash
TASK="ed72-s${SEED}"
JOBS="$MATRIX_ROOT/seed-${SEED}"
mkdir -p "$JOBS"
"${HARBOR_RUN[@]}" run -p "$TASK" -o "$JOBS" --job-name reference -y -a oracle -k 1 -n 1
"${HARBOR_RUN[@]}" run -p "$TASK" -o "$JOBS" --job-name do-nothing -y -a nop -k 1 -n 1
```

### Run the models

Set `MODEL` to the agreed provider/model ID. Export the provider key on the host. For Gemini, #17 confirmed that OpenCode needs the key under `GOOGLE_GENERATIVE_AI_API_KEY`. If the host stores it as `GEMINI_API_KEY`, configure the literal shell argument below and let Harbor resolve the variable. Use the verified provider setup from #37 for other models.

```bash
# Gemini example. Kostiantyn's shell already has GEMINI_API_KEY exported.
AUTH=(--ae 'GOOGLE_GENERATIVE_AI_API_KEY=${GEMINI_API_KEY}')
"${HARBOR_RUN[@]}" run -p "$TASK" -o "$JOBS" --job-name "model-${MODEL//\//-}" -y \
  -a opencode -m "$MODEL" "${AUTH[@]}" --ak version=1.19.5 \
  -k 3 -n 1 --max-retries 0
```

Run one command per model and seed. `-k 3` schedules three attempts. `-n 1` runs them sequentially. If the runner chooses to use the first attempt in a matrix cell as a smoke check, run with `-k 1`, inspect its trajectory and verifier evidence, then use a fresh job name and `-k 2` to finish that cell. The #17 calibration on seed 42 is tracked separately.

### Record the results

- Keep each seed under its own output root. Generate a diagnostic summary with `uv run --no-project --python 3.12 python eval/summarise.py "$JOBS" --out "$JOBS/summary.md"`. The summariser counts missing rewards as zero. Assign the seed from the task and output directory in the combined results, since the score object has no seed field.
- Record the full revision, Harbor and OpenCode versions, seed, model ID and job path. For the official model mean and range, include only completed trials with evidence of model activity, a valid verifier score and no infrastructure failure. A model that ends play early with a valid score still counts. Keep the failure logs, list setup, authentication and verifier failures separately, and mark any cell with fewer than three valid trials as incomplete. Report the valid count alongside the planned count.
- Report per-model, per-seed reward mean and range, O/T/W/B, deaths, faints and failure counts from valid trials. Compare each model's range and mean with the oracle from the same seed. Preserve the OpenCode trajectory, score report and reward paths. Review the intended artifacts for secrets before sharing them.
- The task exports the hospital score report. Its raw `events.jsonl` stays inside the hospital container. Use the captured OpenCode trajectory and score report for #19, or coordinate separate collection from the trusted hospital side if the analysis needs the raw event log.
- Stop-early stays in process for this submission. See the baseline evidence in `docs/TUNING.md` and the deferred Harbor adapter in #83.

## Handoff

Seed generation was checked against `083a723`. A Harbor 0.26.0 dry run with a placeholder credential resolved the Gemini key mapping and scheduled exactly three trials. Post-#89 calibration, final model and seed selections, and matrix results remain pending with the assigned runner.
