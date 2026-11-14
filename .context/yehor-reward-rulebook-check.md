# Branch: yehor/reward-rulebook-check

- **Issue:** #35
- **Owner:** yehor
- **Agent:** yehor-codex-3
- **Parent branch:** main

## Goal
Prepare a replay matrix for every decision in SPEC §12 and identify what is needed to compare the Python port with Denys's JavaScript prototype. No decision is marked confirmed until Denys or the prototype supports it.

## Files and folders I own
- `.context/yehor-reward-rulebook-check.md` only

## Don't touch
- `docs/SPEC.md`, `docs/CONTRACTS.md`, `docs/ED_Management_Simulator_RU.md`
- Any simulator, scorer, handbook, issue or PR

## Contracts used or changed
- None changed. Reference CONTRACTS v1 and SPEC §12 from `main` at merge commit `2a5ea0f` (PR #43), plus rulebook §§2–14 on `main`.

## Status
- [x] Read rulebook §§2–14 and the SPEC §12 decisions in PR #43.
- [x] Drafted a complete comparison matrix and boundary-case replay plan below.
- [x] Obtain Denys's confirmation on #35.
- [ ] Track Denys's SPEC confirmation PR.
- [ ] If any rule changes, announce on #1 and use `contract-change`; coordinate matching handbook text with #7.

## Denys's confirmation

Denys confirmed all adopted SPEC §12 rules and the three TUNE starting values on issue #35.
He said there is no JavaScript prototype and removed the prototype-parity requirement.
The matrix below preserves potential Python replay test cases. Its statuses describe
literal replay evidence, which has not been collected.

Denys owns the confirmation PR from `leonardodadenchik/reward-rulebook-confirm`.
The #67 and #69 tasks own calibration measurements. No gameplay contract changed here.

## Comparison matrix

| Rulebook §14 item | SPEC §12 choice | Probe or confirmation needed | Status |
|---|---|---|---|
| Arrival rate and daily cycle | `TUNE`: mean 1.5 arrivals/tick; sinusoidal ±50%, peak 15:00, low 03:00; about 215 arrivals before events | Compare expected rate/time profile and seeded arrivals against the JS engine over a full episode; clarify whether its cycle is sinusoidal and its phase/amplitude | Unconfirmed |
| Flu-wave severity mix | `TUNE`: ESI 3 40%, ESI 4 35%, ESI 5 25% | Compare the six ticks of 2 extra arrivals and category counts/probabilities; base rulebook only says “mostly” ESI 3–5 | Unconfirmed |
| Wellbeing weights and staff-time denominator | `TUNE`: `a=1.0`, `b=0.05`; share of on-shift staff-ticks above fatigue 60; W clipped at 0 | Hand-calculate a short trace with known on-shift/rest/fatigue/faint counts; confirm denominator (all on-shift person-ticks or all possible person-ticks), threshold strictness, and clipping | Unconfirmed |
| Budget curve above €12,000 | Linear to 0 at €24,000, clipped to [0,1] | Check spend at €12,000, an interior point, €24,000 and above cap; exact formula from prototype or Denys | Unconfirmed |
| Clock starts 08:00; initial fatigue 0 | Adopted | Verify tick-0 clock, all 15 staff status/fatigue, and end clock after 144 ticks | Unconfirmed |
| Separate random streams | Arrivals/events share a stream; each patient's hazards use its own stream | Replay same seed with changed actions; confirm arrivals/events and per-patient rolls remain unchanged | Unconfirmed |
| Eight-step tick order | Adopted rulebook §9 order | Boundary trace: returns/agency arrivals; event start/end and warnings; arrivals/diversion; observation; ordered actions; coverage/treatment/discharge; hazards; fatigue/fainting | Unconfirmed |
| Coverage priority and fractional rounding | Severity, then admission time; round fractional coverage down | Construct mixed-severity beds with tied admission order and fractional staff coverage; compare which beds progress | Unconfirmed |
| CT disclosure/queue/stop point | Need shown on arrival; no queue; treatment pauses at half rounded up | Test arrival visibility, several simultaneous CT patients, odd/even treatment lengths, and CT downtime/restart | Unconfirmed |
| ESI 3 upgrade | Upgraded patient follows ESI 2 rules, gets a new 50% CT roll, scored as highest ESI reached | Force/locate an upgrade case; compare hazards, treatment/zone eligibility, CT draw, outcome weight and event record | Unconfirmed |
| Faint recovery / agency arrival | Fainted staff return after 10 ticks at about fatigue 65; agency arrives after 4 ticks at fatigue 0 in rest | Trace faint at threshold and agency order across exact tick boundaries; check rest-room location and reassignment requirement | Unconfirmed |
| Diversion | Free, cannot overlap, 70% of arrivals including bus-crash arrivals diverted for 4 ticks | Seed/control arrivals during active diversion, including bus-crash patients; verify probability semantics, duration boundaries and rejection while active | Unconfirmed |
| Repair | Only while CT is down; €2,000; works after 3 ticks or original recovery if sooner | Compare order at breakdown start/midpoint/one tick before natural recovery; resolve whether “after 3 ticks” means active at t+3 | Unconfirmed |
| Warning timing | Exact start tick visible from 10 ticks ahead (flu) / 8 ticks ahead (bus), through event end | Check first visible tick, visibility at event start/end and whether a warning can appear in the same tick as event start | Unconfirmed |
| Timeliness eligibility | `T` uses first covered bed tick; diverted and never-admitted count late | Compare admission tick vs first covered tick around each ESI target boundary; include diverted/never-admitted cases | Unconfirmed |
| End-of-episode bed loss | Loss 0.3 only if at least one covered tick; otherwise loss 1 | Compare a covered patient, a never-covered patient, and waiting patient at tick 143; verify exact event/score bookkeeping | Unconfirmed |

## Required inputs and probe procedure
- Denys or the #41 owner must provide the JavaScript prototype repository/file, exact revision, runtime/setup instructions, and the fixed-seed/fixed-action replay entry point. The checked-in Russian rulebook only identifies `@Denys`; no prototype is linked in #35, #41, PR #43 or accessible local/GitHub branches.
- Confirm whether the prototype is the reference for unspecified numeric choices or whether Denys intends SPEC §12's explicit TUNE values to be port-only defaults.
- For deterministic boundary cases, inject identical exogenous arrivals/events/hazard outcomes into both engines if their interfaces permit it, then compare observations, events and score. The same numeric seed in JS and Python does not imply identical RNG streams or draws. If injection is unavailable, compare within-engine same-seed reproducibility separately, and compare cross-engine distributions/mechanics over matched scenarios rather than attributing sequence differences to rule differences.
- Record the smallest differing tick and field. Keep stochastic comparisons separate from exact deterministic replay.
- Keep fixture traces synthetic and avoid changing simulator or scorer code in this branch.

## Decisions and notes
- 2026-11-14: PR #43 merged to `main` at `2a5ea0f`; the matrix reflects its SPEC §12. The Russian rulebook remains authoritative.
- 2026-11-14: No prototype result or Denys confirmation is available yet. Every matrix row is explicitly pending; no claim of “none found” is justified.
- 2026-11-14: SPEC adopts both rulebook §13 exploit fixes: timeliness begins on first covered tick; end loss 0.3 requires a covered tick. These need direct score-boundary probes.

## Handoff

Denys's confirmation is linked in #35. The SPEC confirmation PR is his. Use the matrix
above to derive synthetic Python regression cases if #10 or #15 needs additional coverage.
