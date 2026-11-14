# Emergency Department Management Simulator: architecture

An AI agent manages a fictional emergency department (ED) for 72 simulated hours. This is an **operational** benchmark. Complaint categories, acuity levels and outcomes are abstract simulation variables. Nothing here diagnoses, treats, or uses real patient data.

Implementation: `backend/app/edsim/`, written with the Python standard library only.

## 1. Time model and engine choice

**Choice: a time-stepped engine (1 simulated minute per step) driven by a pre-generated exogenous schedule.**

- The agent acts while the clock is frozen. Only `advance_time(minutes)` moves the clock (1 to 120 minutes per call). Observations and actions cost no simulated time.
- Continuous processes need integrating as resources change: treatment progress, deterioration risk, fatigue and costs. A pure discrete-event engine would have to recompute every "next event" time whenever the agent reassigns a nurse or a monitor fails. That is error-prone and hard to test. Integrating each minute is simple and exact enough, and cheap: a full 72-hour run (4,320 steps, around 200 patients, around 25 staff) takes well under a second.
- Discrete happenings (arrivals, shift changes, equipment failures, inpatient-bed offers, temporary staff arriving) live in a schedule keyed by minute and are applied at the start of their step.
- Clock 0 is 07:00 on day 1. The episode ends at minute 4,320 (07:00 on day 4). If the agent stops early, the evaluator fast-forwards the rest with no actions (M2), so stopping early equals doing nothing for the remaining time.

### Order inside each minute (fixed, `engine.py`)
Each minute has two phases. The agent sees the state, and may act, between the begin phase of minute `t` and its run phase.

**Begin phase** (discrete happenings at the start of minute `t`):
1. Exogenous events start or expire (`events.py`)
2. Equipment repairs and rental availability; bed reopening, cleaning and rental returns (`resources.py`)
3. Shift transitions, including agency staff arriving. Staff going off duty or falling sick are released from their patients (`staffing.py`)
4. Arrivals. Diversion applies to ambulances; major-incident casualties cannot be diverted (`flow.py`)
5. Inpatient-bed offers and transfers out (`flow.py`)
6. Triage completion and assignment (`flow.py`)
7. Imaging completion and next scan (`resources.py`)

**Run phase** (continuous processes during minute `t`):
1. Treatment progress, complications, completion (`flow.py`)
2. Deterioration risk, deterioration, critical events, walk-outs (`outcomes.py`)
3. Fatigue and breaks (`staffing.py`)
4. Cost accrual (`budget.py`)
5. Ground-truth metric sampling (`flow.py`)

## 2. Reproducibility and fairness

- `rng.py` derives independent named streams from `(seed, name)` with SHA-256, for example `arrivals`, `events` and `patient:PT-0042`. Distributions are built only from `random.Random.random()` with our own inverse-CDF and Box-Muller transforms, so results don't depend on how a given Python version implements `expovariate` or `gauss`.
- **Common random numbers:** everything exogenous is drawn at reset, before the agent acts: arrival times, each patient's hidden attributes, true treatment duration, complication, need for admission, patience, deterioration thresholds, and the full event schedule. Agent actions never consume random numbers, so two agents on the same seed face identical patients and incidents. The same seed and the same actions give an identical run. Tests check both properties.

## 3. Domain model (`entities.py`)

### Patients
| Field | Visible to agent | Notes |
|---|---|---|
| `patient_id` (`PT-0001`), age, arrival minute, arrival mode (walk-in or ambulance), complaint category | yes | |
| `acuity` 1 (most urgent) to 5 | after triage | Major-incident patients arrive field-triaged |
| requirements: bed classes, doctor grade, critical-care nurse, monitoring, ventilator, imaging (ct/xray) | after triage | Derived from acuity and complaint; recomputed on deterioration |
| status (`awaiting_triage`, `waiting`, `in_treatment`, `ready`, `boarding`, then a terminal status), wait so far, assigned bed, staff and equipment, active treatment minutes, nominal expected minutes | yes | |
| true duration, complication, deterioration thresholds, patience, need for admission | **no** | Need for admission is revealed when treatment completes |

