"""Difficulty knobs (SPEC §7): defaults are the constants, a JSON file overrides any of them.

The hospital server and collect.py both build the world from `load_config(ED72_CONFIG)`,
so the live episode and the verifier replay always agree.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import constants as c
from .rules.events_extra import EXTRA_EVENTS, default_extra_events
from .rules.layouts import DEFAULT_LAYOUT, load_layout

_EVENT_FIELDS = ("window", "duration", "warning")


def _default_events() -> dict[str, dict[str, Any]]:
    core = {
        kind: {"window": tuple(spec["window"]), "duration": spec["duration"], "warning": spec["warning"]}
        for kind, spec in c.EVENTS.items()
    }
    return core | default_extra_events()


@dataclass(frozen=True)
class Config:
    arrival_mean: float = c.ARRIVAL_MEAN
    arrival_amplitude: float = c.ARRIVAL_AMPLITUDE
    arrival_peak_hour: float = c.ARRIVAL_PEAK_HOUR
    flu_mix: dict[int, float] = field(default_factory=lambda: dict(c.FLU_MIX))
    bus_mix: dict[int, float] = field(default_factory=lambda: dict(c.BUS_MIX))
    events: dict[str, dict[str, Any]] = field(default_factory=_default_events)
    budget: float = c.BUDGET
    hard_limit: float = c.HARD_LIMIT
    layout: str = DEFAULT_LAYOUT


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def _number(name: str, value: object) -> float:
    if not _is_number(value):
        raise ValueError(f"{name} must be a number, got {value!r}")
    return value  # type: ignore[return-value]


def _mix(name: str, raw: object) -> dict[int, float]:
    if not isinstance(raw, dict):
        raise ValueError(f"{name} must be an object of ESI -> weight")  # noqa: TRY004
    mix = {}
    for key, weight in raw.items():
        if not (isinstance(key, str) and key.isdigit() and int(key) in c.ESI_LEVELS):
            raise ValueError(f"{name}: unknown ESI level {key!r}")
        mix[int(key)] = _number(f"{name}[{key}]", weight)
    if any(w < 0 for w in mix.values()) or abs(sum(mix.values()) - 1) > 1e-9:
        raise ValueError(f"{name} weights must be >= 0 and sum to 1, got {mix}")
    return mix


def _event(kind: str, raw: object, base: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError(f"events.{kind} must be an object")  # noqa: TRY004
    allowed = (*_EVENT_FIELDS, "enabled") if kind in EXTRA_EVENTS else _EVENT_FIELDS
    unknown = set(raw) - set(allowed)
    if unknown:
        raise ValueError(f"events.{kind}: unknown key(s) {sorted(unknown)}")
    spec = dict(base)
    if "window" in raw:
        window = raw["window"]
        if not (isinstance(window, list) and len(window) == 2 and all(_is_int(v) for v in window)):
            raise ValueError(f"events.{kind}.window must be [lo, hi] integers")
        lo, hi = window
        if not (0 <= lo <= hi < c.TICKS):
            raise ValueError(f"events.{kind}.window {window} must satisfy 0 <= lo <= hi <= {c.TICKS - 1}")
        spec["window"] = (lo, hi)
    for key, minimum in (("duration", 1), ("warning", 0)):
        if key in raw:
            if not _is_int(raw[key]) or raw[key] < minimum:
                raise ValueError(f"events.{kind}.{key} must be an integer >= {minimum}")
            spec[key] = raw[key]
    if "enabled" in raw:
        if not isinstance(raw["enabled"], bool):
            raise ValueError(f"events.{kind}.enabled must be true or false")
        spec["enabled"] = raw["enabled"]
    return spec


def load_config(path: str | None) -> Config:
    """None gives the defaults; a file overrides only the keys it names. Invalid input raises ValueError."""
    if path is None:
        return Config()
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("config must be a JSON object")  # noqa: TRY004
    unknown = set(raw) - set(Config.__dataclass_fields__)
    if unknown:
        raise ValueError(f"unknown config key(s) {sorted(unknown)}")
    default = Config()
    values: dict[str, Any] = {}
    for name in ("arrival_mean", "arrival_amplitude", "arrival_peak_hour", "budget", "hard_limit"):
        if name in raw:
            values[name] = _number(name, raw[name])
    if "flu_mix" in raw:
        values["flu_mix"] = _mix("flu_mix", raw["flu_mix"])
    if "bus_mix" in raw:
        values["bus_mix"] = _mix("bus_mix", raw["bus_mix"])
    if "events" in raw:
        if not isinstance(raw["events"], dict):
            raise ValueError("events must be an object")
        events = default.events
        for kind, spec in raw["events"].items():
            if kind not in events:
                raise ValueError(f"unknown event kind {kind!r}")
            events[kind] = _event(kind, spec, events[kind])
        values["events"] = events
    if "layout" in raw:
        load_layout(raw["layout"])
        values["layout"] = raw["layout"]
    config = Config(**values)
    if config.arrival_mean < 0:
        raise ValueError("arrival_mean must be >= 0")
    # Above 1 the daily cycle gives negative off-peak arrival rates, and generate_world would fail.
    if not 0 <= config.arrival_amplitude <= 1:
        raise ValueError("arrival_amplitude must be in [0, 1]")
    # The budget score divides by hard_limit - budget, so the range must not be empty.
    if config.budget <= 0 or config.hard_limit <= config.budget:
        raise ValueError("need 0 < budget < hard_limit")
    return config
