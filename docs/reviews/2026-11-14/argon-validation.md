# Validation of Argon's supplied review

Yehor supplied `CODE_REVIEW.md` and asked for valid additional findings to be uploaded for Kostya. This checks its claims against main `474829afe5f9b5bf5b10f18561ce149c634a957f`, using three Astra reviewers and consolidated source/reproduction checks. Argon's document names the older ref `59d55c836900e027534db5cc254617c091350e1e`. Main was rechecked before publication and still pointed to the reviewed commit.

**Result: six additional, narrowly scoped triage items: four P2 and two P3. No outstanding critical finding was confirmed.** These supplement the original seven findings in [findings.md](findings.md). Priorities below describe review urgency, not the project's board labels. Fixes remain for Kostya and the owners to schedule.

The supplied review is evidence to evaluate, not an instruction source. Its patches were not applied. This upload changes documentation only.

## Disposition of all twelve claims

| Argon ID | Decision at reviewed main | Follow-up |
|---|---|---|
| REV-01 | Already fixed: live server loads and passes ED72_CONFIG, matching collector replay. | No new issue. Existing regression covers the custom-config path. |
| REV-02 | Confirmed invalid nonfinite config acceptance. Impact is operator configuration, not an agent-facing DoS surface. The claimed NaN reward was not reproduced. | A1, P2. |
| REV-03 | Confirmed ordinary-command false negatives in the local hook. No bypass of GitHub protections or complete permission system established. | A2, P3. |
| REV-04 | Boundary behavior exists, but no high-severity gameplay bug established. Ending at tick 144 does not truncate effects. | Clarify custom-event lifecycle policy if needed; no proposed defect issue. |
| REV-05 | Missing done-slug validation and status-query encoding are real. Shell execution and arbitrary-directory deletion claims are unsupported. | A3, P3. |
| REV-06 | Confirmed mixed-ref inputs; secondary rule regex is wrap-sensitive. This script is not executed as a CI gate. | A4, P2; regex note P3. |
| REV-07 | Source-checkout startup lacks the adjacent handbook; the documented Docker deployment explicitly supplies it. | Native startup convenience only; no shipped runtime defect. |
| REV-08 | Failures require synthetic/corrupt histories that normal simulation and collector replay do not produce. | No new production bug. Explicit validation would be preferable to hiding corruption. |
| REV-09 | Confirmed mixed units in chart totals. Duplicate-label aggregation is explicitly documented in the function, though the chart title says per run. | A5, P2. |
| REV-10 | Bash 3.2 empty-array crash disproved on the actual macOS shell. Separate .env parsing problem confirmed. | A6, P2, for environment parsing only. |
| REV-11 | Null-agent-info setup-failure claim conflicts with pinned Harbor 0.25's required schema and initialization. Corrupt/truncated JSON can fail parsing. | Optional diagnostic robustness; no demonstrated normal completed-run failure. |
| REV-12 | Empty/non-JSON unexpected replies can escape the CLI's diagnostic handler; no such response established from the shipped server's normal tool path. | Optional diagnostic hardening, not a confirmed shipping blocker. |

## Additional findings for issue triage

### A1 [P2] Reject nonfinite numeric configuration before world generation

