"""Hidden-information firewall checks (issue #31) for one collected tool result.

Each check takes the result as the agent received it (raw JSON text) and the ground truth taken
from sim internals, and returns violations tagged with the issue's assertion letter:
  a  future information: a patient, arrival tick or unannounced event that has not happened yet
  b  secrets: hidden field names, the seed, dice rolls, log or config paths
  c  warnings: only announced events, exact start tick, inside the rulebook lead time
  d  shape: exactly the CONTRACTS v1 fields and values

Values are matched by structured field (a patient-id string, a `*_tick` integer, an event-kind
string), never by bare digits, so ordinary counts cannot cause false alarms.
"""

import json
import re
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from firewall_shapes import result_errors

# Rulebook §7: the two announced events and their notice in ticks. The other two never warn.
WARNING_LEAD = {"flu_wave": 10, "bus_crash": 8}
UNANNOUNCED_EVENTS = ("staff_sickness", "ct_breakdown")

# Internal names from ed72_sim (model.World/PatientSpec/EventSpec, state.State/PatientState/
# StaffState, the event log) and the CONTRACTS score object. None of them is an agent-facing field.
DENY_KEYS = frozenset(
    {
        "seed",
        "ed72_seed",
        "ed72_config",
        "config",
        "config_path",
        "rng",
        "rng_state",
        "random_state",
        "dice",
        "roll",
        "rolls",
        "hazard_u",
        "divert_u",
        "upgrade_ct_u",
        "world",
        "state",
        "patients",
        "events",
        "event_log",
        "log",
        "log_path",
        "seq",
        "src",
        "kind",
        "source",
        "arrival_tick",
        "warning_ticks",
        "duration",
        "ends_tick",
        "return_tick",
        "arrive_tick",
        "leave_tick",
        "ct_return_tick",
        "divert_last",
        "needed",
        "scanned",
        "ever_covered",
        "covered_now",
        "schedule",
        "future",
        "upcoming",
        "next_arrival",
        "score",
        "reward",
        "spend",
        "outcome",
        "on_time",
        "failures",
        "failure_codes",
        "first_covered_tick",
        "ticks_with_actions",
        "tool_calls",
        "ended",
    }
)
# Case-sensitive: the score components, the log's tick key and a raw uniform.
DENY_KEYS_EXACT = frozenset({"O", "T", "W", "B", "t", "u"})
SECRET_MARKERS = ("ED72_SEED", "ED72_CONFIG", "events.jsonl", "/var/lib/ed72", "ed72_sim", "random.Random")
# A seed this large is unlikely to collide with any count or tick, so its digits can be matched.
SEED_VALUE_MIN = 100_000

PATIENT_ID_IN_TEXT = re.compile(r"\bP\d{3,}\b")
ECHO_PARENT = re.compile(r"(^|\.)last_rejected\[\d+\]$")
WARNING_PATH = re.compile(r"(^|\.)warnings\[\d+\]\.(event|start_tick)$")


@dataclass(frozen=True)
class HiddenEvent:
    kind: str
    start_tick: int
    duration: int


@dataclass(frozen=True)
class Truth:
    seed: int
    arrivals: dict[str, int]  # every patient id of the episode -> its arrival tick
    events: tuple[HiddenEvent, ...]
    dice: frozenset[float] = frozenset()  # every uniform the world generator drew


@dataclass(frozen=True)
class Violation:
    rule: str
    path: str
    detail: str


def truth_from_world(world: Any) -> Truth:
    """Ground truth from an ed72_sim.model.World (read by attribute, so this module imports no sim)."""
    dice = set()
    for p in world.patients:
        dice.update((p.divert_u, p.upgrade_ct_u, *p.hazard_u))
    return Truth(
        seed=world.seed,
        arrivals={p.id: p.arrival_tick for p in world.patients},
        events=tuple(HiddenEvent(e.kind, e.start_tick, e.duration) for e in world.events),
        dice=frozenset(dice),
    )


