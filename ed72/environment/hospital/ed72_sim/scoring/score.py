"""Pure scorer: reward from the hospital event log only (rulebook §11, SPEC §6)."""

from ed72_sim import constants as c
from ed72_sim.scoring.failures import failure_analysis

_LOSS = {
    "discharged": c.LOSS_DISCHARGED,
    "diverted": c.LOSS_DIVERTED,
    "died": c.LOSS_FAILED,
    "left": c.LOSS_FAILED,
    "never_admitted": c.LOSS_FAILED,
}
_TOTAL_KEYS = ("discharged", "in_bed_end", "diverted", "died", "left", "never_admitted")
_PATIENT_KEYS = ("id", "esi", "outcome", "arrived_tick", "admitted_tick", "first_covered_tick", "on_time")


def score(events: list[dict]) -> dict:
    sim = [e for e in events if e["src"] == "sim"]
    starts = [e for e in sim if e["event"] == "episode_start"]
    if not starts or not any(e["event"] == "episode_end" for e in sim):
        raise ValueError("event log needs both episode_start and episode_end")
    patients = _patients(sim)
    for p in patients:
        p["loss"] = _loss(p)
    weights = {p["id"]: c.OUTCOME_WEIGHT[p["esi"]] for p in patients}
    total_w = sum(weights.values())
    o = 1.0 if not patients else 1 - sum(weights[p["id"]] * p["loss"] for p in patients) / total_w
    t = 1.0 if not patients else sum(weights[p["id"]] for p in patients if p["on_time"]) / total_w

    faints = sum(1 for e in sim if e["event"] == "faint")
    on_shift = sum(e["on_shift"] for e in sim if e["event"] == "staff_fatigue")
    tired = sum(e["on_shift_above_60"] for e in sim if e["event"] == "staff_fatigue")
    share = tired / on_shift if on_shift else 0.0
    w = max(0.0, 1 - c.W_TIRED_WEIGHT * share - c.W_FAINT_WEIGHT * faints)

    spend = sum(e["amount"] for e in sim if e["event"] == "spend")
    budget, hard_limit = starts[0]["budget"], starts[0]["hard_limit"]
    b = min(1.0, max(0.0, 1 - (spend - budget) / (hard_limit - budget)))

    total = 60 * o + 20 * t + o * (10 * w + 10 * b)
    counts, codes = failure_analysis(events)
    out_patients = [
        {k: p[k] for k in _PATIENT_KEYS} | {"failure_codes": codes.get(p["id"], [])} for p in patients
    ]
    agent = [e for e in events if e["src"] == "agent"]
    steps = [e for e in agent if e.get("tool") == "step" and "error" not in e.get("result", {})]
    capped = any(e.get("result", {}).get("error") == "call_cap_reached" for e in agent)
    totals = {"arrived": len(patients)} | {k: sum(p["outcome"] == k for p in patients) for k in _TOTAL_KEYS}
    return {
        "reward": round(total / 100, 6),
        "score": round(total, 4),
        "O": round(o, 6),
        "T": round(t, 6),
        "W": round(w, 6),
        "B": round(b, 6),
        "spend": spend,
        "totals": totals | {"faints": faints},
        "patients": out_patients,
        "failures": counts,
        "ticks_with_actions": sum(1 for e in steps if e["args"].get("actions")),
        "tool_calls": len(agent),
        "ended": _ended(steps, capped),
    }


def _patients(sim: list[dict]) -> list[dict]:
    by_id: dict[str, dict] = {}
    for e in sim:
        kind, pid = e["event"], e.get("patient")
        if kind in ("arrival", "diverted"):
            by_id[pid] = {
                "id": pid,
                "esi": e["esi"],
                "outcome": "diverted" if kind == "diverted" else None,
                "arrived_tick": e["t"],
                "admitted_tick": None,
                "first_covered_tick": None,
                "on_time": False,
            }
            continue
        p = by_id.get(pid)
        if p is None:
            continue
        if kind == "upgrade":
            p["esi"] = min(p["esi"], e["esi"])
        elif kind == "admitted":
            p["admitted_tick"] = e["t"]
        elif kind == "covered" and p["first_covered_tick"] is None:
            p["first_covered_tick"] = e["t"]
        elif kind in ("discharged", "left"):
            p["outcome"] = {"discharged": "discharged", "left": "left"}[kind]
        elif kind == "death":
            p["outcome"] = "died"
    for p in by_id.values():
        if p["outcome"] is None:
            p["outcome"] = "in_bed_end" if p["admitted_tick"] is not None else "never_admitted"
        covered = p["first_covered_tick"]
        p["on_time"] = covered is not None and covered - p["arrived_tick"] <= c.TARGET_TICKS[p["esi"]]
    return sorted(by_id.values(), key=lambda p: p["id"])


def _ended(steps: list[dict], capped: bool) -> str:
    if any(e["t"] == c.TICKS - 1 for e in steps):
        return "tick_143"
    return "call_cap" if capped else "agent_stopped"


def _loss(p: dict) -> float:
    if p["outcome"] == "in_bed_end":
        covered = p["first_covered_tick"] is not None
        return c.LOSS_IN_BED_COVERED if covered else c.LOSS_FAILED
    return _LOSS[p["outcome"]]
