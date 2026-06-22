"""Briefing orchestrator — stitches calendar + weather + advice together.

This is still *logic*, not UI: it returns a :class:`DailyBriefing` data object
and never prints. The key design choice is dependency injection. Instead of
reaching out to the network itself, ``build_daily_briefing`` accepts a
``lookup`` callable:

    lookup(event) -> Optional[WeatherSnapshot]

In production that callable is backed by :class:`OpenMeteoClient` (see
``make_lookup``). In tests it is a trivial in-memory stub. Same orchestration
code, no network in the test suite.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Callable, Dict, List, Optional, Sequence

from . import advisor
from .config import DEFAULT_OUTDOOR_KEYWORDS, AppConfig, Thresholds
from .models import DailyBriefing, Event, EventBriefing, WeatherSnapshot
from .weather import OpenMeteoClient, WeatherUnavailable, location_candidates

WeatherLookup = Callable[[Event], Optional[WeatherSnapshot]]


def match_hourly(
    when: datetime, snapshots: Sequence[WeatherSnapshot]
) -> Optional[WeatherSnapshot]:
    """Pick the forecast hour that best represents ``when``.

    Strategy, in order of preference:
      1. Exact same calendar date *and* hour.
      2. Same hour-of-day on the earliest forecast day. This lets a recurring
         daily-routine calendar ("07:00 beach run") be advised against *today's*
         forecast no matter what date is written in the file — so the demo works
         on any day a reviewer runs it.
      3. The chronologically nearest hour, as a last resort.

    Returns ``None`` only if there are no snapshots at all.
    """
    dated = [s for s in snapshots if s.time is not None]
    if not dated:
        return None

    for snap in dated:
        if snap.time.date() == when.date() and snap.time.hour == when.hour:
            return snap

    for snap in dated:  # snapshots are chronological → first match is earliest day
        if snap.time.hour == when.hour:
            return snap

    return min(dated, key=lambda s: abs((s.time - when).total_seconds()))


def make_lookup(client: OpenMeteoClient, config: AppConfig) -> WeatherLookup:
    """Build a caching weather lookup backed by the live Open-Meteo client.

    Geocoding + forecasting is cached per location string so a five-event day
    in two places makes two network round-trips, not five. Any
    :class:`WeatherUnavailable` is swallowed and surfaced as ``None`` so the
    briefing degrades gracefully instead of crashing.
    """
    cache: Dict[str, List[WeatherSnapshot]] = {}

    def forecast_for(place: str) -> List[WeatherSnapshot]:
        if place in cache:
            return cache[place]
        # Try the full venue string, then progressively more general queries
        # (its city), then the configured home as a final fallback.
        queries = location_candidates(place)
        if config.home_location not in queries:
            queries.append(config.home_location)
        snapshots: List[WeatherSnapshot] = []
        for query in queries:
            try:
                snapshots = client.hourly_forecast(query, config.forecast_days)
            except WeatherUnavailable:
                continue
            if snapshots:
                break
        cache[place] = snapshots
        return snapshots

    def lookup(event: Event) -> Optional[WeatherSnapshot]:
        place = event.location or config.home_location
        return match_hourly(event.start, forecast_for(place))

    return lookup


def build_daily_briefing(
    events: Sequence[Event],
    lookup: WeatherLookup,
    *,
    location: str,
    thresholds: Optional[Thresholds] = None,
    on_date: Optional[date] = None,
    keywords: Sequence[str] = DEFAULT_OUTDOOR_KEYWORDS,
) -> DailyBriefing:
    """Assemble a full daily briefing from events and a weather lookup."""
    thresholds = thresholds or Thresholds()
    briefing = DailyBriefing(on_date=on_date or _first_date(events), location=location)

    missing_weather = 0
    for event in events:
        weather = lookup(event)
        if weather is None:
            missing_weather += 1
            briefing.items.append(EventBriefing(event=event, weather=None, advice=[]))
            continue
        advice = advisor.advise(event, weather, thresholds, keywords=keywords)
        briefing.items.append(EventBriefing(event=event, weather=weather, advice=advice))

    if missing_weather:
        briefing.notes.append(
            f"Weather was unavailable for {missing_weather} event(s); "
            "showing the schedule without advice for those."
        )
    return briefing


def _first_date(events: Sequence[Event]) -> date:
    if events:
        return events[0].start.date()
    # No events and no explicit date: fall back to the earliest representable
    # date rather than calling datetime.now() (kept deterministic for tests;
    # the CLI passes an explicit on_date).
    return date(1970, 1, 1)
