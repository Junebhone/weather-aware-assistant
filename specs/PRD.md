# PRD — Weather-Aware Personal Assistant

| Field | Value |
|---|---|
| **Product** | Weather-Aware Personal Assistant (CLI / REPL) |
| **Version** | 1.0 |
| **Owner / Architect** | Bhone |
| **Status** | Built & shipped |
| **Last updated** | 2026-06-20 |

> This document is the **source of truth**. It was written *before* the code as a
> brief for an AI builder. It defines the **What** and the **Why** in enough
> detail that the **How** is obvious — the goal being that if you handed this PRD
> to a brand-new AI model, it would rebuild substantially the same application.

---

## 1. Summary

A small command-line assistant that reads my local calendar, fetches live
weather for each event's time and place, and **synthesises practical advice** —
the kind a thoughtful friend would give: *"It'll be raining during your 6:30
beach run — take the bus instead of cycling, and pack a rain jacket."*

It is deliberately tiny in scope and large in discipline: clean module
boundaries, deterministic logic, and tests that pin down the advice rules.

## 2. Problem & Motivation (the *Why*)

People already have two data sources that rarely talk to each other: a
**calendar** (what I'm doing and where) and a **weather forecast** (what the sky
is doing). The synthesis between them is done manually, in our heads, every
morning — and we frequently get it wrong (cycle into a downpour, forget the
umbrella, underdress for a cold commute).

The assistant automates that synthesis. The *value* is not the weather data or
the calendar data in isolation — both are commodities — it's the **decision** at
their intersection: *given this event, in this weather, what should I do
differently?*

## 3. Goals & Non-Goals

### Goals
- **G1** — Fuse a local calendar with live weather and emit actionable advice.
- **G2** — Run instantly for anyone: no API key, no paid services, no install
  step beyond having Python 3.
- **G3** — Keep advice **logic** completely separable from **presentation**, so
  the rules are unit-testable in isolation.
- **G4** — Degrade gracefully: if the network is down, still show the schedule.
- **G5** — Be re-tunable for a different climate by editing *data* (thresholds),
  not code.

### Non-Goals
- **N1** — Not a calendar editor. We read `calendar.json`; we never write it.
- **N2** — No GUI or web server in v1. The interface is a terminal REPL.
- **N3** — No multi-day trip planning, routing, or travel-time estimation.
- **N4** — No account system, no persistence of user data beyond the local file.

## 4. Target User & Persona

**"Bhone, the busy student/commuter."** Starts the day with a fixed-ish routine
(morning run, classes, a couple of meetings). Wants a 5-second glance that tells
them what today's weather *means for their actual plans* — not a wall of
meteorological numbers they have to interpret themselves.

The assistant's own voice is defined in [`../docs/rules.md`](../docs/rules.md):
practical, concise, safety-first, never preachy.

## 5. User Stories

- **US1** — *As a commuter,* when rain is expected during an event, I want to be
  told to take the bus and bring rain protection, so I don't get soaked.
- **US2** — *As a runner,* when an outdoor event coincides with bad weather, I
  want a nudge to move it indoors or reschedule.
- **US3** — *As someone who dresses for the indoors,* I want to be warned when
  it's cold/hot/freezing so I dress for the day, not the office.
- **US4** — *As a cyclist,* I want a heads-up when it's too windy or stormy to
  ride safely.
- **US5** — *As a user with no internet,* I still want to see my schedule and a
  clear note that weather couldn't be fetched, rather than a crash.
- **US6** — *As a curious user,* I want to ask for the current weather of any
  city on demand.

## 6. Functional Requirements

### 6.1 Data Sources

**Weather — Open-Meteo** (`api.open-meteo.com`).
- Chosen because it is **free and keyless** (satisfies G2). Reviewers can run
  the app with zero setup.
- We request, in metric units with `timezone=auto`: temperature, apparent
  temperature, precipitation (mm), precipitation probability (%), WMO weather
  code, wind speed (km/h), and an is-day flag.
- City names are resolved to coordinates via Open-Meteo's geocoding endpoint.

**Calendar — local `calendar.json`.**
- A list of events, each with `title`, `start`, `end`, `location`
  (see §8 for the contract).

### 6.2 Commands (REPL)

| Command | Behaviour |
|---|---|
| `brief [location]` | The headline feature. For each event, find the weather at its time/place and print the synthesised advice. |
| `weather [location]` | Current conditions for a city (defaults to home). |
| `agenda` | The plain schedule, no weather. |
| `home <location>` | Change the session's home/base city. |
| `help` | List commands. |
| `quit` / `exit` | Leave. |

The app also supports **one-shot mode** for scripting/demos:
`python run.py brief` runs the command once and exits.

