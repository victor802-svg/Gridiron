# Follow-ups

Things known to be unfinished, thin, or deferred. Created 2026-08-29, in P1,
after two projects ran without one.

The rule for this file: an entry says what is wrong, how it was measured, and
what would settle it. "Look into X" is not an entry. If something here turns out
to be fine, the entry is deleted with a line in the commit saying so — not left
as a permanent worry.

---

## Open

### The first MLB forward predictions carry the pre-fix factor set

The **25 standing MLB forward predictions** — day 155 and day 156, written
2026-08-29 19:17 and 19:22 UTC — were made before the rolling-window leak was
found. Their factor vectors were computed with the UTC-date cutoff, so any of
them whose game falls on the ~24% of MLB dates where the league date differs may
have included the game in progress in its own rolling form.

**They stand, and that is deliberate.** LAW 3: a prediction cannot be edited,
deleted or re-scored after the fact. They were written blind and before first
pitch, so LAW 1 held. Re-writing them with corrected factors would be exactly
the re-scoring the law forbids, and voiding them would be discarding a real
forward record to tidy up an inconvenience.

But **the record should know its first resolutions came from a contaminated
factor set**, and this is where it is written down. When these resolve — the
first real resolutions this project has ever had — they enter the fs2 MLB
moneyline curve alongside later predictions made with the corrected cutoff. At
n=25 out of a 100-prediction gate they are a small share and will be a smaller
one by the time anything is claimable, but the mixture is real and is not
visible in the curve itself.

**What would settle it:** when MLB moneyline passes n=100, compute the curve
twice — with and without these 25 — and record whether the difference is
material. If it is, the honest move is to report the corrected-cutoff sample as
the headline and these as a footnote. Do not pre-judge which; measure it.

### P5 left two items incomplete, and one of them is now done

**Phone proof over Tailscale — INCOMPLETE.** See the entry below. The 390px
phone pass is verified headlessly over localhost; the tailnet leg is not.

**The first real resolutions — DONE, 2026-08-30.** Six MLB moneylines settled,
three correct, Brier 0.2556 on n=6. The calibration page reports the single
occupied bucket as PROVISIONAL and says 94 more are needed before anything is
claimable, which is the machinery behaving exactly as LAW 4 requires. These are
the 25 standing predictions written under the pre-fix UTC cutoff — see the entry
above; the contamination note applies to them.

### The tailnet leg is UNVERIFIED

`tools/phone_setup.ps1` is written and its not-installed path is verified — it
detects the absence of Tailscale, prints install instructions, changes nothing
and exits 1. **The serving path has never been run**, because Tailscale is not
installed on this machine. What is untested: whether `tailscale serve --bg
--https=443` succeeds, whether the TLS certificate provisions, whether the app
loads over the tailnet, and whether "Add to Home Screen" installs it.

The phone layout itself IS verified, headlessly at 390px with touch emulation:
every screen, tap targets, card expansion, dumbbells, contribution bars and the
schedule panel. That was done over localhost, not over the tailnet.

**What would settle it:** install Tailscale, run the script, open the URL on a
phone. Until then, treat P4's phone claim as "the app is ready for a tailnet",
not "the app has been used on one".

### Factors that fire too rarely to be tested

Each of these is **untested, not disproved**, and the distinction is the one
this project keeps insisting on. The backtest verdicts say so in those words.

| factor | fires in | measured |
|---|---|---|
| `nfl/prop_player_status` | 4.0% of rows | NFL backtest, 1,892 resolved |
| `nfl/neutral_site` | 2.2% of rows | NFL backtest, 1,892 resolved |
| `nba/nba_pace_rolling` | *inert* — barely moves any forecast | NBA backtest, 1,230 resolved |

`nba_pace_rolling` is the one to watch: it is not rare, it simply does nothing.
That may be correct — pace scales a margin, and a spread question already
carries the margin in `asked_line` — in which case it is redundant rather than
wrong. **What would settle it:** a forward season. If it is still inert at
n=100+ forward, retire it with a dated note saying redundancy, not refutation.

### `LIVE_TTL` is a blunt instrument

P1 split the fetch cache into `LIVE_TTL` (6h) and `LIVE_TODAY_TTL` (5min), keyed
on whether a fetched date range reaches today. That fixed the immediate failure —
a schedule cached at 19:10 still claimed every game was scheduled at 20:39 while
two were final upstream — but the split is coarse:

- The TTL is chosen by the *caller* passing `ttl_for_range`. A caller that
  forgets gets six hours and no warning.
- NFL and NBA loaders do not use it yet. Only MLB does, because MLB is the sport
  currently resolving.

**What would settle it:** make the TTL a property of the URL rather than the
call site, so forgetting is impossible.

### The margin SD for MLB is measured but unused

