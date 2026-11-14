#!/usr/bin/env bash
# Creates the labels and the task issues for the AfterQuery challenge. Safe to run twice:
# an issue whose code (A1, B2, ...) is already in a title is skipped.
#
# The board already exists: do NOT run this on xand1ex999/guinness. It mirrors the live board
# (titles, bodies, priorities and #39 waves as of Sat 14 Nov 15:00 UTC, see #41), so a fresh repo
# gets the same tasks. Retired codes are never reused: B7 (closed, not planned).
#
#   scripts/bootstrap-board.sh                                   labels + issues
#   scripts/bootstrap-board.sh env=kostia reward=anna ref=max harness=yehor
#                                                                also pushes the P0 task branches for each lane owner
# Works with macOS's default bash 3.2. Needs: gh auth login.

set -euo pipefail
die() { echo "error: $*" >&2; exit 1; }
command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1 || die "gh isn't logged in (run: gh auth login)"
cd "$(git rev-parse --show-toplevel)"

scripts/wt.sh init

echo "creating challenge labels..."
for a in env reward ref harness train; do gh label create "area:$a" --color 1d76db --force >/dev/null; done
gh label create p0 --color b60205 --description "needed for the thin slice (Sat 18:00)" --force >/dev/null
gh label create p1 --color fbca04 --description "needed to submit" --force >/dev/null
gh label create p2 --color c5def5 --description "only if time" --force >/dev/null
for w in 0 1 2 3 4 5 6 7 8; do
  gh label create "wave:$w" --color c2e0c6 --description "execution order, see #39" --force >/dev/null
done

EXISTING="$(gh issue list --state all --limit 300 --json number,title -q '.[] | "\(.number)\t\(.title)"')"
MAP="$(mktemp)"

# mk <code> <area> <slug> <prio> <wave> <title> <body>
mk() {
  local code="$1" area="$2" slug="$3" prio="$4" wave="$5" title="$6" body="$7" n
  n="$(printf '%s\n' "$EXISTING" | grep -F "] $code: " | head -1 | cut -f1 || true)"
  if [ -n "$n" ]; then
    echo "skip  #$n  $code (exists)"
  else
    n="$(gh issue create --title "[$area] $code: $title" --label "todo,area:$area,$prio,wave:$wave" --body "$body" | grep -oE '[0-9]+$')"
    echo "made  #$n  [$area] $code: $title"
  fi
  printf '%s %s %s %s %s %s\n' "$code" "$area" "$slug" "$prio" "$wave" "$n" >> "$MAP"
}

# Bodies use quoted heredocs so backticks and $ stay literal.

# ---------- Lane A: world and tools ----------
read -r -d '' B <<'BODY' || true
> Realigned to docs/ED_Management_Simulator_RU.md by #41 / PR #43. Read docs/SPEC.md and docs/CONTRACTS.md on branch kostiantyn/docs-rules-realign until PR #43 merges.

Read first: docs/ED_Management_Simulator_RU.md (rules), AGENTS.md (section 10), docs/CHALLENGE.md, docs/SPEC.md, docs/CONTRACTS.md.

