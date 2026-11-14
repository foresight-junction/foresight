"""Failure-mode counts F1-F10 for the analysis; they never change the reward.

Computed here: F1, F2, F6, F7, F8, F10. F3, F4, F5 and F9 need analysis beyond the log and are
omitted rather than reported as 0, which would claim they never happened (C4, issue #19, owns them).
"""

from ed72_sim import constants as c

CODES = ("F1", "F2", "F6", "F7", "F8", "F10")


def failure_analysis(events: list[dict]) -> tuple[dict[str, int], dict[str, list[str]]]:
    """Replay the log in order, tracking bed occupancy, and return (counts, per-patient codes)."""
    counts = dict.fromkeys(CODES, 0)
    per_patient: dict[str, list[str]] = {}
    esi: dict[str, int] = {}  # current ESI of each known patient
    bed_zone: dict[str, str] = {}  # patient -> zone of the bed they hold

    def flag(code: str, pid: str | None = None) -> None:
        counts[code] += 1
        if pid is not None:
            per_patient.setdefault(pid, []).append(code)

    last_step = None
    for e in events:
        if e["src"] == "agent":
            if e.get("tool") == "step" and "error" not in e.get("result", {}):
                last_step = e["t"]
            continue
        kind, pid = e["event"], e.get("patient")
        if kind in ("arrival", "diverted"):
            esi[pid] = e["esi"]
        if kind == "upgrade":
            esi[pid] = e["esi"]
            flag("F8", pid)
        elif kind == "admitted":
            bed_zone[pid] = e["zone"]
        elif kind in ("discharged", "left"):
            bed_zone.pop(pid, None)
        elif kind == "death":
            if e["cause"] == "uncovered_bed":
                flag("F7", pid)
            if e["cause"] == "waiting" and esi[pid] == 1 and _resus_held_by_low_acuity(bed_zone, esi):
                flag("F1", pid)
            bed_zone.pop(pid, None)
        elif kind == "faint":
            flag("F2")
        elif kind == "diverted" and _allowed_bed_free(esi[pid], bed_zone):
            flag("F6", pid)
    counts["F10"] = c.TICKS - 1 - last_step if last_step is not None else c.TICKS
    return counts, per_patient


def _resus_held_by_low_acuity(bed_zone: dict[str, str], esi: dict[str, int]) -> bool:
    # Blocking only counts when resus is full: with a free resus bed the death was not caused by it.
    in_resus = [p for p, zone in bed_zone.items() if zone == "resus"]
    return len(in_resus) >= c.BEDS["resus"] and any(esi[p] >= 3 for p in in_resus)


def _allowed_bed_free(level: int, bed_zone: dict[str, str]) -> bool:
    used = list(bed_zone.values())
    return any(used.count(zone) < c.BEDS[zone] for zone in c.ZONE_EXTRA_TICKS[level])
