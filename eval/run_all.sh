#!/usr/bin/env bash
# Reproduce the reported ED-72 results (docs/EVAL.md section 3) and write a report for each run.
#
#   eval/run_all.sh            three baselines, then 3 agent runs on $ED72_MODEL
#   eval/run_all.sh baselines  reference, do-nothing and stop-early (no API key needed)
#
# Needs Docker, uv, and for the agent runs ED72_MODEL (e.g. gemini/gemini-3.8-flash) plus that
# provider's key, from the shell or the repo's .env. HARBOR overrides the pinned Harbor command.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TASK_DIR="$REPO_ROOT/ed72"
ENV_FILE="$REPO_ROOT/.env"
RESULTS_DIR="$REPO_ROOT/eval/results"
LATEST_SUMMARY="$RESULTS_DIR/summary.md"
OPENCODE_VERSION="1.19.5"
AGENT_RUNS=3
PYTHON_CMD=(uv run --no-project --python 3.12 python)
MANIFEST="$REPO_ROOT/eval/manifest.py"
# Stop-early is a Harbor custom agent in #12's ed72_baselines package; this script only calls it.
STOP_EARLY_PATH="$REPO_ROOT/eval/baselines"
STOP_EARLY_FILE="$STOP_EARLY_PATH/ed72_baselines/harbor_agent.py"
STOP_EARLY_AGENT="ed72_baselines.harbor_agent:StopEarlyAgent"
MODE="${1:-all}"

export HARBOR_TELEMETRY=0
read -r -a HARBOR_CMD <<<"${HARBOR:-uvx --python 3.12 --from harbor==0.26.0 harbor}"

die() {
  echo "run_all: $*" >&2
  exit 1
}

case "$MODE" in
  all | baselines) ;;
  *) die "unknown mode '$MODE' (use: all | baselines)" ;;
esac

# Fill only unset variables from .env: an empty KEY= copied from .env.example must not blank a key
# exported in the shell. Harbor's own --env-file would override, so it is not used.
if [ -f "$ENV_FILE" ]; then
  while IFS='=' read -r key value || [ -n "$key" ]; do
    [[ "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue
    value="${value%\"}"
    value="${value#\"}"
    [ -n "${!key:-}" ] || export "$key=$value"
  done <"$ENV_FILE"
fi

command -v docker >/dev/null 2>&1 || die "docker not found. Install Docker Desktop and start it."
docker info >/dev/null 2>&1 || die "Docker is not running. Start Docker Desktop and retry."
command -v uv >/dev/null 2>&1 || die "uv not found. Install it: https://docs.astral.sh/uv/"
command -v "${HARBOR_CMD[0]}" >/dev/null 2>&1 || die "'${HARBOR_CMD[0]}' not found (HARBOR=${HARBOR_CMD[*]})"
[ -f "$TASK_DIR/task.toml" ] || die "$TASK_DIR/task.toml not found. Run this from the repository root."
for required in "$STOP_EARLY_FILE" "$STOP_EARLY_PATH/ed72_baselines/ward_driver.py" \
  "$TASK_DIR/solution/solve.sh" "$TASK_DIR/solution/reference.py" "$TASK_DIR/solution/policy.py" \
  "$TASK_DIR/environment/ward" "$REPO_ROOT/eval/manifest.py" "$REPO_ROOT/eval/summarise.py"; do
  [ -f "$required" ] || die "required baseline/evaluator file missing: $required"
done

# Native Windows Python needs a Windows PYTHONPATH even when the runner uses Git Bash.
BASELINE_PYTHONPATH="$STOP_EARLY_PATH"
PATH_SEPARATOR=:
if command -v cygpath >/dev/null 2>&1; then
  BASELINE_PYTHONPATH="$(cygpath -w "$STOP_EARLY_PATH")"
  PATH_SEPARATOR=';'
fi
export PYTHONPATH="$BASELINE_PYTHONPATH${PYTHONPATH:+$PATH_SEPARATOR$PYTHONPATH}"

# KEY_NAME is the key the user sets; OPENCODE_KEY_NAME is the variable OpenCode's provider reads.
# They differ only for Google (README "Run it" has the same table).
KEY_NAME=""
OPENCODE_KEY_NAME=""
if [ "$MODE" = all ]; then
  [ -n "${ED72_MODEL:-}" ] || die "ED72_MODEL is not set (e.g. ED72_MODEL=gemini/gemini-3.8-flash)"
  case "${ED72_MODEL%%/*}" in
    anthropic) KEY_NAME=ANTHROPIC_API_KEY OPENCODE_KEY_NAME=ANTHROPIC_API_KEY ;;
    openai) KEY_NAME=OPENAI_API_KEY OPENCODE_KEY_NAME=OPENAI_API_KEY ;;
    gemini | google) KEY_NAME=GEMINI_API_KEY OPENCODE_KEY_NAME=GOOGLE_GENERATIVE_AI_API_KEY ;;
    *) die "ED72_MODEL '$ED72_MODEL' must start with anthropic/, openai/, gemini/ or google/" ;;
  esac
  [ -n "${!KEY_NAME:-}" ] || die "$KEY_NAME is not set (shell or $ENV_FILE), needed for $ED72_MODEL"
fi

