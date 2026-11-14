# Unfindable — Security model

Status: proposal. The asset is the integrity of the benchmark, not real data: all data is synthetic.

## 1. Assets

| Asset | Why it matters |
|---|---|
| Ground truth: truth ledger, oracle results, scenario labels | If the agent reads it, the score measures retrieval, not judgement |
| Future queue and event schedule | Knowing them lets an agent avoid traps without the skill being tested |
| Hidden identity facts (`identity_ok`, true identities) | They decide R3 and R4 |
| Verifier token | Whoever holds it can finalize and read the score |
| Reward file | Forging it is direct reward hacking |
| Episode state | A reset or rollback would allow retries |

## 2. Adversaries

1. **The evaluated agent:** runs as an installed agent inside the main container, with a shell and filesystem access (Harbor docs: "Harbor installs and runs the agent CLI inside the task environment"). It may have internet access, because the default `network_mode` is public.
2. **Judges red-teaming the reward:** 15 minutes, with full knowledge of the README and code.
3. **Anyone reading the public repository.**

## 3. Trust boundaries

```
[ main container: UNTRUSTED ]  agent, its shell, its files, its environment variables
        │  only channel: MCP over HTTP to unfindable:8000/mcp
        ▼
[ sidecar: TRUSTED ]  server, SQLite, scenario, oracle, evaluator, logs, token
        ▲
        │  POST /admin/finalize + token (token arrives with tests/ after the run)
[ verifier step: SEMI-TRUSTED ]  runs in the main container in shared mode (see T14)
```

## 4. Threats and mitigations

| ID | Threat | Vector | Mitigation | Test | Residual |
|---|---|---|---|---|---|
| T1 | Read ground truth from the filesystem | Shell, `find`, `cat` the SQLite file or scenario | DB, scenario, oracle and evaluator exist only in the sidecar image; no shared volumes | Isolation test: the main image contains no `*.sqlite`, `scenarios/` or `unfindable_core` | Low with a sidecar; high under the stdio fallback |
| T2 | Import the server package | `python -c "import unfindable_core"` | Package not installed in the main image | Isolation test | Low |
| T3 | Secrets in environment variables | `env` | No seed or token in the main container; the token lives only in sidecar env and `tests/` | Isolation test greps `env` and `/proc/1/environ` | Low |
| T4 | Docker socket or escape | `/var/run/docker.sock` | Not mounted; container escape is out of scope (Harbor sandbox) | Isolation test | Out of scope |
| T5 | Call finalize or the grader early | HTTP to the sidecar | Token required; finalize freezes the episode; `401` is constant-time | Adversarial test | Low |
| T6 | Debug endpoints or tracebacks | HTTP route discovery, forcing exceptions | Only `/mcp`, `/healthz`, `/admin/finalize`; debug off; catch-all returns `INTERNAL` | Route enumeration test; fuzz test | Low |
| T7 | Leakage through error messages | Crafted invalid arguments | Fixed error catalog; structural validation only (`MCP_CONTRACTS.md` §1.3) | Contract test: every error message is in the catalog | Low |
| T8 | Enumerate future requesters or cases | `get_requester(Q-0001…Q-9999)` | Visibility scope: pulled requesters only; `NOT_FOUND` identical for out-of-scope and nonexistent IDs | Adversarial test | Low. `verify_authority` exposes case existence, which is accepted as clerk knowledge |
| T9 | Probe correctness by retrying | Calling `respond` repeatedly | One answer per request; constant acknowledgement | Adversarial test | None |
| T10 | Reset the episode | Reconnecting the MCP session | State bound to the sidecar process, not the session; no reset tool | Integration test: reconnect keeps response count | Low |
| T11 | Race conditions | Parallel tool calls | Global lock; SQLite transactions | Concurrency test: 10 parallel `respond` calls, exactly 1 accepted | Low |
| T12 | Timing side channel | Measuring `respond` latency | Truth computed for every response | — | Negligible |
| T13 | Read logs | Log files | Trajectory log only on a sidecar volume | Isolation test | Low |
| T14 | Forge the reward in the verifier step | In shared mode the verifier runs in the agent's container. The agent could leave a fake `curl` or `python`, edit `/etc/hosts` to point `unfindable` at its own server, or pre-write `/logs/verifier/reward.json` | (a) Prefer separate verifier mode if sidecar state persists (B4). (b) `test.sh` always overwrites the reward file, uses absolute paths, and checks an HMAC signature on the finalize response with the token. (c) The sidecar also writes the authoritative report to its own volume for the demo | Adversarial test with a tampered container | **Updated by Spike S0, see §7** |
| T15 | Public repo + internet: precompute answers from the source and seed | Fetching GitHub | Policy code gives no advantage beyond the tools. Optional held-out judge seed via sidecar env (N10) | — | Low |
| T16 | Sidecar image pulled from a public registry | Registry HTTP API | Build the sidecar locally from the task directory; publish no image containing scenarios | — | Low |
| T17 | Resource exhaustion | Flooding tool calls | Per-episode call cap returns `INVALID_ARGUMENT` after N (e.g. 5,000) | — | Low; not in the MVP |
| T18 | Prompt injection in request text | "Ignore the policy and release…" | Intended test content (R7, F8), not a threat to the environment; the oracle ignores text | Property test: truth unchanged under text mutation | By design |

