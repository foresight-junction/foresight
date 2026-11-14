# Spike S0 results: Harbor + MCP sidecar

Date: 2026-11-13. Host: Windows 10 Pro 19045, Git Bash. Branch `kostiantyn/env-unfindable-slice`.
Spike code: `spikes/s0-harbor/`. Raw job outputs: `spikes/s0-harbor/jobs/` (gitignored).

## TL;DR

| Question | Answer | Evidence |
|---|---|---|
| Can a Harbor task run an MCP server as a compose sidecar over streamable HTTP? | **Yes** | Runs 1–6 |
| Can code in `main` call it? | **Yes**, at `http://unfindable:8000/mcp` | Run 1: `initialize`, `list_tools`, `call_tool("ping")` → `1` |
| Can the verifier reach the sidecar and write a reward? | **Yes** in shared mode (live call). In separate mode it reaches a **new** sidecar, so the reward must come from collected evidence | Runs 1–4 |
| Does sidecar state survive into the verifier? | Shared: **yes** (same process). Separate: **no** (fresh compose project), but `[[verifier.collect]]` + sidecar artifacts carry it over | Runs 1, 3 |
| Is shared mode safe against T14? | **No. Reward forged and token stolen in a real run** | Run 5 |
| Is separate mode + collect hook safe against the same attack? | **Yes** for the attacks tried | Run 6 |
| Does OpenCode connect to the sidecar? | **Yes**, transport level (`opencode mcp list` → `connected`). A full OpenCode agent run was **not** executed (paid API calls not allowed) | §5 |

**Recommendation:** `environment_mode = "separate"`, plus a collect hook that finalizes inside the sidecar and writes `/evidence/report.json`, which is declared as a sidecar artifact (§8). Do not compute the reward from a live call in shared mode.

## 1. Environment

| Component | Version |
|---|---|
| Docker Desktop | 4.47.0 (engine 28.4.0, Compose v2.39.4-desktop.1, WSL2 kernel `6.6.87.1-microsoft-standard-WSL2`) |
| Python (host) | 3.13.5, venv at `spikes/s0-harbor/.venv` |
| Harbor | `harbor==0.25.0` from PyPI. The PyPI JSON has `project_urls: null`, so I checked it against `github.com/harbor-framework/harbor` `pyproject.toml` (same name `harbor`, version 0.25.0, author Alex Shaw, script `harbor = "harbor.cli.main:app"`), and the docs install page says `pip install harbor` |
| FastMCP (sidecar) | 4.2.0 (pinned in the sidecar image) |
| MCP Python SDK (client in main) | 2.3.0 (pinned in the main image) |
| OpenCode (transport check only) | 1.19.5 (`npm i -g opencode-ai@latest`) |
| Base images | `python:3.12-slim` (main and sidecar), `node:22-slim` (OpenCode check) |

