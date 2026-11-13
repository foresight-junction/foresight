# Deep dive: Break the Agent (AfterQuery)

## Summary

Build one environment (a task, tools and a checkable reward) where a frontier agent reliably scores below a reference run we can reproduce, and where judges cannot hack the reward in 15 minutes. AfterQuery's own published work (StoreBench) has the same shape: a long-horizon operator simulation, scripted anchor policies, a reward built to resist hacks, and deterministic replay. Copying that playbook at hackathon scale is the safest path. **Verdict: a good pick for a Python-strong team that enjoys simulation design and attacking its own code, and does not need a flashy UI.** It is a poor pick if the team wants a consumer product or a visual demo. The work-trial prize is a real bonus.

## Who AfterQuery is / what the harness likely is

- YC W25, San Francisco. Sells expert human data, tool-calling RL environments (real APIs, MCP servers), computer-use environments and rubric/verifier-based RL to frontier labs (verified, products page). Benchmarks: FinanceQA (frontier models "fail ~50% of professional tasks"), UI-Bench, App-Bench.
- **StoreBench** (AfterQuery GitHub org, arXiv 2610.10942): the agent runs an apparel store with 29 merchant tools. Reward = 0.7 business + 0.2 reliability + 0.1 continuity. Business is normalised so the better of the *do-nothing* and *absentee* anchors scores 0 and scripted heuristics set the scale. The best model passed 49% of cells, while a scripted "smart-triage" heuristic passed 97%. GRPO on Qwen3.5-27B raised held-out composite from 0.136 to 0.373. One run used the Claude Code harness. This is close to a template for what the judges want.
- **Harness: probably Harbor (unverified).** Harbor comes from the Terminal-Bench team. A task is `instruction.md`, `task.toml`, `environment/Dockerfile` (or docker-compose), `solution/solve.sh` and `tests/test.sh`. The test script writes `/logs/verifier/reward.txt` or `reward.json` (verified, Harbor docs). Harbor's agent enum includes `oracle` (runs solve.sh), `nop` (does nothing), `claude-code`, `codex`, `gemini-cli` and `terminus-2`. Its environments include `modal` (verified in source). The judging list (reference run, 3 agent runs, do-nothing) maps one-to-one onto oracle, `-a <agent>` x3 and nop. "Stop-early" has no built-in agent (unverified how they run it).
- Other formats it might be: Prime Intellect `verifiers`, OpenEnv, Inspect AI, or an MCP tool server. Ask on day one.

## What already exists

| Area | Benchmarks | State late 2026 (secondary sources, unverified numbers) |
|---|---|---|
| Coding | SWE-bench Verified, SWE-bench Pro, Terminal-Bench 2.x | Verified is saturated and retired by OpenAI; Terminal-Bench 2 top scores around 80% |
| Tool/customer service | tau-bench, tau2, AppWorld | Mostly high scores |
| Web/OS | WebArena, OSWorld-Verified, OSWorld 2.0 | OSWorld 2.0 (long-horizon) still low |
| Research/QA | GAIA, MLE-bench | GAIA near ceiling |
| Games/novelty | BALROG, TextArena, ARC-AGI-3 | ARC-AGI-3 launched with frontier models under 1%, humans 100% |
| Long-horizon business | Vending-Bench 2, StoreBench | Large variance across runs; models below scripted heuristics |
| Finance | FinanceQA (AfterQuery) | About 50% failure |

The pattern: short, fully specified tasks are saturated. Gaps remain in **long-horizon consistency, acting under partial information, and discovering rules through experiments**.

## Gaps / openings

Cheap to simulate in Python and still hard for frontier agents:
- Long horizons with delayed consequences (lead times, cash flow, compounding errors).
- Information that exists but must be gathered actively within a budget (probes cost something).
- Mid-episode changes: new constraints, supplier failures, shocks.
- Verifying before committing, and recovering from one's own earlier mistakes.
- Multiple parties with private information (negotiation, procurement).

Key trap: in a terminal harness the agent can write code. Anything a solver can crack in one pass (pure scheduling, puzzles) gives no gap, because the agent will just `pip install ortools`. The difficulty has to come from interaction over time, not from computation.

## Reward hacking and how to resist it

Known exploits: editing or overwriting tests, a `conftest.py` that forces passes, wrapping `curl`/`pip` so the grader's dependencies return fake output (Berkeley RDI reached 100% on Terminal-Bench and SWE-bench Verified without solving tasks), writing `reward.txt` directly, reading answer files or simulator source, special-casing tests, monkeypatching time (o3 on RE-bench), state recording, and stopping early. ImpossibleBench found Claude models cheat mostly by editing tests, and GPT-5/o3 use all four categories.

Design rules:
1. **Keep authoritative state out of the agent's reach.** Run the simulator as a separate compose service. The agent only gets HTTP or CLI calls, and the verifier reads the server's event log, not files in the agent container.
2. Verifier uses its own interpreter and never calls tools from the agent's PATH.
3. Score outcomes only (final net assets, constraints met). Never score "actions taken" or "files written".
4. Normalise: `score = clip((agent - max(do_nothing, absentee)) / (reference - anchor), 0, 1)`. Fast-forward any unplayed days with null actions, so stopping early scores like doing nothing for the rest.
5. A hard gate: violating a constraint (overdraft, missed contract) multiplies the score down.
6. Fuzz the sim's economics with a random agent and an adversarial script (buy/sell arbitrage loops, negative quantities, float overflow, reset or undo abuse). Simulator loopholes are the most likely judge exploit.
7. No LLM judge in the reward (prompt-injectable).
8. Seeded, deterministic replay, so judges can recompute every score from the log.