### 6.3 The Advice Engine (the heart of the product)

The engine is a pure function: `advise(event, weather, thresholds) -> [Advice]`.
It evaluates the following rules **in priority order** and returns zero or more
suggestions. Cheerful "it's lovely out" advice is only emitted when nothing more
urgent fires.

#### Decision table

| # | Condition | Severity | Advice (intent) |
|---|---|---|---|
| R1 | Thunderstorm | **Warning** | Avoid open-air travel/cycling; take an enclosed ride (bus); delay outdoor plans. |
| R2 | Snow | Caution | Leave earlier; take the bus/transit over driving/biking; waterproof boots. |
| R3 | Rain / drizzle, **or** precipitation ≥ `wet_precip_mm`, **or** rain probability ≥ `rain_probability_pct` | Caution | **Take the bus instead of walking/cycling; bring an umbrella or rain jacket.** |
| R3a | …and the event is outdoors | Caution | Also suggest moving it indoors or rescheduling. |
| R4 | Fog | Caution | Leave earlier; favour transit; reduced visibility. |
| R5 | Feels-like ≤ `freezing_c` | **Warning** | Heavy coat, gloves, hat; watch for ice. |
| R6 | Feels-like ≤ `cold_c` | Caution | Warm jacket + a layer. |
| R7 | Feels-like ≤ `chilly_c` | Info | Light jacket or sweater. |
| R8 | Feels-like ≥ `hot_c` | Caution | Hydrate, light clothing, sunscreen; avoid midday exertion if outdoors. |
| R9 | Feels-like ≥ `warm_c` | Info | Pleasant; sunscreen/sunglasses if outdoors in daylight. |
| R10 | Wind ≥ `gale_wind_kmh` | **Warning** | Cycling risky; umbrellas fail; secure loose items; take the bus. |
| R11 | Wind ≥ `high_wind_kmh` | Caution | Windy; umbrella may be useless; hard cycling. |
| R12 | Fair, calm, mild, dry **and** no rule above fired | Info | Great conditions — walking/cycling is pleasant. |

**Key design points**
- **"Feels-like"** drives clothing rules: we use apparent temperature when the
  API provides it, falling back to dry-bulb. (A 20 °C day that feels like 2 °C
  should advise a coat.)
- Thresholds (`freezing_c`, `cold_c`, `hot_c`, `rain_probability_pct`, …) are
  **configuration data**, not constants in the logic (G5). Re-tuning for a cold
  climate is a config edit, not a code change.
- **Outdoor detection** is a keyword heuristic over the event title + location
  (`run`, `beach`, `park`, `bike`, …). Outdoor events get firmer advice.

#### Why rule-based and not an LLM?

The assignment allows either. I chose **rule-based synthesis** deliberately:

1. **Testability (G3).** The whole point of the Guardrails is to assert "rain ⇒
   bus." A deterministic function lets a unit test pin that down exactly; an LLM
   would make the same test flaky and unprovable.
2. **Zero-key, offline-capable (G2/G4).** No second API dependency or secret.
3. **Transparency.** The decision table *is* the spec — auditable and explicable.

An LLM layer is a clean future extension (see §12): the `Advice` objects this
engine returns could be handed to an LLM purely for *phrasing*, while the
*decisions* remain rule-based and tested.

### 6.4 Worked example (input → processing → output)

This is the `brief` command for one event, end to end, so the data flow is
unambiguous:

1. **Calendar input** — `{"title": "Sunrise Beach Run", "start":
   "...T06:30:00", "location": "Waikiki Beach, Honolulu"}`.
2. **Geocode + forecast** — `weather.py` resolves "Waikiki Beach, Honolulu" to
   coordinates and pulls the hourly forecast (cached per location).
3. **Match the hour** — `briefing.match_hourly` finds the 06:00 forecast slot:
   `WeatherSnapshot(category=RAIN, temp=23 °C, precip_prob=80%, wind=18 km/h)`.
4. **Outdoor check** — `advisor.is_outdoor_event` sees "run" + "Beach" ⇒ outdoor.
5. **Apply rules** — R3 (wet) fires ⇒ *bus + rain protection*; R3a (wet +
   outdoor) ⇒ *move indoors/reschedule*. Temp 23 °C and wind 18 km/h trip no
   threshold, so no clothing/wind advice; positive advice is suppressed because
   higher-severity advice already fired.
6. **Render** — `formatting.py` turns the `Advice` objects into:

   ```text
   🔹 06:30–07:15  Sunrise Beach Run @ Waikiki Beach, Honolulu
      🌧️ 23°C, Slight rain, wind 18 km/h, rain 80%
      🌧️ Rain is likely — take the bus instead of walking or cycling, and pack an umbrella or a waterproof jacket.
      🏠 This looks like an outdoor activity in the wet — consider moving it indoors or rescheduling to a drier window.
   ```

