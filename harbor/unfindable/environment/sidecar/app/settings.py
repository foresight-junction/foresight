from __future__ import annotations

import os
from dataclasses import dataclass

from app.sim.episode import EpisodeService
from app.sim.observe import ObservationBus
from app.sim.policy import PROFILES
from app.sim.scenario import load_scenario


def _flag(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    scenario: str = "slice"
    seed: int | None = None
    profile: str = "v0.2"
    observe: bool = True
    live_reveal: bool = True
    spectator_token: str = ""
    verifier_token: str = ""
    cors_origins: tuple[str, ...] = ("http://localhost:5173", "http://127.0.0.1:5173")

    @classmethod
    def from_env(cls) -> Settings:
        seed = os.environ.get("UF_SEED")
        origins = os.environ.get("UF_CORS_ORIGINS")
        return cls(
            scenario=os.environ.get("UF_SCENARIO", cls.scenario),
            seed=int(seed) if seed else None,
            profile=os.environ.get("UF_PROFILE", cls.profile),
            observe=_flag("UF_OBSERVE", cls.observe),
            live_reveal=_flag("UF_LIVE_REVEAL", cls.live_reveal),
            spectator_token=os.environ.get("UF_SPECTATOR_TOKEN", cls.spectator_token),
            verifier_token=os.environ.get("UF_VERIFIER_TOKEN", cls.verifier_token),
            cors_origins=tuple(o.strip() for o in origins.split(",")) if origins else cls.cors_origins,
        )


class AppState:
    """Process-level holder: settings, the spectator bus and the current episode."""

    def __init__(self, settings: Settings) -> None:
        if settings.profile not in PROFILES:
            raise ValueError(f"unknown profile {settings.profile}")
        self.settings = settings
        self.bus = ObservationBus(enabled=settings.observe)
        self._counter = 0
        self.service = self._new_episode(settings.scenario, settings.seed, settings.profile)

    def _new_episode(self, scenario: str, seed: int | None, profile: str) -> EpisodeService:
        if profile not in PROFILES:
            raise ValueError(f"unknown profile {profile}")
        world = load_scenario(scenario, seed)
        self._counter += 1
        return EpisodeService(
            world,
            PROFILES[profile],
            bus=self.bus,
            live_reveal=self.settings.live_reveal,
            episode_id=f"ep-{scenario}-{self._counter:04d}",
        )

    def reset(
        self, scenario: str | None = None, seed: int | None = None, profile: str | None = None
    ) -> EpisodeService:
        self.service = self._new_episode(
            scenario or self.settings.scenario,
            seed if seed is not None else self.settings.seed,
            profile or self.settings.profile,
        )
        return self.service
