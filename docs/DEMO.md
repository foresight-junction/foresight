# ED-72 judging demo

Use the browser replay for the walkthrough and the published Harbor results for the benchmark. Open both before presenting. The scripted replay illustrates how the simulator works. The final matrix uses seeds 3101–3103 and the pinned evaluation revision in the README.

## Before you record

- Start the viewer from the [README](../README.md#watch-a-replay) and open `?replay=reference-seed42.json&tick=60` on the Vite URL. Check that playback and the timeline work at the resolution you will share.
- Open the [final results matrix and trial logs](https://github.com/xand1ex999/guinness/releases/tag/ed72-eval-20261115-002252). Unpack the final archive and open the trajectory and verifier report under `gemini-r2-3101/ed72__Dd8UGG9/` for the staffing example.
- Open the [pinned evaluation command](../README.md#reproduce-the-reported-results) and a terminal with the clean-checkout summary if it has finished. Keep `.env` and any credentials off screen.
- Rehearse once with a timer. Allow time at the end for questions or a slow browser.

## Walkthrough

| Time | Show | Explain |
| --- | --- | --- |
| 0:00–1:00 | Hospital map and waiting room | All patients and staff are synthetic. The agent manages 17 beds and limited staff for 144 half-hour ticks. |
| 1:00–3:00 | Play the seed-42 replay and scrub to an event | Show the queue, the staff covering each zone, and what happens when the CT goes down or patients arrive in a surge. Point to the action log at the selected tick. |
| 3:00–4:30 | Final Gemini trace and score report | The observation used `on_shift` for staff already working. The controller selected only `resting` and `working`, leaving those workers out of its plan. Across the run, the verifier recorded 53 staff faints and 12 deaths in uncovered beds. |
| 4:30–6:00 | Score breakdown and reward integrity | Walk through outcome, timeliness, wellbeing, and budget. The hospital container records actions and replays the episode to compute the score. Stop-early leaves the remaining ticks to play out. |
| 6:00–8:00 | Final matrix, seed 3101 column | Reference scored 95.86 and discharged 573 of 584 patients. Best completed runs on that seed were 88.42 for Kimi and 80.70 for Gemini. Gemini ranged from 8.19 to 80.70. Point out the incomplete Kimi attempts in the matrix. |
| 8:00–9:00 | README benchmark command | Show how judges can run reference, do-nothing, stop-early, and three Gemini trials from the pinned commit. Point out the keyless baseline command. |
| 9:00–10:00 | Questions | Keep the replay and the run logs open. |

The viewer can also start a live scripted episode from **New run**. Keep a saved replay open for the timed walkthrough. A full Harbor evaluation can take longer than the presentation.

## Before you submit

- Confirm the README and the final results release open from the GitHub link in the submission.
- Check the playthrough video from a signed-out browser window, then add its URL to the submission and README.
- Record whether the clean-checkout evaluation completed all six trials. If a provider rejects the key, use the published campaign as the evidence for the demo and rerun the reproduction check with a valid key.
- Submit the repository, at least one scored Harbor model run, and the playthrough video by the deadline in the [challenge brief](CHALLENGE.md).
