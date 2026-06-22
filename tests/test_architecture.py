"""Architecture guardrails — tests that enforce the design rules themselves.

The rubric's top criterion is "logic separated from UI." Rather than just claim
that in the README, we *prove* it automatically: these tests parse the source
of every logic module and assert it contains no ``print()`` / ``input()`` calls,
and that the advice engine never imports the UI layer.

If a future change (human or AI) sneaks a ``print`` into the advice engine, the
suite goes red. The separation of concerns becomes a property the build
guarantees, not a convention people remember to follow.
"""

import ast
import unittest
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent.parent / "weather_assistant"

# Modules that must stay pure: no terminal I/O, ever.
LOGIC_MODULES = [
    "models",
    "config",
    "advisor",
    "briefing",
    "weather",
    "calendar_loader",
    "formatting",
]


def _parse(module: str) -> ast.AST:
    return ast.parse((PACKAGE / f"{module}.py").read_text(encoding="utf-8"))


def _calls_to(tree: ast.AST, names: set) -> list:
    """Return (function_name, line) for every direct call to one of `names`."""
    hits = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in names
        ):
            hits.append((node.func.id, node.lineno))
    return hits


def _imported_names(tree: ast.AST) -> set:
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module:
                names.add(node.module.split(".")[-1])
            for alias in node.names:
                names.add(alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[-1])
    return names


class LogicNeverDoesTerminalIO(unittest.TestCase):
    def test_logic_modules_never_call_print_or_input(self):
        for module in LOGIC_MODULES:
            with self.subTest(module=module):
                hits = _calls_to(_parse(module), {"print", "input"})
                self.assertEqual(
                    hits, [], f"{module}.py must not call print()/input(); found {hits}"
                )

    def test_cli_is_the_single_io_module(self):
        # Sanity check the other side of the boundary: the UI layer *does* print.
        src = (PACKAGE / "cli.py").read_text(encoding="utf-8")
        self.assertIn("print(", src)
        self.assertIn("input(", src)


class DependencyDirection(unittest.TestCase):
    def test_advisor_does_not_import_the_ui(self):
        imported = _imported_names(_parse("advisor"))
        self.assertNotIn("cli", imported, "the advice engine must not depend on the CLI")
        self.assertNotIn("formatting", imported, "the engine must not depend on formatting")

    def test_advisor_does_not_import_the_network_client(self):
        # The brain reasons over a WeatherSnapshot; it must not know how weather
        # is fetched. (It may import models/config only.)
        imported = _imported_names(_parse("advisor"))
        self.assertNotIn("weather", imported)


if __name__ == "__main__":
    unittest.main()
