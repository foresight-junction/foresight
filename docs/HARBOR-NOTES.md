# Harbor and OpenCode smoke test

On 14 November 2026, OpenCode 1.19.5 and Gemini 3.8 Flash called
`hospital_rules`, `hospital_observe`, and `hospital_step` in order over
streamable HTTP. The sidecar's collected report independently recorded the
same sequence. The separate verifier wrote a scalar reward of **1.0**.
Harbor 0.26.0 completed one trial with zero exceptions in 29 seconds with
the agent image cached.

## Reproduce

From the repository root, set `JUNCTION_ENV_FILE` to the absolute path
to an ignored local dotenv file containing `GEMINI_API_KEY`.

```bash
HARBOR_TELEMETRY=0 uvx --python 3.12 --from harbor==0.26.0 harbor run \
  -p spikes/ed72-harbor-smoke -a opencode -m gemini/gemini-3.8-flash \
  --api-key-name GEMINI_API_KEY --env-file "$JUNCTION_ENV_FILE" \
  --ak skip_install=true -o jobs --job-name ed72-harbor-smoke -n 1 -y
```

The trajectory is `jobs/ed72-harbor-smoke/<trial>/agent/trajectory.json`.
The same trial directory contains `artifacts/evidence/report.json`,
`verifier/reward.txt`, and `trial.log`. The reward is specific to the
one-tick fixture and measures delivery of the three calls.

## Setup and verifier

The agent image pins OpenCode 1.19.5 on Node 22 Alpine. The initial npm
install took 456 seconds on this Apple Silicon host. Harbor 0.26.0 uses the
cached image with `--ak skip_install=true`. The earlier Debian trial was
stopped after 16 minutes in package setup, before any model calls.

The sidecar runs FastMCP 4.2.0 at `http://hospital:8000/mcp` with
`/health` for readiness. Harbor stops the agent before collecting the
report. In 0.26.0 a custom verifier Dockerfile bundles the tests.
The first preinstalled trial reached the MCP tools, then hit
`RewardFileNotFoundError` because the temporary verifier image omitted
`/tests/test.sh`. The successful retry bundles the script.

The earlier three-tool Python smoke over the same transport completed under
Harbor 0.25.0 with oracle reward 1 and no-op reward 0. The model run above
is the transport check for the final task. Runs against the full simulator
belong to #17.
