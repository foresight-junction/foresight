#!/usr/bin/env bash
# Creates the labels and the task issues for the AfterQuery challenge. Safe to run twice:
# an issue whose code (A1, B2, ...) is already in a title is skipped.
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

EXISTING="$(gh issue list --state all --limit 300 --json number,title -q '.[] | "\(.number)\t\(.title)"')"
MAP="$(mktemp)"

# mk <code> <area> <slug> <prio> <title> <body>
mk() {
  local code="$1" area="$2" slug="$3" prio="$4" title="$5" body="$6" n
  n="$(printf '%s\n' "$EXISTING" | grep -F "] $code: " | head -1 | cut -f1 || true)"
  if [ -n "$n" ]; then
    echo "skip  #$n  $code (exists)"
  else
    n="$(gh issue create --title "[$area] $code: $title" --label "todo,area:$area,$prio" --body "$body" | grep -oE '[0-9]+$')"
    echo "made  #$n  [$area] $code: $title"
  fi
  printf '%s %s %s %s %s\n' "$code" "$area" "$slug" "$prio" "$n" >> "$MAP"
}

READ="Read first: AGENTS.md (section 10), docs/CHALLENGE.md, docs/SPEC.md, docs/CONTRACTS.md."

# ---------- Lane A: world and tools ----------
mk A1 env world p0 "Seeded world generator: patients, staff, beds, equipment, events" "$READ

**Goal:** generate the hospital from a seed: about 220 patients over 72 hours (true acuity 1 to 5, triage label, condition, required skill and equipment, treatment duration, health), a staff roster with skills (critical_care, general) and three 8-hour shifts plus an on-call pool, 15 beds (3 resus, 12 general), equipment (4 monitors, 2 ventilators, 1 CT) and the event schedule. Spec section 3.

