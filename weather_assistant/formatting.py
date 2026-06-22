"""Presentation helpers — turn data objects into display strings.

This module is the *text* half of the UI. It is still pure: every function
takes data and returns a string. It performs no input and calls no ``print``.
That means the look of the assistant can be unit-tested ("does the briefing
mention the umbrella advice?") and the only module that actually writes to the
screen is ``cli.py``.

If you wanted a web UI or a JSON API instead of a terminal, you would replace
this file and ``cli.py`` and leave every logic module untouched.
"""

from __future__ import annotations

from datetime import date
from typing import List, Sequence

from .models import (
    Advice,
    DailyBriefing,
    Event,
    EventBriefing,
    Severity,
    WeatherCategory,
    WeatherSnapshot,
)

SEVERITY_ICON = {
    Severity.INFO: "•",
    Severity.CAUTION: "⚠️ ",
    Severity.WARNING: "🚨",
}

CATEGORY_EMOJI = {
    WeatherCategory.CLEAR: "☀️",
    WeatherCategory.CLOUDY: "☁️",
    WeatherCategory.FOG: "🌫️",
    WeatherCategory.DRIZZLE: "🌦️",
    WeatherCategory.RAIN: "🌧️",
    WeatherCategory.SNOW: "🌨️",
    WeatherCategory.THUNDERSTORM: "⛈️",
    WeatherCategory.UNKNOWN: "🌡️",
}


def weather_emoji(snapshot: WeatherSnapshot) -> str:
    return CATEGORY_EMOJI.get(snapshot.category, "🌡️")


def render_weather_line(snapshot: WeatherSnapshot) -> str:
    """A compact one-line weather summary, e.g. '☀️ 27°C, Clear sky, wind 11 km/h'."""
    parts = [
        f"{weather_emoji(snapshot)} {round(snapshot.temperature_c)}°C",
        snapshot.description,
        f"wind {round(snapshot.wind_speed_kmh)} km/h",
    ]
    if snapshot.precipitation_probability is not None:
        parts.append(f"rain {snapshot.precipitation_probability}%")
    return ", ".join(parts)


def render_weather(snapshot: WeatherSnapshot, advice: Sequence[Advice]) -> str:
    """A full weather card for the ``weather`` command."""
    lines = [
        f"📍 Weather for {snapshot.location}",
        f"   {render_weather_line(snapshot)}",
        f"   feels like {round(snapshot.feels_like_c)}°C",
    ]
    if advice:
        lines.append("")
        lines.extend(_render_advice_block(advice, indent="   "))
    return "\n".join(lines)


def _format_time_range(event: Event) -> str:
    return f"{event.start.strftime('%H:%M')}–{event.end.strftime('%H:%M')}"


def render_agenda(events: Sequence[Event]) -> str:
    """The plain schedule, no weather."""
    if not events:
        return "🗓️  Your calendar has no events."
    lines = ["🗓️  Schedule:"]
    for event in events:
        when = f"{event.start.strftime('%a %d %b')} {_format_time_range(event)}"
        lines.append(f"   • {when} — {event.title} @ {event.location}")
    return "\n".join(lines)


def _render_advice_block(advice: Sequence[Advice], indent: str = "   ") -> List[str]:
    lines: List[str] = []
    for item in advice:
        icon = item.icon or SEVERITY_ICON[item.severity]
        lines.append(f"{indent}{icon} {item.message}")
    return lines


def render_event_briefing(item: EventBriefing) -> str:
    """One event with its weather and advice."""
    event = item.event
    header = f"🔹 {_format_time_range(event)}  {event.title} @ {event.location}"
    lines = [header]
    if item.weather is not None:
        lines.append(f"   {render_weather_line(item.weather)}")
    else:
        lines.append("   (weather unavailable)")
    if item.advice:
        lines.extend(_render_advice_block(item.advice))
    elif item.weather is not None:
        lines.append("   • Nothing to flag — you're good to go.")
    return "\n".join(lines)


def render_daily_briefing(briefing: DailyBriefing) -> str:
    """The headline output: the whole day, synthesised."""
    title_date = _format_date(briefing.on_date)
    lines = [f"🗓️  Daily Briefing — {title_date}  ({briefing.location})", ""]

    if not briefing.items:
        lines.append("   Your calendar is empty. Enjoy the open day!")
    for index, item in enumerate(briefing.items):
        lines.append(render_event_briefing(item))
        if index != len(briefing.items) - 1:
            lines.append("")

    if briefing.general:
        lines.append("")
        lines.append("General:")
        lines.extend(_render_advice_block(briefing.general))

    for note in briefing.notes:
        lines.append("")
        lines.append(f"ℹ️  {note}")
    return "\n".join(lines)


def _format_date(value: date) -> str:
    return value.strftime("%A, %d %B %Y")


def render_banner(home: str) -> str:
    return (
        "═══════════════════════════════════════════════\n"
        " 🌤️  Weather-Aware Personal Assistant\n"
        f"     Home base: {home}\n"
        "═══════════════════════════════════════════════\n"
        " Type a command, or 'help' to see what I can do.\n"
        " (Tip: try 'brief' for your weather-aware day.)"
    )


def render_help() -> str:
    return "\n".join(
        [
            "Commands:",
            "   brief [location]   Weather-aware rundown of today's schedule",
            "   weather [location] Current conditions (defaults to home)",
            "   agenda             Show the schedule with no weather",
            "   home <location>    Change your home base for this session",
            "   help               Show this help",
            "   quit / exit        Leave the assistant",
        ]
    )
