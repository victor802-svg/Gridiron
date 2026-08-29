# Basketball

Written 2026-08-29, at the end of phase S3.

Basketball is the one sport here where the model is built before it can be used.
The 2026-27 season tips on **2026-10-20**, fifty-two days after this was written,
so everything below is a description of an instrument, not a record. The NBA tab
says so on its face rather than rendering an empty page that reads as broken:

> The NBA season starts on 2026-10-20, 52 days from now. 1,200 games are loaded
> and waiting; the first forecasts are written the morning of the first slate.
> Nothing is predicted before then, because there is nothing yet to predict.

---

## What is predicted

**Spreads on a four-rung ladder, and four player prop markets.**

The spread rungs are `-9.5, -4.5, +0.5, +5.5` from the home side, chosen wider
than football's `-7.5, -3.5, +0.5, +3.5` because basketball margins are wider — a
four-point NBA spread is close to a coin flip where a four-point NFL spread is
not. Every rung ends in .5, so nothing can push and every prediction resolves 0
or 1. Which rung a game is asked at is a stable hash of its id, so the record is
reproducible.

The four prop markets are **points, rebounds, assists and threes**. Each is its
own scoring category, its own calibration curve and its own 100-resolution gate.
They are never merged, and `nba_prop_rate` is the only factor that differs
between them.

**One question per player per game**, on a stat chosen by a stable rotation. That
matters more than it sounds: the first version sorted the four stats and took the
first eligible one, which asked every player in the league about *assists*
forever and left three markets permanently empty while looking merely unlucky.
Alphabetical order is not a sampling strategy.

## The factors

Fifteen: eight on the spread, seven shared across all four prop markets.

Basketball gets a fuller set than baseball because basketball is far less random.
Five players take almost every possession, the better club wins about two thirds
of its games rather than three fifths, and a single absence moves the result more
than any single absence in either other sport. So there is more to know, and the
factors say who is playing and how tired they are — those two things, over and
over, in different shapes.

### The spread

| Factor | Fitted weight | Present in |
|--------|--------------:|-----------:|
| `nba_asked_line` | +1.1078 | 4,920 / 4,920 |
| `nba_availability_index` | +1.0338 | 4,904 |
| `nba_net_rating_rolling` | +0.6244 | 4,841 |
| `nba_rest_days_diff` | +0.0969 | 4,904 |
| `nba_home_court` | +0.0665 | 4,920 |
| `nba_pace_rolling` | +0.0380 | 3,690 |
| `nba_b2b_either` | +0.0109 | 4,904 |
| `nba_travel_recent` | −0.0069 | 4,857 |

Fitted on 2022-23 through 2025-26, 4,920 completed games, **after the
rolling-window leak was fixed**. Nothing dropped, nothing constant.

The first fit of this table, before the fix, is worth keeping beside it:
`nba_net_rating_rolling` sat at +1.03 and `nba_availability_index` at +0.55.
Once the model stopped seeing the game it was predicting, those swapped —
availability rose to +1.03 and net rating fell to +0.62. Net rating was the
factor carrying most of the leaked information, which is exactly why it looked
like the strongest thing in the model.

`nba_pace_rolling` is present in only 3,690 rows because it is expressed against
the league average of **prior** seasons, and 2022-23 is the earliest season
loaded, so it has no prior. Absent for those rows rather than defaulted, the same
way MLB's park factor is.

### The props

Seven factors, shared across all four markets and fitted separately per market:

- `nba_prop_minutes` — everything a basketball player does is bounded by how long
  he is on the floor, and minutes move before production does when a role changes.
- `nba_prop_usage` — the share of his club's shooting and turnovers he accounts
  for while on the floor. Minutes say how long; usage says how much runs through
  him while he is out there. The two move independently.
- `nba_prop_rate` — production per minute in the stat actually being asked about.
  The only market-specific factor of the five.
- `nba_prop_opponent_allowance` — how much of this stat the opponent gives up.
- `nba_prop_teammate_competition` — the club's recent total in this stat
  excluding the player himself, scaled by that club's availability tonight, so it
  moves when a co-star is ruled out.
