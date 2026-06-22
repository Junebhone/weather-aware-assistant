#!/usr/bin/env python3
"""Convenience launcher so reviewers can just run ``python run.py``.

It avoids any install step: the package lives alongside this file, so we simply
hand control to the CLI entry point.
"""

from weather_assistant.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
