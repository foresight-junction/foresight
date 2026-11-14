# Branch: kostiantyn/reward-verifier

- **Issue:** #11
- **Owner:** kostiantyn
- **Agent:** kostiantyn-claude-2e
- **Parent branch:** main

## Goal
collect.py (hospital container) replays the agent's logged steps, scores, writes /evidence/report.json. test.sh + verify.py turn that into /logs/verifier/reward.txt (always a number) and score_full.json.

## Files and folders I own
- ed72/environment/hospital/collect.py, ed72/tests/{test.sh,verify.py,Dockerfile}, hospital/tests/test_collect.py, test_verify.py

## Don't touch
- ed72/task.toml, docker-compose, environment Dockerfiles (lane D #22), ed72_sim/*.

## Contracts used or changed
CONTRACTS v1 Admin endpoints, Score object. No changes.

## Status
- [x] collect.py (assumes Simulation(world), sim.step(actions), sim.tick, sim.events, sim.run_to_end(); score(events))
- [x] verify.py + test.sh + tests/Dockerfile (copied from Unfindable)
- [x] unit tests (18 pass; collect tests use fake ed72_sim modules until #3/#4/#10 merge)
- [ ] integration with real sim once merged; `harbor run -p ed72 -a oracle`

## Decisions and notes
- verify.py checks reward==score/100 and score==60O+20T+O(10W+10B) within 1e-3 to catch forged reports.
- Verifier image is python:3.12-slim; task needs tests/Dockerfile in separate mode like Unfindable.

## Handoff
Done: all files above. Not done: real-sim integration. Test: cd ed72/environment/hospital && python -m pytest -q.