def walk(value: Any, path: str = "$") -> Iterator[tuple[str, str | None, Any]]:
    """Yield (path, key, value) for every node.

    The agent's own action echoed in last_rejected[i].action is not descended into: it holds
    whatever the agent sent. The episode tests check that it equals the sent action verbatim.
    """
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            yield child_path, key, child
            if not (key == "action" and ECHO_PARENT.search(path)):
                yield from walk(child, child_path)
    elif isinstance(value, list):
        for i, child in enumerate(value):
            child_path = f"{path}[{i}]"
            yield child_path, None, child
            yield from walk(child, child_path)


def secret_violations(payload: Any, truth: Truth) -> list[Violation]:
    out = []
    seed_digits = str(truth.seed) if truth.seed >= SEED_VALUE_MIN else None
    for path, key, value in walk(payload):
        if key is not None and (key in DENY_KEYS_EXACT or key.lower() in DENY_KEYS):
            out.append(Violation("b", path, f"hidden field name {key!r}"))
        if isinstance(value, str):
            out += [Violation("b", path, f"contains {m!r}") for m in SECRET_MARKERS if m in value]
            if seed_digits and seed_digits in value:
                out.append(Violation("b", path, "contains the seed"))
        elif type(value) is int and seed_digits and value == truth.seed:
            out.append(Violation("b", path, "equals the seed"))
        elif type(value) is float and value in truth.dice:
            out.append(Violation("b", path, f"{value!r} is a pre-drawn dice roll"))
    return out


def future_violations(payload: Any, truth: Truth, as_of: int) -> list[Violation]:
    out = []
    hidden = [e for e in truth.events if e.kind in UNANNOUNCED_EVENTS and as_of < e.start_tick]
    for path, key, value in walk(payload):
        if isinstance(value, str):
            for pid in PATIENT_ID_IN_TEXT.findall(value):
                arrival = truth.arrivals.get(pid)
                if arrival is None:
                    out.append(Violation("a", path, f"{pid} is not a patient of this episode"))
                elif arrival > as_of:
                    out.append(Violation("a", path, f"{pid} arrives at tick {arrival}, now {as_of}"))
            out += [
                Violation("a", path, f"names {e.kind}, which starts at tick {e.start_tick}, now {as_of}")
                for e in hidden
                if e.kind in value
            ]
        elif type(value) is int and key is not None and key.endswith("_tick") and value > as_of:
            if WARNING_PATH.search(path):
                continue  # announced start ticks are judged by warning_violations
            starts = [e.kind for e in truth.events if e.start_tick == value]
            what = f" (start of {', '.join(starts)})" if starts else ""
            out.append(Violation("a", path, f"future tick {value}{what}, now {as_of}"))
    return out


def warning_violations(obs: dict, truth: Truth, path: str) -> list[Violation]:
    """Warnings must be exactly the announced events from start - lead until the event ends."""
    tick = obs.get("tick")
    rows = obs.get("warnings")
    if type(tick) is not int or not isinstance(rows, list):
        return []  # malformed: reported by the shape check
    expected = {
        (e.kind, e.start_tick)
        for e in truth.events
        if e.kind in WARNING_LEAD and e.start_tick - WARNING_LEAD[e.kind] <= tick < e.start_tick + e.duration
    }
    shown = [(r.get("event"), r.get("start_tick")) for r in rows if isinstance(r, dict)]
    out = [
        Violation("c", f"{path}.warnings", f"warning {kind}@{start} not due at tick {tick}")
        for kind, start in shown
        if (kind, start) not in expected
    ]
    out += [
        Violation("c", f"{path}.warnings", f"missing warning {kind}@{start} at tick {tick}")
        for kind, start in sorted(expected - set(shown))
    ]
    if len(shown) != len(set(shown)):
        out.append(Violation("c", f"{path}.warnings", "duplicate warning"))
    return out


