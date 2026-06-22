"""Weather-Aware Personal Assistant.

A small, modular CLI assistant that fuses a local calendar with live weather
and synthesises practical, rule-based advice ("rain at 7am — take the bus to
your beach run instead of cycling").

Package layout (each file small and single-purpose):
    models.py           pure data types (no logic, no I/O)
    config.py           tunable thresholds and settings (data, not magic numbers)
    weather.py          Open-Meteo client; network isolated from pure parsing
    calendar_loader.py  read + validate calendar.json
    advisor.py          the advice engine — pure rules, the heart of the app
    briefing.py         orchestrates calendar + weather + advice (no I/O)
    formatting.py       data -> display strings (pure; no printing)
    cli.py              the REPL — the only module that prints / reads input
"""

__version__ = "1.0.0"
