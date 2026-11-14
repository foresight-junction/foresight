# Branch: yehor/ref-matrix

- **Issue:** #18
- **Owner:** yehor
- **Agent:** lead
- **Parent branch:** main
- **Created:** Sat 17:32

# Model matrix handoff

Issue #18. Run on Kostiantyn’s laptop as assigned on #1, using the authorized models and keys. The frozen revision is `474829a`. The first full OpenCode attempt on seed 42 timed out during setup before model calls. #17 tracks the retry with a setup timeout multiplier of four.

From a clean checkout of the frozen revision, run `scripts/make_seeds.sh 1 2 3`. Use one job output root per seed and record the frozen revision, Harbor version, OpenCode version, exact model ID and seed. Use the same seed task for its oracle, nop and all model trials.

```bash
# Set MODEL, KEY_NAME (the provider key variable name), and SEED before running.
# Export the provider key itself separately.
HARBOR_RUN=(uvx --python 3.12 --from harbor==0.25.0 harbor)
TASK="ed72-s${SEED}"
JOBS="eval/results/jobs/matrix-$(git rev-parse --short HEAD)/seed-${SEED}"
mkdir -p "$JOBS"

# Run these two baselines once per seed.
"${HARBOR_RUN[@]}" run -p "$TASK" -o "$JOBS" --job-name reference -y -a oracle -n 1
"${HARBOR_RUN[@]}" run -p "$TASK" -o "$JOBS" --job-name do-nothing -y -a nop -n 1

# Run this once per authorized model. Use a distinct job name per model.
"${HARBOR_RUN[@]}" run -p "$TASK" -o "$JOBS" --job-name "model-${MODEL//\//-}" -y \
  -a opencode -m "$MODEL" --api-key-name "$KEY_NAME" --ak version=1.19.5 \
  --agent-setup-timeout-multiplier 4 -k 3 -n 3

uv run --no-project --python 3.12 python eval/summarise.py "$JOBS" --out "$JOBS/summary.md"
```

Use the explicit seed from the job directory in the combined results. The frozen report lacks the seed field used by the summariser. Verify three completed model trials with scores and evidence per seed and model. Report setup failures separately, retain their logs, and compare each model's maximum reward against its same-seed oracle. Preserve the trajectory, score report and reward for the submission. Job folders are gitignored, so review the intended artifacts before committing them. #83 tracks the absent Harbor stop-early adapter. The in-process stop-early result is in `docs/TUNING.md`.
