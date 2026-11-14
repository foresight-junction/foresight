from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
from enum import StrEnum
from typing import Any


class Kind(StrEnum):
    LOOKUP = "lookup"
    AUTHORITY = "authority"
    DATA_SUBJECT = "data_subject"
    BULK = "bulk"
    STATISTICS = "statistics"


class Action(StrEnum):
    RELEASE = "RELEASE"
    DENY = "DENY"
    FORWARD = "FORWARD"


RELEASABLE_FIELDS: tuple[str, ...] = (
    "full_name",
    "date_of_birth",
    "street_address",
    "postcode",
    "municipality",
    "phone",
    "email",
    "employer",
    "school",
)

LRF: frozenset[str] = frozenset(
    {"street_address", "postcode", "municipality", "phone", "email", "employer", "school"}
)

ALLOWED_FIELDS: dict[str, frozenset[str]] = {
    "bank": frozenset({"full_name", "date_of_birth", "street_address", "postcode", "municipality"}),
    "courier": frozenset({"full_name", "street_address", "postcode", "phone"}),
    "private_person": frozenset({"full_name", "municipality"}),
    "marketing": frozenset({"full_name", "street_address", "postcode"}),
}

LOOKUP_TYPES = frozenset({"bank", "courier", "private_person"})
AUTHORITY_TYPES = frozenset({"police", "social_services", "court"})
STATISTICS_TYPES = frozenset({"research", "media"})
REQUESTER_TYPES = frozenset(LOOKUP_TYPES | AUTHORITY_TYPES | STATISTICS_TYPES | {"marketing", "data_subject"})

STAT_DIMENSIONS: tuple[str, ...] = ("municipality", "postcode", "age_band", "moved_in_last_12m")
AGE_BANDS: tuple[str, ...] = tuple(f"{d}-{d + 9}" for d in range(0, 80, 10)) + ("80+",)


def age_on(dob: str, as_of: date) -> int:
    born = date.fromisoformat(dob)
    return as_of.year - born.year - ((as_of.month, as_of.day) < (born.month, born.day))


def age_band(dob: str, as_of: date) -> str:
    age = age_on(dob, as_of)
    if age >= 80:
        return "80+"
    low = (age // 10) * 10
    return f"{low}-{low + 9}"


def moved_in_last_12m(moved_in: str, as_of: date) -> bool:
    moved = date.fromisoformat(moved_in)
    try:
        year_ago = as_of.replace(year=as_of.year - 1)
    except ValueError:
        year_ago = as_of.replace(year=as_of.year - 1, day=28)
    return year_ago < moved <= as_of


@dataclass(frozen=True)
class Person:
    person_id: str
    full_name: str
    date_of_birth: str
    street_address: str
    postcode: str
    municipality: str
    phone: str
    email: str
    employer: str | None
    school: str | None
    household_id: str
    moved_in_date: str

    def record(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Requester:
    requester_id: str
    type: str
    organization: str
    claimed_name: str | None
    claimed_dob: str | None
    claimed_staff_id: str | None
    true_person_id: str | None
    true_staff_id: str | None
    identity_ok: bool

    def public(self) -> dict[str, Any]:
        return {
            "requester_id": self.requester_id,
            "type": self.type,
            "organization": self.organization,
            "claimed_name": self.claimed_name,
            "claimed_dob": self.claimed_dob,
            "claimed_staff_id": self.claimed_staff_id,
        }


@dataclass
class Case:
    case_id: str
    organization: str
    subject_person_id: str
    officer_ids: set[str]
    status: str


@dataclass(frozen=True)
class Request:
    request_id: str
    position: int
    requester_id: str
    kind: str
    requested_fields: tuple[str, ...]
    text: str
    subject: dict[str, str] | None = None
    case_id: str | None = None
    postcode: str | None = None
    filter: dict[str, Any] | None = None
    labels: dict[str, Any] = field(default_factory=dict)

    def public(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "request_id": self.request_id,
            "requester_id": self.requester_id,
            "kind": self.kind,
            "text": self.text,
        }
        if self.kind in (Kind.LOOKUP, Kind.AUTHORITY):
            out["subject"] = dict(self.subject or {})
        if self.kind == Kind.AUTHORITY:
            out["case_id"] = self.case_id
        if self.kind == Kind.BULK:
            out["postcode"] = self.postcode
        if self.kind == Kind.STATISTICS:
            out["filter"] = dict(self.filter or {})
        else:
            out["requested_fields"] = list(self.requested_fields)
        return out


@dataclass(frozen=True)
class ScheduledEvent:
    event_id: str
    after: int
    type: str
    person_id: str | None = None
    case_id: str | None = None
    staff_id: str | None = None


ERROR_MESSAGES: dict[str, str] = {
    "INVALID_ARGUMENT": "Argument '{arg}' is invalid.",
    "INVALID_FIELD": "Argument '{arg}' contains an unknown field name.",
    "NOT_FOUND": "No matching {arg} was found.",
    "NO_ACTIVE_REQUEST": "There is no pulled request to respond to. Call next_request first.",
    "REQUEST_NOT_CURRENT": "Only the current request can be answered.",
    "ALREADY_ANSWERED": "This request has already been answered.",
    "INVALID_ACTION_FOR_KIND": "This action is not valid for this request kind.",
    "EPISODE_FINISHED": "The shift has ended.",
    "INTERNAL": "Internal error.",
}


class UFError(Exception):
    def __init__(self, code: str, arg: str | None = None) -> None:
        if code not in ERROR_MESSAGES:
            raise ValueError(f"unknown error code {code}")
        self.code = code
        self.arg = arg
        super().__init__(code)

    def payload(self) -> dict[str, Any]:
        message = ERROR_MESSAGES[self.code].format(arg=self.arg or "value")
        return {"error": {"code": self.code, "message": message}}