Terminal statuses: `discharged`, `admitted`, `transferred`, `lwbs`, `critical_event`, `diverted`.

Complaint categories (abstract labels): `chest_pain`, `breathing_difficulty`, `major_trauma`, `neuro_symptoms`, `abdominal_pain`, `minor_injury`, `fever_infection`, `mental_health`. Each has an acuity distribution and probabilities of needing imaging, monitoring or a ventilator.

### Staff
Roles: `attending` (senior doctor, has `critical_care`), `resident` (doctor, cannot lead acuity 1), `nurse` (some have `critical_care` and/or `triage`). Each staff member has a shift list, an on-duty / on-break / off-duty / sick state, a zone (`triage` or `floor`, nurses only), assigned patients, fatigue 0 to 100, and a load capacity.

- Two 12-hour teams: day (07–19) and night (19–07), each working three shifts in the 72 hours. Night is thinner.
- Load units: a doctor carries 5/3/2/1/1 units for acuity 1–5 (attending capacity 10, resident 8). A nurse carries 12/6/4/3/3 units (capacity 12). This gives 1:1 nursing for resuscitation and about 1:4 for minor cases.

### Beds and equipment
- Bed classes: `resus`, `monitored`, `general`, `fast_track`, plus temporary `hallway` beds (rented; treated as `general` for compatibility). Compatibility: acuity 1 needs resus; 2 needs resus or monitored; 3 needs resus, monitored or general; 4–5 can use any bed, including fast track (fast track only takes acuity 4–5). After a discharge, a bed is cleaned for 15 minutes.
- Equipment: `ventilator` and `portable_monitor` are held by one patient; `ct` and `xray` are shared imaging served from a queue. A portable monitor lets a patient who needs monitoring be treated in a general bed. Equipment can fail and be repaired.

## 4. Process mechanics

- **Arrivals:** a non-homogeneous Poisson process (generated by thinning) with a day/night curve (low at night, peak 11:00–20:00), plus demand spikes and major incidents (surges).
- **Triage:** automatic, done by nurses whose zone is `triage`. Each nurse triages one patient at a time (4–8 minutes, drawn per patient). Ambulances go first, then arrival order. With no triage nurse, nobody gets triaged.
- **Treatment** starts when the agent places a triaged patient in a compatible bed with a qualified doctor and nurse (and a ventilator or monitor if required). Progress per minute is `speed / true_duration`, where `speed` comes from the slowest fatigue factor among the assigned staff. Progress is **stalled** whenever a requirement is missing: a staff member off shift or on a break, broken equipment, an incompatible bed after deterioration, and so on.
- **Imaging:** patients who need it join the modality queue when treatment starts (ordered by acuity, then queue time). Progress is capped at 50% until the scan finishes. When a scanner fails, its queue stops.
- **Complications:** a hidden per-patient multiplier extends treatment. It is announced when progress reaches 60%.
- **Disposition:** at 100% the patient is `ready`, and home or admit is revealed. The agent must call `discharge_patient`. Home patients leave and the bed goes to cleaning. Admitted patients join the inpatient queue and stay in their ED bed (`boarding`) until an inpatient-bed offer arrives (a seeded day/night process). The agent can pay to `request_transfer` a boarding patient out.
- **Deterioration** (synthetic): each patient accumulates hazard `H`. Untreated (waiting, or stalled in treatment), the rate grows with untreated time: `h = β/τ_a · (u/τ_a)^(β−1)` with β = 1.5 and τ = 45/90/300/900/2000 minutes for acuity 1–5. Stalled treatment counts at half rate. In active treatment the rate is a small constant (`0.01/τ_a`) times the fatigue risk factor of the assigned staff. When `H` passes the patient's next pre-drawn Exp(1) threshold, acuity worsens by one level, requirements are recomputed, untreated time halves, and remaining treatment grows by 30%. If an acuity-1 patient deteriorates, a `critical_event` (abstract severe outcome) ends that patient's ED episode.
- **Leaving without being seen:** acuity 3–5 patients whose treatment has never actually started leave once their wait passes a hidden patience (lognormal; median 240/180/150 minutes for acuity 3/4/5). This includes patients parked in a bed with no staff, so parking is not a way to avoid walk-outs.
- **Fatigue:** on duty, it rises by `0.095 · (0.5 + load_ratio)` per minute, ×1.2 at night (23:00–07:00) and ×1.5 in overtime. A break recovers 0.5 per minute; time off recovers 0.15 per minute. Above 60, speed falls linearly to 0.6 at 100. Above 70, the hazard multiplier for that staff member's patients rises linearly to 2.0 at 100.
- **Budget:** wages accrue per minute (overtime ×1.5, temporary staff ×2.2 plus a call-out fee). Supplies are charged once per patient at first treatment start (by acuity; a supply shortage multiplies them). Rentals accrue per minute. Expedited repairs and transfers are one-off costs. The budget is set by the difficulty config; a budget-cut event lowers it.