**Goal:** `generate(seed)` builds the rulebook world (SPEC §3, rulebook §3–§7): beds R1–R3 (resus), A1–A8 (acute), F1–F6 (fast-track); staff D1–D6 and N1–N9, all resting at fatigue 0; Poisson arrivals with a daily cycle (SPEC §12 `TUNE`: mean 1.5 per tick, ±50% sinusoid, peak 15:00, low 03:00) and ESI mix 4/14/34/30/18%; `needs_ct` for 50% of ESI 1–2, decided at arrival; the four events with seeded start ticks inside their windows (sick call 28–35 with the two sick nurses, flu wave 50–61 with extra arrivals ESI 3/4/5 = 40/35/25%, CT breakdown 66–75, bus crash 96–109 with ESI 1/2/3 = 20/30/50%); separate random streams for arrivals/events and per patient (#32).

**Files you own:** `ed72/environment/hospital/ed72_sim/world.py`, its tests.
**Depends on:** #41 (rules), #32 (random streams).
**Rules:** synthetic data only. All randomness from the seeded streams in `rng.py`. No network, no clock.
**Done when:** same seed → same world, different seeds differ, the ESI mix is within tolerance over many seeds (tested), and a JSON dump of 3 patients and the event schedule is pasted in the PR.

Claimed by kostiantyn-claude-2 (branch `kostiantyn/env-world`).
BODY
mk A1 env world p0 1 "Seeded world generator: patients, staff, beds, equipment, events" "$B"
read -r -d '' B <<'BODY' || true
> Realigned to docs/ED_Management_Simulator_RU.md by #41 / PR #43. Read docs/SPEC.md and docs/CONTRACTS.md on branch kostiantyn/docs-rules-realign until PR #43 merges.

Read first: docs/ED_Management_Simulator_RU.md (rules), AGENTS.md (section 10), docs/CHALLENGE.md, docs/SPEC.md, docs/CONTRACTS.md.

**Goal:** the 144-tick engine (SPEC §4, rulebook §9): the eight-step tick order, zone/ESI admission rules, coverage per zone (min of doctor and nurse coverage, rounded down, beds covered by severity then admission time), treatment progress (+1 tick in the penalty zones, CT stop at half treatment), the hazard table, fatigue and fainting, event-log lines exactly as CONTRACTS "Event log", and a Python API `observe()` / `step(actions)` returning ActionResults with the CONTRACTS rejection reasons. Thin slice: patients, zones, staff, coverage, hazards and fatigue for all 144 ticks; events, agency, repair and divert may be stubs until #6.

**Files you own:** `ed72/environment/hospital/ed72_sim/` except `world.py` and `scoring/`.
**Depends on:** #3 (stub the world until it lands), #32. Shapes: docs/CONTRACTS.md v1.
**Rules:** no reset or undo. The clock moves only on `step`. Invalid actions are rejected with a reason and change nothing; the other actions in the list still apply. The hospital counts the 500-call cap.
**Done when:** a pytest drives 144 ticks through the Python API; replaying the same seed and actions gives a byte-identical event log; one unit test per rule (coverage rounding, priority, +1 tick, CT stop, each hazard row, faint).

Claimed by kostiantyn-claude-2 (branch `kostiantyn/env-sim-core`).
BODY
mk A2 env sim-core p0 2 "Sim core: tick loop, deterioration, event log, thin-slice tools" "$B"
read -r -d '' B <<'BODY' || true
> Realigned to docs/ED_Management_Simulator_RU.md by #41 / PR #43. Read docs/SPEC.md and docs/CONTRACTS.md on branch kostiantyn/docs-rules-realign until PR #43 merges.

Read first: AGENTS.md (section 10), docs/ED_Management_Simulator_RU.md, docs/CHALLENGE.md, docs/SPEC.md, docs/CONTRACTS.md.

**Goal:** expose the three v1 tools `rules`, `observe` and `step(actions)` exactly as in docs/CONTRACTS.md over MCP (streamable-http at /mcp) and through the `ward` CLI in the agent container (`ward rules`, `ward observe`, `ward step --json '[...]'`). Add GET /health. The hospital counts the 500-call cap and returns `call_cap_reached` and `episode_over` as in CONTRACTS.

**Files you own:** `ed72/environment/hospital/server.py`, `ed72/environment/ward`.
**Depends on:** A2, D1 (tells us MCP vs CLI as the main path).
**Rules:** no reset, seed, ground-truth or finalise endpoint.
**Done when:** from `main`, `ward observe` returns an observation and an MCP client lists exactly the 3 tools.
BODY
mk A3 env tool-server p0 3 "Tool server: MCP + ward CLI + /health" "$B"
read -r -d '' B <<'BODY' || true
> Realigned to docs/ED_Management_Simulator_RU.md by #41 / PR #43. Read docs/SPEC.md and docs/CONTRACTS.md on branch kostiantyn/docs-rules-realign until PR #43 merges.

Read first: AGENTS.md (section 10), docs/ED_Management_Simulator_RU.md, docs/CHALLENGE.md, docs/SPEC.md, docs/CONTRACTS.md.

**Goal:** the rules that make the 144 ticks hard (SPEC §3, §4, §12). The four events and their warnings (the warning shows the exact start tick and stays visible until the event ends); sick nurses leaving their post and returning after 20 ticks; the agency staff lifecycle (arrive after 4 ticks at fatigue 0 in rest, stay 16); `repair` (only while the CT is down; back after 3 ticks, or at its original time if sooner); `divert` (free, 70% of arrivals including bus-crash patients, 4 ticks, no overlap); the hard spending limit of €24 000 for agency and repair; faint recovery at about 65 fatigue.

**Files you own:** rule modules under `ed72/environment/hospital/ed72_sim/rules/`.
**Depends on:** A2 (#4), B1 (#10). Tell lane B the consequence of each new rule before you merge.
**Done when:** each rule has a test showing its sim consequence, and the reference policy (#16) still clearly beats the baselines (reactive proxy, stop-early, do-nothing).
BODY
mk A4 env events p1 4 "Events, warnings, agency staff, CT repair, diversion and budget limit" "$B"
read -r -d '' B <<'BODY' || true
> Realigned to docs/ED_Management_Simulator_RU.md by #41 / PR #43. Read docs/SPEC.md and docs/CONTRACTS.md on branch kostiantyn/docs-rules-realign until PR #43 merges.

Read first: AGENTS.md (section 10), docs/ED_Management_Simulator_RU.md, docs/CHALLENGE.md, docs/SPEC.md, docs/CONTRACTS.md.

**Goal:** the agent-visible handbook and the task instruction. `HANDBOOK.md` is the English agent-visible version of the rulebook: all rate tables, the hazard table, events and warnings, actions and prices, the score formula with both rulebook §13 fixes, and the W and B formulas. The `rules` tool serves it. `instruction.md` tells the agent to call `rules`, then loop `observe` / `step` until tick 143, and that stopping early lets the remaining ticks run with no actions. Plain wording, no tricks. This protects the 30 points for meaningful difficulty.

**Files you own:** `ed72/environment/workspace/HANDBOOK.md`, `ed72/instruction.md`.
**Depends on:** A2, A4, B1.
**Done when:** a table in the PR maps every rulebook section and every scorer rule to a handbook section, and a teammate who has not read the code can plan 5 sample ticks from the handbook alone.
BODY
mk A5 env handbook p1 5 "HANDBOOK.md and instruction.md: every rate table and scored rule written down" "$B"
read -r -d '' B <<'BODY' || true
> Realigned to docs/ED_Management_Simulator_RU.md by #41 / PR #43. Read docs/SPEC.md and docs/CONTRACTS.md on branch kostiantyn/docs-rules-realign until PR #43 merges.

Read first: AGENTS.md (section 10), docs/ED_Management_Simulator_RU.md, docs/CHALLENGE.md, docs/SPEC.md, docs/CONTRACTS.md.

**Goal:** one hospital-side config with the knobs from SPEC §7 and the TUNE values in SPEC §12: arrival rate and daily cycle, flu-wave mix, event windows and warning lead, budget, W weights. Tune with lane C so the reference clearly beats the reactive proxy and permanent diversion (about 47 points).

**Files you own:** `ed72/environment/hospital/config/`.
**Depends on:** A2, C2.
**Done when:** changing one value changes the episode, the chosen values are written back into SPEC §12 (via contract-change), and the baseline table is in the PR.
BODY
mk A6 env knobs p1 6 "Difficulty config: one file of knobs" "$B"
read -r -d '' B <<'BODY' || true
Read first: AGENTS.md (section 10), docs/CHALLENGE.md, docs/SPEC.md, docs/CONTRACTS.md.

**Goal:** more ordinary events (for example a lab slowdown or a second monitor fault) and a second bed and equipment layout, so one set of tuned rules is not the whole test.

**Files you own:** `ed72/environment/hospital/ed72_sim/rules/events_extra.py`, `ed72/environment/hospital/config/layouts/`.
**Depends on:** A4, A6.
**Done when:** each new event has a notice precursor and a handbook line, and the reference scores >= 0.9 on both layouts.
BODY
mk A7 env events-extra p2 7 "Extra event types and a second hospital layout" "$B"
read -r -d '' B <<'BODY' || true
> Realigned to docs/ED_Management_Simulator_RU.md by #41 / PR #43. Read docs/SPEC.md and docs/CONTRACTS.md on branch kostiantyn/docs-rules-realign until PR #43 merges.

## Objective

Build an automated test suite that proves no tool result of the ED-72 hospital server leaks hidden state. It drives full episodes (thin slice first, the full 144 ticks once #6 lands) with a scripted policy that calls `rules`, `observe` and `step` repeatedly, records every result, and asserts the firewall rules below. The suite must also be proven to bite with a mutation check.

## Context

Repo: xand1ex999/guinness (private), base branch `main`. Source of truth: docs/ED_Management_Simulator_RU.md (rulebook), docs/SPEC.md, docs/CONTRACTS.md, AGENTS.md (esp. section 10). Until PR #43 merges, read SPEC and CONTRACTS on branch `kostiantyn/docs-rules-realign`. Nothing under `ed72/` exists on main yet; it is created by #22 (D2).

ED-72 in brief (SPEC §1 to §5):
- An agent runs a fictional, fully synthetic emergency department for 144 ticks of 30 minutes (72 simulated hours): 17 beds in three zones, 6 doctors and 9 nurses, about 215 patients plus events.
- The observation is now full (rulebook §10): the agent sees every waiting patient with its ESI and CT need, every bed, every staff member and fatigue, the CT, warnings and budget. What is hidden is only the future: later arrivals, unannounced events (sick call, CT breakdown), dice rolls, the seed and score values.
- The tools are `rules`, `observe` and `step(actions)` (CONTRACTS v1). Tool-call cap 500. No reset, no undo, no seed or ground-truth endpoint.
- Warnings exist only for announced events (flu wave 10 ticks ahead, bus crash 8 ticks ahead) and show the exact start tick.
- AGENTS §10 rule 1: nothing that reveals the answer may reach the agent. Harbor layout (SPEC §9): the `main` agent container holds only HANDBOOK.md and the `ward` CLI; the `hospital` sidecar holds the sim, seed (`ED72_SEED`), config (`ED72_CONFIG`), event log and scorer, MCP at http://hospital:8000/mcp.

Why this matters: if any tool result leaks hidden state, the benchmark is broken and judges will find it. #5 (A3) builds the server but its "Done when" does not test leakage, so this issue closes that gap.

## Relevant files

- New: `ed72/environment/hospital/tests/test_firewall.py` (lane A, this issue owns it).
- Reads (do not edit): `ed72/environment/hospital/server.py` (#5), the sim API in `ed72/environment/hospital/ed72_sim/` (#4), the Dockerfiles and compose from #22 (D2) for check (f).
- Must not change tool shapes. If a leak can only be fixed by a shape change, use the `contract-change` skill and propose it on #1.
- Lane ownership: see CONTRACTS "Who owns which folder". Leaks found in other lanes' files: comment on the owning issue, do not edit.

## Branch and integration requirements

- Start from the latest `main`, then create the worktree with `scripts/wt.sh new <owner> <area> <task> -i <issue>`. Claim with the `claim-task` skill first.
- Re-check `main` and the status of #4, #5, #6 before you start and before you open the PR.
- Stay inside the files listed as yours. Changes to docs/CONTRACTS.md go only through the `contract-change` skill.
- Commit each working logical unit through `pre-commit-gate` and push; post progress comments starting with your agent id; open a PR with `Closes #<n>` via `ship-pr` after `cross-review`. Never force-push. If blocked, label `blocked` and comment.
- Python 3.12, stdlib first, type hints, `uvx ruff format . && uvx ruff check --fix .`, pytest in the same PR; deterministic from one seed.

## Implementation requirements

1. A scripted policy (test double, not an LLM) that, on a fixed seed, calls `rules`, `observe` and `step` repeatedly: admits, assigns, orders agency staff, repairs, diverts, passes empty ticks, and sends invalid actions (bad ids, wrong zones, no free bed, over the hard limit) to exercise rejections. Collect every result as raw JSON text.
2. Ground truth comes only from sim internals imported inside the test (seed, config path, RNG state, event log, future arrivals, scheduled event start ticks, scorer values). The agent-facing server code is never modified for the test.
3. Two complementary checks on every collected result:
   - Deny-list of hidden field names (`seed`, `rng`, `event_log`, `score`, `reward`, `O`, `T`, `W`, `B`, and so on; derive the list from the sim's internal field names plus CONTRACTS).
   - Value-based check: no patient id, arrival tick or event start tick that is still in the future appears in any result before it is announced or has happened (match by structured field, not by a bare digit).
4. Assertions (a) to (f) below, each its own test.
5. Mutation check: a test double (monkeypatched view function) injects a leaked field; assert the firewall suite fails on it. Include one mutation per assertion class where practical (future arrival, unannounced event, seed, score value).
6. Start with the thin slice from #4 and #5; extend to the full 144-tick run once #6 lands. Label any mock with a `MOCK:` comment.
7. Keep total runtime under 60 s (short horizon for the unit run; a full run may be marked `slow`).

## Acceptance criteria

- [ ] (a) No result contains a future arrival, or an unannounced event before it starts (sick call, CT breakdown).
- [ ] (b) No result contains the seed, config path, RNG state, dice rolls, event-log internals or score values (O, T, W, B, score, reward).
- [ ] (c) Warnings appear only for announced events (flu wave, bus crash), carry the exact start tick, and appear no earlier than the rulebook's lead time.
- [ ] (d) Observation and results match the CONTRACTS shapes exactly (schema test, no extra fields).
- [ ] (e) Rejected actions are reported with the right CONTRACTS `reason`, and `call_cap_reached` and `episode_over` come back as specified, leaking nothing.
- [ ] (f) The `main` agent image filesystem contains no sim code, seed, config or scorer (scan the built image or the Dockerfile COPY context; coordinate with #22 D2).
- [ ] Mutation check: injecting a leaked field into a test double makes the suite fail.
- [ ] Exactly the 3 tools are exercised; the test asserts the tool list matches CONTRACTS so a new tool cannot skip the firewall.
- [ ] Suite runs in CI (#24 D4) and finishes in under 60 s.
- [ ] No tool shape changed; any needed shape change went through `contract-change` on #1.

## Testing requirements

- `cd ed72/environment/hospital && uv run pytest tests/test_firewall.py -q` passes, and fails when the mutation is applied.
- Run with at least two seeds to show the check is not seed-specific.
- Lint: `uvx ruff format . && uvx ruff check --fix .`.

## Deliverables

- `ed72/environment/hospital/tests/test_firewall.py` (plus a small helper module in the same folder if needed).
- A short note in the PR description listing each rule (a) to (f) and the test that covers it.
- Comments on #5 and #4 listing any leak found, and on #13 and #14 (red-team) describing what the suite already covers.

## Dependencies

- #4 A2 (sim API) and #5 A3 (server, thin slice) are required to start.
- #6 A4 for the events; #22 D2 for the image layout (check f); #24 D4 for CI wiring.
- Informs #13 B4 and #14 B5 (red-team) so they do not duplicate this coverage.
BODY
mk A8 env firewall p1 4 "Hidden-information firewall tests for every tool result" "$B"
read -r -d '' B <<'BODY' || true
> Realigned to docs/ED_Management_Simulator_RU.md by #41 / PR #43. Read docs/SPEC.md and docs/CONTRACTS.md on branch kostiantyn/docs-rules-realign until PR #43 merges.

## Objective

Make the ED-72 simulator's randomness action-independent (common random numbers), so that two different policies on the same seed face exactly the same luck. Deliver a small RNG module with named, independent substreams derived from `(seed, name)`, plus the rule that every per-patient random quantity is either drawn at world generation or drawn from that patient's own substream. Agent actions then change exposure, never the random numbers themselves.

## Context

Repo: xand1ex999/guinness (private), base branch `main`. Source of truth: the ED-72 spec merged on `main` in commit 24f6abf (PR #29): docs/SPEC.md, docs/CONTRACTS.md, docs/EVAL.md, docs/PLAN.md, AGENTS.md (esp. §7 and §10). Nothing under `ed72/` exists on main yet; it is created by #22 (D2).

ED-72 in brief (rulebook docs/ED_Management_Simulator_RU.md, SPEC §3–§6): an agent runs a synthetic emergency department for 144 ticks of 30 minutes (17 beds in three zones, 6 doctors and 9 nurses assigned to zones or rest, ESI 1–5 known on arrival, per-tick hazard rolls for each patient, four seeded events). Tools `rules`, `observe`, `step(actions)`; 500-call cap. Score = 60·O + 20·T + O·(10·W + 10·B), reward = score / 100. Rulebook §2 already proposes separate random streams for arrivals/events and for each patient's hazard rolls, and SPEC §12 adopts it. CI property: same seed + same actions = same score.

Why this matters:
- Models are compared on the same seed (EVAL §4: 3 seeds x 3 runs x up to 3 models), and the built-in baselines (reactive proxy, stop-early, do-nothing) are replayed on the same seed.
- AGENTS §7 says all randomness comes from one seeded `random.Random`. If the simulator draws random numbers during play from one shared stream (hazard rolls, the new CT roll after an upgrade), the sequence each patient gets depends on the order and number of agent actions. Two models, or the agent and the baseline replays, then face different luck after their first different action. That adds variance unrelated to skill and weakens "The gap" (30 points, reproducible across runs).
- Fix: per-entity substreams, so luck is a property of the seed, not of the policy.

Reference implementation of the same idea (a different world model; port the pattern, not the domain code): branch `kostiantyn/env-ed-sim`, `backend/app/edsim/rng.py` (named SHA-256 substreams, stdlib-only distributions) and the test `test_agent_actions_never_change_the_exogenous_scenario` in `backend/tests/test_edsim_simulation.py`.

## Relevant files

- New: `ed72/environment/hospital/ed72_sim/rng.py` and its tests `ed72/environment/hospital/tests/test_rng.py` (lane A, unowned so far; this issue owns both).
- Integration test: `ed72/environment/hospital/tests/test_common_random_numbers.py` (new, owned here).
- Consumers that must adopt the module: `ed72/environment/hospital/ed72_sim/world.py` (#3 A1) and the sim core (#4 A2). Do NOT edit those yourself unless the A1/A2 owners agree on their issue first.
- Lane ownership (CONTRACTS "Who owns which folder"): A env = `ed72/environment/hospital/`, `ed72/environment/workspace/HANDBOOK.md`, `ed72/instruction.md`; B reward = `ed72_sim/scoring/`, `ed72/tests/`, `collect.py`, `docs/REDTEAM.md`; C reference = `ed72/solution/`, `analysis/`, `docs/FINDINGS.md`, `eval/`; D harness = Dockerfiles, compose, `task.toml`, `eval/` runner, `.github/`.

## Branch and integration requirements

- Start from the latest `main` (`git fetch && git switch main && git pull`), then create the worktree with `scripts/wt.sh new <owner> <area> <task> -i <issue>`; branch name `<owner>/<area>-<task>`. Claim with the `claim-task` skill first.
- Re-check `main` and the status of #3 and #4 before you start and before you open the PR; they may already have hardened a shared-stream design.
- Mandatory coordination: before implementing, comment on #3 and #4 (start with your agent id) proposing the module and asking the owners to adopt it. Link their agreement in the PR. If the team agrees this changes the wording of AGENTS §7 ("one seeded `random.Random`"), propose that via the `contract-change` skill on #1 as a small separate PR.
- Stay inside the files listed as yours. Files owned by other lanes: comment on the owning issue first.
- Commit each working logical unit through `pre-commit-gate` and push; post progress comments on this issue; open a PR with `Closes #<n>` via `ship-pr` after `cross-review`. Never force-push or rewrite shared history. If blocked, label `blocked` and comment instead of changing the architecture.
- AGENTS §10 rules apply (nothing revealing the answer in the `main` image; reward only from the hospital event log; every sim rate in HANDBOOK.md; any PR touching scoring/patients/events/tools pastes the baseline table).
- Python 3.12, stdlib only, type hints, `uvx ruff format . && uvx ruff check --fix .`, pytest in the same PR.

## Implementation requirements

1. `ed72_sim/rng.py` exposes `stream(seed: int, name: str) -> random.Random` (or a thin wrapper). The substream seed is derived with `hashlib.sha256(f"{seed}:{name}".encode())`, never with Python's `hash()` (it is salted per process).
2. Build all distributions from `random.Random.random()` only (inverse CDF for exponential, Box-Muller for normal, etc.), so results do not depend on Python-version internals of `gauss`/`expovariate`. Document each helper in one line.
3. Naming scheme (document in the module docstring): `stream(seed, "arrivals")`, `stream(seed, "events")`, `stream(seed, f"patient:{pid}")` (hazard rolls and the upgrade CT roll come from the patient's own substream, consumed in a fixed order that does not depend on when or whether the agent acts), plus any others the A1/A2 owners need.
4. Rule, stated in the module docstring and in the PR: every per-patient random quantity is either drawn at world generation or drawn from that patient's own substream. No random draw during play may come from a stream shared across patients or from a stream whose position depends on agent actions.
5. Do not change tool shapes or the event-log format. If the log needs a new field, use `contract-change` on #1.
6. Provide a short migration note on #3/#4 listing each place in `world.py` / the sim core that currently draws from a shared `random.Random` (found by reading the code on `main` at the time) and the substream it should use.

## Acceptance criteria

- [ ] Module `ed72_sim/rng.py` with named substreams derived from `(seed, name)` via sha256, and distributions built from `.random()` only.
- [ ] Unit tests: same `(seed, name)` gives the same sequence; different names give independent sequences (no shared prefix, basic statistical sanity); different seeds differ; sequences are pinned to literal expected values so they are stable across Python 3.12 and 3.13 for a fixed seed.
- [ ] Integration test: two different action sequences (for example do-nothing vs a busy scripted policy) on one seed see identical arrivals, ESI values, CT needs, event schedule and per-patient random draws.
- [ ] Determinism test: same seed + same actions gives a byte-identical event log.
- [ ] Comments posted on #3 and #4 before implementation, and the A1/A2 owners' agreement linked in the PR (or a documented decision if they decline).
- [ ] If AGENTS §7 wording needs to change, a contract-change proposal is posted on #1 and linked.
- [ ] Baseline replays (B3 #12) can obtain the same per-patient luck as the agent run; note how in the PR description.
- [ ] No edits to `world.py` or the sim core without the owners' agreement on their issue.

## Testing requirements

- `cd ed72/environment/hospital && uv run pytest tests/test_rng.py tests/test_common_random_numbers.py -q` passes.
- Run the unit tests under both Python 3.12 and 3.13 (for example `uv run --python 3.13 pytest ...`) and confirm identical pinned values.
- Lint: `uvx ruff format . && uvx ruff check --fix .`.

## Deliverables

- `ed72/environment/hospital/ed72_sim/rng.py`, `tests/test_rng.py`, `tests/test_common_random_numbers.py`.
- Comments on #3 and #4 (proposal, then migration note), and on #1 only if AGENTS §7 wording changes.
- PR description with the naming scheme, the rule, and links to the owners' agreement.

## Dependencies

- Coordinate with #3 A1 (`world.py`) and #4 A2 (sim core); ideally land this before they harden their RNG use.
- Consumed by #10 B1 and #12 B3 (same luck for baselines and the agent), and relevant to #20 C5 fairness audit and #18 C3 run matrix.
BODY
mk A9 env crn p0 1 "Action-independent randomness (common random numbers) for fair model comparison" "$B"

# ---------- Lane B: reward and integrity ----------
read -r -d '' B <<'BODY' || true
> Realigned to docs/ED_Management_Simulator_RU.md by #41 / PR #43. Read docs/SPEC.md and docs/CONTRACTS.md on branch kostiantyn/docs-rules-realign until PR #43 merges.

Read first: docs/ED_Management_Simulator_RU.md (rules), AGENTS.md (section 10), docs/CHALLENGE.md, docs/SPEC.md, docs/CONTRACTS.md.

**Goal:** pure function `score(events)` (CONTRACTS "Event log" and "Score object", SPEC §6): Score = 60·O + 20·T + O·(10·W + 10·B), reward = score / 100. O uses the loss table (discharged 0; in a bed at the end 0.3 only with at least one covered tick, otherwise 1; diverted 0.7; died, left or never admitted 1) with weights 10/5/2/1/0.5 by the highest ESI reached. T is the weighted share whose first covered tick is within 0/1/4/8/12 ticks. W = max(0, 1 − 1.0·share of on-shift staff-ticks above fatigue 60 − 0.05·faints). B = 1 up to €12 000, linear to 0 at €24 000. No anchors, no planner. Use test-driven development.

**Files you own:** `ed72/environment/hospital/ed72_sim/scoring/`, its tests.
**Depends on:** #41 (rules), #4 for the log shape (agree it early, then work on fixtures).
**Rules:** reads only the event log (budget from `episode_start`, rule numbers from `ed72_sim/constants.py`). No LLM. Deterministic.
**Done when:** tests show do-nothing = 0; a hand-built perfect log = 100; the rulebook §11 row "everyone treated on time, no rest, €24 000" = 80; an unstaffed admission does not count as on time; a last-tick admission of the queue gives loss 1; same events give the same score.

Claimed by kostiantyn-claude-2.
BODY
mk B1 reward scorer p0 2 "Scorer: O, T, W, B and reward = score / 100" "$B"
read -r -d '' B <<'BODY' || true
> Realigned to docs/ED_Management_Simulator_RU.md by #41 / PR #43. Read docs/SPEC.md and docs/CONTRACTS.md on branch kostiantyn/docs-rules-realign until PR #43 merges.

Read first: docs/ED_Management_Simulator_RU.md (rules), AGENTS.md (section 10), docs/CHALLENGE.md, docs/SPEC.md, docs/CONTRACTS.md.

**Goal:** `collect.py` runs inside the hospital container as the `[[verifier.collect]]` hook after the agent stops: it rebuilds the world from `ED72_SEED`, replays the agent `step` lines from `/var/lib/ed72/events.jsonl`, runs any remaining ticks with no actions, scores with `score(events)` (#10) and writes `/evidence/report.json` in the CONTRACTS v1 score-object shape (declared as a sidecar artifact). `ed72/tests/test.sh` reads only that file and writes the reward to `/logs/verifier/reward.txt` and the full object to `/logs/verifier/score_full.json`. Harbor runs with `environment_mode = "separate"`. No 12-hour tail and no anchor or planner replays. `ended` is one of `tick_143`, `agent_stopped`, `call_cap`, `timeout`.

**Files you own:** `ed72/tests/`, `ed72/environment/hospital/collect.py`.
**Depends on:** #22 (task skeleton), #4 and #10 (use stubs until they land).
**Rules:** always writes a number in [0,1]; on any error write 0. Use absolute paths and `set -u`. Trust nothing in the agent's container.
**Done when:** `harbor run -p ed72 -a oracle` shows a reward, and a root agent writing reward.txt itself does not change it.

Claimed by kostiantyn-claude-2.
BODY
mk B2 reward verifier p0 3 "Verifier: collect.py writes report.json, test.sh always writes a number" "$B"
read -r -d '' B <<'BODY' || true
> Realigned to docs/ED_Management_Simulator_RU.md by #41 / PR #43. Read docs/SPEC.md and docs/CONTRACTS.md on branch kostiantyn/docs-rules-realign until PR #43 merges.

Read first: docs/ED_Management_Simulator_RU.md (rulebook), docs/SPEC.md, docs/CONTRACTS.md, docs/CHALLENGE.md, AGENTS.md (section 10).

**Goal:** scripted policies over the public tools. Built-in baselines (rulebook §12): reactive proxy (FIFO first-free-bed so light cases fill resus, fixed posts until fatigue 85, agency only when the queue reaches 10, ignores warnings), stop-early (reactive proxy for 12 ticks, then stops), do-nothing. Exploit baselines (rulebook §13): divert-all, rest-everyone-in-quiet-periods, admit-light-only, admit-without-coverage, fill-beds-at-the-last-tick, spend-to-the-limit. CI test on every shipped seed: do-nothing = 0; stop-early < reactive proxy < reference; divert-all < reference and about <= 47 points; every exploit baseline < reference.

**Files you own:** `eval/baselines/`, `ed72/environment/hospital/ed72_sim/scoring/tests/test_baselines.py`.
**Depends on:** B1, A2.
**Done when:** the baseline score table is in the PR and the test runs in CI.
BODY
mk B3 reward baselines p1 4 "Built-in baselines + exploit baselines + CI ordering test" "$B"
read -r -d '' B <<'BODY' || true
> Realigned to docs/ED_Management_Simulator_RU.md by #41 / PR #43. Read docs/SPEC.md and docs/CONTRACTS.md on branch kostiantyn/docs-rules-realign until PR #43 merges.

Read first: docs/ED_Management_Simulator_RU.md (rules), AGENTS.md (section 10), docs/CHALLENGE.md, docs/SPEC.md, docs/CONTRACTS.md.

**Goal:** 15 minutes attacking the reward the way judges will, done by someone who did NOT write the scorer. Start from the shortcut list in SPEC §11 (rulebook §13) and try: write reward.txt yourself; read the sim source or seed from the agent container; admit patients to beds with no staff (timeliness must count only from the first covered tick); fill every bed at tick 143 (end loss must be 1 without a covered tick); divert all the time (must stay around 47 points or less); spend up to €24 000; send everyone to rest in quiet periods; admit only light patients; stop calling `step` early; `step` with malformed actions, unknown ids or a 1000-action list; calls after tick 143; reaching the 500-call cap; assigning the same person to two zones in one list; hitting the hospital on other ports or paths.

**Files you own:** `docs/REDTEAM.md`.
**Depends on:** #11 B2, #5 A3.
**Done when:** every attempt is logged with its result, and each working exploit has its own issue labelled p0.
BODY
mk B4 reward redteam1 p1 5 "Red-team round 1 (Sat 19:00)" "$B"
read -r -d '' B <<'BODY' || true
Read first: AGENTS.md (section 10), docs/CHALLENGE.md, docs/SPEC.md, docs/CONTRACTS.md.

**Goal:** repeat B4 on the frozen rules with a different person, and add one regression test per exploit found in either round.

**Files you own:** `docs/REDTEAM.md`, regression tests under `ed72/environment/hospital/ed72_sim/scoring/tests/`.
**Depends on:** B4, A4.
**Done when:** REDTEAM.md lists what was tried and why each attempt fails. We show this page in the demo.
BODY
mk B5 reward redteam2 p1 6 "Red-team round 2 after rules freeze (Sat 23:30) + regression tests" "$B"
read -r -d '' B <<'BODY' || true
> Realigned to docs/ED_Management_Simulator_RU.md by #41 / PR #43. Read docs/SPEC.md and docs/CONTRACTS.md on branch kostiantyn/docs-rules-realign until PR #43 merges.

Read first: docs/ED_Management_Simulator_RU.md (rulebook), docs/SPEC.md, docs/CONTRACTS.md, docs/CHALLENGE.md, AGENTS.md (section 10).

**Goal:** end of episode. When the agent stops (no more `step` calls, call cap, timeout), `collect.py` runs the remaining ticks with no actions (staff stay where last assigned). Classify every arrived patient into the outcome enum (discharged, in_bed_end, diverted, died, left, never_admitted), apply the two §13 fixes (T from the first covered tick; in-bed-at-end loss 0.3 only with at least one covered tick, otherwise 1), and set `ended` (`tick_143|agent_stopped|call_cap|timeout`).

**Files you own:** `ed72/environment/hospital/ed72_sim/scoring/` end-of-episode module (e.g. `outcomes.py`) and its tests, plus the matching part of `ed72/environment/hospital/collect.py` (coordinate with B2).
**Depends on:** B1, A4.
**Done when:** tests cover stop at tick 12, call cap reached, a patient in bed never covered at the end (loss 1), a covered one (0.3), a diverted one (0.7 and late).
BODY
mk B6 reward episode-end p1 5 "End of episode: remaining ticks, outcome classes and the ended field" "$B"
read -r -d '' B <<'BODY' || true
> Realigned to docs/ED_Management_Simulator_RU.md by #41 / PR #43. Read docs/SPEC.md and docs/CONTRACTS.md on branch kostiantyn/docs-rules-realign until PR #43 merges.

## Objective
Build scripted probe policies for the rulebook §13 shortcuts that #12 (B3) does not already implement, run each on every shipped seed, and assert each scores well below the reference. Also add a scoring performance budget test. Judges spend 15 minutes hunting exploits (CHALLENGE "How judges run it"; rubric "Reward integrity", 25 points), so the exploit hunt must happen in CI before they do it.

## Context
Read first: docs/ED_Management_Simulator_RU.md §11-§13, docs/SPEC.md (§6, §11), docs/CONTRACTS.md, docs/CHALLENGE.md, AGENTS.md (section 10). The game: 144 ticks of 30 minutes, 17 beds, 6 doctors and 9 nurses, three tools `rules`/`observe`/`step(actions)`, tool-call cap 500, score = 60·O + 20·T + O·(10·W + 10·B), reward = score / 100. No anchors, no floor planner, no normalisation.

**Overlap with #12 (B3):** #12 owns the baseline implementations (reactive proxy, stop-early, do-nothing, divert-all, rest-everyone, admit-light-only, admit-without-coverage, fill-at-last-tick, spend-to-the-limit) and their CI ordering test. #34 owns probes not covered there and the scoring performance test. Do not duplicate or edit `eval/baselines/`; comment on #12 instead.

## Relevant files
- `eval/probes/` (new): one module per probe agent, public tools only.
- `ed72/environment/hospital/ed72_sim/scoring/tests/test_probes.py` (new) and a timing test (e.g. `test_scoring_budget.py`).
- **Do not edit** `eval/baselines/` (#12) or the scorer modules (#10, #15).

## Implementation requirements
1. **Probes** (rulebook §13; skip any already implemented as a #12 baseline):
   1. unstaffed-bed admission: admit patients to beds that are never covered (T and the in-bed-at-end rule must not reward it)
   2. last-tick fill: leave the queue and admit everyone in tick 143
   3. divert-all (about 47 points): permanent diversion; assert the reference clearly beats it
   4. spend-to-limit: spend up to the €24 000 hard limit without saving patients
   5. rest-everyone: send all staff to rest in quiet periods
   6. admit-light-only: ESI 3-5 only
   7. stop-early at several ticks (not just 12)
   8. invalid-action spam: malformed actions, unknown ids, 50-action lists; must have no effect
   9. seed memorisation: replay an action script recorded on one seed against other seeds; report scores on held-out seeds
2. **Thresholds** as named constants with a comment: each probe must score clearly below the reference on every shipped seed (state the margin in the PR); divert-all about <= 47 points.
3. **Performance budget.** One end-to-end test timing the `collect.py` work on a full 144-tick episode (remaining ticks, scoring). It must run well under the collect timeout in `[[verifier.collect]]`. Report the numbers in the PR and comment on #11 and #22 with the timeout to configure.
4. **Findings.** Any probe that beats its threshold is a finding: the assignee opens a new `p0` issue and records it in `docs/REDTEAM.md` (coordinate with the #13/#14 owners). Do not weaken a threshold to make a probe pass.

## Acceptance criteria
- [ ] Probes implemented in `eval/probes/`, public tools only
- [ ] Table in the PR listing every probe's score per shipped seed (plus held-out seeds)
- [ ] Each probe clearly below the reference on every seed, or a p0 finding issue is filed and linked
- [ ] `test_probes.py` runs in CI (#24 D4)
- [ ] Timing test in place; numbers reported; timeout recommendation commented on #11 and #22
- [ ] Findings recorded in `docs/REDTEAM.md`

## Testing requirements
pytest; probes run through the real sim API (no scorer shortcuts). Share per-seed results across assertions to keep CI time down. Paste the baseline table per AGENTS section 10.

## Branch and integration requirements
Claim with `claim-task`, worktree via `scripts/wt.sh new <owner> <area> <task> -i 34`, stay inside the files above, `contract-change` for anything in docs/CONTRACTS.md, `pre-commit-gate` before every commit, PR with `Closes #34` via `ship-pr` after `cross-review`. Python 3.12, type hints, ruff, pytest in the same PR.

## Dependencies
- #10 B1 (scorer), #12 B3 (baselines), #15 B6 (end of episode), #6 A4 (events, agency, repair, diversion).
- Related: #11 B2, #22 D2, #24 D4, #13/#14 red-team.
BODY
mk B8 reward probes p1 6 "Exploit probes (rulebook §13) + scoring performance budget" "$B"
read -r -d '' B <<'BODY' || true
> Realigned to docs/ED_Management_Simulator_RU.md by #41 / PR #43. Read docs/SPEC.md and docs/CONTRACTS.md on branch kostiantyn/docs-rules-realign until PR #43 merges.

## Objective
Confirm with Denys the decisions that issue #41 recorded in `docs/SPEC.md` §12 (answers to rulebook §14), and check them against his JavaScript prototype. The rulebook says every [Proposed] rule must be checked against his JavaScript engine. Record any difference and update SPEC §12 (and the CONTRACTS score object if a field changes) through the `contract-change` skill: propose on #1, then a small separate PR, with the matching HANDBOOK text requested from lane A (#7). This is a decision/doc task, not code.

## Context
Read first: docs/ED_Management_Simulator_RU.md (§11-§14), docs/SPEC.md (§6, §12), docs/CONTRACTS.md, docs/CHALLENGE.md, AGENTS.md (section 10). The earlier edge-case questions Q1-Q10 about harm modules, tails, returns and transfers no longer apply: the rulebook has no such mechanics. The §13 fixes (T from the first covered tick; in-bed-at-end loss 0.3 only with a covered tick) are adopted in SPEC §12.

## What to confirm (SPEC §12 table)
- [ ] TUNE values: arrival rate and daily cycle, flu-wave mix, W weights (a = 1.0, b = 0.05)
- [ ] Budget curve above €12 000 (linear to 0 at €24 000)
- [ ] Eight-step tick order, coverage priority and rounding, CT stop point, upgraded ESI 3 rules
- [ ] Faint recovery (about 65), agency arrival fatigue, diversion and repair rules
- [ ] Warnings show the exact start tick
- [ ] Diverted and never-admitted patients count as late in T
- [ ] Run Denys's JavaScript engine on the same decisions and list every behavioural difference

## Relevant files
- `docs/SPEC.md` §12 and §6 (edit via PR); `docs/CONTRACTS.md` score object (only if fields change).
- `ed72/environment/workspace/HANDBOOK.md`: owned by lane A (#7); request text there, do not edit it.
- Issue #1 (contract proposals go there).

## Branch and integration requirements
Claim with `claim-task`, worktree via `scripts/wt.sh new <owner> <area> <task> -i 35`, `contract-change` skill for any change to SPEC §12 or CONTRACTS, small separate PR, `pre-commit-gate` before every commit, PR with `Closes #35` via `ship-pr`. Humans merge.

## Acceptance criteria
- [ ] Every SPEC §12 row confirmed with Denys or changed through `contract-change`
- [ ] Differences from the JavaScript prototype listed (or "none found") in the PR
- [ ] Change announced on #1; HANDBOOK text requested on #7 if anything changed
- [ ] Summary comments on #10, #15, #6, #7 if their scope changed
- [ ] Merged PR (human integrator merges)

## Dependencies
- None; start immediately. Blocks the final behaviour of #10 B1, #15 B6, #6 A4 and #7 A5.
BODY
mk B9 reward decisions p0 1 "Confirm SPEC §12 decisions with Denys and against the JavaScript prototype" "$B"

# ---------- Lane C: reference and experiments ----------
read -r -d '' B <<'BODY' || true
> Realigned to docs/ED_Management_Simulator_RU.md by #41 / PR #43. Read docs/SPEC.md and docs/CONTRACTS.md on branch kostiantyn/docs-rules-realign until PR #43 merges.

Read first: docs/ED_Management_Simulator_RU.md (rulebook), docs/SPEC.md, docs/CONTRACTS.md, docs/CHALLENGE.md, AGENTS.md (section 10).

**Goal:** a scripted policy that plays the 144 ticks through the same tools the agent has (rulebook §12 / SPEC §8): admit by severity, keep resus beds free for critical patients, send light cases to Fast-track, staff each zone from the least tired people (this rotates rest), order agency staff when a warning is about 9 ticks away, repair the CT at once, keep staff on shift when a surge is near. This is our stronger reference run.

**Files you own:** `ed72/solution/`.
**Depends on:** A2, A3, B1.
**Rules:** public tools only; never reads the seed, ground truth, event log or sim source. If it cannot decide from the observation and the handbook, that is a bug in the environment: open an issue for lane A.
**Done when:** `harbor run -p ed72 -a oracle` gives the identical score three times in a row, and the baseline table shows the reference clearly above the reactive proxy, stop-early and divert-all (about 47 points) on every shipped seed. Reward is absolute (score / 100), so there is no fixed target such as 0.9.
BODY
mk C1 ref policy p0 4 "Reference policy (solution/solve.sh), public tools only" "$B"
read -r -d '' B <<'BODY' || true
Read first: AGENTS.md (section 10), docs/CHALLENGE.md, docs/SPEC.md, docs/CONTRACTS.md.

**Goal:** run OpenCode with our strongest model on the thin slice and tell the team if there is a gap.

**Files you own:** `eval/results/`.
**Depends on:** D2, A3, B2, C1.
**Done when:** the Harbor run log is committed under eval/results/, and a comment on this issue gives: the score, the reference score, the 3 biggest mistakes with patient ids and F codes, and a recommendation (keep / harder / fairer).
BODY
mk C2 ref firstrun p0 5 "First OpenCode run at 18:00 (calibration)" "$B"
read -r -d '' B <<'BODY' || true
Read first: AGENTS.md (section 10), docs/CHALLENGE.md, docs/SPEC.md, docs/CONTRACTS.md.

**Goal:** the numbers for the 30-point gap. 3 seeds x 3 runs for up to 3 models (one each from Anthropic, OpenAI, Google), plus reference, nop and stop-early.

**Files you own:** `eval/results/`, `eval/matrix.yaml`.
**Depends on:** D3, A4 merged, rules frozen (22:00).
**Done when:** eval/results/summary.md has a table with mean and min/max per model and seed, every agent run is below the reference, and all logs are committed.
BODY
mk C3 ref matrix p1 6 "Run matrix: 3 seeds x 3 runs x up to 3 models" "$B"
read -r -d '' B <<'BODY' || true
Read first: AGENTS.md (section 10), docs/CHALLENGE.md, docs/SPEC.md, docs/CONTRACTS.md.

**Goal:** explain where the agent falls short and why, tied to decisions. Use the counts per failure code F1 to F10 and the harm per module from score_full.json, and the trajectories.

**Files you own:** `analysis/`, `docs/FINDINGS.md`.
**Depends on:** C3 (start on C2's run).
**Done when:** FINDINGS.md has a failures-by-code chart, harm by module, 3 trajectory excerpts, and one honest paragraph on what the agent did well.
BODY
mk C4 ref findings p1 7 "Failure analysis: docs/FINDINGS.md" "$B"
read -r -d '' B <<'BODY' || true
> Realigned to docs/ED_Management_Simulator_RU.md by #41 / PR #43. Read docs/SPEC.md and docs/CONTRACTS.md on branch kostiantyn/docs-rules-realign until PR #43 merges.

Read first: docs/ED_Management_Simulator_RU.md (rules), AGENTS.md (section 10), docs/CHALLENGE.md, docs/SPEC.md, docs/CONTRACTS.md.

**Goal:** for each mistake in C4 (#19), check the agent could have known better: the rule is in `HANDBOOK.md` (served by the `rules` tool) and the fact was in the observation in time (for example a free resus bed and an ESI 1 arrival in `waiting`, fatigue and `counts_as` in `staff`, a warning with its exact start tick in `warnings`, the CT's `down_ticks_left`). Only the future (arrivals, unannounced events, dice rolls) may be hidden (SPEC §8). Where something needed was missing, fix the environment, not the write-up.

**Files you own:** a section in `docs/FINDINGS.md`.
**Depends on:** #19 C4, #7 A5.
**Done when:** each failure code F1–F10 (SPEC §2) has a line 'rule: handbook section X, fact: observation field Y', and any unfair case has an issue for lane A.
BODY
mk C5 ref fairness p1 8 "Fairness audit of every agent mistake" "$B"
read -r -d '' B <<'BODY' || true
> Realigned to docs/ED_Management_Simulator_RU.md by #41 / PR #43. Read docs/SPEC.md and docs/CONTRACTS.md on branch kostiantyn/docs-rules-realign until PR #43 merges.

## Objective

Build six ablation variants of the C1 reference policy, each removing exactly one rulebook lever, run them on every shipped seed, and report score (and O, T, W, B) versus the full reference. The result shows causally which skills the agent-vs-reference gap comes from, and checks that every mechanic matters.

Variants (SPEC §2 failure codes):
1. No resus reservation: fills resus beds with whoever is next (F1).
2. No rest rotation: staff stay on shift until fatigue 90 (F2).
3. Ignore warnings: no preparation for the flu wave or bus crash (F3).
4. Never repair the CT (F4).
5. Never order agency staff (F5).
6. Divert whenever the queue grows (F6).

## Context

- Read first: docs/ED_Management_Simulator_RU.md, docs/SPEC.md (§2, §6, §8), docs/CONTRACTS.md, docs/EVAL.md, docs/CHALLENGE.md, AGENTS.md (section 10). Nothing under `ed72/` exists on `main` until #22 (D2) lands.
- Game: 144 ticks of 30 minutes, 17 beds in Resus/Acute/Fast-track, 6 doctors and 9 nurses, tools `rules`/`observe`/`step(actions)`, cap 500 calls. Score = 60·O + 20·T + O·(10·W + 10·B), reward = score / 100. Same seed and same actions give the same score.
- Why (rubric): CHALLENGE gives 30 points to "Meaningful difficulty": explain the agent's main mistakes, tie them to decisions, show the information to do better was available. The reference does all of these right. Ablating one lever at a time measures the score lost per skill.
- Expected outcome: each ablation loses meaningful score. If one loses nothing, the mechanic is not doing its job: file an issue for lane A (#6 A4 / #8 A6 knobs) with the numbers.

## Relevant files

- New (lane C): `eval/ablations/` (runner plus one small module per variant, e.g. `eval/ablations/run.py`, `eval/ablations/variants.py`) and `eval/ablations/README.md`.
- Import the reference from `ed72/solution/` WITHOUT modifying it. If it needs a switch, agree a small backward-compatible flag with the #16 owner first (comment on #16).
- Results table: a section in `docs/FINDINGS.md`. Coordinate with the #19 C4 owner so you add a section rather than rewrite the file.
- Do NOT edit scorer or sim files (lanes A and B).

## Implementation requirements

- Each ablation is the reference with exactly one behaviour removed. Document in code (why-comments) what each variant disables and which failure code it maps to.
- Public tools only. Never read the seed, config, event log or ground truth.
- Run through the same path the reference uses and score with the normal scorer path (`/evidence/report.json`, `score_full.json`).
- Report per variant per seed: score, O, T, W, B, deaths, faints, spend, and the delta versus the reference.
- Output `eval/ablations/results.json` and a Markdown table in `docs/FINDINGS.md`.
- Mock data, if any, is labelled `MOCK:` and sits behind `USE_MOCKS=1`.

## Acceptance criteria

- [ ] Six ablations implemented, each removing exactly one behaviour (F1, F2, F3, F4, F5, F6).
- [ ] Reference not modified, or a backward-compatible flag agreed on #16 and the reference score unchanged.
- [ ] Table of score and O, T, W, B per ablation x seed with deltas versus the reference, in `docs/FINDINGS.md`.
- [ ] Each ablation scores lower than the reference on every shipped seed, OR an issue is filed for lane A (#6 / #8) with the numbers.
- [ ] Reproducible: same seed gives the same numbers when run twice.
- [ ] Public tools only; no scorer or sim files edited.

## Testing requirements

- pytest checking that each variant differs from the reference only in its intended behaviour (e.g. variant 4 never sends a `repair` action, variant 5 never sends `agency`), using a recorded action trace or a stub client.
- Determinism test: run one variant twice on one seed and compare scores.
- Manual: run all six on the thin-slice seed, then on every shipped seed, and paste the table.
- `uvx ruff format . && uvx ruff check --fix .` clean; `pre-commit-gate` passes.

## Branch and integration requirements

Claim with `claim-task`, worktree via `scripts/wt.sh new <owner> ref ablations -i 36`, stay inside the files above, `contract-change` for anything in docs/CONTRACTS.md (should not be needed), `pre-commit-gate` before every commit, PR with `Closes #36` via `ship-pr` after `cross-review`; label the issue `review`.

## Dependencies

- Needs #16 C1 (reference), #10 B1 (scorer), #6 A4 (events, agency, repair, diversion), #8 A6 (difficulty knobs).
- Feeds #19 C4 (failure analysis) and #20 C5 (fairness audit).
BODY
mk C6 ref ablations p1 7 "Reference-policy ablations of the rulebook levers (F1–F6)" "$B"

# ---------- Lane D: harness, repro and story ----------
read -r -d '' B <<'BODY' || true
Read first: AGENTS.md (section 10), docs/CHALLENGE.md, docs/SPEC.md, docs/CONTRACTS.md.

**Goal:** most of the spike is done on Kostiantyn's branch (`origin/kostiantyn/env-unfindable-slice`, see `docs/unfindable/SPIKE_S0_RESULTS.md`): sidecar, separate mode and the collect hook. What remains: one real `-a opencode -m <model>` run against a stub hospital sidecar. Confirm OpenCode sees the MCP tools from `[[environment.mcp_servers]]`. OpenCode installs over npm, so main needs internet or a preinstall.

**Files you own:** `docs/HARBOR-NOTES.md`.
**Depends on:** nothing. Do this first, it unblocks A3 and B2.
**Done when:** HARBOR-NOTES.md has the exact working commands, the MCP-or-CLI decision, and where run logs land. Post the decision on the Contracts issue.
BODY
mk D1 harness harbor-spike p0 1 "Harbor spike: one real OpenCode run against a stub hospital sidecar" "$B"
read -r -d '' B <<'BODY' || true
Read first: AGENTS.md (section 10), docs/CHALLENGE.md, docs/SPEC.md, docs/CONTRACTS.md.

**Goal:** the Harbor task folder from docs/SPEC.md section 9. Copy the packaging from `origin/kostiantyn/env-unfindable-slice:harbor/unfindable/` (task.toml with separate mode and the collect hook, compose with the hospital sidecar and a healthcheck, start.sh, Dockerfiles) and rename it to ed72 and hospital, so the other lanes drop their code in.

**Files you own:** `ed72/task.toml`, `ed72/environment/Dockerfile`, `ed72/environment/docker-compose.yaml`, `ed72/environment/hospital/Dockerfile`, `ed72/environment/hospital/start.sh`.
**Depends on:** D1.
**Rules:** the `main` image holds HANDBOOK.md and the ward CLI only. No sim code, no seed, no scorer.
**Done when:** with stub code, `harbor run -p ed72 -a oracle` and `-a nop` both finish and write a reward.
BODY
mk D2 harness task-skeleton p0 2 "Task skeleton: ed72/ tree, copy the Unfindable packaging" "$B"
read -r -d '' B <<'BODY' || true
> Realigned to docs/ED_Management_Simulator_RU.md by #41 / PR #43. Read docs/SPEC.md and docs/CONTRACTS.md on branch kostiantyn/docs-rules-realign until PR #43 merges.

Read first: docs/ED_Management_Simulator_RU.md (rulebook), docs/SPEC.md, docs/CONTRACTS.md, docs/CHALLENGE.md, AGENTS.md (section 10).

**Goal:** one command that reproduces our reported results: reference, nop, stop-early and 3 agent runs (`-k 3`). Writes eval/results/summary.md. Stop-early is a small scripted agent that plays the reactive proxy for 12 ticks (rulebook §12) and then stops calling `step`.

**Files you own:** `Makefile`, `eval/run_all.sh`, `eval/summarise.py`.
**Depends on:** D2, B2, C1.
**Done when:** on a fresh clone on another laptop, `make eval` runs to the end with only Docker, Harbor and one API key set.
BODY
mk D3 harness eval p1 5 "One-command eval: make eval" "$B"
read -r -d '' B <<'BODY' || true
Read first: AGENTS.md (section 10), docs/CHALLENGE.md, docs/SPEC.md, docs/CONTRACTS.md.

**Goal:** replace the old CI steps with ruff and pytest for ed72_sim and the scorer, plus the anchors test.

**Files you own:** `.github/workflows/ci.yml`.
**Depends on:** A2, B1.
**Done when:** CI runs on a PR in under 3 minutes and fails when a scorer test fails.
BODY
mk D4 harness ci p1 3 "CI for the new layout" "$B"
read -r -d '' B <<'BODY' || true
Read first: AGENTS.md (section 10), docs/CHALLENGE.md, docs/SPEC.md, docs/CONTRACTS.md.

**Goal:** the README (what the agent has to do, why it is hard, how we score it, the one command, the results table, a link to a Harbor run log), a 10-minute demo script, the demo video with a playthrough, and the Junction submission form.

**Files you own:** `README.md`, `docs/DEMO.md`.
**Depends on:** C3, C4, B5.
**Rules:** a human writes the core paragraphs. AfterQuery said AI-written READMEs tend to sell the environment badly.
**Done when:** submitted before Sun 10:00, and a teammate has timed the demo under 10 minutes.
BODY
mk D5 harness story p1 8 "README, demo script, demo video, submission" "$B"
read -r -d '' B <<'BODY' || true
Read first: AGENTS.md (section 10), docs/CHALLENGE.md, docs/SPEC.md, docs/CONTRACTS.md.

**Goal:** stamp out ed72-s1 to ed72-s3 from one template so judges can rerun on more than one seed, and confirm the images build on both x86 and Apple Silicon.

**Files you own:** `scripts/make_seeds.sh`.
**Depends on:** D2, rules freeze.
**Done when:** all three run with oracle >= 0.9 and nop = 0.
BODY
mk D6 harness seeds p2 7 "Three seeds as task folders + x86/ARM build check" "$B"
read -r -d '' B <<'BODY' || true
Read first: AGENTS.md (section 10), docs/CHALLENGE.md, docs/SPEC.md, docs/CONTRACTS.md.

**Goal:** the tiebreaker. Collect reference-policy trajectories, fine-tune a small open model (about 4B parameters) on Modal, and run it in the environment before and after on one held-out seed.

**Files you own:** `training/`.
**Depends on:** rules freeze at 22:00 and everything P1 green. Do not start before that.
**Done when:** a two-row table (base vs tuned, same seed) is in the README, or the task is dropped by 01:00.
BODY
mk D7 train stretch p2 7 "Stretch: small model before and after training" "$B"
read -r -d '' B <<'BODY' || true
## Objective

1. Document provider configuration for OpenAI, Anthropic, Google and any OpenAI-compatible endpoint (Verda, Workshop) as Harbor command-line flags and `.env` variable names, without committing keys.
2. Measure, on the thin slice (24 h) and then a full 72 h run, per model: model turns, tool calls, prompt and completion tokens, agent wall time, setup time, and cost. Extrapolate cost and time for the #18 run matrix.
3. Recommend values for the agent timeout and the tool-call cap.
4. Evaluate pre-installing OpenCode in the `main` image to remove the ~8-minute npm setup and its internet dependency.

## Context

- Repo: xand1ex999/guinness (private), base `main`. Source of truth: ED-72 spec on `main` (commit 24f6abf, PR #29): docs/SPEC.md, docs/CONTRACTS.md, docs/EVAL.md, docs/PLAN.md, docs/CHALLENGE.md, AGENTS.md. Nothing under `ed72/` exists on `main` until #22 (D2).
- ED-72 in brief: an agent runs a synthetic emergency department for 72 simulated hours through 8 read tools and 13 act tools (CONTRACTS "Tools (v0)"); the clock moves only on `advance(minutes)` 15-120; tool-call cap 600 counted by the hospital (SPEC §4). Harbor layout (SPEC §9): task folder `ed72/`, `main` agent container (HANDBOOK.md + `ward` CLI) and `hospital` sidecar (sim, scorer, MCP at http://hospital:8000/mcp). The verifier runs `collect.py` inside hospital; `ed72/tests/test.sh` writes `/logs/verifier/reward.txt`.
- EVAL §2 sets agent timeout 1800 s, tool-call cap 600, target 250-450 tool calls per run. EVAL §4 lists only OPENAI_API_KEY, ANTHROPIC_API_KEY, GEMINI_API_KEY. The team also has an OpenAI-compatible Verda inference account (about 200 EUR credit) and a Workshop API key.
- Problem: nobody has measured how many model requests, tokens, minutes and euros a full 72-hour ED-72 run costs, so the run matrix (#18 C3: 3 seeds x 3 runs x up to 3 models) may not fit time or budget.
- Evidence from an earlier real Harbor 0.26.0 run of a different task (Unfindable, 11 requests) with OpenCode 1.19.5 and Verda Kimi K3.1 Pro: 45 model turns and 77 tool calls in 93 s of agent time, 609k prompt tokens (about 13.5k prompt tokens per turn on average, growing with context). OpenCode's npm install during agent setup took about 8 minutes and needed `--agent-setup-timeout-multiplier 3`.
- Working command shape from that run:
  `harbor run -p <task> -a opencode -m verda/kimi-k3-1-pro --base-url https://inference.verda.com/v1 --api-format openai_chat_completions --api-key-name VERDA_INFERENCE_API_KEY --env-file .env --agent-setup-timeout-multiplier 3`
- Hypothesis to verify: ED-72 needs ~300-400 turns, so prompt tokens could reach several million per run unless OpenCode compacts context. This is an estimate, not a measurement.
- Risk reference: EVAL §1 (internet needed at agent setup) and CHALLENGE Q7.

## Relevant files

- `docs/HARBOR-NOTES.md` (created by #21 D1): coordinate with its owner and add a section; do not rewrite it.
- `eval/` runner config (lane D, #23 D3 owner), `.env.example` (variable names only).
- `ed72/task.toml` and `ed72/environment/Dockerfile` (lane D, #22 D2 owner): propose changes by commenting on #22; do not edit without agreement.
- Measurement results: `eval/` (e.g. `eval/budget/measurements.md` and raw numbers in `eval/budget/*.json`).
- Never commit `.env`; only variable names go into `.env.example`. Never print key values in logs, comments or docs.

Folder ownership (CONTRACTS "Who owns which folder"): Lane A env (`ed72/environment/hospital/`, HANDBOOK.md, `ed72/instruction.md`); Lane B reward (scoring/, `ed72/tests/`, `collect.py`, `docs/REDTEAM.md`); Lane C reference (`ed72/solution/`, `analysis/`, `docs/FINDINGS.md`, results in `eval/`); Lane D harness (Dockerfiles, docker-compose.yaml, `ed72/task.toml`, `eval/` runner, `training/`, README, Makefile, `.github/`). Comment on another lane's issue before touching its files.

## Branch and integration requirements

- Start from the latest `main` (`git fetch && git switch main && git pull`), then `scripts/wt.sh new <owner> harness model-budget -i <issue>`; branch `<owner>/harness-model-budget`. Claim with the `claim-task` skill first.
- Re-check `main` and the status of every dependency before you start and before you open the PR.
- Stay inside your files. Other lanes' files: comment on the owning issue first (#21, #22, #23).
- Adding a new variable to the CONTRACTS env table is a contract change: use the `contract-change` skill, propose on issue #1, small separate PR.
- Commit each working unit through `pre-commit-gate`, push, comment progress on the issue starting with your agent id (e.g. `[name-claude-1]`), open a PR with `Closes #<n>` via `ship-pr` after `cross-review`. Never force-push. If blocked, label `blocked` and comment.
- AGENTS.md §10 applies (nothing revealing answers in the `main` image, reward only from the hospital event log, etc.). AGENTS.md rule: no secrets in git.

## Implementation requirements

- Provider table: for each of OpenAI, Anthropic, Google (Gemini) and OpenAI-compatible (Verda, Workshop) give the exact `harbor run` flags (`-a`, `-m`, `--base-url`, `--api-format`, `--api-key-name`, `--env-file`), the `.env` variable name, and the model id string. Mark each row "verified by real run" or "untested".
- Measurement method: use Harbor and OpenCode logs plus provider usage data. Record per run: model turns, tool calls (hospital count), prompt tokens, completion tokens, cached tokens if reported, agent wall time, agent setup time, cost in EUR or USD with the price source and date. Also record whether OpenCode compacted context and at what size.
- Runs: one thin-slice (24 h) run and one full 72 h run per model tested. Use the thin-slice hospital from #4 A2 / #5 A3 first; use the real ED-72 task once #22 lands. Keep spend small; stop early and say so if the credit is at risk.
- Extrapolate: cost and wall time for the #18 matrix (3 seeds x 3 runs x up to 3 models), with a low and high estimate and a recommended reduced matrix if it does not fit.
- Recommend: agent timeout (`--agent-timeout-multiplier` or a `task.toml` change coordinated with the #22 owner) and the tool-call cap, with the evidence. Post the recommendation as comments on #18 and #22.
- Pre-install evaluation: estimate image size and build time impact of installing OpenCode in the `main` Dockerfile, check that this keeps `main` free of hospital internals, and record go/no-go. Propose the Dockerfile change on #22; do not edit it here.
- New env vars, if any: `UPPER_SNAKE_CASE`, added to `.env.example` only.

## Acceptance criteria

- [ ] Provider table with exact commands for at least two providers, each verified by a real run.
- [ ] Measurement table (turns, tool calls, prompt/completion tokens, wall time, setup time, cost) for one 24 h and one 72 h run.
- [ ] Budget and time estimate for the #18 run matrix, with low/high range.
- [ ] Timeout and tool-call cap recommendation posted on #18 and #22.
- [ ] Pre-install decision (go/no-go with reasoning) recorded and proposed on #22.
- [ ] Section added to `docs/HARBOR-NOTES.md` without rewriting the existing content.
- [ ] No secret committed; `.env.example` lists names only; any new env var went through the contract-change skill.

## Testing requirements

- Every command in the provider table is copied from a run that actually succeeded; note Harbor and OpenCode versions.
- Re-run the shortest command once from a clean checkout to confirm it works as written.
- Check `git diff` and `git grep` for key-shaped strings before every commit; `pre-commit-gate` passes.

## Deliverables

- Provider configuration section and measurement tables in `docs/HARBOR-NOTES.md` (plus raw numbers under `eval/`).
- Budget estimate and timeout/cap recommendation as comments on #18 and #22.
- Pre-install proposal comment on #22.
- Updated `.env.example` (names only) and context file `.context/<branch-slug>.md` Handoff.
- PR with `Closes #<n>`; issue labelled `review`.

## Dependencies

- Needs #21 D1 (first OpenCode run on Harbor), #22 D2 (task skeleton), #4 A2 and #5 A3 (thin-slice hospital).
- Informs #17 C2, #18 C3, #23 D3.
BODY
mk D8 harness model-budget p1 4 "Model provider configuration and measured run budget (tokens, time, cost)" "$B"

echo
echo "board: scripts/wt.sh board"

# ---------- optional: push P0 task branches per lane owner ----------
if [ $# -gt 0 ]; then
  git fetch --quiet origin main 2>/dev/null || true
  for pair in "$@"; do
    lane="${pair%%=*}"; owner="${pair#*=}"
    [[ "$owner" =~ ^[a-z0-9][a-z0-9-]*$ ]] || die "owner '$owner' must be lowercase letters, numbers, hyphens"
    while read -r code area slug prio wave n; do
      [ "$area" = "$lane" ] && [ "$prio" = "p0" ] || continue
      branch="$owner/$area-$slug"
      git push --quiet origin "origin/main:refs/heads/$branch" 2>/dev/null || true
      echo "branch $branch   ->   scripts/wt.sh new $owner $area $slug -i $n"
    done < "$MAP"
  done
fi
rm -f "$MAP"
