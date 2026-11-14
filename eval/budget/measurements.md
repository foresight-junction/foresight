# Model run budget (issue #37)

Status: **estimates only, no ED-72 run measured yet.** Real runs need the thin-slice hospital (#4 A2, #5 A3) and the `ed72/` task (#22 D2). Every number marked *estimate* gets replaced by a measured one.

Interface assumed: CONTRACTS v1 from PR #43 (`rules`, `observe`, `step`; 144 `step` calls per episode; call cap 500; agent timeout 3600 s).

## 1. Provider configuration

Keys go in `.env` (gitignored) and are passed with `--env-file`. Never put a key on the command line.

| Provider | `.env` name | Command flags | Status |
|---|---|---|---|
| OpenAI-compatible: Verda | `VERDA_INFERENCE_API_KEY` | `-a opencode -m verda/kimi-k3-1-pro --base-url https://inference.verda.com/v1 --api-format openai_chat_completions --api-key-name VERDA_INFERENCE_API_KEY --env-file .env --agent-setup-timeout-multiplier 3` | Verified by a real run: Harbor 0.26.0, OpenCode 1.19.5, Unfindable task (Kostiantyn, Sat 14 Nov) |
| Google Gemini | `GEMINI_API_KEY` | `-a opencode -m gemini/gemini-3.8-flash --api-key-name GEMINI_API_KEY --env-file .env --ak version=1.19.5 --agent-setup-timeout-multiplier 3` | Untested. Command from `docs/HARBOR-NOTES.md` on `yehor/harness-harbor-spike` (#21); Harbor maps `gemini/` to OpenCode's `google/` |
| OpenAI | `OPENAI_API_KEY` | `-a opencode -m openai/<model> --env-file .env` | Untested. `OPENAI_API_KEY` is the opencode agent's default key name (SPIKE_S0_RESULTS §5) |
| Anthropic | `ANTHROPIC_API_KEY` | `-a opencode -m anthropic/<model> --api-key-name ANTHROPIC_API_KEY --env-file .env` | Untested |
| OpenAI-compatible: Workshop | TBD | `--base-url <workshop url> --api-format openai_chat_completions --api-key-name <name>` | Untested. Needs the base URL and a variable name |

Prefix every command with `harbor run -p ed72`. Model ids for OpenAI and Anthropic are picked at the 18:00 checkpoint (EVAL §4).

## 2. Tokens per run (estimate)

Measured with `obs_tokens.py` (o200k tokenizer) on observations in the CONTRACTS v1 shape:

| Department state | Observation, compact JSON | Observation, indented JSON | `step` result, compact |
|---|---:|---:|---:|
| Quiet: 3 waiting, 60% of beds full | 1.4k | 2.3k | 1.4k |
| Busy: 12 waiting, all beds full, 2 agency | 1.8k | 3.0k | 1.9k |
| Surge: 25 waiting, all beds full, 4 agency | 2.2k | 3.7k | 2.3k |

Indented JSON costs about 65% more tokens than compact JSON, so the tool server (#5) should return compact JSON.

Per-run model (`estimate.py`): one model turn per tick, about 14k tokens of fixed context (OpenCode system prompt, tool schemas, instruction, rules) and about 2.4k added per tick (1.9k `step` result plus a 0.5k answer). The 14k base comes from the Verda Kimi run, which averaged 13.5k prompt tokens per turn on a much smaller task.

| OpenCode compaction | Prompt tokens per run | Peak context | Completion tokens |
|---|---:|---:|---:|
| None (1M-context model) | 26.7 M | 357k | 72k |
| At 200k | 14.6 M | 199k | 72k |
| At 128k | 10.2 M | 127k | 72k |

Whether and when OpenCode compacts is unknown. Measure it on the first real run.

## 3. Cost (estimate)

Prices below are illustrative tiers, not quotes. Replace them with each provider's published price and its date once models are chosen. A share of prompt tokens served from cache is billed at 10% of the input price.

| Input / output price (USD per M) | Caching | No compaction: per run / 27 runs | Compact at 200k: per run / 27 runs |
|---|---|---:|---:|
| 0.5 / 2 | none | $14 / $365 | $7 / $201 |
| 0.5 / 2 | 80% cached | $4 / $105 | $2 / $59 |
| 3 / 15 | none | $81 / $2,194 | $45 / $1,209 |
| 3 / 15 | 80% cached | $24 / $635 | $13 / $360 |
| 15 / 75 | none | $406 / $10,970 | $224 / $6,046 |
| 15 / 75 | 80% cached | $118 / $3,177 | $67 / $1,798 |

27 runs is the full #18 matrix: 3 seeds x 3 runs x 3 models. Prompt caching changes the bill by about 3.5x, so check that each provider caches OpenCode's prefix.

Reduced matrix if the full one does not fit: 3 runs x 1 seed for the strongest model, plus 1 run x 3 seeds for the other two (9 runs, a third of the cost).

## 4. Wall time (estimate)

144 model turns at 5 to 20 s each is 12 to 48 minutes of agent time, plus about 30 s for separate-mode verification and up to 8 minutes of OpenCode setup (section 6). The 3600 s timeout holds for fast models. Reasoning models with long per-turn thinking may need `--agent-timeout-multiplier 2`. Decide after the first measured run.

The 500-call cap leaves 356 calls beyond the 144 required `step` calls, so it binds only on agents that call `observe` before every `step` and also retry. Keep it.

## 5. Measurement plan (per real run)

Record: model turns, hospital-counted tool calls, prompt, completion and cached tokens, agent wall time, setup time, cost with price source and date, and whether OpenCode compacted and at what size. Sources: Harbor trial logs, the OpenCode session log in the trial's agent folder, the hospital event log, and the provider's usage page. Raw numbers go in `eval/budget/<date>-<model>.json`.

Order: one 24 h (48-tick) thin-slice run per model first, then one full 72 h run. Stop and report if a single run costs more than $30.

## 6. Pre-installing OpenCode in `main`

**Recommendation: go.** To be proposed on #22. Do not edit the Dockerfile from this branch.

- Harbor's opencode agent installs Node through nvm and runs `npm i -g opencode-ai@<version>` inside `main` at setup. On the Verda run this took about 8 minutes and needed `--agent-setup-timeout-multiplier 3`.
- Across the 27-run matrix plus the judges' 3 agent runs, that is roughly 4 hours of setup and 30 chances for an npm or nvm failure.
- `opencode-ai@1.19.5` is a 8 KB wrapper. The real binary is `opencode-linux-x64` (214 MB unpacked) or `opencode-linux-arm64` (211 MB). npm may also pull the `-baseline` variant on x64, so expect 210 to 430 MB of image growth.
- The binary contains nothing from the hospital, so AGENTS.md §10.1 holds.
- It does not remove the internet requirement: OpenCode in `main` still calls the model provider. CHALLENGE Q7 stays open for that reason.
- Checked in Harbor 0.26.0 (`harbor agent schema opencode`): `--ak skip_install=true` skips the install, and the image must provide OpenCode and its dependencies. Leaving out `--ak version=...` uses the version the image already has. So a preinstalled image needs no new flag, but pin `opencode-ai@1.19.5` in the Dockerfile so every run uses the same version.
- The same schema has `opencode_config` (an OpenCode config overlay) and `reasoning_effort`. These may let us set compaction and reasoning per run. Try them on the first measured run.