## 5. Unexpected events (`events.py`)

All events are drawn at reset from the seed and difficulty. They change engine state, not just text. The agent sees an event only once it is active.

| Kind | Effect on state |
|---|---|
| `major_incident` | 15-minute pre-alert with an approximate count, then a burst of field-triaged, high-acuity ambulance arrivals that cannot be diverted |
| `demand_spike` | Arrival rate ×1.6–2.0 for 2–4 hours |
| `staff_sickness` | A staff member leaves mid-shift (patients stall), or a future shift is cancelled with notice |
| `equipment_failure` | Equipment goes out of service for 3–10 hours (the agent sees a noisy estimate). Held equipment is pulled from its patient; an imaging queue stops |
| `bed_closure` | 2–4 beds of a class close for 4–8 hours. Occupied beds close once vacated |
| `supply_shortage` | Supply cost ×1.6 for 12 hours |
| `budget_cut` | Budget reduced by 6–8% |
| complication (per patient) | Treatment extended (hidden multiplier, announced at 60%) |

## 6. Agent interface

### Observations (only information a manager would have now)
`get_department_status`, `list_patients(status?)`, `get_patient(patient_id)`, `get_staff_status`, `get_resource_status`, `get_budget_status`, `get_active_events`, `get_department_metrics`, `get_recent_log(since?)`.
**Never exposed:** future arrivals or events, true durations, thresholds or hazard, patience, need for admission before completion, the true repair time, the reward.

### Actions
| Action | Effect | Main constraints / errors |
|---|---|---|
| `start_treatment(patient_id, bed_id, doctor_id, nurse_id, equipment_ids?)` | Atomic placement of bed, staff and equipment | `NOT_TRIAGED`, `BED_INCOMPATIBLE`, `BED_UNAVAILABLE`, `STAFF_NOT_QUALIFIED`, `STAFF_AT_CAPACITY`, `STAFF_UNAVAILABLE`, `EQUIPMENT_UNAVAILABLE` |
| `assign_bed(patient_id, bed_id)` | Place or move a patient. `ready` and `boarding` patients may move to any free bed (for example a hallway bed) to release an acute bed | same bed checks while treatment is unfinished |
| `assign_staff(staff_id, patient_ids)` | Fill the doctor or nurse slot (replacing any current holder) | qualification, availability, capacity, zone |
| `release_staff(staff_id, patient_id)` | Free capacity (the patient may stall) | |
| `allocate_equipment(equipment_id, patient_id)` / `release_equipment(equipment_id)` | Ventilator or portable monitor | operational, free, patient placed |
| `discharge_patient(patient_ids)` | Home: leave. Admit: join the inpatient queue (boarding) | `NOT_READY` |
| `request_transfer(patient_id)` | Boarding patient leaves after 60 minutes; cost | boarding only |
| `set_staff_zone(staff_id, zone)` | Nurse between triage and floor | needs a triage skill; no patients when moving to triage |
| `schedule_break(staff_id, minutes)` | 15–60 minute break; patients stall meanwhile | on duty |
| `extend_shift(staff_id, hours)` | 1–4 hours of overtime | max 16 hours continuous |
| `request_temporary_staff(role, hours)` | Arrives after 60 minutes for 4–12 hours | daily agency limit |
| `request_resources(kind, hours)` | `hallway_bed`, `portable_monitor`, `ventilator` rental (60-minute lead time) | daily limit |
| `request_repair(equipment_id)` | Expedited repair: remaining downtime −70%; cost | failed equipment only |
| `set_diversion(active)` | Ambulances (except major incidents) go elsewhere | counted as diverted |
| `advance_time(minutes)` | Run the engine 1–120 minutes; returns what happened | ends at 72 hours |

