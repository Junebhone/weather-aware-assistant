"""Calendar loader — reads and validates ``calendar.json``.

The on-disk schema is intentionally minimal (it is what the assignment asks
for): a list of events, each with ``title``, ``start``, ``end`` and
``location``. We accept either a bare JSON list or an object with an
``"events"`` key, so the file can grow metadata later without breaking.

File reading lives here and nowhere else; parsing/validation is broken out so
it can be tested against in-memory dictionaries without touching the disk.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, List, Union

from .models import Event

REQUIRED_FIELDS = ("title", "start", "end", "location")


class CalendarError(Exception):
    """Raised when the calendar file is missing, malformed, or invalid."""


def parse_datetime(value: Any, field: str, index: int) -> datetime:
    """Parse an ISO-8601 string into a datetime, with a helpful error."""
    if not isinstance(value, str):
        raise CalendarError(
            f"Event #{index + 1}: '{field}' must be an ISO-8601 string, "
            f"got {type(value).__name__}."
        )
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CalendarError(
            f"Event #{index + 1}: '{field}' is not a valid ISO-8601 datetime "
            f"('{value}'). Try e.g. '2026-06-20T09:00:00'."
        ) from exc


def parse_event(obj: Any, index: int) -> Event:
    """Validate one raw dict and turn it into an :class:`Event`."""
    if not isinstance(obj, dict):
        raise CalendarError(f"Event #{index + 1} must be an object, got {type(obj).__name__}.")

    missing = [f for f in REQUIRED_FIELDS if f not in obj or obj[f] in (None, "")]
    if missing:
        raise CalendarError(
            f"Event #{index + 1} is missing required field(s): {', '.join(missing)}."
        )

    start = parse_datetime(obj["start"], "start", index)
    end = parse_datetime(obj["end"], "end", index)
    if end < start:
        raise CalendarError(
            f"Event #{index + 1} ('{obj['title']}') ends before it starts."
        )

    return Event(
        title=str(obj["title"]).strip(),
        start=start,
        end=end,
        location=str(obj["location"]).strip(),
    )


def parse_events(data: Union[list, dict]) -> List[Event]:
    """Parse already-decoded JSON (list or ``{"events": [...]}``) into Events.

    Events are returned sorted by start time so downstream code can rely on
    chronological order.
    """
    if isinstance(data, dict):
        raw_events = data.get("events")
    else:
        raw_events = data

    if not isinstance(raw_events, list):
        raise CalendarError(
            "Calendar must be a JSON list of events, or an object with an "
            "'events' list."
        )

    events = [parse_event(obj, i) for i, obj in enumerate(raw_events)]
    events.sort(key=lambda e: e.start)
    return events


def load_events(path: Union[str, Path]) -> List[Event]:
    """Read ``path`` and return validated, chronologically sorted events.

    Raises:
        CalendarError: if the file is missing or its contents are invalid.
    """
    file_path = Path(path)
    if not file_path.exists():
        raise CalendarError(f"Calendar file not found: {file_path}")
    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CalendarError(f"Calendar file is not valid JSON: {exc}") from exc
    return parse_events(data)