- `nba_prop_mean_vs_line` — where the line sits relative to the player's own
  average.
- `nba_prop_volatility` — dispersion over the window, because a high-variance
  player clears a high line more often than a steady one with identical output.

Fitted on 2023-24 through 2025-26. Every factor is present in every row of every
market; nothing was dropped and nothing was constant.

| | points | rebounds | assists | threes |
|-|--:|--:|--:|--:|
| **n** | 15,076 | 11,866 | 11,374 | 9,280 |
| `nba_prop_mean_vs_line` | +3.34 | +3.33 | +3.12 | +2.51 |
| `nba_prop_opponent_allowance` | +2.41 | +1.75 | +1.87 | +1.24 |
| `nba_prop_teammate_competition` | −1.17 | −1.71 | −2.33 | −0.55 |
| `nba_prop_usage` | +0.20 | +0.39 | +0.58 | +1.08 |
| `nba_prop_minutes` | −0.66 | −0.68 | −0.25 | −0.54 |
| `nba_prop_rate` | −0.24 | −0.05 | −0.97 | −1.07 |
| `nba_prop_volatility` | +0.10 | +0.15 | +0.35 | +0.22 |

Two things in that table are worth reading rather than skipping.

`nba_prop_teammate_competition` is negative everywhere and **strongest for
assists**, which is the mechanism it was declared for: more shot-takers around a
player means fewer assists to go round. That it is weakest for threes fits too —
a shooter's threes depend on his own attempts far more than on who else is on the
floor.

`nba_prop_minutes` is **negative** in all four markets, which looks wrong until
you remember how the line is set. The line is the player's own rolling mean
shifted by a fixed offset, so a thirty-six-minute starter is asked a harder
question than a twenty-minute reserve. Minutes therefore predict the *line*, not
the over, and once `mean_vs_line` tells the model where the line sits the residual
sign flips. This is the ladder working as designed, not a broken factor — and it
is exactly the confounding that the first fit, with no `mean_vs_line`, was
silently absorbing.

Each market trains on roughly a quarter of eligible player-games, because the
stat rotation gives each player one stat per game. That is a **random subsample**,
not a selection effect: the rotation is a crc32 of two identifiers and knows
nothing about how anyone played.

The last two factors were **missing from the first fit**, and that is worth recording
because the fit converged anyway and the coefficients looked reasonable. Lines
are set at one of three pre-declared offsets around the player's rolling mean, so
a model with no `mean_vs_line` cannot tell a soft line from a hard one and
averages three different questions into one answer. It is the same failure
`nba_asked_line` prevents on the spread, and it was caught by asking what
football's prop factors do that basketball's did not — not by anything going
wrong.

## Availability, which is the whole sport

`nba_availability_index` is the load-management factor and the one that matters
most. It is the minutes-weighted share of a club's recent rotation expected to be
available: a rotation is whoever averaged twelve minutes or more over the last
ten games, and each man is weighted by those minutes, so losing a
thirty-six-minute starter costs three times what losing a twelve-minute reserve
does.

**The definition is the interesting part, and the easy version would have been
wrong.** The obvious way to measure who is available on a night in 2024 is to
read the box score of that game and see who played. That fits beautifully and is
information a forward prediction can never have on a Tuesday in November. A model
fitted that way would have learned how much it helps to know the future.

So availability is defined to use only information that exists **before tip in
both regimes**. A rotation player counts as unavailable if:

- he did not appear in his club's most recent completed game — strictly prior
  information, identical for a backtest and for a live forecast; **or**
- he is listed OUT on the current injury report — which exists only going
  forward.

The second clause makes the forward measurement strictly *stronger* than the
fitted one. That asymmetry is deliberate and one-directional: the coefficient
comes from the weaker measurement, so it is a floor rather than a flattering
ceiling. A test pins that direction — the injury report may subtract availability
and may never add it — and another test plants a change to the game being
predicted and asserts the number does not move.

