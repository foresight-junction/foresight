"""Per-patient timelines from the event log, for the worst failures."""

from ed72_analysis.tables import WEIGHT

BAD_OUTCOMES = ("died", "never_admitted")


def pick_patients(score: dict, limit: int = 3) -> list[dict]:
    bad = [p for p in score["patients"] if p["outcome"] in BAD_OUTCOMES]
    return sorted(bad, key=lambda p: (-WEIGHT[p["esi"]], p["id"]))[:limit]


def timeline(events: list[dict], patient: dict) -> list[str]:
    """Lines in log order from this patient's sim lines. Zone occupancy comes from other patients' lines."""
    pid = patient["id"]
    zone_of: dict[str, str] = {}
    end_t = max((e["t"] for e in events if e["src"] == "sim"), default=0)
    out: list[str] = []
    arrived: int | None = None
    for e in events:
        if e["src"] != "sim":
            continue
        kind, who = e["event"], e.get("patient")
        if who != pid:
            _track(zone_of, kind, who, e)
            continue
        t = e["t"]
        if kind == "arrival":
            arrived = t
            out.append(f"t{t}: arrived ESI {e['esi']} (needs_ct={e['needs_ct']}, source={e['source']})")
        elif kind == "admitted":
            others = sum(z == e["zone"] for z in zone_of.values())
            wait = t - arrived if arrived is not None else "?"
            out.append(
                f"t{t}: admitted to {e['zone']} bed {e['bed']} after {wait} ticks waiting "
                f"({others} other patients in {e['zone']})"
            )
        elif kind == "upgrade":
            out.append(f"t{t}: upgraded to ESI {e['esi']}")
        elif kind == "covered":
            out.append(f"t{t}: first covered by staff")
        elif kind == "death":
            out.append(f"t{t}: died, cause {e['cause']}")
        elif kind in ("discharged", "left"):
            out.append(f"t{t}: {kind}")
        _track(zone_of, kind, who, e)
    if patient["outcome"] == "never_admitted" and arrived is not None:
        out.append(f"t{end_t}: episode ended, never admitted ({end_t - arrived} ticks after arrival)")
    return out


def _track(zone_of: dict[str, str], kind: str, who: str | None, e: dict) -> None:
    if kind == "admitted":
        zone_of[who] = e["zone"]
    elif kind in ("discharged", "left", "death"):
        zone_of.pop(who, None)


def excerpts_md(events: list[dict], score: dict, limit: int = 3) -> str:
    blocks = []
    for p in pick_patients(score, limit):
        codes = ", ".join(p["failure_codes"]) or "none"
        head = f"**{p['id']}** (ESI {p['esi']}, {p['outcome']}, failure codes: {codes})"
        blocks.append(head + "\n\n" + "\n".join(f"- {line}" for line in timeline(events, p)))
    return "\n\n".join(blocks) if blocks else "No patient died or went unadmitted."
