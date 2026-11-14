import pytest
from ed72_sim import constants as c
from ed72_sim.scoring import score


class Log:
    """Builds a synthetic event log with increasing seq numbers."""

    def __init__(self, budget: int = c.BUDGET, hard_limit: int = c.HARD_LIMIT) -> None:
        self.lines: list[dict] = []
        self.sim(0, "episode_start", budget=budget, hard_limit=hard_limit)

    def sim(self, t: int, event: str, **kw: object) -> "Log":
        self.lines.append({"seq": len(self.lines), "t": t, "src": "sim", "event": event, **kw})
        return self

    def agent(self, t: int, actions: list | None = None, tool: str = "step") -> "Log":
        args = {"actions": actions or []}
        self.lines.append({"seq": len(self.lines), "t": t, "src": "agent", "tool": tool, "args": args})
        return self

    def arrive(self, pid: str, esi: int, t: int = 0) -> "Log":
        return self.sim(t, "arrival", patient=pid, esi=esi, needs_ct=False, source="base")

    def end(self) -> list[dict]:
        return self.sim(143, "episode_end").lines


def treated(log: Log, pid: str, esi: int, t: int = 0, covered: int | None = None) -> Log:
    log.arrive(pid, esi, t).sim(t, "admitted", patient=pid, zone="resus", bed="R1")
    log.sim(t if covered is None else covered, "covered", patient=pid)
    return log.sim(t + 5, "discharged", patient=pid)


def fatigue(log: Log, ticks: int, on_shift: int, tired: int) -> Log:
    for t in range(ticks):
        log.sim(t, "staff_fatigue", on_shift=on_shift, on_shift_above_60=tired)
    return log


def test_do_nothing_scores_zero() -> None:
    log = Log()
    for i, esi in enumerate((1, 2, 3, 4, 5)):
        log.arrive(f"P{i}", esi)
    result = score(log.end())
    assert result["score"] == 0 and result["reward"] == 0
    assert result["W"] == 1.0 and result["B"] == 1.0
    assert result["totals"]["never_admitted"] == 5


def test_perfect_play_scores_100() -> None:
    log = Log()
    for i, esi in enumerate((1, 2, 3, 4, 5)):
        treated(log, f"P{i}", esi)
    fatigue(log, 3, 10, 0)
    result = score(log.end())
    assert result["score"] == 100.0 and result["reward"] == 1.0
    assert result["O"] == result["T"] == 1.0


def test_anchor_everyone_on_time_full_fatigue_max_spend_is_80() -> None:
    log = Log()
    treated(log, "P1", 3)
    fatigue(log, 4, 10, 10).sim(5, "spend", item="repair", amount=24000)
    result = score(log.end())
    assert (result["W"], result["B"]) == (0.0, 0.0)
    assert result["score"] == 80.0


def test_in_bed_end_loss_depends_on_coverage() -> None:
    uncovered = Log().arrive("P1", 3).sim(0, "admitted", patient="P1", zone="acute", bed="A1")
    r = score(uncovered.end())
    assert r["O"] == 0.0 and r["patients"][0]["outcome"] == "in_bed_end"
    covered = Log().arrive("P1", 3).sim(0, "admitted", patient="P1", zone="acute", bed="A1")
    covered.sim(1, "covered", patient="P1")
    r = score(covered.end())
    assert r["O"] == pytest.approx(0.7) and r["patients"][0]["on_time"] is True


def test_admitted_on_time_but_first_covered_late_is_late() -> None:
    log = Log().arrive("P1", 3).sim(2, "admitted", patient="P1", zone="acute", bed="A1")
    log.sim(6, "covered", patient="P1").sim(9, "discharged", patient="P1")
    r = score(log.end())
    p = r["patients"][0]
    assert (p["admitted_tick"], p["first_covered_tick"], p["on_time"]) == (2, 6, False)
    assert r["T"] == 0.0 and r["O"] == 1.0


def test_target_boundary_is_inclusive() -> None:
    r = score(treated(Log(), "P1", 3, t=0, covered=c.TARGET_TICKS[3]).end())
    assert r["patients"][0]["on_time"] is True


