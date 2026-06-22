"""Tests for the CLI command routing.

``Assistant.handle()`` returns a string instead of printing, so the whole
command layer is testable. We inject a fake weather client (no network) and a
throwaway calendar file, then assert each command routes correctly — including
the graceful-degradation path when the client is "offline".
"""

import json
import tempfile
import unittest
from pathlib import Path

from weather_assistant.cli import Assistant
from weather_assistant.config import AppConfig
from weather_assistant.weather import WeatherUnavailable, parse_current, parse_hourly

FIXTURE = Path(__file__).parent / "fixtures" / "sample_forecast.json"


class FakeClient:
    """Stands in for OpenMeteoClient. Returns fixture data, or fails on demand."""

    def __init__(self, raw, *, offline=False):
        self.offline = offline
        self._current = parse_current(raw, "Honolulu")
        self._hourly = parse_hourly(raw, "Honolulu")

    def current(self, location):
        if self.offline:
            raise WeatherUnavailable("offline (test)")
        return self._current

    def hourly_forecast(self, location, days=3):
        if self.offline:
            raise WeatherUnavailable("offline (test)")
        return self._hourly


class CliRouting(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.calendar = Path(tmp.name) / "calendar.json"
        self.calendar.write_text(
            json.dumps(
                {
                    "events": [
                        {
                            "title": "Beach Run",
                            "location": "Waikiki Beach",
                            "start": "2026-06-20T06:30:00",
                            "end": "2026-06-20T07:15:00",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        self.raw = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def _assistant(self, offline=False):
        return Assistant(
            AppConfig(),
            client=FakeClient(self.raw, offline=offline),
            calendar_path=self.calendar,
        )

    def test_help_lists_commands(self):
        self.assertIn("brief", self._assistant().handle("help").lower())

    def test_blank_input_is_silent(self):
        self.assertEqual(self._assistant().handle("   "), "")

    def test_unknown_command_is_reported(self):
        self.assertIn("unknown", self._assistant().handle("teleport").lower())

    def test_agenda_lists_calendar_events(self):
        self.assertIn("Beach Run", self._assistant().handle("agenda"))

    def test_home_changes_session_location(self):
        assistant = self._assistant()
        out = assistant.handle("home Kyoto")
        self.assertIn("Kyoto", out)
        self.assertEqual(assistant.config.home_location, "Kyoto")

    def test_weather_renders_a_card(self):
        out = self._assistant().handle("weather Honolulu")
        self.assertIn("Weather for", out)
        self.assertIn("°C", out)

    def test_weather_offline_is_friendly_not_a_crash(self):
        out = self._assistant(offline=True).handle("weather Honolulu")
        self.assertIn("⚠️", out)

    def test_brief_gives_weather_aware_advice(self):
        # 06:30 run maps to the fixture's 06:00 rainy hour -> bus advice.
        out = self._assistant().handle("brief")
        self.assertIn("Beach Run", out)
        self.assertIn("bus", out.lower())

    def test_brief_offline_still_shows_the_schedule(self):
        out = self._assistant(offline=True).handle("brief")
        self.assertIn("Beach Run", out)            # schedule survives
        self.assertIn("unavailable", out.lower())  # honest about the gap

    def test_command_aliases_work(self):
        assistant = self._assistant()
        self.assertEqual(assistant.handle("schedule"), assistant.handle("agenda"))


if __name__ == "__main__":
    unittest.main()