Invalid actions raise `EDError(code, message)`. Each action validates everything before it changes anything, so a failed call leaves state untouched. The failed call is logged and counted.

## 7. Logging and ground truth

- `state.log`: every state change with minute, type, payload and visibility (`agent`, `spectator`, `truth`). It feeds the spectator stream (M2/M6) and the agent's `get_recent_log` (agent-visible entries only).
- `state.truth`: per-patient ground truth (arrival, triage, first treatment, completion, departure, deteriorations, terminal status, boarding minutes, diverted). It also keeps staff fatigue integrals, the budget ledger, and occupancy and queue integrals. Only the evaluator reads it.

## 8. Scoring model (proposal, for approval before M2)

Five components in [0, 1], combined by a **weighted geometric mean**:
`reward = O^0.35 · T^0.25 · F^0.20 · S^0.10 · B^0.10`

| Component | Definition | Why it matters |
|---|---|---|
| **O, outcomes** | Acuity-weighted mean patient outcome (weights 5/4/2/1/1 for initial acuity 1–5). Per patient: 1.0 if treated without deterioration; −0.3 per deterioration; 0 for a critical event; 0.2 for LWBS; 0.3 for diverted. Patients still in the ED at the end are scored on their current state. | Safety is the purpose of an ED; urgent patients weigh more |
| **T, timeliness** | Acuity-weighted mean of `exp(−max(0, wait − target) / target)`, where wait is door to first *active* treatment minute and targets are 10/20/60/120/240 minutes (`config.TARGET_WAIT`; acuity 1 is 10 because triage itself takes 4–8 minutes) | Door-to-treatment time is the main ED quality measure |
| **F, flow** | Share of patients who arrived before hour 66 and were dispositioned, minus a boarding and bed-blocking term | Stops "treat a few perfectly"; rewards throughput without rewarding throughput alone |
| **S, staff** | `1 − overload`: on-duty staff-minutes with fatigue > 80, divided by total on-duty staff-minutes (scaled ×3, clipped) | Sustainable staffing; fatigue also feeds back into O via risk |
| **B, budget** | 1 if spend ≤ budget; linear down to 0 at 130% of budget; **no bonus for underspending** | Financial constraint without rewarding hoarding |

Why this shape:
- Weights: 80% on patient dimensions (O, T, F), because they are the purpose of the department. Staff and budget (20%) are constraints. The geometric mean makes neglecting any dimension expensive, while a single mistake only dents the score.
- No automatic zero. Repeated critical events pull O, and through it the reward, sharply down. That is a soft hard-penalty.

| Exploit | Why it fails |
|---|---|
| Do nothing / advance only | Nobody is treated: O ≈ 0.2 or lower, T ≈ 0, F ≈ 0 |
| Divert or refuse | Diverted outcome is 0.3 and they don't count as flow |
| Discharge immediately | Impossible: `discharge_patient` needs `ready` |
| Leave resources unused | Same as doing nothing |
| Overwork staff | S falls, and fatigue raises deterioration (O) and slows treatment (T, F) |
| Throughput only (treat minor cases first) | Urgent patients wait: O and T are acuity-weighted |
| Hoard budget | B has no underspend bonus; under-reacting to incidents costs O and T |
| Stop early | Fast-forward with no actions |

