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

## Data sources and licences

Each sport is loaded from a different place, and the terms differ sharply
between them. They are set out separately because "we got it off the internet"
is not a provenance, and a benchmark drawn from a source you cannot describe is
not a benchmark anyone can check.

### Football — nflverse

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

### Baseball — MLB Stats API

| What | Where | Licence |
|------|-------|---------|
| Schedules, results, probable starters, linescores | `https://statsapi.mlb.com/api/v1/schedule` | **None granted.** Copyright MLB Advanced Media; the terms permit personal, non-commercial use and forbid redistribution |
| Club abbreviations and venue ids | `https://statsapi.mlb.com/api/v1/teams` | as above |
| Starting-pitcher game logs | `https://statsapi.mlb.com/api/v1/people/{id}/stats?stats=gameLog` | as above |

Chosen over `pybaseball`, which was the brief's other candidate. Two reasons.
`pybaseball` is a scraping layer over Baseball Reference and Statcast whose
terms are *less* permissive, not more, and it drags in a pandas/lxml stack that
this project deliberately does not have. The Stats API is the source MLB itself
publishes, needs no key, and returns exactly the fields the factors need in one
request per date range.

**No published rate limit exists.** The loader is nevertheless written to a
budget: schedules are fetched in 30-day chunks, game logs only for pitchers who
actually appear as a probable starter, and no per-game boxscore is fetched at
all. A full three-season load is roughly 250 requests, and every response is
cached permanently — a completed season is never refetched.

Verified available on 2026-08-29: 7,289 games across 2023–2025 complete with
scores, plus 2,057 games of the running 2026 season, and probable starters
published one to two days ahead of first pitch.

**The unannounced starter is the important missing case.** A club names its
starter anywhere from a week out to ninety minutes before first pitch. When the
name is not yet published, `mlb_starter_rolling_perf` and `mlb_starter_rest_days`
are **absent from the feature vector**, not zero — the explicit-absent rule from
D2 — and the prediction card says so on its face. Five of the fourteen games on
the first forward slate were in exactly that state.

### Basketball — NBA Stats

| What | Where | Licence |
|------|-------|---------|
| Schedules, including seasons not yet started | `https://stats.nba.com/stats/scheduleleaguev2` | **None stated.** Undocumented endpoint |
| Team game logs | `https://stats.nba.com/stats/leaguegamelog` (`PlayerOrTeam=T`) | as above |
| Player game logs | `https://stats.nba.com/stats/leaguegamelog` (`PlayerOrTeam=P`) | as above |
| Injury report | `https://sports.core.api.espn.com` | **None stated** |

These are the endpoints nba.com's own site calls. No key. The host **refuses any
request that does not look like its own client**: the `Referer`, `Origin` and
`x-nba-stats-*` headers are all required, and without them it hangs rather than
returning an error. `cdn.nba.com`'s static schedule JSON returns 403, so the
schedule comes from the same host as everything else.

Chosen over the `nba_api` package, which is a wrapper over exactly these
endpoints: it would add a dependency, a pandas requirement, and a layer between
us and the bytes, in exchange for constants we can write down.

**Three requests per season**, not one per game — one schedule call and two game
log calls. A four-season load is twelve requests and about 25 MB, cached
permanently. Verified available on 2026-08-29: 4,920 completed games across
2022-23 to 2025-26, 105,253 player-games, and the full 1,200-game 2026-27
schedule. Only the regular season is loaded; preseason lineups are not a club's
lineups and a playoff series is a different question.

**The injury report is a snapshot, not a history.** ESPN publishes what is true
now, so the table is replaced on each fetch. It can therefore inform a forward
prediction and can tell a backtest nothing, and `nba_availability_index` is
defined so that it degrades to a strictly pre-game, strictly symmetric
measurement without it. See [docs/NBA.md](docs/NBA.md).

### Market lines

The line is a benchmark to score against, never an input. Where it comes from
per sport, and what happens where it does not exist:

