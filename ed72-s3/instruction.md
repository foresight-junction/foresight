# Manage the emergency department for 72 hours

Run the fictional ED through all 144 half-hour ticks. Maximize the final score by treating patients, providing timely covered care, managing staff fatigue, and controlling spending.

Read `HANDBOOK.md` or call `rules` for the complete public rules, rates, and score formula. Call `observe` to inspect the initial state. Use `step` with an `actions` list to make decisions and advance one tick; it returns the next observation. Continue until the returned observation has `finished: true`.

The public tools are `rules`, `observe`, and `step`. If needed, the `ward` CLI reaches the same interface:

```sh
ward rules --json '{}'
ward observe --json '{}'
ward step --json '{"actions":[]}'
```

Every call counts toward the current provisional 500-call cap. A full episode requires 144 `step` calls. Stopping early leaves the remaining ticks running without new decisions. Patients keep arriving and staff keep their last assignments.
