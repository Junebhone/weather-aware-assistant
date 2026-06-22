"""Tests for reading and validating calendar.json.

Validation should be strict and the error messages helpful — a malformed
calendar is a user error we want to explain, not a stack trace.
"""

import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from weather_assistant.calendar_loader import (
    CalendarError,
    load_events,
    parse_events,
)

VALID = {
    "events": [
        {"title": "Standup", "start": "2026-06-20T09:00:00",
         "end": "2026-06-20T09:30:00", "location": "Office"},
        {"title": "Run", "start": "2026-06-20T06:30:00",
         "end": "2026-06-20T07:15:00", "location": "Park"},
    ]
}


class ParseEvents(unittest.TestCase):
    def test_parses_and_sorts_by_start(self):
        events = parse_events(VALID)
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0].title, "Run")     # 06:30 sorts before 09:00
        self.assertEqual(events[1].title, "Standup")

    def test_accepts_a_bare_list(self):
        events = parse_events(VALID["events"])
        self.assertEqual(len(events), 2)

    def test_empty_calendar_is_valid(self):
        self.assertEqual(parse_events({"events": []}), [])

    def test_parsed_dates_are_datetimes(self):
        event = parse_events(VALID)[0]
        self.assertIsInstance(event.start, datetime)
        self.assertEqual(event.duration_minutes, 45)


class Validation(unittest.TestCase):
    def test_missing_field_raises_with_helpful_message(self):
        bad = {"events": [{"title": "X", "start": "2026-06-20T09:00:00",
                           "location": "Office"}]}  # no 'end'
        with self.assertRaises(CalendarError) as ctx:
            parse_events(bad)
        self.assertIn("end", str(ctx.exception))

    def test_bad_datetime_raises(self):
        bad = {"events": [{"title": "X", "start": "yesterday",
                           "end": "2026-06-20T09:30:00", "location": "Office"}]}
        with self.assertRaises(CalendarError):
            parse_events(bad)

    def test_end_before_start_raises(self):
        bad = {"events": [{"title": "X", "start": "2026-06-20T10:00:00",
                           "end": "2026-06-20T09:00:00", "location": "Office"}]}
        with self.assertRaises(CalendarError):
            parse_events(bad)

    def test_non_list_payload_raises(self):
        with self.assertRaises(CalendarError):
            parse_events({"events": "not a list"})


class LoadFromDisk(unittest.TestCase):
    def test_round_trips_through_a_real_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "calendar.json"
            path.write_text(json.dumps(VALID), encoding="utf-8")
            events = load_events(path)
            self.assertEqual(len(events), 2)

    def test_missing_file_raises(self):
        with self.assertRaises(CalendarError):
            load_events("/no/such/calendar.json")

    def test_invalid_json_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "calendar.json"
            path.write_text("{ not json", encoding="utf-8")
            with self.assertRaises(CalendarError):
                load_events(path)

    def test_repository_sample_calendar_is_valid(self):
        # Guards the committed sample so the demo never ships broken.
        sample = Path(__file__).resolve().parent.parent / "calendar.json"
        events = load_events(sample)
        self.assertGreaterEqual(len(events), 1)


if __name__ == "__main__":
    unittest.main()
