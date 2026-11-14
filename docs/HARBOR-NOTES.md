# Harbor smoke test

Issue #21 checks whether an OpenCode model can call an MCP tool on the hospital sidecar. The test tool increments a counter and returns the count. The separate verifier awards 1 if the sidecar's collected report records exactly one ping and 0 otherwise.

## Local baselines

Verified with Harbor 0.25.0, Docker Desktop engine 29.9.2, and Python 3.12 containers on an Apple Silicon Mac. The hospital uses FastMCP 4.2.0 at `http://hospital:8000/mcp` over streamable HTTP. The oracle uses MCP Python SDK 2.3.0.

From the temporary fixture's parent directory, where `task/` contains the Docker Compose and Harbor task files:

```bash
export HARBOR_TELEMETRY=0
uvx --python 3.12 --from harbor==0.25.0 harbor run -p task -a oracle -o jobs --job-name junction-s0-oracle -n 1 -y
uvx --python 3.12 --from harbor==0.25.0 harbor run -p task -a nop -o jobs --job-name junction-s0-nop -n 1 -y
```

| Agent | Reward | Evidence |
| --- | ---: | --- |
| `oracle` | 1 | The Python client called `ping` over MCP. The verifier received the sidecar report. |
| `nop` | 0 | The no-op trial collected a report with zero pings. |

In both runs, `trial.log` records that Harbor stopped the agent container before running `python /app/collect.py` on the hospital sidecar. Harbor passes `/evidence/report.json` to the separate verifier, which writes `verifier/reward.txt` in each local trial directory. The job summary is `jobs/<job-name>/result.json`.

The Gemini-backed OpenCode run is pending. The oracle result verifies the MCP and verifier paths using a direct MCP client.

## OpenCode run

OpenCode 1.19.5 lists `google/gemini-3.8-flash` in its Google catalog. Harbor takes the `gemini/` selector and maps it to the `google/` selector inside OpenCode.

From the same fixture parent directory, set `JUNCTION_ENV_FILE` to the absolute path to the ignored `.env` containing `GEMINI_API_KEY`, then run:

```bash
uvx --python 3.12 --from harbor==0.25.0 harbor run -p task -a opencode \
  -m gemini/gemini-3.8-flash --api-key-name GEMINI_API_KEY \
  --env-file "$JUNCTION_ENV_FILE" --ak version=1.19.5 \
  --agent-setup-timeout-multiplier 3 \
  -o jobs --job-name junction-s0-opencode -n 1 -y
```

Check the tool call in the trial's agent logs and the scalar result in `verifier/reward.txt`. A reward of 1 confirms the sidecar recorded exactly one ping.
