# ED-72 demo script (10 minutes)

For the live demo to the judges and for the demo video (#25). The walkthrough uses the seed-42 Gemini calibration run, the same run the README analyses under "Model decisions". If the run matrix (#18) lands before recording, add its means to segment 7.

The judges' rubric is in `docs/CHALLENGE.md`: the gap (30), meaningful difficulty (30), reward integrity (25), craft (15). Each segment below says which criterion it is for.

## Timing

| Start | Length | Segment | Rubric |
|---|---|---|---|
| 0:00 | 0:40 | 1. Hook | |
| 0:40 | 1:10 | 2. Setup: the department and the tools | Difficulty |
| 1:50 | 1:10 | 3. A `harbor run`, live start then saved trial | Craft |
| 3:00 | 2:00 | 4. One agent episode, through its log | Difficulty |
| 5:00 | 1:00 | 5. The score breakdown | Integrity |
| 6:00 | 1:15 | 6. A cheat attempt that fails | Integrity |
| 7:15 | 1:15 | 7. Results | Gap |
| 8:30 | 0:45 | 8. Close | |
| 9:15 | 0:45 | Buffer for questions or a slow terminal | |

## Before the demo

- [ ] `make eval` has finished on the final code and `eval/results/summary.md` is current.
- [ ] One agent trial is picked for segment 4: the same trial the README links as its run log. Use the [seed-42 Gemini calibration](../eval/results/2026-11-14-gemini-seed42/README.md).
- [ ] Open the chosen trial’s `agent/trajectory.json`, `verifier/reward.txt` and `verifier/score_full.json`. These files cover the walkthrough. The frozen task collects the report while the raw simulator log stays in the hospital container.
- [ ] Terminal open in the repo root, font at least 18 pt, with these files ready in editor tabs: `docs/SPEC.md` §3, the trial's `verifier/score_full.json`, `eval/results/summary.md`.
- [ ] `.env` is closed and never shown. Don't run `env` or `cat .env` on screen.

## 1. Hook (0:00, 0:40)

Say:

> An emergency department with 17 beds and only enough staff to cover some of them, for 72 hours. Every 30 minutes the agent decides who gets a bed, who gets a doctor and who goes to rest. It sees everything about the present and nothing about the future. On seed 42, at the original load of 3 arrivals per tick, a short scripted reference policy scored 0.99 and Gemini 3.8 Flash scored 0.81. Thirteen of Gemini's patients died; the reference lost none.

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

Point at `waiting`, `beds` (each bed’s `patient` field is `null`), `staff` (everyone in `rest` at fatigue 0) and the empty `warnings`.

## 3. A `harbor run` (1:50, 1:10)

Export `GEMINI_API_KEY` off screen first. Start a run live with the README's command:

```bash
alias harbor='uvx --python 3.12 --from harbor==0.26.0 harbor'
harbor run -p ed72 -a opencode -m gemini/gemini-3.8-flash \
  --ae 'GOOGLE_GENERATIVE_AI_API_KEY=${GEMINI_API_KEY}' --ak version=1.19.5
```

The agent container has the handbook, the `ward` CLI and the OpenCode runtime. The simulator, seed and scorer run in the `hospital` sidecar. Switch to the saved trial after launching the live run. The saved calibration took 12m 37s.

## 4. One agent episode (3:00, 2:00)

Open the saved [Gemini trajectory](../eval/results/2026-11-14-gemini-seed42/trajectory.json). The agent read the handbook, wrote one Python policy (`/app/run_ed.py`, in the `write` call to that path) and ran it once for all 144 ticks.

1. **The plan (0:30).** Scroll to the `write` call for `/app/run_ed.py`. Show `is_available`: it skips staff whose status is `sick`, `fainted`, `ordered`, `not_arrived` or `departed`. Then show `assign_role`: agency staff fill each zone first, permanent staff fill what is left, everyone else rests.
2. **Tick 121 (0:45).** Scroll to the `python3 /app/run_ed.py` output. At tick 121 (day 3, 20:30), `last_rejected` shows AD1, AN1 and AN2 assigned to Resus and rejected with `staff_unavailable`. Say: the observation calls these workers `agency_left`, not `departed`, so the policy kept counting them as staff. Resus got no permanent staff because the plan thought it was covered.
3. **The cost (0:30).** In [`score_full.json`](../eval/results/2026-11-14-gemini-seed42/score_full.json), search for `P424`: ESI 1, admitted to Resus at tick 120, `first_covered_tick: null`, `died`, failure code `F7`. `P436` (admitted at tick 123) is the same. Say: the reference, on the same seed and the same arrivals, covered both on arrival and discharged them.
4. **Was it fair? (0:15).** Open `HANDBOOK.md` §3: "departed agency staff cannot be assigned", and agency staff leave 16 ticks after arrival. §6 tells the agent to check `last_rejected` before the next tick. The policy printed every rejection and never changed.

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

Show the README Results table. Reference reward 0.989617, Gemini reward 0.811712, and do-nothing reward 0.000000, all on seed 42 at arrival mean 3.0. The in-process reference gives the same seed-42 reward. On seeds 1–5, the reference averages 98.4 points and the reactive proxy averages 61.8.

Say where the 17.8-point gap comes from: Gemini's W and B are both 1 (rested staff, €8 800 spent), so the whole gap is O and T. 13 ESI 1 deaths against none for the reference; 3 of 20 ESI 1 patients covered on time against 16.

If #18 has posted per-seed model means and ranges by recording time, show them next to the matching reference. Otherwise say plainly that this is one trial on one seed.

## 8. Close (8:30, 0:45)

Say:

> The agent's main mistake was not reading the department's feedback: it staffed critical beds with people who had gone home and never noticed the rejections. The score can't be gamed by shortcuts. It weights patient outcomes first, it is computed from the hospital's own log after the agent stops, and every shortcut we could think of is played as a baseline and loses. To reproduce everything, run `make eval` from the README.

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

`docs/CHALLENGE.md` lists what must be in the submission and the required stack. The Junction form's own fields are not recorded in the repo, so check them on the Junction dashboard before submitting. The items below are the ones CHALLENGE requires.

Must be in the submission (CHALLENGE "Must be in the submission"):
- [ ] At least one Harbor run log with its score, a model playing the environment. Linked from the README Results section.
- [ ] A short README: what the agent has to do, why it is hard, how we score it, with the core written by hand. Check: `grep -nE 'HU[M]AN|TODO[(]' README.md docs/DEMO.md` prints nothing.
- [ ] Demo video with a playthrough (recording checklist above).
- [ ] Submitted before Sun 15 Nov 10:00.

Required stack (CHALLENGE "Required stack"):
- [ ] Harbor task with `instruction.md`, `task.toml`, `environment/Dockerfile`, `tests/`, `solution/`. Check: `ls ed72/instruction.md ed72/task.toml ed72/environment/Dockerfile ed72/tests ed72/solution`.
- [ ] OpenCode harness: the README's OpenCode command (`harbor run -p ed72 -a opencode -m gemini/gemini-3.8-flash --ae 'GOOGLE_GENERATIVE_AI_API_KEY=${GEMINI_API_KEY}' --ak version=1.19.5`) finishes with a reward.
- [ ] The verifier writes one number in [0, 1] to `/logs/verifier/reward.txt`.

What judges rerun (CHALLENGE "How judges run it"):
- [ ] On a fresh clone, `make eval` runs the reference, do-nothing and three OpenCode trials. Stop-early runs in process only; its row is in the [tuning table](TUNING.md).
- [ ] The CI baseline checks pass on `main`: do-nothing 0, stop-early below the reactive proxy below the reference, every exploit baseline below the reference (EVAL §5).
