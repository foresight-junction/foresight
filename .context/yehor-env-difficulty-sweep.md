# Branch: yehor/env-difficulty-sweep

- **Issue:** #67
- **Owner:** yehor
- **Agent:** yehor-codex-4
- **Parent branch:** main
- **Created:** Sat 17:30

## Goal
Screen the arrival rate against the reference and baseline policies on fixed seeds. Ship the selected default together with its public rules and test updates.

## Files and folders I own
- `docs/TUNING.md` and this handoff
- Default arrival rate in config, constants, SPEC and handbook
- Tests tied to the former default

## Don't touch
- Config loader, policy implementations, scorer and `eval/tuning/` (#69).

## Contracts used or changed
- Uses merged #64 `Config` and `generate_world(seed, config)`, the #52 baseline policy API, and #16 `ReferencePolicy.actions(observation)` from pinned commit `cc53151`.
- The default rate is 3.0 arrivals per tick. Public tool and score shapes are unchanged.

## Status
- [x] Screened arrival means 2.45, 2.475, and 3.0 on seeds 1–5; other means were used to bracket the transition.
- [x] Compared the reference, severity-first, reactive proxy, do-nothing, stop-early, all merged exploit baselines, and #62 idle-then-fill.
- [x] Recorded full per-seed scores, source pins, driver method, and limitations in `docs/TUNING.md`.
- [x] Kostiantyn selected 3.0. Updated the defaults, SPEC, handbook and affected tests.
- [ ] Integrator merges #77 after the #16 reference.

## Decisions and notes
- 2026-11-14: the selected 3.0 rate passes the reference and exploit ordering on seeds 1–5. The maximum divert-all score was 47.93. Held-out seeds and model performance remain for the evaluation lane.
- The fixed seed makes each candidate reproducible, but changing arrival mean changes the arrivals-stream draw sequence; results are not patient-by-patient paired across candidate values.
- Numeric runs use base main `d1986f054adc9ca4c06ed3863a4e04c7ecac80c9` and reference policy source `cc53151a31fb6db8557b1a9c65274f63580c922a`. PR #73's failure-code attribution change is outside the base and does not affect numeric rewards.

## Handoff

Kostiantyn selected 3.0 arrivals per tick on #67. The runtime constant, default JSON, SPEC and handbook use the selected rate. The red-team round-one ordering still exercises its original 1.5-arrival configuration. The new default was evaluated with the reference and baselines on seeds 1–5, as recorded in docs/TUNING.md.