**Files you own:** \`ed72/environment/hospital/ed72_sim/world.py\`, its tests.
**Depends on:** nothing.
**Rules:** synthetic data only, invented names. All randomness from one seeded random.Random. No network, no clock.
**Done when:** \`generate(seed)\` returns the same world twice for one seed and different worlds for two seeds (tested), and a JSON dump of 3 patients and 3 staff is pasted in the PR."

mk A2 env sim p0 "Sim core: tick loop, deterioration, event log, thin-slice tools" "$READ

**Goal:** the episode engine. A 15-minute tick loop, health falling by true acuity, treatment progress and an append-only event log. Thin-slice tools: board, patient, roster, assess, admit, assign, discharge, advance, clock, end_shift. The thin slice runs 24 sim hours.

**Files you own:** \`ed72/environment/hospital/ed72_sim/\` except \`world.py\` and \`scoring/\`.
**Depends on:** A1 (stub the world until it lands). Tool shapes: docs/CONTRACTS.md.
**Rules:** no reset or undo. The clock moves only on advance (15 to 120 minutes) and advance returns early on a label 1 or 2 arrival or an event. Bad args return an error object and change nothing else. The hospital counts the tool-call cap.
**Done when:** a pytest drives a 24-hour episode through the Python API, and replaying the same actions gives a byte-identical event log."

mk A3 env server p0 "Tool server: MCP + ward CLI + /health" "$READ

**Goal:** expose the sim's tools over MCP (streamable-http at /mcp) and through a \`ward\` CLI in the agent container (\`ward <tool> --json '<args>'\`). Add GET /health.

**Files you own:** \`ed72/environment/hospital/server.py\`, \`ed72/environment/ward\`.
**Depends on:** A2, D1 (tells us MCP vs CLI as the main path).
**Rules:** no reset, seed, ground-truth or finalise endpoint.
**Done when:** from the \`main\` container, \`ward board\` returns the board and an MCP client lists the tools."

mk A4 env rules2 p1 "Rules round 2: fatigue, budget, equipment, transfers, returns, events" "$READ

**Goal:** the rules that make the 72 hours hard. Fatigue and sick-out (above 90 the person is off sick for 24 hours). Budget and overtime pricing (1.5x for the first 4 extra hours, then 2x; call-in, transfer and repair have fixed prices). Equipment faults and repairs. Transfers (90-minute drive, 2 ambulances) and diversion. Early-discharge returns. Seeded events with precursor notices. Adds tools: equipment, budget, notices, handbook, order_test, transfer, set_diversion, call_in, extend_shift, send_on_break, repair. The episode grows to 72 hours.

**Files you own:** rule modules under \`ed72/environment/hospital/ed72_sim/rules/\`.
**Depends on:** A2, B1. Tell lane B the consequence of each new rule before you merge.
**Done when:** each rule has a test showing its sim consequence, and the reference policy (C1) is still >= 0.9."

mk A5 env handbook p1 "HANDBOOK.md and instruction.md: every rate table and scored rule written down" "$READ

**Goal:** the agent-visible handbook and the task instruction. Every rate table (deterioration, safe wait limits, prices, fatigue) and every rule the scorer applies must be findable in the handbook. Say that about 20% of triage labels are wrong. Plain wording, no tricks. This protects the 30 points for meaningful difficulty.

**Files you own:** \`ed72/environment/workspace/HANDBOOK.md\`, \`ed72/instruction.md\`.
**Depends on:** A2, A4, B1.
**Done when:** a table in the PR maps every scorer rule and sim rate to a handbook section, and a teammate who has not read the code can plan 5 sample patients correctly from the handbook alone."

mk A6 env knobs p1 "Difficulty config: one file of knobs" "$READ

**Goal:** one hospital-side config for the number of patients over 72 hours, the share of wrong labels, the share of quiet deterioration, the budget, the evening load and the event timing. Tune with lane C after the 18:00 run.

**Files you own:** \`ed72/environment/hospital/config/\`.
**Depends on:** A2, C2.
**Done when:** changing one value changes the episode, the reference stays >= 0.9, and the chosen values are written in docs/SPEC.md."

mk A7 env events p2 "Extra event types and a second hospital layout" "$READ

**Goal:** more ordinary events (for example a lab slowdown or a second monitor fault) and a second bed and equipment layout, so one set of tuned rules is not the whole test.

**Files you own:** \`ed72/environment/hospital/ed72_sim/rules/events_extra.py\`, \`ed72/environment/hospital/config/layouts/\`.
**Depends on:** A4, A6.
**Done when:** each new event has a notice precursor and a handbook line, and the reference scores >= 0.9 on both layouts."

# ---------- Lane B: reward and integrity ----------
mk B1 reward scorer p0 "Scorer: per-patient harm, M1 and M2, anchors, floor, normalisation" "$READ

**Goal:** pure function \`score(events, world)\` as in docs/SPEC.md section 6 and the score object in docs/CONTRACTS.md. Per patient harm: M1 Outcome (death 100, permanent harm 40) and M2 Timeliness (safe wait 0, 10, 30, 60, 120 minutes for acuity 1 to 5; weight 5, 3, 1.5, 0.5, 0.2 per 10 minutes, cap 30). H_anchor comes from trivial policies replayed on the same seed. H_floor comes from a full-information planner in the hospital image. reward = clip((H_anchor - H) / (H_anchor - H_floor), 0, 1). Use test-driven development.

**Files you own:** \`ed72/environment/hospital/ed72_sim/scoring/\`, its tests.
**Depends on:** A1 for the world shape (agree it early, then work in parallel on fixtures).
**Rules:** reads only the event log and the world. No LLM. Deterministic. Staff fatigue, budget and bed use are never scored directly.
**Done when:** unit tests show an empty log = 0, do-nothing = 0, a hand-built perfect log = 1.0, one death costs more than any wait, and the same events give the same score."

mk B2 reward verifier p0 "Verifier: collect.py writes report.json, test.sh always writes a number" "$READ

**Goal:** \`collect.py\` runs inside the hospital container as the \`[[verifier.collect]]\` hook, finalises the episode and writes /evidence/report.json (declared as a sidecar artifact). \`ed72/tests/test.sh\` reads only that file, writes the reward to /logs/verifier/reward.txt and the full object to /logs/verifier/score_full.json. Harbor runs with environment_mode separate.

**Files you own:** \`ed72/tests/\`, \`ed72/environment/hospital/collect.py\`.
**Depends on:** D2, A2 (use a stub until it lands).
**Rules:** always writes a number in [0,1]. On any error write 0. Use absolute paths and set -u. Trust nothing in the agent's container.
**Done when:** \`harbor run -p ed72 -a oracle\` shows a reward, and a root agent writing reward.txt itself does not change it."

mk B3 reward anchors p1 "Trivial-policy anchors + CI test (all <= 0.05)" "$READ

**Goal:** scripted policies that avoid the task: do-nothing, first-come-first-served by label, discharge-all, transfer-all, divert-all, call-in-everyone, random, plus stop-early at hour k. A test asserts every one scores <= 0.05 on every shipped seed. Stop-early at hour k must score no more than playing to hour k and then doing nothing.

**Files you own:** \`eval/baselines/\`, \`ed72/environment/hospital/ed72_sim/scoring/tests/test_anchors.py\`.
**Depends on:** B1, A2.
**Done when:** the baseline score table is in the PR and the test runs in CI."

mk B4 reward redteam1 p1 "Red-team round 1 (Sat 19:00)" "$READ

**Goal:** 15 minutes attacking the reward the way judges will, done by someone who did NOT write the scorer. Try: write reward.txt yourself, read the sim source or seed from the agent container, discharge everyone, transfer everyone, divert everything, unlimited overtime, stop early, burn everything in the last hours, negative or huge advance minutes, assign the same nurse twice, hit the hospital on other ports or paths.

**Files you own:** \`docs/REDTEAM.md\`.
**Depends on:** B2, A3.
**Done when:** every attempt is logged with its result, and each working exploit has its own issue labelled p0."

mk B5 reward redteam2 p1 "Red-team round 2 after rules freeze (Sat 23:30) + regression tests" "$READ

**Goal:** repeat B4 on the frozen rules with a different person, and add one regression test per exploit found in either round.

**Files you own:** \`docs/REDTEAM.md\`, regression tests under \`ed72/environment/hospital/ed72_sim/scoring/tests/\`.
**Depends on:** B4, A4.
**Done when:** REDTEAM.md lists what was tried and why each attempt fails. We show this page in the demo."

mk B6 reward modules p1 "Modules M3 Disposition and M4 Continuity" "$READ

**Goal:** M3 Disposition: a return after early discharge costs 15 plus the patient's later outcome; leaving without being seen costs 2 to 10 by acuity; harm in transit or after diversion counts. M4 Continuity: outcomes during the 12-hour handover tail, using the same table as M1 to M3.

**Files you own:** \`ed72/environment/hospital/ed72_sim/scoring/disposition.py\`, \`ed72/environment/hospital/ed72_sim/scoring/continuity.py\`, their tests.
**Depends on:** B1, A4.
**Done when:** unit tests cover an early discharge that returns, a diverted critical patient, and a patient who dies in the tail."

# ---------- Lane C: reference and experiments ----------
mk C1 ref policy p0 "Reference policy (solution/solve.sh), public tools only" "$READ

**Goal:** a scripted policy that plays the shift through the same tools the agent has and scores >= 0.9. It assesses every arrival, re-assesses waiting patients by acuity, keeps one resus bed free, rotates breaks before fatigue reaches 70, reads notices every sim hour, holds a budget reserve per remaining day and discharges only on handbook criteria. This is our stronger reference run.

**Files you own:** \`ed72/solution/\`.
**Depends on:** A2, A3, B1.
**Rules:** never reads the seed, ground truth, event log or sim source. If it cannot decide from tool output and the handbook, that is a bug in the environment: open an issue for lane A.
**Done when:** \`harbor run -p ed72 -a oracle\` scores >= 0.9 three times in a row with the identical score."

mk C2 ref firstrun p0 "First OpenCode run at 18:00 (calibration)" "$READ

**Goal:** run OpenCode with our strongest model on the thin slice and tell the team if there is a gap.

**Files you own:** \`eval/results/\`.
**Depends on:** D2, A3, B2, C1.
**Done when:** the Harbor run log is committed under eval/results/, and a comment on this issue gives: the score, the reference score, the 3 biggest mistakes with patient ids and F codes, and a recommendation (keep / harder / fairer)."

mk C3 ref matrix p1 "Run matrix: 3 seeds x 3 runs x up to 3 models" "$READ

**Goal:** the numbers for the 30-point gap. 3 seeds x 3 runs for up to 3 models (one each from Anthropic, OpenAI, Google), plus reference, nop and stop-early.

**Files you own:** \`eval/results/\`, \`eval/matrix.yaml\`.
**Depends on:** D3, A4 merged, rules frozen (22:00).
**Done when:** eval/results/summary.md has a table with mean and min/max per model and seed, every agent run is below the reference, and all logs are committed."

mk C4 ref findings p1 "Failure analysis: docs/FINDINGS.md" "$READ

**Goal:** explain where the agent falls short and why, tied to decisions. Use the counts per failure code F1 to F10 and the harm per module from score_full.json, and the trajectories.

**Files you own:** \`analysis/\`, \`docs/FINDINGS.md\`.
**Depends on:** C3 (start on C2's run).
**Done when:** FINDINGS.md has a failures-by-code chart, harm by module, 3 trajectory excerpts, and one honest paragraph on what the agent did well."

mk C5 ref fairness p1 "Fairness audit of every agent mistake" "$READ

**Goal:** for each mistake in C4, check the agent could have known better: the rule is in the handbook and the fact was reachable through a tool in time (for example the true acuity through assess, a breakdown through notices). Where it was not, fix the environment, not the write-up.

**Files you own:** a section in \`docs/FINDINGS.md\`.
**Depends on:** C4, A5.
**Done when:** each failure code has a line 'rule: handbook section X, fact: tool Y', and any unfair case has an issue for lane A."

# ---------- Lane D: harness, repro and story ----------
mk D1 harness spike p0 "Harbor spike: one real OpenCode run against a stub hospital sidecar" "$READ

**Goal:** most of the spike is done on Kostiantyn's branch (\`origin/kostiantyn/env-unfindable-slice\`, see \`docs/unfindable/SPIKE_S0_RESULTS.md\`): sidecar, separate mode and the collect hook. What remains: one real \`-a opencode -m <model>\` run against a stub hospital sidecar. Confirm OpenCode sees the MCP tools from \`[[environment.mcp_servers]]\`. OpenCode installs over npm, so main needs internet or a preinstall.

**Files you own:** \`docs/HARBOR-NOTES.md\`.
**Depends on:** nothing. Do this first, it unblocks A3 and B2.
**Done when:** HARBOR-NOTES.md has the exact working commands, the MCP-or-CLI decision, and where run logs land. Post the decision on the Contracts issue."

mk D2 harness skeleton p0 "Task skeleton: ed72/ tree, copy the Unfindable packaging" "$READ

**Goal:** the Harbor task folder from docs/SPEC.md section 9. Copy the packaging from \`origin/kostiantyn/env-unfindable-slice:harbor/unfindable/\` (task.toml with separate mode and the collect hook, compose with the hospital sidecar and a healthcheck, start.sh, Dockerfiles) and rename it to ed72 and hospital, so the other lanes drop their code in.

**Files you own:** \`ed72/task.toml\`, \`ed72/environment/Dockerfile\`, \`ed72/environment/docker-compose.yaml\`, \`ed72/environment/hospital/Dockerfile\`, \`ed72/environment/hospital/start.sh\`.
**Depends on:** D1.
**Rules:** the \`main\` image holds HANDBOOK.md and the ward CLI only. No sim code, no seed, no scorer.
**Done when:** with stub code, \`harbor run -p ed72 -a oracle\` and \`-a nop\` both finish and write a reward."

mk D3 harness eval p1 "One-command eval: make eval" "$READ

**Goal:** one command that reproduces our reported results: reference, nop, stop-early and 3 agent runs (\`-k 3\`). Writes eval/results/summary.md. Stop-early is a small scripted agent that plays the reference to hour 24 and then calls end_shift.

**Files you own:** \`Makefile\`, \`eval/run_all.sh\`, \`eval/summarise.py\`.
**Depends on:** D2, B2, C1.
**Done when:** on a fresh clone on another laptop, \`make eval\` runs to the end with only Docker, Harbor and one API key set."

mk D4 harness ci p1 "CI for the new layout" "$READ

**Goal:** replace the old CI steps with ruff and pytest for ed72_sim and the scorer, plus the anchors test.

**Files you own:** \`.github/workflows/ci.yml\`.
**Depends on:** A2, B1.
**Done when:** CI runs on a PR in under 3 minutes and fails when a scorer test fails."

mk D5 harness story p1 "README, demo script, demo video, submission" "$READ

**Goal:** the README (what the agent has to do, why it is hard, how we score it, the one command, the results table, a link to a Harbor run log), a 10-minute demo script, the demo video with a playthrough, and the Junction submission form.

**Files you own:** \`README.md\`, \`docs/DEMO.md\`.
**Depends on:** C3, C4, B5.
**Rules:** a human writes the core paragraphs. AfterQuery said AI-written READMEs tend to sell the environment badly.
**Done when:** submitted before Sun 10:00, and a teammate has timed the demo under 10 minutes."

mk D6 harness seeds p2 "Three seeds as task folders + x86/ARM build check" "$READ

**Goal:** stamp out ed72-s1 to ed72-s3 from one template so judges can rerun on more than one seed, and confirm the images build on both x86 and Apple Silicon.

**Files you own:** \`scripts/make_seeds.sh\`.
**Depends on:** D2, rules freeze.
**Done when:** all three run with oracle >= 0.9 and nop = 0."

mk D7 train stretch p2 "Stretch: small model before and after training" "$READ

**Goal:** the tiebreaker. Collect reference-policy trajectories, fine-tune a small open model (about 4B parameters) on Modal, and run it in the environment before and after on one held-out seed.

**Files you own:** \`training/\`.
**Depends on:** rules freeze at 22:00 and everything P1 green. Do not start before that.
**Done when:** a two-row table (base vs tuned, same seed) is in the README, or the task is dropped by 01:00."

echo
echo "board: scripts/wt.sh board"

# ---------- optional: push P0 task branches per lane owner ----------
if [ $# -gt 0 ]; then
  git fetch --quiet origin main 2>/dev/null || true
  for pair in "$@"; do
    lane="${pair%%=*}"; owner="${pair#*=}"
    [[ "$owner" =~ ^[a-z0-9][a-z0-9-]*$ ]] || die "owner '$owner' must be lowercase letters, numbers, hyphens"
    while read -r code area slug prio n; do
      [ "$area" = "$lane" ] && [ "$prio" = "p0" ] || continue
      branch="$owner/$area-$slug"
      git push --quiet origin "origin/main:refs/heads/$branch" 2>/dev/null || true
      echo "branch $branch   ->   scripts/wt.sh new $owner $area $slug -i $n"
    done < "$MAP"
  done
fi
rm -f "$MAP"
