# ED-72 handbook

Manage a fictional emergency department for 72 simulated hours. Save patients, provide care on time, rotate staff before they become exhausted, and control spending. The final score is 0–100; the reward is score / 100. All patients and staff are synthetic. The values below describe the supplied default configuration.

## 1. Episode and controls

There are 144 half-hour ticks, numbered 0–143. Tick 0 starts at 08:00 on day 1; the episode ends at 08:00 on day 4. Before tick 0 arrivals, all beds and the waiting area are empty, all 6 doctors and 9 nurses are resting with fatigue 0, the CT works, and spending is €0.

Use these tools:

| Tool | Arguments | Effect |
|---|---|---|
| `rules` | `{}` | Returns this handbook as `{"text": "..."}`; time does not advance. |
| `observe` | `{}` | Returns the current state; time does not advance. |
| `step` | `{"actions": [...]}` | Applies up to 50 actions in order, resolves one tick, and returns action results plus the next observation. |

`step` returns `{"results": [...], "observation": {...}}`. An action result contains its zero-based `index` and `ok`; rejected actions also have a `reason`. Rejected actions have no effect or extra penalty; valid actions in the same list still apply. `step` with `{"actions": []}` passes one tick.

The fallback CLI calls the same tools: `ward rules --json '{}'`, `ward observe --json '{}'`, or `ward step --json '{"actions":[]}'`.

Each tool call, including reads, counts toward the current provisional 500-call cap. A full episode takes 144 `step` calls. At the cap, calls return `{"error":"call_cap_reached"}` and the remaining ticks run without new actions. Stopping or timing out also runs all remaining ticks without new actions: staff keep their last assignments and patients continue to arrive, wait, and face hazards. After tick 143, the final observation has `finished: true`; further `step` calls return `{"error":"episode_over"}`. There is no reset or undo.

The observation shows the tick, clock, ticks remaining, budget, waiting patients, all beds, all staff, CT status, announced warnings, diversion status, running totals, and rejected actions. Patient severity and CT need are visible. Staff fatigue, location, availability, and time until return or contract expiry are visible. Empty beds have `patient: null`. Future arrivals, unannounced events, and random draws are hidden; no current score is shown.

## 2. Patients and beds

ESI 1 is the most critical severity; ESI 5 is the least critical.

| ESI | Ordinary arrival share | Base treatment ticks | Target to first covered bed tick | Score weight |
|---|---|---|---|---|
| 1 | 4% | 6 | 0 | 10 |
| 2 | 14% | 5 | 1 | 5 |
| 3 | 34% | 3 | 4 | 2 |
| 4 | 30% | 2 | 8 | 1 |
| 5 | 18% | 1 | 12 | 0.5 |

Targets count ticks since arrival. A target of 0 means receiving covered care in the arrival tick. Merely occupying an uncovered bed does not meet a target.

| Zone value | Beds | Eligible patients and extra treatment time | Beds per doctor | Beds per nurse |
|---|---|---|---|---|
| `resus` | 3, R1–R3 | ESI 1–5, no extra time | 1 | 1 |
| `acute` | 8, A1–A8 | ESI 2: +1 tick; ESI 3–5: no extra time | 3 | 2 |
| `fast_track` | 6, F1–F6 | ESI 3: +1 tick; ESI 4–5: no extra time | 4 | 3 |

The waiting area has no capacity limit. Admit only from waiting to a free bed in an eligible zone. There are no transfers between zones and no manual discharge action. A bed frees when treatment finishes or its patient dies.

Treatment progresses by one tick only on a covered bed. Required treatment is the base time plus any zone penalty. A patient is discharged as soon as the required treatment ticks accumulate.

Half of ESI 1–2 patients need CT, independently determined and shown on arrival. Patients awaiting CT pause at half their required treatment ticks, rounded up, while the scanner is down. When it works, all patients at their scan point can be scanned that tick; there is no scanner queue.

An ESI 3 patient can deteriorate to ESI 2 while waiting (section 4). The patient then follows all ESI 2 rules, including eligible zones and treatment time, receives a new 50% CT-need draw, and is scored at ESI 2. Score weights and targets use the most severe ESI reached, meaning the lowest numerical ESI.

## 3. Staff, coverage, and fatigue

Permanent staff IDs are D1–D6 and N1–N9. Assign each available person to one zone or `rest`. Assignments take effect in the current tick, are free, and persist until changed. Only staff who are on shift contribute coverage.

For each role, add staff contributions in the zone and multiply by the beds-per-person value in section 2. Zone coverage is the smaller of doctor and nurse coverage, rounded down to a whole number of beds and limited by the zone's bed count. A person with fatigue at most 60 contributes 1; above 60 they contribute 0.6. If coverage is insufficient, cover occupied beds by severity first, then admission time.

