# Deep dive: Beyond the Clinic (Aalto University)

## Summary

The brief asks for a home product that keeps people well after TMS for depression, ideally a closed loop: sense how the person is doing, respond with something helpful, learn what works for that person. There is a real, specific gap: about half of people who recover after rTMS relapse within a year, and the evidence hints (not proven) that "rescue" boosters triggered by early warning signs beat fixed schedules, yet nothing at home tells the clinic *when* to rescue. Judging is 75% product (usefulness, ease of use, creativity) and 25% sensing/learning, with no dataset to beat, so a polished, humane demo matters more than model accuracy.

**Verdict:** a good pick for a team strong on UX that keeps claims modest. Risks: the prize is "to be announced" (it could be small), there's no provided data, and it's hard to make "learning per person" look credible in a 3-minute demo. Ask about the prize before committing.

## The clinical problem

- **Durability:** a 2019 meta-analysis (19 studies) found that about 50% of patients who respond to rTMS still respond at one year. A review of relapse predictors says about half of those who recover relapse by 12 months.
- **Timing:** a 2023 review estimates the acute effect lasts about five months in responders, and relapse rises after that. Maintenance TMS appears to reduce relapse, but the protocols vary widely between studies.
- **Fixed vs rescue maintenance:** in a 2023 conference poster (14 studies), rescue-based maintenance had a larger effect than fixed schedules, but the difference was not statistically significant. Treat this as a direction, not a finding.
- **Predictors:** comorbid anxiety, residual symptoms and the strength of the acute response may predict relapse. The review calls the evidence insufficient.
- **Implication:** the most useful home product spots early drift from the person's own baseline, gives the clinic a reason to call or book a booster, and helps in between.

## What already exists

| Product / approach | What it does | What happened / lesson |
|---|---|---|
| Meru Health (named in the brief) | 12-week therapist-supported app plus HRV biofeedback with a sensor | A 2024 RCT (n=100) showed reduced depression symptoms. A human coach plus a physiological signal is the credible pattern. |
| Soihtu DTx (named in the brief) | Aalto spin-off making a therapeutic action game (Prof. Matias Palva) | An 8-week PC trial reduced symptoms and improved cognition. "3x better" CEO claim unverified. Mobile version coming. |
| Mindstrong | Keyboard and tap dynamics as "digital biomarkers" | Raised about $160M and shut down in 2023. About half of early users dropped the keyboard, and it never found paying customers. Passive sensing alone is not a product. |
| Woebot | CBT chatbot | Consumer app closed June 2025. The founder blamed the cost of FDA authorisation and the pace of LLMs. "Mood chatbot" is a crowded, fragile category. |
| Kintsugi (also Sonde, Ellipsis: unverified status) | Voice biomarker for depression and anxiety | Closed Feb 2026 after a failed FDA De Novo. Released its model **DAM** on Hugging Face (Apache-2.0, Whisper-small base, returns depression and anxiety scores). Directly usable this weekend. |
| Wysa, Headspace (merged with Ginger) | Chat plus coaching | Wysa holds an FDA Breakthrough designation (unverified). Engagement is the hard part. |
| mindLAMP, Beiwe | Open-source phenotyping platforms | Good feature ideas; too heavy for 40 hours. |
| Oura, Whoop | Sleep, HRV, activity | Neither makes a validated mood claim. Sleep and circadian disruption are plausible relapse signals (unverified as a predictor after TMS). |
| JITAI / HeartSteps | Contextual bandit (Thompson sampling) chooses when to nudge | The deployed reference design for "learn what works per person" (for physical activity, not depression). |
| Bright light therapy | Morning bright light | 2024 JAMA Psychiatry meta-analysis (11 RCTs, n=858) for non-seasonal depression: remission 40.7% vs 23.5%. The best-evidenced "sensory" intervention on the brief's list. |
| 40Hz gamma flicker/sound | Sensory stimulation | Evidence is mainly for Alzheimer's. Weak for depression (unverified). Avoid therapeutic claims. |
| Flow Neuroscience | Home tDCS headset | FDA PMA Dec 2025, prescription only, 57% remission at 10 weeks (EMPOWER). Home brain stimulation is real; companion apps are a gap. |

**Engagement is the killer:** across 93 Android mental health apps, median 15-day retention was 3.9% and 30-day retention 3.3% (Baumel 2019).

## Usable datasets