`MarginSD("mlb", 4.71, n=2110)` is recorded because the previous table had *no*
MLB key at all, so an MLB caller would have silently received football's 13.2
through a dict default. Gridiron asks no run-line question, so nothing reads it
today. It is here so that if a run-line market is ever added, the number is
already measured and dated rather than invented on the spot.

### Prop markets train on a quarter of eligible rows

Each NBA prop market sees roughly a quarter of eligible player-games, because
the stat rotation gives each player one stat per game. This is a **random
subsample** — the rotation is a crc32 of two identifiers and knows nothing about
performance — so it costs precision, not correctness. Training on all four stats
per player would quadruple rows and runtime and would fit on questions the live
slate never asks. Recorded so nobody "discovers" it later and assumes bias.

### The HTTP cache is copied into every scratch database

`copy_facts` duplicates `http_cache` — currently ~350MB — into each backtest or
verification database. Three backtest databases is over a gigabyte of duplicated
bytes. It is done for network politeness: without it, a season's backtest would
refetch months of ESPN days. **What would settle it:** copy only the cache rows
whose URLs the run will actually request.

### NBA prop fits are slow

~150s per market, ~10 minutes for all four, dominated by per-game context
construction. Acceptable for an occasional refit, uncomfortable for a weekly one.
An index on `nba_player_games(opponent, game_date)` already took this from over
an hour; the remaining cost is Python, not SQL.

---

### The `--ink` collision, and what it says about the test suite

*(found and fixed 2026-08-30, T1)*

The approved palette uses `--ink` for the page GROUND. The CSS it replaced used
`--ink` for the TEXT. Aliasing one to the other painted every heading the colour
of the page: the matchup and the probability rendered **black on black**, in both
the CSS and the canvas that draws the calibration chart.

**Every test passed.** 472 of them. It was caught by looking at a screenshot.

`tools/contrast.py` now measures every foreground token against every ground it
is actually drawn on — heading-on-ground pairs first, because those are the ones
that went invisible — and fails anything under WCAG AA. Running it immediately
found a second, real problem the eye had not: `--faint`, the token carrying every
sample size, sat at 3.23:1 against a card. An N nobody can read is an N that is
not there, so LAW 4 makes that a correctness bug and not a taste one. Lightened
to #6F8471, 4.56:1, same hue and saturation.

**What would settle the wider worry:** the suite still cannot see the page. The
contrast audit and the browser tests together cover a lot, but neither would
catch, say, an element positioned off-screen or a z-index that hides a warning.

### Three launcher tests had never been seen red

*(proved 2026-08-30)*

`test_a_database_inside_dist_is_refused_by_name` and its two siblings passed on
first write and were never watched failing. Proved by neutering
`paths_are_outside_the_bundle()` in a throwaway copy of the tree: all three go
red with named assertions, and the real tree was never modified.

Worth recording what the first attempt showed. Removing only the `dist/` check
left all three still green — the installation check added later caught the same
planted fault. That is defence in depth working, and it also means each test is
less specific than its name suggests. They are load-bearing as a group.

### F2 was assigned and skipped

*(recorded 2026-08-30, executed the same day)*

The greeting was assigned in the F-phase brief, was not blocked, and was simply
not built; the session went from F1 to discussing F3 without it. It has now been
built dark-native as part of T2. Recorded because the failure was not technical —
nothing prevented it — and a list of technical debts that omits "we forgot" is a
list that flatters.

### The markets contract was broken for three sessions

*(found and fixed 2026-08-30, T3)*

`s1: multi-sport` renamed `/api/markets`'s `spread` field to `game_markets`.
The browser still read `data.spread`, so `loadMarkets` threw `undefined.concat`
on **every page load** — inside `boot()`'s catch, which meant no error banner and
no console output. Everything after it in boot never ran, so the week picker and
the chart's market selector have been **empty since s1**.

Nothing caught it: not the suite, not the browser tests, not four sessions of
screenshots. I saw the empty select in a T1 render and did not chase it. It was
found only because a T3 test needed the picker to navigate to a played week.

There is now a contract test asserting that every `data.<field>` the browser
reads from that endpoint is a field the endpoint returns. **What would settle
the wider worry:** the same class of drift can exist on any of the other twelve
endpoints, and only this one is checked.

### MLB player props are deferred, not skipped

*(ruling 2026-08-30)*

C4 — four MLB prop markets (batter hits, total bases, home runs, pitcher
strikeouts) — was deferred to its own session by the operator, on the reasoning
that C3's checklist should GOVERN C4 rather than describe it. Writing both in
one pass would have made `docs/NEW_MARKET_CHECKLIST.md` an account of what had
just been done instead of a constraint on what comes next.

