# Branch: yehor/harness-seed-override

- **Issue:** #110
- **Owner:** yehor
- **Agent:** yehor-claude-21 (lead)
- **Parent branch:** main
- **Created:** Sat 23:10

## Goal
Let judges and lane C run a held-out seed without editing files, and make the README numbers match the shipped difficulty (arrival mean 4.0).

## Files I own
`ed72/environment/docker-compose.yaml` (hospital `ED72_SEED` line only), the `ED72_SEED` row in `docs/CONTRACTS.md`, `.env.example`, the Result row, Run-it block and Results table in `README.md`.

## Don't touch
`scripts/make_seeds.sh` (#26), `eval/summarise.py` and the run manifest (#105), the README prose paragraphs (#25, a human writes them).

## Status
1. Done: `ED72_SEED: "${ED72_SEED:-42}"`. Harbor 0.26 runs compose with `os.environ` (`harbor/environments/docker/docker.py:730`); `:-` covers the empty `ED72_SEED=` that `eval/run_all.sh` can export from `.env`.
2. Done: contract table, `.env.example`, announced on #1 (additive, not breaking).
3. Done: README numbers from measured runs only.
4. Verified: Harbor oracle/nop on default, empty and overridden seeds match the in-process reference.

## Handoff
Done: override, docs and README numbers. Seed folders stamped by `scripts/make_seeds.sh` still pin a literal seed. Summaries do not yet show which seed a trial used; that is #105.
Test: `ED72_SEED=7 harbor run -p ed72 -a oracle` gives 0.934310, and with no variable set it gives 0.940221 (seed 42).