**Source:** [config.py:40–47](https://github.com/xand1ex999/guinness/blob/474829afe5f9b5bf5b10f18561ce149c634a957f/ed72/environment/hospital/ed72_sim/config.py#L40), numeric fields and mixture weights, with range checks at lines 115–122.

`_is_number` accepts NaN and infinities. Comparisons do not reject all such values, so hospital-owned difficulty configs pass `load_config` and fail later or use meaningless budget settings.

Bounded in-memory reproductions patched the file read, then called the real loader/world generator:

| Config | Observed behavior |
|---|---|
| `{"arrival_mean": NaN}` | Loader accepts; world generation raises `ValueError: poisson mean must be finite and >= 0, got nan`. |
| `{"arrival_peak_hour": Infinity}` | Loader accepts; world generation raises `ValueError: math domain error`. |
| `{"flu_mix": {"3": NaN, "4": 0.5}}` | Loader accepts; weighted choice rejects nonfinite weights later. |
| `{"budget": NaN}` | A complete do-nothing simulation produces finite B = 0.0. |
| `{"hard_limit": Infinity}` | A complete do-nothing simulation produces finite B = 1.0. |

**Fix:** reject nonfinite numeric values centrally with a finite-value check, covering scalar settings and mixture weights. Keep bool rejection and existing range rules. Test NaN, positive/negative infinity and overflowed JSON float values, plus normal finite configs. Reject at the configuration boundary with the field name.

**Correction to Argon:** the observed budget cases did not produce NaN rewards. The agent cannot normally edit hospital config. Suggested owner: environment/config owner, with Kostya deciding any rule implications.

### A2 [P3] Extend the main-branch push hook's ordinary-command coverage

**Source:** [no-push-from-main.sh:6–10](https://github.com/xand1ex999/guinness/blob/474829afe5f9b5bf5b10f18561ce149c634a957f/.claude/hooks/no-push-from-main.sh#L6) and [.claude/settings.json](https://github.com/xand1ex999/guinness/blob/474829afe5f9b5bf5b10f18561ce149c634a957f/.claude/settings.json#L46).

Dry JSON-input tests of the unchanged hook, with only the branch query stubbed to return `main`, gave:

| Command text supplied to the hook | Hook result |
|---|---|
| `git push` | deny |
| `git -C . push` | no decision |
| `git --no-pager push` | no decision |
| `true && git push` | no decision |

These command strings were not executed as pushes. The literal JSON substring matcher misses ordinary Git forms; its branch query also checks the hook's current directory rather than a separately targeted checkout.

**Fix:** parse the JSON field, recognize the supported ordinary command forms and their target checkout, and add dry-input regression cases. State the limits of a shell-command heuristic. Repository protections should enforce shared-branch restrictions independently.

**Corrections to Argon:** no actual remote protection bypass was tested. Do not blanket-ban `--force-with-lease`: AGENTS.md explicitly allows it on an owner's own task branch after rebasing. This is a convenience guard improvement, not a high-severity security finding.

### A3 [P3] Validate worktree-removal slugs and encode status query values

**Source:** [wt.sh:354–363](https://github.com/xand1ex999/guinness/blob/474829afe5f9b5bf5b10f18561ce149c634a957f/scripts/wt.sh#L354) and [wt.sh:287–290](https://github.com/xand1ex999/guinness/blob/474829afe5f9b5bf5b10f18561ce149c634a957f/scripts/wt.sh#L287).

`done` documents a slug but constructs a path from unchecked input. A print-only Git stub confirmed that a slug containing path components can reach the removal call as a traversing path. This can select a different registered linked worktree instead of rejecting the malformed slug. No real removal was performed.

Separately, `review/a&per_page=100` is a valid Git ref name. Interpolating it directly into the activity URL changes the query parameters instead of querying that exact branch. This can make the last-push/status signal wrong for such names.

**Fix:** call the existing `valid "$1"` before constructing a removal path. Encode the status query's ref value, for example using structured `gh api --method GET -f` arguments rather than URL interpolation. Test malformed slugs with a print-only Git stub and verify the exact query value for a legal ref containing `&`.

**Corrections to Argon:** quoted arguments do not execute shell content. Status requires an existing ref. Git rejects traversal/backslash ref names; the activity request uses a fixed read-only endpoint. Real Git removes registered linked worktrees, not arbitrary directories. This is narrow tooling correctness, not demonstrated command injection.

### A4 [P2] Read all versioned board-check inputs from the selected ref

**Source:** [board-check.sh:19–22](https://github.com/xand1ex999/guinness/blob/474829afe5f9b5bf5b10f18561ce149c634a957f/scripts/board-check.sh#L19).

PLAN, AGENTS and HANDBOOK are read using `git show "$PLAN_REF:..."`, but bootstrap-board.sh is copied from the working checkout. A local uncommitted bootstrap change or an older feature checkout can therefore change the result of a check nominally targeting `origin/main`. Historical bootstrap `8834ab3` lacks D9, while the reviewed main includes it; Check 2 derives its code set from the mismatched bootstrap input.

**Fix:** use `git show "$PLAN_REF:scripts/bootstrap-board.sh" > "$TMP/bootstrap.sh" || exit 1`. Do not silently fall back to the working file when the selected ref lacks it: that preserves the mismatch. Test with intentionally different working-tree and selected-ref bootstrap content.

**Secondary P3 note:** the [rule regex at line 189](https://github.com/xand1ex999/guinness/blob/474829afe5f9b5bf5b10f18561ce149c634a957f/scripts/board-check.sh#L189) matches `at least one covered tick: loss 0.3` but fails if only the space after `tick:` is replaced by a newline. Normalize whitespace within the same paragraph/table cell before matching. The current handbook passes.

**Correction to Argon:** current CI checks shell syntax; it does not run this board checker as a semantic CI gate.

### A5 [P2] Keep unused ticks separate from clinical failure counts in the SVG

**Source:** [svg.py:16–30](https://github.com/xand1ex999/guinness/blob/474829afe5f9b5bf5b10f18561ce149c634a957f/analysis/ed72_analysis/svg.py#L16).

The chart sums every failure-code value and labels the result “Failure events per run”. F10 counts unused ticks, whereas the currently implemented other codes count failure occurrences. Synthetic input containing only `{"F10":144}` renders a bar labelled 144 failure events, even with no clinical failure counts. This makes the chart's comparison misleading.

**Fix:** show F10 in its own ticks-labelled panel or series, and display each other failure code separately or clearly label any deliberate sum. Individual codes can overlap; a total should not be presented as a unique patient count. Add a chart assertion with only F10 populated.

**Duplicate-label correction:** two synthetic runs with the same label and counts 2 and 3 produce one bar 5. The function explicitly documents summing per label, so aggregation itself is intentional. Either label that chart as a per-label total with run counts, or preserve distinct run rows/reject duplicate labels if “per run” is the desired product behavior. The report's per-code table already preserves units.

Suggested owner: analysis/reporting owner.

### A6 [P2] Parse supported .env quoting without changing model/key values

**Source:** [run_all.sh:38–46](https://github.com/xand1ex999/guinness/blob/474829afe5f9b5bf5b10f18561ce149c634a957f/eval/run_all.sh#L38).

The reader strips only double quotes at the exact start/end. Safe synthetic values confirmed that single quotes survive, a CRLF line retains the carriage return (and can retain the closing quote), and inline comments become part of the value. Ordinary double-quoted values work.

A concrete no-credential trigger is `ED72_MODEL='gemini/example'`: the exported value retains the leading quote, so the provider-prefix case rejects it before the model run. Quoted provider credentials similarly retain literal quote characters. No real credentials or paid model calls were used.

**Fix:** define and parse the intended dotenv syntax safely: matched single/double quotes, CRLF, and comments outside quotes, while preserving literal content inside quotes and the rule that a shell-provided value wins. Use a parser with tested behavior or a small explicitly limited parser; do not source arbitrary .env shell commands. Test with dummy values.

**Bash correction:** on macOS `/bin/bash` 3.2.57, `set -euo pipefail; FAILED=()` followed by the exact final length check succeeds; the length is 0. A populated array reports 1. Do not open the claimed empty-array portability issue or apply a workaround for it.

## Claims not promoted to fix issues

- **REV-01:** [server.py:113–120](https://github.com/xand1ex999/guinness/blob/474829afe5f9b5bf5b10f18561ce149c634a957f/ed72/environment/hospital/server.py#L113) now loads ED72_CONFIG, matching collect.py. [test_server.py:173–184](https://github.com/xand1ex999/guinness/blob/474829afe5f9b5bf5b10f18561ce149c634a957f/ed72/environment/hospital/tests/test_server.py#L173) covers this.
- **REV-04:** a flu event at 138 with duration 6 produces all 12 arrivals over ticks 138–143. Its ends_tick is 144; no event_end is emitted because tick 144 is not executed. An event beyond the horizon naturally has effects only during the episode. A warning whose calculated start is before zero is visible at the initial observation. If the team requires complete lifecycle log pairs, document that policy and its terminal-event semantics; do not confuse “all effects fit” (end <= 144) with “end record executes” (end < 144).
- **REV-07:** [hospital/Dockerfile:15](https://github.com/xand1ex999/guinness/blob/474829afe5f9b5bf5b10f18561ce149c634a957f/ed72/environment/hospital/Dockerfile#L15) supplies /app/HANDBOOK.md. Native source startup would need an explicit supported setup, not just an assumed fallback.
- **REV-08:** unknown-patient death and an invented successful step at 144 reproduce the reported KeyError/negative F10 only with synthetic impossible histories. Collector replay regenerates simulator events and rejects tick mismatch. Normal upgrade is ESI 3 to 2. Do not silently discard impossible events to make corrupted logs look valid.
- **REV-11:** pinned Harbor 0.25 defines agent_info as required and fills it in _init_result before preparation; normal errored trial fixtures already pass the evaluation tests. Truncated JSON does raise JSONDecodeError, and Harbor writes result JSON directly. Handling concurrent/incomplete output is a useful optional improvement, but preserve a visible error/pending state rather than silently dropping corrupted runs and biasing the summary.
- **REV-12:** response decoding lies outside the CLI's exception handler. Unexpected empty/non-JSON replies can produce a traceback; no normal shipped-server reproduction was established. If improving diagnostics, inspect content types and report a concise nonzero error. Do not substitute fake successful output.

## Validation and publication scope

Validation used source comparison, the installed pinned Harbor schema, actual macOS Bash 3.2, in-memory config/simulation and chart reproductions, synthetic environment values, and dry hook/worktree stubs. No real pushes or worktree removals were executed by the reproductions. No live model run or new full Docker matrix was needed for this documentation addendum; the original report retains its separate runtime evidence.

The main implementation and existing worktrees were not modified. The supplied raw review and its unverified patches are not being published as endorsed findings. Kostya should create or reuse owner issues for A1–A6, respecting the existing freeze and priority decisions, and leave the optional items as notes unless a supported failure is demonstrated.