The work is fully specified in the brief and unblocked. **What it needs:** the
MLB loader extended to player game logs, ~13 factors with rationales, four
per-market fits and gates, VOID rules written first, a bucket set that covers
the 15–35% range home runs actually live in rather than starting at 50%, a
dated daily cap, and a walk-forward backtest labelled pipeline-sanity.

MLB is live and resolving daily, so these become the fastest-accumulating record
in the app once they start — which is the argument for doing them next, and also
the argument for doing them carefully.

## Resolved, kept for the record

### The rolling-window leak *(found and fixed 2026-08-29, P1)*

A game tipping after midnight UTC is the previous evening where it is played, so
its own game-log row is dated the day before its `kickoff_utc`. Every rolling
window cut on the UTC date therefore admitted the game being predicted into its
own rolling form, availability and pace — **76.8% of NBA games and 25.1% of MLB
ones**. The model was reading the result it was forecasting.

Fixed by `games.league_date`, carried from each source's own local date
(`officialDate`, `gameDateEst`), backfilled for 18,873 existing rows, with a
planted guard and a test stating the invariant by outcome.

This invalidated the NBA backtest entirely and a quarter of the MLB one. It also
produced at least one *downstream false finding*: `nba_back_to_back` was reported
firing in only 4.4% of games and judged a broken instrument, when the true
leak-free figure is 21.3%. **A leak does not only inflate scores; it manufactures
conclusions about factors.** Anything measured before 2026-08-29 should be
treated as suspect until recomputed.

**MLB's aggregate was unaffected and its published numbers stand.** 24% of MLB
games leaked, and the corrected backtest came back byte-for-byte identical:
MLB predictions cluster in one bucket, the affected factor has a small
coefficient, and one extra game in a 15-game window moves a near-coin-flip
probability by under a percentage point. NBA's leak hit 76.8% of games through a
10-game window with a large coefficient. Same bug, same fix, opposite
consequences — which is why the fix was verified per-sport by inspecting a stored
factor value rather than assumed from the diagnosis.

### The verifier was broken three separate ways *(fixed 2026-08-29, P1)*

`tools/verify.py` had not been run end to end in some time, and each failure hid
the next:

1. a positional `SELECT *` copy — the same bug fixed in `backtest.py`, duplicated
   here, so fixing one left the other broken;
2. `calibration.curve()` called without its required `sport` argument, an S1
   leftover from when LAW 6 made it mandatory;
3. `MAX(week)` taken across every sport, so an NFL-only step targeted **week
   155** — a baseball day number — found no football games, and reported that as
   a pipeline failure.

All three were in the tool whose job is to catch exactly this. A verifier that is
not run is not a verifier. **What would settle it:** P2's scheduler should run it,
not just `resolve`.

### The margin SD was assumed, not measured *(fixed 2026-08-29, P1)*

NBA's was written down as "~11.5 across recent seasons". Measured: 13.95, from
1,191 games. NFL's 13.2 against a measured 12.70 was close enough not to matter.
Neither explained the NBA model's apparent edge — the leak did — but an assumed
constant that decides how confident the *market* is made to look has no business
being unmeasured. `margin_sd()` now fails by name on anything undated.

---

## M1-M4, the MLB prop markets *(2026-08-30)*

### A blanket claim, generalised from one sport, written down as measured

`market/sources.py` said as a checked fact that *"ESPN's odds documents carry a
`propBets` link that returns nothing usable"*, and applied it to every prop
market of every sport by a comprehension over `SPORT_PROP_MARKETS`. Re-checked:
**false for MLB.** One 14-game slate carries 1,306 prop rows, 1,084 naming an
athlete, across all four markets.

The reading was of one NFL document and was probably correct about NFL. The
defect was the generalisation, and it had teeth: a test
(`test_a_market_with_no_source_says_so_rather_than_reporting_a_number`) and a
planted guard both asserted the blanket claim, so the wrong belief was *enforced*
in three places. Correcting the source meant correcting its guards, which is the
shape to watch for — a guard that encodes a measurement rather than a law will
defend the measurement after it stops being true.

Both now check the thing that stays true: an availability claim must be backed by
a fetch path, and an absence must state a reason. NBA's entry says explicitly
that it has **not** been re-checked, because an untested market and a market with
no source must not read the same.

### The feasibility report said lineup slot was available. It is, and it is useless

`battingOrder` is real and decodes cleanly. But it is a fact about a game that
has **started**: measured across three future dates, **0 of 41** scheduled games
carried a lineup, because they post about two hours before first pitch.

The feasibility probe checked a *final* game and reported the field as available,
which was true and misleading — the question a forecaster asks is whether the
field is available *when the forecast is written*. The factor set uses the
batter's **recent** slot and his recent plate appearances per game instead, both
facts about the past.