The injury report is a **snapshot, not a history**: ESPN publishes what is true
now, so the table is replaced on each fetch rather than appended to. When it is
empty, availability still works on the first clause alone and the card says so.

## Two bugs the model's own bookkeeping caught

Neither was found by a test. Both were found because the fit reports which
factors never varied, which is machinery this project built in D2 for exactly
this purpose.

**`nba_back_to_back` never fired.** It tested for zero days since the club's last
game. A back-to-back is a game the night *after* a game, so the dates are one day
apart and "days since" reads 1, never 0. The fit reported the factor constant
across 4,911 rows. The accessor now returns days of *rest*, so the factor's name,
its rationale and its arithmetic all say the same thing — and 17.9% of team-games
are on zero rest, so it has plenty to vary on.

**Neutral sites were mostly arena renames.** The schedule feed has no
neutral-site field, so it is derived — and the obvious derivation was wrong.
Taking each club's modal *arena name* as its home flagged 33 games in 2024-25, of
which 26 were the same building renamed mid-season: Footprint Center became PHX
Arena, Rocket Mortgage FieldHouse became Rocket Arena, and Miami's arena changed
name twice in one year. A factor fitted on that would have been measuring
sponsorship deals. Comparing the arena's **city** instead — which a rename does
not change and a trip to Mexico City does — gives 24 genuine neutral games across
the four seasons, 0.49%.

That 0.49% is thin, four times thinner than football's 2.1%, and `nba_home_court`
may yet come back as never having varied enough to fit. It is declared anyway,
because unlike MLB's version it *can* vary, the measurement is on record, and the
fit's own bookkeeping will say plainly if it did not. This time it did: the factor
fitted at +0.10 across all 4,920 rows.

## Two more, caught by cross-checking rather than by tests

### The spread sign

ESPN writes a spread from the home side the ordinary way: negative means the home
team gives points. Our `spread_line` column stores the home team's expected
**margin**, nflverse's convention, which is the opposite sign. The first version
flipped the sign only when ESPN *also* flagged the home team as the favourite,
which produced correct numbers for home favourites and sign-reversed ones for
home underdogs.

That is a mistake that reverses the market comparison on roughly half of all
games and looks like nothing at all in the data. It surfaced because a stored
line said Washington was favoured by 15.5 while the moneyline beside it said +900.
A spread and a moneyline must agree about which side is favoured; they now do on
13 of 13 games on the check date, and the cross-check is a test.

### The club abbreviations

Two feeds spell six NBA clubs differently — ESPN writes `GS`, `NO`, `NY`, `SA`,
`UTAH`, `WSH` where stats.nba.com writes `GSW`, `NOP`, `NYK`, `SAS`, `UTA`, `WAS`.
The alias map that translates them had two wrong entries and both were silent:
`NOP -> NO` was written backwards, so New Orleans never matched, and `PHX -> PHO`
rewrote a code the two feeds already agree on, so Phoenix stopped matching too.
Seven of fifty-three games on a sample slate went unmatched — **counted**, which
is how it was noticed, but no line was attached to them.

The invariant is now structural and tested: an alias must map a name we do *not*
use onto one we *do*. Both bad entries violate it. The reference set of our own
tricodes was read from the loaded database rather than written from memory —
memory had MLB's Arizona as `ARI` and Chicago as `CHW`, where the feed actually
gives `AZ` and `CWS`, which would have condemned a correct alias as reversed.

## The forecast horizon

Running `predict --sport nba` in August wrote 47 predictions for the season
opener, 52 days ahead. No line was seen, so LAW 1 held — but every factor came
from the previous season's rotations and form, and no injury report existed for a
date two months out.

The harm is not the staleness on its own. It is that **a question once answered is
never re-asked**: those rows would have permanently occupied the opening slate's
slot, and the model would never have got to forecast it with the information it
will actually have on the day. All 47 are voided with that reason recorded.

`MAX_FORECAST_LEAD_DAYS` is now 21, and the number is recorded as a judgement
rather than dressed up as a derivation. What forced it was the 52-day case. What
bounds it from below is a season opener, legitimately forecast about two weeks out
because that is when rosters settle — the NFL 2026 week 1 slate in this record was
written at 12 to 17 days, measured rather than assumed, and sits inside 21.