| Location | Fatigue change each tick |
|---|---|
| `resus` | +2.2 |
| `acute` or `fast_track` | +1.6 |
| `rest` | −2.5, stopping at 0 |

The resting rate applies to resting and fainted staff. Sick staff retain their fatigue until they return. At fatigue 90 or above, a person faints and is unavailable for 10 ticks. During that absence they recover at the resting rate, return to `rest` at about 65 fatigue, and require a new assignment. Fainted, sick, not-yet-arrived, and departed agency staff cannot be assigned.

Agency doctors cost €900 and agency nurses €350 each. They arrive 4 ticks after ordering, with fatigue 0 in `rest`; assign them before they can cover beds. They leave 16 ticks after arrival. Their fatigue and fainting rules are the same as permanent staff. Agency IDs are AD1, AD2, ... and AN1, AN2, ... in order of ordering.

## 4. Patient hazards

Each applicable hazard is rolled once per patient per tick. A stated waiting threshold means strictly more than that many complete ticks since arrival.

| Situation | Chance per tick | Result |
|---|---|---|
| ESI 1 waiting | 15% | Death |
| ESI 2 waiting more than 1 tick | 4% | Death |
| ESI 3 waiting more than 6 ticks | 8% | Becomes ESI 2 |
| ESI 4–5 waiting more than 16 ticks | 8% | Leaves |
| ESI 1 in an uncovered bed | 10% | Death |
| ESI 2 in an uncovered bed | 3% | Death |
| ESI 1–2 in a covered bed, with mean on-shift fatigue in that zone above 60 | 1.5% | Death |

A patient admitted in the current tick does not face its waiting hazard that tick. Covered and uncovered-bed hazards do not stack. ESI 3–5 on beds face no patient hazard. Hazard calculations use fatigue before the current tick's fatigue update. Patients who complete treatment are discharged before hazards resolve.

## 5. Arrivals, events, and warnings

Ordinary arrivals follow a Poisson process with a daily cycle. The default is a mean of 3.0 arrivals per tick, varying by ±50%, with a peak at 15:00 and a low at 03:00. At clock hour h, the mean is `3.0 * (1 + 0.5 * cos(2*pi*(h - 15)/24))`. The ordinary severity mix is in section 2.

Each episode contains all four events below. Their exact start ticks are selected within the stated windows. Public windows and distributions describe possibilities, not a forecast of the current episode.

| Event | Start-tick window | Warning | Effect |
|---|---|---|---|
| Staff sickness | 28–35 | None | Two nurses are unavailable for 20 ticks. Any who are on shift leave their posts immediately; both return to `rest` with their previous fatigue. |
| Flu wave | 50–61 | 10 ticks ahead | Two extra patients per tick for 6 ticks. |
| CT breakdown | 66–75 | None | CT stops working for 16 ticks unless repaired sooner. |
| Bus crash | 96–109 | 8 ticks ahead | Five extra patients per tick for 2 ticks; mix ESI 1: 20%, ESI 2: 30%, ESI 3: 50%. |

The flu wave's current provisional tuning mix is ESI 3: 40%, ESI 4: 35%, ESI 5: 25%. Warnings show the event type and exact start tick, and stay visible until the event ends. CT status shows remaining downtime.

A seed fixes arrivals, CT needs, event timing, and hazard draws. Random streams keep arrivals and patient hazards independent of strategy choices. The same seed and actions reproduce the same result.

## 6. Actions and spending

Submit action objects in a `step` action list. Use zone names exactly as shown in section 2.

| Action example | Cost | Conditions and effect |
|---|---|---|
| `{"type":"admit","patient":"P042","zone":"resus"}` | Free | Patient must be waiting; zone must be eligible and have a free bed. |
| `{"type":"assign","staff":"D3","to":"rest"}` | Free | Assign an available person to `rest`, `resus`, `acute`, or `fast_track`. |
| `{"type":"agency","role":"nurse"}` | €350 | Order one nurse; use `doctor` for a €900 doctor. Arrival and contract timing are in section 3. |
| `{"type":"repair"}` | €2,000 | Only while CT is broken. An order at tick t restores CT at the start of tick t + 3, or at its original return tick if sooner. |
| `{"type":"divert"}` | Free | For 4 ticks, independently turns away 70% of each tick's arrivals, including event patients. Cannot start while diversion is active. |

Ordering another repair while one is already pending is accepted and costs another €2,000; CT still returns at the earlier scheduled time.

The budget is €12,000. Agency and repair share one spending total. Spending above the budget is permitted up to and including exactly €24,000 but reduces the budget score. Reject a purchase if it would take total spending above €24,000. Diversion acts on arrivals while active; it does not remove patients already waiting. Diverted patients still count toward the score.

