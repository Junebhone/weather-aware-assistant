"""The advice engine — the "brain" of the assistant.

This is the most important module in the project and the one the tests guard
most closely. It is *pure*:

    advise(event, weather, thresholds) -> List[Advice]

Data in, decisions out. There is no network here, no file access, and crucially
**no print statements**. The engine never decides how advice is shown; it only
decides what the advice *is*. That separation is what makes the rule
"if it's raining, suggest the bus" something we can assert in a unit test
rather than something we eyeball in the terminal.

The rules are organised by concern (commute, clothing, wind, positive) so each
can be read, reasoned about, and tested in isolation.
"""

from __future__ import annotations

from typing import List, Optional, Sequence

from .config import DEFAULT_OUTDOOR_KEYWORDS, Thresholds
from .models import Advice, Event, Severity, WeatherCategory, WeatherSnapshot


def is_outdoor_event(
    event: Event, keywords: Sequence[str] = DEFAULT_OUTDOOR_KEYWORDS
) -> bool:
    """Heuristic: does this event likely happen outdoors?

    We scan the title and location for tell-tale words. It is intentionally a
    heuristic — "Lunch at the park" counts as outdoor, "Lunch at Park Hotel"
    arguably should not, but erring toward caution is the safer default for a
    weather assistant.
    """
    haystack = f"{event.title} {event.location}".lower()
    return any(word in haystack for word in keywords)


def _is_wet_outlook(weather: WeatherSnapshot, thresholds: Thresholds) -> bool:
    """True if you should plan around precipitation, now or likely."""
    if weather.is_wet or weather.precipitation_mm >= thresholds.wet_precip_mm:
        return True
    prob = weather.precipitation_probability
    return prob is not None and prob >= thresholds.rain_probability_pct


def _commute_advice(
    weather: WeatherSnapshot, thresholds: Thresholds, outdoor: bool
) -> List[Advice]:
    """How to get there. This is where the canonical 'take the bus' rule lives."""
    out: List[Advice] = []
    cat = weather.category

    if cat == WeatherCategory.THUNDERSTORM:
        out.append(
            Advice(
                "safety",
                Severity.WARNING,
                "Thunderstorms expected — avoid open-air travel and cycling. "
                "Take the bus or another enclosed ride, and delay any outdoor plans.",
                "⛈️",
            )
        )
    elif cat == WeatherCategory.SNOW:
        out.append(
            Advice(
                "commute",
                Severity.CAUTION,
                "Snow is in the forecast — leave earlier, take the bus or transit "
                "instead of driving or biking, and wear waterproof boots.",
                "🌨️",
            )
        )
    elif _is_wet_outlook(weather, thresholds):
        out.append(
            Advice(
                "commute",
                Severity.CAUTION,
                "Rain is likely — take the bus instead of walking or cycling, "
                "and pack an umbrella or a waterproof jacket.",
                "🌧️",
            )
        )
        if outdoor:
            out.append(
                Advice(
                    "commute",
                    Severity.CAUTION,
                    "This looks like an outdoor activity in the wet — consider "
                    "moving it indoors or rescheduling to a drier window.",
                    "🏠",
                )
            )
    elif cat == WeatherCategory.FOG:
        out.append(
            Advice(
                "commute",
                Severity.CAUTION,
                "Fog will cut visibility — leave a little earlier and favour the "
                "bus or transit over driving or biking.",
                "🌫️",
            )
        )
    return out


def _clothing_advice(
    weather: WeatherSnapshot, thresholds: Thresholds, outdoor: bool
) -> List[Advice]:
    """What to wear and how to cope with temperature."""
    out: List[Advice] = []
    temp = weather.feels_like_c

    if temp <= thresholds.freezing_c:
        out.append(
            Advice(
                "clothing",
                Severity.WARNING,
                f"It feels around {round(temp)}°C — near freezing. Wear a heavy "
                "coat, gloves and a hat, and watch for icy footpaths.",
                "🥶",
            )
        )
    elif temp <= thresholds.cold_c:
        out.append(
            Advice(
                "clothing",
                Severity.CAUTION,
                f"Cold out (~{round(temp)}°C) — bundle up with a warm jacket "
                "and a layer underneath.",
                "🧥",
            )
        )
    elif temp <= thresholds.chilly_c:
        out.append(
            Advice(
                "clothing",
                Severity.INFO,
                f"A bit chilly (~{round(temp)}°C) — bring a light jacket or sweater.",
                "🧶",
            )
        )
    elif temp >= thresholds.hot_c:
        msg = (
            f"Hot out (~{round(temp)}°C) — hydrate well, wear light clothing and "
            "sunscreen"
        )
        msg += (
            ", and avoid strenuous activity in the midday sun."
            if outdoor
            else ", and seek shade where you can."
        )
        out.append(Advice("health", Severity.CAUTION, msg, "🥵"))
    elif temp >= thresholds.warm_c:
        out.append(
            Advice(
                "health",
                Severity.INFO,
                f"Warm and pleasant (~{round(temp)}°C)"
                + (
                    " — sunscreen and sunglasses are worth it outdoors."
                    if outdoor and weather.is_day
                    else "."
                ),
                "😎",
            )
        )
    return out


