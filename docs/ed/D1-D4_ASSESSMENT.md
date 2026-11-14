# D1–D4 assessment (2026-11-14)

This maps the agreed decisions D1–D4 against what exists. No code was changed for this assessment.

## 0. Blocking finding: three specs disagree

| Source | Where | Ticks | Reward | Control | Scoring runs in |
|---|---|---|---|---|---|
| Team spec ED-72 (Yehor, merged as #29 on `origin/main`, 12:38) | `docs/SPEC.md`, `docs/CONTRACTS.md`, `docs/EVAL.md`, `docs/PLAN.md` | 15 min, `advance(15..120)` with early return | Harm H over modules M1–M4, normalised between trivial-policy anchors and a full-information planner | 21 MCP tools (`board`, `admit`, `assign`, `assess`, `advance`, …), 600-call cap | `collect.py` inside the `hospital` sidecar; verifier only copies `/evidence/report.json` |
| D1–D4 (this brief) | not in the repo | 30 min, fixed, 144 ticks | `60·O + 20·T + 10·O·W + 10·O·B` from "the current rulebook" | One consolidated observation, one JSON action batch per tick | Separate verifier container |
| M1 engine (this branch) | `backend/app/edsim/`, `docs/ed/` | 1-minute integration, `advance_time(1..120)` | Only a proposal (geometric mean) | Single actions + 9 observation calls | Not implemented |

- The "rulebook" with the additive formula, the zone model ("admit a patient into a zone", "assign a nurse to a zone") and the list of known scoring exploits is not in any branch (`main`, `research`, both Kostiantyn branches searched).
- The team spec is also a world spec: 15 beds, 8-hour shifts, wrong triage labels with an `assess` tool, patient health 0–100, notices with precursors, a 12-hour handover tail, an `ed72/` folder layout and lane ownership (A env, B reward, C reference, D harness). The M1 engine models a different world: 23 beds, 12-hour shifts, no wrong labels, hazard-based deterioration.
- This branch is not based on `main`. `main` has docs only, so a merge is mechanical except for `AGENTS.md` and `docs/CONTRACTS.md`.

AGENTS.md says contracts change only through `contract-change` (issue #1), and `ed72/` folders are lane-owned. Implementing D1–D4 on top of the M1 engine without reconciling would put this branch in direct conflict with the team's merged spec.

## 1. D1: 30-minute ticks, 8 h dev / 72 h benchmark

| Item | Status |
|---|---|
| Configurable duration | **Partly.** `horizon_hours` (1–72) exists |
| 8-hour run is the first 8 hours of the benchmark | **No, conflict.** `with_horizon` rescales event counts and windows and budget. Seed 1 at 8 h: 29 patients and 0 events. The first 8 h of the 72 h seed: 29 patients and 3 events (2 equipment failures, 1 sickness) |
| 30-minute decision tick | **Not yet.** The agent chooses 1–120 minutes |
| Mechanics independent of tick | **Yes.** All rates are per minute and integrated every minute, so a 30-minute decision tick changes no durations, fatigue rates or event timing |

Interaction to decide: with the same greedy policy (seeds 1–3), moving from 10-minute to 30-minute decisions drops acuity 1–2 patients treated within target from 80% to 35%, and raises critical events from 32 to 41. The targets (10 and 20 minutes) and the acuity-1 hazard scale (45 minutes) were calibrated for faster decisions. Under a 30-minute cycle, part of that harm is unavoidable for any policy, including the reference.

## 2. D2: `Score = 60·O + 20·T + 10·O·W + 10·O·B`, reward = Score/100

| Item | Status |
|---|---|
| Evaluator | **Not implemented** on this branch |
| O, T, W, B definitions | Missing from the brief (defined in the rulebook, which I don't have). The engine records everything needed: per-patient arrival, first active treatment, outcomes, deteriorations; fatigue minutes; ledger and budget |
| Exploit: uncovered bed counts as timely | **Guarded by the engine.** Timeliness uses `first_active_min`, which is set only when bed, doctor, nurse and required equipment are all present (`flow.step_treatment`). A parked patient also still leaves without being seen (`test_low_acuity_patient_leaves_without_being_seen_even_if_parked_in_a_bed`). An explicit evaluator test is still needed |
| Exploit: end-of-episode patients scored favourably without treatment | **Present in my earlier §8 draft** ("patients still in the ED are scored on their current state"): an untreated patient who has not deteriorated yet would get full outcome credit. Proposed fix below |
| Partial credit that inflates trivial policies | **Present in the draft:** walk-outs 0.2 and diverted 0.3. With W = B = 1 for doing nothing, a do-nothing run would score about 0.15–0.2 instead of about 0 |
| Untreated patients in T | Must count as 0, not be excluded, or do-nothing gets an undefined or high T |

Proposed corrections (not implemented, need your OK):
1. Patients still in the department at the end are scored after a no-action tail run (the team spec uses 12 hours), with the same mechanics. Untreated patients then deteriorate or walk out and are scored on that.
2. Walk-outs, critical events and diversions score 0 in O. Never-treated patients score 0 in T.
3. W and B only scale the O terms, as in the formula, so they cannot rescue a run with poor outcomes.

## 3. D3: direct control, one observation and one action batch per tick

| Item | Status |
|---|---|
| Direct control of individual patients and staff | **Yes**, bed and patient level (`start_treatment`, `assign_staff`, `schedule_break`, `request_temporary_staff`, `request_repair`, `set_diversion`, …) |
| Zones | **Conflict.** The engine uses beds and per-patient staff assignment; the brief's examples use zones. The team spec also uses beds and per-patient assignment |
| Consolidated observation | **Not yet.** It is split across 9 calls; `department_status` is closest |
| Batch with partial success | **Easy.** Each action is already atomic, so a batch applies them in order and returns one result per action; invalid ones change nothing |
| Model-agnostic runtime | Two options, both available in the installed Harbor 0.26.0: (a) OpenCode over MCP with two tools, `observe` and `step(actions)` (step applies the batch, advances 30 minutes and returns the next observation, so about one model call per tick); (b) a custom Harbor agent (`-a module.path:ClassName`, confirmed in `harbor run --help`): a small loop calling any OpenAI-compatible endpoint (Verda, Workshop) with one request per tick |
| Run length | 144 ticks at roughly 10–40 s per model call is about 0.5–1.5 h; `task.toml` has `timeout_sec = 900` today. An 8-hour run (16 ticks) fits in it |

## 4. D4: separate verifier container computes the score

| Item | Status |
|---|---|
| Separate mode, collect hook, sidecar artifact, runtime token | **Exists** (`harbor/unfindable/`), validated in Spike S0 (shared-mode forgery succeeded, separate mode blocked it) and in real Harbor runs (oracle 1.0, nop 0.0, Kimi 1.0) |
| Where the score is computed | **Conflict.** Today the sidecar computes the reward behind `/admin/finalize`; `tests/verify.py` only validates and copies it. D4 wants the verifier to compute O, T, W and B |
| Minimal adaptation | `collect.py` (in the sidecar) freezes the episode, runs the end-of-episode tail and writes the full record (ground truth and event log) to `/evidence/episode.json`. The scorer lives in `tests/`, which Harbor uploads only to the verifier container, so neither the agent nor the sidecar image contains scoring code. `verify.py` computes the score and writes `reward.txt` |
| Agent cannot reach verifier internals | The verifier runs in a fresh container after the agent finishes. The admin route needs a token the agent cannot read. To harden: also accept only loopback callers. Re-probe from `main` in the first Harbor run |
| Public spec | Not yet. Needs a public rules file in the agent container (and an MCP `rules` tool) with the formula, the metric definitions, the acuity table, the actions, costs and event mechanics |

Credentials: `.env` has `VERDA_INFERENCE_API_KEY` and `MOONSHOT_API_KEY`. There is no Workshop key yet; I need its variable name and base URL. The provider stays configurable (`--base-url`, `--api-key-name`, as in the earlier Kimi run).

## 5. Proposed implementation steps (once §0 is resolved)

1. Reconcile with `main`: merge it into this branch; record D1–D4 in `docs/SPEC.md` and `docs/CONTRACTS.md` through `contract-change`, or decide that this branch follows the team spec instead.
2. D1: generate the 72 h world always and truncate it to the horizon; scale only the budget pro rata; add a fixed 30-minute `step`. Test that an 8 h run equals the first 16 ticks of the 72 h run.
3. D3: `observe()` and `step(actions)` on the engine with per-action results; MCP tools `observe`, `step`, `rules`. Remove the 1–120 `advance` from the agent surface.
4. D2 + D4: export the episode record from the sidecar; the scorer in `tests/` with O, T, W and B, the end-of-episode tail and the exploit tests; `reward.txt` = Score/100.
5. Harbor task for the ED (adapt `harbor/unfindable/`), then oracle and nop runs, then an 8 h run with a frontier model, then the 72 h pipeline.
