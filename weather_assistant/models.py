"""Pure data models for the Weather-Aware Personal Assistant.

This module is deliberately *dumb*: it contains only data structures and
trivial derived properties. There is no I/O, no printing, and no business
logic here. Every other module speaks in terms of these types, which keeps
the boundary between "what we know" (data) and "what we decide" (advisor)
crisp and testable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import List, Optional


class Severity(str, Enum):
    """How loudly a piece of advice should speak."""

    INFO = "info"
    CAUTION = "caution"
    WARNING = "warning"

    @property
    def rank(self) -> int:
        """Higher rank == more urgent. Used to pick a headline severity."""
        return {"info": 0, "caution": 1, "warning": 2}[self.value]


class WeatherCategory(str, Enum):
    """A coarse bucket for a weather condition.

    We collapse the ~30 WMO weather codes into a handful of buckets so the
    advice rules stay readable. The mapping lives in ``weather.py``.
    """

    CLEAR = "clear"
    CLOUDY = "cloudy"
    FOG = "fog"
    DRIZZLE = "drizzle"
    RAIN = "rain"
    SNOW = "snow"
    THUNDERSTORM = "thunderstorm"
    UNKNOWN = "unknown"

    @property
    def is_wet(self) -> bool:
        """True for conditions that put water (or ice) on the commute."""
        return self in {
            WeatherCategory.DRIZZLE,
            WeatherCategory.RAIN,
            WeatherCategory.SNOW,
            WeatherCategory.THUNDERSTORM,
        }


@dataclass(frozen=True)
class WeatherSnapshot:
    """The weather at a single place and (optionally) a single hour."""

    location: str
    temperature_c: float
    wind_speed_kmh: float
    precipitation_mm: float
    weather_code: int
    category: WeatherCategory
    description: str
    time: Optional[datetime] = None
    apparent_temperature_c: Optional[float] = None
    precipitation_probability: Optional[int] = None
    is_day: bool = True

    @property
    def is_wet(self) -> bool:
        """Whether you would get wet standing outside in this snapshot."""
        return self.category.is_wet or self.precipitation_mm > 0

    @property
    def feels_like_c(self) -> float:
        """Apparent temperature when known, otherwise the dry-bulb value."""
        return (
            self.apparent_temperature_c
            if self.apparent_temperature_c is not None
            else self.temperature_c
        )


@dataclass(frozen=True)
class Event:
    """A single calendar entry. Mirrors the schema of ``calendar.json``."""

    title: str
    start: datetime
    end: datetime
    location: str

    @property
    def duration_minutes(self) -> int:
        return max(0, int((self.end - self.start).total_seconds() // 60))


@dataclass(frozen=True)
class Advice:
    """One actionable suggestion produced by the advice engine.

    ``message`` is plain text on purpose — the engine never decides *how* the
    advice is displayed. Formatting (emoji, colour, layout) is the UI layer's
    job. ``icon`` is a presentation hint the UI may use or ignore.
    """

    category: str  # commute | clothing | health | safety | general
    severity: Severity
    message: str
    icon: str = ""


@dataclass
class EventBriefing:
    """An event paired with its weather and the advice that follows from it."""

    event: Event
    weather: Optional[WeatherSnapshot]
    advice: List[Advice] = field(default_factory=list)

    @property
    def weather_available(self) -> bool:
        return self.weather is not None

    @property
    def max_severity(self) -> Severity:
        if not self.advice:
            return Severity.INFO
        return max((a.severity for a in self.advice), key=lambda s: s.rank)


@dataclass
class DailyBriefing:
    """The synthesised result for a whole day: the assistant's headline output."""

    on_date: date
    location: str
    items: List[EventBriefing] = field(default_factory=list)
    general: List[Advice] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)  # e.g. "weather unavailable"

    @property
    def max_severity(self) -> Severity:
        severities = [item.max_severity for item in self.items]
        severities.extend(a.severity for a in self.general)
        if not severities:
            return Severity.INFO
        return max(severities, key=lambda s: s.rank)
