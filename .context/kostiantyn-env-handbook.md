# Branch: kostiantyn/env-handbook

- **Issue:** #7
- **Owner:** kostiantyn
- **Agent:** kostiantyn-codex-7
- **Parent branch:** main
- **Created:** 2026-11-14

## Goal
Publish the English agent handbook and task instruction for the v1 RU rulebook. This slice verifies the public rules and worked scenarios; engine, scorer, and Harbor acceptance remains pending integration.

## Files and folders I own
- `ed72/environment/workspace/HANDBOOK.md`
- `ed72/instruction.md`
- `.context/kostiantyn-env-handbook.md`

## Don't touch
- Simulator, scorer, tools, tests, reference policy, Dockerfiles, compose, task.toml.
- Shared docs, rulebook, skills, or any other worktree.

## Contracts used or changed
- Existing v1 `rules`, `observe`, `step`, Action, ActionResult, Observation; no contract changes.
- Public score formula and SPEC section 12 defaults; checked against upstream constants read-only.

## Status
- [x] Claim and owner-authorized start with stubbed dependencies confirmed by root.
- [x] Read mandatory sources, skills, CLAUDE, and public upstream constants.
- [x] Draft handbook and instruction within owned paths.
- [x] Validate source map, five ESI rows, seven hazards, eight JSON examples, coverage and score arithmetic.
- [x] Root independent review: no substantive findings; clarified initial arrivals, one-time CT, and sick staff fatigue.
- [x] Claude cross-review and Codex CLI review complete. Fixed sickness condition, provisional cap wording, repair timing; used source-faithful CT wording.
- [x] Documentation pre-commit gate passes: owned paths, secrets, whitespace, noslop, numeric and JSON audit.
- [ ] Integrated engine/scorer, rules serving, packaged paths, Harbor playthrough, and PR CI.

## Decisions and notes
- 2026-11-14: Arrival cycle, flu severity mix, and W weights are concrete provisional tuning defaults from SPEC section 12; no production mocks or new dependencies.
- 2026-11-14: #22 was notified of A5 ownership; packaging must preserve these files.
- Latest #6 audit input: repeated repairs are charged again without postponing CT return; agency and repair share an inclusive hard limit. Added the explicit wording, root reviewed it.
- #8 active config integration is owned by #5/#8; requested matching active values in rules and packaged handbook. This static artifact documents default.json values, not an unimplemented runtime overlay.
- Claude review: limits mirror CONTRACTS (50 actions, current provisional 500 calls); overflow behavior remains a transport contract question, so no behavior is invented here. First CLI auth failed; isolated subprocess used existing managed login without changing credentials.
- Setup template had trailing whitespace; setup gate stopped before its auto commit. Replaced placeholders with this scoped handoff before committing.

## Rules and rates coverage
| Source | Handbook section |
|---|---|
| Rulebook 2 episode, 9 tick order, 10 observation; CONTRACTS tools/cap/results | 1, 7 |
| Rulebook 3 zones, 4 patients/CT, SPEC 12 CT/upgrades | 2 |
| Rulebook 5 coverage, fatigue, fainting, agency | 3 |
| Rulebook 6 all hazards and thresholds | 4 |
| Rulebook 7 events/warnings; SPEC 12 arrival and flu defaults | 5 |
| Rulebook 8 actions, prices, limits, diversion, repair | 6 |
| Rulebook 11 score, 13 first-covered and end-loss fixes; SPEC 6/12 W | 8 |
| Five invented patient scenarios and score arithmetic | 9, 8 |

## Handoff
- Done: handbook and instruction cover all public tables, scoring, actions and timing. Source map, numeric audit, JSON examples and worked arithmetic pass; root independent review found no substantive issues.
- Next: #5/#8 must expose active config values through rules and the packaged handbook; this file covers supplied defaults only. Rules-tool byte identity, packaged paths, Harbor playthrough, and PR CI still require integration. Reviews and documentation checks pass.
- How to test: compare source rows above with handbook tables; answer the five section 9 scenarios using sections 1–8 alone; verify worked score 69.6/reward 0.696. These are documentation checks, not baseline or engine validation.