def hidden_event_state_violations(obs: dict, truth: Truth, path: str) -> list[Violation]:
    """Before an unannounced event starts, the state must not show its effect."""
    tick = obs.get("tick")
    if type(tick) is not int:
        return []
    out = []
    for e in truth.events:
        if tick >= e.start_tick:
            continue
        if e.kind == "ct_breakdown" and obs.get("ct") != {"working": True, "down_ticks_left": 0}:
            out.append(Violation("a", f"{path}.ct", f"CT shown down before the breakdown at {e.start_tick}"))
        if e.kind == "staff_sickness":
            sick = [
                s.get("id") for s in obs.get("staff", []) if isinstance(s, dict) and s.get("status") == "sick"
            ]
            if sick:
                out.append(
                    Violation("a", f"{path}.staff", f"{sick} sick before the sick call at {e.start_tick}")
                )
    return out


def past_log_violations(obs: dict, log: list[dict], path: str) -> list[Violation]:
    """Totals, waiting patients and bed occupants must follow from the sim's event log so far.

    This catches a covert channel that the name and value checks cannot: future information
    encoded in a legitimate field, such as next tick's arrival count written into a total.
    """
    sim = [e for e in log if e.get("src") == "sim"]
    count = Counter(e.get("event") for e in sim)
    totals = {
        "discharged": count["discharged"],
        "deaths": count["death"],
        "left": count["left"],
        "diverted": count["diverted"],
        "faints": count["faint"],
    }
    out = []
    if obs.get("totals") != totals:
        out.append(Violation("a", f"{path}.totals", f"{obs.get('totals')} but the log so far gives {totals}"))
    arrived = {e["patient"] for e in sim if e.get("event") == "arrival"}
    admitted = {e["patient"] for e in sim if e.get("event") == "admitted"}
    gone_from_bed = {e["patient"] for e in sim if e.get("event") == "discharged"}
    gone_from_bed |= {e["patient"] for e in sim if e.get("event") == "death" and e.get("cause") != "waiting"}
    gone_waiting = {e["patient"] for e in sim if e.get("event") == "left"}
    gone_waiting |= {e["patient"] for e in sim if e.get("event") == "death" and e.get("cause") == "waiting"}
    waiting = {w.get("id") for w in obs.get("waiting", []) if isinstance(w, dict)}
    if waiting != arrived - admitted - gone_waiting:
        out.append(Violation("a", f"{path}.waiting", "waiting patients do not follow from the log so far"))
    in_beds = {b.get("patient") for b in obs.get("beds", []) if isinstance(b, dict)} - {None}
    if in_beds != admitted - gone_from_bed:
        out.append(Violation("a", f"{path}.beds", "bed occupants do not follow from the log so far"))
    return out


def check_result(
    tool: str, raw: str, truth: Truth, as_of: int, log: list[dict] | None = None
) -> list[Violation]:
    """All firewall checks for one result.

    as_of is the sim's true tick after the call; log is the sim's event log up to that moment,
    when the caller has it (the episode tests do, the fixture tests do not).
    """
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        return [Violation("d", "$", f"not JSON: {exc}")]
    out = [Violation("d", "$", e) for e in result_errors(tool, payload)]
    out += secret_violations(payload, truth)
    if tool == "rules":
        return out  # static text, checked to be identical across seeds instead
    out += future_violations(payload, truth, as_of)
    if not isinstance(payload, dict) or "error" in payload:
        return out
    obs, path = (payload, "$") if tool == "observe" else (payload.get("observation"), "$.observation")
    if isinstance(obs, dict):
        if obs.get("tick") != as_of:
            out.append(Violation("d", f"{path}.tick", f"tick {obs.get('tick')!r} but the sim is at {as_of}"))
        out += warning_violations(obs, truth, path)
        out += hidden_event_state_violations(obs, truth, path)
        if log is not None:
            out += past_log_violations(obs, log, path)
    return out
