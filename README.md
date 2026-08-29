# Gridiron

An NFL forecaster that grades itself.

Gridiron makes probabilistic predictions on game spreads and player props,
**writes them to the database before it is allowed to see the market line**,
resolves them against real results, and keeps a permanent calibration record of
how well its stated confidence matched what actually happened.

The interesting output is not the predictions. It is the scorecard.

---

## What it is not

**It is not a betting tool.** There is no stake sizing, no bankroll, no Kelly
criterion, no bet recommendation, and no sportsbook or exchange integration.
The output is a probability, the reasoning behind it, and a track record. This
is Law 5 in [CLAUDE.md](CLAUDE.md) and it is not negotiable in a later session.

**A good-looking calibration curve here is not evidence of an edge.** See
[docs/METHODOLOGY.md](docs/METHODOLOGY.md) for what would have to be true before
any of these numbers deserved trust.

---

## The five laws

The project is built around five constraints, stated in full in
[CLAUDE.md](CLAUDE.md) and enforced by database triggers and guard tests rather
than by good intentions:

1. **Blind first** — the probability is written to the database before any line
   is fetched. A model that sees the line measures the market, not itself.
2. **Declared factors only** — every factor is registered in advance with a
   causal rationale and a date. None are found by scanning for correlations.
3. **Append-only** — a prediction is never edited, deleted, or re-scored.
4. **No sample, no claim** — no figure renders without its N, and nothing claims
   an edge below 100 resolved predictions in that category.
5. **Not a betting tool** — see above.

---

## Data source and licence

All football data comes from **nflverse**:

| What | Where | Licence |
|------|-------|---------|
| Schedules, results, kickoff times, rest days, venue, roof, observed weather, and the closing lines | [`nflverse-data`](https://github.com/nflverse/nflverse-data) release `schedules` → `games.csv` | CC BY 4.0 |
| Weekly player box scores | `nflverse-data` release `stats_player` → `stats_player_week_{season}.csv` | CC BY 4.0 |
| Injury / practice participation reports | `nflverse-data` release `injuries` → `injuries_{season}.csv` | CC BY 4.0 |
| Club home-market coordinates and time zones | [`nfldata`](https://github.com/nflverse/nfldata) `data/airports.csv`, embedded in [`reference.py`](gridiron/data/reference.py) | nflverse; the repo declares no SPDX licence, and we reproduce 32 rows of coordinates with attribution |
| Kickoff weather forecast for upcoming outdoor games | [Open-Meteo](https://open-meteo.com) | CC BY 4.0, free for non-commercial use, no key |

These are the same artifacts the `nfl_data_py` package wraps. Gridiron reads the
release CSVs directly instead of depending on that package, so the runtime needs
no pandas/pyarrow stack and the exact bytes used are cached verbatim in the
local database. Verified available on 2026-08-28: 7,548 games from 1999 through
the completed 2025 season, plus the full 2026 schedule; player weeks from 1999
to 2025; injury reports from 2009 to 2025.

A note on picking the right asset: nflverse also publishes a legacy
`player_stats/player_stats_{season}.csv`, which silently stops at 2024. Loading
from it produced a database that looked fine and had no 2025 box scores at all.
The loader now warns loudly when a season with completed games returns zero
rows, and exits non-zero, because a source that quietly ends is worse than one
that is plainly missing.

**Public betting percentage** is declared as a factor but ships **inactive**: no
free source publishes it reliably enough to depend on. Law 2 says record that
and leave it inactive rather than invent a proxy, so that is what it does.

Nothing is refetched that is already stored. Completed seasons are cached
permanently; the live schedule is revalidated with an ETag every six hours.

---

## Quick start

```bash
python -m venv .venv
```

```bash
.venv/Scripts/pip install -r requirements-dev.txt
```

```bash
.venv/Scripts/python -m gridiron.cli load --since 2016 --until 2026
```

```bash
.venv/Scripts/python -m gridiron.cli status
```

Then train, forecast a week blind, and open the app:

```bash
.venv/Scripts/python -m gridiron.cli train --since 2016 --until 2025
```

```bash
.venv/Scripts/python -m gridiron.cli predict --season 2026 --week 1
```

```bash
.venv/Scripts/python desktop/launcher.py
```

After the games are played, settle them:

```bash
.venv/Scripts/python -m gridiron.cli resolve
```

To see the interface with a full calibration curve before your own forward
record has any volume, run the walk-forward backtest and point the app at it.
It opens with a loud banner saying the predictions in it were made after the
games, because they were:

```bash
.venv/Scripts/python tools/backtest.py --seasons 2024 2025
```

```bash
GRIDIRON_DB=var/backtest.db .venv/Scripts/python desktop/launcher.py
```

On macOS or Linux use `.venv/bin/` instead of `.venv/Scripts/`.

---

## Layout

```
gridiron/
  schema.sql          the laws, as CHECK constraints and triggers
  config.py           paths, budgets, thresholds
  db.py               connection + schema loader
  data/
    sources.py        upstream URLs and the HTTP cache
    loader.py         ingest; the only place a market column is read
    repo.py           read-only accessors for the prediction path
    reference.py      stadium coordinates, kickoff -> UTC
    weather.py        Open-Meteo kickoff forecasts
  factors/
    registry.py       THE registry: every factor, dated, with its rationale
    context.py        everything a factor may see; no market field exists on it
    compute.py        context -> feature vector, with missing values named
  model/
    logistic.py       pure-Python IRLS logistic regression
    questions.py      choosing line_asked, blind
    baseline.py       train / predict / explain
    llm.py            the reasoning pass and its budget ledger
    predict.py        steps 1-4: the blind core. Cannot reach the market.
  market/
    lines.py          step 5: the quarantine. Only this reads market tables.
  blind.py            the blind window: market imports raise inside it
  run.py              the ordering, on one page
  resolve.py          settling, idempotently
  calibration.py      the scorecard, and the LAW 4 validator
  views.py            view models; assembly only, no new claims
  api.py              FastAPI, 127.0.0.1, GET-only
  web/                index.html + app.js + style.css. That is the whole build.
desktop/
  launcher.py         attach-first, health-gated, loud failure
  gridiron.spec       PyInstaller onedir
docs/
  GRIDIRON.md         the build specification, verbatim
  METHODOLOGY.md      what the numbers mean and when to believe them
tests/                including the guard tests that prove the laws hold
tools/                backtest and the planted-violation harness
```

## Status

Phases G1-G5 complete: skeleton, schema, data loader, factor registry, blind
prediction loop, resolution and calibration, and the interface.

2026 Week 1 has been forecast blind: 48 predictions written (16 spreads, 32
props), then 48 market snapshots attached afterwards. The LLM pass degraded to
statistical-only with the tag `llm_unavailable:no_api_key`, which is recorded
on the run rather than papered over.
