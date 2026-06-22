"""Command-line REPL — the user-facing edge of the assistant.

This is the *only* module that performs terminal I/O (``input``/``print``).
Everything below it speaks in data. The command handlers return strings rather
than printing them, so the routing logic itself stays testable; the REPL loop
is the single place that actually writes to the screen.

``Assistant`` is the composition root: it wires the config, the Open-Meteo
client, the calendar and the briefing logic together. Swap the client for a
fake here and the whole app runs offline.
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Sequence

from . import advisor, formatting
from .briefing import build_daily_briefing, make_lookup
from .calendar_loader import CalendarError, load_events
from .config import AppConfig
from .models import Event
from .weather import OpenMeteoClient, WeatherUnavailable

DEFAULT_CALENDAR = Path(__file__).resolve().parent.parent / "calendar.json"


class Assistant:
    """Holds session state and turns a typed command into response text."""

    def __init__(
        self,
        config: AppConfig,
        client: Optional[OpenMeteoClient] = None,
        calendar_path: Path = DEFAULT_CALENDAR,
    ) -> None:
        self.config = config
        self.client = client or OpenMeteoClient(timeout_s=config.request_timeout_s)
        self.calendar_path = calendar_path

    # -- command handlers: each returns text for the caller to display --------

    def cmd_help(self) -> str:
        return formatting.render_help()

    def cmd_home(self, location: str) -> str:
        if not location:
            return f"Home base is {self.config.home_location}. Use: home <location>"
        self.config = self.config.with_home(location)
        return f"🏠 Home base set to {self.config.home_location}."

    def cmd_agenda(self) -> str:
        try:
            events = load_events(self.calendar_path)
        except CalendarError as exc:
            return f"⚠️  {exc}"
        return formatting.render_agenda(events)

    def cmd_weather(self, location: str) -> str:
        place = location or self.config.home_location
        try:
            snapshot = self.client.current(place)
        except WeatherUnavailable as exc:
            return f"⚠️  {exc}"
        tips = advisor.general_advice(snapshot, self.config.thresholds)
        return formatting.render_weather(snapshot, tips)

    def cmd_brief(self, location: str) -> str:
        try:
            events = load_events(self.calendar_path)
        except CalendarError as exc:
            return f"⚠️  {exc}"

        config = self.config.with_home(location) if location else self.config
        lookup = make_lookup(self.client, config)
        briefing = build_daily_briefing(
            events,
            lookup,
            location=config.home_location,
            thresholds=config.thresholds,
            on_date=datetime.now().date(),
            keywords=config.outdoor_keywords,
        )
        return formatting.render_daily_briefing(briefing)

    # -- routing --------------------------------------------------------------

    def handle(self, line: str) -> str:
        """Route one line of input to a handler and return response text."""
        parts = line.strip().split(maxsplit=1)
        if not parts:
            return ""
        command = parts[0].lower()
        argument = parts[1].strip() if len(parts) > 1 else ""

        if command in {"help", "?"}:
            return self.cmd_help()
        if command in {"brief", "briefing", "today"}:
            return self.cmd_brief(argument)
        if command in {"weather", "now"}:
            return self.cmd_weather(argument)
        if command in {"agenda", "schedule"}:
            return self.cmd_agenda()
        if command == "home":
            return self.cmd_home(argument)
        return f"Unknown command: '{command}'. Type 'help' for options."


def run_repl(assistant: Assistant, stream=sys.stdout) -> None:
    """The interactive loop. The single place that prints and reads input."""
    print(formatting.render_banner(assistant.config.home_location), file=stream)
    while True:
        try:
            line = input("\nassistant> ")
        except (EOFError, KeyboardInterrupt):
            print("\n👋 Goodbye!", file=stream)
            return

        command = line.strip().lower()
        if command in {"quit", "exit", "q"}:
            print("👋 Goodbye!", file=stream)
            return

        try:
            response = assistant.handle(line)
        except Exception as exc:  # last-resort guard: never crash the REPL
            response = f"⚠️  Something went wrong: {exc}"
        if response:
            print(response, file=stream)


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Entry point. With no arguments, start the REPL; with arguments, run one
    command and exit (handy for scripting and demos: ``python -m weather_assistant brief``).
    """
    argv = list(sys.argv[1:] if argv is None else argv)
    assistant = Assistant(AppConfig.from_env())

    if argv:
        print(assistant.handle(" ".join(argv)))
        return 0

    run_repl(assistant)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