def _wind_advice(
    weather: WeatherSnapshot, thresholds: Thresholds, outdoor: bool
) -> List[Advice]:
    """Wind hazards, especially for cyclists and umbrella-holders."""
    out: List[Advice] = []
    wind = weather.wind_speed_kmh

    if wind >= thresholds.gale_wind_kmh:
        out.append(
            Advice(
                "safety",
                Severity.WARNING,
                f"Very strong wind (~{round(wind)} km/h) — cycling is risky and "
                "umbrellas will turn inside out. Secure loose items and take the bus.",
                "💨",
            )
        )
    elif wind >= thresholds.high_wind_kmh:
        out.append(
            Advice(
                "commute",
                Severity.CAUTION,
                f"Windy (~{round(wind)} km/h) — an umbrella may be useless and "
                "cycling will be hard work.",
                "🌬️",
            )
        )
    return out


def _positive_advice(
    weather: WeatherSnapshot, thresholds: Thresholds, outdoor: bool
) -> List[Advice]:
    """When conditions are genuinely good, say so — and encourage walking/biking."""
    out: List[Advice] = []
    temp = weather.feels_like_c
    calm = weather.wind_speed_kmh < thresholds.high_wind_kmh
    mild = thresholds.chilly_c < temp < thresholds.hot_c
    fair = weather.category in {WeatherCategory.CLEAR, WeatherCategory.CLOUDY}

    if fair and calm and mild and not _is_wet_outlook(weather, thresholds):
        message = "Great conditions — walking or cycling will be pleasant."
        if outdoor:
            message = "Great weather for being outside — enjoy it."
        out.append(Advice("general", Severity.INFO, message, "✅"))
    return out


def advise(
    event: Event,
    weather: WeatherSnapshot,
    thresholds: Optional[Thresholds] = None,
    *,
    outdoor: Optional[bool] = None,
    keywords: Sequence[str] = DEFAULT_OUTDOOR_KEYWORDS,
) -> List[Advice]:
    """Produce advice for a single event given its weather.

    Args:
        event: the calendar entry.
        weather: the weather snapshot at the event's time and place.
        thresholds: tuning knobs; defaults to :class:`Thresholds` defaults.
        outdoor: override the indoor/outdoor guess (mainly for tests).
        keywords: outdoor-detection vocabulary.

    Returns:
        A list of :class:`Advice`, ordered most-actionable first
        (commute → clothing → wind → positive). May be empty when conditions
        are unremarkable.
    """
    thresholds = thresholds or Thresholds()
    if outdoor is None:
        outdoor = is_outdoor_event(event, keywords)

    advice: List[Advice] = []
    advice += _commute_advice(weather, thresholds, outdoor)
    advice += _clothing_advice(weather, thresholds, outdoor)
    advice += _wind_advice(weather, thresholds, outdoor)
    # Only offer cheerful "it's lovely" advice if nothing more urgent fired.
    if not advice:
        advice += _positive_advice(weather, thresholds, outdoor)
    return advice


def general_advice(
    weather: WeatherSnapshot, thresholds: Optional[Thresholds] = None
) -> List[Advice]:
    """Day-level advice not tied to a specific event.

    Used by the ``weather`` command to add a one-line takeaway, and as a
    fallback header when the calendar is empty.
    """
    thresholds = thresholds or Thresholds()
    advice: List[Advice] = []
    advice += _commute_advice(weather, thresholds, outdoor=False)
    advice += _clothing_advice(weather, thresholds, outdoor=False)
    advice += _wind_advice(weather, thresholds, outdoor=False)
    if not advice:
        advice += _positive_advice(weather, thresholds, outdoor=False)
    return advice
