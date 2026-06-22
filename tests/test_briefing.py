"""Integration tests for the briefing orchestrator.

These prove the pieces fit together — calendar events get paired with the right
forecast hour and the advisor's output lands in the briefing — all without a
network, using an injected in-memory lookup.
"""

import json
import unittest
from datetime import datetime
from pathlib import Path

from weather_assistant.briefing import build_daily_briefing, make_lookup, match_hourly
from weather_assistant.config import AppConfig
from weather_assistant.models import Severity, WeatherCategory
from weather_assistant.weather import WeatherUnavailable, parse_hourly
from tests.helpers import make_event, make_weather

FIXTURE = Path(__file__).parent / "fixtures" / "sample_forecast.json"


def fixture_hours():
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return parse_hourly(raw, "Honolulu")


class MatchHourly(unittest.TestCase):
    def test_exact_hour_match(self):
        hours = fixture_hours()
        snap = match_hourly(datetime.fromisoformat("2026-06-20T15:00"), hours)
        self.assertEqual(snap.category, WeatherCategory.THUNDERSTORM)

    def test_same_hour_on_a_different_date_still_matches(self):
        # Event written for a future date, but 06:00 should map to the 06:00
        # forecast hour we have — this is what makes routine calendars work.
        hours = fixture_hours()
        snap = match_hourly(datetime.fromisoformat("2027-01-01T06:00"), hours)
        self.assertEqual(snap.category, WeatherCategory.RAIN)

    def test_nearest_hour_is_the_last_resort(self):
        # 02:00 has no exact match and no matching hour-of-day in the fixture
        # (which only has 06,09,12,15,18) -> fall back to the nearest, 06:00.
        hours = fixture_hours()
        snap = match_hourly(datetime.fromisoformat("2026-06-20T02:00"), hours)
        self.assertEqual(snap.time.hour, 6)

    def test_returns_none_when_no_snapshots(self):
        self.assertIsNone(match_hourly(datetime.now(), []))


class BuildDailyBriefing(unittest.TestCase):
    def _lookup_from_fixture(self):
        hours = fixture_hours()
        return lambda event: match_hourly(event.start, hours)

    def test_rainy_morning_run_gets_bus_advice(self):
        events = [make_event(title="Beach Run", location="Waikiki Beach",
                             start="2026-06-20T06:30:00", end="2026-06-20T07:15:00")]
        briefing = build_daily_briefing(
            events, self._lookup_from_fixture(), location="Honolulu"
        )
        item = briefing.items[0]
        self.assertEqual(item.weather.category, WeatherCategory.RAIN)
        text = " ".join(a.message.lower() for a in item.advice)
        self.assertIn("bus", text)

    def test_full_day_briefing_flags_the_thunderstorm(self):
        events = [
            make_event(title="Beach Run", location="Waikiki Beach",
                       start="2026-06-20T06:30:00", end="2026-06-20T07:15:00"),
            make_event(title="Lecture", location="Campus Center",
                       start="2026-06-20T15:00:00", end="2026-06-20T16:30:00"),
        ]
        briefing = build_daily_briefing(
            events, self._lookup_from_fixture(), location="Honolulu"
        )
        self.assertEqual(len(briefing.items), 2)
        self.assertEqual(briefing.max_severity.rank, Severity.WARNING.rank)

    def test_missing_weather_degrades_gracefully(self):
        # A lookup that always fails to find weather must not crash the briefing.
        events = [make_event()]
        briefing = build_daily_briefing(
            events, lambda event: None, location="Honolulu"
        )
        self.assertEqual(len(briefing.items), 1)
        self.assertIsNone(briefing.items[0].weather)
        self.assertTrue(briefing.notes)  # a note explains the gap

    def test_empty_calendar_produces_empty_briefing(self):
        briefing = build_daily_briefing([], lambda event: None, location="Honolulu")
        self.assertEqual(briefing.items, [])


class LookupGeocodingFallback(unittest.TestCase):
    """A descriptive venue that the geocoder can't resolve should fall back to
    its city, so a real calendar ("POST Building, UH Manoa, Honolulu") still
    gets weather instead of silently coming back empty."""

    class PickyClient:
        """Only resolves a clean city name; rejects descriptive venue strings."""

        def __init__(self, hours, known="Honolulu"):
            self.hours = hours
            self.known = known
            self.queries = []

        def hourly_forecast(self, location, days=3):
            self.queries.append(location)
            if location == self.known:
                return self.hours
            raise WeatherUnavailable(f"no match for '{location}'")

    def test_falls_back_from_venue_to_city(self):
        client = self.PickyClient(fixture_hours())
        lookup = make_lookup(client, AppConfig())
        event = make_event(
            title="Standup", location="POST Building, UH Manoa, Honolulu",
            start="2026-06-20T06:30:00", end="2026-06-20T07:15:00",
        )
        snapshot = lookup(event)
        self.assertIsNotNone(snapshot)                      # weather was found
        self.assertEqual(snapshot.category, WeatherCategory.RAIN)
        self.assertEqual(client.queries[0], "POST Building, UH Manoa, Honolulu")
        self.assertIn("Honolulu", client.queries)           # fell back to the city

    def test_unresolvable_location_returns_none_without_crashing(self):
        client = self.PickyClient(fixture_hours(), known="Atlantis")
        lookup = make_lookup(client, AppConfig())
        event = make_event(location="Nowhere City")
        self.assertIsNone(lookup(event))


if __name__ == "__main__":
    unittest.main()
