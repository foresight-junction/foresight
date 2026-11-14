# Branch: yehor/ref-fairness

- **Issue:** #20
- **Owner:** yehor
- **Agent:** lead
- **Parent branch:** main
- **Created:** Sat 17:32

# Fairness audit handoff

Issue #20. Source snapshot `474829a`. The entries below state what can be checked once #19 provides model trajectories.

| Code | Handbook section | Observation before the decision |
|---|---|---|
| F1 | §2, §4, §7, §9 | `beds[].zone, patient, esi` and `waiting[].esi, arrived_tick`. Check earlier placement of low-acuity patients in Resus and whether another zone was feasible then. |
| F2 | §3, §8 | `staff[].role, location, status, fatigue, counts_as, ticks_until_change`. Look for feasible rotations before fatigue 60 or 90. |
| F3 | §3, §5, §7 | `warnings[].event, start_tick`, `tick`, staff and beds. Check preparation during the warning window. |
| F4 | §2, §5–7 | `ct.working, down_ticks_left`, `beds[].waiting_for_ct, treated_ticks, treatment_ticks`, `waiting[].needs_ct` and `budget`. Compare visible demand, repair delay and cost. |
| F5 | §3, §6, §8 | `budget.spent, budget, hard_limit`, staff, CT, waiting, beds and totals. Tie a spend decision to a concrete trade-off and a same-seed comparison if available. |
| F6 | §2, §6–8 | `diversion.active, ticks_left`, eligible beds, available staff and warnings. Assess coverage and options when diversion is ordered. The scorer's flag uses capacity at the diverted patient's arrival. |
| F7 | §2–4, §7–9 | `beds[].zone, patient, esi, covered`, `staff[].role, location, status, counts_as` and `waiting[].esi`. Recalculate coverage after the submitted actions. |
| F8 | §2, §4, §7, §9 | `waiting[].esi, arrived_tick, waited_ticks`, eligible beds and available staff. Look for service opportunities before the wait exceeds six ticks. |
| F9 | §3, §5, §7 | `staff[].status, location, ticks_until_change`, `ct.working, down_ticks_left` and `beds[].covered, waiting_for_ct`. Assess the response after sickness or scanner failure is observable. |
| F10 | §1, §8 | `tick`, `ticks_left`, `finished` and tool error replies. Use the runner log to distinguish voluntary stop, timeout and call cap. |

The occupied-bed view exposes a CT blockage once a patient reaches the scan point while the scanner is down. Earlier observations carry CT requirements for waiting patients. The handbook specifies coverage priority by severity and admission time, and the engine breaks any remaining tie by bed order. The occupied-bed view omits admission time. Check whether either detail mattered in each actual trajectory before concluding that the action was avoidable. References are `observation.py`, `state.py` and `tests/test_engine_tick.py` under `ed72/environment/hospital/` on the frozen revision.

`scoring/failures.py` emits F1, F2, F6, F7, F8 and F10 as diagnostics. F3, F4, F5 and F9 need trajectory review. Add the evidence for observed cases to `docs/FINDINGS.md` with the #19 owner. Record the exact tick, evidence available at that tick, feasible alternative and observed outcome.

## Seed 42 calibration on 7173934

OpenCode 1.19.5 with Gemini 3.8 Flash completed all 144 ticks at reward 0.811712. Its generated policy made 148 public tool calls. The score report records eight F7 uncovered-bed deaths.

At tick 123 the agent attempted to assign AD1 to Resus and several other unavailable agency staff. The tool rejected those assignments. The generated availability filter checked `ordered` and `departed` while the observation exposes `agency_ordered` and `agency_left`. Handbook §3 says agency staff who have yet to arrive or have left cannot be assigned. The current status and countdown are visible in `staff[].status` and `staff[].ticks_until_change`. Filtering by the actual statuses and recalculating coverage before sending admissions were available alternatives.

P436, an ESI 1 patient, was admitted at tick 123, never received a covered tick, and is flagged F7. The policy's rejection log establishes the bad assignment in that tick. The available artifacts do not isolate whether a corrected assignment would have prevented P436's death. The model trajectory contains the generated policy and a truncated execution log. Use a full decision trace to establish causality for the other F7 cases.

[Calibration artifacts](https://github.com/xand1ex999/guinness/blob/yehor/harness-submission-evidence/eval/results/2026-11-14-gemini-seed42/README.md).
