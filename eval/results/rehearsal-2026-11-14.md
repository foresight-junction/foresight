# Pipeline rehearsal, Sat 2026-11-14 (issue #17)

Goal: run the real sim, tool server, collect hook, verifier and packaging through Harbor before
the first model run. No model keys were used. Windows 11, Docker 29, Harbor 0.25.0.

## Integration tree

A detached throwaway worktree off `origin/main` (never pushed), merged with
`git -c user.name=integration -c user.email=integration@local merge --no-edit`:

| Branch | Commit | Issue |
|---|---|---|
| main | c62135c | |
| kostiantyn/reward-episode-end (stacks env-world, env-sim-core, reward-scorer, reward-verifier) | b1bf19f | #46 #48 #47 #45 |
| kostiantyn/env-crn | cdf34c3 | #44 |
| mykhailo/env-tool-server | 90db124 | #5 |
| yehor/harness-task-skeleton | f12af74 | #22 |

All merged without conflicts. `kostiantyn/ref-policy` (#16) has no `solve.sh` yet, so the tree
carries a placeholder severity-first policy (`solution/solve.sh` + `policy.py`, drives `ward`
from the `main` container). Placeholder `environment/workspace/HANDBOOK.md` and `instruction.md`
were added in the tree only (#7 not merged yet).

## Commands

```bash
export HARBOR_TELEMETRY=0
uvx --python 3.12 --from harbor==0.25.0 harbor run -p ed72 -a nop    -o ../jobs --job-name ed72-rehearsal-nop    -n 1 -y
uvx --python 3.12 --from harbor==0.25.0 harbor run -p ed72 -a oracle -o ../jobs --job-name ed72-rehearsal-oracle -n 1 -y
```

## Results (seed 42)

| Agent | reward.txt | O | T | W | B | Tool calls | Runtime | Exceptions |
|---|---:|---:|---:|---:|---:|---:|---|---:|
| nop | 0.000000 | 0 | 0 | 1 | 1 | 0 | 3m 12s | 0 |
| oracle (placeholder policy) | 0.773134 | 0.794 | 0.690 | 1 | 1 | 144 | 8m 59s | 0 |

The oracle's live reward equals an offline replay of the same policy on `Simulation(generate_world(42))`
exactly (0.773134), so server, log, collect replay and verifier agree. Oracle totals: 257 arrived,
235 discharged, 11 in bed at end, 11 died, 0 left, 0 diverted. `ended: tick_143`.

Trial log excerpt (both runs):

```
Stopping main service before sidecar evidence collection
Running collect hook in service 'hospital': 'python /app/collect.py'
Collect hook in service 'hospital' completed
```

One `ward step` round trip (new MCP session each call) takes about 3.5 s on this laptop, so a
144-tick episode costs about 8.5 minutes of tool latency alone, before any model time.

## Glue findings

1. **#22 packaging, line endings.** With `core.autocrlf=true` (Git for Windows default) `ward`,
   `hospital/start.sh` and `tests/test.sh` check out with CRLF; the shebangs then fail in Linux
   containers. Fix used: repo-root `.gitattributes` with `* text=auto eol=lf` (or at least
   `*.sh` and `ed72/environment/ward` as `eol=lf`).
2. **#7 handbook.** `ed72/environment/workspace/HANDBOOK.md` and `ed72/instruction.md` are required
   by both Dockerfiles and by Harbor; the build fails without them. Placeholders used.
3. **#16 solution.** No `ed72/solution/solve.sh` yet, so `-a oracle` cannot run on main.
4. No changes needed to #5 server/ward, #45 collect/verifier, #48 sim, or the #22 Dockerfiles,
   compose file and `task.toml`.

## Later heads

After the run the tree also merged cleanly with main 9d4b573, reward-episode-end 5e75484,
reward-verifier 6f2c400 and env-tool-server 56f75af (tree 139bff1). The offline check still gives
nop 0, and a second Harbor run (`ed72-rehearsal-oracle-2`) gave reward 0.773134 again, 0 exceptions, 7m 42s.
