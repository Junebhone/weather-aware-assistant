"""Configuration: the knobs that tune the assistant's behaviour.

Thresholds live here as *data*, not as magic numbers buried inside the advice
engine. That means the advice rules can be re-tuned for a different climate or
a different user without touching logic, and tests can construct custom
thresholds to exercise boundary conditions deterministically.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, replace
from typing import Tuple


@dataclass(frozen=True)
class Thresholds:
    """Numeric boundaries that turn raw weather into qualitative decisions.

    All temperatures are in degrees Celsius and wind in km/h, matching the
    Open-Meteo defaults we request.
    """

    freezing_c: float = 1.0       # at/below: risk of ice
    cold_c: float = 8.0           # at/below: bundle up
    chilly_c: float = 14.0        # at/below: a light layer helps
    warm_c: float = 24.0          # at/above: pleasantly warm
    hot_c: float = 30.0           # at/above: heat caution

    wet_precip_mm: float = 0.2    # at/above (per hour): treat as actively wet
    rain_probability_pct: int = 50  # at/above: plan for rain even if dry now

    high_wind_kmh: float = 35.0   # at/above: blustery
    gale_wind_kmh: float = 55.0   # at/above: hazardous wind


# Words that, when they appear in an event title or location, mark the event as
# happening outdoors. Outdoor events get firmer weather advice (you cannot just
# stay inside through a downpour during a beach run).
DEFAULT_OUTDOOR_KEYWORDS: Tuple[str, ...] = (
    "run",
    "jog",
    "walk",
    "hike",
    "bike",
    "cycle",
    "cycling",
    "ride",
    "beach",
    "park",
    "picnic",
    "garden",
    "field",
    "trail",
    "outdoor",
    "market",
    "golf",
    "tennis",
    "soccer",
    "surf",
    "stadium",
    "patio",
)


@dataclass(frozen=True)
class AppConfig:
    """Top-level application configuration."""

    home_location: str = "Honolulu"
    forecast_days: int = 3
    request_timeout_s: float = 10.0
    units: str = "metric"
    thresholds: Thresholds = field(default_factory=Thresholds)
    outdoor_keywords: Tuple[str, ...] = DEFAULT_OUTDOOR_KEYWORDS

    @classmethod
    def from_env(cls) -> "AppConfig":
        """Build config, allowing a couple of overrides via environment vars.

        Keeps the demo zero-config while still letting a user point the
        assistant at their own city: ``WA_HOME_LOCATION=Berlin python run.py``.
        """
        cfg = cls()
        home = os.environ.get("WA_HOME_LOCATION")
        if home:
            cfg = replace(cfg, home_location=home.strip())
        days = os.environ.get("WA_FORECAST_DAYS")
        if days and days.isdigit():
            cfg = replace(cfg, forecast_days=max(1, min(16, int(days))))
        return cfg

    def with_home(self, location: str) -> "AppConfig":
        """Return a copy pointed at a new home location (used by the REPL)."""
        return replace(self, home_location=location.strip())