| Sport | Market | Source | Licence |
|-------|--------|--------|---------|
| NFL | spread | nflverse `games.csv` closing line | CC BY 4.0 |
| MLB | moneyline | `sports.core.api.espn.com` | **None stated anywhere** |
| NBA | spread | `sports.core.api.espn.com` | **None stated anywhere** |
| all | player props | **no free source found** | — |

ESPN's core API is undocumented and public, needs no key, and republishes
DraftKings prices. Gridiron holds no account and calls no book or exchange
endpoint: this is a media API. If scoring against the market ever required a
betting account, the comparison would be dropped rather than LAW 5 bent.

Because that licence is unstated, it is treated as a source that may vanish
without notice. Responses are cached permanently, a settled game is never
refetched, and a failure degrades the *comparison* visibly rather than touching
the record at all.

**Where no line exists, nothing is invented.** Every prop market in all three
sports has no free line source, and so does any game whose line ESPN did not
publish. Those cards say **"no line available"** in plain words, the gap visual
is absent rather than drawn at zero, and the edge figure states that it cannot
be computed. The prediction is still written blind and still resolves against
the real outcome — a missing line source degrades the comparison, never the
record. This is the same rule that keeps `public_bet_pct` declared but inactive:
no proxies, no inventions.

Two feeds abbreviate two clubs differently (`ARI`/`AZ` and `CHW`/`CWS` in
baseball, seven pairs in basketball). Those are listed explicitly in
[`espn.py`](gridiron/market/espn.py) rather than matched fuzzily, so a game that
cannot be matched stays a *counted failure* instead of being quietly attached to
the wrong line.

**Public betting percentage** is declared as a factor but ships **inactive**: no
free source publishes it reliably enough to depend on. Law 2 says record that
and leave it inactive rather than invent a proxy, so that is what it does.

Nothing is refetched that is already stored. Completed seasons are cached
permanently; live schedules are revalidated with an ETag every six hours.

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

## The appliance

Gridiron is meant to run without being tended. Four scheduled tasks keep the
record current, a panel says whether they actually ran, and the app is reachable
from a phone on your own tailnet.

### What runs, and when

| task | when | what it does |
|---|---|---|
| `Gridiron-Resolve` | every 4 hours | settles every prediction whose game has finished |
| `Gridiron-Predict-MLB` | daily, 11:00 local | forecasts today's baseball slate, blind |
| `Gridiron-Predict-NFL` | Wednesdays, 11:00 local | forecasts the week's football slate, blind |
| `Gridiron-Predict-NBA` | daily, 11:00 local | a logged no-op until the season starts |
| `Gridiron-CatchUp` | at logon | resolve unconditionally; predict only slates that have not started |

Install and remove:

```bash
powershell -ExecutionPolicy Bypass -File tools\schedule_install.ps1
```

```bash
powershell -ExecutionPolicy Bypass -File tools\schedule_install.ps1 -Remove
```

Re-running the installer replaces the existing tasks rather than adding a second
set. Removal leaves the database and its record untouched.

**A missed slate is recorded, never caught up.** If the machine was asleep when
a slate began, those games are gone: a question once answered is never re-asked,
so forecasting them late would permanently occupy the slot the real forecast
should have had. The task writes a MISSED row with its reason and moves on. This
is not a limitation, it is the rule that voided 47 NBA rows and 6 MLB ones
earlier in this project's life.

### How to check it is working

```bash
.venv\Scripts\python.exe -m gridiron.cli schedule
```

or open **Schedule** in the app. Either shows, per task: when it last ran, what
happened, how long ago, when it is next due, all-time failures, and every MISSED
entry. A task silent past its window says so in plain words. A task that has
never run says *that*, rather than rendering an empty row — a blank reads as
"fine".

The same panel carries the per-sport **data freshness** line: how long ago each
sport's schedule was actually fetched. This exists because a loader served
entirely from cache reports success and fetches nothing, so "the load ran" is
not evidence the data is current. Only the fetch record is.

### Reaching it from a phone

The server binds `127.0.0.1` and that never changes. `tailscale serve` puts a
TLS listener in front of it, reachable only from devices signed in to your own
tailnet:

