import io
import sys

import agent


def test_log_survives_a_console_that_cannot_print_the_thought(monkeypatch) -> None:
    # Regression: a thought with "≤" crashed the live episode at tick 116 on a cp1252 Windows console.
    out = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
    monkeypatch.setattr(sys, "stdout", out)
    agent._log(116, [{"type": "divert"}], [{"index": 0, "ok": True}], "keep fatigue ≤60 → rotate")
    out.flush()
    assert (
        out.buffer.getvalue()
        .decode("cp1252")
        .startswith("tick 116: 1 actions, 0 rejected  | keep fatigue ?60")
    )
