# Rules — Persona & Constraints

This file is the operating manual the AI builder was steered with. It has two
parts:

- **Part A — the Assistant's persona:** the voice and values of the *product*.
- **Part B — engineering constraints:** the rules the *AI agent* had to obey
  while building it (the architect's guardrails).

Together with [`../specs/PRD.md`](../specs/PRD.md) these two files are the
"context" that should let any capable AI rebuild the same app with the same
character.

---

## Part A — The Assistant's Persona

**Who it is:** a calm, practical friend who happens to have checked the weather
for you. Think a good cycling buddy, not a TV meteorologist.

**Voice & tone**
- **Practical first.** Lead with the action ("take the bus"), not the data.
- **Concise.** One sentence per suggestion. No paragraphs.
- **Warm, never preachy.** Advise; don't lecture or moralise.
- **Honest about uncertainty.** "Rain is *likely*," not "it *will* rain."
- **Plain language.** "Feels like 2 °C," not "apparent temperature 2.1 °C."

**Values (in priority order)**
1. **Safety** — storms, ice, and gale winds are flagged loudest (Warning).
2. **Comfort** — dress right, stay dry, stay hydrated.
3. **Convenience** — sensible commute swaps (bus when cycling is miserable).
4. **Encouragement** — when it's genuinely nice out, say so and nudge a walk.

**Hard product rules**
- **Never invent weather.** If data can't be fetched, say so plainly and show
  the schedule anyway. A wrong forecast is worse than an honest "unavailable."
- **Default to caution for outdoor events.** A beach run in the rain gets firmer
  advice than a meeting in a building.
- **Metric units**, matching the data source, unless reconfigured.
- **Don't nag.** If conditions are unremarkable, the right output is a short
  "you're good to go," not manufactured concern.

**Voice examples — say this, not that:**

| Situation | ✅ Say | ❌ Don't say |
|---|---|---|
| Rain during a commute | "Rain is likely — take the bus and pack a jacket." | "Precipitation probability is 80%; consider your mobility options." |
| Cold morning | "Cold out (~4°C) — bundle up with a warm jacket." | "You should really wear a coat or you'll regret it." |
| Lovely day | "Great conditions — walking or cycling will be pleasant." | "Weather is acceptable for outdoor transit modalities." |
| Weather can't be fetched | "(weather unavailable)" + show the schedule | *(silence, or a fake/guessed forecast)* |
| Nothing notable | "Nothing to flag — you're good to go." | A paragraph manufacturing mild concerns. |

These examples are the persona's fingerprint: lead with the action, keep it to a
sentence, stay warm, and never invent data.

---

## Part B — Engineering Constraints (rules for the AI builder)

These are the non-negotiables I held the AI to while it generated the code.
They map directly onto the grading rubric.

### B1. Separation of concerns (logic ≠ UI)
- **Logic modules must not print** and must not read input. `advisor`,
  `briefing`, `weather` (parsing), `calendar_loader`, `models`, `config` contain
  **zero** `print()` / `input()` calls.
- **`cli.py` is the only module allowed to do terminal I/O.**
- `formatting.py` converts data → strings but never prints them itself.
- *Test of compliance:* enforced automatically by `tests/test_architecture.py`,
  which parses every logic module's AST and fails if it finds a `print()`/`input()`
  call. (Quick manual check: `grep -rn "print(" weather_assistant/` hits only `cli.py`.)

### B2. The advice engine is a pure function
- Signature: `advise(event, weather, thresholds) -> List[Advice]`.
- No network, no clock, no files, no globals. Same inputs → same outputs,
  always. This is what makes the rules testable.

### B3. Isolate the network ("humble object")
- Exactly one function (`weather._http_get_json`) touches the network.
- Everything else is pure parsing over plain dicts, tested with fixtures.
- The test suite must pass **with the network unplugged.**

### B4. Configuration over magic numbers
- Every threshold (temperatures, wind, rain probability) lives in
  `config.Thresholds` as data and is injected into the logic. No bare numeric
  literals deciding behaviour inside `advisor.py`.

### B5. Fail soft
- Network/parse problems raise `WeatherUnavailable`; bad calendars raise
  `CalendarError`. Both are caught at the edges and turned into a friendly line.
  The REPL must never crash on a single bad command.

### B6. Small, single-purpose files
- One responsibility per module. If a file starts mixing fetching, deciding, and
  printing, split it.

### B7. Zero dependencies
- Standard library only. A reviewer must be able to run the app and the tests
  with a bare Python 3 install — no `pip install`, no API key.

### B8. Tests are part of "done"
- Core logic is not considered built until a test asserts its behaviour —
  especially the canonical rule: **rain ⇒ suggest the bus.**

### B9. Determinism in logic
- No `datetime.now()` / `random` inside logic modules. "Now" is injected by the
  CLI at the edge so tests stay reproducible.

> If a generated change violated any rule in Part B, it was rejected and
> re-steered — see the **Vibe Report** in the README for where that happened.

---

## Part C — Definition of Done & Steering Patterns

### Definition of Done (a change isn't "done" until all of these hold)
- [ ] New behaviour lives in the right layer (logic vs UI per **B1**).
- [ ] Any new advice rule is added to the PRD decision table **and** has a test.
- [ ] Thresholds/strings that encode policy live in `config.py`, not in logic (**B4**).
- [ ] `python -m unittest discover -s tests` is green, **offline**.
- [ ] `tests/test_architecture.py` still passes (no `print`/`input` leaked into logic).
- [ ] Failure modes degrade gracefully; nothing new can crash the REPL (**B5**).
- [ ] No new third-party dependency and no API key introduced (**B7**).

### Steering patterns that worked (for re-steering a drifting agent)
- **Name the layer.** "This belongs in `formatting`, not `advisor` — the engine
  returns `Advice`, it doesn't format." Anchors the fix to a rule, not taste.
- **Demand the test first.** "Before you change the rule, write the failing test
  that captures the behaviour we want." Forces intent to be explicit.
- **Point back at the doc.** "Re-read **B1** and try again" beats re-explaining.
  The PRD and this file are the durable context; reuse them instead of re-typing.
- **Constrain, don't dictate.** Give the *property* ("pure function, no I/O"),
  not the line-by-line code — then let the agent fill it in and verify against
  the constraint.
- **One concern per turn.** Fix the separation, run tests, *then* tune the rule.
  Bundled asks are where drift hides.
