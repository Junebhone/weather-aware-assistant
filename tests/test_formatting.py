"""Tests for the presentation layer.

``formatting`` is pure (data -> string), so we can assert the *content* of what
the user sees without spinning up a terminal: does the briefing actually surface
the bus advice? does an event with no weather say so? does the weather line show
temperature, conditions and wind?
"""

import unittest
from datetime import date

from weather_assistant import formatting
from weather_assistant.advisor import advise
from weather_assistant.models import (
    Advice,
    DailyBriefing,
    EventBriefing,
    Severity,
    WeatherCategory,
)
from tests.helpers import make_event, make_weather

RAINY_RUN_WEATHER = make_weather(
    category=WeatherCategory.RAIN,
    weather_code=61,
    description="Slight rain",
    precipitation_mm=1.2,
    precipitation_probability=80,
    temperature_c=23,
    wind_speed_kmh=18,
    time="2026-06-20T06:00",
)
RUN_EVENT = make_event(
    title="Beach Run",
    location="Waikiki Beach",
    start="2026-06-20T06:30:00",
    end="2026-06-20T07:15:00",
)


class WeatherLine(unittest.TestCase):
    def test_shows_temperature_conditions_and_wind(self):
        line = formatting.render_weather_line(RAINY_RUN_WEATHER)
        self.assertIn("23°C", line)
        self.assertIn("Slight rain", line)
        self.assertIn("wind 18 km/h", line)
        self.assertIn("rain 80%", line)

    def test_omits_probability_when_unknown(self):
        clear = make_weather(precipitation_probability=None, description="Clear sky")
        self.assertNotIn("%", formatting.render_weather_line(clear))

    def test_weather_card_includes_header_feels_like_and_advice(self):
        weather = make_weather(
            location="Honolulu", category=WeatherCategory.RAIN, weather_code=61,
            description="Slight rain", precipitation_mm=1.2,
            precipitation_probability=80, temperature_c=23,
        )
        card = formatting.render_weather(weather, advise(RUN_EVENT, weather))
        self.assertIn("Weather for Honolulu", card)
        self.assertIn("feels like", card)
        self.assertIn("bus", card.lower())


class Agenda(unittest.TestCase):
    def test_lists_each_event(self):
        events = [
            make_event(title="Standup", location="Office"),
            make_event(title="Beach Run", location="Waikiki Beach"),
        ]
        text = formatting.render_agenda(events)
        self.assertIn("Standup", text)
        self.assertIn("Waikiki Beach", text)

    def test_empty_calendar_message(self):
        self.assertIn("no events", formatting.render_agenda([]).lower())


class EventBriefingRendering(unittest.TestCase):
    def test_renders_event_with_weather_and_advice(self):
        item = EventBriefing(RUN_EVENT, RAINY_RUN_WEATHER, advise(RUN_EVENT, RAINY_RUN_WEATHER))
        text = formatting.render_event_briefing(item)
        self.assertIn("Beach Run", text)
        self.assertIn("06:30", text)
        self.assertIn("bus", text.lower())

    def test_weather_unavailable_is_shown_not_hidden(self):
        item = EventBriefing(RUN_EVENT, weather=None, advice=[])
        self.assertIn("unavailable", formatting.render_event_briefing(item).lower())

    def test_calm_event_says_youre_good_to_go(self):
        calm = make_weather(temperature_c=20, category=WeatherCategory.CLOUDY)
        item = EventBriefing(make_event(title="1:1", location="Room 2"), calm, advice=[])
        self.assertIn("good to go", formatting.render_event_briefing(item).lower())


class DailyBriefingRendering(unittest.TestCase):
    def test_headline_includes_date_and_location_and_advice(self):
        item = EventBriefing(RUN_EVENT, RAINY_RUN_WEATHER, advise(RUN_EVENT, RAINY_RUN_WEATHER))
        briefing = DailyBriefing(on_date=date(2026, 6, 20), location="Honolulu", items=[item])
        text = formatting.render_daily_briefing(briefing)
        self.assertIn("Daily Briefing", text)
        self.assertIn("Honolulu", text)
        self.assertIn("bus", text.lower())

    def test_empty_calendar_is_friendly(self):
        briefing = DailyBriefing(on_date=date(2026, 6, 20), location="Honolulu")
        self.assertIn("empty", formatting.render_daily_briefing(briefing).lower())

    def test_notes_are_surfaced(self):
        briefing = DailyBriefing(
            on_date=date(2026, 6, 20),
            location="Honolulu",
            notes=["Weather was unavailable for 2 event(s)."],
        )
        self.assertIn("unavailable", formatting.render_daily_briefing(briefing).lower())


class StaticText(unittest.TestCase):
    def test_help_lists_the_core_commands(self):
        text = formatting.render_help().lower()
        for command in ("brief", "weather", "agenda", "quit"):
            self.assertIn(command, text)

    def test_banner_shows_home(self):
        self.assertIn("Reykjavik", formatting.render_banner("Reykjavik"))


if __name__ == "__main__":
    unittest.main()