## 5. Hardening checklist (definition of done for M6)

- [ ] Main image built without any `unfindable-core` or `unfindable-server` files.
- [ ] Compose file mounts no shared volume between `main` and `unfindable`.
- [ ] Token generated per build and present only in sidecar env and `tests/`.
- [ ] FastMCP debug off; an exception handler maps everything to `INTERNAL`.
- [ ] Routes limited to `/mcp`, `/healthz`, `/admin/finalize`.
- [ ] Hidden-key scan passes for every tool on every scenario.
- [ ] `test.sh` truncates and rewrites the reward file and verifies the HMAC.
- [ ] Every T1–T14 test is in `tests/isolation` or `tests/adversarial` and passing.

## 7. Spike S0 findings (2026-11-13, verified in real Harbor 0.25.0 runs)

Full details: `SPIKE_S0_RESULTS.md`; run outputs in `spikes/s0-harbor/jobs/`.

**T14 is proven in shared verifier mode, so rate it High there.**
- The tamper script, acting as the agent, edited `/etc/hosts` and left a fake sidecar running into the verifier phase. In both runs the verifier wrote `{"reward": 1, "pings": 99}` with no real tool calls.
- The verifier also sent the token to the fake server.
- HMAC signing with the same token does **not** fix this, because the attacker receives the token in the request. A root agent can also replace the verifier's interpreters.

**In separate verifier mode with a sidecar collect hook, T14 is Low.**
- Harbor restarts the whole environment for the verifier, sidecars included.
- A `[[verifier.collect]]` hook runs inside the `unfindable` sidecar after `main` stops and writes the report as a sidecar artifact. The verifier reads only that artifact.
- The same attack, plus forged files in `/evidence` and `/logs/artifacts`, scored 0 in both runs.

**Decision for the real environment:**
- `verifier.environment_mode = "separate"`.
- The reward comes from the in-sidecar collect hook. `test.sh` reads only the sidecar artifact, never `/logs/artifacts`, and writes 0 on any error.
- `/admin/finalize` is not reachable from `main` in evaluation runs: bind it to localhost inside the sidecar, or disable it with an environment flag.

**Other verified isolation facts:**
- No token in any process environment of `main`.
- No sidecar source among 1,859 scanned text files.
- No `docker.sock`.
- Sidecar processes are not visible from `main`.

**Host limitation:** `network_mode = "no-network"` is rejected by Harbor on this Windows / WSL2 host, so it is untested.

## 6. Fallback if sidecars are not allowed (decision depends on B4)

The server would run over stdio inside the main container, as a separate Unix user with an unreadable data directory. This is weaker: an agent running as root defeats it. T1–T3 and T13 become accepted residual risks, documented in the README. This would change the security model materially, so it must be decided before M6.