All runs used `HARBOR_TELEMETRY=0` (Harbor's opt-out, found in `harbor/telemetry.py`) and `PYTHONIOENCODING=utf-8`, from `spikes/s0-harbor/`.

## 2. What was built

```
spikes/s0-harbor/
  prepare.py                  new per-build token -> sidecar/verifier.env + tests/verifier_token; builds variants in build/
  .gitignore                  .venv/, build/, jobs/, both token files
  .gitattributes              eol=lf (repo has core.autocrlf=true; CRLF in test.sh would break bash)
  task/                       the canonical task (shared verifier mode)
    task.toml                 [[environment.mcp_servers]] unfindable/streamable-http; [[verifier.collect]]; sidecar artifact
    instruction.md
    environment/
      Dockerfile              main: python:3.12-slim + mcp==2.3.0 (client only)
      .dockerignore           excludes sidecar/ and docker-compose.yaml from main's build context
      docker-compose.yaml     main depends_on unfindable (service_healthy); unfindable built from ./sidecar, env_file ./sidecar/verifier.env
      sidecar/Dockerfile      python:3.12-slim + fastmcp==4.2.0; COPY server.py collect.py
      sidecar/.dockerignore   excludes verifier.env from the sidecar image
      sidecar/server.py       FastMCP: tool ping (in-memory counter); GET /healthz; POST /admin/finalize (X-Verifier-Token, hmac.compare_digest)
      sidecar/collect.py      collect hook: calls finalize on 127.0.0.1 with the sidecar's own env token -> /evidence/finalize.json
    solution/solve.sh         oracle: runs probes.py, then mcp_ping.py
    solution/mcp_ping.py      MCP client (streamable_http_client + ClientSession) -> ping
    solution/probes.py        isolation probes from inside main -> /logs/agent/probes.json
    tests/test.sh             deletes reward.txt, pre-writes reward 0, runs verify.py, falls back to 0 on any failure
    tests/verify.py           live finalize or evidence (REWARD_SOURCE), token-leak scans, writes details.json, atomic reward.json
  tamper/solve.sh, fake_sidecar.py   adversarial "agent" for T14 (§6)
  opencode-check/docker-compose.yaml sidecar + node:22-slim for the OpenCode transport check
```

Variants built by `prepare.py` in `build/`: `s0-separate` (adds `environment_mode = "separate"` and `env = { REWARD_SOURCE = "evidence" }`), `s0-tamper-shared`, `s0-tamper-separate`, `s0-no-network` (adds `network_mode = "no-network"`).

FastMCP API checked against the installed 4.2.0, not guessed: `@mcp.tool`, `@mcp.custom_route(path, methods=[...])`, `mcp.run(transport="http", host=..., port=..., path="/mcp")`. MCP SDK 2.3.0 differs from 1.x: the client is `streamable_http_client(url)` and yields `(read, write)` (2-tuple), and result fields are snake_case (`server_info`, `structured_content`, `is_error`). FastMCP 4.2.0's `host_origin_protection` defaults to `False`, so a `Host: unfindable:8000` header is accepted. Unknown routes return 404 (`/docs` and `/openapi.json` checked); `GET /mcp` without a session returns 400.

## 3. Runs

Command pattern: `./.venv/Scripts/harbor.exe run -p <task> -a <agent> -o jobs --job-name <name> -n 1 -y`

| # | Task / agent | Expected | Actual `reward.json` | Result |
|---|---|---|---|---|
| 1 | `task` (shared) / `oracle` | 1 | `{"reward": 1, "pings": 1}`, 1m53s (includes first image builds) | **PASS** |
| 2 | `task` (shared) / `nop` | 0 | `{"reward": 0, "pings": 0}`, 27s | **PASS** |
| 3 | `build/s0-separate` / `oracle` | 1 (from evidence) | `{"reward": 1, "pings": 1}`, 61s | **PASS** |
| 4 | `build/s0-separate` / `nop` | 0 | `{"reward": 0, "pings": 0}`, 57s | **PASS** |
| 5 | `build/s0-tamper-shared` / `oracle` (attack) | 0 if safe | `{"reward": 1, "pings": 99}`, twice (v1 and v2 jobs) | **FAIL (attack succeeded)**: T14 demonstrated |
| 6 | `build/s0-tamper-separate` / `oracle` (attack) | 0 | `{"reward": 0, "pings": 0}`, twice (v1 and v2 jobs) | **PASS (attack blocked)** |
| 7 | `build/s0-no-network` / `oracle` | — | Harbor refused to start (exact text in §7) | **BLOCKED on this host** |
| 8 | OpenCode agent with a model | — | not run | **BLOCKED**: no paid API calls allowed (§5) |

Run 1 details (`jobs/s0-oracle-shared/task__oDY8fpc/`):
- `agent/mcp_ping.json`: `{"server": "unfindable", "tools": ["ping"], "ping_result": ["1"], "structured": {"result": 1}, "is_error": false}`
- `verifier/details.json` → `live_finalize`: `pings 1, boot_id badf7351…, finalize_calls 2, unauthorized_calls 2`. The collect hook was call 1 and the verifier was call 2. The two unauthorized calls are the probes.
- `trial.log`: `Collecting sidecar artifacts from services: ['unfindable']` / `Running collect hook in service 'unfindable': 'python /app/collect.py'` / `completed`.

## 4. State across the verifier boundary (B4.2)

**Shared mode (default).** The verifier runs `test.sh` in the same `main` container, and the agent's compose project is still running. The sidecar was the same process: the same `boot_id` in the collect-hook evidence and in the verifier's live call, and the counter kept its value. The environment is stopped only after the verifier finishes (`trial/single_step.py`).

**Separate mode.** Harbor collects artifacts, stops `main` first ("Stopping main service before sidecar evidence collection"), runs sidecar collect hooks, then **stops the whole agent environment**. It then starts a **fresh copy of the full compose project** for the verifier, sidecars included. Measured in run 3: the verifier's live call hit a new sidecar (`boot_id c1dcc76d…`, `pings 0`, uptime 8 s), while the evidence from the agent-phase sidecar said `boot_id 8d23fed4…`, `pings 1`. **In-memory sidecar state does not survive.**

What does carry over in separate mode:
- `[[verifier.collect]]` hooks run inside a named compose service after `main` is stopped. Their docstring says they exist "to snapshot runtime state (database contents, in-memory counters) into files".
- Artifacts with `service = "unfindable"` are pulled from the sidecar's own filesystem, then restored at their **source path** in the verifier container. `/evidence/finalize.json` appeared at `/evidence/finalize.json`.
- `/logs/artifacts/` from `main` is also copied, so it is agent-writable. The verifier must never trust it (see run 6 v2).

Cost: separate mode starts a second compose project, which added about 30 s per trial here (nop: 27 s shared vs 57 s separate).

## 5. OpenCode (B4.1, second half)

- Harbor 0.25.0 ships `opencode` and `opencode-v2` agents. Both declare `mcp_servers=True`; `opencode-v2` also forwards HTTP MCP headers (docs).
- From the source (`harbor/agents/installed/opencode.py`) and checked by instantiating the class, Harbor writes `~/.config/opencode/opencode.json` in `main` with exactly:
  ```json
  {"mcp": {"unfindable": {"type": "remote", "url": "http://unfindable:8000/mcp", "oauth": false}}}
  ```
  `streamable-http` and `sse` both map to `type: remote`. `headers` are not forwarded by `opencode`. We use none.
- Transport check, with no model and no API key in the container (`env | grep -ciE "api_key|anthropic|openai"` → `0`): `node:22-slim` on the same compose network as the sidecar, the config above, `opencode mcp list` → `✓ unfindable connected http://unfindable:8000/mcp`. Sidecar log: `POST /mcp 200`, `POST /mcp 202`, `GET /mcp 200`, `POST /mcp 200`. **Verified: OpenCode 1.19.5 speaks streamable HTTP to FastMCP 4.2.0.**
- Not verified: an OpenCode agent run that actually calls `ping` via an LLM. Credentials: `ANTHROPIC_API_KEY` exists at Windows User and Machine scope (value not read). `OPENAI_API_KEY` is not set. The spike forbids paid model calls, so this stays blocked until the event (AfterQuery credits). Command to run then: `harbor run -p spikes/s0-harbor/task -a opencode -m anthropic/<model> ...`
- Operational notes (source): the `opencode` agent installs Node via nvm and `npm i -g opencode-ai@<version|latest>` **at setup time inside `main`**, so it needs internet unless OpenCode is preinstalled in the image (`--ak skip_install=true`, or a matching version is reused). Its default API key variable is `OPENAI_API_KEY`. Model is passed with `-m provider/model`.

## 6. Isolation findings

Probes ran inside `main` during the oracle run (`agent/probes.json`). Token scans ran inside `main` during shared-mode verification (`verifier/details.json`).

| Check | Result |
|---|---|
| `main` env has the token | **No.** No `*TOKEN*`/`*SECRET*` names in `os.environ` or any `/proc/*/environ`. The verifier found the token value in **no** other process's environ and in **no** file outside `/tests` (runs 1–4) |
| Sidecar source in `main` filesystem | **No.** Content scan of 1,859 text files for sidecar markers found none. The only name hits were stdlib `http/server.py` and `xmlrpc/server.py` |
| `POST /admin/finalize` without token | **401.** Wrong token: **401** (sidecar counted `unauthorized_calls: 2`) |
| `main` can reach sidecar | **Yes.** `unfindable` → `172.24.0.2`, `/healthz` 200, MCP OK |
| Sidecar processes visible from `main` | **No** (separate PID namespace) |
| `/var/run/docker.sock` in `main` | **Not present** |
| Agent user | `uid 0` (root) by default |
| `/logs/verifier` during agent phase | Exists and is writable by the agent. Harbor itself `rm -f`s `reward.txt`/`reward.json` before running `test.sh` (`verifier/verifier.py::_remove_reward_files`), and our `test.sh` overwrites again |

### T14 attack (`tamper/solve.sh`), run as the "agent" with zero pings

1. Pre-write `/logs/verifier/reward.json` and `reward.txt` with reward 1.
2. Append `127.0.0.1 unfindable` to `/etc/hosts`.
3. Start `fake_sidecar.py` with `nohup setsid` on `127.0.0.1:8000`. It answers any POST with `{"reward":1,"pings":99}` and saves any `X-Verifier-Token` header.
4. (v2) Write forged `/evidence/finalize.json` and `/logs/artifacts/evidence/finalize.json`.

**Shared mode (run 5): attack succeeded.** The background process **survived from the agent phase into the verifier phase**. The edited `/etc/hosts` stayed. The verifier resolved `unfindable` → `127.0.0.1`, received the forged body, wrote `{"reward": 1, "pings": 99}`, and **sent the verifier token to the attacker** (`captured_token_file_matches: true`; `/tmp/captured_token` held the token). Signing the response with the token would not help either, because the attacker learns the key from the request header. Even with a nonce-MAC handshake, a root agent can still replace `/usr/local/bin/python3` or `/bin/bash` before the verifier runs. **Shared mode cannot be made trustworthy against a root agent.**

**Separate mode (run 6): attack blocked.** The verifier container is fresh: the original `/etc/hosts`, no background process, no agent-written `/evidence`. The reward came from sidecar-sourced evidence: `pings 0` → `{"reward": 0, "pings": 0}`. The forged `/logs/artifacts/evidence/finalize.json` was copied into the verifier (as documented), but it was ignored because `verify.py` reads only `/evidence/finalize.json`, which comes from the sidecar artifact.

Residual risks for separate mode (not tested):
- The agent can still call MCP tools in ways the sidecar accepts. That is by design.
- The agent can hit `/admin/finalize`, which is token-gated and returned 401.
- In the recommended design, the finalize logic runs only inside the sidecar via the collect hook. The token then never needs to leave the sidecar, and finalize can be bound to `127.0.0.1` or removed from HTTP entirely.

### Other source-level findings (read, not exercised)

- **Do not use `[environment].docker_image` without an `environment/Dockerfile` or `docker-compose.yaml`.** In that case Harbor uploads the whole `environment/` directory into the main workdir after start (`environments/base.py::_upload_environment_dir_after_start`). That would expose sidecar source.
- Harbor's base compose for `main` uses `context: ${CONTEXT_DIR}` = `environment/`. Our `.dockerignore` keeps `sidecar/` out of main's build context. Compose is invoked with `--project-directory environment/`, so `./sidecar` and `env_file` paths resolve there.

## 7. Windows-host problems

1. Docker Desktop was not running. `"/c/Program Files/Docker/Docker/Docker Desktop.exe" &` brought `docker info` up in under 5 s.
2. **`network_mode = "no-network"` (and therefore `allowlist`) cannot be used with the local Docker provider on this host.** Exact error:
   `ValueError: network_mode='no-network' is not supported by EnvironmentType.DOCKER environment. Environment providers must enforce the requested network policy or reject the task.`
   Cause: Harbor's egress control needs `CONFIG_NFT_FIB_INET`. Its probe (`alpine:3.23.4`, `zcat /proc/config.gz | grep -qE '^CONFIG_NFT_FIB_INET=[ym]'`) fails on the WSL2 kernel, which has `CONFIG_NFT_FIB=m`, `CONFIG_NFT_FIB_IPV4=m`, `# CONFIG_NFT_FIB_IPV6 is not set`, and no `NFT_FIB_INET`.
3. Line endings: the repo has `core.autocrlf=true` and no `.gitattributes`. I added `spikes/s0-harbor/.gitattributes` (`eol=lf`) so `test.sh` and `solve.sh` cannot be checked out with CRLF. The real environment needs the same.
4. Nothing else broke. All runs set `PYTHONIOENCODING=utf-8` as a precaution. `harbor lint` without it also worked; `harbor run` without it was not tried.

**Untested risk for no-network on Linux hosts:** with egress control enabled, Harbor puts `main` and every compose service without explicit `networks`/`network_mode` into the egress sidecar's network namespace (`network_mode: service:harbor-docker-egress-control-sidecar`). Local destinations are allowed (`fib daddr type local accept`), so `localhost:8000` would probably work. Whether the name `unfindable` still resolves is **unknown**. If the real harness runs agents with no-network or allowlist, this needs a test on a Linux host, possibly with `url = "http://localhost:8000/mcp"`.

## 8. Recommended Harbor configuration for the real environment

```toml
schema_version = "1.4"

artifacts = [
  { source = "/evidence/report.json", service = "unfindable" },
  { source = "/var/log/unfindable/trajectory.jsonl", service = "unfindable" },
]

[agent]
timeout_sec = 1800            # set after B4.4

[verifier]
environment_mode = "separate"  # required: shared mode was forged in run 5
timeout_sec = 120

[[verifier.collect]]
service = "unfindable"         # runs after main is stopped; agent cannot race it
command = "python -m unfindable_server.finalize --out /evidence/report.json"
timeout_sec = 60

[environment]
build_timeout_sec = 900
# network_mode: leave "public" unless the target harness is verified with no-network (section 7)

[[environment.mcp_servers]]
name = "unfindable"
transport = "streamable-http"
url = "http://unfindable:8000/mcp"
```

- `environment/docker-compose.yaml`:
  - `main.depends_on.unfindable.condition: service_healthy`
  - `unfindable` built from a local context (T16); healthcheck on `/healthz`
  - no shared volumes
  - per-build secret only via `env_file` (gitignored) or not at all
- `environment/.dockerignore` excludes the sidecar directory from main's build context. Never use `docker_image` without a Dockerfile.
- `tests/test.sh` reads **only** the sidecar artifact at `/evidence/report.json`, never `/logs/artifacts/**` (agent-writable). It writes `reward.json` atomically, with numeric values only, and on any error writes reward 0. In separate mode the verifier needs no token, so `tests/` should not ship one.
- Finalize: do it inside the sidecar process via the collect hook (CLI or `127.0.0.1`-only route). Remove `/admin/finalize` from the agent-reachable interface, or keep it token-gated with a constant-time comparison.
- Optional speed-up (untested): a `tests/Dockerfile` makes the separate verifier a standalone image, so it skips the pointless second sidecar. Tests must then be baked into that image.
- `.gitattributes` with `eol=lf` for every script that runs in containers.

Implications for other docs (not edited, outside this spike's write scope):
- `SECURITY_MODEL.md` T14: shared mode is **High** (demonstrated); separate mode + collect hook is **Low**. Mitigation (a) is now confirmed and should be mandatory; (b) HMAC with the shared token is insufficient in shared mode.
- §6 (stdio fallback) is not needed for the local Docker provider.
- ARCHITECTURE §3: the verifier does not run in `main` and does not call `/admin/finalize` over the network; the collect hook does it inside the sidecar.

## 9. OPEN_QUESTIONS B4

| ID | Answer | Status |
|---|---|---|
| B4.1 | **Harbor:** yes. Compose MCP sidecar over streamable HTTP works with Harbor 0.25.0 on the docker provider (runs 1–6). Per the docs, compose works natively on `docker`, `podman`, `ec2`, `islo`, `vercel`, and via DinD on `daytona`, `modal`, `gke`, etc. It is **not supported** on `e2b`, `runloop` and others. **OpenCode:** Harbor's `opencode` agent passes task MCP servers as `type: remote`, and OpenCode 1.19.5 connects (`connected`). **AfterQuery's harness:** which provider they use is unknown, so ask | Verified locally; harness unknown |
| B4.2 | Shared: state survives. Separate: fresh sidecars, state lost, but `[[verifier.collect]]` + `service`-scoped artifacts transfer it. Use separate + collect | Verified |
| B4.3 | Harbor reads `reward.json` first (falls back to `reward.txt`). Every key must be a finite number. All keys become metrics. `reward` is the 1-D convention (`min_reward` gates on it; the job summary shows a "Reward" column). A missing file raises `RewardFileNotFoundError`, a trial error rather than a 0. Which key AfterQuery ranks on is unknown, so ask; we propose `{"reward": <score>, ...numeric sub-scores}` | Harbor side verified; AfterQuery unknown |
| B4.4 | Unknown (external). Harbor side: `[agent].timeout_sec` (default none), `[verifier].timeout_sec` (default 600), CLI `--timeout-multiplier` | Unknown |
| B4.5 | Harbor's `nop` agent does literally nothing (`setup`/`run` are `pass`). It scored 0 here. "Stop-early" is not a Harbor built-in, so it is unknown. A team reference agent can be passed as `--agent module.path:ClassName` (CLI help), not tested | Partly verified |

## 10. Verified vs assumed

Verified by running:
- Runs 1–7 as tabulated.
- OpenCode `mcp list` connection.
- All isolation probes in §6.
- The Docker kernel probe result.

Verified by reading the Harbor 0.25.0 source, not exercised:
- Shared mode stops the environment after the verifier.
- `_remove_reward_files`.
- The `environment/` upload for prebuilt images.
- Egress-control netns sharing.
- The `opencode` install path and API key name.
- Reward JSON validation.

Assumed or unknown:
- AfterQuery's provider, network policy, limits, model and reward key.
- Behaviour on Linux hosts with no-network.
- A full LLM-driven OpenCode run.
- Whether `tests/Dockerfile` avoids the second sidecar.

## 11. Reproduce

```bash
cd spikes/s0-harbor
py -3.13 -m venv .venv && ./.venv/Scripts/python.exe -m pip install harbor==0.25.0 fastmcp==4.2.0
./.venv/Scripts/python.exe prepare.py            # new token + build/ variants
export HARBOR_TELEMETRY=0 PYTHONIOENCODING=utf-8
./.venv/Scripts/harbor.exe run -p task -a oracle -o jobs --job-name s0-oracle-shared -n 1 -y
./.venv/Scripts/harbor.exe run -p task -a nop -o jobs --job-name s0-nop-shared -n 1 -y
./.venv/Scripts/harbor.exe run -p build/s0-separate -a oracle -o jobs --job-name s0-oracle-separate -n 1 -y
./.venv/Scripts/harbor.exe run -p build/s0-separate -a nop -o jobs --job-name s0-nop-separate -n 1 -y
./.venv/Scripts/harbor.exe run -p build/s0-tamper-shared -a oracle -o jobs --job-name s0-tamper-shared-v2 -n 1 -y
./.venv/Scripts/harbor.exe run -p build/s0-tamper-separate -a oracle -o jobs --job-name s0-tamper-separate-v2 -n 1 -y
```
