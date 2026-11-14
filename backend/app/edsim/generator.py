"""Builds everything exogenous for one run from (config, seed), before the agent acts.

Agent actions never draw random numbers, so two agents given the same seed face the same
patients, incidents and inpatient-bed offers (common random numbers).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from app.edsim import config as C
from app.edsim.entities import Bed, Equipment, Patient, ScheduledEvent, Shift, Staff
from app.edsim.rng import Stream

EVENT_ORDER = (
    "staff_sickness",
    "equipment_failure",
    "bed_closure",
    "supply_shortage",
    "budget_cut",
    "demand_spike",
    "major_incident",
)


@dataclass
class Scenario:
    config: C.DifficultyConfig
    seed: int
    budget: float
    patients: list[Patient]
    staff: list[Staff]
    beds: list[Bed]
    equipment: list[Equipment]
    events: list[ScheduledEvent]
    inpatient_offers: list[int]


def _staff(
    staff_id: str, role: str, skills: frozenset[str], team: str, shifts: list[tuple[int, int]], stream: Stream
) -> Staff:
    return Staff(
        staff_id=staff_id,
        role=role,
        skills=skills,
        team=team,
        shifts=[Shift(start=s, end=e, scheduled_end=e) for s, e in shifts],
        fatigue=round(stream.uniform(5, 20), 2),
    )


def _team(prefix: str, team: str, spec: C.TeamSpec, starts: list[int], stream: Stream) -> list[Staff]:
    shifts = [(s, s + 12 * C.MINUTES_PER_HOUR) for s in starts]
    members: list[Staff] = []
    for role, count, tag in (("attending", spec.attending, "att"), ("resident", spec.resident, "res")):
        for i in range(1, count + 1):
            skills = frozenset({"critical_care"}) if role == "attending" else frozenset()
            members.append(_staff(f"{tag}-{prefix}{i}", role, skills, team, shifts, stream))
    for i in range(1, spec.nurse + 1):
        nurse_skills: set[str] = set()
        if i <= spec.nurse_critical_care:
            nurse_skills.add("critical_care")
        if i > spec.nurse - spec.nurse_triage:
            nurse_skills.add("triage")
        members.append(_staff(f"rn-{prefix}{i}", "nurse", frozenset(nurse_skills), team, shifts, stream))
    # The last triage-skilled nurse starts in triage so arrivals are triaged from minute 0.
    triage_nurses = [s for s in members if "triage" in s.skills]
    if triage_nurses:
        triage_nurses[-1].zone = "triage"
    return members


def _layout(config: C.DifficultyConfig) -> tuple[list[Bed], list[Equipment]]:
    beds = [
        Bed(bed_id=f"{C.BED_PREFIX[cls]}-{i}", bed_class=cls)
        for cls in C.BED_CLASSES
        for i in range(1, config.beds.get(cls, 0) + 1)
    ]
    equipment = [
        Equipment(equipment_id=f"{C.EQUIPMENT_PREFIX[kind]}-{i}", kind=kind)
        for kind in (*C.HELD_EQUIPMENT, *C.IMAGING)
        for i in range(1, config.equipment.get(kind, 0) + 1)
    ]
    return beds, equipment


def _scaled_count(stream: Stream, bounds: tuple[int, int], frac: float) -> int:
    n = stream.integer(*bounds)
    return n if frac >= 1.0 else int(round(n * frac))


def _events(
    config: C.DifficultyConfig, staff: list[Staff], beds: list[Bed], equipment: list[Equipment], seed: int
) -> tuple[list[ScheduledEvent], list[tuple[int, int, float]]]:
    """Returns the scheduled events and the demand-spike windows that shape arrivals."""
    horizon = config.horizon_minutes
    frac = horizon / C.HORIZON_MINUTES
    stream = Stream(seed, "events")
    events: list[ScheduledEvent] = []
    spikes: list[tuple[int, int, float]] = []
    sick_pool = list(staff)
    counter = 0

    def window(early: int, late_margin: int) -> int:
        low = min(early, horizon - 1)
        return stream.integer(low, max(low, horizon - late_margin))

    for kind in EVENT_ORDER:
        for _ in range(_scaled_count(stream, config.events.get(kind, (0, 0)), frac)):
            counter += 1
            event_id = f"EV-{counter:02d}"
            if kind == "staff_sickness":
                if not sick_pool:
                    continue
                member = sick_pool.pop(stream.integer(0, len(sick_pool) - 1))
                shift = stream.pick([sh for sh in member.shifts if sh.start < horizon])
                length = shift.end - shift.start
                notice = shift.start >= 120 and stream.chance(0.5)
                minute = shift.start - 120 if notice else shift.start + stream.integer(60, length - 120)
                params = {
                    "staff_id": member.staff_id,
                    "variant": "shift_cancelled" if notice else "left_mid_shift",
                    "sick_from": shift.start if notice else minute,
                    "sick_until": shift.end,
                }
                events.append(ScheduledEvent(event_id, kind, minute, params))
            elif kind == "equipment_failure":
                item = stream.pick(equipment)
                downtime = stream.integer(180, 600)
                estimate = int(round(downtime * stream.uniform(0.7, 1.3) / 15.0)) * 15
                params = {
                    "equipment_id": item.equipment_id,
                    "downtime": downtime,
                    "estimate": max(15, estimate),
                }
                events.append(ScheduledEvent(event_id, kind, window(60, 120), params))
            elif kind == "bed_closure":
                bed_class = stream.weighted({"general": 0.5, "monitored": 0.3, "fast_track": 0.2})
                size = sum(1 for b in beds if b.bed_class == bed_class)
                high = max(1, min(4, size - 1))
                count = stream.integer(min(2, high), high)
                params = {"bed_class": bed_class, "count": count, "duration": stream.integer(240, 480)}
                events.append(ScheduledEvent(event_id, kind, window(60, 240), params))
            elif kind == "supply_shortage":
                params = {"duration": 720, "multiplier": 1.6}
                events.append(ScheduledEvent(event_id, kind, window(60, 240), params))
            elif kind == "budget_cut":
                minute = stream.integer(int(horizon * 0.5), int(horizon * 0.83))
                params = {"fraction": round(stream.uniform(0.06, 0.08), 4)}
                events.append(ScheduledEvent(event_id, kind, minute, params))
            elif kind == "demand_spike":
                start = window(60, 240)
                duration = stream.integer(120, 240)
                multiplier = round(stream.uniform(1.6, 2.0), 3)
                spikes.append((start, start + duration, multiplier))
                params = {"duration": duration, "multiplier": multiplier}
                events.append(ScheduledEvent(event_id, kind, start, params))
            elif kind == "major_incident":
                alert = window(120, 180)
                size = stream.integer(6, 10)
                params = {
                    "estimate": max(3, size + stream.integer(-2, 2)),
                    "first_arrival": alert + 15,
                    "spread": stream.integer(30, 45),
                    "size": size,
                }
                events.append(ScheduledEvent(event_id, kind, alert, params))
    events.sort(key=lambda e: (e.minute, e.event_id))
    return events, spikes


def _arrival_minutes(
    config: C.DifficultyConfig, spikes: list[tuple[int, int, float]], seed: int
) -> list[int]:
    """Non-homogeneous Poisson arrivals by thinning against the peak possible rate."""
    stream = Stream(seed, "arrivals")
    peak = config.base_arrivals_per_hour * max(C.DIURNAL) * 2.0
    t = 0.0
    minutes: list[int] = []
    while True:
        t += stream.exponential(peak / C.MINUTES_PER_HOUR)
        if t >= config.horizon_minutes:
            return minutes
        minute = int(t)
        rate = config.base_arrivals_per_hour * C.DIURNAL[C.hour_of_day(minute)]
        for start, end, multiplier in spikes:
            if start <= minute < end:
                rate *= multiplier
        if stream.uniform() < rate / peak:
            minutes.append(minute)


def _patient(pid: str, arrival: int, incident_id: str | None, seed: int) -> Patient:
    s = Stream(seed, f"patient:{pid}")
    if incident_id:
        complaint = s.weighted(C.INCIDENT_COMPLAINTS)
        acuity = s.weighted(C.INCIDENT_ACUITY)
    else:
        complaint = s.weighted({name: c.weight for name, c in C.COMPLAINTS.items()})
        acuity = s.weighted(C.COMPLAINTS[complaint].acuity_weights)
    age = s.integer(*s.weighted({(1, 17): 0.15, (18, 64): 0.60, (65, 95): 0.25}))
    ambulance = s.chance(C.AMBULANCE_PROB[acuity])
    spec = C.COMPLAINTS[complaint]
    r = s.uniform()
    imaging = "ct" if r < spec.ct else ("xray" if r < spec.ct + spec.xray else None)
    imaging_minutes = s.integer(*C.IMAGING_MINUTES[imaging]) if imaging else 0
    duration = C.EXPECTED_DURATION[acuity] * s.lognormal_factor(C.DURATION_SIGMA)
    complication = s.uniform(*C.COMPLICATION_FACTOR) if s.chance(C.COMPLICATION_PROB) else 1.0
    return Patient(
        patient_id=pid,
        age=age,
        arrival_min=arrival,
        mode="ambulance" if incident_id or ambulance else "walk_in",
        complaint=complaint,
        incident_id=incident_id,
        acuity=acuity,
        initial_acuity=acuity,
        duration=duration,
        complication_factor=complication,
        imaging=imaging,
        imaging_minutes=imaging_minutes,
        triage_minutes=s.integer(*C.TRIAGE_MINUTES),
        thresholds=[s.exponential() for _ in range(C.THRESHOLDS_PER_PATIENT)],
        patience_z=s.normal(),
        admit_draw=s.uniform(),
        vent_draw=s.uniform(),
    )


def _inpatient_offers(config: C.DifficultyConfig, seed: int) -> list[int]:
    stream = Stream(seed, "inpatient")
    day_rate, night_rate = config.inpatient_offers_per_hour
    peak = max(day_rate, night_rate)
    t = 0.0
    offers: list[int] = []
    while True:
        t += stream.exponential(peak / C.MINUTES_PER_HOUR)
        if t >= config.horizon_minutes:
            return offers
        minute = int(t)
        rate = day_rate if 7 <= C.hour_of_day(minute) < 19 else night_rate
        if stream.uniform() < rate / peak:
            offers.append(minute)


def build_scenario(config: C.DifficultyConfig, seed: int) -> Scenario:
    horizon = config.horizon_minutes
    staff_stream = Stream(seed, "staff")
    day_starts = [s for s in (0, 1440, 2880) if s < horizon]
    night_starts = [s for s in (720, 2160, 3600) if s < horizon]
    staff = _team("d", "day", config.day_team, day_starts, staff_stream)
    staff += _team("n", "night", config.night_team, night_starts, staff_stream)
    beds, equipment = _layout(config)
    events, spikes = _events(config, staff, beds, equipment, seed)

    incident_stream = Stream(seed, "incidents")
    arrivals: list[tuple[int, int, str | None]] = [
        (m, 0, None) for m in _arrival_minutes(config, spikes, seed)
    ]
    for event in events:
        if event.kind != "major_incident":
            continue
        first, spread, size = event.params["first_arrival"], event.params["spread"], event.params["size"]
        for minute in sorted(first + incident_stream.integer(0, spread) for _ in range(size)):
            if minute < horizon:
                arrivals.append((minute, 1, event.event_id))
    arrivals.sort(key=lambda a: (a[0], a[1]))

    patients = [
        _patient(f"PT-{i:04d}", minute, incident, seed)
        for i, (minute, _, incident) in enumerate(arrivals, start=1)
    ]
    return Scenario(
        config=config,
        seed=seed,
        budget=round(config.budget * horizon / C.HORIZON_MINUTES, 2),
        patients=patients,
        staff=staff,
        beds=beds,
        equipment=equipment,
        events=events,
        inpatient_offers=_inpatient_offers(config, seed),
    )


def expected_roster_cost(config: C.DifficultyConfig) -> float:
    """Wage bill of the rostered teams with no overtime, used to sanity-check budgets."""
    total = 0.0
    for spec, starts in ((config.day_team, (0, 1440, 2880)), (config.night_team, (720, 2160, 3600))):
        hours = sum(min(12.0, max(0.0, (config.horizon_minutes - s) / 60)) for s in starts)
        hourly = (
            spec.attending * C.WAGE_PER_HOUR["attending"]
            + spec.resident * C.WAGE_PER_HOUR["resident"]
            + spec.nurse * C.WAGE_PER_HOUR["nurse"]
        )
        total += hourly * hours
    return math.floor(total)
