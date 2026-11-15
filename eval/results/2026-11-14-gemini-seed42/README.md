# Gemini 3.8 Flash calibration, seed 42

This run used the earlier difficulty, arrival mean 3.0. The shipped default is 4.0 (`docs/TUNING.md`), and the final scores on seeds 3101–3103 are in the README ("Reported scores").

| Field | Value |
|---|---|
| ED-72 checkout | `71739342bd2c5d7f6e2469c8f81495e384857f4d` |
| Model | `gemini/gemini-3.8-flash` |
| OpenCode version | 1.19.5 |
| Harbor trial | `2026-11-14__19-17-49/ed72__v5mip5U` |
| Run duration | 12m 37s |
| Harbor exceptions | 0 |
| Final tick | 143 |
| Reward | 0.811712 |
| O / T / W / B | 0.833112 / 0.726111 / 1.000000 / 1.000000 |
| Arrived / discharged / died | 477 / 426 / 13 |
| F7 uncovered-bed deaths | 8 |

OpenCode generated a Python policy and ran it through the public MCP tools from its shell. The policy played all 144 ticks. The score report records 148 public tool calls overall. This is one calibration trial on seed 42. The earlier reference on seed 42 scored 0.989617, a difference of 0.177905 reward in this comparison. [Reference calibration](https://github.com/xand1ex999/guinness/issues/17#issuecomment-6880626696).

[OpenCode tool trajectory](trajectory.json) omits the reasoning field. [Verifier score report](score_full.json) and [verifier reward](reward.txt) are the original scored artifacts.