## Data

| What | Where | Licence |
|------|-------|---------|
| Schedules, including future seasons | `stats.nba.com/stats/scheduleleaguev2` | **None stated.** Undocumented |
| Team game logs | `stats.nba.com/stats/leaguegamelog` (`PlayerOrTeam=T`) | as above |
| Player game logs | `stats.nba.com/stats/leaguegamelog` (`PlayerOrTeam=P`) | as above |
| Injury report | `sports.core.api.espn.com` | **None stated** |
| Spread lines | `sports.core.api.espn.com` | **None stated** |
| Prop lines | **no free source found** | — |

stats.nba.com refuses any request that does not look like nba.com's own client:
the `Referer`, `Origin` and `x-nba-stats-*` headers are all required, and without
them the host hangs rather than returning an error. `cdn.nba.com`'s static
schedule JSON returns 403 to us, so the schedule comes from the same host as
everything else.

Chosen over the `nba_api` package, which wraps exactly these endpoints: it would
add a dependency, a pandas requirement, and a layer between us and the bytes, in
exchange for constants we can write down.

**Three requests per season**, not one per game — one schedule call and two game
log calls. A full four-season load is twelve requests and about 25 MB, cached
permanently. Verified 2026-08-29: 4,920 completed games across 2022-23 to
2025-26, 105,253 player-games, and the full 1,200-game 2026-27 schedule.

Only the **regular season** is loaded. Preseason lineups are not a club's
lineups, and a playoff series is a different question that a regular-season fit
does not answer.

## Two measurements weaker than the brief asked for

Both are stated where they are defined rather than quietly being the easy thing.

**Opponent allowance is league-wide, not positional.** The league's game log
carries no position, and deriving one from a player's own stat line would mean
inventing a classification and then measuring against it — discovering a factor
by scanning, which is what LAW 2 exists to prevent.

**Travel is a count of road games, not a distance.** Real travel distance would
need coordinates for thirty arenas, a reference table we would have to source and
cite. The count captures the thing that actually wears a team down — consecutive
nights in hotels — and distinguishes a long homestand from a long road trip,
which are the two states that matter.

---

## Backtest — pipeline sanity, not evidence

2025-26, walk-forward, fitted on 2022-25 only. 1,230 predictions, all resolved.

| | with the leak | **leak-free** |
|-|--:|--:|
| model Brier | 0.1849 | **0.2065** |
| model on the market's subset | 0.1855 | **0.2072** |
| market Brier | 0.1920 | 0.1920 |
| hit rate | 0.7228 | **0.6756** |
| **model as a share of market skill** | **111.3%** | **73.8%** |
| model's confident disagreements right | 66.9% | **52.8%** |
| market's confident disagreements right for model | 72.5% | 80.4% |

The left column is what a model looks like when it can see the result it is
forecasting. It appeared to beat the market by 14%; corrected, the market beats
it and basketball lands at 73.8% of market skill, beside football's 73.1%.

The disagreement line is the one to read. When this model confidently disagrees
with a basketball line it is right 52.8% of the time — a coin flip, on exactly
the questions where it is most sure. When the market is the confident one, the
market is right 80.4% of the time. D1 reached the same conclusion about football
and it has not changed for a second sport.

Two chased explanations were wrong before the right one was found, and both were
stated with more confidence than they had earned: that the margin SD was to
blame (it moved the market's Brier by 0.0012), and that the ladder's tails were
(the advantage sat near the line, and the market won the deep tail). The leak was
found by measuring, not by reasoning.

## The record

**Empty, and correctly so.** No NBA prediction has been written, because no NBA
game has been played this season. The first slate is written blind on the morning
of 2026-10-20.

Under LAW 4 the spread market needs 100 resolved predictions before anything in
it can be claimed. At roughly 45 games a week that arrives in early November; the
four prop markets, sharing a 40-per-week budget between them, arrive around the
turn of the year.
