# ED-72 reference

Harbor uploads this directory to `/solution`; `solve.sh` runs `reference.py`.
The runner invokes only `ward rules`, `ward observe` and `ward step --json ...`.
It uses the observation returned by each step and finishes after 144 ticks.
A failed command, rejected action or nonadvancing tick stops the run with an error.

`ReferencePolicy().actions(observation)` is deterministic. It admits by severity,
preserves Resus for ESI 1–2, routes light cases to Fast-track, and assigns the least
tired available staff to cover the greatest patient weight. Staff not needed for
coverage rest. Announced surges trigger two agency doctors and two nurses nine
ticks ahead, within the budget and with a €2,000 repair reserve. A broken CT gets
one repair order per outage. No simulator, scorer, seed or event log is accessed.

Run the contract tests with:

```sh
cd ed72/solution
python -m unittest discover -s tests -v
```

Or run `uv run --with pytest pytest -q` from this directory. Test fixtures are
confined to the test suite; production has no mock mode. Simulator performance
and Harbor integration must be checked independently of these contract tests.