Rejected-action reasons include `bad_action`, `unknown_patient`, `not_waiting`, `zone_not_allowed`, `no_free_bed`, `unknown_staff`, `staff_unavailable`, `over_hard_limit`, `ct_not_broken`, and `diversion_active`. Check the returned results and the next observation's `last_rejected` list before deciding the next tick's actions.

## 7. Tick order

Each tick resolves in this order:

1. Agency contracts end; sick and fainted staff whose absence has ended return to rest; ordered agency staff arrive.
2. Events start or end; warnings appear.
3. New patients arrive; any active diversion is applied; remaining arrivals enter waiting.
4. You receive the observation.
5. Your action list is validated and applied in order.
6. Coverage is calculated, treatment progresses unless blocked by CT, and completed patients are discharged.
7. Patient hazards resolve.
8. Fatigue changes; staff at fatigue 90 or above faint.

`step` resolves steps 5–8, then steps 1–3 of the next tick before returning its observation. This makes same-tick care possible for newly arrived ESI 1 patients. A new diversion starts after the current tick's arrivals, so it first affects arrivals in the next tick.

## 8. Score

The final score includes every patient who arrived, including diverted patients. O, T, W, and B are each between 0 and 1.

```text
Score  = 60*O + 20*T + O*(10*W + 10*B)
reward = Score / 100
```

**O, outcome:** `1 - weighted_loss / total_patient_weight`. Multiply each patient's loss below by its section 2 weight; use the most severe ESI it reached.

| Final outcome | Loss |
|---|---|
| Discharged after treatment | 0 |
| Still in a bed at the end, with at least one covered tick | 0.3 |
| Diverted on arrival | 0.7 |
| Dead, left, never admitted, or still in a bed that was never covered | 1 |

**T, timeliness:** the weighted fraction of all patients whose first covered bed tick is within their ESI target from section 2. Diverted patients and patients who never receive covered care are late. Admission alone does not earn timeliness credit.

**W, staff wellbeing:** `max(0, 1 - a*share - b*faints)`. `share` is the fraction of on-shift staff-ticks with fatigue above 60, measured when treatment coverage is calculated, before the fatigue update. Resting and unavailable staff-ticks do not count. `faints` is the total number of faints. Current provisional tuning weights are `a = 1.0` and `b = 0.05`.

**B, budget:** 1 when spending is at most €12,000; then `1 - (spend - 12000)/12000`, clipped to [0, 1]. It reaches 0 at €24,000.

Fresh staff and unspent money earn points in proportion to patient outcomes through O. Doing nothing scores 0; perfect outcomes, timeliness, wellbeing, and budget score 100. Stopping early does not end the simulation or preserve patients from later hazards.

For example, if O = 0.8, T = 0.6, 20% of on-shift staff-ticks are above fatigue 60, there are 2 faints, and spending is €18,000, then W = 0.7 and B = 0.5. The score is `48 + 12 + 0.8*(7 + 5) = 69.6`, and reward is 0.696.

## 9. Worked decisions

These invented examples illustrate the rules; they are not observations from your episode. Assume the stated staff are available and no other actions change the scenario.

| Scenario | What follows from the rules |
|---|---|
| An ESI 1 patient arrives at tick 10, needs no CT, and a resus bed is free. | Admit to resus and assign one doctor and one nurse to cover it in tick 10. First covered tick 10 meets the 0-tick target. Six covered ticks complete treatment if no hazard intervenes. |
| An ESI 2 patient needing CT enters Acute, where sufficient staff cover it and CT remains down. | Acute requires 5 + 1 = 6 treatment ticks. It can reach 3 treated ticks, then waits for CT before further progress. First covered care within 1 tick of arrival meets its target. |
| An ESI 3 patient waits 6 complete ticks, then another tick without admission. | At 6 ticks the deterioration threshold has not been exceeded. At 7 ticks it faces an 8% chance of becoming ESI 2. Before upgrading it may use fast-track with 4 treatment ticks; after upgrading only resus or acute is eligible. |
| Acute has two doctors at fatigue 0 and 61 and three nurses at fatigue 0; five ESI 4 patients occupy its beds. | Doctor coverage is `(1 + 0.6)*3 = 4.8`; nurse coverage is `3*2 = 6`. Four beds receive care, in admission order because severity is equal. The fifth makes no treatment progress. |
| An ESI 5 patient is admitted at tick 143 but its bed never receives coverage. | It receives no timeliness credit and, if still there at the end, has loss 1. With a covered tick it completes its one-tick treatment and is discharged; timeliness still depends on its arrival tick. |
