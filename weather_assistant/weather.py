"""Weather provider — talks to the Open-Meteo public API.

We use Open-Meteo (https://open-meteo.com) deliberately: it is free and needs
**no API key**, so a peer reviewer can clone the repo and run it immediately
with nothing to configure.

Design note — the "humble object" pattern:
  * ``_http_get_json`` is the *only* function that touches the network.
  * ``categorize`` and the ``parse_*`` functions are pure: raw JSON in, model
    objects out. They are exhaustively unit-tested with fixtures and never make
    a request.
This keeps the untestable part (the network) tiny and the testable part (the
logic) large.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from .models import WeatherCategory, WeatherSnapshot

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# WMO weather interpretation codes -> (bucket, human description).
# Reference: https://open-meteo.com/en/docs (WMO Weather interpretation codes).
WMO_CODE_MAP: Dict[int, Tuple[WeatherCategory, str]] = {
    0: (WeatherCategory.CLEAR, "Clear sky"),
    1: (WeatherCategory.CLEAR, "Mainly clear"),
    2: (WeatherCategory.CLOUDY, "Partly cloudy"),
    3: (WeatherCategory.CLOUDY, "Overcast"),
    45: (WeatherCategory.FOG, "Fog"),
    48: (WeatherCategory.FOG, "Depositing rime fog"),
    51: (WeatherCategory.DRIZZLE, "Light drizzle"),
    53: (WeatherCategory.DRIZZLE, "Moderate drizzle"),
    55: (WeatherCategory.DRIZZLE, "Dense drizzle"),
    56: (WeatherCategory.DRIZZLE, "Light freezing drizzle"),
    57: (WeatherCategory.DRIZZLE, "Dense freezing drizzle"),
    61: (WeatherCategory.RAIN, "Slight rain"),
    63: (WeatherCategory.RAIN, "Moderate rain"),
    65: (WeatherCategory.RAIN, "Heavy rain"),
    66: (WeatherCategory.RAIN, "Light freezing rain"),
    67: (WeatherCategory.RAIN, "Heavy freezing rain"),
    71: (WeatherCategory.SNOW, "Slight snowfall"),
    73: (WeatherCategory.SNOW, "Moderate snowfall"),
    75: (WeatherCategory.SNOW, "Heavy snowfall"),
    77: (WeatherCategory.SNOW, "Snow grains"),
    80: (WeatherCategory.RAIN, "Slight rain showers"),
    81: (WeatherCategory.RAIN, "Moderate rain showers"),
    82: (WeatherCategory.RAIN, "Violent rain showers"),
    85: (WeatherCategory.SNOW, "Slight snow showers"),
    86: (WeatherCategory.SNOW, "Heavy snow showers"),
    95: (WeatherCategory.THUNDERSTORM, "Thunderstorm"),
    96: (WeatherCategory.THUNDERSTORM, "Thunderstorm with slight hail"),
    99: (WeatherCategory.THUNDERSTORM, "Thunderstorm with heavy hail"),
}


class WeatherUnavailable(Exception):
    """Raised when weather data cannot be fetched or understood.

    Callers are expected to catch this and degrade gracefully — the assistant
    should still show the schedule even when it is offline.
    """


def categorize(code: int) -> Tuple[WeatherCategory, str]:
    """Map a raw WMO code to a (category, description) pair. Pure."""
    return WMO_CODE_MAP.get(code, (WeatherCategory.UNKNOWN, f"Unknown (code {code})"))


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _http_get_json(url: str, params: Dict[str, Any], timeout: float) -> Dict[str, Any]:
    """The single point of network contact. Everything else is pure.

    Raises:
        WeatherUnavailable: on any network, HTTP, or decoding failure.
    """
    query = urllib.parse.urlencode(params)
    full_url = f"{url}?{query}"
    request = urllib.request.Request(full_url, headers={"User-Agent": "weather-assistant/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = response.read().decode("utf-8")
        return json.loads(payload)
    except (urllib.error.URLError, urllib.error.HTTPError) as exc:
        raise WeatherUnavailable(f"Could not reach the weather service: {exc}") from exc
    except (json.JSONDecodeError, ValueError) as exc:
        raise WeatherUnavailable(f"Weather service returned bad data: {exc}") from exc


def parse_current(raw: Dict[str, Any], location: str) -> WeatherSnapshot:
    """Turn an Open-Meteo forecast payload's ``current`` block into a snapshot. Pure."""
    current = raw.get("current")
    if not isinstance(current, dict):
        raise WeatherUnavailable("Weather response had no 'current' block.")
    code = int(current.get("weather_code", -1))
    category, description = categorize(code)
    return WeatherSnapshot(
        location=location,
        time=_parse_iso(current.get("time")),
        temperature_c=float(current.get("temperature_2m", 0.0)),
        apparent_temperature_c=_optional_float(current.get("apparent_temperature")),
        precipitation_mm=float(current.get("precipitation", 0.0) or 0.0),
        precipitation_probability=_optional_int(current.get("precipitation_probability")),
        wind_speed_kmh=float(current.get("wind_speed_10m", 0.0) or 0.0),
        weather_code=code,
        category=category,
        description=description,
        is_day=bool(current.get("is_day", 1)),
    )


