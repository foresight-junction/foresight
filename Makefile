# One-command eval (docs/EVAL.md section 3). Needs Docker and uv; Harbor 0.26.0 runs through uvx.
#   make eval            reference, do-nothing and 3 agent runs on $(ED72_MODEL)
#   make eval-baselines  reference and do-nothing (no API key)
#   make eval-summary    rewrite eval/results/summary.md from the latest run, or JOBS=<dir>
# Results: eval/results/jobs/<run id>/ and eval/results/summary.md.

SHELL := /bin/bash
JOBS ?= $(firstword $(shell ls -td eval/results/jobs/*/ 2>/dev/null))

.PHONY: eval eval-baselines eval-summary

eval:
	eval/run_all.sh all

eval-baselines:
	eval/run_all.sh baselines

eval-summary:
	@test -n "$(JOBS)" || { echo "eval-summary: no runs in eval/results/jobs/. Run make eval-baselines first." >&2; exit 1; }
	uv run --no-project --python 3.12 python eval/summarise.py "$(JOBS)"
