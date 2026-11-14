from __future__ import annotations

import json
import random
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from faker import Faker

from app.sim.domain import (
    REQUESTER_TYPES,
    Case,
    Kind,
    Person,
    Request,
    Requester,
    ScheduledEvent,
    age_on,
)
from app.sim.policy import name_key

SCENARIO_DIR = Path(__file__).resolve().parents[2] / "scenarios"
SCENARIO_NAME_RE = re.compile(r"^[a-z0-9_-]{1,40}$")
EVENT_TYPES = frozenset({"sno_activated", "case_closed", "officer_reassigned"})


@dataclass
class World:
    name: str
    seed: int
    as_of: date
    postcodes: dict[str, str]
    persons: list[Person]
    initial_sno: set[str]
    requesters: list[Requester]
    cases: list[Case]
    requests: list[Request]
    events: list[ScheduledEvent]
    aliases: dict[str, str]


def available_scenarios() -> list[str]:
    return sorted(p.stem for p in SCENARIO_DIR.glob("*.json"))


def load_scenario(name: str, seed: int | None = None) -> World:
    if not SCENARIO_NAME_RE.match(name):
        raise ValueError("invalid scenario name")
    path = SCENARIO_DIR / f"{name}.json"
    if not path.is_file():
        raise ValueError(f"unknown scenario {name}")
    spec = json.loads(path.read_text(encoding="utf-8"))
    return build_world(spec, spec["seed"] if seed is None else seed)


def _ascii(text: str) -> str:
    folded = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", ".", folded.lower()).strip(".")


def _random_date(rng: random.Random, start: date, end: date) -> date:
    return start + timedelta(days=rng.randint(0, (end - start).days))


def build_world(spec: dict[str, Any], seed: int) -> World:
    rng = random.Random(seed)
    fake = Faker("fi_FI")
    fake.seed_instance(seed)
    as_of = date.fromisoformat(spec["as_of_date"])
    postcodes = {p["postcode"]: p["municipality"] for p in spec["postcodes"]}
    aliases: dict[str, str] = {}

    households: dict[str, dict[str, str]] = {}
    used_addresses: set[str] = set()
    for index, household in enumerate(spec.get("households", []), start=1):
        hid = f"H-{index:04d}"
        households[household["alias"]] = {
            "id": hid,
            "street_address": household["street_address"],
            "postcode": household["postcode"],
        }
        used_addresses.add(household["street_address"])
        aliases[household["alias"]] = hid

    persons: list[Person] = []
    used_keys: set[tuple[str, str]] = set()

    def add_person(
        full_name: str,
        dob: str,
        household: dict[str, str],
        moved_in: str,
        overrides: dict[str, Any],
    ) -> Person:
        pid = f"P-{len(persons) + 1:04d}"
        key = (name_key(full_name), dob)
        if key in used_keys:
            raise ValueError(f"duplicate name and date of birth: {full_name} {dob}")
        used_keys.add(key)
        municipality = postcodes[household["postcode"]]
        minor = age_on(dob, as_of) < 16
        person = Person(
            person_id=pid,
            full_name=full_name,
            date_of_birth=dob,
            street_address=household["street_address"],
            postcode=household["postcode"],
            municipality=municipality,
            phone=overrides.get("phone") or fake.phone_number(),
            email=overrides.get("email") or f"{_ascii(full_name)}.{len(persons) + 1}@mail.example",
            employer=None if minor else (overrides.get("employer") or fake.company()),
            school=(overrides.get("school") or f"{municipality} school") if minor else None,
            household_id=household["id"],
            moved_in_date=moved_in,
        )
        persons.append(person)
        return person

    for authored in spec.get("people", []):
        person = add_person(
            authored["full_name"],
            authored["date_of_birth"],
            households[authored["household"]],
            authored["moved_in_date"],
            authored,
        )
        aliases[authored["alias"]] = person.person_id

    filler = spec.get("filler", {})
    filler_total = int(filler.get("persons", 0))
    filler_postcodes = filler.get("postcodes") or sorted(postcodes)
    next_household = len(households) + 1
    created = 0
    while created < filler_total:
        size = min(rng.choice([1, 1, 2, 2, 3, 4]), filler_total - created)
        postcode = rng.choice(filler_postcodes)
        address = fake.street_address()
        while address in used_addresses:
            address = fake.street_address()
        used_addresses.add(address)
        household = {"id": f"H-{next_household:04d}", "street_address": address, "postcode": postcode}
        next_household += 1
        last_name = fake.last_name()
        moved_in = _random_date(rng, as_of - timedelta(days=15 * 365), as_of).isoformat()
        for member in range(size):
            if member < 2:
                dob = _random_date(rng, date(1945, 1, 1), date(2002, 12, 31))
            else:
                dob = _random_date(rng, date(2008, 1, 1), date(2020, 12, 31))
            full_name = f"{fake.first_name()} {last_name}"
            while (name_key(full_name), dob.isoformat()) in used_keys:
                full_name = f"{fake.first_name()} {last_name}"
            add_person(full_name, dob.isoformat(), household, moved_in, {})
            created += 1

    by_id = {p.person_id: p for p in persons}

    initial_sno = {aliases[a] for a in spec.get("sno", [])}

    requesters: list[Requester] = []
    for index, raw in enumerate(spec.get("requesters", []), start=1):
        if raw["type"] not in REQUESTER_TYPES:
            raise ValueError(f"unknown requester type {raw['type']}")
        rid = f"Q-{index:04d}"
        claimed_name = raw.get("claimed_name")
        claimed_dob = raw.get("claimed_dob")
        if raw.get("claims"):
            claimed = by_id[aliases[raw["claims"]]]
            claimed_name, claimed_dob = claimed.full_name, claimed.date_of_birth
        true_person = aliases[raw["true_person"]] if raw.get("true_person") else None
        requesters.append(
            Requester(
                requester_id=rid,
                type=raw["type"],
                organization=raw["organization"],
                claimed_name=claimed_name,
                claimed_dob=claimed_dob,
                claimed_staff_id=raw.get("claimed_staff_id"),
                true_person_id=true_person,
                true_staff_id=raw.get("true_staff_id"),
                identity_ok=bool(raw.get("identity_ok", True)),
            )
        )
        aliases[raw["alias"]] = rid

    cases = [
        Case(
            case_id=raw["case_id"],
            organization=raw["organization"],
            subject_person_id=aliases[raw["subject"]],
            officer_ids=set(raw.get("officers", [])),
            status=raw.get("status", "OPEN"),
        )
        for raw in spec.get("cases", [])
    ]

    requests: list[Request] = []
    for position, raw in enumerate(spec.get("requests", []), start=1):
        if raw["kind"] not in {k.value for k in Kind}:
            raise ValueError(f"unknown request kind {raw['kind']}")
        subject = None
        if raw.get("subject"):
            target = by_id[aliases[raw["subject"]]]
            subject = {"full_name": target.full_name, "date_of_birth": target.date_of_birth}
        elif raw.get("subject_literal"):
            subject = dict(raw["subject_literal"])
        requests.append(
            Request(
                request_id=raw.get("id") or f"R-{position:03d}",
                position=position,
                requester_id=aliases[raw["requester"]],
                kind=raw["kind"],
                requested_fields=tuple(raw.get("requested_fields", [])),
                text=raw.get("text", ""),
                subject=subject,
                case_id=raw.get("case_id"),
                postcode=raw.get("postcode"),
                filter=raw.get("filter"),
                labels=dict(raw.get("labels", {})),
            )
        )

    events: list[ScheduledEvent] = []
    for index, raw in enumerate(spec.get("events", []), start=1):
        if raw["type"] not in EVENT_TYPES:
            raise ValueError(f"unknown event type {raw['type']}")
        events.append(
            ScheduledEvent(
                event_id=f"E-{index:03d}",
                after=int(raw["after"]),
                type=raw["type"],
                person_id=aliases[raw["person"]] if raw.get("person") else None,
                case_id=raw.get("case_id"),
                staff_id=raw.get("staff_id"),
            )
        )

    world = World(
        name=spec["name"],
        seed=seed,
        as_of=as_of,
        postcodes=postcodes,
        persons=persons,
        initial_sno=initial_sno,
        requesters=requesters,
        cases=cases,
        requests=requests,
        events=events,
        aliases=aliases,
    )
    problems = lint_world(world)
    if problems:
        raise ValueError("scenario lint failed: " + "; ".join(problems))
    return world


