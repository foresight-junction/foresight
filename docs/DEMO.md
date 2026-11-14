# ED-72 demo script (10 minutes)

For the live demo to the judges and for the demo video. Status: draft (#25). The hook and the close are for a human to write. The model walkthrough and gap discussion need the run matrix (#18) and failure analysis (#19).

The judges' rubric is in `docs/CHALLENGE.md`: the gap (30), meaningful difficulty (30), reward integrity (25), craft (15). Each segment below says which criterion it is for.

## Timing

| Start | Length | Segment | Rubric |
|---|---|---|---|
| 0:00 | 0:40 | 1. Hook (human) | |
| 0:40 | 1:10 | 2. Setup: the department and the tools | Difficulty |
| 1:50 | 1:10 | 3. A `harbor run`, live start then saved trial | Craft |
| 3:00 | 2:00 | 4. One agent episode, through its log | Difficulty |
| 5:00 | 1:00 | 5. The score breakdown | Integrity |
| 6:00 | 1:15 | 6. A cheat attempt that fails | Integrity |
| 7:15 | 1:15 | 7. Results | Gap |
| 8:30 | 0:45 | 8. Close (human) | |
| 9:15 | 0:45 | Buffer for questions or a slow terminal | |

## Before the demo

- [ ] `make eval` has finished on the final code and `eval/results/summary.md` is current.
- [ ] One agent trial is picked for segment 4: the same trial the README links as its run log. Use the [seed-42 Gemini calibration](../eval/results/2026-11-14-gemini-seed42/README.md).
- [ ] Open the chosen trial’s `agent/trajectory.json`, `verifier/reward.txt` and `verifier/score_full.json`. These files cover the walkthrough. The frozen task collects the report while the raw simulator log stays in the hospital container.
- [ ] Terminal open in the repo root, font at least 18 pt, with these files ready in editor tabs: `docs/SPEC.md` §3, the trial's `verifier/score_full.json`, `eval/results/summary.md`.
- [ ] `.env` is closed and never shown. Don't run `env` or `cat .env` on screen.

## 1. Hook (0:00, 0:40)

<!-- HUMAN: write the hook (2-3 sentences, said out loud). Material:
- An emergency department with fewer staff than beds, for 72 hours, where every 30 minutes someone decides who gets a bed and who rests.
- The agent sees everything about the present and nothing about the future.
- Frontier agents score below a short scripted policy (only once #18 confirms it; otherwise say what was measured).
-->

## 2. Setup (0:40, 1:10)

Say:
- 144 ticks of 30 minutes, 08:00 day 1 to 08:00 day 4. 17 beds: Resus 3, Acute 8, Fast-track 6. 6 doctors and 9 nurses, which is not enough to cover every bed.
- Fatigue builds on shift; at 90 a person faints for 10 ticks. €12 000 budget for agency staff and a CT repair.
- Four events: staff sickness and a CT breakdown with no warning, a flu wave and a bus crash with a warning.
- Three tools: `rules`, `observe`, `step(actions)`. Five actions: `admit`, `assign`, `agency`, `repair`, `divert`.

Show what the agent sees at tick 0. This runs the simulator in-process on a demo seed and works on `main` today. Every command in this script starts from the repo root; the subshell keeps it there:

```bash
(cd ed72/environment/hospital && uv run python -c "
import json
from ed72_sim.world import generate_world
from ed72_sim.engine import Simulation
sim = Simulation(generate_world(7), log_path='/tmp/ed72-demo.jsonl')
print(json.dumps(sim.observe(), indent=1))
")
```

Point at `waiting`, `beds` (every bed `null`), `staff` (everyone in `rest` at fatigue 0) and the empty `warnings`.

## 3. A `harbor run` (1:50, 1:10)

Export the selected provider key, and set `ED72_MODEL` and `ED72_KEY_NAME` as shown in the README. Start a run live:

```bash
uvx --python 3.12 --from harbor==0.25.0 harbor run -p ed72 -a opencode -m "$ED72_MODEL" \
  --api-key-name "$ED72_KEY_NAME" --ak version=1.19.5 --agent-setup-timeout-multiplier 4
```

Say: the agent's container holds only the handbook and the `ward` CLI. The simulator, the seed and the scorer are in the `hospital` sidecar. A full episode is 144 `step` calls, so leave it running and switch to the trial picked under "Before the demo". Once a complete OpenCode run is available, use its measured runtime.

## 4. One agent episode (3:00, 2:00)

Open the saved [Gemini trajectory](../eval/results/2026-11-14-gemini-seed42/trajectory.json) and identify two or three decisions from #19. For each, show the tick, the latest observation the agent had, and its next actions. In `verifier/score_full.json`, match affected patients by ID and show their final outcomes or first covered ticks. Use the corresponding handbook rule to explain the available action. Compare with the reference at the same seed when the evidence supports it.

## 5. Score breakdown (5:00, 1:00)

Open the trial's `verifier/score_full.json`. Show:
- `O`, `T`, `W`, `B` and the formula `Score = 60·O + 20·T + O·(10·W + 10·B)`, `reward = Score / 100`.
- `totals`: arrived, discharged, died, left, never admitted, faints.
- `failures`: the F-code counts. They do not change the reward.
- `ended`: `tick_143` if the agent played to the end.

Say: the score is computed only from the hospital's event log, after the agent stops. No LLM judge. `reward.txt` holds the one number Harbor reads.

## 6. A cheat attempt that fails (6:00, 1:15)

Show the exploit baselines (`eval/baselines/`, works on `main` today). Each one tries one shortcut through the same tools an agent has:

```bash
(cd eval/baselines && PYTHONPATH=../../ed72/environment/hospital uv run python -m ed72_baselines.table 1 2 3)
```

Pick one row and explain why it loses, using SPEC §11:
- `fill_beds_at_last_tick`: the 0.3 end-of-episode credit needs at least one covered tick. Patients held back to fill late kept facing waiting hazards and count as late in T.
- `divert_all`: every diverted patient loses 0.7 of its weight and is late.

Read the numbers off the screen; don't quote them from memory.

Backup if time allows: the leak tests, which check every tool result for future arrivals, unannounced events, the seed and score values.

```bash
(cd ed72/environment/hospital && uv run --with pytest pytest -q tests/test_firewall.py)
```

The [round 1 report](REDTEAM.md) links each tested probe to its regression check. Round 2 is tracked in #14.

## 7. Results (7:15, 1:15)

Show the seed-42 calibration first. Reference reward 0.989617, Gemini reward 0.811712, and do-nothing reward 0.000000. The in-process reference gives the same seed-42 reward. On seeds 1–5, the reference averages 98.4 points and the reactive proxy averages 61.8.

Once #18 is available, show the per-seed model means and ranges and compare each with the matching reference. Keep the confirmed baselines on screen if the matrix is still pending.

## 8. Close (8:30, 0:45)

<!-- HUMAN: write the close (2-3 sentences). Material:
- One line on what the agent gets wrong most, from #19.
- One line on why the score can't be gamed: outcome-weighted, computed from the hospital's log, shortcuts played as baselines.
- How to reproduce: one command, `make eval`, from the README.
-->

## Recording checklist (demo video)

- [ ] Record after the rules freeze and once the results are final. No code changes after Sun 09:00; the video must be submitted by Sun 10:00.
- [ ] A teammate times one full run-through, under 10:00 (the issue's done-when). Time: `____`, by `____`.
- [ ] Screen at 1920×1080, terminal font at least 18 pt, notifications off, other apps closed.
- [ ] No keys on screen: no `.env`, no `env`, no shell history that contains a key.
- [ ] Say once that all patients, staff and records are synthetic.
- [ ] The commands on screen match the README exactly.
- [ ] Microphone checked with a 10-second test clip.
- [ ] Watch the export once end to end before uploading. Upload it with link access for anyone who has the link, and paste the link into the submission.

## Submission checklist

`docs/CHALLENGE.md` lists what must be in the submission and the required stack. The Junction form's own fields are not recorded in the repo. TODO(human): copy the form's fields here from the Junction dashboard.

Must be in the submission (CHALLENGE "Must be in the submission"):
- [ ] At least one Harbor run log with its score, a model playing the environment. Linked from the README Results section.
- [ ] A short README: what the agent has to do, why it is hard, how we score it, with the core written by hand. Check: `grep -n -e 'HUMAN:' -e 'TODO(' README.md` prints nothing.
- [ ] Demo video with a playthrough (recording checklist above).
- [ ] Submitted before Sun 15 Nov 10:00.

Required stack (CHALLENGE "Required stack"):
- [ ] Harbor task with `instruction.md`, `task.toml`, `environment/Dockerfile`, `tests/`, `solution/`. Check: `ls ed72/instruction.md ed72/task.toml ed72/environment/Dockerfile ed72/tests ed72/solution`.
- [ ] OpenCode harness: `harbor run -p ./ed72 -a opencode -m "$ED72_MODEL"` finishes with a reward.
- [ ] The verifier writes one number in [0, 1] to `/logs/verifier/reward.txt`.

What judges rerun (CHALLENGE "How judges run it"):
- [ ] On a fresh clone, `make eval` runs the reference, do-nothing and three OpenCode trials. The Harbor stop-early adapter is tracked in #83. The in-process stop-early row is in the [tuning table](TUNING.md).
- [ ] The CI baseline checks pass on `main`: do-nothing 0, stop-early below the reactive proxy below the reference, every exploit baseline below the reference (EVAL §5).
