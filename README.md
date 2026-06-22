# 🌤️ Weather-Aware Personal Assistant

A CLI / REPL personal assistant that reads my calendar, checks live weather for
each event, and **synthesises practical advice** — *"Rain during your 6:30 beach
run — take the bus instead of cycling and pack a jacket."*

Built for the **"Don't Code, Orchestrate"** lab: I acted as the **architect**,
steering an AI agent to build a modular system from a written
[PRD](specs/PRD.md) and [rules](docs/rules.md), rather than typing the code
myself. The reflection on that collaboration is the [Vibe Report](#-the-vibe-report) below.

- ✅ **No API key** — uses the free, keyless [Open-Meteo](https://open-meteo.com) API
- ✅ **No dependencies** — Python 3 standard library only
- ✅ **No install step** — clone and run
- ✅ **Logic fully separated from UI**, and **83 tests** that never touch the network

---

## What it does

```text
🗓️  Daily Briefing — Saturday, 20 June 2026  (Honolulu)

🔹 06:30–07:15  Sunrise Beach Run @ Waikiki Beach, Honolulu
   🌧️ 23°C, Slight rain, wind 18 km/h, rain 80%
   🌧️ Rain is likely — take the bus instead of walking or cycling, and pack an umbrella or a waterproof jacket.
   🏠 This looks like an outdoor activity in the wet — consider moving it indoors or rescheduling to a drier window.

🔹 12:30–13:30  Client Lunch @ Kakaako, Honolulu
   ☀️ 29°C, Clear sky, wind 14 km/h, rain 5%
   🥵 Hot out (~31°C) — hydrate well, wear light clothing and sunscreen, and seek shade where you can.

🔹 15:00–16:30  Afternoon Lecture @ Campus Center, UH Manoa, Honolulu
   ⛈️ 28°C, Thunderstorm, wind 22 km/h, rain 90%
   ⛈️ Thunderstorms expected — avoid open-air travel and cycling. Take the bus or another enclosed ride, and delay any outdoor plans.
```

## Quickstart

> Requires **Python 3.9+**. Nothing to install.

```bash
# Interactive REPL
python run.py

# …or one-shot commands
python run.py brief            # weather-aware rundown of the day
python run.py weather Tokyo    # current conditions anywhere
python run.py agenda           # the schedule, no weather

# Point it at your own city (no code change)
WA_HOME_LOCATION="Berlin" python run.py brief
```

Inside the REPL: `brief`, `weather [city]`, `agenda`, `home <city>`, `help`, `quit`.

## Run the tests

```bash
python -m unittest discover -s tests        # standard library, zero setup
# or, if you have it:  pytest
```

All 83 tests run **offline** — weather is faked from fixtures and an injected
lookup, so the suite is fast and deterministic.

## Project structure

```
VibeCode/
├── run.py                     # zero-install launcher
├── calendar.json              # the local schedule (you edit this)
├── specs/
│   └── PRD.md                 # ← source of truth: the What & Why
├── docs/
│   └── rules.md               # ← persona + engineering constraints
├── weather_assistant/         # the app (small, single-purpose modules)
│   ├── models.py              # pure data types
│   ├── config.py              # thresholds & settings (data, not magic numbers)
│   ├── weather.py             # Open-Meteo client: network isolated from parsing
│   ├── calendar_loader.py     # read + validate calendar.json
│   ├── advisor.py             # THE BRAIN — pure advice rules
│   ├── briefing.py            # orchestration (calendar + weather + advice)
│   ├── formatting.py          # data → display strings (pure)
│   └── cli.py                 # the REPL — the ONLY module that prints
└── tests/                     # the guardrails (83 tests, no network)
```

## Architecture in one sentence

**Logic never prints; UI never decides.** The advice engine is a pure function
`advise(event, weather, thresholds) -> [Advice]`; the network lives behind a
single function; the REPL is the only place that does I/O. Full diagram and the
advice **decision table** are in the [PRD](specs/PRD.md#63-the-advice-engine-the-heart-of-the-product).

## Configuration

All behaviour-defining numbers (cold/hot/freezing temperatures, wind and rain
thresholds) live in [`config.py`](weather_assistant/config.py) as data, so the
assistant can be re-tuned for any climate without touching the logic. Tests
exploit this to prove the rules are data-driven, not hardcoded.

---

## 🧭 The Vibe Report

> *Reflection on orchestrating the AI build. The professor is grading the
> thinking process, so here is where the steering actually happened.*

I gave the AI the [PRD](specs/PRD.md) and [rules.md](docs/rules.md) as context
**first**, then had it build module by module. Treating those two documents as
the durable "memory" of the project — and re-pointing the AI back at them
whenever it wandered — was the single biggest lever I had. Here's where it
mattered.

### 1. Where did the AI's "vibe" drift?

Three drifts, all in the same direction — **the AI kept wanting to collapse my
layers back together** because that's the path of least resistance:

- **Print statements leaking into the brain.** Asked to "give weather advice,"
  the AI's instinct was to write `print("It's raining, take the bus")` *inside*
  the advice function. That's the most natural way to write a script — and it
  quietly fuses logic and UI, which is exactly what the rubric (and rule **B1**)
  forbid. I had to keep insisting the engine **return `Advice` objects** and let
  a separate `formatting`/`cli` layer decide how they're shown.
- **Magic numbers creeping back in.** It liked writing `if temp < 10:` directly
  in the rules. Readable, but it buries policy in logic. I steered every
  threshold out into `config.Thresholds` so the rules read `if temp <=
  thresholds.cold_c` and a test can flip the threshold to prove the rule is
  data-driven.
- **Tests that quietly phone home.** Its first test instinct was to call the
  *real* Open-Meteo API and assert on whatever came back — which makes the suite
  slow, flaky, and offline-hostile. I redirected it to capture one real response
  as a fixture and **inject** a fake weather lookup into the briefing, so the
  whole pipeline is tested with the network unplugged.
- **A smaller one — over-reaching for dependencies.** It reached for `requests`
  and (later) an LLM call for the phrasing. I held the line on *standard library
  only* and *rule-based synthesis* so a reviewer can run everything with a bare
  Python install and zero keys. Documented the LLM idea as future work instead.

The pattern: the AI optimises for "fewest lines to working output." My job as
architect was to optimise for "boundaries that survive contact with a test."

### 2. When did I reach for the "Builder Hammer"?

Twice the AI produced something that *ran* but was *logically wrong*, and I had
to step in and design the fix by hand:

- **The forecast-matching bug (the big one).** My `calendar.json` has events on
  fixed dates, but a live forecast only covers the next few days. The AI's first
  pass matched an event to weather by **exact timestamp** — so the moment the
  calendar date fell outside the forecast window, *every* event came back
  "weather unavailable" and the headline feature was dead on arrival. I hand-wrote
  the three-tier `match_hourly` fallback in `briefing.py`: exact (date, hour) →
  **same hour-of-day on today's forecast** → nearest hour. That "same hour-of-day"
  rule is the insight that makes a routine calendar produce a real briefing on
  *any* day you run it. It's also now pinned by its own test.
- **Cheerful advice during a thunderstorm.** The engine happily appended "Great
  conditions — enjoy a walk!" *next to* a storm warning, because each rule fired
  independently. I added the guard that positive advice is only emitted when no
  higher-severity rule fired. Small change, but it's the difference between an
  assistant that feels thoughtful and one that feels broken.

Both were cases where the code's *behaviour* looked fine in a quick demo and was
only exposed as wrong by thinking through the edge cases — which is precisely
what the tests now encode.

### 3. My most successful "steering" prompt

> **"The advice engine is a pure function: it takes an event and a weather
> snapshot and *returns a list of Advice objects*. It must never print and never
> fetch anything. The CLI is the only module allowed to print. Put every
> threshold in config, not in the rules."**

That one constraint did all the heavy lifting. By forcing the brain to *return
data instead of producing output*, the clean architecture fell out almost for
free: the briefing orchestrator, the injectable weather lookup, the pure
formatter, and — most importantly — the ability to write `assertIn("bus",
advice_text)` as a real unit test. Nearly every "Exceptional" box on the rubric
traces back to that single sentence about purity. Everything after it was
elaboration.

### What I learned about context management

The PRD and `rules.md` were my **context anchors**. Whenever the AI drifted, the
fastest fix wasn't a clever new prompt — it was *"re-read rule B1 and try
again."* Writing the constraints down once, up front, and pointing back at them
beat re-explaining my intent every turn. If I handed this PRD to a fresh model
tomorrow, the decision table and the engineering rules are explicit enough that
it would rebuild the same app — which, per the peer-review prompt, is the whole
point.

---

## A note on how this was built

In the spirit of the assignment, the code was generated by an AI agent under my
direction; I wrote the [PRD](specs/PRD.md) and [rules](docs/rules.md), set the
architecture, reviewed every module against those constraints, and hand-fixed
the logic errors described above. The reflection above is my own account of that
collaboration.
