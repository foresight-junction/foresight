"""Token and cost estimate for one ED-72 agent run (issue #37).

One model turn per tick: the agent reads the `step` result (the next observation) and answers with the
next `step` call. Context grows by one observation plus one answer per tick until OpenCode compacts it.
Replace the defaults with measured numbers once a real run exists.

    python eval/budget/estimate.py
    python eval/budget/estimate.py --base 16000 --per-tick 2600 --compact-at 200000 --price-in 3 --cached 0.9
"""

import argparse

TICKS = 144
SUMMARY_TOKENS = 3000


def run_tokens(base: int, per_tick: int, compact_at: int, ticks: int = TICKS) -> tuple[int, int, int]:
    """Return (total prompt tokens, peak context, number of compactions)."""
    context, total, peak, compactions = base, 0, base, 0
    for _ in range(ticks):
        total += context
        peak = max(peak, context)
        context += per_tick
        if compact_at and context > compact_at:
            context = base + SUMMARY_TOKENS
            compactions += 1
    return total, peak, compactions


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument(
        "--base", type=int, default=14000, help="system prompt + tool schemas + instruction + rules"
    )
    p.add_argument("--per-tick", type=int, default=2400, help="step result (~1.9k) + model answer (~0.5k)")
    p.add_argument("--output", type=int, default=500, help="completion tokens per turn, incl. reasoning")
    p.add_argument(
        "--compact-at", type=int, default=0, help="context size that triggers compaction, 0 = never"
    )
    p.add_argument("--price-in", type=float, default=1.0, help="USD per million uncached prompt tokens")
    p.add_argument("--price-out", type=float, default=5.0, help="USD per million completion tokens")
    p.add_argument("--cached", type=float, default=0.0, help="share of prompt tokens served from cache")
    p.add_argument("--cache-discount", type=float, default=0.1, help="cached price as a share of --price-in")
    p.add_argument(
        "--runs", type=int, default=27, help="runs in the matrix (#18: 3 seeds x 3 runs x 3 models)"
    )
    a = p.parse_args()

    prompt, peak, compactions = run_tokens(a.base, a.per_tick, a.compact_at)
    completion = a.output * TICKS
    effective_in = a.price_in * ((1 - a.cached) + a.cached * a.cache_discount)
    cost = prompt / 1e6 * effective_in + completion / 1e6 * a.price_out

    print(f"prompt tokens per run:     {prompt / 1e6:.1f} M")
    print(f"peak context:              {peak / 1e3:.0f} k  ({compactions} compactions)")
    print(f"completion tokens per run: {completion / 1e3:.0f} k")
    print(f"cost per run:              ${cost:.2f}")
    print(f"cost for {a.runs} runs:          ${cost * a.runs:.0f}")


if __name__ == "__main__":
    main()
