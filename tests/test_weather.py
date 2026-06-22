"""Tests for the weather module's pure parts: code mapping and JSON parsing.

No network is touched. We load a captured Open-Meteo response from
``fixtures/sample_forecast.json`` and assert the parsers turn it into the
right model objects. One test patches the single network function to prove the
client assembles a request and parses the reply without ever leaving the box.
"""

import json
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

from weather_assistant import weather
from weather_assistant.models import WeatherCategory
from weather_assistant.weather import (
    OpenMeteoClient,
    WeatherUnavailable,
    categorize,
    location_candidates,
    parse_current,
    parse_hourly,
)

FIXTURE = Path(__file__).parent / "fixtures" / "sample_forecast.json"


def load_fixture():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


class CategorizeWmoCodes(unittest.TestCase):
    def test_known_codes_map_to_expected_buckets(self):
        cases = {
            0: WeatherCategory.CLEAR,
            3: WeatherCategory.CLOUDY,
            45: WeatherCategory.FOG,
            51: WeatherCategory.DRIZZLE,
            65: WeatherCategory.RAIN,
            75: WeatherCategory.SNOW,
            95: WeatherCategory.THUNDERSTORM,
        }
        for code, expected in cases.items():
            category, description = categorize(code)
            self.assertEqual(category, expected, f"code {code}")
            self.assertTrue(description)

    def test_unknown_code_is_handled_gracefully(self):
        category, description = categorize(12345)
        self.assertEqual(category, WeatherCategory.UNKNOWN)
        self.assertIn("12345", description)


class ParseCurrent(unittest.TestCase):
    def test_parses_current_block(self):
        snapshot = parse_current(load_fixture(), "Honolulu")
        self.assertEqual(snapshot.location, "Honolulu")
        self.assertAlmostEqual(snapshot.temperature_c, 27.4)
        self.assertAlmostEqual(snapshot.apparent_temperature_c, 29.1)
        self.assertEqual(snapshot.category, WeatherCategory.CLEAR)
        self.assertTrue(snapshot.is_day)
        self.assertFalse(snapshot.is_wet)

    def test_missing_current_block_raises(self):
        with self.assertRaises(WeatherUnavailable):
            parse_current({"hourly": {}}, "Nowhere")


class ParseHourly(unittest.TestCase):
    def test_zips_parallel_arrays_into_snapshots(self):
        snapshots = parse_hourly(load_fixture(), "Honolulu")
        self.assertEqual(len(snapshots), 5)

    def test_first_hour_is_rain_with_probability(self):
        first = parse_hourly(load_fixture(), "Honolulu")[0]
        self.assertEqual(first.category, WeatherCategory.RAIN)
        self.assertEqual(first.precipitation_probability, 80)
        self.assertTrue(first.is_wet)
        self.assertEqual(first.time, datetime.fromisoformat("2026-06-20T06:00"))

    def test_thunderstorm_hour_is_detected(self):
        snapshots = parse_hourly(load_fixture(), "Honolulu")
        storm = next(s for s in snapshots if s.time.hour == 15)
        self.assertEqual(storm.category, WeatherCategory.THUNDERSTORM)


class ClientUsesParsersWithoutNetwork(unittest.TestCase):
    def test_current_calls_geocode_then_forecast(self):
        client = OpenMeteoClient(timeout_s=1)
        geocode_reply = {"results": [{"latitude": 21.3, "longitude": -157.85,
                                       "name": "Honolulu", "country": "United States"}]}
        forecast_reply = load_fixture()

        with mock.patch.object(
            weather, "_http_get_json", side_effect=[geocode_reply, forecast_reply]
        ) as fake:
            snapshot = client.current("Honolulu")

        self.assertEqual(fake.call_count, 2)  # one geocode + one forecast
        self.assertEqual(snapshot.category, WeatherCategory.CLEAR)
        self.assertIn("Honolulu", snapshot.location)

    def test_unknown_place_raises_weather_unavailable(self):
        client = OpenMeteoClient(timeout_s=1)
        with mock.patch.object(weather, "_http_get_json", return_value={"results": []}):
            with self.assertRaises(WeatherUnavailable):
                client.current("Atlantis")


class LocationCandidates(unittest.TestCase):
    def test_descriptive_venue_falls_back_to_city(self):
        self.assertEqual(
            location_candidates("POST Building, UH Manoa, Honolulu"),
            ["POST Building, UH Manoa, Honolulu", "UH Manoa, Honolulu", "Honolulu"],
        )

    def test_plain_city_is_unchanged(self):
        self.assertEqual(location_candidates("Honolulu"), ["Honolulu"])

    def test_handles_extra_whitespace(self):
        self.assertEqual(
            location_candidates(" Waikiki Beach ,  Honolulu "),
            ["Waikiki Beach, Honolulu", "Honolulu"],
        )


if __name__ == "__main__":
    unittest.main()
