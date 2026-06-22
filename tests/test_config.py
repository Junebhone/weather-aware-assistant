"""Tests for configuration: threshold sanity and environment overrides.

These pin down that thresholds form a coherent ladder and that the documented
environment overrides (WA_HOME_LOCATION / WA_FORECAST_DAYS) actually work — the
escape hatch that lets a user point the assistant at their own city without
editing code.
"""

import os
import unittest
from unittest import mock

from weather_assistant.config import AppConfig, Thresholds


class ThresholdLadder(unittest.TestCase):
    def test_temperature_thresholds_are_ordered(self):
        t = Thresholds()
        self.assertLess(t.freezing_c, t.cold_c)
        self.assertLess(t.cold_c, t.chilly_c)
        self.assertLess(t.chilly_c, t.warm_c)
        self.assertLess(t.warm_c, t.hot_c)

    def test_wind_thresholds_are_ordered(self):
        t = Thresholds()
        self.assertLess(t.high_wind_kmh, t.gale_wind_kmh)


class EnvironmentOverrides(unittest.TestCase):
    def test_home_location_override(self):
        with mock.patch.dict(os.environ, {"WA_HOME_LOCATION": "Berlin"}):
            self.assertEqual(AppConfig.from_env().home_location, "Berlin")

    def test_forecast_days_override_is_clamped(self):
        with mock.patch.dict(os.environ, {"WA_FORECAST_DAYS": "99"}):
            self.assertEqual(AppConfig.from_env().forecast_days, 16)

    def test_defaults_apply_when_env_is_empty(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            cfg = AppConfig.from_env()
            self.assertEqual(cfg.home_location, "Honolulu")
            self.assertEqual(cfg.forecast_days, 3)


class WithHome(unittest.TestCase):
    def test_with_home_trims_and_does_not_mutate_original(self):
        base = AppConfig()
        changed = base.with_home("  Paris  ")
        self.assertEqual(changed.home_location, "Paris")
        self.assertEqual(base.home_location, "Honolulu")  # frozen: original intact


if __name__ == "__main__":
    unittest.main()