def parse_hourly(raw: Dict[str, Any], location: str) -> List[WeatherSnapshot]:
    """Turn an Open-Meteo ``hourly`` block into a list of snapshots. Pure.

    Open-Meteo returns parallel arrays (``time[]``, ``temperature_2m[]``, ...);
    we zip them back into per-hour records.
    """
    hourly = raw.get("hourly")
    if not isinstance(hourly, dict):
        raise WeatherUnavailable("Weather response had no 'hourly' block.")
    times = hourly.get("time") or []
    temps = hourly.get("temperature_2m") or []
    feels = hourly.get("apparent_temperature") or []
    precip = hourly.get("precipitation") or []
    probs = hourly.get("precipitation_probability") or []
    winds = hourly.get("wind_speed_10m") or []
    codes = hourly.get("weather_code") or []
    is_day = hourly.get("is_day") or []

    snapshots: List[WeatherSnapshot] = []
    for i, stamp in enumerate(times):
        code = int(_at(codes, i, -1))
        category, description = categorize(code)
        snapshots.append(
            WeatherSnapshot(
                location=location,
                time=_parse_iso(stamp),
                temperature_c=float(_at(temps, i, 0.0)),
                apparent_temperature_c=_optional_float(_at(feels, i, None)),
                precipitation_mm=float(_at(precip, i, 0.0) or 0.0),
                precipitation_probability=_optional_int(_at(probs, i, None)),
                wind_speed_kmh=float(_at(winds, i, 0.0) or 0.0),
                weather_code=code,
                category=category,
                description=description,
                is_day=bool(_at(is_day, i, 1)),
            )
        )
    return snapshots


def _at(seq: List[Any], index: int, default: Any) -> Any:
    return seq[index] if index < len(seq) else default


def _optional_float(value: Any) -> Optional[float]:
    return None if value is None else float(value)


def _optional_int(value: Any) -> Optional[int]:
    return None if value is None else int(value)


class OpenMeteoClient:
    """A thin client that geocodes a place name and fetches its weather.

    Network calls are delegated to :func:`_http_get_json`; this class only
    assembles parameters and hands the raw JSON to the pure parsers.
    """

    def __init__(self, timeout_s: float = 10.0) -> None:
        self.timeout_s = timeout_s

    def geocode(self, location: str) -> Tuple[float, float, str]:
        """Resolve a place name to (latitude, longitude, resolved label)."""
        data = _http_get_json(
            GEOCODE_URL,
            {"name": location, "count": 1, "language": "en", "format": "json"},
            self.timeout_s,
        )
        results = data.get("results") or []
        if not results:
            raise WeatherUnavailable(f"Could not find a place called '{location}'.")
        top = results[0]
        label_parts = [top.get("name"), top.get("admin1"), top.get("country")]
        label = ", ".join(p for p in label_parts if p)
        return float(top["latitude"]), float(top["longitude"]), label

    def current(self, location: str) -> WeatherSnapshot:
        """Current conditions for a named place."""
        lat, lon, label = self.geocode(location)
        raw = _http_get_json(
            FORECAST_URL,
            {
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,apparent_temperature,precipitation,"
                "weather_code,wind_speed_10m,is_day",
                "timezone": "auto",
            },
            self.timeout_s,
        )
        return parse_current(raw, label)

    def hourly_forecast(self, location: str, days: int = 3) -> List[WeatherSnapshot]:
        """An hourly forecast for the next ``days`` days at a named place."""
        lat, lon, label = self.geocode(location)
        raw = _http_get_json(
            FORECAST_URL,
            {
                "latitude": lat,
                "longitude": lon,
                "hourly": "temperature_2m,apparent_temperature,precipitation,"
                "precipitation_probability,weather_code,wind_speed_10m,is_day",
                "forecast_days": max(1, min(16, days)),
                "timezone": "auto",
            },
            self.timeout_s,
        )
        return parse_hourly(raw, label)
