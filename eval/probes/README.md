# Additional exploit probes

These complement #12's baselines. Policy functions receive only public observations.
`play` uses rules, observe and step; stopping returns control to Harbor's collector.
It never accesses a seed, event log, scorer or finalise endpoint.

- `stop_early(policy, tick)` probes horizons 0, 1, 6, 24, 48 and 72; #12 owns tick 12.
- `invalid_actions` sends 50 rejected actions each tick. Real simulation tests require identical patient outcomes and zero reward versus doing nothing.
- `replay(script)` reuses public tick/action records on other seeds without adapting patient IDs.
- `assert_margin` requires a five-point gap from the reference. A failure is a finding, not a reason to lower the threshold.

Inside the agent image: `python -m eval.probes invalid-actions`, or
`python -m eval.probes replay --script /path/to/public-script.json`.
The package must be available to that runner; it is not part of the default agent image.

Run `uv run --with pytest pytest -q` in this directory. Simulator, scorer and collector imports fail loudly. A fixture pass does not establish reference superiority or Harbor integration.

The collector test times actual replay, the remaining episode, scoring and report writing on seed 42, using both one played tick and all 144 ticks with 50 rejected actions each. Its 10-second budget leaves 6x headroom against #22's 60-second hook. Record measured times rather than treating the budget as a measurement.


Measured with simulator-backed schema adapters on 14 Nov, not MCP/Harbor:

| Seed | Reference | Invalid spam | Stop at 72 | Replay seed 1 |
|---|---:|---:|---:|---:|
| 1 | 99.4228 | 0 | 40.1815 | 99.4228 (source) |
| 2 | 99.2931 | 0 | 42.8070 | 19.2550 |
| 3 | 99.7263 | 0 | 46.0504 | 12.7289 |
| 4 | 99.0893 | 0 | 42.9540 | 28.9307 |
| 5 | 97.0795 | 0 | 39.4815 | 7.2126 |
| 42 (held out) | 99.9552 | 0 | 42.8594 | 41.4911 |

Other stopping horizons were 0, 1, 6, 24 and 48. All additional probes beat the required five-point margin; the smallest foreign-seed replay margin was 58.4641 points. Source-seed replay reproduces its source score and is excluded from that comparison. No exploit finding was observed. Python 3.12 collector timing: 0.0945 s for one played tick plus tail; 0.2561 s for the full 144-step, 7,200-action replay. Both include scoring and report writing. Docker timing is pending.