7. **Print** — `cli.py` writes that string to the terminal. Steps 1–6 contain
   no `print`; only step 7 does.

## 7. Architecture & Separation of Concerns

The non-negotiable architectural rule: **logic never prints; UI never decides.**

```
        calendar.json            Open-Meteo API
             │                         │
   calendar_loader.py            weather.py
   (read + validate)        (fetch ◇ + pure parse)
             │                         │
             └──────────┬──────────────┘
                        ▼
                   briefing.py
        (pair each event with its weather,
         call the advisor — no I/O)
                        ▼
                   advisor.py
     ┌── THE BRAIN: advise(event, weather) -> [Advice] ──┐
     │   pure rules, no I/O, no print — fully unit-tested │
                        ▼
                  formatting.py
          (Advice/data  ->  display strings; pure)
                        ▼
                     cli.py
        (the REPL: the ONLY module that prints
         and reads input — the composition root)

  models.py  — pure data types shared by all layers
  config.py  — thresholds & settings as data
   ◇ = the single point of network contact
```

- **Pure logic, no I/O:** `models`, `config`, `advisor`, `briefing`,
  `weather.parse_*`, `formatting`.
- **I/O at the edges only:** `weather._http_get_json` (network),
  `calendar_loader.load_events` (file), `cli` (stdin/stdout).
- **Dependency injection:** `briefing.build_daily_briefing` takes a `lookup`
  callable, so production uses the live client and tests use an in-memory stub.
  No network ever runs in the test suite.

## 8. Data Contracts

### `calendar.json`
A JSON object with an `events` list (a bare list is also accepted). Each event:

```json
{
  "title": "Sunrise Beach Run",
  "start": "2026-06-20T06:30:00",
  "end":   "2026-06-20T07:15:00",
  "location": "Waikiki Beach, Honolulu"
}
```

- `title` — string, non-empty.
- `start` / `end` — ISO-8601 datetimes; `end` ≥ `start`.
- `location` — string; resolvable to a city for weather (else falls back to home).
- Events are loaded **sorted by start**.
- **Routine semantics:** event *times* are matched to the **current day's**
  forecast by hour-of-day, so a calendar of typical daily events produces a
  meaningful briefing on whatever date the app is run.

### `Advice` (engine output)
`{ category, severity, message, icon }` where `category ∈ {commute, clothing,
health, safety, general}` and `severity ∈ {info, caution, warning}`.

## 9. Non-Functional Requirements

- **NFR1 — No external dependencies.** Standard library only (`urllib`, `json`,
  `datetime`, `dataclasses`, `unittest`). Run with nothing but Python 3.9+.
- **NFR2 — Resilience.** Any network/parse failure raises `WeatherUnavailable`,
  which the briefing and CLI catch; the schedule still renders (G4).
- **NFR3 — Determinism.** No `datetime.now()` / randomness in logic modules; the
  CLI injects "today" at the edge so tests stay reproducible.
- **NFR4 — Small files.** Each module is single-purpose and short.
- **NFR5 — Network politeness.** One geocode + one forecast per unique location,
  cached for the briefing.

### 9.1 Edge cases & error handling

The assistant is expected to handle the following without crashing:

| Situation | Expected behaviour |
|---|---|
| No internet / API down / timeout | `WeatherUnavailable` is caught; schedule still shows, with a "(weather unavailable)" note. |
| Event location is a descriptive venue ("X Building, City") | Geocoding falls back from the full string → its city → home base, so it still resolves (`weather.location_candidates`). |
| City name truly not found by geocoder | `weather <city>` shows a friendly "Could not find a place called '…'."; in a briefing the event is marked "(weather unavailable)". |
| `calendar.json` missing | Clear `CalendarError`: "Calendar file not found: …". |
| `calendar.json` not valid JSON | `CalendarError` quoting the JSON parse error. |
| Event missing a field / bad datetime / `end` < `start` | `CalendarError` naming the event index and the problem. |
| Empty calendar | Valid; briefing says "Your calendar is empty. Enjoy the open day!". |
| Event date outside the forecast window | Matched to today's forecast by hour-of-day (routine semantics). |
| Unknown WMO weather code | Categorised as `UNKNOWN` with a descriptive label, never an exception. |
| Unknown REPL command | "Unknown command: '…'. Type 'help' for options." |
| Exception inside a command | Caught by the REPL guard; prints a message, loop continues. |

## 10. Testing Strategy & Acceptance Criteria

Tests live in `tests/` and run with `python -m unittest discover -s tests` —
**no network, no dependencies.** The suite is **83 tests** across 8 files and
completes in well under a second. The network is never touched: weather is
served from a captured fixture (`tests/fixtures/sample_forecast.json`) and an
injected in-memory lookup.