Weights and constants will be checked against the baselines in M3 (do-nothing, naive throughput, resource-conservative, reference) and changed only with a stated reason.

## 9. Difficulty configs (`config.py`)

| | easy | standard | hard |
|---|---|---|---|
| Base arrivals per hour (before the day/night curve and spikes) | 2.0 | 2.5 | 2.9 |
| Patients in 72 h (seeds 1–3) | ~150 | 197–226 | ~260 |
| Beds (resus / monitored / general / fast track) | 3/6/10/4 | 3/6/10/4 | 2/6/10/4 |
| Night team (attending / resident / nurse) | 1/2/5 | 1/2/5 | 1/1/5 |
| Budget | 95k | 106k | 110k |
| Events | fewer | 1–2 major incidents, 2–3 spikes, 2–3 sickness, 2–4 failures, 1–2 closures, shortage, 0–1 cut | more of each |

The roster wage bill is about 47.5k and supplies about 46k for `standard`, which leaves roughly 7–14k for overtime, agency staff, rentals, repairs and transfers, depending on whether a budget cut lands.

`horizon_hours` can be overridden for development and tests; budget and event counts scale with it. Harbor always uses 72 hours. A full LLM run is roughly 400–600 tool calls (see open decision D1 in MIGRATION.md).

Calibration so far (M1, standard, seeds 1–5). The greedy manager is the test fixture `tests/edsim_support.simple_policy`: it never spends money, transfers boarders, takes breaks, moves deteriorated patients or re-staffs triage.

| Policy | Walk-outs | Critical events | Dispositioned | Spend vs budget |
|---|---|---|---|---|
| Do nothing | 98–131 | 77–90 | 0% | ~46% (wages only) |
| Greedy | 0–22 | 4–26 | 73–94% | 84–94% |

The worst greedy seeds (4 and 5) are the ones where the only triage nurse falls sick and nobody moves another nurse into triage, even though `get_department_status` raises an alert. The other critical events come from saturated resus beds and the single night attending. The reference strategy (M3) should close this gap, and the reward has to separate all three.

## 10. Module map

| Module | Responsibility |
|---|---|
| Module | Responsibility (numbers refer to the requested separation of concerns) |
|---|---|
| `config.py` | Difficulty configs and constant tables (complaints, acuity, costs, rates) |
| `rng.py` | Named, seeded substreams and distributions |
| `entities.py` | Patient, Staff, Shift, Bed, Equipment, ScheduledEvent, ActiveEvent, EDError and error codes |
| `generator.py` | (2, 7) Builds the scenario from the seed: roster, layout, arrivals and patients, event schedule, inpatient-bed offers |
| `state.py` | (1, 10) SimState container, schedules, budget ledger, event log, ground-truth accumulators |
| `rules.py` | Pure rules: requirements, qualification, bed compatibility, load units, fatigue speed and risk factors, hazard rates |
| `flow.py` | (3) Arrivals, triage, treatment progress and completion, dispositions, departures |
| `staffing.py` | (4) Shifts, handover, assignment bookkeeping, breaks, fatigue |
| `resources.py` | (5) Beds, equipment, imaging queues, rentals, repairs |
| `budget.py` | (6) Wages, overtime, agency, rentals, supplies |
| `events.py` | (7) Applies and expires unexpected events |
| `outcomes.py` | (8) Deterioration, critical events, walk-outs |
| `engine.py` | (9) `Simulation`: clock, minute phases, `advance_time`, `act`, observations, `truth()` |
| `actions.py` | Validation and atomic application of agent actions |
| `views.py` | Agent-visible projections (the hidden-field firewall) |

Known, accepted signals: `awaiting_imaging` appears when treatment reaches 50%, and `treatment_extended` appears at 60%. Both are things a real manager would be told. They hint at, but do not reveal, the true treatment duration.