```bash
powershell -ExecutionPolicy Bypass -File tools\phone_setup.ps1
```

Then open `https://<this-machine>.<your-tailnet>.ts.net/` on the phone, enter
the access token once, and **Add to Home Screen** installs it as an app.

Verify it is not public:

```bash
tailscale funnel status
```

That must say no funnel is configured. `tailscale serve` is tailnet-only;
`tailscale funnel` is the public internet, and this project configures the
former and never the latter. Binding `0.0.0.0` is refused outright by
`api.serve`, because it would expose the record to whatever network the machine
happens to be joined to.

To withdraw:

```bash
powershell -ExecutionPolicy Bypass -File tools\phone_setup.ps1 -Remove
```

### The phone app caches the shell, never the data

The service worker caches HTML, CSS, JS and the icon so the app opens instantly.
It caches **no** API response, ever, and there is a guard that fails by name if
one is added — `audit.check_no_offline_data_caching`, planted in
`tools/guards/plant.py`.

The reason is the same one behind everything else here. A forecaster showing
yesterday's probabilities as though they were today's is lying in the exact way
this project exists to prevent: a cached calibration figure has no N you can
trust, and a cached slate may describe games that have already finished. So
offline, the app says **OFFLINE** in a bar across the top and refreshes nothing.
It does not guess.

### Access

One token, created once:

```bash
.venv\Scripts\python.exe tools\make_token.py
```

It is printed once and never again, written to `.env`, which is gitignored. The
desktop launcher reads it from there, so `cli serve --open` opens an
already-signed-in browser without you typing anything — using a single-use,
sixty-second nonce, so the token itself never appears in a URL or a browser
history. You need the token only when signing in from another device.

To replace it and end every open session:

```bash
.venv\Scripts\python.exe tools\make_token.py --rotate
```

Every route is closed without a session, including `/api/docs` and
`/openapi.json`. `/api/health` alone answers openly, and it returns only
`{"ok", "version"}` — no path, no counts, no staleness. An open endpoint that
reports what is in the database is a data leak with a reassuring name.

### Two-line uninstall

```bash
powershell -ExecutionPolicy Bypass -File tools\schedule_install.ps1 -Remove
```

```bash
powershell -ExecutionPolicy Bypass -File tools\phone_setup.ps1 -Remove
```

Nothing else is installed anywhere. The database, the record and the repository
are untouched by both.

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
  audit.py            static enforcement of LAW 1 and LAW 5 over the source
tests/                including the guard tests that prove the laws hold
tools/
  backtest.py         walk-forward sanity check, its own database
  verify.py           the whole verification in one command
  guards/plant.py     breaks every law on purpose and requires the guard to fire
```

## Status

Six build phases (G1-G6) and five repair phases (D1-D5). 252 tests. Every law
has a guard and every guard has been made to fire by planting the violation it
exists to catch — 20 plantings, all caught:

```bash
python tools/verify.py
```

**The forward record is N = 0 resolved, and that is the honest state.** 104
predictions were written before kickoff on 2026-08-29 (56 under factor set fs2,
48 under the now-closed fs1) against a first kickoff of 2026-09-10. Nothing can
resolve until the games are played.

**What the backtest says, reported as found.** Walk-forward over 2024-25, each
season fitted only on earlier ones, six markets scored separately and never
merged. On the 544 spread questions the model scores 0.2141 Brier; the closing
line scores 0.2011 on the same questions. Where the model disagreed with the
market by more than 5 points it was right 55.1% of the time (n=207); where the
market was the more confident side, the outcome went the model's way 70.3%
(n=148). Its disagreements are worse than its agreements.

[docs/DIAGNOSIS.md](docs/DIAGNOSIS.md) is a pre-registered attempt to explain
that failure — 29 declared comparisons, a Bonferroni-adjusted threshold, and
four hypotheses of which **none is supported**. The recorded conclusion is *the
disagreements lose and we do not know why yet*, which was the honest answer
available and is better than a manufactured one.

See [docs/METHODOLOGY.md](docs/METHODOLOGY.md) for what would have to be true
before any of it counted as evidence.