**Acceptance criteria → the test(s) that prove them (traceability):**

| AC | Requirement | Proven by |
|---|---|---|
| **AC1** | Rain (or high rain probability) ⇒ advice says "bus" + rain protection *(the canonical rubric test)* | `test_advisor.RainCommuteRules`, `test_briefing.test_rainy_morning_run_gets_bus_advice`, `test_cli.test_brief_gives_weather_aware_advice` |
| **AC2** | Clear, mild weather ⇒ no "bus"/"umbrella"; severity stays Info | `test_advisor.test_clear_weather_does_not_suggest_a_bus_or_umbrella`, `test_advisor.PleasantWeather` |
| **AC3** | Thunderstorm / freezing / gale wind ⇒ Warning severity | `test_advisor.SevereWeatherRules`, `test_advisor.test_freezing_warns_about_ice` |
| **AC4** | Hot ⇒ hydrate + sunscreen; Cold ⇒ jacket/coat | `test_advisor.TemperatureRules`, `test_advisor.CombinedAndBoundaryRules` |
| **AC5** | Thresholds are data: same weather flips outcome under different `Thresholds` | `test_advisor.ThresholdsAreData`, `test_config.*` |
| **AC6** | WMO codes map correctly; Open-Meteo JSON parses into right snapshots | `test_weather.CategorizeWmoCodes`, `test_weather.ParseCurrent`, `test_weather.ParseHourly` |
| **AC7** | Malformed calendars raise a clear `CalendarError` | `test_calendar_loader.Validation`, `test_calendar_loader.LoadFromDisk` |
| **AC8** | Missing weather degrades gracefully (briefing + CLI still work) | `test_briefing.test_missing_weather_degrades_gracefully`, `test_cli.test_brief_offline_still_shows_the_schedule` |
| **AC9** | Output surfaces the right content (bus advice, unavailable notes, agenda) | `test_formatting.*` |
| **AC10** | **Architecture is enforced:** logic modules never `print`/`input`; the brain doesn't import the UI | `test_architecture.*` |

**Guardrails-as-architecture.** AC10 is unusual and deliberate: `test_architecture.py`
parses the source of every logic module and fails the build if any of them calls
`print()`/`input()`, or if the advice engine imports the UI/network layers. The
rubric's "logic separated from UI" is therefore not a convention we hope holds —
it is a property the test suite *guarantees* on every run.

## 11. Key Design Decisions (rationale)

| Decision | Rationale |
|---|---|
| Open-Meteo over OpenWeather | Free **and keyless** → reviewers run it instantly. |
| Rule-based advice | Deterministic ⇒ testable, transparent, offline. |
| Thresholds as config data | Re-tune for any climate without touching logic. |
| `lookup` injected into briefing | Lets the whole pipeline run offline in tests. |
| Match events to *today's* forecast by hour | Demo works on any run date. |
| `Advice` as data, not strings | Formatting/voice changeable without touching rules. |

## 12. Out of Scope / Future Work

- **LLM phrasing layer:** feed the rule-derived `Advice` list to an LLM to
  rephrase in a chosen persona, keeping decisions deterministic.
- **Travel-time + leave-by times** using a routing API.
- **Notifications** (a morning push of the day's brief).
- **Calendar sync** (Google/ICS) replacing the local file.

## 13. Success Metrics

- A reviewer clones, runs `python -m unittest`, and sees green — **with no
  setup** (proves G2/G3).
- `python run.py brief` returns sensible, weather-appropriate advice for the
  sample day (proves G1).
- Killing the network still yields a readable briefing (proves G4).

## 14. Assumptions & Open Questions

**Assumptions** (true for v1; revisit if they break):
- The user runs Python 3.9+ and has occasional internet for live weather.
- Open-Meteo's free tier and current response shape remain stable.
- A calendar represents a typical **daily routine**, so matching event times to
  *today's* forecast by hour-of-day is meaningful (see §6.4 / Data Contracts).
- Metric units are acceptable as the default.
- One forecast location per event is sufficient (no multi-leg journeys).

**Open questions** (deferred, not blocking):
- Should advice consider the *commute window before* an event, not just its
  start hour? (e.g. leave-by time.) — leaning yes, future work.
- For multi-day calendars, do we brief "today only" or the whole forecast
  window? v1 briefs by matched hour; a `--date` selector is a likely addition.
- Is an optional LLM phrasing layer worth the added dependency/key for the
  persona gain? (See §6.3 and §12.) — only behind a flag, decisions stay rule-based.
- Should units (°C/°F, km/h/mph) be user-configurable in v1? Currently metric-only.
