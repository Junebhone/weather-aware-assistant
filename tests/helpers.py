"""Small factories so tests can build domain objects in one readable line.

Tests should never need the network. These helpers fabricate ``Event`` and
``WeatherSnapshot`` objects directly, with sensible, mild defaults that
individual tests override to exercise one condition at a time.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from weather_assistant.models import Event, WeatherCategory, WeatherSnapshot


def make_event(
    title: str = "Meeting",
    location: str = "Downtown",
    start: str = "2026-06-20T09:00:00",
    end: str = "2026-06-20T10:00:00",
) -> Event:
    return Event(
        title=title,
        location=location,
        start=datetime.fromisoformat(start),
        end=datetime.fromisoformat(end),
    )


def make_weather(
    *,
    temperature_c: float = 20.0,
    wind_speed_kmh: float = 10.0,
    precipitation_mm: float = 0.0,
    precipitation_probability: Optional[int] = 0,
    weather_code: int = 0,
    category: WeatherCategory = WeatherCategory.CLEAR,
    description: str = "Clear sky",
    apparent_temperature_c: Optional[float] = None,
    is_day: bool = True,
    location: str = "Testville",
    time: Optional[str] = None,
) -> WeatherSnapshot:
    return WeatherSnapshot(
        location=location,
        temperature_c=temperature_c,
        wind_speed_kmh=wind_speed_kmh,
        precipitation_mm=precipitation_mm,
        precipitation_probability=precipitation_probability,
        weather_code=weather_code,
        category=category,
        description=description,
        apparent_temperature_c=apparent_temperature_c,
        is_day=is_day,
        time=datetime.fromisoformat(time) if time else None,
    )