## Environment ideas (ranked)

| # | Idea | Reward / anti-hack | Why agents fail | Reference run | Build (40h) |
|---|---|---|---|---|---|
| 1 | **Distributor for 30 sim days**: wholesale perishables. Tools: inventory, demand history, supplier quotes, orders, pricing, `advance_day` | Normalised net assets, server-side ledger, unplayed days fast-forwarded | Ignores lead times and spoilage, does not notice an unreliable supplier in the history, panics after shocks, quits mid-horizon | Scripted (s,S) policy plus moving-average forecast, using only the tool API | Medium |
| 2 | **Procurement negotiation**: 4 scripted suppliers with private reservation prices and structured offers | Surplus vs reference, contract validity gate, parser accepts only structured offers (no injection) | Anchors on first offer, reveals budget, takes deals early | Scripted bidding strategy | Low-Med |
| 3 | **Black-box process tuning**: reactor/greenhouse sim, every experiment costs budget, commit one setting at the end | Yield of the committed setting vs optimum, normalised against the default setting | Poor experiment design, overfits noise, stops exploring too early | Scripted Bayesian optimisation or grid search with the same budget | Low (small gap risk: the agent may write BO itself) |
| 4 | **Month-end ledger reconciliation** with planted discrepancies and new transactions arriving mid-episode | Hidden ground-truth diff, penalty for each false correction | Over-corrects, skips checks, declares done too early | Rule-based matcher using only the data the agent can see | Medium |
| 5 | **Clinic roster with change requests** arriving by "email" during the episode | Hard constraint validator x soft objective vs CP-SAT | Misses constraints stated in prose, breaks old constraints when applying new ones | CP-SAT on the parsed constraints | Medium (solver risk, see Gaps) |

Notes for #1, the recommended idea:
- Observations are JSON from a CLI (`shop status`, `shop quote`).
- Make a 15 to 20 minute episode version for judges to rerun live, roughly 150 to 300 tool calls per run (unverified cost; depends on the model). Ship 3 seeds.
- Demo plan (10 min): show the trajectory diff (agent vs reference) on a chart of cash and inventory over time, point to 2 or 3 explained failure moments, run nop and stop-early live, then let judges attack the sim.
- Side prizes: Harbor `--env modal` for parallel runs on Modal sandboxes, plus Modal or Verda GPUs for the stretch goal. Codex fits too: it can be one of the evaluated agents and a build tool.

## Stretch goal feasibility

Realistic only in a reduced form. The cheapest version is SFT (behaviour cloning) of a ~4B model (e.g. Qwen3-4B) on reference-policy trajectories from a short variant, then a comparison against the base model. That takes a few GPU-hours on one H100. GRPO is possible with TRL's `environment_factory` (verified in the TRL OpenEnv docs) or OpenPipe ART, but it needs a base model with non-zero success. ART's FAQ says roughly 30% (unverified). Budget one person for about 8 hours, starting only once the core environment is frozen. StoreBench shows the claim is credible, but they had lab compute.

## Risks

- Frontier agent too good: it writes its own policy script and closes the gap. Mitigate with partial information and mid-episode shocks, and calibrate early (Saturday morning).
- Variance: 3 agent runs must all land below the reference. Pick difficulty so the agent's best run is still clearly lower.
- Judges may call the reference "unfair" if it uses hidden state. The reference must use only the agent's tools and information.
- Harness mismatch: a wrong task format costs hours.
- Cost and wall-clock time of long episodes. Judges cannot rerun a 2-hour run.
- Docker on judge machines (ARM vs x86) and network access.
- A loophole in the sim's economics found by judges costs 25 points.

## Uncertainties

The harness format, the model and agent judges will run, the credit budget, whether one task or a dataset is expected, how "stop-early" is implemented, how the gap is computed (mean? per seed?), and whether a sidecar container and a hidden simulator source are allowed.

## Questions for AfterQuery (prioritised)

1. Is the standard harness Harbor (task dir, `test.sh` writes `reward.txt`)? If not, what format?
2. Which agent scaffold and model will judges run? Is internet access on?
3. Credits per team, max turns and timeout per run?
4. Is a scripted `solve.sh` reference acceptable? Must it use only information the agent can see? Is a human run OK?
5. How is the stop-early baseline produced, by us or by them?
6. How is the gap measured: continuous reward in [0,1] or pass/fail, mean of 3 runs?
7. One task, or several tasks/seeds?
8. Are multi-container environments (a simulator service) allowed?
9. Does hiding simulator internals count as "withheld information" if the rules are documented?
10. For the stretch goal, any GPU credits or a preferred small model?

## Sources

- https://afterquery.com/products
- https://github.com/AfterQuery/storebench
- https://arxiv.org/abs/2610.10942
- https://www.afterquery.com/leaderboard/finance-arena
- https://appbench-ai.pages.dev/blog
- https://github.com/laude-institute/harbor
- https://docs.harborframework.com/tasks/overview
- https://raw.githubusercontent.com/laude-institute/harbor/main/src/harbor/models/agent/name.py
- https://rdi.berkeley.edu/blog/trustworthy-benchmarks-cont/
- https://arxiv.org/html/2510.20270v1 (ImpossibleBench)
- https://arcprize.org/blog/arc-agi-3-launch
- https://andonlabs.com/evals/vending-bench-2
- https://www.codesota.com/benchmark/terminal-bench
- https://huggingface.co/docs/trl/en/openenv
- https://github.com/OpenPipe/ART
- https://primeintellect.ai/blog/verifiers-v1
