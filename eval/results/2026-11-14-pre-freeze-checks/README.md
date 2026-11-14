# ED-72 pre-freeze validation

The local check ran on 14 November 2026 from commit `8746d0e7ff5909adc7c4605f5fa8e9a17ffb72b5` with CPython 3.12.16. Ruff, shell syntax, and seed-generator checks completed. The seven Python suites reported 685 passes and one expected failure. The expected failure is the N6 log-copy case in `test_redteam_round2.py`, which the test documents as unreachable over HTTP.

| Seed | Reference score out of 100 |
| --- | ---: |
| 3101 | 95.8644 |
| 3102 | 96.0179 |
| 3103 | 94.2099 |
| Mean | 95.3641 |

- [Baseline table](baselines.md) includes reactive, stop-early, nop, and the scripted policies.
- [Probe results](probes.json) include per-seed reference scores, invalid-action spam, replay, and several stop horizons.
- [Ablation results](ablations.json) contain the scripted stand-in variants and the unablated reference.

All reported episodes ran in process. Use the frozen release revision to repeat the checks and collect the Harbor baselines and fresh model trials under [#18](https://github.com/xand1ex999/guinness/issues/18). Seeds 3101–3103 have already been inspected in this local pass.
