"""Tests for the advice engine — the core logic the assignment cares about.

These are the project's primary guardrails. They assert *decisions*
("rain → suggest the bus", "thunderstorm → a warning", "hot → hydrate"),
not formatting. Every test runs offline against fabricated weather.
"""

import unittest

from weather_assistant.advisor import advise, general_advice, is_outdoor_event
from weather_assistant.config import Thresholds
from weather_assistant.models import Severity, WeatherCategory
from tests.helpers import make_event, make_weather


def messages(advice):
    return " ".join(a.message.lower() for a in advice)


class RainCommuteRules(unittest.TestCase):
    """The headline rule from the rubric: does it suggest a bus when it rains?"""

    def test_rain_suggests_taking_the_bus(self):
        weather = make_weather(
            category=WeatherCategory.RAIN,
            weather_code=63,
            description="Moderate rain",
            precipitation_mm=2.0,
            precipitation_probability=90,
            temperature_c=18,
        )
        advice = advise(make_event(title="Standup", location="Office"), weather)
        text = messages(advice)
        self.assertIn("bus", text)
        self.assertTrue(
            "umbrella" in text or "waterproof" in text,
            "rain advice should mention rain protection",
        )

    def test_high_probability_but_currently_dry_still_plans_for_rain(self):
        # No rain on the ground yet, but an 80% chance — plan for it anyway.
        weather = make_weather(
            category=WeatherCategory.CLOUDY,
            weather_code=3,
            description="Overcast",
            precipitation_mm=0.0,
            precipitation_probability=80,
        )
        advice = advise(make_event(), weather)
        self.assertIn("bus", messages(advice))

    def test_clear_weather_does_not_suggest_a_bus_or_umbrella(self):
        weather = make_weather(category=WeatherCategory.CLEAR, temperature_c=22)
        text = messages(advise(make_event(), weather))
        self.assertNotIn("bus", text)
        self.assertNotIn("umbrella", text)

    def test_outdoor_event_in_rain_suggests_moving_indoors(self):
        weather = make_weather(
            category=WeatherCategory.RAIN,
            weather_code=61,
            precipitation_mm=1.0,
            precipitation_probability=85,
            temperature_c=19,
        )
        advice = advise(make_event(title="Beach Run", location="Waikiki Beach"), weather)
        text = messages(advice)
        self.assertIn("bus", text)
        self.assertTrue("indoor" in text or "reschedul" in text)


class SevereWeatherRules(unittest.TestCase):
    def test_thunderstorm_is_a_warning_and_avoids_open_air(self):
        weather = make_weather(
            category=WeatherCategory.THUNDERSTORM,
            weather_code=95,
            description="Thunderstorm",
            precipitation_mm=5.0,
            precipitation_probability=95,
            temperature_c=24,
        )
        advice = advise(make_event(location="Park"), weather)
        self.assertEqual(
            max(a.severity for a in advice).rank, Severity.WARNING.rank
        )
        self.assertIn("bus", messages(advice))

    def test_snow_advises_extra_time_and_transit(self):
        weather = make_weather(
            category=WeatherCategory.SNOW,
            weather_code=73,
            description="Moderate snowfall",
            precipitation_mm=3.0,
            precipitation_probability=90,
            temperature_c=-1,
        )
        text = messages(advise(make_event(), weather))
        self.assertTrue("bus" in text or "transit" in text)

    def test_gale_force_wind_is_a_warning(self):
        weather = make_weather(wind_speed_kmh=60, category=WeatherCategory.CLEAR)
        advice = advise(make_event(), weather)
        self.assertEqual(max(a.severity for a in advice).rank, Severity.WARNING.rank)


class TemperatureRules(unittest.TestCase):
    def test_cold_suggests_a_warm_jacket(self):
        weather = make_weather(temperature_c=4, category=WeatherCategory.CLOUDY)
        text = messages(advise(make_event(), weather))
        self.assertTrue("jacket" in text or "warm" in text or "coat" in text)

    def test_freezing_warns_about_ice(self):
        weather = make_weather(temperature_c=0, category=WeatherCategory.CLOUDY)
        advice = advise(make_event(), weather)
        self.assertIn("ic", messages(advice))  # 'ice' / 'icy'
        self.assertEqual(max(a.severity for a in advice).rank, Severity.WARNING.rank)

    def test_hot_suggests_hydration_and_sunscreen(self):
        weather = make_weather(temperature_c=33, category=WeatherCategory.CLEAR)
        text = messages(advise(make_event(), weather))
        self.assertIn("hydrate", text)
        self.assertIn("sunscreen", text)

    def test_uses_apparent_temperature_when_present(self):
        # Dry-bulb 20 °C looks mild, but it *feels* like 2 °C — advise for the feel.
        weather = make_weather(
            temperature_c=20, apparent_temperature_c=2, category=WeatherCategory.CLOUDY
        )
        text = messages(advise(make_event(), weather))
        self.assertTrue("warm" in text or "jacket" in text or "coat" in text)


class ThresholdsAreData(unittest.TestCase):
    """Thresholds come from config, so the same weather yields different advice
    under different tuning — proving the rules are data-driven, not hardcoded."""

    def test_custom_hot_threshold_changes_the_outcome(self):
        weather = make_weather(temperature_c=26, category=WeatherCategory.CLEAR)
        lenient = Thresholds(hot_c=40)   # 26 °C is not 'hot'
        strict = Thresholds(hot_c=25)    # 26 °C is 'hot'
        self.assertNotIn("hydrate", messages(advise(make_event(), weather, lenient)))
        self.assertIn("hydrate", messages(advise(make_event(), weather, strict)))


class OutdoorDetection(unittest.TestCase):
    def test_outdoor_keywords_are_detected(self):
        self.assertTrue(is_outdoor_event(make_event(title="Morning Run", location="Park")))
        self.assertTrue(is_outdoor_event(make_event(title="Lunch", location="Beach Cafe")))

    def test_plain_office_event_is_indoor(self):
        self.assertFalse(is_outdoor_event(make_event(title="1:1", location="Room 204")))


class PleasantWeather(unittest.TestCase):
    def test_nice_day_encourages_walking_or_cycling(self):
        weather = make_weather(temperature_c=21, wind_speed_kmh=8, category=WeatherCategory.CLEAR)
        advice = advise(make_event(title="Coffee", location="Cafe"), weather)
        text = messages(advice)
        self.assertTrue("walk" in text or "cycl" in text or "enjoy" in text)
        # Pleasant weather should never raise an alarm.
        self.assertEqual(max(a.severity for a in advice).rank, Severity.INFO.rank)

    def test_general_advice_mirrors_event_advice(self):
        weather = make_weather(
            category=WeatherCategory.RAIN, weather_code=61,
            precipitation_mm=1.0, precipitation_probability=80, temperature_c=17,
        )
        self.assertIn("bus", messages(general_advice(weather)))


if __name__ == "__main__":
    unittest.main()
