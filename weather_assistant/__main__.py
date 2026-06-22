"""Allow ``python -m weather_assistant`` to launch the assistant."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