**What would settle it:** nothing further; but the general lesson is that
"the source carries field X" and "we will have field X at prediction time" are
different claims and the feasibility answer conflated them.

### R2's specified derivation had no data, and a better one existed

The ruling asked for the over/under side to be derived from cross-rung
monotonicity: P(over) must fall as the line rises, so a subject quoted at two
rungs identifies its own sides. Correct reasoning. Measured: **0 of 354 subjects
were quoted at more than one rung.** Every subject gets exactly one line.

What works instead is a *milestone anchor*: the same slate publishes one-sided
"2+ total bases" quotes, and a milestone at K+ is the same event as the over at
K-0.5, so its price states P(over) directly. Measured separation between the
matching and non-matching member of a pair: **0.001 against 0.10-0.19**, three
orders of magnitude. 173 pairs resolved, 1 refused as unseparable.

The forbidden method was measured too, and it deserved forbidding: the first row
in document order carries the shorter price in **62.7%** of pairs, which is
noise.

### Three declared factors that are not three instruments

`mlb_batter_rate` (hits per plate appearance) times `mlb_batter_expected_pa`
(plate appearances per game) **is** hits per game, which is exactly what
`mlb_prop_mean_vs_line` is built from. Measured on 2,444 sampled batter-games,
`corr(rate x pa, mean) = +1.000` — not close to one, one.

The consequence is visible in the fit: both came out causally backwards
(-5.39 and -0.27) because they act as corrections to a term the model already
has. **It is not ordinary collinearity and no pairwise check would find it** —
the pairwise correlations are -0.077 and +0.082. The dependency runs through the
product.

`mean_vs_line` does still dominate once the factors are put on a comparable
footing: standardised as coefficient times the factor's own spread, +0.527
against -0.314 and -0.179. The raw coefficient table says otherwise and the raw
coefficient table is misleading, because these three factors live on scales an
order of magnitude apart.

**Left as declared, not repaired**, because the factor set was declared in the
brief and changing it is a deliberate dated act (LAW 2), not something to do
quietly while fitting. **What would settle it:** redefine `mlb_batter_rate` over
a longer window than the mean uses, so it measures current form against
established level — information the mean does not already contain — and refit.

### A crosswalk refusal produces no line, not a void

The brief asked for the crosswalk-refused case to VOID the prediction. It does
not, and the reason is the standing rule that a missing line source degrades the
comparison and never the record: voiding would delete a legitimate blind forecast
because a third party's feed was unhelpful. The refusal is recorded, the prop
carries "no line" in words, and the prediction resolves normally against the
stat.

Note also that the crosswalk cannot run at selection time at all — it reads ESPN,
which is inside the LAW 1 quarantine — so there is no point in the flow where a
refusal could prevent a question being asked.

### The prop training set is slow, and avoidably so *(open)*

Each of the four fits takes roughly 12-13 minutes over 81,000 rows, and most of
that is `park_run_environment` and `league_run_environment` re-running a
multi-table scan **once per training row** when the answer only varies by
(stadium, season) and (season). A memo would cut it by most of its runtime.

Not done in this session on purpose: the fits were already running, and adding
an unproven cache to a path that decides what the model sees is not a thing to
do under time pressure. **What would settle it:** memoise both in
`build_prop_context`, keyed on the tuple they actually depend on, with a test
that the memoised value equals the uncached one for a sample of stadium-seasons.

### The record ends 2026-09-27 and several gates cannot clear *(open, by ruling)*

R3 keeps `GAME_TYPES = ("R",)`, so there is no postseason. With ~29 slates left
and a cap of 25 prop predictions a day, the arithmetic on the four gates is in
the M4 close-out. The interface must say so in words where a gate cannot clear
rather than showing a number that will never arrive.

### `FACTOR_SET_VERSION` was NOT bumped for thirteen new factors *(decision, 2026-08-30)*

The convention says bump whenever a factor is added. Thirteen were. It was not
bumped, and the reasoning is in `config.py` beside the constant so a reader finds
it where they look.

In short: every one of the thirteen applies only to the four **new** MLB prop
markets, which had no record to be made incomparable with. Nothing belonging to
`nfl:spread`, any NFL prop, `mlb:moneyline` or any NBA market changed. Bumping
would have declared four untouched records incomparable with their own futures —
a permanent split asserting a difference that does not exist.

The deciding argument is asymmetry: **not bumping is reversible and bumping is
not.** The cost of reversing is six resolved predictions of continuity across the
entire forward record, plus re-running the four prop fits, which are stored
against the version they were trained under.

**What would settle it:** the operator either endorses the narrower reading —
the version tracks changes to an *existing* market's instruments, not the
addition of a market — or calls for the bump, which is cheap today and expensive
later. The underlying mismatch is that the version string is global while factor
sets are per sport per market.