| Dataset | Content | Access | Usable in 40 h? |
|---|---|---|---|
| Kintsugi DAM model + score metadata | Pretrained voice model; no raw audio | Repo metadata says Apache-2.0, but one summary calls it research-use only: read the LICENSE file before relying on it. Validated mainly on North American English | **Yes**, the best shortcut for voice sensing |
| StudentLife (Dartmouth) | 48 students, 10 weeks, phone sensing, PHQ-9 pre/post, EMA | Open download (5 GB) | **Yes**, for showing features and baselines |
| GLOBEM | 497 users, 700+ user-years, phone + Fitbit, BDI-II/PHQ-4 | PhysioNet credentialed access (training and approval, unverified) | **Risky**, approval can take days |
| DAIC-WOZ / E-DAIC | 189 clinical interviews, audio, transcripts, facial features, PHQ-8 | Academic, non-profit only, EULA, academic email | **Risky**, approval time unknown |
| RAVDESS | Acted emotional speech and song | CC BY-NC-SA | Yes, but acted emotion is not depression |

Rule of thumb: use pretrained models plus open data to *show* the features, and simulate users to *show* the learning. Don't claim predictive accuracy.

## Gaps / openings

1. **Deciding when to rescue:** no home tool turns daily signals into "this person is drifting, book a booster", which is exactly what rescue-based maintenance needs.
2. **Per-person learning:** GLOBEM showed that 9 published depression-detection models barely beat guessing the majority when applied to new datasets, and the authors blame individual differences. That is an argument *for* n-of-1 baselines and per-person bandits, not population classifiers.
3. **Engagement:** with 3 to 4% retention, a daily check-in must take under 60 seconds and give the person something back.
4. **Clinician workload:** the brief explicitly wants a "who might need a call" view without extra work.
5. **Measuring anhedonia:** phones rarely measure motivation or effort, but a game can.

## Project ideas (ranked)

| # | Idea | Sense | Respond | Learn | Side prizes | Difficulty |
|---|---|---|---|---|---|---|
| 1 | **Relapse Radar:** 60-second daily ritual plus a clinician "who to call" board | 20 s voice clip (DAM score + pitch/energy/pause rate via Web Audio), 30 s tap/reaction mini-game (psychomotor speed), one slider; optional sleep import | A personalised micro-action for the day; past a drift threshold, a clinician alert suggesting a booster session | Per-person baseline (rolling z-scores) + Bayesian change-point detection | Gemini (daily summary for the clinician), Gemma on-device (privacy), Modal (hosting DAM), Codex | Medium |
| 2 | **Morning Loop:** a bandit picks the daily intervention | Same check-in, plus the next-day change as the reward | Bright-light colour sunrise (screen or smart bulb), music by tempo, a 3-minute behavioural activation task, a walk prompt, messaging a friend | Thompson sampling per person; live chart of what it has learned | ElevenLabs (voice guide), Gemini, Atech/Arduino (a lamp) | Medium |
| 3 | **Effort game:** a Soihtu-style 90-second daily game that is also a sensor | In-game choices modelled on the EEfRT effort-for-reward task (anhedonia), reaction times, accuracy | Difficulty and rewards adapt; the game world reflects progress | Per-person effort curve over days | Gemini (generated content), Codex | Medium-high (game polish) |
| 4 | **Lighthouse:** ambient social lamp | Check-in or no check-in | A friend's lamp glows softly ("think of them"), with no data shared | Learns which nudge leads to contact | Atech, Arduino Uno Q | Medium (hardware) |
| 5 | **EEG check-in** at the booth | Frontal alpha from the portable EEG | Neurofeedback-style music | Per-session tuning | Modal | High, and depends on the lab |

**Recommendation:** build 1 + 2 as one product: Relapse Radar sensing, Morning Loop responses, and a clinician view. Add the game from idea 3 only as the 30-second check-in task.

**3-minute demo:** a judge does the 60-second check-in live on a phone (voice + taps). Their score lands on a personal baseline chart. Then switch to a simulated patient "Anna", 90 days after TMS: her baseline drifts in week 9, the bandit has learned that walks help her more than music, and the clinician board flags her with a plain-language reason ("speech slower, reaction time down 18%, three skipped mornings"). Finish on the "book booster" button.

**How to avoid being a mood chatbot:** the LLM writes only summaries and copy. Sensing comes from signal features plus a pretrained model, decisions come from a bandit you can inspect, and every alert shows its evidence.

**Browser feasibility:** mic (getUserMedia), camera (MediaPipe face landmarks), touch timing, and DeviceMotion (on iOS this needs `DeviceMotionEvent.requestPermission()` plus HTTPS) all work in a PWA. Screen time, app usage, HealthKit/Health Connect sleep and HRV, and background sensing need a native app. Fake those with a "connected Oura" import labelled MOCK.

## Technical and ethical risks

