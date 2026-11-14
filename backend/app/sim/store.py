from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from app.sim.domain import Case, Person, Requester, age_band, moved_in_last_12m
from app.sim.policy import StatRelease, name_key
from app.sim.scenario import World

SCHEMA = """
CREATE TABLE postcodes (postcode TEXT PRIMARY KEY, municipality TEXT NOT NULL);
CREATE TABLE persons (
    person_id TEXT PRIMARY KEY, full_name TEXT NOT NULL, name_key TEXT NOT NULL,
    date_of_birth TEXT NOT NULL, street_address TEXT NOT NULL, postcode TEXT NOT NULL,
    municipality TEXT NOT NULL, phone TEXT NOT NULL, email TEXT NOT NULL, employer TEXT,
    school TEXT, household_id TEXT NOT NULL, moved_in_date TEXT NOT NULL
);
CREATE INDEX ix_persons_lookup ON persons(name_key, date_of_birth);
CREATE INDEX ix_persons_postcode ON persons(postcode);
CREATE INDEX ix_persons_household ON persons(household_id);
CREATE TABLE sno (person_id TEXT PRIMARY KEY, status TEXT NOT NULL);
CREATE TABLE requesters (
    requester_id TEXT PRIMARY KEY, type TEXT NOT NULL, organization TEXT NOT NULL,
    claimed_name TEXT, claimed_dob TEXT, claimed_staff_id TEXT,
    true_person_id TEXT, true_staff_id TEXT, identity_ok INTEGER NOT NULL
);
CREATE TABLE cases (
    case_id TEXT PRIMARY KEY, organization TEXT NOT NULL,
    subject_person_id TEXT NOT NULL, status TEXT NOT NULL
);
CREATE TABLE case_officers (case_id TEXT NOT NULL, staff_id TEXT NOT NULL,
    PRIMARY KEY (case_id, staff_id));
CREATE TABLE responses (
    response_index INTEGER PRIMARY KEY, request_id TEXT NOT NULL UNIQUE, action TEXT NOT NULL,
    person_id TEXT, fields TEXT NOT NULL, person_ids TEXT NOT NULL
);
CREATE TABLE release_log (
    response_index INTEGER PRIMARY KEY, request_id TEXT NOT NULL, organization TEXT NOT NULL,
    kind TEXT NOT NULL, person_ids TEXT NOT NULL, fields TEXT NOT NULL, filter TEXT, count INTEGER
);
CREATE TABLE ledger (
    response_index INTEGER PRIMARY KEY, request_id TEXT NOT NULL, truth TEXT NOT NULL,
    assessment TEXT NOT NULL, population TEXT NOT NULL
);
"""


