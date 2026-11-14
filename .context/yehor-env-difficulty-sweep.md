# Branch: yehor/env-difficulty-sweep

- **Issue:** #67
- **Owner:** yehor
- **Agent:** yehor-codex-4
- **Parent branch:** main
- **Created:** Sat 17:30

## Goal
Screen the `arrival_mean` difficulty knob offline against the merged baselines and the reference on fixed seeds. Record candidate evidence without changing defaults or public rules before Kostiantyn approves.

## Files and folders I own
- `docs/TUNING.md`
- `.context/yehor-env-difficulty-sweep.md`

## Don't touch
- `ed72/environment/hospital/config/default.json`, SPEC, CONTRACTS, or HANDBOOK values until Kostiantyn decides.
- Other owners' code, including `eval/tuning/` (#69).

## Contracts used or changed
- Uses merged #64 `Config` and `generate_world(seed, config)`, the #52 baseline policy API, and #16 `ReferencePolicy.actions(observation)` from pinned commit `cc53151`.
- No contract or runtime changes.

## Status
- [x] Screened arrival means 2.45, 2.475, and 3.0 on seeds 1–5; other means were used to bracket the transition.
- [x] Compared the reference, severity-first, reactive proxy, do-nothing, stop-early, all merged exploit baselines, and #62 idle-then-fill.
- [x] Recorded full per-seed scores, source pins, driver method, and limitations in `docs/TUNING.md`.
- [ ] Kostiantyn's decision on candidate 3.0; no default/SPEC/HANDBOOK changes until then.

## Decisions and notes
- 2026-11-14: candidate `arrival_mean = 3.0` is a screening result, not an adopted value. It passes the checked reference/exploit ordering on seeds 1–5 and keeps worst divert-all at 47.93, but doubles the starting mean and needs a fairness decision plus held-out/model evaluation.
- The fixed seed makes each candidate reproducible, but changing arrival mean changes the arrivals-stream draw sequence; results are not patient-by-patient paired across candidate values.
- Numeric runs use base main `d1986f054adc9ca4c06ed3863a4e04c7ecac80c9` and reference policy source `cc53151a31fb6db8557b1a9c65274f63580c922a`. PR #73's failure-code attribution change is outside the base and does not affect numeric rewards.

## Handoff
Done: offline arrival-mean sweep and per-seed baseline comparison, documented in `docs/TUNING.md`. Next: get Kostiantyn's decision and coordinate with #69 on any follow-up knob. Reproduce by archiving the pinned base, overlaying `ed72/solution/policy.py` from `cc53151`, then running the configured baseline driver described in `docs/TUNING.md`; no paid model run is needed.
- 
