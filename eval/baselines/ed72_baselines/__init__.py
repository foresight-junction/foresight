"""ED-72 scripted baselines over the public tools (issue #12, EVAL §5)."""

from collections.abc import Callable

from ed72_baselines.client import Client, Policy, run_episode
from ed72_baselines.exploits import (
    AdmitLightOnly,
    AdmitWithoutCoverage,
    DivertAll,
    FillBedsAtLastTick,
    RandomPolicy,
    RestInQuietPeriods,
    SpendToLimit,
)
from ed72_baselines.policies import DoNothing, ReactiveProxy, StopEarly

BUILT_IN: dict[str, Callable[[], Policy]] = {
    "reactive_proxy": ReactiveProxy,
    "stop_early": StopEarly,
    "do_nothing": DoNothing,
}

EXPLOITS: dict[str, Callable[[], Policy]] = {
    "divert_all": DivertAll,
    "rest_in_quiet_periods": RestInQuietPeriods,
    "admit_light_only": AdmitLightOnly,
    "admit_without_coverage": AdmitWithoutCoverage,
    "fill_beds_at_last_tick": FillBedsAtLastTick,
    "spend_to_limit": SpendToLimit,
    "random": RandomPolicy,
}

BASELINES: dict[str, Callable[[], Policy]] = BUILT_IN | EXPLOITS

__all__ = ["BASELINES", "BUILT_IN", "EXPLOITS", "Client", "Policy", "run_episode"]