class Store:
    """SQLite-backed state. Implements policy.StateView. The ledger table and the
    requesters' hidden columns are evaluator-only and never reach a tool result."""

    def __init__(self, world: World, path: str = ":memory:") -> None:
        self.as_of = world.as_of
        self.conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self._requesters = {r.requester_id: r for r in world.requesters}
        self._load(world)

    def _load(self, world: World) -> None:
        with self.transaction():
            self.conn.executemany("INSERT INTO postcodes VALUES (?, ?)", sorted(world.postcodes.items()))
            self.conn.executemany(
                "INSERT INTO persons VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                [
                    (
                        p.person_id,
                        p.full_name,
                        name_key(p.full_name),
                        p.date_of_birth,
                        p.street_address,
                        p.postcode,
                        p.municipality,
                        p.phone,
                        p.email,
                        p.employer,
                        p.school,
                        p.household_id,
                        p.moved_in_date,
                    )
                    for p in world.persons
                ],
            )
            self.conn.executemany(
                "INSERT INTO sno VALUES (?, 'ACTIVE')", [(pid,) for pid in sorted(world.initial_sno)]
            )
            self.conn.executemany(
                "INSERT INTO requesters VALUES (?,?,?,?,?,?,?,?,?)",
                [
                    (
                        r.requester_id,
                        r.type,
                        r.organization,
                        r.claimed_name,
                        r.claimed_dob,
                        r.claimed_staff_id,
                        r.true_person_id,
                        r.true_staff_id,
                        int(r.identity_ok),
                    )
                    for r in world.requesters
                ],
            )
            for case in world.cases:
                self.conn.execute(
                    "INSERT INTO cases VALUES (?,?,?,?)",
                    (case.case_id, case.organization, case.subject_person_id, case.status),
                )
                self.conn.executemany(
                    "INSERT INTO case_officers VALUES (?, ?)",
                    [(case.case_id, s) for s in sorted(case.officer_ids)],
                )

    @contextmanager
    def transaction(self) -> Iterator[None]:
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            yield
        except BaseException:
            self.conn.execute("ROLLBACK")
            raise
        self.conn.execute("COMMIT")

    @staticmethod
    def _person(row: sqlite3.Row | None) -> Person | None:
        if row is None:
            return None
        data = dict(row)
        data.pop("name_key")
        return Person(**data)

    def person(self, person_id: str) -> Person | None:
        row = self.conn.execute("SELECT * FROM persons WHERE person_id = ?", (person_id,)).fetchone()
        return self._person(row)

    def find_person(self, full_name: str, date_of_birth: str) -> str | None:
        row = self.conn.execute(
            "SELECT person_id FROM persons WHERE name_key = ? AND date_of_birth = ?",
            (name_key(full_name), date_of_birth),
        ).fetchone()
        return row["person_id"] if row else None

    def household_members(self, person_id: str) -> list[str]:
        rows = self.conn.execute(
            "SELECT person_id FROM persons WHERE household_id = "
            "(SELECT household_id FROM persons WHERE person_id = ?) ORDER BY person_id",
            (person_id,),
        ).fetchall()
        return [r["person_id"] for r in rows]

    def household_id(self, person_id: str) -> str | None:
        row = self.conn.execute(
            "SELECT household_id FROM persons WHERE person_id = ?", (person_id,)
        ).fetchone()
        return row["household_id"] if row else None

    def sno_active(self, person_id: str) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM sno WHERE person_id = ? AND status = 'ACTIVE'", (person_id,)
        ).fetchone()
        return row is not None

    def requester(self, requester_id: str) -> Requester | None:
        return self._requesters.get(requester_id)

    def case(self, case_id: str) -> Case | None:
        row = self.conn.execute("SELECT * FROM cases WHERE case_id = ?", (case_id,)).fetchone()
        if row is None:
            return None
        officers = self.conn.execute(
            "SELECT staff_id FROM case_officers WHERE case_id = ?", (case_id,)
        ).fetchall()
        return Case(
            case_id=row["case_id"],
            organization=row["organization"],
            subject_person_id=row["subject_person_id"],
            officer_ids={o["staff_id"] for o in officers},
            status=row["status"],
        )

    def residents(self, postcode: str) -> list[str]:
        rows = self.conn.execute(
            "SELECT person_id FROM persons WHERE postcode = ? ORDER BY person_id", (postcode,)
        ).fetchall()
        return [r["person_id"] for r in rows]

    def municipality_of_postcode(self, postcode: str) -> str | None:
        row = self.conn.execute(
            "SELECT municipality FROM postcodes WHERE postcode = ?", (postcode,)
        ).fetchone()
        return row["municipality"] if row else None

    def population(self, canonical: tuple[tuple[str, Any], ...]) -> frozenset[str]:
        criteria = dict(canonical)
        sql = "SELECT person_id, date_of_birth, moved_in_date FROM persons WHERE 1 = 1"
        params: list[Any] = []
        if "postcode" in criteria:
            sql += " AND postcode = ?"
            params.append(criteria["postcode"])
        if "municipality" in criteria:
            sql += " AND lower(municipality) = lower(?)"
            params.append(criteria["municipality"])
        members = set()
        for row in self.conn.execute(sql, params).fetchall():
            if "age_band" in criteria and age_band(row["date_of_birth"], self.as_of) != criteria["age_band"]:
                continue
            if "moved_in_last_12m" in criteria and (
                moved_in_last_12m(row["moved_in_date"], self.as_of) != criteria["moved_in_last_12m"]
            ):
                continue
            members.add(row["person_id"])
        return frozenset(members)

    def activate_sno(self, person_id: str) -> None:
        self.conn.execute(
            "INSERT INTO sno VALUES (?, 'ACTIVE') ON CONFLICT(person_id) DO UPDATE SET status = 'ACTIVE'",
            (person_id,),
        )

    def close_case(self, case_id: str) -> None:
        self.conn.execute("UPDATE cases SET status = 'CLOSED' WHERE case_id = ?", (case_id,))

    def remove_officer(self, case_id: str, staff_id: str) -> None:
        self.conn.execute("DELETE FROM case_officers WHERE case_id = ? AND staff_id = ?", (case_id, staff_id))

    def insert_response(
        self,
        index: int,
        request_id: str,
        action: str,
        person_id: str | None,
        fields: list[str],
        person_ids: list[str],
    ) -> None:
        self.conn.execute(
            "INSERT INTO responses VALUES (?,?,?,?,?,?)",
            (index, request_id, action, person_id, json.dumps(fields), json.dumps(person_ids)),
        )

    def insert_release(
        self,
        index: int,
        request_id: str,
        organization: str,
        kind: str,
        person_ids: list[str],
        fields: list[str],
        canonical: tuple[tuple[str, Any], ...] | None,
        count: int | None,
    ) -> None:
        self.conn.execute(
            "INSERT INTO release_log VALUES (?,?,?,?,?,?,?,?)",
            (
                index,
                request_id,
                organization,
                kind,
                json.dumps(person_ids),
                json.dumps(fields),
                json.dumps(dict(canonical)) if canonical is not None else None,
                count,
            ),
        )

    def insert_ledger(
        self,
        index: int,
        request_id: str,
        truth: dict[str, Any],
        assessment: dict[str, Any],
        population: list[str],
    ) -> None:
        self.conn.execute(
            "INSERT INTO ledger VALUES (?,?,?,?,?)",
            (index, request_id, json.dumps(truth), json.dumps(assessment), json.dumps(population)),
        )

    def release_entries(self, organization: str | None = None) -> list[dict[str, Any]]:
        sql = "SELECT * FROM release_log"
        params: list[Any] = []
        if organization is not None:
            sql += " WHERE organization = ?"
            params.append(organization)
        sql += " ORDER BY response_index"
        entries = []
        for row in self.conn.execute(sql, params).fetchall():
            entries.append(
                {
                    "response_index": row["response_index"],
                    "request_id": row["request_id"],
                    "organization": row["organization"],
                    "kind": row["kind"],
                    "person_ids": json.loads(row["person_ids"]),
                    "fields": json.loads(row["fields"]),
                    "filter": json.loads(row["filter"]) if row["filter"] else None,
                    "count": row["count"],
                }
            )
        return entries

    def stat_history(self) -> list[StatRelease]:
        rows = self.conn.execute(
            "SELECT r.organization, r.filter, r.count, l.population FROM release_log r "
            "JOIN ledger l ON l.response_index = r.response_index "
            "WHERE r.kind = 'statistics' ORDER BY r.response_index"
        ).fetchall()
        return [
            StatRelease(
                organization=row["organization"],
                filter=tuple(sorted(json.loads(row["filter"]).items())),
                count=row["count"],
                population=frozenset(json.loads(row["population"])),
            )
            for row in rows
        ]