def test_diverted_loss_and_late() -> None:
    log = Log().sim(0, "diverted", patient="P1", esi=4)
    r = score(log.end())
    assert r["O"] == pytest.approx(0.3) and r["T"] == 0.0
    assert r["totals"]["arrived"] == 1 and r["totals"]["diverted"] == 1
    assert r["patients"][0]["outcome"] == "diverted"


def test_upgraded_patient_uses_weight_and_target_of_esi_2() -> None:
    log = Log().arrive("P1", 3).sim(1, "upgrade", patient="P1", esi=2, needs_ct=False)
    log.sim(1, "admitted", patient="P1", zone="acute", bed="A1")
    log.sim(3, "covered", patient="P1").sim(6, "discharged", patient="P1")
    treated(log, "P2", 5, t=3)
    r = score(log.end())
    p = r["patients"][0]
    assert p["esi"] == 2 and p["on_time"] is False  # target 1, covered 3 ticks after arrival
    assert r["T"] == pytest.approx(0.5 / 5.5)
    assert r["failures"]["F8"] == 1 and "F8" in p["failure_codes"]


def test_died_left_never_admitted_are_full_loss() -> None:
    log = Log()
    log.arrive("P1", 4).sim(3, "death", patient="P1", cause="waiting")
    log.arrive("P2", 4).sim(3, "left", patient="P2")
    log.arrive("P3", 4)
    treated(log, "P4", 4)
    r = score(log.end())
    assert r["O"] == pytest.approx(0.25)
    t = r["totals"]
    assert (t["died"], t["left"], t["never_admitted"], t["discharged"]) == (1, 1, 1, 1)


@pytest.mark.parametrize(
    ("spend", "expected"), [(12000, 1.0), (18000, 0.5), (24000, 0.0), (30000, 0.0), (0, 1.0)]
)
def test_budget_curve(spend: int, expected: float) -> None:
    half = spend // 2
    log = (
        Log().sim(1, "spend", item="repair", amount=half).sim(2, "spend", item="repair", amount=spend - half)
    )
    r = score(log.end())
    assert r["B"] == expected and r["spend"] == spend


def test_wellbeing_formula_and_clamp() -> None:
    log = fatigue(Log(), 4, 10, 1)  # share 0.1
    log.sim(1, "faint", staff="D1").sim(2, "faint", staff="D2")
    r = score(log.end())
    assert r["W"] == pytest.approx(1 - 0.1 - 2 * c.W_FAINT_WEIGHT)
    assert r["totals"]["faints"] == 2 and r["failures"]["F2"] == 2
    clamped = Log()
    fatigue(clamped, 2, 4, 4)
    for i in range(3):
        clamped.sim(1, "faint", staff=f"D{i}")
    assert score(clamped.end())["W"] == 0.0


def test_no_on_shift_ticks_means_zero_share() -> None:
    assert score(Log().end())["W"] == 1.0


def test_no_patients_gives_o_and_t_of_one() -> None:
    r = score(Log().end())
    assert (r["O"], r["T"]) == (1.0, 1.0)
    assert r["score"] == 100.0


def test_missing_start_or_end_raises() -> None:
    with pytest.raises(ValueError):
        score(Log().lines)
    with pytest.raises(ValueError):
        score([{"seq": 0, "t": 143, "src": "sim", "event": "episode_end"}])


def test_rounding_and_determinism() -> None:
    log = Log()
    for i in range(3):
        log.arrive(f"P{i}", 3)
    treated(log, "P9", 3)
    r1, r2 = score(log.end()), score(log.lines)
    assert r1 == r2
    assert r1["O"] == round(r1["O"], 6) and r1["score"] == round(r1["score"], 4)


def test_agent_counters_and_ended() -> None:
    log = Log().agent(0, [{"type": "assign"}]).agent(1).agent(2, tool="observe").agent(5, [{"type": "x"}])
    r = score(log.end())
    assert (r["ticks_with_actions"], r["tool_calls"], r["ended"]) == (2, 4, "agent_stopped")
    assert r["failures"]["F10"] == 143 - 5
    full = Log().agent(143, [{"type": "x"}])
    r = score(full.end())
    assert r["ended"] == "tick_143" and r["failures"]["F10"] == 0
    assert score(Log().end())["failures"]["F10"] == 144


