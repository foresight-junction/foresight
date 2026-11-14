# Challenge: Break the Agent (AfterQuery)

Source: Junction dashboard + AfterQuery Discord posts (Ved, Sat 01:35). Read this before any task.

## The ask
Build an RL environment that challenges today's best agents, show real failure modes, and show the reward reflects real progress. We need: a clear goal, actions, a checkable reward, a frontier-agent run, and a stronger reference run we can reproduce.

## Starting points
The challenge lists these starting points: planning several steps ahead, exploring an unfamiliar system, using tools, managing limited resources, adapting when new information arrives. It says: "These are prompts, not required features." Teams should "think about what better play looks like, how you would measure it, and whether an agent could increase its score without getting better at the task".

- **Planning ahead:** harm lands hours later. Fatigue and the budget run over 72 hours, and the 12-hour handover tail scores what the agent leaves behind.
- **Exploring an unfamiliar system:** about 20% of triage labels are wrong and only `assess` shows true acuity. Quiet deterioration shows only on a re-assess.
- **Using tools:** 8 read tools and 13 act tools over MCP.
- **Limited resources:** 15 beds, staff fatigue, one 72-hour budget, 2 ambulances.
- **Adapting to new information:** sick calls, a CT breakdown and surges, each with a precursor in `notices`.

Better play means lower patient harm. We measure it as summed per-patient harm (M1 to M4) from the hospital event log. The score cannot be pumped without better play, because only patient outcomes are scored and trivial policies are anchored at 0.

## Required stack (not optional)
- **Harbor task**: `instruction.md`, `task.toml`, `environment/Dockerfile`, `tests/`, `solution/`.
- **Harness**: OpenCode. `harbor run -p ./ed72 -a opencode -m <provider/model>`.
- **Reward**: the verifier writes ONE number in [0,1] to `/logs/verifier/reward.txt`. Partial credit is welcome.
- **No credits from AfterQuery.** Use our own OpenAI / Anthropic / Google keys. Modal for compute.

## Must be in the submission
- At least one Harbor run log with its score (a model playing the environment).
- A short README: what the agent has to do, why it is hard, how we score it. Write the core by hand.
- Demo video with a playthrough. Deadline: **Sun 15 Nov 10:00**.

## Rubric (100 p)
| Criterion | Points | Full points | Zero |
|---|---|---|---|
| The gap | 30 | Frontier agent consistently below our reference run; both reproducible across repeated runs | No measurable gap, or it cannot be reproduced |
| Meaningful difficulty | 30 | We can explain the agent's main mistakes and tie them to decisions; info and tools to do better are available to it | Gap comes from withheld info, trick wording, impossible timing, broken tools |
| Reward integrity | 25 | Holds up when judges try to exploit it; do-nothing and stop-early earn ~0; playing well is the best way to score | Any exploit or task-avoiding strategy beats honest play |
| Craft | 15 | Rules make sense for the setting; one command from the README reproduces our results | Only works in our demo |

Tiebreaker: a smaller model improving after training on experience from our environment.

## How judges run it
10-minute demo. Then they rerun with the standard harness: **our reference run, three agent runs, a do-nothing baseline, a stop-early baseline**. Then **15 minutes hunting reward exploits**. Scores come from those runs, not from our slides.

## Open questions for Daksh / Ved (answers go here; Q1 and Q2 answered by our own spike)
1. Is a docker-compose sidecar allowed, so the simulator state lives outside the agent's container?
   **Answered (Harbor side):** yes. Kostiantyn's spike ran a compose MCP sidecar over streamable HTTP on Harbor 0.25.0 (`docs/unfindable/SPIKE_S0_RESULTS.md` on branch `kostiantyn/env-unfindable-slice`). Which provider the judges use is still unknown.
2. Does OpenCode in Harbor register MCP servers from `[[environment.mcp_servers]]` in `task.toml`? If not, is a CLI tool fine?
   **Answered (transport only):** yes. Harbor's `opencode` agent registers the server and OpenCode 1.19.5 connects (same spike). No model run yet. Fallback if it fails: the `ward` CLI.
3. Which model do judges use for the three agent runs? Timeout and turn limits?
4. How is the stop-early baseline produced, by them or by us?
5. One task or several seeds? Is the gap a mean over runs?
6. Is a scripted `solution/solve.sh` accepted as the reference run?
7. Does the agent container have internet during judging?

## Known risks
- OpenCode installs over npm when the agent is set up, so the `main` container needs internet, or OpenCode must be preinstalled in the image. This ties to Q7.