def lint_world(world: World) -> list[str]:
    problems: list[str] = []
    by_id = {p.person_id: p for p in world.persons}
    keys = [(name_key(p.full_name), p.date_of_birth) for p in world.persons]
    if len(keys) != len(set(keys)):
        problems.append("G1: duplicate (name, date of birth)")

    ever_protected = set(world.initial_sno) | {
        e.person_id for e in world.events if e.type == "sno_activated" and e.person_id
    }
    protected_households = {by_id[p].household_id for p in ever_protected}
    for household_id in protected_households:
        members = [p for p in world.persons if p.household_id == household_id]
        address = members[0].street_address
        outsiders = [
            p.person_id
            for p in world.persons
            if p.household_id != household_id and p.street_address == address
        ]
        if outsiders:
            problems.append(f"G2: protected household {household_id} shares its address")

    requester_ids = {r.requester_id for r in world.requesters}
    case_ids = {c.case_id for c in world.cases}
    for req in world.requests:
        if req.requester_id not in requester_ids:
            problems.append(f"G3: {req.request_id} has an unknown requester")
        if req.case_id and req.case_id not in case_ids and not req.labels.get("unknown_case"):
            problems.append(f"G3: {req.request_id} has an unknown case")
        if req.subject and not req.labels.get("expect_not_found"):
            key = (name_key(req.subject["full_name"]), req.subject["date_of_birth"])
            if key not in set(keys):
                problems.append(f"G3: {req.request_id} subject does not resolve")
    ids = [r.request_id for r in world.requests]
    if len(ids) != len(set(ids)):
        problems.append("duplicate request ids")
    for event in world.events:
        if event.type == "sno_activated" and event.person_id not in by_id:
            problems.append(f"{event.event_id}: unknown person")
        if event.type in ("case_closed", "officer_reassigned") and event.case_id not in case_ids:
            problems.append(f"{event.event_id}: unknown case")
    return problems