def test_f1_resus_held_by_low_acuity_while_esi1_dies() -> None:
    log = Log().arrive("P1", 4).sim(0, "admitted", patient="P1", zone="resus", bed="R1")
    log.arrive("P2", 1, t=1).sim(3, "death", patient="P2", cause="waiting")
    r = score(log.end())
    assert r["failures"]["F1"] == 1
    p2 = next(p for p in r["patients"] if p["id"] == "P2")
    assert p2["failure_codes"] == ["F1"]


def test_f1_not_raised_when_resus_empty_or_held_by_high_acuity() -> None:
    log = Log().arrive("P1", 2).sim(0, "admitted", patient="P1", zone="resus", bed="R1")
    log.arrive("P2", 1).sim(3, "death", patient="P2", cause="waiting")
    assert score(log.end())["failures"]["F1"] == 0
    freed = Log().arrive("P1", 4).sim(0, "admitted", patient="P1", zone="resus", bed="R1")
    freed.sim(1, "discharged", patient="P1").arrive("P2", 1).sim(3, "death", patient="P2", cause="waiting")
    assert score(freed.end())["failures"]["F1"] == 0


def test_f6_diversion_with_free_allowed_bed() -> None:
    r = score(Log().sim(0, "diverted", patient="P1", esi=4).end())
    assert r["failures"]["F6"] == 1 and r["patients"][0]["failure_codes"] == ["F6"]
    log = Log()
    n = 0
    for zone in c.ZONES:
        for _ in range(c.BEDS[zone]):
            log.arrive(f"B{n}", 4).sim(0, "admitted", patient=f"B{n}", zone=zone, bed=f"X{n}")
            n += 1
    log.sim(1, "diverted", patient="P1", esi=4)
    assert score(log.end())["failures"]["F6"] == 0


def test_f6_respects_zone_restrictions() -> None:
    log = Log()
    for i in range(c.BEDS["resus"]):
        log.arrive(f"B{i}", 1).sim(0, "admitted", patient=f"B{i}", zone="resus", bed=f"R{i}")
    log.sim(1, "diverted", patient="P1", esi=1)  # ESI 1 only fits resus, which is full
    assert score(log.end())["failures"]["F6"] == 0


def test_f7_uncovered_bed_deaths() -> None:
    log = Log().arrive("P1", 2).sim(0, "admitted", patient="P1", zone="resus", bed="R1")
    log.sim(2, "death", patient="P1", cause="uncovered_bed")
    r = score(log.end())
    assert r["failures"]["F7"] == 1 and r["patients"][0]["failure_codes"] == ["F7"]
    assert r["patients"][0]["outcome"] == "died"


def test_only_log_derivable_failure_codes_and_object_shape() -> None:
    r = score(Log().end())
    assert set(r["failures"]) == {"F1", "F2", "F6", "F7", "F8", "F10"}
    assert list(r) == [
        "reward", "score", "O", "T", "W", "B", "spend", "totals", "patients", "failures",
        "ticks_with_actions", "tool_calls", "ended",
    ]  # fmt: skip


def test_patients_sorted_by_id() -> None:
    log = Log().arrive("P2", 3).arrive("P1", 3).sim(0, "diverted", patient="P0", esi=5)
    assert [p["id"] for p in score(log.end())["patients"]] == ["P0", "P1", "P2"]


def test_refused_calls_count_as_calls_but_not_as_played_ticks() -> None:
    log = Log().agent(0, [{"type": "divert"}])
    log.lines.append(
        {"seq": len(log.lines), "t": 1, "src": "agent", "tool": "step",
         "args": {"actions": [{"type": "divert"}]}, "result": {"error": "call_cap_reached"}}
    )  # fmt: skip
    r = score(log.end())
    assert (r["tool_calls"], r["ticks_with_actions"], r["ended"]) == (2, 1, "call_cap")
    assert r["failures"]["F10"] == 143
