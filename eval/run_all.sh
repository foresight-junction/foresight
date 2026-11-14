#!/usr/bin/env bash
# Reproduce the reported ED-72 results (docs/EVAL.md section 3) and write eval/results/summary.md.
#
#   eval/run_all.sh            reference, do-nothing, stop-early, then 3 agent runs on $ED72_MODEL
#   eval/run_all.sh baselines  reference, do-nothing, stop-early (no API key needed)
#
# Needs Docker, uv, and for the agent runs ED72_MODEL (e.g. gemini/gemini-3.8-flash) plus that
# provider's key, from the shell or the repo's .env. HARBOR overrides the pinned Harbor command.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TASK_DIR="$REPO_ROOT/ed72"
ENV_FILE="$REPO_ROOT/.env"
RUN_ID="$(date +%Y%m%d-%H%M%S)"
JOBS_DIR="$REPO_ROOT/eval/results/jobs/$RUN_ID"
SUMMARY="$REPO_ROOT/eval/results/summary.md"
OPENCODE_VERSION="1.19.5"
AGENT_RUNS=3
# Stop-early is a Harbor custom agent from #12 (eval/baselines/); this script only calls it.
STOP_EARLY_FILE="$REPO_ROOT/eval/baselines/harbor_agent.py"
STOP_EARLY_AGENT="eval.baselines.harbor_agent:StopEarlyAgent"
MODE="${1:-all}"

export HARBOR_TELEMETRY=0
read -r -a HARBOR_CMD <<<"${HARBOR:-uvx --python 3.12 --from harbor==0.25.0 harbor}"

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
[ -f "$TASK_DIR/task.toml" ] || die "$TASK_DIR/task.toml not found. The Harbor task is built by #22."

KEY_NAME=""
if [ "$MODE" = all ]; then
  [ -n "${ED72_MODEL:-}" ] || die "ED72_MODEL is not set (e.g. ED72_MODEL=gemini/gemini-3.8-flash)"
  case "${ED72_MODEL%%/*}" in
    anthropic) KEY_NAME=ANTHROPIC_API_KEY ;;
    openai) KEY_NAME=OPENAI_API_KEY ;;
    gemini | google) KEY_NAME=GEMINI_API_KEY ;;
    *) die "ED72_MODEL '$ED72_MODEL' must start with anthropic/, openai/, gemini/ or google/" ;;
  esac
  [ -n "${!KEY_NAME:-}" ] || die "$KEY_NAME is not set (shell or $ENV_FILE), needed for $ED72_MODEL"
fi

mkdir -p "$JOBS_DIR"
FAILED=()

# A failed job is recorded and the rest still run, so the summary shows whatever finished.
# Harbor can exit 0 with errored trials; summarise.py exits non-zero if any trial has no reward.
run_job() {
  local job="$1"
  shift
  echo "run_all: $job -> $JOBS_DIR/$job"
  if ! "${HARBOR_CMD[@]}" run -p "$TASK_DIR" -o "$JOBS_DIR" --job-name "$job" -y "$@"; then
    echo "run_all: $job FAILED" >&2
    FAILED+=("$job")
  fi
}

run_job reference -a oracle -n 1
run_job do-nothing -a nop -n 1

if [ -f "$STOP_EARLY_FILE" ]; then
  PYTHONPATH="$REPO_ROOT${PYTHONPATH:+:$PYTHONPATH}" run_job stop-early -a "$STOP_EARLY_AGENT" -n 1
else
  echo "run_all: SKIP stop-early: $STOP_EARLY_FILE not found (built by #12)." >&2
fi

if [ "$MODE" = all ]; then
  run_job agent -a opencode -m "$ED72_MODEL" --api-key-name "$KEY_NAME" \
    --ak "version=$OPENCODE_VERSION" --agent-setup-timeout-multiplier 3 \
    -k "$AGENT_RUNS" -n "$AGENT_RUNS"
fi

if ! uv run --no-project --python 3.12 python "$REPO_ROOT/eval/summarise.py" "$JOBS_DIR" --out "$SUMMARY"; then
  FAILED+=(summary)
fi

if [ "${#FAILED[@]}" -gt 0 ]; then
  die "failed: ${FAILED[*]} (see $JOBS_DIR)"
fi