- **No labels:** no ground truth for relapse this weekend. Frame outputs as "change from your baseline", never "you are depressed".
- **Weak signals:** voice and tap features are noisy and generalise poorly across people (GLOBEM). DAM wasn't trained on post-TMS patients.
- **EU MDR:** under Rule 11, software that informs diagnosis or treatment decisions is at least class IIa. MDCG 2021-24 gives depression-diagnosis software as a class IIb example. The pitch should say "research prototype, clinician-in-the-loop" and avoid diagnostic claims.
- **Safety:** a depression app must handle suicidal ideation: crisis resources (Finland: MIELI crisis line 09 2525 0111, unverified number), no automated "you're fine", and escalation to a human.
- **Privacy:** voice and camera data are special-category health data under GDPR. Process on-device where possible (Gemma, browser feature extraction) and send only features.
- **Burden and credibility:** daily tracking can feed rumination, so keep it short and skippable. Label simulated longitudinal data as simulated.

## Uncertainties

- Prize amount and format ("to be announced").
- Which studies and datasets the "pointers" refer to; none are linked.
- Whether the TMS and portable EEG demos happen, and whether teams can record EEG themselves.
- Submission format, judging process, and primary user (patient vs clinician): not stated.
- Whether the closed loop must be brain-based ("how the patient's brain reacts") or whether behavioural signals count.

## Questions for Aalto (prioritised)

1. What is the prize, and is there a follow-up path (lab collaboration, Aalto Innovation support)?
2. What kind of "learning per person" would convince you: a per-person baseline, a bandit choosing interventions, or something tied to brain response?
3. Which published studies and open datasets did you have in mind? Can you share links now?
4. Will the portable EEG be available for teams to record from, and with what SDK or stream format?
5. In your clinic, what signs come before relapse after TMS that a home tool could pick up?
6. Do you use rescue boosters or fixed maintenance? Would a "book a booster" trigger be useful?
7. Who is the primary user for judging: the patient, the clinician, or both?
8. Any constraints on medical claims or patient-safety features you expect to see?
9. Could a clinician or patient-experience expert give 10 minutes of feedback on Saturday?

## Sources

- Senova et al., rTMS durability meta-analysis: https://pubmed.ncbi.nlm.nih.gov/30344109/
- Miljevic et al., relapse predictors after rTMS: https://www.brainsway.com/knowledge-center/potential-predictors-of-depressive-relapse-following-repetitive-transcranial-magnetic-stimulation-a-systematic-review/
- d'Andrea et al. 2023, maintenance TMS review: https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10141590/
- Soihtu / Aalto game: https://www.aalto.fi/en/news/researchers-develop-a-digital-therapy-to-alleviate-the-symptoms-of-depression
- Meru Health studies: https://pmc.ncbi.nlm.nih.gov/articles/PMC8350582 , https://pmc.ncbi.nlm.nih.gov/articles/PMC7250954
- Woebot shutdown (STAT): https://www.statnews.com/2025/07/02/woebot-mental-health-chatbot-shuts-down-founder-says-ai-moving-faster-than-regulators/
- Mindstrong (STAT): https://www.statnews.com/2023/02/28/mindstrong-mental-health-technology-prediction/
- Kintsugi closure: https://bhbusiness.com/2026/02/11/mental-health-voice-biomarker-kintsugi-closes-makes-all-technology-and-research-public/
- Kintsugi DAM model: https://huggingface.co/KintsugiHealth/dam
- Flow Neuroscience FDA: https://spectrum.ieee.org/flow-neuroscience-tdcs-depression-fda
- Bright light meta-analysis: https://pubmed.ncbi.nlm.nih.gov/39356500/
- Baumel 2019 engagement: https://www.jmir.org/2019/9/e14567
- GLOBEM: https://physionet.org/content/globem/ , https://ubicomplab.cs.washington.edu/pdfs/globem_dataset.pdf
- DAIC-WOZ: https://dcapswoz.ict.usc.edu/
- StudentLife: https://studentlife.cs.dartmouth.edu/dataset.html
- HeartSteps bandit: https://arxiv.org/pdf/1711.03596
- Beiwe / mindLAMP: https://hsph.harvard.edu/research-resource/beiwe/technology , https://www.digitalpsych.org/mindlamp.html
- MDCG 2021-24 examples: https://openregulatory.com/mdcg-2021-24-examples-for-software-classification-of-software-as-a-medical-device-samd/
- Mental wellbeing apps as medical devices: https://www.mhc.ie/latest/insights/is-your-mental-wellbeing-app-a-medical-device
- Aalto closed-loop TMS-EEG: https://acris.aalto.fi/ws/portalfiles/portal/81458974/Closed_loop_optimization_of_transcranial_magnetic_stimulation_with_electroencephalography_feedback.pdf