HARBOR_VERSION="$("${HARBOR_CMD[@]}" --version)" || die "cannot determine Harbor version"
mkdir -p "$RESULTS_DIR/jobs"
RUN_TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
JOBS_DIR="$(mktemp -d "$RESULTS_DIR/jobs/$RUN_TIMESTAMP-XXXXXXXX")" \
  || die "cannot reserve a run directory under $RESULTS_DIR/jobs"
SUMMARY="$JOBS_DIR/summary.md"

PLAN_ARGS=(--entry "job=reference,policy=oracle" --entry "job=do-nothing,policy=nop"
  --entry "job=stop-early,policy=stop_early")
if [ "$MODE" = all ]; then
  PLAN_ARGS+=(--entry "job=agent,policy=opencode,model=$ED72_MODEL,repeats=$AGENT_RUNS")
fi
"${PYTHON_CMD[@]}" "$MANIFEST" plan "$JOBS_DIR" --task "$TASK_DIR" "${PLAN_ARGS[@]}" \
  || die "manifest planning failed; no jobs started (requires #105's plan/write API)"

preflight() {
  "${HARBOR_CMD[@]}" run -p "$TASK_DIR" "$@" --dry-run \
    || die "Harbor preflight failed; no jobs started"
}
preflight -a oracle
preflight -a nop
preflight -a "$STOP_EARLY_AGENT"
if [ "$MODE" = all ]; then
  preflight -a opencode -m "$ED72_MODEL" --api-key-name "$KEY_NAME" \
    --ae "$OPENCODE_KEY_NAME=\${$KEY_NAME}" --ak "version=$OPENCODE_VERSION"
fi

FAILED=()

# A failed job is recorded and the rest still run, so the summary shows whatever finished.
# Harbor can exit 0 with errored trials; summarise.py exits non-zero when it finds a failed trial.
run_job() {
  local job="$1" policy="$2" model="$3" status=0
  shift 3
  echo "run_all: $job -> $JOBS_DIR/$job"
  if "${HARBOR_CMD[@]}" run -p "$TASK_DIR" -o "$JOBS_DIR" --job-name "$job" -y "$@"; then
    status=0
  else
    status=$?
    echo "run_all: $job FAILED" >&2
    FAILED+=("$job")
  fi
  mkdir -p "$JOBS_DIR/$job"
  printf '%s\n' "$status" > "$JOBS_DIR/$job/harbor-exit-code.txt"
  local manifest_args=(--agent "$policy" --repeat 1)
  if [ -n "$model" ]; then
    manifest_args+=(--model "$model" --ak "version=$OPENCODE_VERSION" --ae "$OPENCODE_KEY_NAME")
  fi
  if ! "${PYTHON_CMD[@]}" "$MANIFEST" write "$JOBS_DIR/$job" --task "$TASK_DIR" \
    --harbor-version "$HARBOR_VERSION" "${manifest_args[@]}"; then
    FAILED+=("$job-manifest")
  fi
}

run_job reference oracle "" -a oracle -n 1
run_job do-nothing nop "" -a nop -n 1

run_job stop-early stop_early "" -a "$STOP_EARLY_AGENT" -n 1

if [ "$MODE" = all ]; then
  # Harbor may exit 0 even when a trial failed. Check each required baseline before paid calls.
  for job in reference do-nothing stop-early; do
    if ! "${PYTHON_CMD[@]}" "$REPO_ROOT/eval/summarise.py" "$JOBS_DIR/$job" \
      --out "$JOBS_DIR/$job/summary.md"; then
      FAILED+=("$job-verification")
    fi
  done
  if [ "${#FAILED[@]}" -eq 0 ]; then
    # Harbor resolves the ${...} template from the host env; the key never appears here.
    run_job agent opencode "$ED72_MODEL" -a opencode -m "$ED72_MODEL" --api-key-name "$KEY_NAME" \
      --ae "$OPENCODE_KEY_NAME=\${$KEY_NAME}" --ak "version=$OPENCODE_VERSION" \
      -k "$AGENT_RUNS" -n "$AGENT_RUNS"
  else
    echo "run_all: required baselines failed; no model runs started" >&2
  fi
fi

SUMMARY_STATUS=0
"${PYTHON_CMD[@]}" "$REPO_ROOT/eval/summarise.py" "$JOBS_DIR" --out "$SUMMARY" || SUMMARY_STATUS=$?
if [ "$SUMMARY_STATUS" -ne 0 ]; then
  FAILED+=(summary)
fi

# The summariser returns 3 and 4 only after writing a report with failed or incomplete trials.
if [[ "$SUMMARY_STATUS" =~ ^(0|3|4)$ ]] && [ -f "$SUMMARY" ]; then
  echo "run_all: report -> $SUMMARY"
  # Stage the copy beside its destination so concurrent readers see a complete report.
  TEMP_SUMMARY="$(mktemp "$RESULTS_DIR/.summary-XXXXXXXX")" || die "cannot stage $LATEST_SUMMARY"
  if [ -d "$LATEST_SUMMARY" ] || ! cp "$SUMMARY" "$TEMP_SUMMARY" || ! mv -f "$TEMP_SUMMARY" "$LATEST_SUMMARY"; then
    rm -f "$TEMP_SUMMARY"
    die "cannot publish $LATEST_SUMMARY (see $SUMMARY)"
  fi
fi

if [ "${#FAILED[@]}" -gt 0 ]; then
  die "failed: ${FAILED[*]} (see $JOBS_DIR)"
fi
