# ED-72 failure analysis

## Final campaign

The final Harbor campaign evaluated [revision `9f3bdbb`](https://github.com/xand1ex999/foresight/tree/9f3bdbb9ddc24182b76b914874294fa5521c09be) at the shipped arrival mean of 4.0. On seeds 3101–3103, the reference scored 94.21–96.02. All nine Gemini 3.8 Flash trials finished. Of nine planned Kimi K3.1 Pro trials, four finished, four timed out with partial scores, and one has no record. Gemini's three completed scores on seed 3101 were 42.56, 8.19, and 80.70. [Final release and matrix](https://github.com/xand1ex999/foresight/releases/tag/ed72-eval-20261115-002252)

### Score by component on seed 3101

The table covers the reference, all three Gemini repeats, and the highest-scoring completed Kimi repeat on seed 3101. These are points contributed to the 100-point total. Outcome contributes `60 × O`, timeliness `20 × T`, staff wellbeing `10 × O × W`, and budget `10 × O × B`. Totals are rounded from unrounded components. [Score definition](SPEC.md#6-reward-rulebook-11-with-the-13-fixes-adopted-in-12-below)

| Completed run | Outcome | Timeliness | Wellbeing | Budget | Total |
|---|---:|---:|---:|---:|---:|
| Reference | 58.68 | 18.97 | 9.78 | 8.44 | 95.86 |
| Gemini repeat 1 | 30.08 | 7.47 | 0.00 | 5.01 | 42.56 |
| Gemini repeat 2 | 6.06 | 1.13 | 0.00 | 1.01 | 8.19 |
| Gemini repeat 3 | 51.71 | 16.34 | 4.04 | 8.62 | 80.70 |
| Kimi repeat 3 | 55.83 | 16.53 | 8.04 | 8.02 | 88.42 |

In Gemini repeat 2, outcome alone was 52.62 points below the reference. Gemini stayed under €12,000 (`B = 1`), but its low outcome reduced the budget contribution to 1.01 points. Every selected completed run reached the last tick. Repeat 2 submitted nonempty action lists on 51 of 144 ticks.

### Failures by code on seed 3101

Each block represents about 10 occurrences in Gemini repeat 2, rounded up. Codes have different units and can co-occur. F3, F4, F5, and F9 are absent from the verifier report, so their counts are unavailable. The excerpts below trace staffing decisions and one successful response to a CT outage. [Failure definitions](SPEC.md#2-what-we-think-agents-get-wrong-hypotheses-to-test-not-facts) · [Verifier code](../ed72/environment/hospital/ed72_sim/scoring/failures.py)

| Code and verifier signal | Reference | Gemini 1 | Gemini 2 | Gemini 3 | Kimi 3 | Gemini 2 plot |
|---|---:|---:|---:|---:|---:|:---|
| F1 · Waiting ESI 1 deaths with Resus full and at least one ESI 3–5 occupant | 0 | 0 | 0 | 0 | 0 | |
| F2 · Staff faints | 0 | 36 | 53 | 6 | 0 | `██████` |
| F3 · Missed warnings | n/a | n/a | n/a | n/a | n/a | |
| F4 · CT left broken | n/a | n/a | n/a | n/a | n/a | |
| F5 · Unproductive spend or unmet need for spending | n/a | n/a | n/a | n/a | n/a | |
| F6 · Diverted patients while an allowed bed was free | 0 | 0 | 0 | 0 | 0 | |
| F7 · Deaths in uncovered beds | 0 | 14 | 12 | 3 | 0 | `██` |
| F8 · ESI 3 patients upgraded after waiting | 0 | 76 | 171 | 1 | 0 | `██████████████████` |
| F9 · Failure to adapt to an unannounced event | n/a | n/a | n/a | n/a | n/a | |
| F10 · Ticks after the last successful step | 0 | 0 | 0 | 0 | 0 | |

## Three decision excerpts

Open `agent/trajectory.json` and `verifier/score_full.json` under each named directory in the [final Harbor trace archive](https://github.com/xand1ex999/foresight/releases/download/ed72-eval-20261115-002252/ED72_Final_Campaign_Logs_Final.tar.gz). The reference reports are under `reference-3101/ed72__TYDtk3h/`. The selected verifier reports match their hospital report copies.

1. **Gemini repeat 2 omitted on-shift staff from its controller.** In `gemini-r2-3101/ed72__Dd8UGG9/`, trajectory step 21 selected staff with `status in ("resting", "working")`. Step 23 ran that controller. In the scored session, the controller reported 15 on duty, nine waiting patients, and zero actions at tick 5. Its output recorded two actions at tick 6. The verifier records that P025 arrived as ESI 1, was admitted at tick 6, never received coverage, and died. The reference admitted and covered the same arrival at tick 6 and discharged the patient. The controller filter omitted `on_shift` staff. The trace does not isolate the effect of that omission on P025's coverage. The verifier recorded 29 discharges, 206 deaths, 53 faints and 171 upgrades across the full episode. These totals reflect the controller's decisions across all ticks.
2. **Gemini repeat 3 corrected the filter from a live observation.** In `gemini-r3-3101/ed72__GWvZZ5D/`, step 24 stopped on a type error when the runner treated the string `bed.patient` as an object. Step 25 returned the tick-1 observation with the actual bed shape and D1 and others marked `on_shift`. Step 28 corrected the staffing filters to accept `on_shift`, step 29 rewrote the runner to handle the bed shape, and step 30 resumed play from tick 1. The verifier for that scored session shows 461 discharges, eight deaths, six faints, and one ESI upgrade. These were separate model sessions with different controllers and execution paths, so their 72.51-point difference cannot isolate the filter change.
3. **Kimi repeat 3 reacted to the CT outage and rotated staff.** In `kimi-r3-3101/ed72__zKXdnoK/`, step 75 returned tick 72 with `ct.working = false` and `down_ticks_left = 16`. In step 76, Kimi ordered `repair` and two agency doctors and moved D1, D6, and N6 to rest. All actions in the batch were accepted. Step 78 showed CT working again at tick 75, matching the three-tick repair rule in handbook §6. In the decision from tick 76 (step 80), Kimi assigned AD5 to Fast Track and AD6 to Acute. The run discharged 511 patients with two deaths and zero faints. Its largest component deficit against the reference was 2.85 outcome points, with another 2.44 points lost on timeliness. Fatigue exposure also lowers wellbeing even when there are zero faints.

Gemini's strongest seed-3101 session recovered after its initial script error, finished with actions at all 144 ticks, and spent €11,500. Kimi repeat 3 and the reference both spent €13,650 and recorded two deaths. On seed 3102, Kimi repeat 2 completed and discharged 565 patients versus the reference's 562. It scored 93.69 versus 96.02 because the score also weighs acuity, timeliness, fatigue, and spending. [Final campaign results](https://github.com/xand1ex999/foresight/releases/tag/ed72-eval-20261115-002252)

### Fairness inputs

The [evaluated handbook](https://github.com/xand1ex999/foresight/blob/9f3bdbb9ddc24182b76b914874294fa5521c09be/ed72/environment/workspace/HANDBOOK.md) explains assignment persistence, the fatigue thresholds, covered-care requirements, and CT repair timing. The exact `on_shift` status is visible in the live observation, as Gemini repeat 3 demonstrates, and is listed in the [observation contract](CONTRACTS.md#observation). Staff location and fatigue support rotation, and bed coverage and queue wait times expose the effects of staffing and admission decisions. Handbook §§5–7 describe the unannounced CT outage, which appears immediately in the live `ct` fields, and the time a repair takes to restore the scanner. Future arrivals and hazard draws are hidden.

## Offline ablations and replay

The [lever ablations](../analysis/ablations/FINDINGS-section.md) used a scripted stand-in at arrival mean 4.0 over seeds 42, 1, 2 and 3. Relative to its full policy, removing rest rotation cost 44.36 points, removing agency orders for shortfalls cost 44.18, and removing Resus reservation cost 39.57. Adding panic diversion cost 28.11; removing warning preparation cost 5.66. Removing CT repair changed the score by −0.64 points on average. The effect ranged from a 15.4-point loss to a 9.0-point gain across these seeds. These deltas apply to the stand-in and its tested seeds.

A [separate calibration replay](https://github.com/xand1ex999/foresight/issues/109#issuecomment-6884011148) applied one availability-filter correction to the saved seed-42 Gemini controller at arrival mean 3.0 and improved the scripted replay from 81.1712 to 98.5938. That offline intervention reused one saved controller and one calibration world at 3.0 arrivals per tick. The [historical scored seed-42 trial](../eval/results/2026-11-14-gemini-seed42/README.md) is the source for the original controller. The final campaign used fresh Harbor sessions at 4.0.
