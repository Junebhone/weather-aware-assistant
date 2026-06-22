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

My intent lived in two documents — the [PRD](specs/PRD.md) and
[rules.md](docs/rules.md) — and they were the project's durable memory: the thing
I re-pointed the AI back at whenever it wandered. But the honest story has two
phases. **Phase one** was a fast build from a high-level brief — the AI scaffolded
the whole modular system in one pass, and it *looked* finished. **Phase two**,
where the real architecture work happened, was running the app, watching it lie or
break, and steering the fixes. My single most effective steer wasn't a clever
prompt at all — it was *pasting the wrong output back and saying "this isn't
right."* Here's where it mattered.

### 1. Where did the AI's "vibe" drift?

The drifts came in two flavours.

**Design-time drift — the AI kept collapsing my layers back together,** because
that's the path of least resistance:
- **Print statements leaking into the brain.** Asked to "give weather advice," its
  instinct was `print("take the bus")` *inside* the advice function — fusing logic
  and UI, exactly what rule **B1** forbids. I kept insisting the engine *return
  `Advice` objects* and let `formatting`/`cli` decide how they're shown.
- **Magic numbers creeping in.** It wrote `if temp < 10:` in the rules; I steered
  every threshold into `config.Thresholds` so a test can flip it and prove the rule
  is data-driven.
- **Tests that quietly phone home.** Its first tests called the *real* API; I
  redirected them to a captured fixture plus an injected fake lookup, so the whole
  suite runs with the network unplugged.
- **Reaching for dependencies.** It wanted `requests`, then an LLM for the phrasing.
  I held the line on standard-library-only and rule-based synthesis, and parked the
  LLM idea as documented future work.

**Runtime drift — code that read fine but was wrong in the real world.** These only
surfaced because I *ran* it:
- **Geocoding the full venue string.** The AI geocoded `"POST Building, UH Manoa,
  Honolulu"` verbatim. Open-Meteo only matches place *names*, so every event came
  back "weather unavailable" and the headline feature looked dead. The code was
  perfectly reasonable; reality disagreed.
- **A `brief <location>` argument that did nothing visible.** Its first design let
  the location set only a header *label* while each event quietly used its own place
  — so `brief san jose` printed "(san jose)" above five lines of *Honolulu* weather.
  Looked like a bug; was really a confused design.

The pattern: the AI optimises for "fewest lines to working output." My job was to
optimise for "behaviour that survives contact with a test *and* a real run."

### 2. When did I reach for the "Builder Hammer"?

Four times the AI produced something that *ran* but was *wrong*, and I had to step
in and design the fix:

- **The geocoding fallback (caught live).** The first time I ran `brief` and saw
  five "weather unavailable" lines, I knew the venue strings weren't resolving. The
  fix wasn't "try harder" — it was a design: `location_candidates()` walks a
  location from specific to general (`"POST Building, UH Manoa, Honolulu"` →
  `"UH Manoa, Honolulu"` → `"Honolulu"`) and the lookup tries each until one
  resolves, then falls back to home. Pure, and pinned by tests.
- **The `brief <location>` redesign (caught live).** When `brief san jose` showed a
  San-Jose header over Honolulu weather, I changed the semantics so the argument
  weathers *every* event as if you were there, plus a note that makes the mode
  explicit. A UX bug only a real run exposes.
- **The forecast-matching bug.** Matching an event to weather by *exact timestamp*
  meant any calendar date outside the forecast window returned nothing. I hand-wrote
  the three-tier `match_hourly`: exact (date, hour) → **same hour-of-day on today's
  forecast** → nearest. That middle tier is what lets a routine calendar work on any
  day you run it.
- **Cheerful advice during a thunderstorm.** Each rule fired independently, so
  "enjoy a walk!" appeared *beside* a storm warning. I added the guard that positive
  advice only fires when nothing more urgent did.

Every one looked fine in the code and fine on a quick read. They were exposed only
by running the thing — which is exactly why those behaviours are now tests.

### 3. My most successful "steering" prompt

Two kinds of steering mattered, and the second surprised me.

**The architectural prompt** that set the whole shape:
> *"The advice engine is a pure function: it takes an event and a weather snapshot
> and returns a list of Advice objects. It must never print and never fetch
> anything. The CLI is the only module allowed to print. Put every threshold in
> config, not in the rules."*

By forcing the brain to *return data instead of producing output*, the clean
architecture fell out for free — the injectable lookup, the pure formatter, and the
ability to write `assertIn("bus", advice_text)` as a real test. Most "Exceptional"
boxes on the rubric trace back to that one sentence.

**But the steer that fixed the most bugs wasn't a prompt — it was running the app
and pasting the wrong output back.** "I don't think `brief` is working properly,"
with the actual five-line failure underneath, did more than any description could:
it dropped the AI into the real failure and let it work backwards to the cause. With
a capable agent, *demonstrating* the wrong behaviour is a higher-bandwidth steer than
*explaining* the right one.

### 4. Context management — keeping a long session coherent

This wasn't one prompt; it was a long session that ran build → tests → docs → live
debugging → deploy. Two habits kept the AI from drifting as the context grew:

- **Durable anchors over repeated explanation.** The PRD and `rules.md` are the
  project's memory. When the AI slipped, the cheapest fix was *"re-read rule B1 and
  try again,"* not re-describing my intent. The decision table and the
  acceptance-criteria→test map are *compressed context*: hand either to a fresh model
  and it can rebuild the same app without me in the loop — which is exactly the
  peer-review test.
- **One concern per turn.** Fix the separation, run the tests, *then* tune a rule.
  Bundled asks are where drift hides, so I kept each turn to a single change and
  re-verified before moving on.

### 5. Keeping the AI honest (oversight, not autopilot)

The habit that mattered most: **I didn't take the AI's word that things worked.**
When it claimed the weather integration was fine, I pushed for proof — and it had to
admit it *couldn't* test live, because its sandbox had no internet. So I ran it on my
own machine, watched real Honolulu weather come back (31 °C, "hot — hydrate"), and
fed the output in. That loop — AI builds, I run and verify, AI fixes — is the
opposite of "the AI did everything." Both runtime bugs above were caught by *me
running it*, not by the AI noticing.

Hand this PRD and these rules to a brand-new model tomorrow and it would rebuild the
same app — but the *judgement* about when the output was actually wrong is the part
that stayed human.

---

## A note on how this was built

In the spirit of the assignment, the code was generated by an AI agent under my
direction. I owned the [PRD](specs/PRD.md) and [rules](docs/rules.md), set the
architecture and its constraints, ran and verified the app at every step, caught the
runtime bugs, and steered every fix. The reflection above is my own account of that
collaboration.
