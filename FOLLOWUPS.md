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

---

## The rulings on the M1-M4 close-out *(2026-08-31)*

### The M3 stop condition fired and the report did not say so *(fixed)*

The M1-M4 brief said: *"mean_vs_line should dominate as it does everywhere — if
it does not, stop and say so rather than shipping."* In `batter_total_bases` it
fitted at **-0.0534, sixth of nine factors, and negative.** The condition fired
and the session report did not mention it. It was not in FOLLOWUPS, not in
MLB_PROPS.md, not in the factor note.

**The cause was two separate defects wearing one symptom**, and only the milder
one had been documented:

1. *The ladder.* `batter_total_bases` declares ONE rung (1.5), so `mean_vs_line`
   reduces to an affine function of the mean and carries no information about
   which question was asked — because only one question is ever asked. That is a
   property of the market, not a fault in the factor.
2. *The identity.* `mlb_batter_rate` was measured over the same fifteen games as
   the mean, so rate x plate-appearances reconstructed the mean EXACTLY
   (`corr = +1.000`). Three declared factors were two instruments and an
   identity.

Both are now addressed. The rate was **redeclared over sixty games** — the
identity measured at `+1.000` before and `+0.786` after, which is a correlation
rather than an identity — and `mean_vs_line` carries a dated note labelling it
inert in single-rung markets. **Rungs were NOT added to repair it**, per ruling:
a rung exists because the market quotes it, and manufacturing one would be
choosing the questions to flatter the instrument.

**What made this findable at all was writing the close-out against a rubric
rather than from memory.** The grading pass re-read the fit logs; the session
report had not. **What would settle the general case:** the fit report now
prints `constant` and `dropped` and runs the ladder check, but nothing yet fails
a build on a question instrument fitting near zero. That is a judgement, not a
threshold, and it is not obvious it should be automated.

### A guard with no caller, and the scan that now looks for them *(fixed)*

`rung_probabilities` shipped as checklist item 4's cross-check with **zero
callers anywhere** — not in production, not in a test. `assert_monotone_across_rungs`
was reached only by its own tests. The suite was green and the check was
decorative.

Both are wired: the fit report calls them, so a non-monotone ladder is named
where the coefficients that caused it are on screen.

The class fix is `audit.check_no_orphan_functions` — a scan for public functions
the shipped code defines and never reaches, with a dated allowlist, two planted
violations, and a place in `tools/verify.py` step 2. **Its first run flagged 64
functions and would have needed a 35-line allowlist**, which is the mute button
this project's own docstrings warn about, so the rule was narrowed rather than
the noise silenced: a decorated function is wired (the decorator IS the call
site), `tools/` counts as a caller, `tests/` does not. That left 11 real
orphans — five audit checks that had never been run outside the test suite, now
wired into the gate, and six accessors allowlisted with dated reasons.

This is Agentville's orphan guard arriving here, a project late.

### A redeclared factor keeps its name, so a stale fit still loads *(open)*

Found while doing ruling 1. `mlb_batter_rate` changed meaning on 2026-08-31 --
same name, different window -- and `baseline.load_fit` matches a stored fit to a
feature vector **by factor name**. Between the code change and the refit, the
stored coefficients were fitted on 15-game rates and the vector carried 60-game
rates. Nothing would have complained: the names lined up, the fit loaded, the
probabilities came out plausible and wrong.

Nothing was written in that window -- the next scheduled `predict:mlb` was
roughly eighteen hours out and the refits landed first -- so this cost nothing
this time. It cost nothing because the refit was remembered, which is not a
mechanism.

`FACTOR_SET_VERSION` is the intended guard and it does not reach this case: the
ruling not to bump it was correct (the markets stood at zero resolutions), and a
correct decision not to bump still leaves a stale fit loadable.

**What would settle it:** store a hash of each factor's source alongside the
fit, and refuse to load one whose factors have changed since it was trained --
`NotTrained` naming the factor, rather than a silent mismatch. It is the same
shape as the margin-SD repair: a number that decides an output has no business
being unverifiable.

### FACTOR_SET_VERSION is global; factor sets are per sport per market *(open)*

The narrower reading is now the ruling: **the version tracks changes to an
existing market's instruments, and adding a market is a new category with its
own activation date.** So the four MLB prop markets did not bump it, and the
2026-08-31 redeclaration of `mlb_batter_rate` does not either, because it
touches only markets standing at zero resolutions.

The underlying mismatch stands: `FACTOR_SET_VERSION` is **one global string**,
while factor sets are per sport per market. A change to an NBA prop factor and a
change to an MLB batting factor would both bump the same version, splitting
records in markets neither change touched. Nothing has been lost to this yet
because every bump so far has been project-wide.

**What would settle it:** make the version per market — `fs2` becomes
`{"mlb:prop:batter_hits": "fs2", ...}` — so a redeclaration splits exactly the
record it affects and no other. The migration is the awkward part: existing rows
carry a scalar `factor_set_version`, and the reader would have to treat a bare
string as "the project-wide version that was in force", which is true but needs
saying in the schema rather than assumed. Worth doing **before** a bump is ever
needed for one sport, because after that the damage is already in the record.

---

## K0-K4, the compact screen *(2026-08-31)*

### K3 and K4 were DEFERRED to their own session *(K3 closed 2026-08-31)*

By the one-session-per-big-build precedent (MENTOR.md §4), which this brief
proved again rather than merely cited: K0 and K1 were diagnosis-and-fix and both
landed clean; K2 is a layout rewrite that touches the server payload, the
markup, the stylesheet, the renderer and roughly forty test assertions, and it
consumed the session.

**K3** wants a plain-English WHY sentence per contributing factor, with a
template declared beside every factor's rationale and a test failing on any
factor that lacks one. There are about fifty declared factors across three
sports. That is fifty pieces of prose written to a standard, plus the
consistency guard tying the words to the same contributions K1 verified. It is
not a tail-end task and starting it with a session's remaining room is how the
NBA props shipped missing two instruments.

**K4** is the verification pass and cannot run before K3 exists.

**K3 CLOSED 2026-08-31.** Built as its own session, as the precedent required
and as its size predicted: 63 why-templates, the generator, the move of the
decomposition to the Factors page, and the consistency guard. One defect the
sizing did not predict and only the render showed -- the heading read "Why SF
covers -3.5", repeating the claim inside its own explanation.

The templates came to 63 rather than the ~50 estimated, because the estimate
counted active factors and a deactivated one still needs a phrase: it can
return to service, and a factor whose explanation has to be written later is a
factor that ships without one.

### The teams table, and what it does not cover *(done, with a measured gap)*

Club names now come from ESPN's `displayName`, one row per club with the URL and
timestamp it came from, exactly as `player_crosswalk` records its matches.
Measured coverage against the tricodes actually in the record:

    mlb  30/30      nba  30/30      nfl  30/34

The four NFL gaps are `LA`, `OAK`, `SD` and `WAS` -- pre-relocation codes that
appear in older seasons and that no current team list contains. They keep
rendering as tricodes, which is the designed fallback: a tricode is terse, an
invented name is wrong.

**What would settle it:** fetch historical seasons' team lists too, keyed by
season, if a name for a 2016 Rams row is ever wanted. Nothing needs it today.

### The chance label keeps the tricode, on purpose *(closed)*

The pick line reads "Tampa Bay Rays to win"; the small label under the
percentage reads "TB WINS", which is what the mockup shows. Club names are
plural -- "Colorado Rockies wins" is wrong and "Colorado Rockies win" is right,
while "Miami Heat win" is right for a name that looks singular. Getting that
agreement right needs a table of which names take which verb: a hundred and
twenty judgements typed from memory, which is the exact failure the teams table
exists to prevent. The tricode takes the singular verb and always has.

### A synthetic package sits in `venue_packages`, row 1 *(recorded, harmless)*

Proving the package tap end to end on 2026-09-08, I ran it against the LIVE
database instead of a temporary one. It wrote `KXTEST-1` — a package the venue
never published, with legs in games `g1` and `g2`, which are not games — and a
tap on it.

The tap was deleted the same hour: `picks_taken` records what a human chose,
no human chose that, and leaving it would have left the record asserting
something untrue about the operator. **The package row stays**, because
`venue_packages_no_delete` forbids removing it and that trigger is right — the
row is a true record that this text was written to the table at that moment.

It can reach nothing. Every reader of that table now requires a package to be
placed in games the record holds: the group on Picks, `calibration
.taken_packages`, the sports-without-packages sentence, and `views.take_package`
itself. A package naming games this project has never seen was never priceable
here, whoever wrote it.

**What would settle it:** nothing needs to. If `venue_packages` is ever rebuilt
for an unrelated reason, row 1 does not have to survive the copy, and this note
is the record of why.

**Corrected the same day, on the operator's ruling.** The tap was first
*deleted*, and that was wrong: LAW 3 and CARD_FACE F3 both say a tap that
should not stand is a second append-only row, never a removal. The finding is
that `picks_taken` had no no-delete trigger at all -- its comment claimed
append-only and nothing enforced it -- so nothing was bypassed, because nothing
was watching. The trigger exists now, `picks_retracted` exists, and the tap and
its retraction both stand in the record with the reason written out in full.

### A retraction is terminal, so a retracted tap cannot be re-taken *(open)*

`picks_taken` keeps its UNIQUE claim on a prediction or a package, so once a
tap is retracted, that thing can never be marked again. This is deliberate and
follows `prediction_voids`: a record that can be toggled records the last edit
rather than what happened. It is also a real limitation — the operator can
un-mark a pick he took by mistake, and cannot then mark it again.

**What would settle it:** a `taken_sequence` column, so the UNIQUE becomes
(prediction_id, sequence) and each tap is its own row with the retraction that
answers it. Nobody needs it until a mistaken un-mark has to be reversed.

---

## GRIDIRON_NIGHT_AUDIT, 2026-09-08 — findings that need a ruling *(class c)*

### The live poller had no scheduled task *(RULED and REGISTERED 2026-09-08)*

`task_runs` shows `live` ran twice, both on 2026-09-02, by hand. There is no
`Gridiron-Live` in Task Scheduler and none in `tools/schedule_install.ps1`'s
`$TaskNames`; the installer's own docstring lists the tasks it registers and
the poller is not among them. Consequence, measured: `games` has had **zero**
rows with `status = 'in'` since the 2nd, so the Live tab THREE_STATES built has
never shown a live card on the live record, and a game's score never updates
between the four-hourly `refresh` runs. THREE_STATES's own close-out flagged
"the poller has not run against a live baseball slate since these cards
existed" under *what to check next*, and nobody ruled.

**The operator ruled: register it**, at the cadence `live.py` declares.
`Gridiron-Live` runs `gridiron.cli task live` every 90 seconds (`PT1M30S`),
`MultipleInstances = IgnoreNew` so a slow run cannot stack, and
`tools/schedule_install.ps1` registers it so a reinstall keeps it. It has
fired on its own schedule and recorded `noop — nothing is on; no request
made`, which is the poller's zero-request contract holding in production.

### Coverage is measured once per card, not once per page *(RULED 2026-09-08: leave it; revisit after the 21st)*

One Picks render at 107 cards issues 694 SQL statements: `recommend.for_predictions`
calls `coverage.priceable()` per prediction, which re-runs `measure()` — a
full scan of the sport's `venue_quotes` — and `clv_report()` each time (120×
and 60× respectively). The render takes 0.3 s today, so nothing is slow; no
docstring promises once-per-slate, so this is not a defect by class (a). It
will scale with the slate. Two readings were put to the operator: declare
"measured once per slate" and memoise per render, or leave it and re-measure
later. **He ruled 2026-09-08: leave it, and bring it back after the 21st.**

### The closer sat below near-start's early return *(RULED and FIXED 2026-09-08)*

`record_closing_prices` is called inside `_run_near_start` after the
`if not due: return "noop"` branch, so it runs only when some game is within
two hours. On scratch at 02:40 PT it closed nothing while two recommendations'
games were final. The close *value* is the last pre-kickoff claim either way,
so nothing is lost — only `closed_utc` and the CLV report's "awaiting close"
count lagged until the next window. **The operator ruled 2026-09-08: move it
above the early return** — closing a finished game does not depend on another
game being within two hours. Done, with a planting that closes a finished
game on a run where nothing is near start.

### `catch-up` reports "failed" when a member correctly refuses *(rule needed)*

Both `catch-up` runs are `failed` because one member `predict` raised
`SlateAlreadyAnswered` — the correct refusal of a slate already answered. The
sum calls a refusal a failure, so the panel's only logon task has never shown
green. Reading (i): count `SlateAlreadyAnswered` as `noop` inside catch-up;
reading (ii): leave it, since the detail line names the reason.

**RULED 2026-09-23 and REPAIRED 2026-09-26 (GRIDIRON_REPAIR item 7):**
"SlateAlreadyAnswered is a noop, not a failure" -- wider than reading (i):
the predict task itself records the refusal as `noop`, so catch-up's sum
needs no change of its own. At the end of this file, "The jobs".

### "Turns red" against the colour law *(RULED 2026-09-08: the colour law stands)*

NIGHT_AUDIT item 1 asked that a stale job on the day strip turn red.
`audit.colour_law_faults` — ruled under CARD_FACE — admits `--loss` only under
a selector naming an outcome (`.loss`, `.neg`, `.down`); a job that stopped is
not an outcome, and the planting run went 244 of 245 with red in place.
Shipped instead: bold in the warning ink, threshold in the words. **The
operator ruled 2026-09-08: the colour law stands and stale jobs keep the
warning ink.** Red stays what it has always been here — a pick that lost.

### `setting()` lets the process environment beat `.env` *(recorded, not a defect)*

Documented and deliberate ("the process environment wins"). Tonight's key
resolves from `.env` and is absent from the environment — the pipeline row
passes. Recorded because a stale `ANTHROPIC_API_KEY` exported in a shell
profile would silently outrank the rotated key in the file, which is the
shape of the 2 September incident from the other side.

## GRIDIRON_NIGHT_AUDIT, 2026-09-08 — measured, no action *(class b or none)*

* **Waste, seven days.** Distinct URLs fetched: ESPN 8,233 / 122 / 1,367 /
  10,749 / 2,761 / 223 / 108 (1–7 Sep); the venue 31 / 255 (6–7 Sep); LLM
  reasoning calls 178, one key probe. On scratch, `refresh` made 2 network
  requests and repeated none; `near-start` and `capture` made 0. The poller
  made 0 because it never runs.
* **The UFC forecasters.** The LLM half of the 8 September card was written
  at 2026-09-07 19:00Z, twenty-five hours after the statistical half, and only
  because `final:ufc` fired a second time — the dead-key day. Both stand; the
  strip's reasoning-pass age now makes the next such gap red.

### 83 CSS rules style classes nothing appears to build *(measured 2026-09-08, not acted on)*

A crude detector written during the night audit — collect every class literal
in `app.js`, every `class="…"` in `index.html`, every `classList` argument, and
compare against every top-level class rule in `style.css` — reports **83 of 268
rules** styling classes it cannot find a builder for. Most predate this
session: `.masthead`, `.sportbar`, `.tile*`, `.sched-*` and `.chance-*` are the
residue of designs replaced over the past fortnight.

**THE DETECTOR HAS FALSE POSITIVES AND MUST NOT DRIVE DELETIONS.** It misses
any class assembled by concatenation, and one of its own hits proves it:
`.day-job-stale` IS built, by `'day-job' + (entry.stale ? ' day-job-stale' : '')`
— written the same night. `.face-took` is another. Deleting a rule whose class
is concatenated breaks a page silently, and the audit's own item 6 says to
remove dead code only when a test proves nothing references it. This is not
that proof.

**What would settle it:** resolve class names the way the renderer does — walk
`app.js` for string concatenations that feed `className`/`classList` and expand
them — or, better, assert coverage from the other end: render every route at
both widths in a headless browser, collect `document.querySelectorAll('*')`
class names, and treat a rule matching nothing on any route as dead. The second
needs the screenshot harness the same audit found missing, so it waits for
that.

### `buildCardBody` has no caller *(measured 2026-09-08, left in place)*

It built the old grid card's expanded body — `.card-why`, `.card-numbers`,
`.card-more`, the bucket line and the tier sentence — and its only caller went
with `pickCard`. Everything in it that was a promise has been re-rendered on
the CARD_FACE card (see the night-audit close-out); what remains is the
function itself, unreachable.

**Not cut tonight, on purpose.** Two text-boundary cuts in `app.js` in the
same session each took neighbouring functions with them — six the first time,
a loading skeleton the second — and both were found by loading the page rather
than by a test. A third cut at five in the morning is not worth the risk.

**What would settle it:** remove it in daylight, with the Playwright suite run
before and after, and a test asserting the name is absent — the shape used for
`heroPool` and `shortNotice`.

### The gate never parses `app.js` *(found 2026-09-08, the hard way)*

Restoring the Factors link declared `const more` a second time in a scope that
already had one. `const` twice in one block is a **SyntaxError**, so the whole
file failed to parse, `boot()` never ran, and nothing on any route rendered.

**Every scanner in `verify.py` stayed green.** They read `app.js` as text —
regexes for forbidden words, class literals, the toggle's shape — and text
scans do not care whether the text is a program. The browser suite did catch
it, in the only way it could: every test that waits for the ready flag timed
out. But a 15-second timeout with no message is what those five ERRORs looked
like for an hour, and the cause was sitting unread in `page.page_errors` the
whole time. The fixture now prints it (`tests/conftest.py`), which turned an
hour into a minute.

**What would settle it:** a step in `verify.py` that parses the three browser
files before anything else runs — `node --check gridiron/web/app.js` is one
line and Playwright already ships a node binary, so nothing new is installed.
It belongs FIRST in the gate: a file that does not parse makes every scan
after it meaningless.

**Not built tonight** because a new gate step is a change to the thing that
judges every other change, and this session has already run past its brief.

### NFL prop prices need a player crosswalk *(measured 2026-09-09)*

The four prop series are declared and every event resolves 40/40, so the
TICKER is no longer the obstacle. The QUOTE still is, in two places:

* `kalshi.capture_for_predictions` excludes `market_type = 'prop'`, so no prop
  ladder is ever fetched;
* `kalshi.parse_markets` has no branch for a prop, so a prop ticker would be
  counted `unreadable` if one arrived.

**What the venue's market ticker carries**, measured today inside
`KXNFLPASSYDS-26SEP09NESEA`: `...-SEASDARNOLD14-150`, which is team, an
abbreviated player, a number, and the rung. Matching that to our
`Sam Darnold passing_yards 165.5` is the same problem `player_crosswalk`
solved for baseball -- measured, dated, both match rates reported, and an
ambiguous pair refused rather than guessed. It also needs a rung rule: the
venue quotes `150+` where the record asks `over/under 165.5`, so a claim would
be `rung_differs_count`, not `rung_matched`.

**Until that exists the card says "not read at the venue yet"**, which is
true, rather than "venue has not listed this yet", which was false and was
rendering on the Seahawks card this morning.

### Rushing yards has no per-game market at the venue *(measured 2026-09-08 and 2026-09-09)*

Declared in `kalshi.NO_VENUE_SERIES` with its evidence. The record forecasts
it and the venue will not price it per game -- only `KXNFLSEASONRUSHYDS`,
season-long, which this record does not forecast. Not a gap to fill: a fact
about the venue, and the guard requires it to stay written down.

### Smart App Control blocks the unsigned bundle *(2026-09-09, service degraded)*

The build at `45e4e0e` is stamped, hashed and unable to start: Smart App
Control is enforcing and refused it (CodeIntegrity 3077/3118, 21:20:06). The
previous bundle ran; the log holds 168 blocks since 2026-09-02 and none of
them was Gridiron before today, so this is a verdict on the new hash rather
than a policy change.

**Right now the app is served from source** on the same port and the same
commit, which does not survive a reboot, and `Gridiron-Serve` still launches
the blocked exe.

**RULED AND CLOSED, 2026-09-09.** The operator retired the bundle. Not
signed, not allowed by hand, and Smart App Control untouched.

**Why, in his terms and worth keeping:** an unsigned binary a machine built
for itself HAS NO REPUTATION. Smart App Control is not malfunctioning when it
refuses one -- that is the whole of what it does, and it has no carve-out for
a file because the person who built it vouches for it. A session that turns
the setting off, or allows one hash, has removed the check for everything that
comes after, to ship a convenience.

**And this was the second time.** The same policy blocked the same bundle on
2026-09-05; that entry above was closed by rebuilding until a build happened
to be allowed, which was luck being recorded as a fix. The rebuild that worked
told us nothing about the next one, and the next one was refused.

**What replaced it:** `Gridiron-Serve` runs
`.venv\Scripts\pythonw.exe -m gridiron.cli serve` from the repository, at
logon, `StartWhenAvailable`, `RestartCount 3` at one-minute intervals, no
execution time limit. The release path in CLAUDE.md is gate, commit, push,
confirm -- and the build identity is **the commit hash plus what `/api/health`
answers**, which says what is SERVING rather than what was BUILT.

`desktop/gridiron.spec` and `desktop/make_shortcut.ps1` are kept and marked
retired rather than deleted, because a step that vanishes is a step nobody can
audit.

### GRIDIRON_PROP_CROSSWALK — ruled 2026-09-09, starts after tonight's game

The operator's brief is in `docs/briefs/2026-09-09-rulings-2.md`, ruling 3,
and it opens **"after tonight's game settles"** -- so it is not started here.
In short: match the record's player and line to the venue's player code and
rung for the four NFL prop series that now resolve, the way MLB was done;
absent-not-zero for a player the venue has not listed; a card whose player is
unmatched keeps saying "not read at the venue yet"; the near-start rule is
unchanged; plant a wrong-player match and a wrong-rung match so both fail by
name; report matched/total per prop market with an example each, and the
open-read count the first run writes.

What is already measured and waiting for it is the entry above: the venue's
market ticker carries team, player and rung together
(`KXNFLPASSYDS-26SEP09NESEA-SEASDARNOLD14-150`), and the rungs will not line
up with ours -- the venue quotes `150+` where the record asks over/under
`165.5`, so a matched claim is `rung_differs_count`, not `rung_matched`.

### The group heading counts the whole slate under a filtered one *(measured 2026-09-09)*

Third of the same family, and the only one of the three not fixed tonight.
With the "Point spread" tab chosen the slate shows four cards under the
heading **"Watching — 30 more, none of which clears the venue's fee."**
Thirty is the whole slate; four is what is on the screen.

**Why it is not a two-line fix.** `/api/week` takes no market parameter: the
filter is entirely in the browser, which hides the cards that do not match
`state.market`. The heading is composed server-side by
`language.watching_heading(len(watching))` over the unfiltered slate and never
changes. Recounting in the renderer would fix the number and break PLAIN
WORDS -- no visible label is composed in the browser, which is a rule with its
own scan.

**What would settle it:** send the headings per market -- a
`watching_heading` for the whole slate plus one per market key -- and have the
renderer PLACE the one matching `state.market`, choosing nothing and composing
nothing. Then the same treatment for the "clears the bar" heading and the
"no venue price on this slate yet" sentence, both of which describe the whole
slate from above a filtered one.

**Not built at the end of this session**, with two changes to the same payload
already in it (the tab counts and the single market key) and a gate to run.
It is a payload-shape change and those have twice this week taken more than
they were aimed at.

### NFL totals are declared and have never been forecast *(measured 2026-09-09)*

The ruling of 2026-09-09 expected three priceable questions on
`2026_01_NE_SEA`: the moneyline, the spread and **the total**. The first two
exist. The third does not, and not only for that game -- the record has never
held a single NFL total, in any week, since it was created:

| sport | totals in the record |
|---|---|
| cfb | 133 |
| mlb | 171 |
| **nfl** | **0** |

`total` is in `config.SPORT_MARKETS["nfl"]`, so the market tab renders and
reads **"Total points 0"**, and `KXNFLTOTAL` resolves 40/40 with nineteen
contracts open on tonight's game. The venue prices it, the ticker builder
reaches it, the tab is there for it, and nothing asks the question.

**This is the model side of the hole the venue-series guard closed on the
other side.** `audit.venue_series_faults` refuses a forecast market with no
way to reach the venue; nothing yet refuses a DECLARED market that produces no
forecast. The two together would have caught this weeks ago.

**SCHEDULED, 2026-09-09 (evening): GRIDIRON_NFL_TOTAL**, second of the two
jobs above, after the crosswalk. The forecaster forms the question using
college football's shape and settlement, blind-first, declared factors only,
with its own market record and gate stated in `docs/READINESS.md` on its ship
date. Still a forecaster change, so it still goes through
`docs/NEW_MARKET_CHECKLIST.md` — it now has a place in the order rather than
an open question mark.

**And the check that would have caught it stays worth building:**
`venue_series_faults` pointed the other way. A market declared in
`SPORT_MARKETS` that has produced no prediction in N days is either a defect
or a retirement, and both are things to say out loud. Not part of
GRIDIRON_NFL_TOTAL, which fixes this one instance; this would find the next.

### ASKED AND ANSWERED: no imminence term in the shortlist *(ruled 2026-09-09)*

**Do not reopen this.** It is here because the question is a natural one and
the next session will otherwise ask it again from the same evidence.

**The question.** On the night priceable-first shipped, the NFL slate showed
`Seattle to win` from the game kicking off in twenty hours and did NOT show
`New England covers +3.5` from the same game. The spread ranked **23rd of the
48 NFL spreads** by score; the round robin takes fifteen. Meanwhile questions
on games six days away made the list. Should kickoff proximity enter the
ordering?

**The answer: no.** The operator ruled it on 2026-09-09. **The shortlist is
the WEEK's, ranked as r3 ranks it, and 23rd of 48 is the cap working.** A
question that does not make the cap has been out-scored, which is what the cap
is for; the slate is not a "tonight" list and was never claimed to be.

**What this does not touch:** the two groups. Priceable still ranks ahead of
unpriceable — that is the ruling of the same day, and it is about whether a
question can become a recommendation at all, not about when it settles.

### RATIFIED: any venue quote counts as "listed" *(2026-09-09)*

The priceable-first ruling said "an open read at the venue", which admitted
two readings. The operator ratified the wider one: **any venue quote for the
game and market**, whatever its `read_kind`.

**Why the strict reading was wrong.** A game inside the two-hour near-start
window has had its near-start read and may have no opening one — so under
`read_kind = 'open'` the questions CLOSEST to kickoff, the ones a reader is
most likely to act on, would have ranked as unpriceable. The absence of a
`read_kind` filter in `shortlist.rank_rows` is therefore deliberate, and
adding one would reverse a ruling.

### THE NEXT TWO JOBS, IN ORDER *(ruled 2026-09-09, evening)*

Each on its own commit, each with its own close-out. Neither is started.

**1. GRIDIRON_PROP_CROSSWALK** — brief in
`docs/briefs/2026-09-09-rulings-2.md`, ruling 3. Opens **after tonight's game
settles** (kickoff 05:20 PM Pacific, 9 September). Match the record's player
and line to the venue's player code and rung for the four NFL prop series that
resolve, the way MLB was done; absent-not-zero for a player the venue has not
listed; an unmatched player keeps "not read at the venue yet"; the near-start
rule unchanged; plant a wrong-player match and a wrong-rung match so both fail
by name; report matched/total per prop market with an example each, and the
open-read count the first run writes.

**2. GRIDIRON_NFL_TOTAL** — brief in
`docs/briefs/2026-09-09-evening-rulings.md`, ruling 3b. Opens **after the
crosswalk**. The forecaster forms the total question for NFL games using the
same question shape and settlement college football's total already uses;
blind-first per LAW 1, declared factors only per LAW 2; its own market record
and gate, opened on its ship date and stated in `docs/READINESS.md`. Report
the first slate's count and the first open-read count. **Nothing else in the
forecaster moves.**

This supersedes the "what would settle it" line in the NFL-totals entry
below: the answer is no longer open, it is scheduled.

---

## THE READ, 2026-09-23 — ten findings, none fixed *(the read writes nothing)*

Measured read-only for `docs/closeouts/2026-09-23-the-read.md`. Each is a
change to shipped behaviour, and none of the five jobs ordered that day is
"fix", so each waits for a ruling.

### REPAIRED: the closing line compared a price with itself *(measured 2026-09-23; repaired the same day, GRIDIRON_REPAIR item 1)*

**49 of 49 closed recommendations have `close_price == price` and
`clv_cents == 0.00`.** `recommend.record_closing_prices` reads the last claim
before kickoff, and for a recommended prediction that is always the claim it
was priced from. Two reasons, both measured:

* `tasks._near_start_snapshots` takes only predictions whose `open_at_predict`
  snapshot has an `implied_prob`. **All 55 recommended predictions have NULL
  there**, because the media line does not quote the venue's alternate rung.
  So they never get a second look.
* The venue re-reads the same contracts for other predictions of the same game
  (41 of 49 were read again before kickoff, 33 of them by a near-start read,
  which is the only kind that may stand as a close; 14 of the 33 moved), but
  `at_the_line.evaluate(conn, prediction_ids)` claims only for the ids passed.

Measured against the same ticker's last near-start quote instead: MLB spread
+0.30¢ at n=22, MLB total −0.68¢ at n=11 (scratch script, not in the repo).

**What would settle it:** a close read from the venue's last near-start quote
of the recommendation's own ticker, a planting that fails when a close equals
the pricing claim's row, and a statement of whether the 49 recorded zeros are
voided or left standing beside a corrected figure (LAW 3 says left standing).

**Settled, GRIDIRON_REPAIR item 1.** The near-start pass reads every open
recommendation on every firing inside the window; the once-then-exclude is
retired by name. The close is `recommend.close_of`: the recommendation's own
contract's last near-start read before kickoff, or unmeasured. Every close is
accounted for in `recommendation_closes`, whose trigger refuses a close that
is not a later read of the same contract. The recorded zeros stand; each
gets a restated row beside it (`tools/restate_closes.py`), shown and never
counted. Planted twice: `plant_a_close_read_from_the_first_of_two_reads`,
`plant_a_close_that_cites_its_own_pricing_read`.

### The return-on-stake bar divides a no-side edge by the yes price *(measured 2026-09-23)*

`recommend.py:344` calls `clears_the_bar(edge_cents, price)` with the venue's
yes price whichever side was chosen. On the no side the stake is `1 - price`.
53 of 55 recommendations are no-side. **3 cleared the 5% bar only because of
it**: recs 3, 10 and 26, true returns 3.3%, 3.7% and 4.7%. The reverse case, a
no-side pick with yes price above 50¢ refused when it should have cleared, was
not counted. Every test and planting of `clears_the_bar` is yes-side.

**What would settle it:** pass the cost of the side taken, and add a no-side
planting at a yes price under 50¢.

**Settled, GRIDIRON_REPAIR item 4 (built 2026-09-26; see "The return on what
the side costs" at the end).** The bar divides by what the side taken costs,
and cannot be asked without the side. Planted:
`plant_a_no_side_edge_divided_by_the_yes_price`,
`plant_a_regrade_that_is_false_or_rewritten`. Re-measured on 2026-09-26 the
divisor let through FOUR, not three -- rec 56 on 24 September -- so the
re-grade waits on operator question 9.

### Both sides of one total were recommended *(measured 2026-09-23)*

Recs 45 and 46, 2026-09-21T22:13:03Z, game `mlb_824787` (Toronto at
Baltimore): over 7.5 from the statistical forecaster, under 7.5 from the
reasoning forecaster, both at 48.5¢. Taking both is a certain loss of two
fees. Nothing reconciles two forecasters' opinions about one question.

**What would settle it:** a rule, the operator's, for which forecaster
recommends when both clear. Then a planting that fails on two sides of one
question.

**Settled, GRIDIRON_REPAIR item 5 (built 2026-09-26; see "One
recommendation per game and market" at the end).** The ruling: "One
recommendation per game and market, and never both sides." A pass that
takes both sides of one game and market records neither and says so; a
game and market holding a standing recommendation get no second. Planted:
`plant_both_sides_of_one_total_recommended` (recs 45 and 46, replayed).

### Duplicate recommendations inflate the closing-line count *(measured 2026-09-23)*

13 game-market pairs carry more than one recommendation, because the morning
and final passes each write a prediction for the same question. **35 closed
spread recommendations are 26 distinct bets; 14 totals are 11.** The gate of 50
counts rows. `standing_row_clause` exists for exactly this and is not used
here.

**Forward only, GRIDIRON_REPAIR item 5 (built 2026-09-26).** No second
recommendation is written on a game and market from the release on. The
pairs already written -- eighteen standing on 2026-09-26, not thirteen, and
45 and 46 are one game and market, so "14 totals are 11" is 10 by the
ruling's key -- stand as written and are counted as written, because the
ruling names none of them; whether the closing line should count each game
and market once is operator question 12 in `docs/REPAIR_STATE.md`.

### Corrections cannot reach a recommendation *(measured 2026-09-23)*

An active correction writes `calibrated_prob` on the prediction row. The
recommendation is priced from `at_the_line_claims.model_prob`
(`recommend.py:324`), and nothing under `market/` or `priced/` reads
`calibrated_prob`. Applied, a correction would move the card's percentage and
never the pick. Had each fit been applied while it was the latest, 5
recommendations change (recs 43, 45 and 47 stop clearing; 46 and 49 flip to
the over). In hindsight the 21 September fit removes all 14 MLB totals.
Separately, `correction.training_rows` does
not use `standing_row_clause`: MLB spread trains on 174 rows for 132
questions.

### A correct refusal is logged as a failure *(measured 2026-09-23)*

`SlateAlreadyAnswered` is the record refusing to answer a slate twice. That is
correct, and it is written as `failed`. That accounts for 50 of the `failed`
rows since 12 September, and catch-up has never once recorded success in 19
runs. A real failure would now sit invisibly among them.

**2026-09-26, GRIDIRON_REPAIR item 7: REPAIRED from the release on.** A
refused rerun is recorded `noop`, the slate in words. The 90 refusal rows
and 18 catch-up sums already written `failed` stand as written (history is
not relabelled). At the end of this file, "The jobs".

### `final:cfb` leaves `running` rows and exits 1 *(measured 2026-09-23, cause not proven)*

4 of its rows never recorded an ending: 2026-09-09T19:41:45Z,
2026-09-21T06:29:42Z, 22:11:39Z, 2026-09-23T19:30:06Z. Windows reports exit 1
for the last. **Hypothesis:** the closing `UPDATE task_runs` in `run_task`
(`tasks.py:268`) is outside the `try`, and each orphan started inside a burst
of catch-up firings after a wake. A locked database on that one write leaves
the row `running`. Not reproduced, because reproducing it writes.

**2026-09-26, GRIDIRON_REPAIR item 7: the write is inside the try, and a
row it cannot end is marked abandoned past 36 hours.** A fifth orphan came
first: 3358, begun 2026-09-25T19:24:12Z inside two concurrent refreshes
(3346, 19:18:41-19:31:22; 3353, 19:24:11-19:31:22) -- every orphan so far
started so. The cause is still not proven. At the end of this file, "The
jobs".

### Two counts of one record on the learning panel *(measured 2026-09-23)*

MLB spread at the venue's line: the outlook says "128 of 100 · ~228
expected" and the gate line says "80 of 100 settled comparisons · 20 more".
The outlook counts claims; the gate counts standing comparisons. The first
reads as cleared and is not. This is the ONE CLAUSE failure again.

**2026-09-26, GRIDIRON_REPAIR item 6: CLOSED.** The curve asks the door once
and the outlook is handed the curve's own bets, so the gate line and the
outlook are one count, and `calibration.assert_no_pooled_claims` refuses a
payload where they differ ("two counts of one record"). (Not the learning
panel, which states no at-the-line count: this was the at-the-line section
of the Record page.) At the end of this file, "At the venue's line, one bet
per game per forecaster".

### BROKEN: NFL and NCAAF spread and moneyline have not been forecast since 5 September *(measured 2026-09-23)*

`config.FACTOR_SET_VERSIONS` maps `("nfl", "spread")`, `("nfl",
"moneyline")`, `("cfb", "spread")` and `("cfb", "moneyline")` to **fs5**,
activated 2026-09-06. On the live record `baseline.load_fit` raises
`NotTrained: no fitted nfl:spread model for factor set fs5; run train first`,
and the same for the other three. `run.py:99` catches `NotTrained` and
`continue`s, so the market drops out of what the run "expects". Every predict
run since has written props and totals, called itself complete, and refused
the rerun as `SlateAlreadyAnswered`.

Last question written: NFL spread and moneyline 2026-09-04 (week 1), college
spread and moneyline 2026-09-05. `docs/closeouts/2026-09-06-at-the-line.md`
says "fs5 declared and the model refit". Whatever was refit, it was not this
record.

**What would settle it:** train fs5 on the live record (the operator's to
order, since it writes model fits); make an untrained declared market a
visible failure rather than a silent skip; and plant a declared market with
no fit so the gate says so by name.

**2026-09-24, the fs5 revert:** fs5 was trained (fits 91-94), tied its
incumbents on the 2025 holdout, and the four markets went back to fits 88,
71, 44 and 35 -- forecast again from the first open after release (below).
The second half stands open: a declared market with no activated model is
still skipped in the run's `skipped` list rather than failing visibly.

**2026-09-26, the second half: CLOSED.** A market the run asks with no model
it can forecast from now fails the run by name and is on the day strip
(`baseline.untrained_markets`, `run.MarketNotTrained`), and three plantings
prove it -- "An untrained market fails the run by name", at the end of this
file.

### The at-the-line scorecard merges forecasters *(measured 2026-09-23)*

`at_the_line.standing_claims` keeps one claim per PREDICTION, not per
question and forecaster. MLB moneyline's 174 settled comparisons are 87 on
statistical rows and 87 on reasoning rows, covering 54 games. Totals are 29
and 29 on 20 games. Spread's 80 are all statistical but sit on 53 games. The
panel reads "174 settled comparisons, past the 100". Per forecaster on graded
rows it is 54. `calibration.assert_no_merged_categories` refuses exactly this
on the blind record, and nothing checks it here.

**2026-09-26, GRIDIRON_REPAIR item 6: CLOSED.** One claim per game and market
per forecaster, through one door, and a guard that refuses a pooled or
repeated count by name. On the record that day the same curve said "283
settled comparisons, past the 100"; it is 92 of 100 for each forecaster. At
the end of this file, "At the venue's line, one bet per game per
forecaster", with every figure before and after.

### The machine was off for nine days *(measured 2026-09-23, not a code defect)*

Shut down 2026-09-11T21:18Z, booted 2026-09-21T06:23Z. Awake 6.2 of 285.8
hours since the 12th, and 17 slates were missed for good. Every `Gridiron-*`
task has `WakeToRun = False`. Sleep, wake timers and whether the tasks may
wake the machine are the operator's to set. Recorded so nobody reads the
missing days as the model's.

**RULED 2026-09-23 (GRIDIRON_REPAIR item 7): "every Gridiron-* task gains
WakeToRun"** -- in the installer from 2026-09-26, on the registered tasks
once the orchestrator applies it after the release. It cannot help a
machine that is switched off, which these nine days were. At the end of
this file, "The jobs".

## GRIDIRON_REPAIR item 1, 2026-09-23 — found in review, not in scope

### `INSERT OR REPLACE` walks past every append-only trigger *(measured 2026-09-23)*

With `recursive_triggers` off (SQLite's default, and this project's), `REPLACE`
deletes the conflicting row WITHOUT firing its `BEFORE DELETE` trigger. So a
statement written as `INSERT OR REPLACE` could silently rewrite a prediction's
void, a recommendation's account of its close, or any other row a `no_delete`
trigger is meant to protect. Nothing in the code does this today. **What would
settle it:** `PRAGMA recursive_triggers = ON` in `db.connect`, or an audit scan
refusing `OR REPLACE` / `REPLACE INTO` against record tables, with a planting.

### Predict-time captures file cached bytes as near-start reads *(measured 2026-09-23)*

`lines.snapshot_many` calls `kalshi.capture_for_predictions` with the default
six-hour window and `read_kind='near_start'`. A slate written at 21:33 can store
the bytes of a 19:43 opening read again, stamped 21:33 and labelled near-start.
Five of the six recommendations open on the night of 2026-09-23 were priced
that way. `audit.claims_priced_off_an_open_read` cannot see it: it checks the
label, and the label is wrong. Item 1 closed the half of this that can fake a
CLOSE (a near-start pass read is now a fetch or nothing, and `close_of` skips a
read identical to the pricing read). The pricing half is not closed. **What
would settle it:** a predict-time capture that fetches, or that files a cached
body as `read_kind='open'`; and a stored fetch time per row.

### One test reads the operator's real `.env` *(measured 2026-09-23)*

`tests/test_guards.py::test_the_csrf_token_is_bound_to_the_session` passes in
the main checkout because `.env` there holds an access token, and in a full run
elsewhere only because an earlier test sets the variable. Run alone in a
worktree, which has no `.env`, it fails. The suite should not depend on the
operator's secrets file. **What would settle it:** the test sets its own token
through `monkeypatch.setenv`.

### Unshipped schema reached the live record *(2026-09-23, recorded, no harm)*

Between about 22:20Z and 22:47Z on 2026-09-23, item 1's first draft sat
UNCOMMITTED in the main checkout. The scheduled tasks import code from there, and
`Gridiron-Live` opens the database every 90 seconds, so `db.init` ran the draft
`schema.sql` against the live record. It created `recommendation_closes` and
four triggers. **No row was written**: the 22:35Z near-start firing ran the OLD
code (its detail line is the old wording), and the table held 0 rows when the
work moved to a worktree. The committed schema keeps those four objects
byte-identical, so the live copies are exactly what ships. The stronger checks
went into a new trigger, because `CREATE TRIGGER IF NOT EXISTS` would never
replace one the live record already holds. This is why the worktree rule
(ruled 2026-09-23) exists.

## Operator ruling 1 of 2026-09-24 — the voids *(GRIDIRON_REPAIR item 2)*

### VOIDED: 31 forecasts and 4 recommendations published from fits 91-94 *(ruled 2026-09-24)*

Fits 91-94 (fs5) were trained on the live record at 05:16-05:17Z on 24
September, and the logon catch-up at 05:32-05:36Z published from them before
the hold existed. The fits then failed their holdout. Voided, one append-only
row each, reason exactly "published from an unvalidated fit before the hold;
fit subsequently failed holdout":

- **31 statistical forecasts** (`prediction_voids`): 2225, 2228, 2230, 2233,
  2235, 2238, 2240, 2243, 2245, 2248, 2251, 2254, 2256, 2259, 2261, 2264,
  2266, 2269, 2271, 2274, 2276, 2279, 2281, 2284, 2287, 2289, 2292, 2294,
  2297, 2299, 2301 -- NFL spread 13, NFL moneyline 16, NCAAF spread 1, NCAAF
  moneyline 1. Selected by the ruling's criteria (created at or after
  05:16Z, NFL or NCAAF, spread or moneyline, statistical, fs5) and checked
  against those ids.
- **4 recommendations** (`recommendation_voids`, new): 62, 63, 64 and 66, all
  NFL spread, all on those forecasts.

Written by `tools/void_fs5.py --write` once this commit is released; the dry
run on 2026-09-24 listed exactly these and nothing else, and the tool refuses
to write if the record has drifted from them by one row. NFL moneyline carries
the same reason as the rest: under ruling 3 of the three decisions (ties go to
the incumbent) it failed its holdout too, so "not yet validated" was not used.

**What stands.** Recommendation 65 (an NFL total, reasoning forecaster, fs2)
is not voided: it was not written from a fit (ruling 1 of the three
decisions). The **31 reasoning-forecaster rows** written in the same runs are
not voided either: their prompts were rebuilt and read one by one, and none
carried fit output (ruling 2). They stand in the record and on the page. They
exist only because fits 91-94 existed -- the catch-up that wrote them was the
one those fits set off -- and a reader of the NFL and NCAAF reasoning curves
should know that 31 of their rows came from that run.

**Found while building it, and fixed in the same commit** (each proved on the
unfixed code first):

- Every read of `recommendations` counted straight off the table -- seven
  statements in six functions, including the closing line and the kill
  criterion behind it. A recommendation made on a voided forecast was counted
  in the closing line at +6.0c on the unfixed code. Now one door,
  `recommend.not_withdrawn`, with a source scan and a recount as guards.
- `calibration.standing_row_clause` let a voided row that had SETTLED be
  graded, and let it displace an earlier forecast of the same question that
  still stands. The resolver never produces that case (a trigger refuses to
  settle a voided row); a hand-written void can, if its game finishes first.
- `at_the_line.standing_claim_clause` counted claims on voided forecasts:
  `resolve_claims` settles claims from the score, so the 58 claims on 29 of
  the 31 would have entered the at-the-line record the night their games
  finished.
- `prediction_voids` refused an edit and not a delete, while this file and
  the enforcement table both called it append-only.

### Readers that still rely on a void coming before the settle *(open, measured 2026-09-24)*

Four counts of settled forecasts outside the standing clause were given an
explicit void exclusion in this commit (the early-versus-final pairs, the
correction gate's settled count, the least-tested tier line, the login page's
record). What remains relies on the trigger that refuses to settle a voided
row: `resolve.summary`'s resolved count, and the History page's "correct" and
"wrong" filters, which would list a row voided after it settled (its chip
still reads WITHDRAWN). Harmless for every void the resolver writes, and for
the ruling's 31 if they are written before tonight's games settle
(401869941 at 23:30Z, Atlanta at Green Bay at 00:15Z on the 25th); the tool
names any that settled first. **What would settle it:** route every count of
settled forecasts through `calibration.standing_row_clause`, or an audit scan
that refuses `resolved_utc IS NOT NULL` over `predictions` without it, with a
planting.

### The rail drops a tap on a withdrawn forecast *(open, recorded 2026-09-24)*

The ruling keeps a tap on a voided forecast ("it is the operator's choice")
and takes it out of the model's curves, which `calibration.taken_comparison`
now does through the standing clause. But the running list beside the slate is
built from the slate's cards, and a voided forecast is not a card, so such a
tap is kept in `picks_taken` and not listed. `picks_taken` holds no single-pick
tap today (one package tap), so nothing is hidden now. **What would settle
it:** the rail lists a tap whose forecast was withdrawn, saying so.

## Operator ruling of 2026-09-24 — the gate reads the live record, never writes it

### REPAIRED: the gate opened the live record writable and ran the tree's schema on it *(ruled and repaired 2026-09-24)*

Step 2's foreign-key check opened the record with `db.open_db`, which runs
`db.init`, which runs the tree's own `schema.sql`. So a gate run from a
worktree put unmerged schema on the operator's record: on 24 September, the
trigger `recommendation_close_cites_its_own_priced_read`, by 05:53Z, 55
minutes before item 1 merged. Measured while repairing it, the same gate also
opened the record writable in fifteen other step-2 checks and one more inline
(`db.connect()`, never closed), and step 3 ATTACHed it writable on every run.
The read door itself was only `query_only`, which its holder can switch off
with one PRAGMA.

Now the whole run is verification to `db`, every read goes through a door that
opens the file `mode=ro`, the record checks and step 3 read one migrated
scratch copy, and the gate fails naming any schema object that changed on the
record while it ran. Three plantings, each escaped on the unfixed code. The
occasions and their evidence: `docs/closeouts/2026-09-24-unmerged-schema.md`.

### The scheduler still applies whatever schema the main checkout holds *(open, 2026-09-24)*

The first occasion's path is untouched by the repair above. `Gridiron-Live`
runs `db.init` from the main checkout's working tree every 90 seconds, so an
uncommitted `schema.sql` there reaches the record within 90 seconds, gate or
no gate. The only defence is the worktree rule. The gate now notices it only
if it happens during a gate, when the start-and-end schema comparison fails
by name. **What would settle it:** the scheduled tasks open the record
without running `init`, leaving migration to the release step, or `init`
refuses a `schema.sql` that differs from the one committed at `HEAD`.

### Rows the gate might write are prevented, not measured *(open, 2026-09-24)*

The gate does not compare rows, because the scheduler writes to the record
for the whole of every run. Instead nothing in the gate can hold a writable
handle through `db`. That covers `db.connect` and `copy_facts`. It does not
cover a raw `sqlite3.connect` in a gate step, and it does not cover a child
process started with `GRIDIRON_VERIFYING` removed, which is exactly what the
three plantings do against their stand-in. A row written either way would
not be seen. **What would settle it:** an audit scan that refuses
`sqlite3.connect(` outside `gridiron/db.py` and the plantings' stand-in, run
in the gate, with a planting. **The raw-connect half is closed 2026-09-25**
(schema ruling 6; "BUILT: one way into a database file", below). The child
started without `GRIDIRON_VERIFYING` is still open.

### A gate that is killed leaves a gigabyte in the temp directory *(open, 2026-09-24)*

The gate's copy of the record is about 1.02 GB, made in about 3 seconds. It
is deleted when the gate ends, even when a step fails, and the gate says so
if it cannot delete it. A gate that is killed never reaches that line, and
the voids gate of 24 September was stopped by hand. It stopped before step 2,
so it made no copy, but the next one to be stopped might have. The copy is
left under `gridiron-gate-*` in the temp directory. **What would settle it:**
the gate removes stale `gridiron-gate-*` folders when it starts.

## Operator ruling 2 of 2026-09-24 — the activation gate *(GRIDIRON_REPAIR, the queue's item 2)*

### BUILT: a fit is written inactive, and ties go to the incumbent *(ruled and built 2026-09-24)*

The root cause of fits 91-94 publishing was a rule nobody had written down:
the newest fit of a market's declared factor set WAS the model, so training
and publishing were one act. Now `load_fit` reads only the fit named by the
market's latest row in `fit_activations`; a `measured` activation needs its
holdout against the active fit and a bootstrap interval of the log-loss
difference wholly below zero; an `incumbent` activation is for fits fitted
before 2026-09-24T05:16:00Z only. Recorded in CLAUDE.md as THE ACTIVATION
GATE, with five plantings, each shown landing with its guard removed.

**On the live record, at the first open after release**, `db.init` writes 24
incumbent activations, one per market still asked, each naming the fit that
market was already reading. The four fs5 markets (NFL and NCAAF spread and
moneyline, fits 91-94, fitted after the birthday) get none and stay
unforecast; retired MLB home runs gets none. Simulated on a scratch copy the
same day: 24 written, 0 on a second run, 0 audit faults. The revert of the
four is the next commit.

### Two NBA markets forecast from fits trained through 2024 only *(open, measured 2026-09-24)*

Found by the bootstrap simulation, and it is the 91-94 failure, earlier and
unnoticed. NBA spread's in-use fit is **80** (fs4, `season:2024`, n=3,688)
and NBA total's is **79** (fs2, `season:2024`, n=3,611), both written at
23:52-23:54Z on 4 September by a walk-forward run on the live record. Under
the newest-fit rule they silently replaced fits 61 (n=4,914) and 70
(n=4,841), which had trained on every season. The bootstrap records 80 and 79
as the incumbents because they are what those markets were forecasting from;
changing that is a ruling, not a repair. **What would settle it:** the
operator rules; a revert to 61 and 70 is lawful as an `incumbent`
activation, since both predate the birthday. Written under "Questions for
the operator" in `docs/REPAIR_STATE.md`.

### Tools still train on the live record *(open, 2026-09-24)*

`tools/walkforward_distributional.py` trains on `db.connect()`, the record
itself, and its fits have the shape of 74-90 (`season:N week:None`, no note;
which tool wrote those was not established). A fit written that way can no
longer publish -- it is inactive -- but it is still a row in the operator's
record that no forecast used. **What would settle it:** the tool
trains on a scratch copy, as `tools/holdout.py` does.

### REPAIRED: the Factors page reads the newest fit, not the active one *(open 2026-09-24; repaired the same day with ruling 4)*

`calibration._fit_status` still picks the newest fit of a version to report
each factor's training rows, so the page can describe a fit no market is
forecasting from. **What would settle it:** it reads `activation.active_fit`.

**Repaired** with the weather ruling (below, "Operator ruling 4"): it reads
`activation.active_fit` for every asked market under `baseline.market_key`
-- which also mends the total, looked up as `prop:total` -- and reports one
entry per market, so a factor three markets share shows three counts.

## The fs5 revert, 2026-09-24 *(the three decisions; GRIDIRON_REPAIR, the queue's item 2)*

### BUILT: all four fs5 markets back on their incumbents, and the hold lifted *(ruled and built 2026-09-24)*

"Ties go to the incumbent ... all four fs5 markets revert, including NFL
moneyline." `tools/holdout.py`, run read-only on a scratch copy, reproduced
the 24 September measurement to the fifth place and wrote it to
`gridiron/model/fs5_revert_holdout.json`: fs5 minus incumbent log loss
+0.00543 [-0.00935, +0.02048] NFL spread (n 272), -0.00893 [-0.02553,
+0.00769] NFL moneyline (271), +0.00166 [-0.00411, +0.00837] NCAAF spread
(839), +0.00371 [-0.01428, +0.02154] NCAAF moneyline (888) -- four ties.
`db.init` writes one `incumbent` activation each (fits 88, 71, 44, 35),
before the birthday bootstrap, only where the record's fit of that id is
exactly the named one. The config declares the pre-fs5 sets again, and
`srs_diff` and `cfb_srs_diff` are reactivated by dated entry.

**What the investigation found first.** The feature vector is built from the
registry's active factors (`compute.feature_vector`), not from the fit, and
`Fit.log_odds` skips a name the row lacks. All four incumbents carry the
plain rating fs5 retired, so reverting without reactivating it would have
forecast every NFL and college game without its rating term and without a
word: measured on a scratch copy, 0.11 of probability on average on the NFL
spread and 0.21 on the moneyline. `baseline.assert_the_vector_carries_the_fit`
now refuses that by name.

**Simulated on a scratch copy of the record, the revert applied:** the
forecast pass wrote NFL spread 13, NFL moneyline 16, NCAAF spread 68 and
NCAAF moneyline 71 (the next college slate 1 and 1; the rest of the week's
days the remainder), every row reproduced by fit 88, 71, 44 or 35 to the
sixth place with the rating measured on every one; the page check passed;
the day strip carried no held line.

### Count-market prop rows carry the class's factor set, not their own *(open, measured 2026-09-24)*

Found by the page check on its first run. `predict.write_prediction` stamps
`config.factor_set_version(sport, q.market_type)`, and for a prop that is
`(sport, "prop")`, which has no entry, so fs2. `baseline.load_fit` reads
`config.factor_set_version(sport, "prop:<stat>")`, fs3-rate for the count
markets since 3 September. So NFL passing touchdowns and receptions and MLB
batter hits and pitcher strikeouts are computed by fs3-rate rate fits and
stamped fs2: on the live record's page that day, forecasts 1899, 2081, 2083,
2087, 2090, 2092 and 2093 (NFL) and 2224 (MLB) are stamped fs2 and are
reproduced exactly by fits 56, 57 and 66, which are fs3-rate. Every curve or
version table split on the label splits those markets on a wrong one, and
`load_fit`'s own note says a label that lies is what it exists to refuse.
The page check reads the rows' own numbers instead of the label, so it is
not fooled. **What would settle it:** the operator rules whether future rows
carry their market's own set (which splits those curves at a date) and how
the rows already written are described; LAW 3 forbids re-stamping them.

### A prediction stores no fit id *(open, 2026-09-24)*

"Its forecasts come from its active fit" is checked by recomputation:
`baseline.is_its_forecast` applies the fit to the row's stored factor values
and rung and compares the probability. That is exact but indirect. It also
leaves a trap for the first `measured` activation: a new fit of the SAME
factor set, activated mid-slate, leaves that slate's rows from the old fit
on the page -- which the gate check then names -- and `already_written`,
keyed on the factor set, stops the new fit answering those questions again.
**What would settle it:** a fit-id column on `predictions`, written with the
row, before the first measured activation.

### The decayed ratings stay active beside the plain ones *(open, 2026-09-24)*

`nfl_rating_decayed_diff` and `cfb_rating_decayed_diff` were not retired:
nothing breaks with them active today. They are computed on every NFL and
college spread and moneyline row, stored among its values, counted in its
factor total and handed to the reasoning pass, and they carry no
coefficient in fits 88, 71, 44 or 35, so no probability and no factor score
reads them. **What breaks next:** a retrain of these markets -- the weather
step's NFL spread retrain is queued next -- would fit both ratings into a fit
labelled fs3, a different set under the old name. **What would settle it:**
before that retrain, either retire them by dated entry or declare the set
the retrain is meant to be.

## Operator ruling 4 of 2026-09-24 — weather: an indoor game carries no value *(GRIDIRON_REPAIR, the overnight queue's item 3)*

### BUILT: an indoor game carries no weather value, and each fit's rows used are read from the market's active fit *(ruled and built 2026-09-24)*

**What was there.** `context._weather` returned wind 0.0 and rain 0.0 for a
roof listed `dome` or `closed`, and `wind`, `cold` and `precipitation` each
returned 0.0 whenever the game was indoors -- although precipitation's note
said "REPAIRED 2026-08-29 ... EXCLUDES": that repair excluded outdoor games
with no reading and left every dome filled. In the NFL spread's training set
(2016-2025, 2,632 rows): precipitation read 0 / filled 760 / absent 1,872;
wind and cold read 1,703 / filled 760 / absent 169. College football's wind
never gave an indoor venue a value (NCAAF total: read 1,557, absent 44); MLB,
NBA and UFC declare no weather factor.

**What changed.** An indoor game is recorded as indoors, with a note saying
why, and carries no weather reading; each weather factor carries no value
under a roof and the row lists it absent with its reason ("played indoors: no weather
reaches the game"). `weather.roof_state` is the one test of a roof, asked by
the forecast fetch and the context alike. A weather factor declares the
reading it is computed from (`Factor.weather`), and
`compute.assert_weather_was_read`, inside `feature_vector`, refuses by name
any weather value on a row that is indoors or whose weather was not read
(`WeatherNotRead`). `calibration._fit_status` reads each market's ACTIVE fit
under the market's own key (it read the newest fit of the default set, looked
a total up as `prop:total`, and kept one market's count for a factor three
markets share), and the Factors page prints each factor's training rows used
per market. A fit trained from now on stores `indoor_weather: absent`; a
count from a fit without it is printed with "indoor games among them".

**Ruling taken, by precedent (reversible in one line).** A roof the source
has not published is UNKNOWN, not open: nflverse publishes a retractable
roof only after the game, so 37 of the 2026 season's scheduled games carry
none -- every home game of the five retractable-roof clubs, two of them
abroad; none in the history -- and in 2016-2025 those roofs were published
closed for 354 of their 402 home games published open or closed. So an unknown roof carries no weather value and no forecast is fetched
for it -- the treatment college football already gives a venue whose indoor
flag is unknown. It moves nothing today (no NFL forecast is fetched at all,
below). Reversal: map None to 'outdoors' in `weather.roof_state`.

**THE MEASUREMENT (ruling 4: "Report each factor's coefficient before and
after on the holdout").** Every market whose active fit carries a weather
factor, from `fit_activations` and each fit's coefficient names: seven NFL
markets and the NCAAF total. Each refit on its active fit's own factor set
through 2024 and scored on 2025, on a scratch copy of the record made
through `db.read_the_live_record`, no network; baseline.train's l2 (2.0);
the fit's own form. "Before" is the released code (ed5c07e, `git archive`),
"after" is this commit. Paired bootstrap as `tools/holdout.py` (1,000 draws,
seed 20260923).

| market (active fit) | train rows | scored (2025) | log loss before / after | Brier before / after | after − before [95% CI] |
|---|---|---|---|---|---|
| NFL spread (88, fs3) | 2,360 | 272 | .683614 / .683614 | .245353 / .245353 | 0 [0, 0] |
| NFL total (90, fs2) | 2,222 | 256 | .682861 / .682861 | .244877 / .244877 | 0 [0, 0] |
| NFL passing yards (12, fs2) | 1,171 | 144 | .525885 / .525885 | .171890 / .171890 | 0 [0, 0] |
| NFL receiving yards (13, fs2) | 1,203 | 144 | .625087 / .625087 | .216911 / .216911 | 0 [0, 0] |
| NFL rushing yards (14, fs2) | 1,160 | 148 | .620817 / .620817 | .214478 / .214478 | 0 [0, 0] |
| NFL passing touchdowns (56, fs3-rate, Poisson) | 1,159 | 140 | .589143 / .589143 | .201675 / .201675 | 0 [0, 0] |
| NFL receptions (57, fs3-rate, negative binomial) | 1,202 | 141 | .625077 / .625077 | .214465 / .214465 | 0 [0, 0] |
| NCAAF total (36, fs2) | 720 | 881 | .579844 / .579844 | .197723 / .197723 | 0 [0, 0] |

| market | factor | coefficient before = after | training rows used before → after | 2025 rows with a value before → after |
|---|---|---|---|---|
| NFL spread | wind | +0.051409 | 2,195 → 1,527 | 268 → 176 |
| NFL spread | cold | −0.088087 | 2,195 → 1,527 | 268 → 176 |
| NFL spread | precipitation | not fitted: constant (668, all domes) → dropped (0) | 668 → 0 | 92 → 0 |
| NFL total | wind | −0.181788 | 2,078 → 1,454 | 252 → 165 |
| NFL total | cold | +0.131717 | 2,078 → 1,454 | 252 → 165 |
| NFL total | precipitation | constant → dropped | 624 → 0 | 87 → 0 |
| NFL passing yards | wind | −0.185990 | 1,094 → 737 | 141 → 100 |
| NFL passing yards | cold | +0.050948 | 1,094 → 737 | 141 → 100 |
| NFL passing yards | precipitation | constant → dropped | 357 → 0 | 41 → 0 |
| NFL receiving yards | wind | −0.089848 | 1,114 → 762 | 143 → 87 |
| NFL receiving yards | cold | +0.103381 | 1,114 → 762 | 143 → 87 |
| NFL receiving yards | precipitation | constant → dropped | 352 → 0 | 56 → 0 |
| NFL rushing yards | wind | +0.150449 | 1,083 → 741 | 147 → 100 |
| NFL rushing yards | cold | +0.041898 | 1,083 → 741 | 147 → 100 |
| NFL rushing yards | precipitation | constant → dropped | 342 → 0 | 47 → 0 |
| NFL passing touchdowns | wind | −0.074080 | 1,087 → 755 | 136 → 94 |
| NFL passing touchdowns | cold | +0.059642 | 1,087 → 755 | 136 → 94 |
| NFL passing touchdowns | precipitation | constant → dropped | 332 → 0 | 42 → 0 |
| NFL receptions | wind | +0.031288 | 1,116 → 768 | 141 → 81 |
| NFL receptions | cold | +0.011333 | 1,116 → 768 | 141 → 81 |
| NFL receptions | precipitation | constant → dropped | 348 → 0 | 60 → 0 |
| NCAAF total | wind at kickoff | −0.021882 | 700 → 700 | 857 → 857 |

**Nothing moved but the counts.** Every coefficient, every intercept, every
2025 probability, log loss and Brier is bit-for-bit the same before and
after (largest |Δ| 0.0, so every bootstrap interval is [0, 0]): a 0.0 adds
nothing to a logistic's or a rate model's gradient or Hessian, exactly as an
absent term does (`test_missingness.py` already pinned that for the logistic;
`test_weather_indoors.py` now pins it through the real training path). The
rows each fit counts as used fell by the domes, and precipitation, whose only
values were domes, goes from "never varied" to "never measured".

**This week's slates, active fits unchanged** (scratch copy, the same two
trees, network refused): every NFL and NCAAF question with a kickoff in the
seven days from 24 September, 295 of them, 18 indoor. Under the released code
those 18 carried 30 weather values; now none. Every probability from the
active fits is bit-for-bit the same (largest |Δp| 0).

**Not done, and why.** No fit was trained or activated on the live record.
An identical refit would tie its incumbent, and ties go to the incumbent, so
the active fits (88, 90, 12, 13, 14, 56, 57) stay, and their stored weather
counts include the domes -- the page says "indoor games among them" beside
each. Whether to do more is written under "Questions for the operator" in
`docs/REPAIR_STATE.md`. The reasoning pass does change for an indoor game:
its prompt no longer lists "the wind = 0 [source: indoors]" among measured
factors; the three are under NOT MEASURABLE and the caveats say the game is
played indoors.

### Weather forecasts are never fetched by the scheduled tasks *(open, measured 2026-09-24)*

`weather.fetch_week` is called only by the command-line `predict` and
`weather` commands; the scheduled `predict:nfl` and `final:nfl` tasks call
`run.run_slate` without it. `weather_forecasts` holds 9 rows, all fetched at
07:34:56Z on 29 August for 2026 week 1 (2 of them for games now listed with
a closed roof). **What it means today:** every outdoor NFL forward forecast
carries no wind, cold or rain value -- absent, with "no weather reading for
this game", never filled: on this week's slate 62 outdoor NFL questions
say so, and 11 at the retractable roofs say "the roof is not known to be
open". The active fits' wind and cold
coefficients therefore never act forward: an absent term contributes what the
reference level does (10 mph, 55F), so every NFL forecast sits at calm, mild
weather whatever the sky does, and the factor scorecard scores them on no
forward row after week 1 (whose seven outdoor forecasts were fetched by
hand). Precipitation has no coefficient in any active fit, and has never
had a reading in the history. College football is not affected: its wind is
read inline at forecast time (`weather.wind_at`). **What would settle it:**
the scheduled NFL passes fetch the week's forecasts before they predict
(outdoor games only, `weather.roof_state`), inside the forecast horizon.

### A college game at a neutral site reads the listed home side's weather *(open, 2026-09-24)*

`sports.cfb._weather` reads the listed home side's venue: its indoor flag and
its coordinates. The record keeps no per-game venue or neutral-site flag for
college games, so a bowl or a kickoff game in a dome is given the home
campus's wind -- an indoor game carrying a value, which the new guard cannot
see, because the context does not know the game is indoors -- and one
outdoors elsewhere is given the wrong city's. How many: not measurable from
the record. **What
would settle it:** the loader stores each event's venue (ESPN's event carries
it), and the context reads that venue's flag and coordinates.

### The card's weather line does not ask about the roof *(open, measured 2026-09-24)*

`views._weather` prints any stored forecast beside a game. Two of the nine
stored (2026_01_BUF_HOU, 2026_01_BAL_IND) are for games now listed with a
closed roof: their cards print a forecast no factor read. **What would settle
it:** the card asks `weather.roof_state` first, the same door.

## Schema rulings 3, 4, 5 and 6 of 2026-09-24 — built 2026-09-25 *(GRIDIRON_REPAIR, the overnight queue's item 5; rulings 1 and 2 are the diff check and the migration, built after these)*

### BUILT: schema.sql declares `market_lines_raw.spread_sign_source` *(ruling 3; built 2026-09-25)*

"A fresh database built at the released commit must match the live record
without relying on ensure code." Measured before building: of the 34 ADD
COLUMN declarations in the code, this was the only column `schema.sql` did
not declare. `lines.ensure_raw_columns` adds it, and only
`repair_run_line_signs` calls that, after an MLB line fetch -- so a fresh
`db.init` at the release lacked it, and `audit.check_run_line_signs` raised
"no such column: r.spread_sign_source" on a fresh build (it passes in the
gate only because the gate reads a copy of the live record).

Declared exactly as the step adds it -- `TEXT NOT NULL DEFAULT 'unverified'`,
no CHECK, as the last column, where the live record holds it. A CHECK would
have made a new behavioural difference and a ninth table to rebuild. The live
record's text differs only cosmetically (the column arrived by ALTER). The
ensure step stays, now a no-op on every database built from this file: it is
for a record built before 2026-09-02 that never met it, where `CREATE TABLE
IF NOT EXISTS` leaves the old table alone. `var/` holds three such files by
their dates -- `backtest.db`, `mlb-backtest.db` and `nba-backtest.db`, last
written 2026-08-29 (listed, not opened). The live record already has the
column. `test_schema.py::test_a_fresh_build_holds_every_column_an_ensure_step_adds`
failed on the unfixed tree ("a fresh build lacks
['market_lines_raw.spread_sign_source']") and passes on the fix, and its
companion holds the two declarations to the same `table_xinfo` row.

### DELETED BY HAND: market_snapshots ids 174-181 *(ruling 4; measured 2026-09-25; the table now refuses it)*

The ruling asked, for each of the 8 missing ids, whether it was a
rolled-back insert or a deletion. **All eight were deleted.** Evidence,
read from a scratch copy of the record taken through the read-only door:

- **The hole.** Ids 174, 175, 176, 177, 178, 179, 180, 181: one block.
  `sqlite_sequence` for the table is 2355, equal to its highest id, with
  2,347 rows, so exactly these 8 are missing (the same 8 as the 2026-09-24
  measurement: then 2,187 rows, highest 2195). No other AUTOINCREMENT table in
  the record has a hole.
- **The rows around it.** 152-173 are the opening rows for predictions
  191-212 (the MLB slate of task run 35, fetched 2026-08-31T18:00:47Z).
  182-185 are the near-start rows of task run 41 (fetched
  2026-09-01T00:07:56Z). Nothing above 181 carries an earlier stamp.
- **The task log.** Task run 40 (refresh, 22:33:39Z-22:33:46Z on 31 August,
  started by hand from the main checkout) reported "near_start taken 8, due
  8". Re-running its due query selects exactly predictions 192-199. Those 8
  rows were copies of the cached opening quote -- near equal to open to the
  last decimal -- not a second look at the market.
- **The deletion.** At 2026-09-01T00:08:32Z the development session ran, from
  the main checkout, through the ordinary writable `db.connect()`:
  `DELETE FROM market_snapshots WHERE kind='near_start' AND fetched_utc <
  '2026-09-01T00:00:00Z'`. It printed 8. Commit 2d0e98f says "The eight stale
  rows were DELETED", and docs/closeouts/2026-08-31-calibration.md says so too.
- **Per id**, by insertion order (the set of 8 predictions is certain; which
  id held which was not recorded before the delete): 174 prediction 192,
  175 193, 176 194, 177 195, 178 196, 179 197, 180 198, 181 199. Each:
  DELETION, not a rolled-back or aborted insert.
- **Why not a rolled-back insert.** Measured on SQLite 3.49.1 with the
  table's own triggers: an insert a BEFORE trigger aborts, a ROLLBACK, a
  savepoint rollback, a close without commit and a process killed
  mid-transaction all leave `sqlite_sequence` where it was. Only INSERT OR
  IGNORE / ON CONFLICT DO NOTHING (an id is used up), INSERT OR REPLACE (the
  old row is deleted), an explicit id or a DELETE leave a hole. The only
  writer in the code is a plain INSERT (`lines.py`). So in this table a hole
  is a deletion or an ignored insert, never "a normal AUTOINCREMENT gap".
- **A second ad hoc delete**, at 07:00:05Z the same day, aimed at 29 college
  predictions' opening rows before re-snapshotting them, matched none: ids
  186-347 are contiguous and the 13 new rows follow 347 directly.

**The code path, and the fix.** No code in the repository deletes from this
table, on master or here. The path was a writable handle and a statement typed
by hand, and nothing refused it: the table's only rules were the two LAW 1
insert triggers. The trigger `market_snapshots_no_delete` now refuses every
delete, whoever types it, and `plant.py::plant_a_deleted_snapshot` runs the
exact 00:08:32Z statement: on the unfixed schema it removed the row, and on
the fix it is refused ("GRIDIRON LAW 3: a market snapshot is never deleted").
It reaches the live record through the release's `CREATE TRIGGER IF NOT
EXISTS`. Ruling 6's raw-connect scan would not have caught this: the delete
went through `db.connect()`.

**The rows are not restored.** They were cache replays, not observations;
putting them back would write a look at the market that was never taken.

**Still open.** (1) No BEFORE UPDATE trigger: an opening row can be rewritten
in place, and that leaves no hole to find. Freezing it goes beyond ruling 4's
words, so it waits for the operator. (2) `INSERT OR REPLACE` walks past the new
trigger as it walks past every `no_delete` trigger (the entry of 2026-09-23
above); no code writes this table that way. **Fixed 2026-09-25 (5a', the
adversarial review of 3603300):** `market_snapshots_never_replaced` refuses
it; see "5a'" below. (3) For ruling 2's rebuild of this
table: recreate this trigger with the other two, and carry `sqlite_sequence`
explicitly -- a rebuild resets it to the highest id (measured). **Done
2026-09-25:** `gridiron.rebuild` recreates every index and trigger from the
released text and carries the sequence exactly; rehearsed, 2355 -> 2355
(schema rulings 1 and 2, below).

### BUILT: one way into a database file *(ruling 6; built 2026-09-25)*

`audit.check_no_raw_connect_to_the_live_record`, in gate step 2, refuses every
raw SQLite open outside `db.connect`, in the package, `tools/` (plantings
included), `tests/` and `desktop/`. A scan cannot know which file a call
opens, so refusing every raw open is the reading that covers "to the live
record path". Run on the unfixed tree it names fourteen raw opens: two that
could reach the record (`tools/restate_closes.py` and `tools/void_fs5.py`
opened whatever `--database` named, `mode=ro` but with no reason, no
`query_only` and nothing under verification to refuse it) and twelve on
scratch files (the gate's and the holdout's backup targets, four in the
plantings, two in `conftest.world_copy`, four in `test_the_gate.py`). All
fourteen now go through a door: `db.read_only(path, why)` (new; `read_the_live_record` is now
that door on the record), `db.back_up_the_live_record(target, why)` (new; the
gate's copy and the holdout's copy had each written it by hand, and it refuses
the record as its own target) or `db.connect` on a scratch path. The exemption
list is empty. This closes the raw-connect half of "Rows the gate might write
are prevented, not measured" above.

**Found proving it, and fixed (2026-09-25).** `from sqlite3 import *` (which
brings `connect` in under a bare name) and the driver underneath, `_sqlite3`,
each opened a database past the scan as built. Both are now refused at the
import; `test_one_way_in.py::test_a_star_import_and_the_driver_underneath_are_named`
was red on the build as handed over and is green on the fix, and the real tree
gains no fault.

**Not covered, and what would settle each:**
- A module named at run time: `importlib.import_module("sqlite3")` or
  `__import__("sqlite3")` and then `.connect`. A static scan cannot follow a
  computed name; the audit hook below would. **Narrowed 2026-09-25 (5a'):**
  a CONSTANT name through `importlib`, `__import__` or `sys.modules` is now
  refused, with six more shapes the review found; a name computed at run
  time is still out of reach (see "5a'" below).
- A connect written inside a string and run by a child
  (`plant_a_schema_change_during_the_gate` does it on purpose, against a
  stand-in). A `sys.addaudithook` in `db` on the `sqlite3.connect` event would
  see every spelling at run time, including this one, for any process that
  imports `gridiron`; measured 2026-09-25 that the event fires for every
  spelling and that raising from the hook stops the open before a file is
  made. Not built: the ruling asks for a scan.
- An ATTACH opens a file without calling connect. `tools/backtest.py` defaults
  `--source` to the live record and ATTACHes it from a scratch connection,
  writable, when run by hand; `refuse_the_live_record` stops it only under
  verification. Settle it by backing the record up through the backup door
  and attaching the copy.
- `db._is_the_live_record` applies the temp-directory rule before comparing
  with the record's path, so a TMP that contains the record (the user folder,
  say) would make the record scratch and switch every refusal off. Settle it
  by comparing with the record's path first.
- Hand-run tools that open the record writable through `db.connect()`
  (`fingerprint.py`, the `measure_*` tools, `walkforward_distributional.py`,
  `backfill_lines.py`). That is the path the 2026-09-01 snapshot delete took,
  and fits 79 and 80 were written the same way (question 2). Settle it by
  giving each tool that only reads `db.read_the_live_record`.

### BUILT: the auth backoff on a clock a test moves *(ruling 5, first sentence; built 2026-09-25)*

The cause, measured 2026-09-25, is not the "4-second penalty" the state file
recorded. After three failures the penalty is 2 s; the stamps are cut to whole
seconds and the wait is rounded down, so the restart test held only while the
third stamp's fraction of a second plus the real time of the restart (a new
client, a new connection, a full `db.init`) stayed under one second: 0 of 60
red idle, 3 of 3 red with a 1.1 s pause at the restart. Reproduced on the
unfixed tree: red with a 1.1 s and a 4.1 s pause. On the fix, with the same
pauses, green at 0, 1.1 and 4.1 s.

`auth._now()` reads `auth.clock`, which is the real clock in production and is
never reassigned there. `test_auth.py` installs a clock it moves by hand,
starting months in the past on a whole second, so a reading of the real clock
that leaked into the backoff would fail every run rather than now and then.
The backoff tests now assert the exact Retry-After and move the clock to lift
it; the handoff tests are on the same clock (their 60-second limit was real
time too); new tests cover the 30-minute window and the handoff's minute.
`audit.check_auth_reads_one_clock` refuses another reading of the clock in
`auth.py`; `plant_a_wall_clock_read_in_the_backoff` plants one.

**Found proving it, and fixed (2026-09-25).** The auth scan knew a clock by its
usual spellings only: `import time as t; t.monotonic()`, `from time import
perf_counter` and `from datetime import datetime as D; D.now()` each read the
machine's clock in `auth.py` and passed it, while the tests scan beside it
already resolved the first two (neither resolved the third). Both scans now
read a module's clock names from its own imports through one helper,
`audit._clock_names`. Tests: `test_the_clock.py::test_every_spelling_of_a_clock_reading_in_auth_is_named`
and `::test_an_aliased_datetime_in_a_test_is_still_the_real_clock`, both red
on the build as handed over and green on the fix; the real tree gains no
fault. Still not seen: a clock read through another function (`db.just_after`
reads `db.utcnow`), which would need a call graph; auth calls neither.

### HELD: the browser tier's fixed waits *(ruling 5, second sentence; operator question 5, asked 2026-09-25)*

`audit.check_no_test_waits_on_the_clock` refuses, in `tests/`, a sleep, a fixed
browser wait, a reading of the elapsed-time clocks, and a difference or
comparison reckoned from the real clock. It found 44 in the browser tier -- 43
`page.wait_for_timeout` in 9 files and one `time.sleep(1.2)` in a route
handler that makes a response late (`test_rapid.py`) -- plus the two server
start-up loops, which are exempt by date as real timeouts (a 20-second upper
limit, nothing asserted about how long start-up took). Whether the ruling
reaches the fixed waits is question 5 in docs/REPAIR_STATE.md, because it
needs either a reading of "depend on elapsed real time" or a rework of the
browser tier onto events the app does not yet signal. Until it is answered the
44 are held by function and count in `audit.ELAPSED_TIME_HELD`: none was
changed, a function may not gain one, and the register can only shrink.
Upper-limit timeouts (Playwright's `timeout=`, the plantings' 600 s subprocess
limit, a socket's 5 s) are not refused: they change a hang into a failure and
change no result below the limit.

**What the scan cannot see:** a test whose code under test reads the clock
while the test reads none -- which is exactly what the backoff test did. The
auth half is closed by the clock seam and its scan. The rest of the suite's
wall-clock dependence, listed 2026-09-25 so it can be checked: unit tests that
place a row at now plus or minus a gap the code compares with its own clock,
each with an hour or more of margin (`test_near_start_reads`, `test_scheduler`
311, `test_night_audit`, `test_at_the_line`, `test_kalshi`, `test_paper`,
`test_multisport`, `test_login_count`, `test_guards` 1032 and 1051,
`test_mlb_props` 372, and two plantings that place a row six hours and two
days back), and the fixtures that seat a season on today's date. None can change its result
inside a run; each could take a `now=` if the operator wants them clock-free.
The production caches keyed on `time.monotonic` (`scheduler.read_os`, 30 s;
`buildinfo.freshness`, 60 s) have no test that waits on them.

### The browser-test skip guard misses ten files *(open, found 2026-09-25 in passing)*

Only `tests/test_smoke.py` carries `pytest.mark.browser`, and the hook in
`tests/conftest.py` that turns a skip for an unallowed reason into a failure
looks only at browser-marked tests. So the ten other files that drive the
browser through the `page` fixture escape it (`test_cards`, `test_empty`,
`test_every_control`, `test_health_words`, `test_hidden`,
`test_login_redirect`, `test_motion`, `test_rapid`, `test_settled_line`,
`test_tabs`), and `test_cards.py` has eleven skips that depend on the slate
("no cards on this slate") that would read as green. `verify.py --quick`
("not browser and not slow") does not deselect them either. **What would
settle it:** the `page` fixture marks its test as browser, or the hook keys on
the fixture rather than the mark.

## Schema rulings 1 and 2 of 2026-09-24 — built 2026-09-25 *(GRIDIRON_REPAIR, the overnight queue's item 5, after rulings 3-6 above)*

### BUILT: the gate compares the schema with the release *(ruling 1; built 2026-09-25)*

"The diff check compares after normalising quoting, whitespace, comments and
column order, and fails on any difference in behaviour." `gridiron.schema_diff`
is the one door; `audit.check_the_schema_matches` holds a comparison to the
dated register; gate step 2 runs it twice.

- **The live record against the release.** The release is the branch master,
  read as git objects (`git archive master gridiron` into the temp directory),
  and a child runs that tree's own `db.open_db` on a new scratch file with a
  scratch home, so no settings file and no record is in its reach; it asserts
  the package it imported is the archive's. The live record is read through
  `db.read_the_live_record`. Measured on 2026-09-25 against master fddd61b:
  213 objects each side; 11 objects differ only in what the ruling
  normalises (at_the_line_claims, mlb_pitcher_starts, notifications,
  prediction_voids, recommendations, sessions, task_runs, teams, venue_quotes,
  and the two LAW 1 snapshot triggers); 9 differ in behaviour, all registered.
  The fresh build takes under a second.
- **The gate's migrated copy against this tree.** The copy of the record that
  step 2 already makes and migrates with this tree's `db.init`, against a
  database this tree built from nothing in the same kind of child. This is the
  pre-merge half the map proposed: every one of the eight arose from an ALTER
  without the CHECK, or an edit to a table the record already had, and the
  release comparison sees such a drift only after it has reached the record.
  Here it fails the gate that would release it. Measured: 214 objects each
  side (the tree adds `market_snapshots_no_delete`); 12 cosmetic
  (`market_lines_raw` joins them, ruling 3 now declaring its column); the 8.
- **The register, and why it has nine lines.** `audit.SCHEMA_DIFFERENCES_REGISTERED`
  holds each measured difference by object, property and side, with the
  commit its reference definition came from and what clears it. Eight are
  "cleared by the dated migration of ruling 2", in both comparisons. The ninth
  is the release comparison's `market_lines_raw.spread_sign_source`, which the
  record has and master's `schema.sql` does not: it is cleared by the release
  that carries ruling 3's declaration, and without it the gate would fail on
  the commit that fixes it. A difference not in the register fails by name
  ("NEW"); a registered one no longer found fails too ("CLEARED, STILL
  REGISTERED -- remove it"). **The lifecycle:** this commit's gate passes with
  9 and 8 outstanding; once merged, the ninth clears and the next gate says
  so; once the operator has run the migration, the eight clear; the commit
  after that empties the register, and from then on any difference fails.
- **Not covered.** Rows are not compared, only the schema (the tree
  comparison's copy carries rows, but only its schema is read). A difference
  inside a trigger body that normalises equal but behaves differently cannot
  exist (the token sequence is the body), but `<>` against `!=` or
  `DEFAULT (0)` against `DEFAULT 0` is reported although it behaves the same:
  the check fails safe. Planner statistics (`sqlite_stat*`) are left out by
  name; there are none today. **The map's static check (c)** -- every ADD
  COLUMN declaration in the code equal to `schema.sql`'s column -- was not
  built; the tree comparison catches the same drift at the gate, from the
  record's side.

### BUILT, NOT RUN ON THE LIVE RECORD: the dated migration *(ruling 2; built and rehearsed 2026-09-25)*

`tools/migrate_2026_09_25_behaviour.py`, through `gridiron.rebuild`, rebuilds
factors, factor_scores, model_fits, market_snapshots (its entry is
`market.lines.SNAPSHOT_REBUILD`, LAW 1), mlb_lineups, prediction_ranks,
ufc_events and nba_injuries to the released definitions, in one transaction,
with the rename-aside the ruling's "then swap" needs: the old table is renamed
aside with foreign keys off and `legacy_alter_table` on, the new one is created
under its own name from the released text -- so the record's stored text
becomes byte for byte the release's, quotes included -- and the old is dropped
after the copy is verified.

**The rehearsal** (2026-09-25T05:05:54Z-05:06:38Z, `--rehearse`, the live
record read through the read-only door, the copy in the session's scratch
directory): the verified backup took 39.7 s -- `integrity_check` ok, 59 tables
and 1,172,119 rows, every row count and column checksum equal on both sides at
the instant copied. Then, rows before -> after and the table checksum (a
digest of every column's SHA-256) before -> after:

| table | rows | table checksum | sequence |
|---|---|---|---|
| factors | 105 -> 105 | 52aa956d629885fa -> 52aa956d629885fa | none -> none |
| factor_scores | 0 -> 0 | 413f59a448bc39f6 -> 413f59a448bc39f6 | none -> none |
| model_fits | 94 -> 94 | 217c810c4324add6 -> 217c810c4324add6 | 94 -> 94 |
| market_snapshots | 2,347 -> 2,347 | eb2127c49ac10bcf -> eb2127c49ac10bcf | 2355 -> 2355 |
| mlb_lineups | 130,392 -> 130,392 | c82c392d619c8729 -> c82c392d619c8729 | none -> none |
| prediction_ranks | 4,981 -> 4,981 | 33ca7b1ca3d27184 -> 33ca7b1ca3d27184 | 4981 -> 4981 |
| ufc_events | 269 -> 269 | f4a62721d07b8128 -> f4a62721d07b8128 | none -> none |
| nba_injuries | 70 -> 70 | f4cbaf910af6d1af -> f4cbaf910af6d1af | none -> none |

Every column's own checksum is equal too (the report prints each). The write
lock was held **3.18 s** (mlb_lineups 1.92 s of it), against the scheduler's
30 s busy timeout; `foreign_key_check` returned 0 rows before and after.
Afterwards, on the rehearsed copy: against a fresh build of this tree, **0
differences in behaviour with an empty register** (10 cosmetic; the two LAW 1
snapshot triggers are now byte for byte the release's); this tree's `db.init`
changed nothing; `widen_sport_checks` returned []; a snapshot of an unknown
kind, a snapshot delete, a factor or fit of an unknown sport, a rank off the
shortlist domain, a lineup from an unknown source, a card of an unknown tier,
an injury with no name, a factor delete and a rank update were each refused
by name; `ufc_bouts` still names `ufc_events`. The copy also gained
`market_snapshots_no_delete`, which the live record gets from the release
before the migration runs. Reports: the session scratchpad's
`schema5a/i2_rehearsal.txt`, `.json` and `i2_after_rehearsal.txt`.

**For the operator, after the release that carries it** (from the main
checkout; not run by `db.init`, the gate or this session):

1. At a quiet hour -- 10:15Z measured quietest (Resolve at 09:20, Capture at
   11:15, no game on); never at :05 or :35, never during a gate, never within
   half an hour of a logon; the machine must be on.
2. `python tools/migrate_2026_09_25_behaviour.py --database var/gridiron.db --rehearse`
   -- a fresh verified copy, migrated; read its report.
3. `python tools/migrate_2026_09_25_behaviour.py --database var/gridiron.db --live --backup var/gridiron.before-ruling-2.<date>.db`
   -- the verified backup (about 40 s, about 1 GB, never over an existing
   file), then the one transaction. A failed backup migrates nothing; a table
   that fails verification rolls everything back and names it.
4. The next commit empties `audit.SCHEMA_DIFFERENCES_REGISTERED`; its gate
   fails until it does ("CLEARED, STILL REGISTERED").

**DONE 2026-09-26 (after 5a' released as f4c4db2).** Run by the session, from
the worktree at master's commit (the tool checked its definitions equal to
master before the backup), with no pass running and nothing due until
Predict-MLB at 05:00Z:
- step 2 at 02:11:20Z: a fresh verified copy, 8 tables committed, no column
  checksum differing, sequences carried, lock 3.31 s;
- step 3 at 02:12:17Z: `--live --backup var/gridiron.db.pre-behaviour-migration-2026-09-26.bak`
  -- the backup verified (60 tables, 1,191,063 rows, every count, column
  checksum and schema object equal), then the transaction took the lock at
  02:12:57Z and COMMITTED all eight, every column's exact checksum equal
  before and after, sequences 94, 2558 and 5116 carried, foreign_key_check 0
  rows, lock held 3.52 s;
- step 4: 5b empties the register (the eight kept as history in
  `audit.SCHEMA_DIFFERENCES_CLEARED_2026_09_26`).
The report is in the session scratchpad, `migration_live/`.

It is idempotent: a table already at its definition is skipped, and a record
already migrated is not even copied. The plan is asked read-only first.

### The second rehearsal, and three defects it fixed *(2026-09-25, 05:42Z-06:09Z)*

A separate rehearsal of the tool, never `--live`: a verified copy of the
record through the read-only door's backup, the tool's `--rehearse` on that
copy, then everything checked from outside the tool. It ran three times,
because each fix was followed by a rerun from a fresh copy. The last run
(copy at 06:04:24Z, 1,172,242 rows, 59 tables) found this:

- **Before**: against a fresh `db.init` of master fddd61b, 9 differences in
  behaviour: the 8, plus `market_lines_raw.spread_sign_source` (ruling 3's
  ensure-only column, which this tree declares). There are 11 cosmetic
  objects, and a crude second reading that does not use `schema_diff` agrees
  on each of them.
- **The rehearsal**: every table's rows and all 81 column checksums were
  equal before and after, with the sequences at 94 -> 94, 2355 -> 2355 and
  4981 -> 4981. `foreign_key_check` returned 0 rows, and the write lock was
  held **2.69 s**.
- **Checked outside the tool**: all 59 tables' checksums, every
  `sqlite_sequence` (name, seq) pair, and the 189 objects that are not the
  eight's are byte for byte as before. The eight were also joined on rowid
  and compared value by value (`IS NOT` and `typeof`). The one difference is
  in `sqlite_sequence`'s own rowids: the three rebuilt tables' rows were
  written again, and no code reads them.
- **After**: 0 differences from this tree, even with an empty register.
  Against master, 2 differences remain, and neither is one of the 8:
  `market_snapshots_no_delete` (ruling 4) and `spread_sign_source`. Both clear
  when this tree is released. `integrity_check` was ok and
  `foreign_key_check` returned 0 rows. This tree's `db.open_db` changed
  nothing. Every new CHECK, both LAW 1 insert triggers, `ranks_no_update`,
  `ranks_no_delete`, `factors_no_delete` and the new snapshot delete trigger
  each refused, and the `ufc_bouts` foreign key still refuses deleting a card.
- **Second run**: every table was skipped. The file's SHA-256 and mtime were
  unchanged, and `rebuild_tables` called directly began no transaction.
- **Forced failure** (on a new copy, through the planting's `_copy_rows`
  hook): one TEXT value was altered in the last table (after seven swaps), and
  one REAL was moved by 1e-12 in `market_snapshots`. Each rolled back. The
  schema, the sequences and every table's checksums were identical, and
  nothing was left aside. The unpatched control run on the same copy then
  committed.

Fixed in `tools/migrate_2026_09_25_behaviour.py` and `gridiron/rebuild.py`,
each with a test that failed on the unfixed code:

1. `--report` was ignored on the nothing-to-do exit and on both
   unverified-copy exits, so a run asked for its record left none. It is now
   written on every exit that reaches a verdict
   (`test_a_report_asked_for_is_written_when_there_is_nothing_to_do`,
   `::..._when_the_copy_does_not_verify`).
2. A refusal whose rollback was NOT proved used to print "ROLLED BACK.
   NOTHING WAS SWAPPED: ROLLED BACK, AND THE SCHEMA IS NOT WHAT IT WAS". That
   happens when another connection changes the schema between the plan and
   the lock. Now "nothing was swapped" is printed only when the library
   attaches its report, which it does exactly when it re-read the schema and
   found it unchanged. Otherwise the line reads "NOT COMMITTED: ..."
   (`test_a_rollback_that_is_not_proven_is_never_called_nothing_swapped`).
3. A table that failed part way printed "sequence 2355 -> None" for a
   sequence it never measured, and the rollback had kept it.
   `TableReport.finished` now marks a table whose rebuild ran to its end, and
   an unfinished one prints "not reached"
   (`test_a_sequence_the_failure_never_reached_is_not_reported_as_lost`).

The column order changes on five tables. Checked the same day, every
`SELECT *` reader of the eight reads by name, and none inserts without a
column list. The report is in the session scratchpad at
`schema5a/REHEARSAL.md`.

### OPEN: `widen_sport_checks` renames with foreign keys on *(found by the ruling-2 map, 2026-09-25)*

Today it skips factors, factor_scores and model_fits because their stored
text lacks "sport IN" (their column came by ALTER). After ruling 2's rebuild
they carry the five-sport CHECK, so declaring a sixth sport rebuilds them on
sight -- through a rename to `<table>_narrow` with `legacy_alter_table` on but
foreign keys ON (set by `db.connect`), which measured 2026-09-25 repoints
children (factor_scores.factor, fit_activations.fit_id and incumbent_fit_id)
at the renamed-aside table that is then dropped. That path also copies with
INSERT OR IGNORE, checks only that no row was lost, and does not carry the
sequence. `games` is exposed the same way today. **What would settle it:**
route `widen_sport_checks` (and the two hand-written widenings) through
`gridiron.rebuild`. **Fixed 2026-09-25 (5a') for `widen_sport_checks`**; the
two hand-written widenings (`notifications`, `task_runs`) are unchanged --
each turns foreign keys off inside its own script and no table references
either. See "5a'" below.

### Found in passing *(2026-09-25)*

- `db.back_up` (the backup door, which `back_up_the_live_record` now calls)
  refuses a target that resolves to the record by comparing paths directly,
  before the temp-directory rule `_is_the_live_record` applies; the wider flaw
  recorded above under ruling 6 -- a TMP that contains the record switches
  every other refusal off -- is still open.
- The rehearsal's 1 GB copy (`schema5a/i2_rehearsal.db` in the session
  scratchpad) is scratch and may be deleted.
- *Fixed 2026-09-25, found proving the plantings.* With the rebuild's checks
  switched off in a copy, `plant_a_rebuild_that_alters_a_row` still said NOT
  CAUGHT, rightly, but reported its second case as "factors: COMMITTED a
  corrupted copy": the first case had committed every table, so the second
  rebuilt nothing. It now reports what each run did ("tested nothing -- an
  earlier case had committed"). The verdict's condition is unchanged.

## 5a': the adversarial review of 3603300 -- fixed 2026-09-25 *(GRIDIRON_REPAIR, after item 4, before the live migration)*

The review (meant for the cloud, run on this machine; reproduction scripts
`e1_dqs.py` .. `e8_widen_after.py` in the 25 September session's scratchpad)
found eight defects in the migration tool, the diff and the scans. Each is
fixed with a test or a planting that fails on the code the review read (a
`git archive` of a1df279, the new tests or plantings laid over it) and passes
on the fix, and each reproduction was run again on the fix. None of them was
ever run on the live record; the live record was read only through the
read-only door, for its schema text.

### FIXED: `--report` wrote over whatever it named *(finding 1)*

`Path.write_text`, never checked: `--live --backup X --report X` turned the
verified backup into JSON, `--report <record>` overwrote the record, and a
rehearsal with nothing to do overwrote it too, exit 0 (all three reproduced on
a1df279). Now, before anything is done, the report must be a new file in an
existing folder and must not be the database, the record (every place it is
reached from), the backup, the scratch copy, or a `-wal`, `-shm` or
`-journal` beside any of them, compared by the folder's identity and the
name; and it is created exclusively (`open(..., "x")`), so a file that
appears during the run is left alone and the run says "REPORT NOT WRITTEN".
`test_rebuild.py::test_a_report_is_never_written_over_the_record_the_backup_or_a_database`,
`::test_a_report_that_appears_during_the_run_is_not_written_over`.

### FIXED: the record was known by the running checkout's settings *(finding 2)*

The `--live` refusal compared the path with the RUNNING checkout's
`config.DB_PATH`, resolved: from a worktree, through a hard link, or with
GRIDIRON_DB, GRIDIRON_HOME or GRIDIRON_STATE set, the record was "not it", and
without `--live` it was migrated in place with no backup. The identity rule
`tools/reconstruct_prompts.py` used is now the one door,
`db.is_the_live_record_file` (the configured record, the default one, this
checkout's `var` and the main worktree's `var`, from `git worktree list`, each
by `os.path.samefile`), and both tools ask it. Proved on a scratch git
repository standing in for the install (a main checkout whose master is the
fixed tree, a worktree of it, a stand-in record): from the worktree, through a
hard link, with GRIDIRON_DB or GRIDIRON_STATE elsewhere, each refused, the
record unchanged; the same run on a1df279 migrated the record in place from
the worktree and then wrote the report over it.
`test_rebuild.py::test_the_record_is_known_by_its_identity_whatever_runs_the_tool`.

### FIXED: `--live` wrote whatever `schema.sql` the checkout held *(finding 3)*

With `--live` the tool now reads `gridiron/schema.sql` and
`gridiron/market/lines.py` from the branch master (`git show`) and refuses,
by name and before the backup, unless the definitions it would write (each
table's CREATE, every index and trigger, the automatic indexes), the map's
snapshot entry (`lines.SNAPSHOT_REBUILD`) and the running tree's `schema.sql`
itself equal master's, line endings apart. The consequence the operator will
see: `--live` runs only from a checkout whose two files are master's -- the
main checkout after the merge. A worktree, or local edits, are refused.
`test_rebuild.py::test_live_refuses_definitions_that_are_not_the_release`
(a table's CHECK, a trigger, the file outside the eight, the snapshot entry),
`::test_the_release_is_read_from_the_branch_master_through_git`.

### FIXED: the diff read quoted text as a name everywhere *(finding 4)*

Double-quoted, bracketed and backquoted text was unquoted and lower-cased, so
`DEFAULT CURRENT_TIMESTAMP` equalled `DEFAULT "CURRENT_TIMESTAMP"` (a clock
against a string), `CHECK (sport IN ("nfl"))` equalled `("NFL")`,
`CHECK (s != NULL)` equalled `(s != "NULL")`, `DEFAULT live` equalled
`DEFAULT LIVE`, a trigger's `WHEN OLD.kind = "near_start"` and an index's
WHERE equalled their upper-case twins, and two COLLATE clauses swapped
compared equal though the last one wins. Now a quoted word is a name only
where only a name can stand (the list is in `schema_diff`'s docstring) or
where, inside a table's or an index's expression, it names one of that
table's columns -- which is what SQLite resolves it to; anywhere else it keeps
its quotes and its case. A bare word after DEFAULT keeps its case (SQLite
stores it as a string) unless it is NULL, TRUE, FALSE or a CURRENT_ keyword.
Of a COLLATE, DEFAULT or NOT NULL written twice only the last is compared.
The PRAGMA check reads the default as a default. **Measured the same day** on
the live record's own schema text (read through the read-only door) against
fresh builds of master f6e57f3 and of this tree: the same eight differences
with the same register keys, and the same twelve cosmetic objects as before
(the eleven of 24 September, market_snapshots now behavioural, plus
`market_lines_raw`). A false alarm stays possible where SQLite would agree
(a quoted literal and a single-quoted one in a DEFAULT, say); the check fails
safe. `test_schema_diff.py` (every example above, each first shown to behave
differently in SQLite), `test_the_schema_matches.py`.

### FIXED: `INSERT OR REPLACE` got round the snapshot delete rule *(finding 5)*

A replacing insert on (prediction_id, kind), or on a stored id, deleted the
stored row without firing `market_snapshots_no_delete` (SQLite runs no delete
trigger for a replacement unless recursive_triggers is on) and gave the new
row a new id -- a hole like 174-181. `market_snapshots_never_replaced`, a
BEFORE INSERT trigger in the form the prompt record's table already carries,
refuses an insert whose id or whose (prediction_id, kind) is already stored.
**Every writer read first:** the package's only writer is
`lines.snapshot_prediction` (a lookup, then a plain INSERT); `tasks.py` calls it
for the near-start look inside a try that counts a failure; the plantings
(`plant.py` 207, 224, the deleted-snapshot planting) and the tests
(`test_drift`, `test_guards`, `test_near_start_reads`, `test_priced`,
`test_rebuild`, `test_recommend`, `test_schema`, `test_shortlist`) insert
plainly; the rebuild copies into the new table before its triggers exist;
`dbcopy.FACT_TABLES` does not copy the table. None uses OR REPLACE, OR IGNORE
or ON CONFLICT on it, so no lawful behaviour changes: a plain duplicate was
already an IntegrityError from the unique index and is now the same error,
named (`test_drift.py::test_only_one_snapshot_of_each_kind_per_prediction`
still holds). The migration's definition of the table carries the trigger, and
the live-shapes fixture has it, as the release will create it on the record
before the migration runs. `plant.py::plant_a_replaced_snapshot` (ESCAPED on
a1df279: rows 1 and 2 became 1 and 3; CAUGHT on the fix),
`test_rebuild.py::test_the_migrated_snapshot_table_refuses_a_replacing_insert`.
An UPDATE is still not refused: question 6.

### FIXED: the raw-connect scan missed aliasing *(finding 6)*

Seven opens went past it (`s = sqlite3; s.connect`, a subclass of
`sqlite3.Connection` called, `importlib.import_module("sqlite3")`,
`__import__("sqlite3")`, `vars(sqlite3)["connect"]`, `getattr` by a computed
name) and an eighth through a helper named `connect` nested in `db.py`, which
the exemption, keyed on the bare function name, let through. The scan now
refuses the module bound to another name or used as a value at all (the name
is then read as the module too), a dunder read off it, `sqlite3.Connection`
anywhere but an annotation or an isinstance/issubclass (so a subclass, and
its call, are named), and a constant driver name through `importlib`,
`__import__` or `sys.modules`; the exemption is keyed on the qualified name,
so only the module-level `db.connect` is exempt. The real tree gains no
fault. `plant.py::plant_a_raw_connect_past_the_door` now plants every shape
(ESCAPED on a1df279, CAUGHT on the fix);
`test_one_way_in.py::test_every_way_round_the_first_scan_is_named`.
**Still not seen by a static scan:** a module name computed at run time, the
class of a live connection (`type(conn)(path)`, `conn.__class__`), a connect
inside a string a child runs, an ATTACH. The audit hook described under
ruling 6 above would see all of them.

### FIXED: the checksum missed -0.0 and text after a NUL; the backup compared tables only *(finding 7)*

The per-column checksum hashed `quote()`, under which -0.0 and 0.0 are both
`0.0` and a text ends at its first NUL (`'a'||char(0)||'b'` quoted as `'a'`).
Each value is now hashed exactly: its storage class, then an integer's
digits, a real's eight IEEE-754 bytes, a text's or a blob's bytes as SQLite's
`hex()` gives them. `verified_backup` also compares every sqlite_master row
byte for byte (type, name, table, root page, text), naming each object that
differs. Measured on the way: -0.0 survives only in a column with no REAL,
INTEGER or NUMERIC affinity -- a REAL column stores it as the integer 0 --
and none of the eight tables has such a column, so this closes a gap in the
proof rather than a loss that happened. The rehearsal digests in the table
above were taken with the old checksum and are not comparable with the next
rehearsal's. `plant.py::plant_a_rebuild_that_alters_a_row` gains a third
corruption, a text changed only after its NUL (ESCAPED on a1df279: "COMMITTED
a corrupted copy"; CAUGHT on the fix);
`test_rebuild.py::test_the_checksum_tells_every_stored_value_apart`
(16 values, every pair apart; on a1df279 four pairs clash),
`::test_a_copy_that_changes_a_text_after_its_nul_fails_verification`,
`::test_a_backup_whose_schema_differs_from_its_source_is_refused`.

### FIXED: a sixth sport after the migration *(finding 8)*

`db.widen_sport_checks` now rebuilds every table it must widen through
`gridiron.rebuild` in one transaction -- foreign keys off, `legacy_alter_table`
on, rows and column checksums verified, indexes, triggers and sequence
carried -- instead of renaming aside with foreign keys on. The review's e8,
run on the fix: on the migrated copy all five tables widen, `fit_activations`
names `model_fits`, 0 `foreign_key_check` rows, no sequence moved. It also
settles `games`: on the unmigrated copy a1df279 left five
`foreign_key_check` rows, children repointed at the dropped `games_narrow`;
the fix leaves none.
`test_rebuild.py::test_a_sixth_sport_after_the_migration_repoints_nothing_and_changes_no_row`
(every foreign key of every table resolves, `fit_activations` takes a new row
against `model_fits` with foreign keys on, every table's checksums and every
sequence as before).

### NOTE 9: the backup is one instant *(reported, not changed)*

The verified backup holds the record as it was at the instant it was copied.
The migration's write lock (`BEGIN IMMEDIATE`) comes after the backup has been
verified -- about 40 s on the live record. Any row a scheduled task writes in
between is in the migrated record and NOT in the backup, so a restore from the
backup would lose it silently. The tool now prints both instants ("THE BACKUP
IS ONE INSTANT", and after COMMIT "THE BACKUP IS NOT THE RECORD AS
MIGRATED", with the time of each) (`test_rebuild.py::test_the_live_run_says_what_the_backup_does_not_hold`).
What it means for the operator: run it at a quiet hour -- 10:15Z measured
quietest, never at :05 or :35, never during a gate or within half an hour of a
logon -- and if a restore is ever needed, compare the task log between the two
printed instants first.

### Found in passing *(2026-09-25, 5a')*

- `db.widen_taken_for_packages` renames `picks_taken` aside with
  `legacy_alter_table` on and foreign keys ON, and `picks_retracted`
  references it: the same repointing as finding 8, but it runs only on a
  database made before 2026-09-08 (no `package_id`), which the live record is
  not. Open; settle it through `gridiron.rebuild` like the sport widening.
- `db._is_the_live_record` (the verification guard) and
  `db.is_the_live_record_file` (a tool's `--live`) are two questions on
  purpose: the guard exempts the temp directory and is keyed on the path the
  deployment was configured with at import. The temp-directory flaw recorded
  under ruling 6 is still open.

### The rehearsal of the 5a' fixes *(2026-09-25T23:47Z to 2026-09-26T01:00Z)*

A separate rehearsal of the fixes above, never `--live` on the record: the
review's eight reproductions run again, the fixed tool rehearsed on verified
copies of the record, the `--live` refusals shown on a scratch stand-in
install in the real topology (a git main checkout whose master is this
tree, a worktree of it whose `var` is a junction to main's), and every
defect it found fixed with a test or planting that fails on the unfixed code
(a1df279) and on the fix as the builder left it. The report is in the 25
September session's scratchpad at `fix5a/REHEARSAL.md`.

**The copies.** Each through `db.back_up_the_live_record`, proved against
a snapshot of the record held through `db.read_the_live_record` (integrity
ok, all 225 schema rows byte for byte, all 60 tables' exact column
checksums): 00:12:05Z (1,190,414 rows) and 00:35:36Z (1,190,591), each
with a second copy for the forced failure.

**The rehearsal** (`--rehearse` on a copy; the tool copied it again,
verified, and migrated that): all 8 tables rebuilt in one transaction, all
81 column checksums equal before and after, sequences 94 -> 94, 2546 ->
2546 (2558 -> 2558 in the second run) and 5116 -> 5116, `foreign_key_check`
0 rows, **the write lock held 3.28 s** (3.96 s in the second run, with the
full test suite running beside it). Outside the tool: every table's rows and
exact checksums equal (only `sqlite_sequence`'s own rowids moved, as
before), the 200 objects not the eight's byte for byte, the eight joined on
rowid with no value, type or rowid differing, the snapshot table carrying
all five of its triggers, `fit_activations` still naming `model_fits`.
Against a fresh build of this tree: **0 differences in behaviour** with an
empty register (10 cosmetic). Against master: only the two new snapshot
triggers. A second run skipped all 8 and left the file's bytes as they
were; this tree's `db.open_db` changed nothing. Forced failures on a fresh
copy (the planting's hook) in nba_injuries after seven swaps, in
market_snapshots by 1e-12, and in mlb_lineups by a character after a NUL
each rolled back with the schema, sequences and every checksum as they
were; the unfixed tool, given the NUL case on a copy of the same rows,
COMMITTED the corrupted name. A sixth sport on copies of the real record,
migrated and not: every foreign key resolves, no row changes; the unfixed
tree, on the migrated copy, left 18 tables pointing at dropped tables (17
at `games_narrow`, `fit_activations` at `model_fits_narrow`), 357,247
`foreign_key_check` rows, `games` itself changed and a sequence moved --
and on the unmigrated copy, as the record stands today, 17 tables and
357,219 rows: `games` was exposed all along.

### FIXED BY THE REHEARSAL: a file the tool creates could be a stream inside the record *(2026-09-25)*

On Windows a colon names an NTFS alternate data stream inside the file
before it. On the builder's fix, each exit 0: `--rehearse --report
<record>:report` wrote the report into the record's own file;
`--live --backup <record>:backup` put the verified backup (and its -wal and
-shm) inside the record it was meant to protect; `--rehearse --scratch
<record>:scratch` wrote the whole rehearsal copy into it; and
`--report <backup>.` (Windows strips a trailing dot) passed every check and
met the backup only after the migration had committed. An ISO time in a
backup's name (`...2026-09-26T10:15.db`) makes such a stream by accident,
inside a new empty file most copies drop it from. One door now,
`db.not_a_file_of_its_own`, asked by the tool for `--report`, `--backup`
and `--scratch` before anything is done and by `db.back_up` for every
caller. `test_rebuild.py::test_a_file_the_run_creates_is_never_a_stream_or_another_name`.

### FIXED BY THE REHEARSAL: a backup named as the record's -journal was deleted by SQLite *(2026-09-26)*

Measured: SQLite deletes a file at a database's -wal, -shm or -journal the
next time it opens and closes the database, and takes a -journal for a hot
journal at once. On the builder's fix `--live --backup <record>-journal`
wrote and verified the backup, then the migration's own open of the record
deleted it: exit 0, COMMITTED, no backup anywhere (the record itself
intact). `-wal` and `-shm` mangled the backup ("did not verify") and it was
gone after the next open; `--rehearse --scratch <record>-journal` lost its
copy the same way. Only `--report` had been held to the sidecar rule. The
same door refuses any new file that is the database, the record or a
sidecar of either. `test_rebuild.py::test_a_backup_or_a_copy_is_never_a_file_sqlite_keeps_beside_a_database`.

### FIXED BY THE REHEARSAL: `UPDATE OR REPLACE` still removed a snapshot round the delete rule *(2026-09-25)*

The fix for finding 5 refused a replacing INSERT. An `UPDATE OR REPLACE`
moving one snapshot onto another's forecast and look, or onto another's
id, removed that other row exactly the same way (measured on the fixed
definitions: ids 2 and 1 went). `market_snapshots_never_replaced_by_update`
(BEFORE UPDATE OF id, prediction_id, kind) refuses an update that would take
another stored row's place, and nothing else: no writer updates those
columns (read: `lines.py` inserts only; the only UPDATE of the table in
the tree is a test's corruption of `implied_prob`), a plain colliding
update was already refused by the unique key, and an update that takes no
other row's place still lands. **It is not question 6's no-update trigger**
and freezes nothing; it refuses a deletion, which is ruling 4's own words.
The migration's definition of the table carries it (five triggers), and the
live-shapes fixture has it, as the release's `db.init` creates it on the
record before the migration runs. `plant.py::plant_a_snapshot_replaced_by_an_update`
(ESCAPED on a1df279 and on the builder's fix: rows 1 and 2 became 1;
CAUGHT on this), `test_rebuild.py::test_the_migrated_snapshot_table_refuses_an_update_that_replaces`.

### FIXED BY THE REHEARSAL: the driver read off another module went past the scan *(2026-09-25)*

Every module that imports sqlite3 holds it as an attribute. Seven shapes
opened a database past the builder's scan, each measured on a scratch
file: `db.sqlite3.connect`, `from gridiron.db import sqlite3`,
`gridiron.db.sqlite3.connect`, `vars(db)["sqlite3"]`,
`getattr(db, "sqlite3")`, `db.__dict__["sqlite3"]` and
`sys.modules["gridiron.db"].sqlite3`; an eighth, `getattr(sqlite3,
"dbapi2")`, was found writing the planting. An attribute named `sqlite3`
is now the module on any base, a `from ... import sqlite3` from any module
binds it, and a namespace looked up by a driver's constant name (subscript,
`.get`, `getattr`) is refused. The real tree still has 0 faults.
`plant.py::plant_a_raw_connect_through_another_module` (ESCAPED on a1df279
and on the builder's fix, 8 of 8 unnamed; CAUGHT on this),
`test_one_way_in.py::test_the_driver_read_off_another_module_is_named`.

### FIXED BY THE REHEARSAL: a rehearsal said its own copy had lost rows *(2026-09-25)*

The note-9 line, THE BACKUP IS NOT THE RECORD AS MIGRATED ("rows ... in the
migrated record and not in the backup"), printed on a `--rehearse`, of a
scratch copy nothing writes. It is said on the live run only.
`test_rebuild.py::test_a_rehearsal_does_not_say_its_copy_lost_rows`.

### OPEN, found by the rehearsal *(2026-09-26)*

- **The record can go unrecognised where git cannot answer.** The candidates
  are the configured record, the default one, this checkout's `var` and the
  main worktree's `var` from `git worktree list`. Run from a worktree with
  no `var` junction, with GRIDIRON_DB/HOME/STATE elsewhere, and with git
  unavailable, the record is "not the record" and would be migrated in
  place. `--live` needs git anyway (the release check). Not changed: failing
  closed would refuse every scratch run outside a repository.
- **The review's e5 case 3 still "migrates"** under its own model, where the
  "main checkout" is only a GRIDIRON_HOME folder that no git lists: nothing
  a process can read identifies it. In the real topology (a git main
  worktree, the worktree's `var` junction) the same run is refused, and so
  are GRIDIRON_DB and GRIDIRON_HOME set elsewhere, a hard link and a `..`
  spelling (`fix5a/rehearsal/s10_final.txt`). The meta `kind` is no second
  witness: every `db.init` writes `live` by default.
- **A column name's case is still normalised.** `Sport` and `sport`
  compare equal; they read the same in SQL and differ as `dict(row)` keys.
  Measured on the live record: no table's column names differ in case from
  either build, so nothing is hidden today. Unchanged, as ruling 1's
  normalisation has always read it.
- The rehearsal's copies (about 1 GB each, `fix5a/rehearsal/*.db` and
  `fix5a/rehearsal/final/*.db`) are scratch and may be deleted.

### FIXED BY THE PROVER: the last-one-wins rule erased a NOT NULL and a DEFAULT *(2026-09-26)*

Finding 4's fix compares only the last COLLATE, DEFAULT or NOT NULL of a
column, as SQLite keeps it. But `NOT DEFERRABLE` and `ON DELETE/UPDATE SET
DEFAULT`, the tail of a REFERENCES clause, each opened a clause of their own
whose kind was "not" or "default" -- so `x INTEGER NOT NULL REFERENCES p (id)
NOT DEFERRABLE` lost its NOT NULL, and `x INTEGER DEFAULT 5 REFERENCES p (id)
ON DELETE SET DEFAULT` its DEFAULT 5. Measured on scratch tables: SQLite
refused a NULL in one and took it in the other, and stored 5 in one and NULL
in the other, while `table_differences` found nothing and
`rebuild.differences_from` said "already at its definition" -- the
migration would have skipped the table. a1df279 saw both (it compared every
clause); the regression came with the fix. The gate's `compare` still caught
each through SQLite's own PRAGMA reading. Neither shape is in `schema.sql` or
on the live record today, so no comparison changed. `schema_diff._column`
now keeps both inside their REFERENCES.
`test_schema_diff.py::test_quoted_text_that_changes_behaviour_is_a_difference`
gains both pairs, each shown first to behave differently; both fail on the
tree as built and pass now.

### FIXED BY THE PROVER: an importer under another name fetched the driver past the scan *(2026-09-26)*

The raw-connect scan knew the importer only by the names `import_module` and
`__import__` were written with, and only with the driver's name as its first
positional argument. Six shapes opened a database unnamed, measured on a
scratch tree: `load = importlib.import_module` then `load("sqlite3")`, the
same with `builtins.__import__`, `builtins.__dict__["__import__"]("sqlite3")`,
`getattr(builtins, "__import__")("sqlite3")`, `importlib.util.find_spec`, and
`importlib.import_module(name="sqlite3")`. A constant naming a driver, as
any call's argument or keyword, is refused now; the real tree hands the name
to no call (0 faults). `plant.py::plant_a_raw_connect_through_any_call_by_name`
ESCAPED on a1df279 and on the tree as built, and is CAUGHT;
`test_one_way_in.py::test_the_driver_fetched_by_name_through_any_call_is_named`
runs each shape first to show it opens a database. Still unseen: a driver
name computed at run time (`"sql" + "ite3"`), as before.

### FIXED BY THE PROVER: a report "folder" that was a file *(2026-09-26)*

`--report <record>/report.json` passed the folder check -- `exists()` is
true of a file -- so a `--live` run migrated the record and then ended in a
traceback where the report was to be written, after the COMMIT (measured on
a stand-in record). The folder must be a folder now, checked before
anything is done, and a report that cannot be created at the end is named
("REPORT NOT WRITTEN ... could not be created"), never a traceback in the
verdict's place. `test_rebuild.py::test_a_report_is_never_written_over_the_record_the_backup_or_a_database`
gains the case; `::test_a_report_that_cannot_be_created_is_named_not_a_traceback`
is new; both fail on the tree as built.

Found in passing, not changed: a `--scratch` whose "folder" is a file ends
in a traceback (`FileExistsError`, the backup door making the folder) BEFORE
anything is migrated -- measured on a scratch database in the live shapes,
the source byte for byte unchanged; only the message is unkind. A missing
folder is made by the backup door, and the run goes on.

## The prompt record -- built 2026-09-25 *(the ruling of 2026-09-24, two additions, item 1; the ruling on question 4, 2026-09-25; GRIDIRON_REPAIR item 4)*

### BUILT: every reasoning forecast carries the prompt it was sent, or a labelled reconstruction *(ruled 2026-09-24 and 2026-09-25; built 2026-09-25)*

- **Sent.** `llm.reason` builds the request once (`reasoning_request`),
  serializes it canonically (keys sorted, no spaces, UTF-8) BEFORE the call and
  sends the parse of those bytes, so what `reasoning_prompts` keeps is what the
  client received by construction; `StubClient` now records every keyword and
  `test_prompt_record.py` compares the two byte for byte. The reformatting
  request, whose user message is the reasoning model's raw reply (stored
  nowhere else until now), is kept with it when that runs.
  `write_prediction` refuses a reasoning row without the prompt and writes the
  record, the row citing it in its factors, and the fingerprint in one
  savepoint. The link lives in `factors_json` (already frozen and
  fingerprinted), so `predictions`, `fingerprint.PROTECTED` and
  `RECORD_BASELINE` are unchanged.
- **The release instant** is written once into `meta` by the first `db.init`
  under the new schema -- now, or one second after the newest reasoning row
  if that is later -- and triggers refuse a second value, an edit, a delete
  and a replacing insert. The trigger and the gate read it from there.
- **Reconstructed.** `tools/reconstruct_prompts.py`. Rehearsed on a scratch
  copy of the live record (backup door, 19:37Z on 25 September): **510
  reasoning rows, 14 commits, 6.8 s**, every row matched to exactly one
  reasoning call in the ledger; a second run wrote nothing; the gate's audit
  passed on the result. The 467 rows the dry run of the morning rebuilt
  independently are byte-identical to this tool's (467 of 467), and that dry
  run matched the 24 September rebuild of 31 rows (31 of 31). By commit:
  48628e5 23, b80c5ca 42, 148e484 22, 57dcc78 1, 65b698b 5, 25d83b8 30,
  d3bce31 6, 9e4203f 31, 9ac0ac4 64, fb6dcdf 10, c44f508 128, e1d9632 71,
  fddd61b 34 (ids 2358-2441), 3603300 43 (ids 2448-2507, written since 5a's
  release). By sport: CFB 25, MLB 301, NFL 90, UFC 94.
- **The gate** applies the reconstruction to its migrated copy (about 7 s on
  top of the copy it already makes) WHILE THE RECORD HAS NO RELEASE INSTANT,
  and then names, on the copy, every row after the instant without its sent
  record, every row with none at all, and every record whose text does not
  hash to what was written with it. From the release on it rebuilds nothing
  and checks the record's own records as they stand (changed by the
  rehearsal, below).

### NEXT, AFTER THE RELEASE: the reconstruction on the live record *(operator step, not run)*

After the fast-forward and the scheduler's first task (which writes the
release instant), from the main checkout, at a quiet hour:
`python tools/reconstruct_prompts.py --database var/gridiron.db --live`. It
appends one reconstructed record per reasoning row before the instant and
writes nothing else; it is idempotent, and its last line says how many of
the record's reasoning forecasts carry a record after the run, of each
kind, and which carry none (exit 1 while any does). UNTIL IT RUNS, EVERY
GATE FAILS BY NAME on each pre-release row without a record, as the ruling
asks: from the release on the gate checks the record as it holds it. A pass that writes reasoning rows between the
release and the scheduler's first `db.init` is impossible (that init writes
the instant); an old-code process still running after it is refused loudly
by the trigger, and its task run is recorded as failed.

### THE REHEARSAL *(2026-09-25, about 20:20-20:45Z; scratch copies of the live record through the backup door, never the record, never `--live`)*

- **The instant.** The first `db.open_db` of a fresh copy wrote
  `prompt_record_binds_from` once (20:41:59Z; the newest reasoning row was
  19:33:02Z); a second open two seconds later and a direct second call of
  `write_the_release_instant` left it where it was, one row under the key.
- **The tool, from its command line.** 510 reasoning rows, 510
  reconstructed records, 14 commits, 6.7 s; every reasoning row has exactly
  one record, every record names one ledger call (510 distinct), and the
  audit finds nothing. A second run wrote nothing. Two independent runs
  (before and after the fixes below) wrote identical records but for the
  rebuild date. Rows per commit and the caveat each carries, as the tool now
  prints them: 48628e5 23 (working tree 23, a halfway digit 1); b80c5ca 42
  (working tree 42, no scheduled task 42); 148e484 22, 57dcc78 1, 65b698b 5,
  d3bce31 6, 9ac0ac4 64, fb6dcdf 10 (working tree, all); 25d83b8 30 (working
  tree 30, no scheduled task 30, halfway 1); 9e4203f 31 (working tree 31,
  halfway 1); c44f508 128 (working tree 128, halfway 3); e1d9632 71,
  fddd61b 34, 3603300 43 (no caveat beyond the commit). For every row the
  commit at its minute is also the commit its own task run started under
  (measured: 0 differ), so no process ran code older than the row's minute.
- **Against the 24 September rebuild.** The 31 prompts rebuilt that morning
  (ids 2226-2302) are byte-identical to the tool's, through e1d9632, and the
  ledger calls named agree 31 of 31. No difference, so no cause to give.
- **Against the ledger's own counts.** The rebuilt request's length over the
  call's input tokens is 3.9 to 4.4 characters a token for all 510 rows,
  none more than 15% off the median -- nothing rebuilt lost or gained a
  section, which a byte comparison with no original cannot show.
- **A post-release pass**, MLB slate 182's late pass through the tests'
  `StubClient`, the network blocked: 28 reasoning rows, 28 sent records
  byte for byte what the client received, each cited, sent before its row,
  hashed, tied to its ledger call; each record, its row and the fingerprint
  sit between one `SAVEPOINT write_prediction` and its `RELEASE`, with no
  COMMIT between. Refused by name: a raw reasoning row after the instant with
  no record, citing a record that does not exist, reusing another row's,
  citing another game's, citing a reconstruction, with factors that are not
  JSON; a reconstruction of a post-instant row through the door and round
  it; a second reconstruction; an edit, a delete, a moved instant. Nothing
  changed.
- **The gate's three checks** pass on the copy (538 forecasts, 510
  reconstructed and 28 sent, the label scan reading all 538). On throwaway
  copies the audit named a reasoning row planted dated before the instant
  with no record ("NO PROMPT RECORD AT ALL"), and one after it with the
  trigger dropped ("WRITTEN AFTER THE RELEASE ..." and the missing rule).

### FIXED BY THE REHEARSAL: the gate rebuilt a released record before checking it *(2026-09-25)*

`verify._gate_copy_path` applied the reconstruction to every copy, so the
check the ruling asks for -- "the gate fails by name ... on any row of any
date with no record at all" -- could never fire for a row dated before the
instant. Measured on a released throwaway copy: forecast 2582, written
round the door dated 20:00Z against an instant of 20:24Z, was rebuilt on the
gate's copy through 3603300 (which never wrote it) and the check passed.
The same step would have passed every gate after the release while the live
record still lacked its reconstructions (what the build's notes called a
known gap). Now `verify._bring_the_copy_to_this_tree` reads the record's own
instant before it migrates the copy, and rebuilds the copy only while the
record has none; from the release on the copy is checked as the record holds
it. Planting `plant_a_released_record_the_gate_rebuilds_before_checking`
(ESCAPED on HEAD d835fff and on the build before this fix; CAUGHT after);
tests in `test_prompt_record.py` for both sides of the release.

### FIXED BY THE REHEARSAL: "no scheduled task was running" *(2026-09-25)*

The tool asked whether ANY task run enclosed the forecast's minute, and a
run never finished enclosed every minute after it: `live` polls every few
minutes and `refresh` writes no forecast, and a `final:cfb` run begun at
19:41Z on 9 September was still "running" on 25 September. A forecast
written by hand beside either would have been told a scheduled task wrote
it. Now only the sport's own predict and final tasks and the catch-up count,
and a run never finished counts until its task next started. No record on
the live record changes (72 rows carry the caveat before and after); a row
planted at 20:00Z on 25 September now carries it, where the stale `final:cfb`
run of 19:24Z would have hidden it.

### FIXED BY THE REHEARSAL: what the tool prints *(2026-09-25)*

The run that writes the live record now prints each commit's caveat counts,
the coverage it leaves behind (how many reasoning forecasts carry a record,
of each kind, and which carry none), and exits 1 while any carries none.

### OPEN: a row dated before the instant but committed after it is rebuilt, not refused *(found by the rehearsal, 2026-09-25)*

The tool and the trigger `reasoning_prompt_reconstructed_only_before_the_release`
decide "written before the release" by the forecast's own `created_utc`, which
its writer chose. A reasoning row inserted round the door after the release
with an earlier date is therefore rebuilt by `--live` and labelled
reconstructed -- after the fix above the gate names it until then, and the
tool now names it as it rebuilds it and exits 1 ("REBUILT, BUT COMMITTED
AFTER THE RELEASE INSTANT", read off its fingerprint's time or its missing
fingerprint above the record's fingerprint baseline). Not refused, because
both ways of refusing it also refuse a lawful row: old code that took its
`created_utc` just before the first `db.init` of the release and committed
just after (waiting on the write lock) writes a row dated before the instant
and fingerprinted after it, which could never carry a sent record and would
fail every gate for good. Options: refuse above the baseline by fingerprint
time and accept that race (it needs a reasoning write inside the same
second as the release's first open); or freeze the last forecast id at the
instant, with the same race. Neither was needed for the rehearsal.

### READINGS TAKEN, for the operator to overrule *(2026-09-25)*

- **"The Record page".** The Record tab shows only aggregates; the per-row
  record is Results. Both readings are built with one component: a panel on
  the Record tab, shown only while its forecaster picker is on the reasoning
  pass (a count with its N, and the sport's newest twenty), and the same
  disclosure under every reasoning row in Results -- plus the card's Why
  panel for "the page". Nothing on the statistical record changes.
- **The prompt is shown verbatim**, in a `.code-literal` block -- the
  existing exemption from the plain-words scan for "an identifier stamped on
  a prediction" and strings a reader must see exactly. Measured: 70 of 467
  prompts rebuilt through today's code contain snake_case, from 17 registry
  rationales that name other factors by code name (the `what it measures:`
  lines), and the pre-5 September prompts named every factor that way.
  Humanised, it would match no stored hash and would not be the prompt the
  ruling asks to be shown. The label, the note and every other word stay
  plain and are scanned (`audit.prompt_label_faults`).

### The prompt of a call that wrote no row is not kept *(open, 2026-09-25)*

The ruling binds "every row it writes"; a call that failed, or answered with
something unparseable, writes no row, and its request is not stored. 33
failed reasoning calls are on the ledger (read 2026-09-25). If a rejected
answer's prompt is ever wanted, `llm.record_call` would carry the request.

### `llm_calls` has no append-only triggers *(open, found by the item 4 maps, 2026-09-25)*

The conventions call it append-only; the schema has only its day index, and
row 37 (`key_probe`) was written by hand. A prompt record now cites a ledger
row by foreign key, which stops a cited row being deleted but not edited.

### The Results "Prediction" column is outside the rendered plain-words scan *(open, found 2026-09-25)*

`td.wide` is excluded to spare the Factors table's rationale column, and the
Results table's first column carries the same class -- so the scan never
reads the column whose `rushing_yards` leak is why the rendered scan exists,
nor the prompt disclosure's label and note placed there. The server-side
audit covers the disclosure's words; the column itself is unscanned. Scope
the exclusion to the Factors table.

### FIXED BY THE RENDER CHECK: two defects a green suite passed *(2026-09-25)*

The disclosure was rendered from the browser suite's own world (one sent and
one reconstructed reasoning forecast, stub data, never the live record) at
1100 and 390 wide, each prompt collapsed and opened, on a card's Why panel,
in Results and on the Record page. Labels, overflow (0 px), tap floor (44
px) and the collapsed card were right. Two things were not:

- **A reconstruction's text was headed as the prompt sent.** Opened, it read
  "What it was told before the question" and "The question and the factors
  it was given" above the rebuilt text -- headings asserting what the
  forecast was told, over text the ruling says "is never presented as the
  prompt sent" -- and on a phone the one "reconstructed" sat about 4,000 px
  above the end of it. `language.prompt_part_label` now takes the record's
  kind and a reconstruction's parts read "..., reconstructed"; a sent
  prompt's never do. Asserted in `test_prompt_disclosure.py` (every heading
  of each open disclosure, both kinds, on all three surfaces and both
  widths) and `test_prompt_record.py`.
- **An opened prompt in Results floated its row's facts out of sight.** The
  row grew to about 3,000 px and the table's middle alignment put the date,
  model, tier and result about 520 px below the sentence at both widths, so
  the screen showed prompt text beside an empty band. A row with its prompt
  open now aligns its cells to the top (`style.css`, only while open);
  `test_prompt_disclosure.py` measures each cell against the sentence.

Both assertions were shown failing on the unfixed code first (headings; 522
and 532 px of drift) and passing after. Not changed, and why: the prompt
stays in the Prediction column's width at a desk (widening the column broke
the other columns' lines); the commit and the model's name are shown as
`.code-literal`, the reading already recorded above.

### FIXED BY THE PROOF: a planting that crashed where it should have said NOT CAUGHT *(2026-09-25)*

Each of the six prompt-record plantings was proved twice before this commit:
against `git archive` of HEAD d835fff with the new `plant.py` (all six
ESCAPED), and against a copy of the new tree with ONLY that planting's own
guard neutralised -- the trigger kept by name with its condition made false,
or the one audit branch made unreachable, or the gate's copy rebuilt
whatever the record's instant (nine copies: (a) trigger, (a) audit, (b)
audit, (c) each of the three append-only triggers, (d) audit, (e) audit, (f)
gate). Eight ESCAPED. The ninth, (a) with its trigger neutralised, did not
report at all: the row the trigger let in stayed on the world, the planting
then copied that world and wrote the same question again for the audit, and
the one-answer index refused it -- an `IntegrityError` traceback that would
have ended the whole harness at that line instead of printing a verdict.
`plant_a_reasoning_row_after_the_release_without_its_prompt` now reads a row
that landed with the audit on the world it landed on, and says NOT CAUGHT in
words (the schema did not refuse it; whether the audit named it). Shown
crashing on the unfixed planting and ESCAPED after; CAUGHT on the new tree
as before; the harness 294 of 294.

### FIXED BY THE PROOF: one sent prompt shared by two forecasts through a cite spelled as text *(2026-09-25)*

Probed on a scratch world after the plantings: a reasoning forecast after
the release instant whose factors cite its sent record as the TEXT "1"
rather than the number 1 landed, and a second forecast citing the same
record as the number landed beside it (and the other way round). SQLite
matched the text to the record by the id column's integer affinity, so
`reasoning_row_carries_its_prompt`'s record test passed; its
no-other-forecast test and the one-forecast index compare two cites as
stored, where a number and a text never match. The page (`records_for`,
matching the same way) showed one prompt under both forecasts. The gate's
audit already named the text cite ("WRITTEN AFTER THE RELEASE WITHOUT THE
PROMPT IT WAS SENT ... it cites '1'"), so the second lock held; the first,
the schema, did not. Only a write round the door can do it --
`write_prediction` writes the id the door returned, a number.

Now the trigger refuses any cite whose JSON type is not an integer (a text,
a real, a boolean, none), and `prompt_record.records_for` reads only an
integer cite, as the audit does, so the page and the gate agree that a
text cite is no record. `plant_a_second_forecast_citing_a_sent_prompt_as_text`
ESCAPED on the build before the fix and on `git archive` HEAD d835fff and is
CAUGHT after; `test_prompt_record.py::test_a_cite_that_is_not_the_records_own_number_is_refused`
failed on the build before the fix and passes after. Not changed: the
audit's "ONE PROMPT FOR TWO FORECASTS" still keys cites as stored, which is
moot now that a post-release text cite cannot land and a pre-release one is
named as having no record at all.

### Found in passing *(2026-09-25)*

- **A made-up identifier in stored reasoning.** Row 2471 (NFL, written
  19:26Z on 25 September) says "(neither_neutral=1)"; no factor declares the
  name, so no registry phrase could replace it, and
  `test_stored_reasoning_is_humanised_at_render_time_not_rewritten` went red
  on live data. `language.humanise_reasoning` now reads any code-shaped word
  left over in words, the rule `plain_reason` has used for a void's reason
  since 2026-09-24. The row keeps what was written.
- **Six rows where one digit of the prompt cannot be known** (467, 1226,
  1328, 1779, 1821, 2035): each stores a number exactly halfway at the fourth
  decimal place, which the prompt showed rounded from full precision. The
  reconstruction names the factor on each record.
- **Corroboration outside the record** (session transcripts, not stored on
  any record): the 5 September hand run was on a clean checkout at b80c5ca
  (02:38:43Z and 02:58:21Z); the 9 September final:mlb run at 21:30Z ran on
  uncommitted non-prompt edits later committed in fb6dcdf; the 24 September
  e1d9632 rows were on a clean checkout (05:29:31Z).
- **A reasoning card hides its own reasoning when a market line exists**
  (12 of 39 cards the live record would show): the Why panel shows the market
  sentence instead. The prompt disclosure sits beside it.
- **The Results "Forecaster" column prints the raw value** `llm` when both
  forecasters are shown, and the Record headline's sub-line glues the raw
  predictor in the renderer; neither word is on a scan's list.

## An untrained market fails the run by name -- built 2026-09-26 *(GRIDIRON_REPAIR item 2, its remainder; the operator's ruling of 2026-09-23)*

"run.py:99 may never skip an untrained market silently -- a predict run with a
skipped market fails by name, and the day strip shows it. Planting: an
untrained market in the active set fails the run." The fs5 half of the ruling
was settled on 24 September (the activation gate, ff7e5ab; the revert,
4c3bda4). This is the rest.

### BUILT *(2026-09-26)*

- **One door**: `baseline.untrained_markets(conn, sport, include_props=)`.
  Every market in `config.active_markets` that is not held (a prop only when
  the run asks props) and cannot be forecast from: `load_fit` finds no
  activated fit (`none_active`) or an active fit of another factor set
  (`another_set`), or the active fit reads a factor the registry no longer
  computes for the market (`factor_not_computed`, through
  `assert_the_vector_carries_the_fit` against every factor the market's
  vector would hold).
- **The run**: `predict_slate` carries that list on `BlindRun.untrained`, and
  adds any question skipped for either reason that the door did not foresee.
  `run.run_slate` raises `MarketNotTrained` -- every market named, with its
  reason, in words ("NFL moneyline not forecast: no model is in use for it.
  This run wrote 8 forecasts for the markets that have a model and is
  recorded as failed ...") -- AFTER the markets that have a model are written,
  snapshotted, ranked and recommended, and before it returns, so `run_task`
  records the task `failed` with those words (the Health panel strips the
  class name). The final pass fails the same way.
- **The refusal**: `run.already_answered` no longer leaves a market with no
  model out of what a run expects (0768ce4's rule of 2026-09-04, retired by
  the ruling), so a slate one of whose markets was never asked is never
  refused as answered: every rerun fails by name instead. No question is
  written twice -- `predict.already_written` is that door, and the unique
  index behind it.
- **The strip**: `views.freshness` adds one stale line per sport the record
  has forecast, or whose run has been recorded failed for want of a model
  (the prover, below), through the same door ("NFL moneyline not forecast: no model
  is in use for it"), and `audit.freshness_faults` refuses a strip that
  leaves a market off; "not forecast" joins the words a stale line may say it
  in. Rendered at 1100 and 390 px on a synthetic world, one market and seven:
  no horizontal overflow, the seven-market line wraps to four lines at 390.
- **Plantings** (all three ESCAPE on HEAD f2c40ff with this plant.py, and are
  CAUGHT on this tree; 301/301, and 302/302 with the prover's fourth, below):
  `plant_an_untrained_market_in_the_active_set`
  (the act of 6 September -- a version declared for the NFL moneyline and
  never trained: the run must fail naming it, the spread and total still
  written, and the strip say so), `plant_a_rerun_refused_over_a_market_it_never_asked`
  (the 27 NFL and college refusals of 7-23 September, 20 college and 7 NFL,
  read from `task_runs`: the rerun must fail by name, not be
  refused as answered, and write nothing twice), and
  `plant_an_untrained_market_the_strip_leaves_off`. `plant_a_fit_reading_a_retired_factor`
  now also requires the run to fail naming the point spread.
  `plant_an_unfitted_market_that_blocks_a_rerun_refusal` is RETIRED with the
  rule it asserted.
- **The worlds**: the harness league trains the moneyline and the total as
  well as the spread (the spread last, so it stays the newest fit the
  activation plantings read). The tests' league has a running back (its own
  random stream; no existing number moved), because rushing yards is asked
  of a back alone and a league without one could never train it. A test world
  that trains only some markets says so with `tests.conftest.asks_only`,
  which retires the others for the test -- the one way the record itself
  stops asking a market -- where it used to lean on the silent skip.

### MEASURED ON THE LIVE RECORD, read-only *(2026-09-26 about 03:00Z, `db.read_the_live_record`)*

Every active market of all five sports has an activated fit of its declared
set, and no active fit reads a factor the registry no longer computes (the
four fs5 markets on fits 88, 71, 44 and 35; MLB home runs is retired and not
asked). `baseline.untrained_markets` is empty for every sport with and
without props, the strip adds no line, and `check_the_strip_shows_a_dead_job`
passes. So the release turns no scheduled pass red. Gate step 3 trained all
eight NFL markets on the gate's copy in the last gate (5b), so it is not
turned red either. **No live-record write is needed.**

### READINGS TAKEN, for the operator to overrule *(2026-09-26)*

- **Write what can be answered, then fail** -- not refuse the whole slate
  before writing. The ruling's words are "a predict run with a skipped market
  fails by name": a run that skipped a market, and failed. The precedent is
  the hold and the activation gate's own refusals, each of which leaves its
  one market unforecast and says why while the rest are written. Failing
  first would have cost every other market of the sport for as long as the
  one market had no model -- on 6 to 23 September, the NFL and college totals
  and props too. The one-line reversal: raise before `forget_market_module`
  instead of after the recommendations.
- **"Untrained" is every reason a market has no model it can forecast from**:
  no activated fit, an active fit of another set, and a fit reading a retired
  factor -- the three skips `predict` made. A held market is not untrained
  (not asked; the strip has its own line), nor a retired one (over, not
  missing), nor a prop in a run that asks no props.
- **The strip lists a sport only once the record has forecast it**, as the
  hold does: an empty record is not a stopped one. **Narrowed by the prover
  the same day**: or once a run of it has been recorded failed for want of a
  model (below).

### FOUND BY THE PROVER *(2026-09-26)*

- **A sport whose first run failed by name was off the strip.** A sport
  whose first run meets no model writes nothing, so the record never holds a
  forecast of it, and the strip that waited for one said nothing while the
  run failed by name on the Health panel -- with the daily-run age kept fresh
  by another sport, the shape of 6-23 September. Reached on the harness
  league through the task runner: recorded `failed`, 0 written, three ages on
  the strip. None of the five sports is in that state today (every one has
  forecasts on the record), so it waited for a new sport. FIXED:
  `tasks.failed_for_want_of_a_model` (read from the words `run_task` records
  a failure in, beside it) and `views.freshness` lists such a sport too; the
  door still decides what is listed, so the line goes once the market has a
  model. `plant_a_first_run_failed_by_name_off_the_strip` ESCAPES on HEAD
  f2c40ff (recorded `noop`, "every question on this slate was already
  answered" -- the silent skip itself) and on the implementer's tree
  (recorded `failed`, the strip silent), and is CAUGHT on this tree (302/302);
  `test_untrained.py::test_a_sport_whose_first_run_failed_by_name_is_listed`.

### OPEN, found by this item *(2026-09-26)*

- **A long failure pinches the Health panel's name column** (the prover's
  renders, 2026-09-26). `.set` is `grid-template-columns: 1fr auto`, so a
  long `last_detail` in the value column squeezes the task's name and its
  description to one word a line, at 1100 px and at 390 (no overflow; the
  words are right). Not new -- any long failure does it, a
  `SlateAlreadyAnswered` among them -- but this item's words are long and
  every untrained run now writes them. A CSS or placement change for its own
  render review.
- **A run that fails for another reason after writing says only that
  reason.** The untrained check is raised after the snapshot, the ranking,
  the second forecaster and the recommendations, so one of those raising
  first fails the run naming itself, not the market with no model; the strip
  still names the market (a sport with a forecast). Written-then-fail is the
  reading taken above; the fail-first reversal would close this too.
- **Every rerun of an open slate re-measures its rungs.** A slate kept open
  by a market with no model is no longer refused on rerun, so each scheduled,
  catch-up and final pass re-logs the prop rung claims
  (`rungs.record`, append-only, one row per rung per second) while the
  market has no model. Measurement rows, not forecasts; none today.
- **A failing task pops a desktop notice in a test or a planting.**
  `run_task` calls `notify_failures` on any failure, which shows a Windows
  toast and posts to the push topic if one is configured; the scheduler test
  of a failing task does it already, and `test_untrained.py`'s run-task test
  does too. The prover's own test and planting keep it quiet
  (`GRIDIRON_NOTIFY_FAILURES=0`; a stub).

- **Item 7 must not reclassify this failure.** Item 7 turns
  `SlateAlreadyAnswered` into a noop; `MarketNotTrained` must stay `failed`,
  or the gap is silent again.
- **Training still skips in a list.** `baseline.train_all` catches
  `NotTrained` and `ValueError` per market and reports it only to `progress`.
  It is caught downstream now -- the next run fails by name -- but
  `tools/backtest.py` (not in the gate) will now fail a season in which a
  market cannot be fitted, where it used to skip it.
- **A held market still counts as a gap in `already_answered`**, as it did
  before when trained: a rerun while a market is held is not refused and
  writes only questions with no row. Unchanged here; `HELD_MARKETS` is empty.
- **The strip reads the door, not the run.** A question skipped for want of
  a model that the door did not foresee fails the run by name (the run adds
  it to its own account) but is not on the strip. None is known: the door
  checks each fit against the factors the registry computes for its market,
  which is what every adapter's vector holds today (only baseball narrows a
  prop's factors by market, and its adapter passes the market).
- **"total" on the strip, "Total points" on the tab.** `language.market_words`
  has no entry for the total, so the held line and this one say "total";
  plain, but not the tab's word.

## Corrections reach recommendations -- built 2026-09-26 *(GRIDIRON_REPAIR item 3; the operator's ruling of 2026-09-23)*

"Corrections reach recommendations. recommend.py:324 reads the corrected
probability, never the raw claim. Re-derive nothing retroactively (LAW 3);
from the fix forward, every recommendation carries the correction that was
current. Planting: a fitted correction that would flip a side must flip it."
(The line has moved since the ruling: the raw read was `model_prob =
row["claim_prob"]` at recommend.py:330 on 7aedf30.)

### BUILT *(2026-09-26)*

- **One door for a number stated from a proposition**:
  `correction.shown_proposition(conn, sport=, market_type=, forecaster=,
  proposition=, at_utc=None)`. A claim at the line is stated from the home
  side or the over, so it sits either side of a half (628 of the live
  record's 1,264 claims were below it on 2026-09-26), while every fit is
  fitted on confidences (0 of 2,581 forecasts below a half). The door turns
  the number to the side it favours (a half favours the proposition, as
  `baseline.stated_side`), corrects it through `shown_claim`, and turns it
  back -- the order `predict.write_prediction` already uses. It has no SQL of
  its own. `shown_claim` gained `at_utc` (passed to `active_correction`,
  which already took it); every existing caller is unchanged.
- **The pick**: `recommend.for_predictions` reads the claim through the door
  (the correction in force now -- before the start only, from the prover of
  2026-09-26; see "PROVED" below), so the side, the edge, the bar and the size
  come from the corrected number. Each entry carries `fair_value` (corrected:
  what the card's model chip, the recommendation line, a combo's legs and a
  package's legs read, so they agree with no second door), `raw_fair_value`
  and `correction_version`.
- **The row**: `record_for` writes `fair_value` = the raw claim's number, as
  every earlier row has it, and beside it `calibrated_fair_value` and
  `correction_version` -- NULL together when nothing was in force, which a
  column CHECK holds (paired, and the number strictly between 0 and 1). The
  version is looked up before the row is stamped (`just_after` is never
  earlier), so a row never carries one that activated after it. The same
  shape as a forecast's `model_prob` / `calibrated_prob` /
  `correction_version`.
- **Frozen**: `recommendation_correction_is_frozen`, a NEW trigger, refuses an
  update of either column (LAW 3). `recommendations_no_update`'s column list
  is untouched: its text never reaches a record that holds it, and dropping a
  LAW 3 guard to restate it would leave the table unguarded meanwhile.
- **The migration**: two `db.MIGRATIONS` entries, correction_version first
  (the CHECK names it), with exactly the clauses `schema.sql` declares, last
  in the table as on a record that gains them by ALTER. In `db`, not the
  market module: `recommendations` is not a LAW 1 quarantined table (nothing
  in `audit.FORBIDDEN_IDENTIFIERS`; the closing line in `calibration`, the
  near-start pass in `tasks` and the views already read it), and since 5b the
  gate compares a copy that `db.init` alone migrated with a fresh build, so a
  column added only when `record_for` next ran would fail it.
- **The page**: `views._at_the_line` reads the claim through the same door --
  the correction in force now before the start, as the pick beside it; the
  claim's own instant once the game has started, so a started card is never
  corrected afterwards (`views._claim_instant`). `views._pregame_probability`
  (a live card) corrects as of the claim's writing, which makes its docstring
  -- and `language.pregame_words`' -- true: both already said "the corrected
  probability the claim was written with" and it returned the raw claim.
  `combos.fair_value`'s docstring ("the corrected ones where a correction is
  in force") is true from today and says so.
- **Planting** `plant_a_correction_that_does_not_reach_the_pick` (a baseball
  away forecast at 57%, a 43% home claim, a 48.5c price; the correction is
  the live baseball total reasoning fit, v2: slope 0.449, intercept -0.270):
  raw, the no side at +3.5c; the fit recorded INACTIVE, still the no side;
  activated, the yes side at +3.08c from 0.5358, version 2; the row written
  with 0.43 / 0.5358 / 2; an update of the pair to NULL refused by LAW 3.
  ESCAPES on HEAD 7aedf30 with this plant.py ("left the pick on no at 3.5c
  with fair value 0.43 (version None)"), and on six broken copies of this
  tree, each ESCAPED at its own step: the fit applied to the proposition
  unturned (no at +6.29c from 0.4021), the latest fit applied whether active
  or not (the inactive fit flipped it), the raw claim read, the row written
  without its correction, the corrected number written over the raw one, and
  the freezing rule disabled. CAUGHT on this tree (303/303). The eight new
  tests and the harness-list test each fail on HEAD 7aedf30's package; the
  full suite passes on this tree (1,643 passed, the standing 8 skipped).
- **Tests**: `test_correction.py` (no correction, an inert fit, the turn and
  the tie, the version in force at an instant, another forecaster's fit);
  `test_recommend.py` (the flip, an inert or future fit decides nothing, the
  row and its freeze and its CHECK, one number on the card, the at-the-line
  sentence, the recommendation line and the pregame figure);
  `test_schema.py::test_an_older_record_gains_the_correction_columns_exactly_as_declared`
  (an older table through `db.init` equals a fresh one by `table_xinfo` and
  by `schema_diff`, keeps its row, and is frozen from the first open);
  `test_schema.py::test_a_fresh_build_holds_every_column_an_ensure_step_adds`
  now covers the two columns through `db.MIGRATIONS`.

### MEASURED ON THE LIVE RECORD, read-only *(2026-09-26 about 05:00Z, `db.read_the_live_record`)*

- **63 fits, 0 ever active** (`calibration_corrections` is append-only, so
  that is its whole history); the last refit 2026-09-21T22:11:39Z, weekly, so
  the next about 2026-09-28. **The fix changes no recommendation today**: every
  row written until a refit activates a category carries NULL / NULL, and the
  pick is the raw claim's, exactly as before.
- **The rehearsal** (a scratch copy through the backup door, never the
  record): before, the copy against a fresh build of master: 10 objects
  differ only cosmetically, 0 differences. `db.init` of this tree added the
  two columns and the trigger; 96 rows, every stored column's checksum
  unchanged, both new columns NULL on all 96. The migrated copy against a
  fresh build of this tree: 10 cosmetic, **0 differences**. Against master it
  shows exactly the two columns and the trigger, as it must until the
  release. A second `db.init` changed nothing.
- **Hindsight only, nothing written** (97 standing recommendations at about
  05:05Z; `recommend.not_withdrawn`): as built (the correction ACTIVE at each
  row's stamp) all 97 are unchanged. Had the latest FITTED version at each
  row's stamp been applied, active or not, 10 would differ: 3 flip (46 and
  49, baseball totals from the reasoning pass, no to yes; 88, a college
  spread, no to yes) and 7 lose their side (43, 45, 47, 81, 82, 91, 99). With
  the latest fit of today applied to all, 20 would differ, 8 of them flips.
  They keep their sides, edges and fair values as written (LAW 3).

### THE LIVE WRITE THE RULING REQUIRES *(after the release; no tool)*

Schema only, additive, and `db.init` makes it: the first open of the live
record by the released code -- the release step's own `/api/health` call
after the restart (it opens the record through `db.open_db`), or the
scheduler's next task, whichever comes first -- adds `correction_version`
and `calibrated_fair_value` to `recommendations` (NULL on every existing
row) and creates `recommendation_correction_is_frozen`. Nothing is updated,
deleted or backfilled, and no tool is needed. Until that open, the gate's
release comparison would name the two columns and the trigger as missing
from the record, so confirm through the read-only door after the restart,
before the next gate.

### READINGS TAKEN, for the operator to overrule *(2026-09-26)*

- **"The correction that was current" is the ACTIVE correction** for (sport,
  market type, forecaster) at the moment the recommendation is written --
  never a fitted version the holdout did not activate, and never a later
  one. The C2 gate's ruling (a fit is inert until activated) and every other
  consumer of `shown_claim` read it so. "A fitted correction" in the planting
  is read as fitted and activated; the planting also proves an inactive one
  decides nothing. The other reading (the latest fitted version, active or
  not) would have applied fits the holdout refused -- two with NEGATIVE
  slopes (baseball moneyline reasoning v3, -0.353; UFC rounds statistical v3,
  -0.127) -- and in hindsight changed 10 of 97 standing recommendations.
- **`fair_value` keeps its meaning**; the corrected number goes beside it
  with the version, as a forecast's does. The other way (the corrected number
  in `fair_value`, the raw one beside it) would change what an existing
  column means from a date on. No reader of the table reads `fair_value`.
- **The migration lives in `db.MIGRATIONS`** (above), where the house rule
  puts a market table's migration in the market module: that rule rests on
  the LAW 1 scan, which does not cover this table, and only `db.init` reaches
  the gate's migrated copy.
- **The page's numbers go through the same door** (the at-the-line sentence,
  the pregame figure): the brief's "no new features" is kept -- no label,
  layout or word changed, and while nothing is active every number is the
  one it was.

### OPEN, found by this item *(2026-09-26)*

- **The ranker orders on the raw claim.** `shortlist.rank_rows` scores
  confidence and the edge from `predictions.model_prob` and the snapshot,
  while `shown_claim`'s docstring names "the sort order" as a consumer of the
  corrected number. The brief forbids ranker changes, so it stays raw; once a
  category activates, the shortlist and the pick can disagree about how
  strong a question is.
- **A card computed after a later activation differs from its stored row.**
  The page calls `for_predictions` at view time, so a correction activated
  after a recommendation was written shows on the card's pick and not on the
  row -- the drift the card already has on price. The row is the record.
  BEFORE THE START ONLY, from the prover of 2026-09-26: once the game has
  started the pick is corrected as of its claim's writing and a later
  activation no longer reaches it (below).
- **The fit's reach at another number.** A `rung_differs_margin` claim (86 on
  the live record on 2026-09-26; the map of 2026-09-23 counted none) is the
  frozen distribution read at the venue's line, while the category's fit was
  fitted on confidences at the model's own line; the door corrects it all
  the same. For `line_less` and `rung_matched` claims the corrected claim is
  exactly the forecast's corrected confidence restated.
- **Props merge every prop type into one correction category**
  (`category_of` is sport, market type, forecaster), so if a prop is ever
  recommended, one fit across all prop types decides its side. No prop
  recommendation exists.
- **`tasks._run_recalibrate` says "activates nothing"**, and
  `correction.refit_all` sets `active_from` when the holdout passes. From
  today an activation reaches the picks; the docstring is wrong.
- **A corrected number of exactly 0 or 1 after rounding** is refused by the
  pairing CHECK (as `fair_value`'s own CHECK refuses the raw one), and
  `record_for` raises, failing the run by name. Only a fit of a very large
  slope on an extreme claim could produce one.
- **Found in passing, not item 3 -- a combo prices a no-side leg on the yes
  side** (read in the code 2026-09-26, flagged by the map of 2026-09-23, not
  measured on a rendered card). `combos.propose` multiplies each leg's
  `fair_value` and `_proposal_card` prints it, but `fair_value` is the
  probability of the claim's proposition, and a leg recommended on the no
  side wins with one minus it; `singles_alternative` is handed the yes
  prices the same way. 82 of the 96 recommendations on the record at 04:50Z
  were no-side. Item 3 changes which number reaches these legs, not how they
  are oriented; a fix is its own ruling.

### PROVED, and three holes closed *(the prover, 2026-09-26)*

- **The planting ESCAPES on HEAD 7aedf30** (`git archive` into scratch, this
  `plant.py` over it: "left the pick on no at 3.5c with fair value 0.43
  (version None)") and is CAUGHT on this tree; `plant.py` whole is all
  caught. Twelve broken copies of the fix were each run against the
  planting and the item's tests (scratch copies of this tree; nothing else
  touched): the planting escapes on the eleven that break the pick or the
  row, and the tests fail on all twelve.
- **A FINISHED GAME'S PICK WAS RE-DERIVED BY A LATER CORRECTION** (a defect
  of the fix, fixed). `for_predictions` prices every shortlisted question
  whose game is not being played, a finished one included -- the Today
  block and the recommendation lines still show it -- and it corrected all
  of them by the correction in force NOW. Measured on a scratch world: a
  baseball pick on a game played on 9 September, on the no side as written
  and as recorded, moved to the yes side at +3.08c when a correction
  activated on the 20th, while the at-the-line sentence on the same card,
  which already read the claim's own instant once the game had started,
  kept the claim's 43%. "Re-derive nothing retroactively" forbids it, and
  the build's own words ("a started card is never corrected afterwards")
  were true of the sentence and not of the pick. NOW
  `recommend.correction_instant` is the one rule for both: the correction in
  force now before the start, the one in force when the claim was written
  once it has started. `views._claim_instant` reads it; a started card's
  pick and sentence agree and a later activation reaches neither. Before
  the start nothing changed. The reading taken: "the correction that was
  current" for a started card is the claim's, the precedent the build had
  already set for the sentence and the pregame figure; the kickoff instant
  would differ only if a correction activated between the last claim and
  the start.
- **Two broken copies passed every item-3 guard** (holes in the guard,
  closed). A pick SIZED from the raw claim while its side came from the
  corrected one: below a market's gate every size is one flat unit, so the
  flip could not show it. And a pick corrected by the STATISTICAL
  forecaster's fit whatever its forecaster: the planting had one forecaster.
  The planting now asks the pick again with the gate met and the edge
  measured ahead (a quarter of Kelly on the corrected 54% is a stake, on the
  raw 43% nothing), prices a reasoning-pass pick on another game beside the
  statistical fit (it must stay raw), and prices a finished game whose claim
  predates the activation (it must stay raw). Three tests say the same:
  `test_recommend.py::test_a_finished_games_pick_is_never_re_derived_by_a_later_correction`,
  `::test_the_size_is_computed_from_the_corrected_claim`,
  `::test_a_correction_reaches_only_its_own_forecasters_picks`; each fails
  on HEAD's package and on its broken copy. The at-the-line sentence left raw
  is caught by the build's own one-number test, not by the planting, which
  guards the pick.
- **The live write, rehearsed again on a fresh copy** (backup door, 101
  recommendations that morning): `db.init` added the two columns and the
  trigger and nothing else, every stored column's exact checksum unchanged,
  both new columns NULL on all 101; a second and third `db.init` changed
  nothing; on the migrated copy the freeze refused an edit of either column,
  the old rule still refused a rewrite of the side, the pairing CHECK
  refused a version without its number and a number without its version,
  the range CHECK refused 1, and a paired row was taken. Gate step 2's
  record and schema rows, dry-run on the gate's own migrated copy: both
  schema comparisons 0 registered, nothing new; every record check passes.
- **Found in passing, not item 3 -- above the gate, a no-side pick sizes
  nothing.** `size_for` asks `kelly_fraction(model_prob, price)` with the
  claim's YES probability and the YES price whatever the side, so a pick on
  the no side with a real edge (43% against 48.5c: +3.5c on the no side)
  gets a quarter of Kelly of the yes bet, which is zero units, recorded as
  a `fraction`. Latent while every market is under its gate (all flat
  units). The same shape as item 4's return-on-stake denominator; a fix is
  its own ruling.

## The return on what the side costs -- built 2026-09-26 *(GRIDIRON_REPAIR item 4; the operator's ruling of 2026-09-23)*

"Return-on-stake denominator: a no-side edge divides by the no-side cost.
Re-grade the three recommendations it let through as 'would not have
cleared'. Planting." (The line has moved since THE READ: the call was
`clears_the_bar(chosen.get("edge_cents"), price)` at recommend.py:412 on
01b6c97.)

### BUILT *(2026-09-26)*

- **The divisor**: `recommend._cost_of(side, price)` is the one orientation
  -- the yes price on the yes side, the rest of the dollar on the no side, a
  ValueError for anything else (the old `else:` read any other word as the
  no side). `edge_cents` asks it (bit for bit what it was, tested across the
  price range, and its `side` lost its default: the one caller names it);
  `return_on_stake(edge, price, *, side)` and `clears_the_bar(edge, price, *,
  side)` divide by it. `side` is keyword-only with NO default on both, so a
  caller that forgets it is a TypeError; `side=None` has no return (absent,
  not zero), and a price outside (0, 1) has none on either side. The bar's
  words name the side's cost to the tenth of a cent ("62.5¢"; the old words
  rounded the yes price and printed "38¢" or "50¢").
- **The call site**: `for_predictions` asks the bar with `side=edge_side`.
  With no side (the fee not cleared, the market not covered) the entry's
  `return_on_stake` is None where it was a share of the yes price; nothing
  reads it but a test. A package is bought on its yes: `combos.package_edge`
  names `side="yes"`, so every package figure is unchanged.
- **The re-grade**: `recommendation_regrades`, a companion row in the shape
  of `recommendation_voids` -- the recommendation id (terminal primary key),
  when, the verdict `would_not_have_cleared` (the only one the CHECK
  admits), what the side cost, the return on that cost and on the yes price,
  the bar as declared, a reason of ten characters or more. Triggers refuse a
  label whose numbers are not the row's own (side cost, both returns,
  recomputed from the frozen side, price and edge) or whose return is not
  under its bar; one stamped at or before its recommendation; an edit; a
  delete; and a replacing insert (INSERT OR REPLACE removes a row without a
  delete trigger, as the snapshot review found). A new table, so `db.init`
  creates it and no migration entry is needed.
- **The re-grade rule, tightened by the prover (2026-09-26).** The
  arithmetic rule checked a label's figures against the row but took the
  bar from the label itself, trusted the figures within a tolerance, and
  admitted any row. Measured on a scratch world, each of these was taken
  as "would not have cleared": a no-side pick that cleared 5.6% of its
  62.5c, labelled against an 8% bar; one that cleared 5.05% of 49.5c,
  against 6%; a yes-side pick that cleared 10% of 20c, against 50%; a
  no-side pick at 4.996% of its cost, which the bar rounds to 5.0% and
  clears, labelled 4.99%; a yes-side pick at 3.2% and a no-side one above
  50c that the yes price never passed; and rec 3's numbers written before
  the bar was declared. The rule now also requires a no-side row written on
  or after 2026-09-07T00:00:00Z (the side is required outright, because the
  rule now reads the no side's cost off the row: without it a yes-side pick
  that cleared 6.7% of 30c is taken labelled as if on the no side),
  `minimum_return` equal to the declared 0.05 (pinned in the trigger, as
  `ACTIVATION_GATE_BIRTHDAY` is; a test holds both literals equal to
  `config`), and the row's OWN returns, rounded to the bar's four places,
  at or over the bar on the yes price and under it on the no side's cost.
  `plant_a_regrade_that_is_false_or_rewritten` carries a probe for each
  condition; each probe ESCAPES with its own condition removed from a copy,
  and the implementer's rule lets through the 8% bar, the 4.996% and the
  pick above 50c among them.
  The four live labels (3, 10, 26, 56) satisfy it, rehearsed on a scratch
  copy. If the operator ever moves `MIN_RETURN_ON_STAKE`, the rule still
  names 5%, which is the bar these recommendations were let through under;
  the pin test then fails by name and says which to keep.
- **The page**: `calibration.clv_report` carries `regraded` and a
  `regraded_line` ("Would not have cleared", its N, and the words: "3
  recommendations would not have cleared the bar: each edge was measured
  against the yes price rather than against what the side taken cost, and on
  that cost they came to 3.34%, 3.68% and 4.69%, under the 5% asked for.
  They were made, so they stay on the record and are counted where they
  were"); `app.js` draws it beside the closing line under the withdrawn
  line, through `requireN`. To the hundredth of a per cent, because rec 56's
  4.97% prints as "5.0%, under the 5%" to one place.
- **The tool**: `tools/regrade_return_on_stake.py --database PATH [--write]
  [--live]`. Dry by default, through the read-only door; `--write` through
  `db.connect`, applying no schema (a record without the table is refused by
  name); refused on the record without `--live` and `--live` refused on
  anything else (`db.is_the_live_record_file`). It selects by rule
  (`recommend.let_through_by_the_yes_price`: written after the bar was
  declared, standing, cleared 5% of the yes price, and refused by
  `clears_the_bar` on its own side -- never the outcome), then refuses,
  writing nothing, unless the selection is exactly `RULED` (3, 10, 26) plus
  `LEFT_BY_RULING` (empty). `recommend.write_regrades` checks every id
  against the arithmetic again and writes in one transaction; an id already
  re-graded is counted and skipped.
- **Plantings**: `plant_a_no_side_edge_divided_by_the_yes_price` (the door
  cannot be asked blind; rec 3's numbers refused and the 50.5c mirror taken;
  through the call site on a scratch record, rec 3's numbers get no side and
  `record_for` writes nothing, the mirror is recommended on the no side --
  every check runs and every failure is named) and
  `plant_a_regrade_that_is_false_or_rewritten` (a re-grade of a pick that
  clears on its own cost, stated honestly or falsely, a false cost and an
  early stamp refused; the true one taken; an edit, a delete and a replacing
  insert refused by LAW 3). BOTH ESCAPE on 01b6c97 (`git archive` into
  scratch, this plant.py over it): the first names all five failures -- both
  doors callable blind, the bar taking no side, rec 3's numbers recommended
  on the no side at 0.0557, the mirror refused ("5.0% of the 50¢ it costs"),
  and `record_for` writing 1 -- and the second "no such table:
  recommendation_regrades". Both are CAUGHT on this tree.

### MEASURED ON THE LIVE RECORD, read-only *(2026-09-26 about 06:40Z, `db.read_the_live_record`)*

- **101 recommendations** (86 no side, 15 yes; the newest 2026-09-26T05:02:40Z);
  withdrawn 62, 63, 64 and 66. **The rule selects four**, not three: 3, 10,
  26 and **56** (MLB spread, PIT -1.5 not covered, prediction 2165, written
  2026-09-24T05:21:25Z by the logon catch-up's predict:mlb run, task run
  2325): +3.03c at a 39c yes price, 7.77% of it, 4.97% of the 61c the no side
  cost. None was written before the bar was declared; no recorded row would
  clear only on its cost (a refused pick is never written). Operator
  question 9.
- **The closes**: 3, 10 and 26 carry restated closes (item 1's restatement:
  a later near-start read of their own contract, at 0.00c); 56 closed
  unmeasured, with no later read. None of the four is in any closing-line N,
  so labelling them moves no figure.
- **Recs 3 and 10 are one bet** (mlb_824714, BOS -1.5 not covered, early and
  final pass; BOS lost 1-6, so the no side won), and rec 26 is the
  final-pass twin of rec 21 (mlb_823416, which cleared correctly at 6.45% of
  59.5c; PHI won 11-7, so the no side lost) -- the map of 2026-09-23, re-read
  today. The re-grade reads none of that.
- **The size** (question 10): every recommendation is a flat unit. Six
  categories have their hundred settled -- NCAAF spread statistical 132, MLB
  moneyline statistical 233 and reasoning 121, MLB spread statistical 175,
  MLB total statistical 182 and reasoning 110 -- and none is measured ahead
  (the three moneyline and college rows behind the market, the three others
  with nothing settled beside a price), so a fraction has never been sized
  and the no-side Kelly defect has touched nothing.

### THE REHEARSAL *(2026-09-26; scratch copies through `db.back_up_the_live_record`, never the record, never `--live`)*

- Before the schema reached the copy, the dry run read it (no table: nothing
  already re-graded), listed the four and exited 2, refusing, naming rec 56.
- `db.init` of this tree added exactly the table and its five triggers;
  nothing removed, no object's text changed, no stored row of any table
  changed (every table's row count and a hash of its rows equal); a second
  `db.init` changed nothing.
- The tool as built: dry and `--write` both refuse (exit 2), naming rec 56
  and its arithmetic, writing nothing; `--write --live` on the copy refused
  as not the record.
- Each reading, set in-process on a fresh copy (the committed constants
  untouched): (A) `LEFT_BY_RULING = (56,)` wrote 3 rows (3, 10, 26), (B)
  `RULED = (3, 10, 26, 56)` wrote 4; a second run wrote none ("already
  re-graded"); the rows read back with side costs 0.625 / 0.625 / 0.605 /
  0.61 and returns 0.0334 / 0.0368 / 0.0469 / 0.0497; every closing-line
  count and every market's N the same before and after; the page line
  carries N and passes the plain-words and advice scans; an edit and a
  delete of a written re-grade refused by LAW 3; the recommendations
  untouched.

### THE LIVE WRITE THE RULING REQUIRES *(after the release, and after question 9)*

1. **Schema, by `db.init`**: the first open of the live record by the
   released code (the release's own `/api/health` after the restart, or the
   scheduler's next task) creates `recommendation_regrades` and its five
   triggers. Nothing else changes. Confirm through the read-only door before
   the next gate, as with item 3.
2. **The labels, by the tool, once question 9 is ruled**: first
   `python tools/regrade_return_on_stake.py --database var/gridiron.db`
   (dry, read-only), then with `--write --live`. It refuses today (the rule
   selects 56 as well); the ruling's answer is one line in the tool --
   rec 56 into `RULED` (B) or into `LEFT_BY_RULING` (A) -- committed through
   the gate. It writes 3 or 4 rows into `recommendation_regrades` and
   nothing else: no recommendation is updated or deleted. Any recommendation
   the old code lets through before the release makes it refuse again, by
   name.

### READINGS TAKEN, for the operator to overrule *(2026-09-26)*

- **A re-grade is a label, not a withdrawal.** The ruling says "re-grade
  ... as 'would not have cleared'", where ruling 1 said "void" for rows out
  of the counts, and the recommendations table's own text makes the row the
  evidence of what the app said. So a re-graded row stays in every count it
  was in (none of the four is in a closing-line N today), and the page names
  it beside the closing line with its N. The other reading -- re-graded rows
  counted like withdrawn ones -- is one clause in `clv_report` and the door.
- **Selected by rule from the frozen row, checked against the named set.**
  The rule is the bar itself on the row's side, price and edge; the tool
  writes only the set the ruling names and refuses any difference (the
  precedent of `tools/void_fs5.py`).
- **Withdrawn rows are not re-graded**: a withdrawn recommendation is never
  counted and is shown as withdrawn; none of 62, 63, 64 and 66 (the four
  withdrawn) was let through anyway.
- **The reverse case writes nothing.** THE READ found one candidate refused
  only by the divisor (prediction 1774, under 7.5 on mlb_824787, 2.5c on
  the no side of 50.5c; the early-pass twin of rec 46). A recommendation
  written for it now would be stamped after its game and would not be what
  the app said (LAW 3; item 3's "re-derive nothing retroactively"). Not
  re-measured for claims since 2026-09-23.
- **`edge_cents` shares the helper** (bit for bit unchanged): the ruling's
  rule is one orientation, and two copies of it are how the bar and the
  edge came to disagree.

### OPEN, found by this item *(2026-09-26)*

- **The size of a no-side pick** (item 3's prover; question 10): measured
  latent above.
- **The payout floor reads the yes price's payout on a no-side pick.**
  `for_predictions` carries `payout = payout_multiple(price)` -- one over the
  YES price -- and `views` folds a clearing pick below `min_payout` (1.5 by
  default) on that number whatever the side, while the card's own chip turns
  it for a flipped question. A no-side pick at a 30c yes price shows 3.33
  where it pays 1.43 and is not folded; at 70c it shows 1.43, pays 3.33, and
  is. Display only (`record_for` ignores the floor); not named by the
  ruling, which is about an edge; not built.
- **A proposed combo's no-side legs** (item 3's entry above): not built.
- **The bar's own words print the return to one place**, so a pick at 4.97%
  of its cost would read "5.0% ... under the 5%" in `side_why`. Nothing
  renders `side_why`; the re-grade and the page line use two places.

## One recommendation per game and market -- built 2026-09-26 *(GRIDIRON_REPAIR item 5; the operator's ruling of 2026-09-23)*

"One recommendation per game and market, and never both sides. Recs 45 and
46 are the planting." (THE READ's map of 2026-09-23 was re-verified against
b039020 before anything was built: the insert is in `record_for`, the table
has had `recommendation_voids` and its door since, and item 3 added two
columns; nothing else it named had moved.)

### BUILT *(2026-09-26)*

- **The door**: `recommend.one_per_game_and_market(conn, entries)` decides,
  for one pass's picks that cleared the bar, which may be written. By game
  and `recommendations.market`: a game and market that already hold a
  standing recommendation (`recommend.standing_recommendations`: first by
  stamp then id, through `not_withdrawn`) get none -- "already" for a
  forecast whose own recommendation is there, "second" for any other, on
  either side; where none stands and the pass's picks take both sides,
  NEITHER is written ("both_sides"); where several take one side, the
  forecast written first is ("write") and the rest are "second". Every
  verdict that writes nothing carries its words: `STANDS_WHY` (names the
  standing recommendation, its side, price and time), `BOTH_SIDES_WHY`,
  `FIRST_IN_THE_PASS_WHY`.
- **The writer**: `record_for` asks the door once per pass, before any
  insert, and counts each pick not written by name -- `already`,
  `second_on_game_market`, `both_sides` (the old keys unchanged) -- with the
  words in `refused`. `run.run_slate` carries them on `result["recommended"]`
  as before, and `tasks._run_predict` and `_run_final_pass` now keep that in
  the run's payload, so a refused pick is said and kept with the run.
- **The schema's second lock**: `recommendation_one_per_game_and_market`,
  a BEFORE INSERT trigger on `recommendations`, refuses any row on a game
  and market that already hold a standing one -- standing as the door reads
  it: no row in `recommendation_voids`, no void on its forecast. Its words
  carry `recommend.ONE_PER_GAME_AND_MARKET` and not "UNIQUE", and
  `record_for` counts its refusal (a second writer between the look and the
  insert) as a second, by those words -- not as `already`, the forecast
  written twice, which is where a "UNIQUE" message would have been filed.
  Declared in `schema.sql` after the withdrawal table it reads; `db.init`
  makes it on the next open, over the existing pairs, reading none of them.
  No uniqueness index could be built there: the live record's pairs would
  make it fail, and `schema.sql` runs on every open.
- **Fixtures that wrote a second row on one game and market**, moved to a
  game each (nothing they assert changed): `test_priced.py`'s kill
  criterion (fifty recommendations on one total were fifty rows on one game
  and market; now fifty games), `test_recommend.py::_recorded` (the item-4
  re-grade world), two single inserts in `test_recommend.py` (another
  market of the same game), and `plant_a_regrade_that_is_false_or_rewritten`
  (seven rows, seven games; still caught, every probe as before).
- **The planting**: `plant_both_sides_of_one_total_recommended` replays recs
  45 and 46 as the record holds them -- game `mlb_824787`, both forecasts,
  quote `KXMLBTOTAL-26SEP211835TORBAL-8` at 48/49c, both claims (54.9% and
  43% on the over), both ranks (places 15 and 11, gates 116 and 63) -- and
  checks the pass as it ran (neither written, both counted, "both sides" in
  words), the replay in order (45 recorded, 46's forecast refused and
  counted, 45's own forecast adds nothing) and the schema (46 as written,
  and a second over, refused in the ruling's words). On b039020 (`git
  archive`, before the fix) it ESCAPES with all six named; on the tree it
  is CAUGHT.
- **Words**: the Settings "Minimum payout" line said the closing line "is
  still measured on all of them", which stopped being true of a second pick
  on a game already recommended; it now says "a folded pick is recorded
  exactly as a card is" (rendered at 1100px and 390px through the suite's
  signed-in scratch world: no page scroll, no console error). The
  `_today_block` docstring says the same.

### MEASURED ON THE LIVE RECORD, read-only *(2026-09-26 about 08:20Z, `db.read_the_live_record`)*

- 101 recommendations (ids 1-101, newest 05:02:40Z on 26 September); 4
  withdrawn (62, 63, 64, 66). No forecast holds two recommendations.
- **18 game-markets hold two standing recommendations each, 36 rows** (22
  counting withdrawn rows; the other four -- NFL spreads 62/73, 63/75, 64/76,
  66/78 -- have a withdrawn first and one standing, which the rule allows):
  mlb_823414 spread 1, 9; mlb_824714 spread 3, 10; mlb_824875 total 4, 12;
  mlb_823738 spread 5, 13; mlb_824957 spread 6, 14; mlb_824791 spread 20, 25;
  mlb_823416 spread 21, 26; mlb_824064 total 23, 28; mlb_824550 spread 32,
  34; mlb_824787 spread 41, 44; mlb_823169 spread 42, 48; mlb_823169 total
  43, 49; **mlb_824787 total 45 (yes), 46 (no)**; mlb_823411 spread 60, 79;
  mlb_824707 spread 61, 80; mlb_822681 spread 84, 93; mlb_824058 spread 86,
  94; mlb_823652 spread 87, 95. Seventeen are one forecaster, early then
  final, the same side; 45 and 46 are two forecasters in one pass, opposite
  sides, the same second (the id breaks the tie). THE READ counted thirteen;
  the scheduler wrote five more since, and until the release it can write
  more the same way -- each stands as written.
- **In the closing line**: MLB spread n = 9 measured closes, three of them
  (93, 94, 95) the second row of their game and market; MLB total n = 0;
  45 and 46 are restated and unmeasured. The second rows are 9, 10, 12, 13,
  14, 25, 26, 28, 34, 44, 46, 48, 49, 79, 80, 93, 94 and 95.

### THE LIVE WRITE THE RULING REQUIRES *(after the release; no tool)*

**No row is written, updated or deleted.** The one change that reaches the
record is the trigger, made by `db.init` on the first open by the released
code (the server's restart or the scheduler's next task), as item 3's
columns and item 4's table were. Confirm through the read-only door before
the next gate: `sqlite_master` holds `recommendation_one_per_game_and_market`
and the 36 rows are as measured.

### READINGS TAKEN, for the operator to overrule *(2026-09-26)*

- **Both sides in one pass: neither.** The ruling says "never both sides"
  and names no survivor; the app's two forecasters cancelling is not an
  opinion. The other reading -- the first written stands, which would keep
  45 -- is one branch in the door.
- **A standing recommendation decides first**: a later pass that takes both
  sides of a game and market already recommended adds nothing and is
  counted as a second, not as both sides.
- **One side, several forecasts in one pass: the forecast written first**
  (its stamp, then its id) -- the statistical row of a question, which is
  written before the reasoning row.
- **"Market" is `recommendations.market`**, whatever the rung and, for a
  prop, whatever the player: the literal words and the stricter reading.
  No prop is priced today (every claim on the record is a game market), so
  nothing turns on it yet; a priced prop market would hold one
  recommendation per prop type per game.
- **A withdrawn recommendation does not stand**, by ruling 1's door.
- **Nothing written before is touched, relabelled or re-counted** (the
  ruling names no row): question 12.
- **The page is not changed**: question 11.

### OPEN, found by this item *(2026-09-26)*

- **The page can show a pick the record refused** (question 11): after the
  final pass the final card's pick shows at its new price while the record
  keeps the morning's; if the two forecasters split in one pass each
  forecaster's page shows its own side while the record holds neither.
- **No withdrawal**: a morning recommendation stands even when the final
  pass no longer clears it, or clears the other side; the morning price is
  what the closing line measures. A rule that withdraws one would be a new
  feature, not in the ruling.
- **The taken rail's edge is keyed by forecast** (`views.taken_today`): a
  pick marked on a final card whose recommendation was refused shows "no
  price recorded at the time" rather than the standing recommendation's
  edge.
- **The trigger restates `not_withdrawn` in SQL** (no row in
  `recommendation_voids`, no void on its forecast). A third way to withdraw
  a recommendation would have to be added to both; a test holds them to the
  same answer on the two that exist.
- **Found in passing, not this item's: a browser test that fails about two
  runs in five.** `test_smoke.py::test_every_tap_target_on_the_slate_is_big_enough`
  measured a `BUTTON.expand` at 43.99951171875px against its 44px floor on
  the first full suite run of this item; rerun alone it failed 1 of 3 on the
  tree and 2 of 5 on b039020 (before the fix, `git archive`), the same
  height each time -- a sub-pixel height, not a change. It can turn a gate
  red by itself; not touched here.

### THE REHEARSAL *(2026-09-26 about 09:20Z; a scratch copy through `db.back_up_the_live_record`, never the record)*

A 1.06 GB copy of the live record, opened with `db.open_db` under this tree:
the trigger was made (absent before), all 101 recommendations byte for byte
as before, the 18 standing pairs (36 rows) intact; `schema_diff.compare`
against a fresh build of the tree found 0 differences in behaviour (235
objects each; ten tables differ only in what the ruling normalises, the
new trigger not among them: its text is the tree's). On the migrated copy, a
third row on 45 and 46's total and a second on a game and market with one
standing row (`mlb_823083` spread, rec 101) were both refused in the
ruling's words.

### PROVED, and one gap closed *(the prover, 2026-09-26)*

- **The planting ESCAPES on b039020** (`git archive` into scratch, this
  `plant.py`'s planting run over it: all six faults named) and is CAUGHT
  on this tree. **Each lock alone is proved by it**: with the door
  neutralised in a scratch copy (every pick "write"), the schema still
  refuses the second row, so the pass writes ONE side, counts the refusal
  as a second and never says "both sides" -- ESCAPED; with the trigger
  neutralised, rec 46 as written and a second over go straight into the
  table -- ESCAPED. The escape's first words said "both sides ... two fees"
  of the one row the neutralised door leaves; they now fit the rows found.
- **The eight new tests fail on b039020** (the new `test_recommend.py` run
  over the unfixed tree) and pass here.
- **Other ways in, tried on scratch databases, all refused on this tree and
  all accepted on b039020**: two rows in one multi-row VALUES, INSERT OR
  IGNORE, INSERT OR REPLACE on the other side, INSERT ... SELECT of the
  stored row turned over, and an UPSERT. An UPDATE of the side or of the
  game is `recommendations_no_update`'s (LAW 3), on both.
- **A RUN FAILED FOR WANT OF A MODEL KEPT NO ACCOUNT** (a gap in the build,
  closed). `run.MarketNotTrained` is raised after the markets with a model
  are recorded, and `run_task`'s failure payload held the traceback alone,
  so what such a run recommended and refused, and why, was not kept -- while
  the build said the predict and final tasks keep it. `run_task` now keeps
  `exc.result["recommended"]` beside the traceback, inside a guard that can
  never stop the failure being recorded.
  `test_recommend.py::test_a_run_failed_for_want_of_a_model_keeps_what_it_recommended`
  fails on the tree before the fix (a scratch copy: no `recommended` in the
  stored payload) and passes after. The live record has no such failure
  since 19 September (measured read-only), so nothing was lost there.
- **The gate's step 2, dry-run on a fresh copy** (the record rows and the
  two schema comparisons only, through `verify`'s own helpers; the
  credential scan handed an empty scratch settings file): every row passes.
  Both comparisons: 0 differences in behaviour, 0 registered, and the same
  ten tables differing only cosmetically in each (234 objects against the
  release, 235 against this tree: the trigger, its text on the migrated
  copy byte for byte the fresh build's).
- **Found in passing, not this item's: a recommendation can be REPLACED.**
  `INSERT OR REPLACE` naming a stored recommendation's id removes it and
  writes another in its place -- SQLite fires no delete trigger for a
  replacement unless recursive triggers are on, so `recommendations_no_delete`
  never sees it (measured on scratch databases, on this tree and on
  b039020). The snapshot table had the same hole until
  `market_snapshots_never_replaced`. It cannot put both sides on one game
  and market -- the new rule refuses a replacement onto a game and market
  holding one -- but it erases what was said (LAW 3). No writer does it;
  not built here, because no ruling names it.

## At the venue's line, one bet per game per forecaster -- built 2026-09-26 *(GRIDIRON_REPAIR item 6; the operator's ruling of 2026-09-23)*

"The at-the-line scorecard never pools forecasters or duplicates;
per-forecaster, per-distinct-bet counts only, LAW 4 and LAW 6. Re-state every
gate distance on the corrected counts." (THE READ's map of 2026-09-23 was
re-verified against 5499520 before anything was built: since it was drawn,
item 1 had put `at_the_line.standing_claim_clause` -- one claim per forecast,
the last before the start -- into the outlook, the card count and the venue
drift, and ruling 1 had put voids into it; nothing else it named had moved,
and none of it asked the forecaster.)

### BUILT *(2026-09-26)*

- **The door**: `market.at_the_line.standing_claims(conn, *, sport, market,
  predictor, event_tier=None)`. The forecaster is required and refused by
  name unless it is one of the two (`at_the_line.PooledCount`, "never
  pooled"); a sport that splits below the market must name one declared
  tier, and one that does not may name none (LAW 6). It keeps ONE claim per
  game, market and side (the side is fixed by the market) per forecaster: the
  last written before the start, the id breaking a tie, however many passes,
  rungs or looks wrote one. A voided forecast's claim is never a candidate,
  so a withdrawal takes back that forecast and not the bet. Every row carries
  its forecaster, season and week. `standing_claim_clause` is folded into it
  (its history is in the door's docstring); `at_the_line.settled`,
  `bet_of` and `count_of_bets` are the one predicate and the one key the
  counts share.
- **Every count reads it**: the curve (`calibration.at_the_line_curve`, one
  per market, tier and forecaster, asking the door ONCE); its gate line and
  its outlook (`horizon.at_the_line_outlook` is handed the curve's own bets:
  resolved is the curve's n, the pace is this season's bets over the slates
  they were written on); the edge (the statistical model's, in the headline
  market); the hypothetical ledger (`paper.ledger`, one per curve); the
  coverage share (`at_the_line.coverage`, per forecaster, over the standing
  forecast of each question, read if that forecaster's bet on the game
  stands); the count beside a pick card (`views._at_the_line`, its own
  forecaster's bets in its market, and tier); and the venue's drift pair
  (`drift.venue_pairs` / `venue_report`, per forecaster; `views.drift_report`
  lost `venue_n`, a sum of both). The scorecard's total `n` (a sum of both
  forecasters' curves, never rendered) is gone.
- **The guard**: `calibration.assert_no_pooled_claims`, inside
  `at_the_line_scorecard` (so the API answers 500 rather than serve a pool,
  and the gate's build of every sport on its copy of the record runs it).
  It first runs `assert_no_merged_categories` on the at-the-line payload --
  nothing did until today; on 23 September it raised "merges the
  statistical and LLM forecasters" on the live payload -- then refuses by
  name: a count of more claims than distinct bets (`distinct_bets`, counted
  off the items beside the door, so a door that let a bet in twice is seen);
  claims of another forecaster than the one named (`forecasters_counted`);
  an outlook, or a gate line, stating another count than the curve's ("two
  counts of one record"); a ledger, edge or coverage line naming no
  forecaster or tier; and a total.
- **Words**: `language.at_the_line_category_label` ("point spread at the
  venue's line, reasoning pass"; a UFC row names its card), and the ledger
  and coverage lines name the forecaster (and the tier) after the market.
  The pace line with nothing written now says "no claim from this forecaster
  has been written in this market yet": the old words, "no claim has been
  written in this market", would have stood under the reasoning pass's MLB
  spread row one line below a statistical row with 88.
- **The plantings**: `plant_an_at_the_line_curve_pooling_two_forecasters`
  (THE READ's payload: both forecasters in one curve, both under one
  forecaster's name, one forecaster's two passes counted twice, an outlook of
  128 beside a curve of 80, and a total -- each refused by name, the honest
  pair passing) and `plant_an_at_the_line_game_counted_twice` (a scratch
  world, every row through the triggers: one MLB game forecast by the morning
  and final pass and by both forecasters at the moneyline, and at two rungs
  at the spread; the door counts one bet per forecaster, the card the same;
  the door as it stood, and the same asking the forecaster, swapped back in,
  are refused by the Record page's own builder). **Both ESCAPE on 5499520**
  (`git archive`, scratch): the unfixed scorecard runs no check that sees
  them, and it builds the planted world as moneyline 3, spread 2, ledger 3
  and a card saying 3 -- one game.
- **Tests** (`test_at_the_line.py`): one bet per forecaster per game through
  the curve, the ledger, the edge, the card, the coverage and the drift pair;
  the outlook and the gate line count the curve's bets; a withdrawn forecast
  takes back its claim and not the bet; every pooled shape refused by name,
  the door refusing a pooled forecaster or tier, and UFC in six curves. All
  four fail on 5499520. `test_paper.py`'s ledger keyed by market alone (the
  second forecaster's row silently replaced the first) is keyed by market and
  forecaster.

### MEASURED ON THE LIVE RECORD, read-only *(2026-09-26 about 10:50Z, `db.read_the_live_record`; newest claim 05:02:39Z)*

Every gate distance the app states at the venue's line, as the shipped code
(5499520) states it and as this tree does. "PRINTED": the figure itself is on
the page. The projections (~) move with every slate; the orchestrator
re-reads them at release.

| sport | figure | before (pooled) | after (per forecaster, per bet) |
|---|---|---|---|
| MLB | spread curve | 130, past the 100 (outlook 130, ~157) | statistical 88 of 100, 12 more (~107); reasoning 0 (no claim written) |
| MLB | total curve | 67 of 100 (~81, cannot clear) | statistical 24 of 100, 76 more (~29, cannot clear); reasoning 24 (~29) |
| MLB | moneyline curve | **283, past the 100** (~344) | statistical 92 of 100, 8 more (~112); reasoning 92 of 100, 8 more (~112) |
| MLB | spread ledger | 88 of 100 | statistical 59; reasoning 0 |
| MLB | total ledger | 35 of 100 | statistical 10; reasoning 16 |
| MLB | moneyline ledger | **176, PRINTED "-0.47 units, or -3.98 after the venue's fee"** | statistical 49 of 100; reasoning 66 of 100 -- **the figure is withdrawn** |
| MLB | edge (spread) | n 130, 2 of 100 disagreements | statistical n 88, 1 of 100 |
| MLB | pick-card count (slate payload; painted nowhere, below) | moneyline 283 "past the 100", spread 130 "past the 100", total 67 | moneyline 92, spread 88, total 24 (each forecaster's) |
| MLB | venue drift, gate 50 (payload only) | moneyline 132 and spread 69, past the 50; total 21 | moneyline statistical 38, reasoning **55 (past the 50)**; spread 49 and 0; total 6 and 10 |
| MLB | coverage | spread 140 of 286; total 71 of 452; moneyline 315 of 531 | spread statistical 95 of 188; total 25 of 195 and 25 of 123; moneyline 102 of 246 and 102 of 134 |
| NFL | curves | spread 4 (~132); total 0 (~48); moneyline 2 (~754) | spread statistical 2 (~114), reasoning 0; total 0 and 0 (~16 each, cannot clear); moneyline 1 and 1 (~257 each) |
| NFL | ledgers | spread 1; total 0; moneyline 2 | spread 1 and 0; total 0 and 0; moneyline 1 and 1 |
| NFL | edge (spread) | n 4, 1 of 100 | statistical n 2, 1 of 100 |
| NFL | pick-card count | moneyline 2, spread 4, total 0 | moneyline 1, spread 2, total 0 |
| NFL | venue drift | moneyline 30, spread 12, total 0 | moneyline 11 and 8; spread 12 and 0; total 0 and 0 |
| NFL | coverage | spread 29 of 99; total 3 of 68; moneyline 63 of 79 | spread 14 of 42 and 0 of 13; total 1 of 18 and 1 of 17; moneyline 16 of 32 and 16 of 16 |
| NCAAF | curves | spread 3 (~183); total 0; moneyline 6 (~366) | spread statistical 3 (~183), reasoning 0; total 0 and 0; moneyline 3 and 3 (~183 each) |
| NCAAF | ledgers | spread 3; moneyline 4 | spread 3 and 0; moneyline 1 and 3 |
| NCAAF | pick-card count | moneyline 6, spread 3 | moneyline 3, spread 3 |
| NCAAF | venue drift | moneyline 2, spread 1 | moneyline 1 and 1; spread 1 and 0 |
| NCAAF | coverage | spread 4 of 147; total 0 of 157; moneyline 8 of 150 | spread 4 of 133 and 0 of 6; total 0 of 90 and 0 of 13; moneyline 4 of 88 and 4 of 6 |
| NBA | every figure | 0 | 0, per forecaster |
| UFC | every figure | 0 (one moneyline curve, all tiers) | 0, in six curves: three cards by two forecasters |

Nothing at the venue's line is past its hundred for any forecaster in any
sport. Three things the page showed are withdrawn by LAW 4 working: the MLB
moneyline and spread curves' "past the 100" and the PRINTED moneyline ledger
(and, in the slate payload, every MLB moneyline and spread card's "past the
100"). The nearest gates are MLB moneyline, 8 more
for each forecaster, and MLB spread, 12 more for the statistical model, both
projected to reach the hundred by 27 September at this season's pace -- a
projection, and the season's last slates. The one count now past a gate is a
venue drift pair (MLB moneyline, reasoning pass, 55 of 50), in the payload
and on no page. No forecaster's claims on one game carry two venue lines
(measured: 0), so a bet keyed by line as well would count the same today.

### RENDERED *(2026-09-26; this tree and 5499520 served against one scratch copy of the record, signed in with the browser suite's test token)*

The Record page's "At the venue's line" section for MLB, at 1100px and
390px, read: six curves, each naming its forecaster ("point spread at the
venue's line, statistical" / "..., reasoning pass"), the gate line and the
outlook in each saying the same count (88, 0, 24, 24, 92, 92); six ledger
lines, none printing a figure; five coverage lines, each naming its
forecaster. On 5499520 the same copy rendered "283 settled comparisons,
past the 100 this record needs" and the moneyline ledger's units. No
horizontal page scroll, no console error, at either width. The row where
the reasoning pass has no claim says "no claim from this forecaster has been
written in this market yet". **The count beside a pick card is not on
screen**: `views._at_the_line` puts it in the slate payload, and the only
code that paints it, `app.js` `buildCardBody`, has no caller -- 0 of 50 MLB
card faces show it, before and after (found in passing; not changed).

### THE LIVE WRITE THE RULING REQUIRES *(none)*

**No row is written, updated or deleted, and the schema does not change.**
Item 6 is read-side: the counts, the payload, the guard and the words. The
pooled figures were never stored (they were computed on every request), so
there is nothing to void or relabel. Rehearsed on a scratch copy through
`db.back_up_the_live_record`: `db.init` under this tree changed no schema
object (235 before and after, byte for byte) and no claim (1,293); the
migrated copy against a fresh build of this tree: 0 differences in
behaviour (ten tables cosmetic, as at item 5); and the at-the-line
scorecard of every sport built on it with the guard passing. The Record
page's payload for MLB builds in 0.34 s against 0.29 s before (best of
three, read-only on the record).

### READINGS TAKEN, for the operator to overrule *(2026-09-26)*

- **A distinct bet is a game and market** (with its fixed side), per
  forecaster -- THE READ's "distinct bets" (game-market pairs) and item 5's
  key. The other reading, a game, market and venue LINE, would count a later
  look at another rung as a second bet; it counts the same on the record
  today (no forecaster's claims on one game carry two lines).
- **The claim that stands for a bet is the last written before the start**
  -- the standing-claim rule, which already chose one forecast's last look --
  from whichever of that forecaster's forecasts wrote it, so a question whose
  final pass was never read at the venue still holds its morning claim
  (none today). The other reading, only the standing forecast's claim, would
  drop such a bet from the count.
- **UFC splits by card at the line**, as its blind record does (LAW 6 one
  level down): six curves, six ledgers, and the edge on the numbered card.
  Nothing moves: UFC has no claim.
- ~~**Coverage counts forecasts, not bets** ("forecasts could be read at the
  venue's line"): the standing forecast of each question, per forecaster, so
  two standing rungs of one game are two forecasts read by one bet.~~
  **REPLACED by the prover, 2026-09-26** (below): the ruling allows
  "per-distinct-bet counts only" on this scorecard, and the coverage line is
  on it, so it counts one bet per game the forecaster forecast. Kept struck
  through, not deleted, so the reading and its reversal can both be read.
- **The venue's drift pair is counted per forecaster and per bet**: it is
  read off the claims, and states a gate (fifty).
- **The learning panel states no at-the-line count.** Its two figures are the
  correction's settled count (`calibration.resolved`, statistical, one per
  question) and the media line's drift (below); THE READ's "174, past the
  100" was the at-the-line section of the Record page.
- **Recommendations are not counted here** (item 5; question 12).

### OPEN, found by this item *(2026-09-26)* -- the first, second and fourth are `docs/REPAIR_STATE.md` question 14

- **The priced forecaster's record pools the same way, on the same page.**
  `calibration.priced_scorecard` counts one priced row per blind forecast --
  both blind forecasters, both passes -- and words its gate with
  `at_the_line_gate_line`: MLB moneyline shows "261 settled comparisons, past
  the 100 this record needs", which are 139 rows on the statistical model's
  forecasts (96 standing questions, 96 games) and 122 on the reasoning
  pass's (84 standing). Neither is past the hundred. Not the at-the-line
  scorecard; not built here.
- **The learning panel's drift line counts superseded passes.**
  `drift.report` (the media line, statistical model only, gate fifty) pairs
  every forecast with both looks: MLB moneyline "75 games", past the fifty,
  is 58 questions, 48 of them standing rows. Not at the venue's line; not
  built here.
- **Nothing scans for a claim count written round the door**, as
  `audit.check_every_recommendation_reader_uses_the_door` does for
  recommendations: the card's count reads the door, and a planting proves
  the door by the page it builds, but a new `COUNT(*) FROM
  at_the_line_claims` elsewhere would not fail a scan.
- **The blind record's outlooks count every row.** `horizon.market_outlook`
  (the line beside each statistical curve, through `_written_so_far`) counts
  every forecast of the market that is not voided -- a question's morning
  and final pass twice -- and for UFC the whole market beside each tier's
  curve: MLB moneyline "330 of 100" beside a curve of 233; spread and total
  "272 of 100" beside 175 and 182; UFC moneyline "62 of 100" beside a
  Numbered-card curve of 0 (Fight Night 27, Contender Series 10). The same
  "two counts of one record" the at-the-line outlook was, in the blind
  record; not item 6's scorecard, not built here.

### PROVED, and one count fixed *(the prover, 2026-09-26)*

- **Both plantings ESCAPE on 5499520 and are CAUGHT here** (`git archive`
  of HEAD into the scratchpad; each planting's own code run against it, with
  the checks the unfixed `at_the_line_scorecard` ran and the gate's
  at-the-line scan standing in for the guard it lacks). Independently built,
  one MLB game forecast by both passes of both forecasters and read at two
  looks: the unfixed page says moneyline 4, spread 2, a total of 6 and a
  card of 4; this tree says 1 for each forecaster. With the guard made a
  no-op in the process, both plantings report NOT CAUGHT, so they prove the
  guard and not the world.
- **FOUND AND FIXED: the coverage line counted a bet more than once.** The
  builder's coverage counted each forecaster's standing QUESTIONS, so a game
  asked at two rungs was two forecasts, both "read" by its one bet: on the
  live record (read-only, 2026-09-26) NCAAF point spread, statistical, said
  "4 of 133 forecasts" for 88 bets (45 games asked at two rungs), NFL point
  spread "14 of 42" for 29, MLB total "25 of 195" and "25 of 123" for 188 and
  119; the planted game said "2 of 2 forecasts" beside a curve of 1. The
  ruling allows "per-distinct-bet counts only" on the at-the-line scorecard,
  and the coverage line is on it. Now `at_the_line.coverage` counts one bet
  per game the forecaster forecast (the standing forecasts grouped by game;
  a bet not read is put down to a missing distribution only when none of its
  forecasts carried one), carries `distinct_bets` and `forecasts` beside
  `n`, and the line says games: "point spread, statistical: the venue's line
  could be read for 4 of 88 games it forecast (5%)".
  `assert_no_pooled_claims` refuses a coverage line whose `n` is not its
  distinct bets, or that reads more bets than it counts. Planted: two more
  shapes in `plant_an_at_the_line_curve_pooling_two_forecasters`, and the
  coverage lines in `plant_an_at_the_line_game_counted_twice`'s world -- both
  ESCAPE on 5499520 and on the builder's tree before this fix, and are
  CAUGHT here. The builder's test that asserted "2 of 2" asserts one bet.
- **The coverage lines on the live record after the fix** (read-only,
  2026-09-26; the forecasts each counts in brackets where they differ): NFL
  spread 14 of 29 (42), 0 of 13; total 1 of 17 (18), 1 of 17; moneyline 16
  of 32, 16 of 16. MLB spread 95 of 188; total 25 of 188 (195), 25 of 119
  (123); moneyline 102 of 246, 102 of 134. NCAAF spread 4 of 88 (133), 0 of
  6; total 0 of 90, 0 of 13; moneyline 4 of 88, 4 of 6. UFC Fight Night 0 of
  41 and 0 of 41, Contender Series 0 of 10 and 0 of 10. NBA none: all 47 of
  its forecasts are withdrawn. No coverage line states a gate, so no gate
  distance moves; the curves, ledgers, edges and cards above are unchanged.
- **FOUND AND FIXED, BY THE RENDER: the pace line denied the claims it
  counted.** The builder made the outlook's count the curve's (every
  season's settled bets) and kept the pace this season's, so a forecaster
  whose claims were all written in an earlier season read "2 of 100 · no
  claim from this forecaster has been written in this market yet" -- a
  count and its denial in one sentence. Every curve on the browser test
  world's Record page said it (its games are last season's); on the live
  record every claim is this season's, so it would first have shown when a
  season turned over. The line now says "... has been written in this
  market this season" when a claim exists from an earlier one, and "yet"
  only when none ever has (`language.at_the_line_pace_line(...,
  written_before=)`, from `horizon.at_the_line_outlook`).
  `test_at_the_line.py::test_the_pace_line_never_denies_the_claims_it_counts`
  fails on 5499520 and on the builder's tree, and passes here.
- **OPEN, not built: the tier is checked by label only.** A UFC curve names
  its card, and the guard refuses one that names none, but its claims do not
  carry their card, so a door that stopped filtering by tier would put every
  card's bouts in each card's curve and pass -- as the blind record's tier
  guard is also label-only (`assert_no_merged_categories`). UFC has no claim
  at the line today. Carrying the tier on each claim and refusing a curve
  whose claims span cards, as `forecasters_counted` does for forecasters,
  would close it.

## The jobs -- built 2026-09-26 *(GRIDIRON_REPAIR item 7; the operator's ruling of 2026-09-23)*

"Jobs: SlateAlreadyAnswered is a noop, not a failure; the run_task closing
UPDATE moves inside the try and a hung "running" row older than its task's
silent_after_hours is marked abandoned; every Gridiron-* task gains
WakeToRun. Report awake fraction since the fix in each close-out." (The map
of 2026-09-23 was re-verified against f58b3a1 first: since it was drawn,
item 2 had made a market the run cannot answer keep its slate open, so a
refusal now means every market the run asks is answered -- the ordering the
map required before a refusal could become a noop.)

### MEASURED FIRST, read-only *(2026-09-26 about 21:37Z, `db.read_the_live_record`)*

- `task_runs`: 4,498 rows. failed 114, of which `SlateAlreadyAnswered` 90
  and catch-up sums 18; since 21 September, 58 refusals (predict:cfb 15,
  predict:mlb 17, predict:nfl 9, predict:ufc 17) and 12 catch-up sums.
  Catch-up: 18 failed, 4 running, never ok or noop; every one of the 18 was
  failed by refusing members and nothing else. Failure notices: 95 sent, 1
  failed; the last three bodies "Predict baseball missed a slate (and 3
  more)".
- 13 rows 'running', none with an ending: 969, 1742, 1847, 2057, 3358
  (final:cfb), 1983, 1986, 1989 (refresh), 1981 (predict:nfl), 1978, 1982,
  1985, 1988 (catch-up). Against each task's own `silent_after_hours`, 7
  were past it: 969, 1742, 1847, 1983, 1986, 1989, 2057.
- 3358 is new since the map: `final:cfb` begun 2026-09-25T19:24:12Z inside
  two concurrent refreshes (3346, 3353), as every final:cfb orphan was.
  final:cfb has ended ok 4 times, noop 6 and never 5.

### BUILT *(2026-09-26)*

- **A refused rerun is a noop**: `tasks._run_predict` catches exactly
  `run.SlateAlreadyAnswered` and records 'noop' -- "the NFL slate of Week 3,
  2026 already has 35 forecasts in every market this run asks. A slate is
  answered once, so this rerun was refused and nothing was written." -- with
  `{"refused_slate", "already_written"}` as its payload (no "week":
  `views._below_floor` reads that key to find the run that wrote a slate).
  `RuntimeError` (which it subclasses) and `run.MarketNotTrained` (its
  sibling) stay failures. `run.run_slate` still raises it (the CLI, the
  backtest and two tests rely on the raise). Catch-up's own sum needed no
  change.
- **The closing write is inside the try**: kept as an inline literal (the
  order check reads constants), now `... WHERE id = ? AND result =
  'running'`. The dispatch's outcome is held once it returns; a closing
  write that raises records THAT outcome with the error beside it
  (`closing_write`), retried once with `json.dumps(..., default=str)`; if the
  retry fails too, nothing is raised and the row is left for the sweep. A
  task that raised is recorded failed as before, notice and all.
  `audit.task_run_order_faults` now also refuses a write ending the row, or a
  commit after the dispatch, outside a `try` body (it names f58b3a1's lines
  283 and 288).
- **A hung run is marked abandoned**: `tasks.abandon_hung_runs(conn, *,
  by_task, by_run, now)`, called by every `run_task` just after its own row
  is committed, in its own `try` (a failing sweep rolls back only itself and
  never stops the run). Per 'running' row whose task is declared and whose
  age from `started_utc` exceeds that task's `silent_after_hours`: `result`
  'abandoned', `detail` from `language.abandoned_run_line` (lower case first:
  a leading "Word:" is cut on the panel as a class name), `payload_json`
  `{abandoned_utc, silent_after_hours, marked_by_task, marked_by_run}`,
  `finished_utc` left empty. `tasks.status` treats an abandoned latest row
  as unfinished, like a hung running one.
- **The ledger admits it**: `schema.sql`'s CHECK gains 'abandoned' (and the
  glossary two lines); `db.widen_task_run_results` gates on "'abandoned'"
  and rebuilds through `gridiron.rebuild` in ONE `BEGIN IMMEDIATE` (it used to
  copy and swap in two transactions, which a concurrent `open_db` could
  split, losing a row written between them).
- **Every task wakes the machine**: `-WakeToRun` in `New-GridironTask`'s
  settings (17 tasks) and Serve's own (1); PowerShell's own parser reads both
  settings sets back with it (parse only, nothing run). `audit.
  installer_wake_faults` / `check_every_task_wakes_to_run`, in gate step 2,
  name by task any the installer defines without it, read from code (a
  comment neither satisfies nor trips it), keyed on `$TaskNames`, and name a
  `schtasks`, `Set-ScheduledTask` or `New-ScheduledTask` it cannot read.
- **The awake fraction**: `tools/awake.py --since <UTC> [--until <UTC>]
  [--json]`, read-only, described in its docstring. On the log today:
  12-23 September (the map's window) awake 6.75 of 286.38 hours (2.4%),
  asleep 30.32, off 249.31 -- the map's own figures to the second place;
  since 2026-09-21T06:23:11Z to 22:00Z on 26 September, 60.60 of 135.61
  hours (44.7%), asleep 30.32, off 44.69; no wake by a timer, ever.
- **Plantings** (each ESCAPES on f58b3a1, `git archive`, scratch, notices
  off; each CAUGHT here): `plant_a_refusal_recorded_as_a_failure` (recorded
  'failed' on the head; the control -- a plain RuntimeError -- must stay
  failed), `plant_a_closing_write_that_escapes_the_try` (OperationalError
  raised out of run_task on the head, and the head's order check passes the
  close outside the try), `plant_a_hung_run_left_running` (the 13-hour
  refresh stays running on the head), `plant_a_task_definition_without_
  wake_to_run` (the head defines all 18 without it, and nothing reads it).
- **Tests**: the item 7 block of `test_scheduler.py` (13, every one failing
  on f58b3a1) and `test_awake.py` (the tool absent there).

### READINGS TAKEN *(each reversible in one line)*

- **"Older than its task's silent_after_hours" is literal**: each TaskSpec's
  own figure. `catch-up` and `live` declare 8,760 hours (a year), so the four
  hung catch-up rows (1978, 1982, 1985, 1988) stay 'running' until
  2027-09-23; 1981 (predict:nfl, 216 h) goes after 2026-10-02T06:36Z and 3358
  (final:cfb, 36 h) after 2026-09-27T07:24Z. The figures are not named by
  the ruling and were not changed. (Reversal, if ruled: a per-task ceiling
  in `abandon_hung_runs`.)
- **'abandoned' is a result value, written once on the row that has no
  ending** -- the lawful form: `task_runs` refuses a delete and permits the
  one write that ends a row, which `run_task` makes itself; nothing is
  deleted or rewritten, `finished_utc` stays empty, and both writes carry
  `AND result = 'running'`, so the mark is terminal. Consequence: a run that
  outlives its task's silence (impossible under the installer's two-hour
  limit; possible by hand past six hours) finds its row marked and its own
  ending is not written; `run_task` still returns it. (Reversal: drop the
  clause from the two closing writes.)
- **A closing write that fails after the task finished records what the
  task did**, not 'failed': the ledger's own words are "failed: it raised",
  and final:cfb had written its forecasts. No failure notice is sent for it.
  (Reversal: set `result, detail = "failed", ...` in that branch.)
- **The retry does not roll back first.** Under a held lock in WAL mode the
  same transaction may fail again at once; a rollback would give it a fresh
  start but could drop a task's own uncommitted writes on a journal-mode
  database. The row then waits for the sweep (36 hours for final:cfb); the
  Health panel says it never recorded an ending after two.
- **WakeToRun on every task, Live and Serve included**: the ruling says
  every. Live fires every 90 seconds and Serve every 2 minutes, so a
  sleeping machine will be woken within two minutes of going to sleep --
  whether it then stays awake or cycles in and out of sleep (each sleep here
  writes about 1.3-1.5 GB of hibernation file) depends on a hidden
  unattended-sleep timeout nobody read. Recorded, not decided.
- **The registered tasks are not touched here, and the installer is not
  run**: re-running it is not neutral on this machine (it resets Live's and
  NearStart's hand-set limits and Refresh's and Resolve's phase). The
  orchestrator applies WakeToRun in place after the release
  (`$t = Get-ScheduledTask -TaskName $n; $t.Settings.WakeToRun = $true;
  Set-ScheduledTask -TaskName $n -Settings $t.Settings`, the
  `scheduler.apply_time` precedent) and reads back 18 of 18; that instant is
  "the fix" the close-outs measure from.

### THE LIVE RECORD AFTER THE RELEASE *(no tool to run by hand)*

1. The first `open_db` of the record under the release (the Serve restart,
   or any task or request) rebuilds `task_runs` through the rebuild door to
   admit 'abandoned': rehearsed on a copy made through the backup door at
   22:02Z on 26 September -- 4,516 rows before and after, every column's
   checksum equal, the index and the no-delete trigger recreated, no
   difference from this tree's definition, the whole copy against a fresh
   build passing the gate's "tree" comparison, 0.5 seconds, and a second open
   changing nothing.
2. The first `run_task` after that (Live, within 90 seconds) marks
   abandoned the rows then past their silence: 7 in the rehearsal (969,
   1742, 1847, 1983, 1986, 1989, 2057), nothing else touched, the Health
   panel plain words on the swept copy.
3. Nothing retroactive: the 114 failed rows (90 refusals, 18 catch-up sums)
   stand, no notification row changes, no forecast or recommendation is
   touched.

### OPEN

- **The push channel quietens.** Refusals were its main trigger (the last
  three failure notices were refusals). A missed slate still shows on the
  Health panel and the first screen, and a real failure still pushes.
- **WakeToRun is unproven on this machine**: every wake since 1 September
  records TargetState 4 and EffectiveState 5, and `powercfg /waketimers`
  needs elevation. The only proof is a wake by a timer in `tools/awake.py`'s
  count, which has never been above 0. Most lost time was switched off,
  which no wake setting reaches.
- **`scheduler.NOT_INSTALLED` still says Live has no registered timer** --
  stale since 2026-09-08; out of scope.
- **A suite run can show a real desktop notice**:
  `test_scheduler.py::test_a_failing_task_is_recorded_not_raised` takes the
  failure path without `GRIDIRON_NOTIFY_FAILURES=0`, so `notify_failures`
  sends (the phone push is stopped by the suite's shut network; the toast is
  not). Every item 7 test and planting sets it; the old test is out of
  scope.

### THE PROVER *(2026-09-26)*

Every planting escaped on f58b3a1 (`git archive`) and was caught here; each
guard, neutralised in a copy of the tree, let its planting escape (17
neutralisations). Then the defect was reached by other paths the gate
passed, and each was closed and planted:

- **The wake scan passed a task that would not wake.** It refused only
  `-WakeToRun:$false`, and read a settings variable by its last assignment
  from `New-ScheduledTaskSettingsSet`, so 13 shapes passed while the
  seventeen tasks through `New-GridironTask` registered without the wake:
  `-WakeToRun:0`, `:$null`, `:$off`, `:(1 -eq 2)`; `$settings.WakeToRun =
  $false` (or `= 0`, `${settings}.WakeToRun`, a `PSObject` property) after
  the set was made; the set made again (`$settings = (New-...)`, `= $plain`,
  `Set-Variable`, `$script:settings`); and the set handed to a command that
  may change it (`Update-Settings $settings`, whose name ends in
  `-Settings` and was read as the parameter). Now the switch counts only
  bare or as `:$true`, and a variable only if it is assigned once, straight
  from the cmdlet, and otherwise only passed as `-Settings`. Four of the
  shapes are now in `plant_a_task_definition_without_wake_to_run`; all of
  them in `test_scheduler.py::test_a_wake_taken_away_another_way_is_named`.
  The planting's first comment shape (above the function) could never have
  satisfied the scan; the comment on the settings statement is the one that
  proves comments are blanked.
- **The order check passed a close under a handler that lets it out.** Any
  handler made a `try` count, so a close inside `try: ... except
  ValueError:` -- or under `except Exception:` that raises again -- passed
  while the locked write left `run_task`. The suite's behaviour tests would
  have failed on the shipped code; the gate's own check did not. Now a
  `try` guards only if a handler catches `Exception` or wider and raises
  nothing; both shapes are in `plant_a_closing_write_that_escapes_the_try`
  and `test_scheduler.py::test_the_gate_sees_a_closing_write_under_a_
  handler_that_lets_it_out`.
- **The Health row of an abandoned run was hard to read.** The panel's
  value column is `auto`, so the abandoned detail (and, before item 7, a
  failed run's) took the row and left the warning -- the sentence the panel
  exists to say -- a few words a line, 25 lines down at 1100px and at 390.
  `.set-v .set-how` now wraps inside 62ch, and a Health row stacks at 640px
  and below (the Health panel only; a row with a control keeps it beside
  its label). Rendered from the browser world at 1100 and 390 before and
  after; `test_health_words.py::test_a_long_detail_leaves_the_label_room_
  to_be_read` measures the label column's share of each Health row (4% at
  1120px and 12% at 390 on the unfixed stylesheet; above 30% and 90% now).

Seen and left as they are:

- **A refused rerun now counts as the day's run on the first screen.**
  `views.freshness` reads the last predict run ended `ok` or `noop`, so a
  refusal -- recorded `failed` until now -- keeps "daily run" fresh, as
  "every question on this slate was already answered" always has. It
  follows from the ruling's word; the strip's other two lines (the venue
  read, the reasoning pass) are unchanged.
- **An abandoned row says its cause twice**: the panel's warning ("The
  process was killed, or the machine slept ...") and the stored detail end
  in nearly the same sentence. The detail is stored and stands alone in the
  ledger; the warning is the panel's. Not changed.
- **The widening, three processes at once**: on a copy through the backup
  door, three children opening it together all opened (0.5 to 1.7 s), and
  every row and column checksum survived, and no table was left aside.

## The closing line's window -- built 2026-09-27 *(GRIDIRON_REPAIR item 8; the operator's ruling of 2026-09-23)*

"READINESS: two BROKEN findings recorded; the observation window restarts on
the date item 1 ships; the first clean CLV read is 21 days after that, not
before." **THE OBSERVATION WINDOW RESTARTS 2026-09-24; THE FIRST CLEAN READ IS
2026-10-15.** The window it restarts is the two-week observation period of
2026-09-07 (`docs/FOLLOWUPS.md`, "2026-09-07 — readiness, and a two-week
observation period"), read on 2026-09-21; that entry is not edited. The map
of 2026-09-23 was re-verified against 549aab7 first: since it was drawn, item
1 had moved the measured close into `recommendation_closes` (restated closes
shown beside the count, never in it), so the window is one more clause in a
reader, not a marking of rows.

### MEASURED FIRST, read-only *(2026-09-27 about 00:15Z, `db.read_the_live_record`)*

- **When item 1 shipped**: `23cf89b` committed 2026-09-24T06:48:39Z; the main
  checkout's reflog (read with `git reflog`, nothing changed) fast-forwarded
  to `4941fa1`, which carries it, at 2026-09-23T23:49:12-07:00 =
  **2026-09-24T06:49:12Z**; served from about 06:57Z; the restatement wrote
  its 55 rows at 06:49:48Z. The UTC date is the 24th at every one of them.
- **The closing line today**: 107 recommendations; 88 accounts in
  `recommendation_closes` -- 55 restated (the old closer's, all written
  before the 24th: 31 with a later read, 24 without) and 33 by the repaired
  closer (21 measured, the first at 2026-09-25T20:05:01Z; 12 unmeasured, the
  first at 2026-09-24T16:35:02Z). Measured closes counted: MLB spread 12,
  NCAAF spread 8, MLB total 1; NFL 0 (1 unmeasured); NBA and UFC 0. **No
  measured close is on a recommendation written before the 24th**, and no
  close written in the window came from the old closer.
- **What the window holds**: 48 standing recommendations written since the
  24th (MLB spread 25 on 20 games, NFL spread 12, NCAAF spread 8, MLB total
  2, NFL total 1), 42 of them before items 3, 4 and 5 reached the checkout
  on the 26th; five MLB spread game-markets hold two each (60/79, 61/80,
  84/93, 86/94, 87/95); eleven written on the 24th before 06:49Z (56-61
  unmeasured, 62-64 and 66 withdrawn, 65 open). Since 2026-09-07, MLB spread
  holds 66 standing (52 games).
- **The cost of the two findings**, for READINESS: 55 of 55 old closes at
  the price paid, from 2026-09-08T20:35:08Z to 2026-09-24T02:05:01Z; NFL and
  NCAAF spread and moneyline last forecast 2026-09-04T18:40:24Z and
  2026-09-05T15:00:57Z and next at 2026-09-24T15:00Z, 16 NFL and 165 NCAAF
  games kicking off in between with no forecast in either market (15 and 160
  while the machine was off, 11-21 September).

### BUILT *(2026-09-27)*

- **Dated constants** in `config`: `CLOSING_LINE_WINDOW_START = "2026-09-24"`,
  `CLOSING_LINE_FIRST_READ_AFTER_DAYS = 21`, `CLOSING_LINE_FIRST_CLEAN_READ =
  "2026-10-15"`, literals under a comment quoting the ruling and saying why
  the date is the 24th. `test_closing_line_window.py::test_the_dates_are_
  the_ruling_s` ties them to the ruling and each other, and pins the
  thresholds (50, 50) and `CLV_DECLARED` where they were.
- **One door**: `calibration.closing_line_window(now=None)` -- the UTC date
  of `now` (the clock by default), the days counted by `language.date_gate`,
  `open` from the first clean read on.
- **`calibration.clv_report(conn, *, sport, now=None)`**: a measured close is
  in N only if its recommendation was written on or after the start; a
  measured close on an older one is `before_window`, per market and in
  total, named in words ("... more were written before Thursday 24
  September, when the count started again, and are not counted"). Before the
  first clean read: `renderable` False, `mean_cents` and `beat_the_close`
  None (not computed), no `finding`; the words give the count with its N,
  "since Thursday 24 September", and "the first clean read is Thursday 15
  October, and nothing is claimed before it". New keys: `window` (dates,
  open, the day count) and `window_line` ({label "Since the repair", n,
  words}), said on every sport's page, a sport with nothing closed
  included. After the date the report is what it was, counted from the
  24th.
- **The kill criterion waits**: `priced.coverage.stopped(conn, sport, *,
  now=None)` returns nothing while the report's window is shut;
  `priceable(..., now=None)` passes the clock through. `calibration.
  scorecard` reads the clock once for the closing line and the kill.
- **The withdrawn recount** (`audit.withdrawn_counted_faults`) counts every
  measured close in the count or before the window (its "n" and its
  buckets), so the window moves no withdrawn close past it; its fault label
  says so.
- **The Record page**: `renderPriced` places `window_line` first in the
  closing line's list, through `requireN`, composing nothing.
- **Plantings** (each ESCAPES on 549aab7 -- `git archive HEAD` into the
  scratchpad, this `plant.py` copied over it -- and each is CAUGHT here):
  `plant_a_closing_line_verdict_before_its_first_clean_read` (sixty closes
  at +3.0c and sixty at -4.0c written from the start's first second -- the
  day after it until the prover, below -- read at noon on 14 October: on the
  head the spread rendered at +5.0c over 90, the total carried "THE MODEL IS
  BUYING RICH" and the kill stopped it; here each gives its count, no figure
  and the date, and on 15 October itself the verdict, the finding and the
  kill arrive), and `plant_a_close_from_before_the_window_counted` (thirty
  at +9.0c written in the ninety minutes before the start and closed after
  it -- the day before it until the prover: on the head the spread counted
  90 at +5.0c; here 60 at +3.0c with the thirty named beside, and the
  recount agrees).
  Two existing plantings had worlds dated 7 September, before the window,
  and are dated after it now, each re-run caught on the head and here:
  `plant_a_close_read_from_the_first_of_two_reads`,
  `plant_a_withdrawn_recommendation_in_the_closing_line`.
- **Tests**: `test_closing_line_window.py` (the dates, the door at 23:59:59
  and 00:00, the wait and the day itself, a close from before the window,
  the Record page's sentence, an empty sport, the words through the plain-
  words and advice scans); `test_priced.py::test_the_kill_criterion_waits_
  for_the_first_clean_read`; the kill test and `test_voids.py`'s closed world
  dated inside the window, and read with `now` where they read a mean.

### RENDERED *(2026-09-27 about 00:50Z; this tree and 549aab7 served against one scratch copy of the record made through `db.back_up_the_live_record`, signed in with the browser suite's test token)*

"Priced, and against the close" at 1100px and 390px, MLB and UFC, read as
pictures: no horizontal scroll, no console error. On 549aab7 MLB's closing
line read "12 of 50 priced against a close · nothing is claimed from a sample
this size · ..." and UFC's said nothing about the closing line at all. Here
a "Since the repair" row comes first -- "The closing line was repaired on
Thursday 24 September, and its count started again that day: 13
recommendations priced against a close since. The first clean read is
Thursday 15 October, 21 days after the repair, and nothing is claimed from it
before then." -- and it also separates the coverage rows above it from the
closing line's own below; MLB point spread "12 of 50 priced against a close
since Thursday 24 September · the first clean read is Thursday 15 October,
and nothing is claimed before it · ..." and total "1 of 50 ..." (12 + 1 = 13,
as the row above says); UFC shows the one row, with 0. The row is in the
same text colour as its neighbours.

### READINGS TAKEN *(each reversible in one line)*

- **"Ships" is when the released main checkout holds it**: 06:49:12Z on 24
  September (the reflog), not the commit (06:48:39Z) or the serve restart
  (about 06:57Z). All three are the 24th, so the date does not depend on it.
- **"The date" is the UTC date, 00:00Z**: the ruling names a date, and every
  date here is UTC. Recommendations 56-66, written on the 24th before
  06:49Z, are in the window; none is measured, four are withdrawn, 65 is
  open. (Reversal: `from_utc` in `closing_line_window` becomes the instant.)
- **"Counted from the window" is by when the recommendation was written**
  (`created_utc`), which also means its close was measured on or after the
  start -- the stricter of the two, and item 1's close-out's own words (the
  restart "puts every pre-repair recommendation outside it"). No figure moves
  either way today: no measured close is on an older recommendation.
  (Reversal: the clause reads the account's `written_utc`.)
- **The kill criterion is a read of the closing line**, so it waits for the
  date: it reads the mean and prints it ("... a contract against the close,
  which is buying rich"). The exposure is small and stated: no market has
  more than 12 counted closes today, baseball ends on the 27th, and a market
  buying rich meanwhile is a flat unit beside "no measured edge".
- **Before the first clean read the mean is not computed at all**, rather
  than computed and hidden: "not before" is read as nothing to read. After
  it, a mean below fifty is carried as it always was (a LAW 4 question
  outside this ruling).
- **The closing line's window is not a `READ_WINDOWS` entry**: those count a
  wait down on the Record page's list of gates and withhold nothing; this
  withholds a figure in every sport and says its date where the figure
  would be. No second countdown was added to the page.
- **No READINESS run row**: the section records two findings and a ruling
  and re-reads no criterion. The next row is the re-read's.

### THE LIVE RECORD AFTER THE RELEASE *(none)*

The ruling writes nothing to the record: no schema change, no row, no tool.
The window is a clause in a reader, and the 55 restated closes, the 12
unmeasured and every recommendation stay as written (LAW 3). From the
release the Record page shows each sport's count since 24 September with the
first clean read's date, and no closing-line mean until 15 October.

### OPEN

- **For the re-read: criterion 2's count.** READINESS criterion 2 is "≥ 50
  recommendations in one coverage entry". Counted since 2026-09-07 MLB spread
  holds 66 standing (52 games); counted since 2026-09-24, 25 (20 games).
  Whether the restarted window covers criterion 2 as well as the closing
  line is not settled here -- nothing in item 8 reads it -- and the re-read
  must say which count it applied.
- **The old period's other terms.** The 2026-09-07 period also said "no new
  features ... softening a threshold, adding surface area, or re-tuning
  anything on a sample this size". Softening a threshold is refused under
  any reading; the feature queue after the repair's close-out is the
  operator's ruling of 2026-09-26 and is not re-decided here.
- **LAW 4 and the fifty.** At the first clean read a market with fifty
  measured closes may render "buying cheaper than the market's own final
  estimate" on fifty, where LAW 4 asks a hundred of an edge claim. The fifty
  was declared on 2026-09-07 as a comparison of two prices, not an edge
  estimate; no closing-line verdict has ever rendered, so the question
  arrives for the first time on 15 October.
- **Nine of the 21 measured closes are at the price paid**, each on a later
  read of its own contract that the schema checks (the price had not
  moved). Not the old defect; worth watching when the first read comes.
- **`views.scorecard` counts the dated read windows in the machine's local
  date** (`language.date_gate` with no `today`). Only the rung window of
  2026-09-14, long open, uses it; the closing line's door passes the UTC
  date. Out of scope.
- **`settings.py`'s comment on the payout floor** still says the closing line
  is measured "separately, over the ones this let through", which no report
  does; the visible words no longer say it. Out of scope.

### THE PROVER *(2026-09-27)*

Both new plantings ESCAPE on 549aab7 (`git archive HEAD`, this `plant.py`
copied over it) and are CAUGHT here; the two re-dated ones are caught on
both. Each guard, neutralised in a scratch copy of this tree, lets its
planting escape: no window on the count (both), the gate always open, the
gate a day early, and the mean computed before the gate (the first). Full
harness 314/314. Step 2's record and schema rows, dry-run on a gate copy:
both schema comparisons pass with 0 registered differences, every record
check passes, the live schema as found. Read-only on the record: every
`created_utc` and `closed_utc` is the one format, so the window's string
comparison is a time comparison; no measured close is on a recommendation
written before the 24th; the first close by the repaired closer was written
2026-09-24T16:35:02Z. The ten test modules that read the closing line pass
with every clock read of the window moved to 20 October, so none of them
waits on the window being shut.

- **THE BOUNDARY WAS NOT PROVED** (closed). Both plantings' worlds and the
  tests' sat a day either side of the start, so four wrong windows passed
  every planting and every test, each tried in a scratch copy: counted by
  when the CLOSE was written (the reading not taken, which counts a
  recommendation written before the repair and closed after it -- the most
  likely shape of a close from before the window, since the repaired closer
  closes whatever is open); opened at item 1's instant, 06:49:12Z; opened on
  the operator's clock, 07:00Z on the 23rd; and opened a second late (`>`
  for `>=`). The planted world now writes its first counted recommendation
  at 00:00:00Z on the 24th and the thirty before the window in the ninety
  minutes before it, each read and closed after it; both plantings escape
  on all four, and `test_closing_line_window.py::test_the_window_opens_at_
  midnight_utc_and_counts_when_each_was_written` fails on all four. Both
  still escape on 549aab7 and are caught here.

Seen and left as they are:

- **The ship date is the 24th in UTC and the 23rd on the operator's
  clock** (23:49:12 -07:00). The UTC date is the house rule ("All times are
  UTC") and the later of the two, so the first clean read, 15 October, is
  "not before" under either; READINESS and `config` say "in UTC".
- **The kill criterion re-counts from the window.** A market stopped on the
  old count would start again until 15 October without a ruling; none ever
  was (every old close read 0.00c, and no market has fifty measured closes),
  so nothing is re-entered.

## No stored recommendation is replaced -- built 2026-09-27 *(operator question 13; the ruling of 2026-09-27)*

"Q13: fix first, its own commit, planting proved on the unfixed code. No
stored recommendation may be replaced by any statement." The question as
asked is `docs/REPAIR_STATE.md` question 13; the hole was found by item 5's
prover (above, "Found in passing, not this item's: a recommendation can be
REPLACED"). No map of 2026-09-23 covers it; the precedents are the snapshot
table's two replace rules of 2026-09-25 (`market_snapshots_never_replaced`,
`..._by_update`), the prompt record's and the re-grade table's.

### MEASURED FIRST *(2026-09-27; scratch databases built by 1448c1e -- the released f02e913 plus documents -- and by this tree; the record only through a copy made by `db.back_up_the_live_record`)*

- **Every form that took a stored recommendation's place on 1448c1e**, each
  on a fresh scratch world: `INSERT OR REPLACE` and `REPLACE` naming a
  stored number -- as `id`, as `rowid`, as the text `'1'`, as `1.0` -- wrote
  another recommendation under it (another game, the other side, 90c);
  `INSERT OR REPLACE` on a stored forecast and stamp removed the row and
  wrote the newcomer under a new number, the forecast id given as text too;
  `INSERT OR REPLACE ... SELECT` colliding with one row's number and
  another's forecast and stamp removed both; `INSERT OR REPLACE` onto a
  WITHDRAWN recommendation's number on its own game and market passed the
  one-per-game rule (a withdrawn one does not stand), and its row in
  `recommendation_voids` then stood beside a recommendation nobody withdrew
  -- with foreign keys on, since the new row has the old number; and
  `UPDATE OR REPLACE` moving one row onto another's number by `id`, `rowid`,
  `oid` or `_rowid_` removed the other.
- **Already refused on 1448c1e, and why**: an update of what was
  recommended, or of the forecast and stamp (`recommendations_no_update`),
  of the correction (`recommendation_correction_is_frozen`), of a close once
  written (`recommendation_closes_once`); each also refuses the update half
  of an upsert. An upsert moving a row onto another's number failed on the
  key. What an upsert could still do there -- write an open
  recommendation's close, or give a row a free number -- replaces nothing.
- **The table's keys, on the copy of the record**: 107 recommendations, ids
  1-107 (sequence 107); two unique keys only, the number and `UNIQUE
  (prediction_id, created_utc)` (`sqlite_autoindex_recommendations_1`);
  `recommendations_sport` is not unique. Three tables point at it --
  `recommendation_closes`, `recommendation_voids`, `recommendation_regrades`
  -- all NO ACTION, so no cascade reaches it; `recursive_triggers` off; the
  newest rule on the table `recommendation_one_per_game_and_market`.
- **SQLite 3.49.1, measured on scratch tables**: a table's BEFORE rules run
  NEWEST FIRST (the last made fires first, on a fresh connection and after
  a reopen); a rule of the form `BEFORE UPDATE OF id` is NOT run by an
  update naming `rowid`, `oid` or `_rowid_`, though they are the same
  column; a BEFORE INSERT rule sees `NEW.id` as -1 when the number is left
  to SQLite, and as the integer when it is given as `'7'` or `8.0`.

### BUILT *(2026-09-27)*

- **`recommendations_never_replaced`** (BEFORE INSERT): refuses an insert
  naming a stored number, or a forecast and stamp already stored. A rule
  cannot see a statement's conflict clause, so it refuses them whatever it
  says: a plain duplicate (until now the key's refusal, "UNIQUE constraint
  failed") and an upsert naming a stored row are refused too, by name.
- **`recommendations_never_replaced_by_update`** (BEFORE UPDATE, no column
  list): refuses an update that would take the place of another stored
  recommendation -- its number or its forecast and stamp -- and nothing
  else. It runs on every update of the table (the closer's included) and
  asks two indexed lookups; it names no columns because the list form
  misses `rowid`, `oid` and `_rowid_` (tried: with the rule rewritten as
  `BEFORE UPDATE OF id, prediction_id, created_utc`, the planting's three
  updates by those names escape).
- **Declared after `recommendation_one_per_game_and_market`** in
  `schema.sql`, so a fresh build makes them in the order the record will:
  the record gains them on its first open after the release, after that
  rule, and the newest runs first. Both refuse in words carrying
  `recommend.NEVER_REPLACED` ("a recommendation is never replaced"), never
  "UNIQUE" and never the one-per-game words; a test holds the schema to it.
- **`record_for` counts as it did.** It names no number, so the insert rule
  refuses its row only for a forecast and stamp already stored -- the
  forecast written twice, which it counted `already` off the key's "UNIQUE".
  It now counts the replace rule's words the same way. The one case that
  reaches it: a withdrawn recommendation's own forecast asked again (the
  door lets it through, since a withdrawn one does not stand), `already`
  before and after (`test_a_forecast_written_twice_is_still_counted_as_
  already`, which passes on 1448c1e too).
- **Every writer read**: `recommend.record_for` (a plain INSERT naming no
  number) and `record_closing_prices` (a plain UPDATE of the close); no
  other package or tool module writes the table (`tools/dbcopy.FACT_TABLES`
  does not copy it; `gridiron.rebuild` copies into a new table before its
  rules exist and has never rebuilt this one; `db._finish_widening_table`'s
  OR IGNORE copy is only for tables with a sport CHECK, which this has not);
  the plantings and the tests insert plainly, the explicit numbers in
  `test_recommend.py` (`_recorded`) and `test_voids.py` (62-66, 70) all
  fresh. None uses OR REPLACE, REPLACE, OR IGNORE or ON CONFLICT on it, so
  no lawful write changes.
- **Planting** `plant.py::plant_a_replaced_recommendation`: recs 1 and 2
  standing, rec 3 withdrawn; the ten forms above that replace and two no
  release lets replace (an update onto another's forecast and stamp, an
  upsert rewriting what was recommended), each run and rolled back; CAUGHT
  means each refused under LAW 3 -- the ten by the replace rules' words --
  with every recommendation and every withdrawal as stored, a new
  recommendation on a game of its own and the close of an open one still
  written, and, with both rules dropped, each of the ten changing the table.
- **Tests** in `test_recommend.py`: fifteen forms (the planting's twelve,
  the number as `1.0`, the forecast id as text, an upsert moving a row onto
  another's number), each refused in the rules' words with the table and
  its withdrawals unchanged; the ten replacing without the rules (and the
  withdrawal left beside the newcomer); the lawful writes (`record_for`, a
  plain insert, the closer, a withdrawn one never closed); the forecast
  written twice; the words and the order on a fresh build; and an older
  record gaining exactly the two rules through `db.init`, with a fresh
  build's text, after the one-per-game rule, no row moved, a second open
  adding nothing.

### THE REHEARSAL *(2026-09-27 about 03:25Z; a copy of the record made through `db.back_up_the_live_record` at 03:01Z, and a verified copy of that, never the record)*

The copy of the copy verified (`rebuild.verified_backup`: 61 tables,
integrity ok, every sqlite_master row and every table's count and column
checksums equal). Before: 235 objects, 1,228,727 rows, 107 recommendations,
and `schema_diff.compare` against a fresh build of this tree found exactly
the two rules missing and nothing else. `db.init` under this tree then made
exactly `recommendations_never_replaced` and `..._by_update` -- no object
gone, none changed, no table's count or column checksums moved -- with a
fresh build's text byte for byte, after
`recommendation_one_per_game_and_market`. After: the comparison found 0
differences in behaviour (237 objects each; 9 differ only in what the ruling
normalises, the two rules not among them). On the copy's own rows, OR
REPLACE naming rec 107, OR REPLACE on rec 1's forecast and stamp, and UPDATE
OR REPLACE moving rec 2 onto rec 1 by `rowid` were each refused by the
replace rules, and an update of an open recommendation's close column still
landed (rolled back); the recommendations' checksums unchanged throughout.

### PROVED *(2026-09-27)*

- **The planting ESCAPES on 1448c1e** (`git archive HEAD` into the
  scratchpad, this `plant.py` copied over it): all ten replacing forms
  taken, each named with the rows before and after. It is CAUGHT here.
- **Each rule alone is proved by it**: with `recommendations_never_replaced`
  dropped after `db.init`, the six inserts escape; with `..._by_update`
  dropped, the four updates; with the update rule rewritten to list `id,
  prediction_id, created_utc`, the updates by `rowid`, `oid` and `_rowid_`.
- **The new tests fail on 1448c1e** (this `test_recommend.py` run over the
  archive): the fifteen forms, the forms-without-the-rules test, the words
  and order, and the older record gaining the rules; the lawful-writes test
  and the forecast-written-twice test pass there too, as they must: they
  hold the writers to what they did.
- **The full suite passes here** with a dummy access token: 1730 passed, 8
  skipped, the harness among them; run alone, the harness is 315/315.

### READINGS TAKEN *(each reversible in one line)*

- **"Replaced" is a stored recommendation removed by another's taking its
  place** -- the conflict resolution of OR REPLACE, whether an insert or an
  update triggers it. So the insert rule refuses any insert naming a stored
  number or forecast and stamp (a rule cannot tell OR REPLACE from a plain
  insert, and the precedent refuses both); the update rule refuses only an
  update that takes another's place, as the snapshot rule does. (Reversal
  of the second: the update rule refuses any change of number.)
- **An upsert naming a stored recommendation is refused whatever it would
  set**, even one that would only write an open recommendation's close: the
  insert half names a stored number, and the close has its own writer, an
  update, which is untouched. No writer uses an upsert here.
- **The companion tables are not fixed here** (the ruling names
  recommendations): OPEN, below.
- **The words of a plain duplicate moved.** A second row of one forecast at
  one stamp beside a STANDING row used to be refused in the one-per-game
  words (that rule ran before the key), and is now refused in the replace
  rule's (it runs first); `record_for` would count it `already` where it
  counted it `second_on_game_market`. It cannot reach `record_for` from the
  package: `run.run_slate` records only the forecasts its own run wrote,
  once, and a rerun is refused as answered. The two-writers test, whose
  forecasts differ, is unchanged.

### THE LIVE RECORD AFTER THE RELEASE *(no tool)*

No row is written and no tool runs. The scheduler's first open of the record
under the released code (`db.init`, as every schema rule has arrived since
5b) makes the three rules (the third from the prover, below), and nothing
else; every recommendation stays as written. Afterwards, read through
`db.read_the_live_record`: sqlite_master holds
`recommendations_never_replaced`, `recommendations_never_replaced_by_update`
and `recommendations_never_replaced_by_the_number_written`, in that order,
after `recommendation_one_per_game_and_market`, with `schema.sql`'s text.
Until that first open the record lacks them while the release has them, so
the gate's release comparison is run after it, as with every rule since 5b.

### OPEN, found by this item *(2026-09-27; measured on scratch databases built by this tree)*

- **`recommendation_closes` and `recommendation_voids` still take a
  replacing insert.** Their no-update and no-delete rules hold, and an
  upsert on either is refused by the no-update rule, but `INSERT OR REPLACE`
  naming a stored `recommendation_id` was taken on both: an account of a
  close rewritten as a restated, unmeasured one written later, and a
  withdrawal's time and reason rewritten. (A measured close is harder:
  the new row must still cite its own pricing read and a later read of its
  contract.) `recommendation_regrades` refuses it (item 4's
  `recommendation_regrades_never_replaced`). The fix has the prompt record's
  shape, one rule of a new name per table; not built, because the ruling
  names recommendations.
- **The snapshot table's update rule has the gap this item's update rule
  was built round.** `market_snapshots_never_replaced_by_update` is `BEFORE
  UPDATE OF id, prediction_id, kind`, and `UPDATE OR REPLACE
  market_snapshots SET rowid = 1 WHERE id = 2` (or `oid`, `_rowid_`) was
  taken on this tree: two snapshots became one, a hole in the ids like
  174-181. Schema ruling 4's rule is released and serving; restating it is
  not this item's.
- **A prediction can be replaced.** On this tree, `INSERT OR REPLACE`
  naming a stored prediction's number rewrote its probability (0.61 to
  0.99 under the same number), and `UPDATE OR REPLACE ... SET rowid` onto
  another removed that one; `predictions_no_delete` never runs. LAW 3's own
  table has no replace rule: nothing refuses it, and the gate's
  `audit.check_record_fingerprint` is what would name a rewritten row
  afterwards, as drifted from its fingerprint (not tried here). The same
  census on a fresh build: of
  the twenty tables with a delete rule, only `recommendations`,
  `market_snapshots`, `reasoning_prompts` and `recommendation_regrades`
  carry a replace rule; the other sixteen -- `predictions`,
  `at_the_line_claims`, `calibration_corrections`, `factors`,
  `fit_activations`, `picks_retracted`, `picks_taken`,
  `prediction_fingerprints`, `prediction_ranks`, `prediction_voids`,
  `priced_forecasts`, `recommendation_closes`, `recommendation_voids`,
  `settings`, `task_runs`, `venue_packages` -- carry none, which is the
  2026-09-23 finding above ("`INSERT OR REPLACE` walks past every
  append-only trigger"), still open. Replacing was tried here only on
  `predictions` and the two companions; another rule on insert may refuse
  it on some of the rest. *(Closed for `predictions` by question 15's first
  step, ruled 2026-09-27, third set: "No stored prediction is replaced",
  below. The other fifteen still carry no replace rule; the same ruling's
  gate scan is about replacing statements in the shipped code, not rules.)*
- **A recommendation's number can still be changed.** `recommendations_no_
  update` lists no `id`, so `UPDATE recommendations SET id = 99 WHERE id =
  1` (or by `rowid`) lands when no other row holds 99 -- with foreign keys
  on, a recommendation with a close, a withdrawal or a re-grade is held by
  the key, and one without moves. A later plain insert naming the old number
  would then put another recommendation under it: two statements, neither a
  replacement. Freezing the number goes past the ruling's words (the
  precedent's own question 6 for snapshots); not built. *(From the prover of
  2026-09-27 the second statement is refused: the old number is at or below
  one already given out, so `recommendations_never_replaced_by_the_number_
  written` refuses an insert under it. The change of number itself still
  lands.)*
- **A number below 1.** An insert leaving the number to SQLite shows the
  insert rule -1; a recommendation stored under -1 -- none is, the record's
  lowest is 1, and only an insert naming it could make one -- would make
  every such insert refused, and `record_for` would count each `already`.
  *(Closed by the prover, 2026-09-27, below: an UPDATE could make one --
  the update rule lets a row take a free number -- and on the tree as built
  it then did exactly this; the insert rule no longer looks -1 up.)*

### THE PROVER *(2026-09-27; scratch worlds built by 1448c1e, by the tree as built, and by this tree; the record only through copies made by `db.back_up_the_live_record`)*

- **FOUND: A NUMBER READ ONE WAY BY THE RULES AND ANOTHER BY THE KEY.** For
  an insert of one row of values SQLite works the row's number out twice:
  once into the row the BEFORE rules see, and again when the row is
  written (measured on 3.49.1: a function the connection defines is called
  twice, and the rule sees the first answer). Every other value of the row
  is worked out once; an insert from a query, or of several rows, goes
  through a holding store and is worked out once; an update works its new
  values out once, before its rules run (all measured, the last with the
  same function: called once). So on the tree as built, `INSERT OR REPLACE`
  and `REPLACE` whose number answered NULL (the rule sees -1) or a free
  number to the rule, and a stored one to the key, wrote another game's
  recommendation over rec 1, rec 2 and the withdrawn rec 3 of the planted
  world, the withdrawal left beside the newcomer; with `random()` in the
  number, about one try in four did it (300 tries each form). On 1448c1e
  the same statements replace too.
- **BUILT: `recommendations_never_replaced_by_the_number_written`** (AFTER
  INSERT, declared after the two rules as built): refuses the row's number,
  read after it lands, at or below `sqlite_sequence` for the table -- which
  SQLite writes back only when the statement ends, so the rule reads the
  highest number given out before the statement (measured: both BEFORE and
  AFTER rules of every row of a three-row insert read the value from before
  it) -- or below any stored recommendation. Every stored recommendation is
  at or below that mark, and `RAISE(ABORT)` takes the statement back, the
  removed row with it. `record_for` is never refused by it: SQLite gives its
  insert the next number up.
- **THE CONSERVATIVE DEFAULT IT TAKES** (recorded, reversible only by a
  witness below): after the insert a rule cannot tell a number that was
  stored from one that is free, so a new recommendation written under a
  free number at or below one already given out is refused too -- one
  vacated by an update, 0, -1. No writer names a number, and the record's
  numbers run 1 to 107 with no gap. One test world did (`test_recommend.py`
  `_let_through_world` wrote rec 2 after recs 3 to 33); it now writes rec 2
  first, as its stamp says it was written, and every assertion stands.
- **FIXED: THE -1 THE INSERT RULE IS SHOWN.** The update rule lets a row
  take a free number, -1 included; on the tree as built a recommendation
  moved to -1 then had the insert rule refuse every later insert that left
  the number to SQLite (it saw -1, and found -1 stored), and `record_for`
  counted each `already`: the next pick was not written and nothing said so
  (measured: `recommended` 0, `already` 1). The insert rule no longer looks
  -1 up; a number given as -1 is checked after it lands, by the rule above.
- **NOT SEEN, AND NOT FIXED: SQLite's sequence set back first.** SQLite
  lets an ordinary statement rewrite its own sequence for a table (`UPDATE
  sqlite_sequence SET seq = ...`, or a delete of its row) and refuses any
  rule on that store ("cannot create trigger on system table", measured).
  After such a statement sets the sequence below the newest recommendation,
  an insert whose number reads free to the rules and the newest's to the
  key writes over the newest one: the table and the sequence are then
  exactly what a lawful newcomer leaves, so no rule can tell (measured: rec
  3 of the planted world, with the sequence set to 2 or its row deleted).
  Every other recommendation stays protected by "below any stored one".
  Closing it needs a witness kept outside SQLite's sequence -- a table of
  every number given out, append-only, filled for the record's 107 by a
  tool after the release -- which is more than a rule, and a write to the
  record; not built, for the orchestrator and the operator.
- **TRIED AND NOT A REPLACEMENT** (on this tree): the forecast or the stamp
  read twice (worked out once: nothing written over); an insert from a
  query, or of several rows, whose number is read twice (worked out once);
  an update whose new number is read twice (called once: the row moves to
  the free number, finding 4 above); a temporary table, or a WITH, named
  `recommendations` or `sqlite_sequence` (the rules read the main
  database's own); a temporary rule turning the number between its
  readings (refused or a new row). AND AN UPSERT WHOSE NUMBER READS TWICE
  reaches its DO UPDATE on a stored row past the insert rule: it wrote an
  open recommendation's close, or gave the row a free number -- updates the
  table's own rules govern (`recommendation_closes_once`, the update rule),
  neither a replacement. The reading above that an upsert naming a stored
  recommendation is refused holds for a number read once.
- **PROVED.** The planting, with the three read-twice forms added and a
  check that dropping only the new rule lets them write over a stored one,
  ESCAPES on 1448c1e (all thirteen replacing forms taken) and on the tree
  as built (exactly the three read-twice forms taken), and is CAUGHT here.
  The new tests (`test_a_number_read_one_way_by_the_rules_and_another_by_
  the_key_is_refused` for three forms by `INSERT OR REPLACE` and `REPLACE`,
  `..._worked_out_at_random_...`, `..._below_one_already_given_out_...`,
  `..._given_a_number_below_one_does_not_stop_the_next`) fail on the tree
  as built and on 1448c1e, and pass here. Full suite with a dummy access
  token: 1739 passed, 8 skipped; the harness alone 315/315.
- **REHEARSED** on a fresh copy of the record made through the backup door
  (a verified copy of it; 61 tables, 1,232,541 rows, recommendations 1-107,
  sequence 107): `db.init` under this tree made exactly the three rules,
  with a fresh build's text, after the one-per-game rule; no object gone or
  changed, no table's count or column checksums moved; 0 differences from a
  fresh build (238 objects each); a second `db.init` changed nothing. On
  the copy's own rows: OR REPLACE naming rec 107, on rec 1's forecast and
  stamp, UPDATE OR REPLACE by `rowid`, both read-twice forms (onto rec 1,
  and onto rec 107, the newest) and a free 0 were refused in the replace
  rules' words; a lawful update of an open one landed and a plain insert
  took 108 (both rolled back). The gate's step-2 record rows, dry-run on
  their own copy: both schema comparisons 0 registered, nothing new, every
  record check passing, the record's schema as found.

## A pair counted once, and both sides not at all -- built 2026-09-27 *(operator question 12; the ruling of 2026-09-27)*

"Q12: the record shows rows as written. Every measurement counts a same-side
pair once (the earlier row). Recs 45/46, opposite sides of one total, count
zero in every measurement and are labelled 'both sides, no position'."
(`docs/briefs/2026-09-27-close-out-rulings.md`; placed after the Q9 labels
and before the flaky tests by the second set.) **A MEASUREMENT RULE, NOT AN
EDIT**: no recommendation is changed, deleted, hidden or labelled in the
record; no table, column or schema object is added; nothing is written.

### MEASURED FIRST, read-only *(2026-09-27, `db.read_the_live_record`; newest recommendation 110, written 05:48:52Z)*

- **The pairs, by rule** (every game and market holding more than one
  standing recommendation, the withdrawn ones left out first): eighteen,
  each of exactly two rows -- 1/9, 3/10, 4/12, 5/13, 6/14, 20/25, 21/26,
  23/28, 32/34, 41/44, 42/48, 43/49, **45/46** (the over and the under, one
  second, the only pair on both sides), 60/79, 61/80, 84/93, 86/94, 87/95:
  **the eighteen measured on 2026-09-26, exactly**, every one MLB (spread
  fourteen, total four). Counting withdrawn rows too there are 22: the four
  more are NFL 62/73, 63/75, 64/76, 66/78, each a withdrawn row and the
  standing one written after it -- no pair, since a withdrawn row never
  counts.
- **The rule's selection** (`recommend.not_counted_once`, read-only on the
  record after the build): repeats 9, 10, 12, 13, 14, 25, 26, 28, 34, 44,
  48, 49, 79, 80, 93, 94, 95 -- the later row of each of the seventeen
  same-side pairs -- and both sides 45 and 46; 106 standing, 87 counted
  once; every earlier row counted; 73, 75, 76 and 78 counted.
- **Where each set-aside row was counted before**: MLB spread measured in
  the window 93, 94, 95 (each +0.00c); restated with a later read 9, 10, 13,
  25, 26, 48; restated with none 14, 34, 44 and unmeasured 79, 80 (both
  "not counted" in the words); MLB total restated with a later read 28, 49,
  restated with none 12, 45, 46. Re-graded: 10 and 26.

### EVERY FIGURE THAT MOVED, before and after *(read-only on the live record, the same instant each side, `now` 2026-09-27T12:00Z)*

| figure (MLB; no other sport moves) | before | after |
|---|---|---|
| closing line, point spread: measured closes counted since 24 Sep (its N; the gate distance "N of 50") | 15 | **12** (93, 94, 95 out) |
| closing line, point spread: closed with no later read, beside the count | 28 | 23 |
| closing line, point spread: older closes worked out again, beside | 23 | 17 |
| closing line, point spread: repeats named beside, counted once | -- | 14 |
| closing line, total: counted since 24 Sep | 1 | 1 |
| closing line, total: no later read / worked out again, beside | 7 / 8 | 4 / 6 |
| closing line, total: repeats named beside | -- | 3 |
| closing line, "Since the repair" window line | 16 | **13** |
| awaiting a close | 3 | 3 |
| "Both sides, no position" (new row, with its N) | -- | **2** (45, 46) |
| "Would not have cleared" (its N; the returns named) | 4 (3.34%, 3.68%, 4.69%, 4.97%) | **2** (3.34%, 4.97%: recs 3 and 56) |
| the kill criterion (`priced.coverage.stopped`), today and on 15 October | stops nothing | stops nothing |
| READINESS criterion 2, recommendations since 7 Sep, point spread / total | 69 / 16 | **55 / 11** |
| the same since 24 Sep, point spread / total | 28 / 2 | 23 / 2 |
| `tools/empty_bar.py`, days nothing cleared | unchanged in every sport and span | |

Every other sport's closing line, re-grade line and count is unchanged (no
pair outside MLB). The two sides add up: MLB point spread 15 + 28 + 23 = 66
closed before, 12 + 23 + 17 counted + 14 repeats = 66 after; total 16 =
1 + 4 + 6 + 3 repeats + 2 both sides. The 2026-09-26 edge read's "9 measured
closes" for MLB spread (READINESS) was read before the window; the 12 of
2026-09-27 00:15Z was the count in the window then, and three of those
twelve were 93, 94 and 95.

### BUILT *(2026-09-27)*

- **One door**: `recommend.counted_once(conn, alias="r")`, a clause beside
  `not_withdrawn` that is `not_withdrawn` and the rule -- no other standing
  row on the same game and market written earlier (stamp, then number) or
  on the other side. `recommend._another_standing_row` is the rule itself;
  `recommend.not_counted_once(conn, *, sport)` lists what the door leaves
  out, each with why (`REPEAT` or `BOTH_SIDES`), made of the same rule, so
  the count and the label cannot disagree. `BOTH_SIDES_LABEL = "Both sides,
  no position"`, the ruling's words.
- **The measurements through it**: `calibration.clv_report` (the counted
  rows, the awaiting count; new keys `repeats` per market and in total,
  `both_sides`, `both_sides_line` {label, n, words}, `set_aside` {n,
  measured, closed, awaiting_close}); so `priced.coverage.stopped`, which
  reads the report; `recommend.regraded`, the "Would not have cleared"
  line; `tools/empty_bar.py`. The words: `language.clv_line(repeats=)` ("...
  3 more repeat an earlier recommendation on the same game and side and are
  counted once, as the earlier one") and
  `language.both_sides_recommendations_line` ("2 recommendations took both
  sides of one game's total on Monday 21 September, so between them they
  hold no position: neither is counted in any figure here, and each stays
  on the record as written"). No club is named, so no subject is read.
- **The record's readers, named**: `audit.RECORD_READERS`, with a reason
  each -- the rule and its other side, item 5's `standing_recommendations`,
  `let_through_by_the_yes_price` (question 9's four labels are on rows as
  written), the closer, the restatement, the near-start reader,
  `views.taken_today`. They read through `not_withdrawn` alone.
- **Guards**: `audit.measurement_door_faults` /
  `check_every_measurement_counts_each_pair_once` (the source: a reader of
  the table that is neither through `counted_once` nor a record reader is
  named by file, function and line; the withdrawn scan now shares its walk,
  `_reads_round`, and accepts `counted_once` as the door it is);
  `audit.pair_counted_faults` / `check_each_pair_counted_once` (the
  arithmetic: the rule worked out again in Python from rows read without
  either door, `_closing_line_rows`, now shared with the withdrawn recount;
  refuses a count, a set-aside tally, a repeat or both-sides count, or the
  re-grade count that differs, naming the rows). Both in the gate's step 2
  (the recount on the record's copy, every sport); the recount also inside
  `views.scorecard`. **The withdrawn recount adds the set-aside tallies
  back**, so every standing row is still accounted for once and a withdrawn
  one still shows. A pair counted twice leaves the withdrawn recount silent
  and is named by the pair recount; a withdrawn row counted is named by the
  withdrawn recount, and the pair recount, which also counts only standing
  rows, sees its count differ too (naming no pair row).
- **The page**: `renderPriced` places `both_sides_line` beside "Withdrawn"
  and before "Would not have cleared", through `requireN`, composing nothing.
- **Plantings** (each ESCAPES on e890de9 -- `git archive HEAD` into the
  scratchpad, this `plant.py` copied over it -- and is CAUGHT here):
  `plant_a_same_side_pair_counted_twice` (a morning and a final pass on one
  side beside a single, all measured, read on 15 October: on the head the
  spread counted 3 at +5.0c and nothing checked; here 2 at +3.0c, the final
  named beside, and with the rule removed the recount names the final row);
  `plant_both_sides_of_one_total_counted` (45/46's shape beside a single: on
  the head the closing line counted 3, the total 2, no label; here 1, the
  label "Both sides, no position" with its N of 2 in plain words, and with
  the rule removed the recount names both rows);
  `plant_a_measurement_that_goes_round_the_counted_once_door` (a count
  through `not_withdrawn` alone in a copy of the package: on the head
  nothing asks; here named by file and function, the withdrawn scan
  silent).
- **Tests**: `test_counted_once.py` (the rule on every shape -- a pair, both
  sides in one second, three on one side, a withdrawn row and the one after
  it, another market of the same game; first by stamp then number; the
  record and the schema unchanged by every read; the closing line, its
  words and label, an open repeat, the kill criterion at 49 counted of 50
  closed, the re-grade line of recs 3/10, 21/26 and 56, the empty-bar day
  that holds only a repeat; both recounts on a pair let through, on a report
  counting a repeat and naming it, and on a report hiding what it set aside;
  the source scan and the register; the renderer).

### RENDERED *(2026-09-27; this tree and e890de9 served against one scratch copy of the record made through `db.back_up_the_live_record`, signed in with a dummy token)*

"Priced, and against the close", MLB, at 1100px and 390px, read as
pictures: no horizontal scroll, no console error, the new row in the same
type and colour as its neighbours and wrapping inside the column at 390px.
On e890de9 the closing line read "Since the repair ... 16", point spread
"15 of 50 ... 28 more ... 23 older ...", total "1 of 50 ... 7 ... 8 ...",
and "Would not have cleared: 4 recommendations ... 3.34%, 3.68%, 4.69% and
4.97%"; here "13", point spread "12 of 50 ... 23 more ... 17 older ... 14
more repeat an earlier recommendation on the same game and side and are
counted once, as the earlier one", total "1 of 50 ... 4 ... 6 ... 3 more
repeat ...", then **"Both sides, no position -- 2 recommendations took both
sides of one game's total on Monday 21 September, so between them they hold
no position: neither is counted in any figure here, and each stays on the
record as written"**, then "Would not have cleared: 2 recommendations ...
3.34% and 4.97%".

### READINGS TAKEN *(each reversible in one line)*

- **Paired after the withdrawals**: a withdrawn row never counts (ruling 1),
  so it is never a pair's member -- NFL 73, 75, 76, 78 count alone, and
  withdrawing a pair's first row makes its second count. (Reversal: the
  rule's inner read drops `not_withdrawn`.)
- **"A pair" read as a group**: every standing row of one game and market
  beyond the first on one side is a repeat, and any group on both sides
  counts zero, the ruling's "count zero" and item 5's "never both sides".
  The record holds only pairs; item 5 stops any new one.
- **"Earlier" is the stamp, then the number**, as `standing_recommendations`
  orders a pair; no pair on the record ties except 45/46, which counts zero
  either way.
- **"Market" is the table's own `market`**, item 5's key, whatever the rung.
- **The re-grade line is a measurement**: it counts recommendations, so
  question 9's four labels stay on the record as written and the line counts
  the labelled rows the rule counts -- rec 3 and rec 56. Rec 10 is its
  pair's later row; rec 26's pair counts as rec 21, which cleared. The
  re-grade tool's selection is not a measurement and still selects all
  four from the rows as written, so it and the written labels agree.
- **Named beside, as every exclusion from the closing line is**: each
  market's repeats in its words (question 12's option B as posed: "names
  the later rows beside the count"), and 45/46 under the ruling's label as
  a row of their own beside "Withdrawn", with their N. The label is derived
  on every read, never stored -- the page could say it without a stored
  label, so no question for the operator.
- **Not measurements, left reading every standing row**: the closer and the
  near-start reader (the record closes every row), item 5's write rule, the
  re-grade selection, the restatement (ran once), the taken rail's edge (a
  lookup, today's cards only, so 45/46 never appear there).
- **The hypothetical ledger counts no recommendation** (it counts
  at-the-line claims, item 6's door), and **no code computes READINESS
  criterion 2**: it was measured by hand; the figures above are for the
  re-read, and READINESS carries a dated note.

### THE LIVE RECORD AFTER THE RELEASE *(none)*

The ruling writes nothing to the record: no schema change, no row, no tool.
The rule is a clause in the readers and the label is derived on every read,
so the record's own rows -- all 36 of the pairs among them -- stay as
written (LAW 3). From the release the Record page counts each pair once and
names 45/46 "Both sides, no position", and the gate recounts it on the
record's copy.

### OPEN

- **For the re-read**: every closing-line count, the "Would not have
  cleared" count and criterion 2 are restated on the rule above; the re-read
  should apply it, and say so, where it counts recommendations by hand.
- **The page does not follow the record** (question 11, default stands): a
  Picks card may still show a pick the record refused. Not re-decided here.

### PROVED *(2026-09-27)*

The three plantings ESCAPE on e890de9 and are CAUGHT here (above). Full
suite with a dummy access token: 1761 passed, 8 skipped, exit 0, the
planting harness inside it included. A first run failed one test,
`test_the_schema_matches.py::test_the_normaliser_is_the_one_door`, because
`audit.py` was edited while that run was going (`inspect.getsource` read
the edited file at the old line number); it passes alone, and the second
run, with nothing edited, is the one above. The gate's two new checks and
the withdrawn recount pass for every sport on a copy of the record made
through `db.back_up_the_live_record` and opened under this tree.

## The priced record, one standing question per forecaster -- built 2026-09-27 *(operator question 14, 1 of 3; the second set of rulings of 2026-09-27)*

"Q14: (B). Every count on the Record page that states a gate distance is
rebuilt per forecaster (per tier for UFC) and per distinct bet, through its
record's standing rule. Three commits, each with a planting that passes on
the unfixed code: priced_scorecard, drift.report, horizon.market_outlook.
They land before the re-read." (`docs/briefs/2026-09-27-rulings-second-set.md`;
"passes on the unfixed code" read, as the brief reads it, as: the planted
violation gets through there and is caught on the fix.) This is the first
of the three: `calibration.priced_scorecard`. **A MEASUREMENT RULE, NOT AN
EDIT**: no row, table, column or schema object changes; nothing is written.

### MEASURED FIRST, read-only *(2026-09-27, `db.read_the_live_record`; newest priced row 700, written 05:48:51Z)*

- **As the page stated it** (one category per market, every settled priced
  row of this blend version, `b1`): NFL point spread 2; MLB moneyline 281,
  "past the 100"; NCAAF moneyline 102, point spread 110 and total 130, each
  "past the 100"; NBA and UFC none. The payload also carried a total `n`
  (NFL 2, MLB 281, NCAAF 342) and `awaiting_outcome` (NFL 49, MLB 6, NCAAF
  20): every unsettled priced row, both forecasters, both passes. Neither
  was painted.
- **Per blind forecaster, per distinct question**: MLB moneyline's 281 are
  149 rows on the statistical model's forecasts (103 distinct questions)
  and 132 on the reasoning pass's (91) -- on 26 September, 139 (96) and 122
  (84). NCAAF moneyline 51 and 51, point spread 55 and 55, total 66 rows on
  64 questions and 64. NFL point spread 1 and 1. No priced row sits on a
  withdrawn forecast.
- **Through the blind record's standing rule** (`standing_row_clause`, the
  latest forecast before the start, a withdrawn one never): the standing
  forecasts' priced rows are exactly the distinct questions above in every
  cell -- no question on the record has a priced superseded pass and an
  unpriced standing one -- and in every cell the distinct questions are
  distinct games (so item 6's game-and-market key would count the same).

### EVERY FIGURE THAT MOVED, before and after *(read-only on the live record, the same instant each side: newest priced row 700; e0ca747 and this tree)*

| sport | figure | before (pooled) | after (per forecaster, per standing question) |
|---|---|---|---|
| MLB | moneyline | **281 settled comparisons, past the 100** | statistical **103, past the 100**; reasoning pass **91 of 100, 9 more** |
| NCAAF | moneyline | **102, past the 100** | statistical 51 of 100, 49 more; reasoning pass 51 of 100, 49 more |
| NCAAF | point spread | **110, past the 100** | 55 of 100, 45 more; 55 of 100, 45 more |
| NCAAF | total | **130, past the 100** | 64 of 100, 36 more; 64 of 100, 36 more |
| NFL | point spread | 2 of 100 | 1 of 100; 1 of 100 |
| NBA, UFC | -- | no row (no priced row) | no row |
| all | payload total `n` (not painted) | NFL 2, MLB 281, NCAAF 342 | gone |
| all | `awaiting_outcome` (not painted) | NFL 49, MLB 6, NCAAF 20 | gone; the standing questions awaiting, per forecaster: NFL 12 and 12, MLB 2 and 3, NCAAF 9 and 9 |

Four "past the 100" lines were pooled; three of them -- every NCAAF one --
are under the gate for each forecaster, and MLB moneyline stays past it for
the statistical model alone, on 103 standing questions (on 26 September it
was 96, under it: the season's last slates moved it). **One priced count on
the Record page is past its hundred: MLB moneyline, statistical, 103.** No
figure is shown beside the gate line on the page -- the row states the count
and the gate, nothing more -- so no number the page prints is withdrawn.

### BUILT *(2026-09-27)*

- **The door**: `priced.forecast.standing_forecasts(conn, *, sport,
  predictor, event_tier=None)` -- this version's priced row on each standing
  question of one blind forecaster, settled or not, through
  `calibration.standing_row_clause(False)` (the blind record's own rule,
  unfiltered by factor set, as `calibration.resolved` asks it). The
  forecaster is required and refused by name (`priced.forecast.PooledCount`,
  "never pooled") unless it is one of `BLIND_FORECASTERS`; UFC must name one
  declared card and a sport that splits nowhere may name none. Each row
  carries its market as the record names it (the prop type, or the market),
  its forecaster, its question's keys and its card, read off its own bout.
  `bet_of` (the question without its forecaster), `count_of_bets` and
  `settled` are the one key and the one predicate the counts share.
- **The builder**: `calibration.priced_scorecard` asks the door once per
  card and forecaster and builds one category per market, card and
  forecaster where something has settled (as before, a market with nothing
  settled has no row), statistical first; each carries `predictor`,
  `event_tier`, `filters`, `category`, `category_label`, `distinct_bets`,
  `forecasters_counted`, `tiers_counted`, the three scores on its own rows
  and the gate line on its own count. No total `n`, no `awaiting_outcome`.
- **The guard**: `calibration.assert_no_pooled_priced_counts`, inside the
  builder (so `/api/scorecard` answers 500 rather than serve a pool; a test
  asserts it). It runs `assert_no_merged_categories` on the priced payload
  first -- nothing did until today -- then refuses by name: more rows than
  distinct bets; rows of another forecaster, or another card, than the one
  named; no blind forecaster named; a score on other questions than the
  count; a gate line stating another count; a category of another record;
  and a total or a pooled awaiting count.
- **The gate**: `audit.check_the_priced_record_is_never_pooled` builds every
  sport's priced record on the record's copy and turns the guard's refusal
  into a failure by name (gate step 2: "the priced record counts one
  standing question per forecaster"). Until today the gate built the Record
  page for NFL alone (`check_forecasters_are_never_merged`), so the MLB and
  NCAAF counts were never built by it. Passes on the live record,
  read-only.
- **Words**: `language.priced_category_label` -- "moneyline blended with the
  price, statistical" / "..., reasoning pass", a UFC row naming its card --
  the market in `market_words`, the words the rest of the page uses. The
  renderer (`renderPriced`) places the label and requires each row's N; the
  `requireN` on the whole payload went with the total it read.
- **Plantings** (`tools/guards/plant.py`, in the harness and in
  `test_guards.py`'s list): `plant_a_priced_count_pooling_two_forecasters`
  (26 September's MLB moneyline payload: both forecasters in one count
  naming none, both under one forecaster's name, one forecaster's two
  passes, a gate line "past the 100" beside a count under it, scores on
  other questions, a total `n` and a pooled awaiting count -- seven shapes,
  each refused by name, the honest pair passing) and
  `plant_a_priced_question_counted_three_times` (a scratch world, every row
  through the triggers and the priced forecaster's own writer: one MLB game
  forecast by the statistical model's morning and final pass and by the
  reasoning pass, all priced and settled; the builder counts 1 and 1, each
  row naming its forecaster; the count as it stood swapped back in as the
  door -- every forecaster, and asking the forecaster but one row per pass --
  is refused by the builder, and the first by the gate's check naming MLB).
- **Tests** (`test_priced.py`): one standing question per forecaster (the
  final pass's row is the one scored), a withdrawn final pass leaving the
  morning pass standing, the door's refusals, every pooled shape refused by
  name, the count as it stood refused by the builder, the gate and the API
  (500), and UFC counted per card -- a door that stopped filtering by card
  refused off the rows' own cards. All six fail on e0ca747.

### RENDERED *(2026-09-27; the browser suite's own world -- `seed_league` and `_build_world` -- on a scratch file, given a reasoning-pass forecast, priced and settled, beside each of its eight settled priced statistical forecasts; served by this tree and by e0ca747 with the suite's test token; never the live app)*

"Priced, and against the close", NFL, at 1100px and 390px, read as
pictures (`scratchpad/q14/priced/priced-{after,before}-{1100,390}.png`): on
e0ca747 one row, "point spread -- 16 of 100 settled comparisons · 84 more";
here two, "point spread blended with the price, statistical -- 8 of 100
settled comparisons · 92 more" and "point spread blended with the price,
reasoning pass -- 8 of 100 ...", in the same type as their neighbours,
wrapping inside the column at 390px. No horizontal page scroll and no
console error at either width, on either tree.

### READINGS TAKEN *(each reversible in one line)*

- **"Per forecaster" is the blind forecaster whose forecast the priced row
  blended.** The priced forecaster is one forecaster by name, but each of
  its rows is the blend of one blind forecast, and the operator's question
  counted them that way ("139 on the statistical model's ..., 122 on the
  reasoning pass's"). Each row keeps `forecaster: "priced"` and gains
  `predictor`.
- **"Its record's standing rule" is the blind record's**
  (`standing_row_clause`): a priced row belongs to one blind forecast, and
  the orchestrator's brief names that rule. So a question whose standing
  forecast carried no price is not counted even if a superseded pass of it
  was (none on the record). The other reading -- the latest priced row
  among a question's forecasts -- would count such a question; it counts
  the same today.
- **A distinct bet is the blind question** (game, market, subject, rung),
  without its forecaster: two standing rungs of one game are two questions
  in the blind curve beside this one, each priced at its own line. Item 6's
  key, game and market, would refuse that shape; it counts the same on the
  record today (every cell's questions are distinct games).
- **A category appears where something has settled**, as it did: a market
  whose priced rows are all awaiting has no row, and neither has a
  forecaster with nothing settled in a market the other has.
- **The unpainted pooled counts were removed, not split**: the total `n`
  and `awaiting_outcome` had no reader; the guard refuses both by name.

### THE LIVE RECORD AFTER THE RELEASE *(none)*

Nothing is written. The counts are computed on every read, so from the
release the Record page states the per-forecaster counts above, and the
gate builds every sport's priced record on the record's copy.

### OPEN

- **"b1" in the panel's heading** is the blend version's identifier,
  painted raw (`priced-version`), on every sport's Record page since
  2026-09-07 -- a PLAIN WORDS matter, found by the render; not this
  question's, not changed.
- **Steps 2 and 3 of question 14** (`drift.report`, `horizon.market_outlook`)
  follow in their own commits.

### PROVED *(2026-09-27)*

Both plantings ESCAPE on e0ca747 (`git archive HEAD` into the scratchpad;
this tree's `plant.py` loaded against it): "nothing checks the priced
record's counts", and the planted world counted as one moneyline row of 3,
"3 of 100 settled comparisons". Both are CAUGHT here. **Each part is
needed**, shown on three copies of this tree with one part neutralised: the
guard a no-op, both plantings escape; the door without the standing rule
and the forecaster, the world planting escapes (the builder refuses its
honest world); the gate's check a no-op, the world planting escapes on its
gate probe. Full suite with a dummy access token: 1775 collected, 1767
passed, 8 skipped, exit 0, the planting harness inside it included; the
harness alone 320/320; `audit.prose_reaching_the_raw_side()` is `[]`. The
gate's new check passes on the live record, read-only.

## Where the line went, one bet per forecaster -- built 2026-09-27 *(operator question 14, 2 of 3; the second set of rulings of 2026-09-27)*

"Q14: (B). Every count on the Record page that states a gate distance is
rebuilt per forecaster (per tier for UFC) and per distinct bet, through its
record's standing rule. Three commits, each with a planting that passes on
the unfixed code: priced_scorecard, drift.report, horizon.market_outlook.
They land before the re-read." This is the second: `drift.report`, the media
line's drift and its gate of fifty, which the Record page states twice -- the
learning panel's line under each market ("When the model disagreed by 5% or
more, the market moved toward it 33% of the time over 79 games") and the
"What else is still counting" rows ("Where the line went after point spread
· 12 of 50 pairs"). **A MEASUREMENT RULE, NOT AN EDIT**: no row, table,
column or schema object changes; nothing is written.

### MEASURED FIRST, read-only *(2026-09-27, `db.read_the_live_record`; newest prediction 3108 at 05:49:14Z, newest snapshot 3317)*

- **As the page stated it**: one count per market TYPE of every forecast
  with both looks at the line that disagreed with the first by five points,
  the statistical model's by a default argument. MLB moneyline 79, past the
  fifty ("33% ... over 79 games"); NCAAF point spread 79 (28%), moneyline 57
  (28%), total 62 (19%), each past it; NFL point spread 4 of 50; every
  other market 0. Each prop row of the learning panel showed the count of
  every prop type at once (`market_type` 'prop'), and the gate list one row,
  "Where the line went after prop". UFC's cards were one count per market.
  The payload also carried a total `n` across the markets (NFL 4, MLB 79,
  NCAAF 198), never painted.
- **Per forecaster, per question, through the standing rule**: MLB
  moneyline's 79 pairs are on 61 questions, and 50 of them are the
  question's standing forecast (on 26 September: 75, 58 and 48 -- the
  question as asked). NCAAF point spread 79 pairs on 78 standing questions,
  and those are **66 games**: twelve games were asked at two rungs, the
  morning pass's (1 September) and a later pass's (5 September), both
  standing questions, and five of the twelve games' two pairs point opposite
  ways. NCAAF moneyline 57 pairs on 50 questions, 49 standing; total 62 on
  54, 54 standing; NFL point spread 4 pairs on 3 standing questions and 2
  games (one of the eight forecasts with both looks is withdrawn). MLB's one
  prop forecast with both looks (hits) is withdrawn.
- **The reasoning pass** (never painted; counted by the door when named),
  one per bet: MLB moneyline 41 (12 toward), NCAAF point spread 44,
  moneyline 41, total 48, NFL point spread 1 -- under the fifty everywhere.
  Counted as the old code counted, MLB moneyline would have been 64.
- **UFC** has first looks and no second: 0 on every card.

### EVERY FIGURE THAT MOVED, before and after *(read-only on the live record, the same instant each side; 29811e0 and this tree; statistical, as the page paints)*

| sport | market | before (every forecast with both looks) | after (one bet per forecaster, standing) |
|---|---|---|---|
| MLB | moneyline | **79 pairs, past the fifty: "moved toward it 33% of the time over 79 games"** | **50 pairs, at the fifty: "24% of the time over 50 games"** |
| NCAAF | point spread | **79: "28% ... over 79 games"** | **65: "22% ... over 65 games"** |
| NCAAF | moneyline | **57: "28% ... over 57 games"** | **49 of 50 pairs, 1 more; no direction** |
| NCAAF | total | **62: "19% ... over 62 games"** | **54: "15% ... over 54 games"** |
| NFL | point spread | 4 of 50 | 2 of 50 |
| NFL, MLB | props | one row, "prop", 0 of 50, and that pooled count on every prop row of the learning panel | one row per prop type the record forecast, 0 each |
| UFC | moneyline, rounds, distance | 0 of 50, one line per market | 0 of 50 on each card, three lines per market, each naming its card |
| all | payload total `n` (not painted) | NFL 4, MLB 79, NCAAF 198 | gone |

**One direction on the Record page is withdrawn: NCAAF moneyline**, 49 of
50 once each game is counted once. Three stay past the fifty on smaller
counts and every stated share moves: MLB moneyline 33% to 24%, NCAAF point
spread 28% to 22%, NCAAF total 19% to 15%. **MLB moneyline sits exactly at
the fifty** (the page reports a direction from fifty); one withdrawn or
superseded standing forecast would take it back under.

### BUILT *(2026-09-27)*

- **The door**: `drift.standing_pairs(conn, *, sport, market, predictor,
  event_tier=None)`. The forecaster is required and refused by name
  (`drift.PooledCount`, "never pooled") unless it is one of the two
  (`drift.FORECASTERS`, read from `config.FORECASTER_LABELS`); the market is
  one the sport declares, as the record names it -- a prop by its own type,
  'prop' refused ("every prop type in one count"); UFC must name one
  declared card and a sport that splits nowhere may name none. The
  candidates are the forecaster's STANDING forecasts
  (`calibration.standing_row_clause(False)`, the blind record's own rule),
  with their looks joined beside them; ONE PER BET (`drift.bet_of`: the game
  and market, and the player for a prop), the bet's last standing forecast
  written before the start, the id breaking a tie; the bet is counted if
  that forecast has both looks and disagreed by five points. Each pair
  carries its forecaster, market, bet keys and its card read off its own
  bout. `drift.pairs`, the count as it stood, is gone.
- **The builder**: `drift.report(conn, *, sport, market, predictor,
  event_tier=None)` -- no default forecaster -- asks the door once and
  builds one category: `record`, `market`, `predictor`, `event_tier`,
  `filters`, `category`, `category_label`, `n`, `distinct_bets`,
  `forecasters_counted`, `tiers_counted` (counted off the pairs beside the
  door), the progress line and the sentence, and the direction only past
  the fifty. `views.drift_report` builds one per declared market the record
  has forecast (in the sport's own order), card and painted forecaster
  (`drift.PAGE_FORECASTERS`, the statistical model's) under `categories`,
  and no total; `views.learning` puts a list of them on each market's row
  (`drift`, one per card), replacing `drift_words` and `drift_n`.
- **The guard**: `drift.assert_no_pooled_drift_counts`, inside both
  builders -- so `/api/scorecard` and `/api/learning` answer 500 rather than
  serve a pool (tests assert both through TestClient; `/api/learning` gained
  the named 500 `/api/scorecard` already had). It runs
  `calibration.assert_no_merged_categories` on the drift categories first
  (nothing did), then refuses by name: a category of another record; one
  naming no forecaster, or counting another's pairs; one counting another
  card's pairs, or naming a card in a sport that has none; one category
  twice in a payload; more pairs than distinct bets; a direction below the
  gate; a progress line or a sentence stating another count than its own;
  and a total.
- **The gate**: `audit.check_the_drift_record_is_never_pooled` builds the
  gate list and the learning panel for every sport on the record's copy
  (gate step 2: "where the line went counts one bet per forecaster"). The
  gate built NFL's gate list alone, inside the first sport's Record page,
  and no learning panel. Passes on the live record, read-only.
- **Words**: `language.drift_category_label` ("moneyline, Fight Night,
  statistical", the market in `market_words`), so a gate row reads "Where
  the line went after point spread, statistical", beside "A correction for
  point spread, statistical"; `language.drift_line` carries the sentences
  that were composed in `drift.py`, a UFC line leading with its card, and
  past the fifty "over N games" (true now: one per game) or "player lines"
  for a prop. The renderer places each line of a market's row and requires
  each its N.
- **Plantings** (`tools/guards/plant.py`, in the harness and in
  `test_guards.py`'s list): `plant_a_drift_count_pooling_passes_and_forecasters`
  (the learning panel's MLB moneyline of 26 September and nine more shapes:
  a question's two passes, both forecasters naming none, both under one
  name, a sentence past the fifty beside a count under it, a direction on
  48 pairs, every prop type in one count, one market on two rows, UFC's
  cards in one count, a card counting another's bouts, a total -- each
  refused by name, the honest payloads passing) and
  `plant_a_drift_game_counted_twice` (a scratch world, every row through the
  snapshot triggers: one MLB game forecast by the statistical model's
  morning and final pass and by the reasoning pass, and one NCAAF game
  asked at two rungs by two passes; the gate list and the learning panel
  count one bet each, naming the forecaster; the count as it stood swapped
  back in as the door -- asking the forecaster, asking nobody in
  particular, and the standing rule without the bet -- is refused by both
  builders and by the gate's check naming MLB).
- **Tests** (`test_drift.py`): ten new, and the six that were there moved
  to the new door and to one game per pair (they built five "pairs" on one
  game). All ten new ones fail on 29811e0.

### RENDERED *(2026-09-27; the browser suite's own world -- `seed_league` and `_build_world` -- on a scratch file, given a second look near the start for each of its twelve statistical NFL forecasts with a first look, and a final pass with both looks on four early point spread questions; served by this tree and by 29811e0 with the suite's test token; never the live app)*

Read as pictures at 1100px and 390px
(`scratchpad/q14/drift/drift-{before,after}-{nfl,ufc}-{other-gates,learning}-{1100,390}.png`).
On 29811e0 the gate list read "Where the line went after point spread · 12
of 50 pairs" and "... after prop · 0 of 50 pairs", and the learning panel's
point spread line "12 of 50 disagreements"; here "Where the line went after
point spread, statistical · 8 of 50 pairs", one row per prop type the world
forecast, each naming its forecaster in the type of the correction rows
above them, and the learning panel 8. UFC's learning panel has three lines
under each market, "Numbered card: 0 of 50 ...", "Fight Night: ...",
"Contender Series: ...", wrapping inside the column at 390px. No horizontal
page scroll and no console error at either width, on either tree. (UFC's
gate list is hidden in this world: it forecasts no UFC bout.)

### READINGS TAKEN *(each reversible in one line)*

- **A distinct bet is a game and market -- and the player, for a prop** --
  item 6's key, not the blind question (step 1's, `priced.forecast.bet_of`).
  Here they differ on the record: NCAAF point spread's 78 standing
  questions are 66 games, and a drift pair measures the one published line
  of a game moving, so two rungs are that movement counted twice (and "over
  78 games" would be false). Item 6's own test world is exactly this shape
  and counts it as one bet. Reversed by adding the rung to `drift.bet_of`
  (NCAAF point spread 78, NFL point spread 3).
- **The bet's pair is its last standing forecast's**, and an earlier rung is
  not its fallback: if the last word on the game has no second look, or
  agreed with the line, the bet has no disagreement to count. The other
  reading -- the last standing forecast that has a pair -- counts NCAAF
  point spread 66 (15 toward) and every other cell the same. Reversed in
  one line in `standing_pairs` (keep only paired rows before choosing).
- **A question whose standing forecast has no second look is not counted**,
  even if a superseded pass had one: the ruling's "through its record's
  standing rule", and the question's own contrast of 58 questions with 48
  standing rows. Eleven MLB moneyline questions of the statistical model
  (nine of the reasoning pass's) and one NCAAF moneyline question lose
  their pair this way: each has one only on a superseded pass.
- **The page paints the statistical model's drift, as it always did**
  (`drift.PAGE_FORECASTERS`); the ruling rebuilds the counts the page
  states and asks for none to be added. Adding "llm" paints the reasoning
  pass's rows beside them, each naming its forecaster.
- **The gate list lists the declared markets the record has forecast**, in
  the sport's order (it was every `market_type` in name order). A name the
  sport does not declare has no row: 32 NFL prop forecasts of 29 August
  (fs1) carry no prop type; they have a first look and no second, so no
  pair is lost today, and the door cannot count them.
- **The unpainted total `n` was removed, not split**; the guard refuses one.

### THE LIVE RECORD AFTER THE RELEASE *(none)*

Nothing is written. The counts are computed on every read, so from the
release the Record page states the counts above, and the gate builds both
panels for every sport on the record's copy.

### OPEN, found by this step *(2026-09-27)*

- **The correction gates on the same page count every settled row.**
  `views.corrections_report` ("A correction for moneyline, statistical · 350
  settled", in "What else is still counting") counts every settled forecast
  of a market type and forecaster -- a question's passes each, every prop
  type as "prop", UFC's cards as one -- while the correction's own count on
  the learning panel (`calibration.resolved`, standing) says 246 for the
  same category. Measured read-only: MLB moneyline 350 against 246 standing
  (reasoning pass 188 against 134), point spread 292 against 188, total 292
  against 199 (173 against 127), props 97 against 78; NCAAF moneyline 194
  against 139, point spread 189 against 182, total 195 against 141; NFL
  point spread "49 of 50" against 30, props 80 against 57, total 4 against
  2 for each forecaster; **UFC distance, moneyline and rounds "85 settled",
  past the fifty, against 49 standing -- under it** (reasoning-pass
  moneyline 63 against 49), and the learning panel's UFC correction line
  pools the cards too. A count on the Record page stating a gate distance,
  outside the three commits the ruling names: for the operator, whether it
  falls under question 14's first sentence or needs its own ruling. Not
  built here.
- **Two keys for "a distinct bet" in one ruling's work**: the priced record
  (1 of 3) counts the blind question, this step the game and market. They
  count the same on the priced record today; the operator may prefer one.
- **Step 3 of question 14** (`horizon.market_outlook`) follows in its own
  commit.

### PROVED *(2026-09-27)*

Both plantings ESCAPE on 29811e0 (`git archive HEAD` into the scratchpad;
this tree's `plant.py` loaded against it): "nothing checks a drift count",
and the planted world counted as the page stated it, MLB moneyline 2 and
NCAAF point spread 2 on the gate list and the learning panel, for one game
each. Both are CAUGHT here, each of the payload planting's ten shapes by
its own reason (read one by one, none by a neighbour's). **Each part is
needed**, shown on three copies of this tree with one part neutralised: the
guard a no-op, both plantings escape; the door without the standing rule and
the bet (one pair per forecast), the world planting escapes (the builder
refuses its honest world); the gate's check a no-op, the world planting
escapes on its gate probe. Full suite with a dummy access token: 1777
passed, 8 skipped, exit 0, the planting harness inside it included; the
harness alone 322/322; `audit.prose_reaching_the_raw_side()` is `[]`. The
gate's new check passes on the live record, read-only (newest prediction
3108, the instant measured).

## The line beside each blind curve, its curve's own count -- built 2026-09-27 *(operator question 14, 3 of 3; the second set of rulings of 2026-09-27)*

"Q14: (B). Every count on the Record page that states a gate distance is
rebuilt per forecaster (per tier for UFC) and per distinct bet, through its
record's standing rule. Three commits, each with a planting that passes on
the unfixed code: priced_scorecard, drift.report, horizon.market_outlook.
They land before the re-read." This is the third: `horizon.market_outlook`,
the line under each statistical curve in the Record page's "Record by
category" table ("350 of 100 · ~367 expected · season ends 09-27"), and with
it `horizon.llm_routed_off_outlook`, the reasoning pass's "final count" line
in a market it no longer asks -- both counted by `_written_so_far`. **A
MEASUREMENT RULE, NOT AN EDIT**: no row, table, column or schema object
changes; nothing is written.

### MEASURED FIRST, read-only *(2026-09-27, `db.read_the_live_record`; newest prediction 3108 at 05:49:14Z)*

- **As the page stated it**: one query per market (`_written_so_far`) of
  every forecast of the market this season that was not withdrawn -- a
  question's morning and final pass each -- for the statistical model by a
  default argument, and for UFC every card: one count beside each card's
  curve. MLB moneyline "350 of 100 · ~367 expected" beside a curve of 246
  (on 26 September, the question as asked: 330 beside 233); point spread
  and total "292 of 100" beside 188 and 199; NCAAF moneyline 194 beside 139,
  total 195 beside 141, point spread 189 beside 182; NFL point spread 49
  beside 30; each UFC card's moneyline, rounds and distance curve "85 of 100
  · ~302 expected" beside curves of 0 (Numbered card), 39 (Fight Night) and
  10 (Contender Series) -- and the reasoning pass's rounds and distance
  "14 of 100 · ... the final count" beside curves of 0 on the Numbered and
  Contender cards.
- **Per forecaster, per card, per standing question** (the blind record's
  rule, `calibration.standing_row_clause`, with the curve's own filters):
  every settled count equals its curve's n -- by construction, since the
  curve counts the same rows. This season's standing questions written, the
  pace's numerator: MLB moneyline 261 of 365 rows, spread 203 of 307, total
  214 of 307; NCAAF spread 185 of 192, moneyline 142 of 197, total 144 of
  198; NFL point spread 42 of 61, total 18 of 34, the props 10 to 13 of 15
  to 21. UFC by card: Fight Night 41 standing over 3 cards written on,
  Contender Series 15 over 3, Numbered card none; of the 14 cards still to
  come, 6 are Fight Nights, 3 Contender Series and 5 numbered.
- **The reasoning pass** (the page paints no projection beside its curve in
  a market it is still asked, and did not before): MLB moneyline 134 (~146
  expected), total 127 (~140); NCAAF spread 55, moneyline 57, total 64; NFL
  1, 1 and 2; UFC moneyline Fight Night 39, Contender Series 10.
- **The two readings of a distinct bet** (read off the new door): the blind
  question -- game, market, subject and rung -- and item 6's game and market
  count the same everywhere but where one game was asked at two rungs: NFL
  point spread 30 questions on 17 games, NCAAF point spread 182 on 137, MLB
  total 199 on 188 (reasoning pass 127 on 119). See READINGS TAKEN.

### EVERY FIGURE THAT MOVED, before and after *(read-only on the live record at the same instant each side -- newest prediction 3108; cdaf03c and this tree; the line under each statistical curve unless named)*

| sport | category (its curve's N) | before | after |
|---|---|---|---|
| MLB | moneyline (246) | **350 of 100 · ~367 expected** | **246 of 100 · ~258 expected** |
| MLB | point spread (188) | **292 of 100 · ~310 expected** | **188 of 100 · ~200 expected** |
| MLB | total (199) | **292 of 100 · ~310 expected** | **199 of 100 · ~212 expected** |
| MLB | hits (31) | 40 of 100 · ~43, cannot clear | 31 of 100 · ~33, cannot clear |
| MLB | home runs, retired (31) | 36 of 100, the final count | 31 of 100, the final count |
| MLB | batter strikeouts (9) | 12 of 100 · ~14, cannot clear | 9 of 100 · ~11, cannot clear |
| MLB | strikeouts (7) | 9 of 100 · ~11, cannot clear | 7 of 100 · ~9, cannot clear |
| NCAAF | point spread (182) | 189 of 100 · ~1597 | 182 of 100 · ~1539 |
| NCAAF | moneyline (139) | **194 of 100 · ~1639** | **139 of 100 · ~1180** |
| NCAAF | total (141) | **195 of 100 · ~1066** | **141 of 100 · ~775** |
| NFL | point spread (30) | **49 of 100 · ~537** | **30 of 100 · ~366** |
| NFL | total (2) | 4 of 100 · ~276 | 2 of 100 · ~146 |
| NFL | passing yards (7) | **10 of 100 · ~154** | **7 of 100 · ~95, CANNOT CLEAR** |
| NFL | rushing yards (8) | **11 of 100 · ~131** | **8 of 100 · ~88, CANNOT CLEAR** |
| NFL | passing touchdowns (7) | **10 of 100 · ~130** | **7 of 100 · ~87, CANNOT CLEAR** |
| NFL | receiving yards (8) | 9 of 100 · ~153 | 8 of 100 · ~112 |
| NFL | receptions (8) | 13 of 100 · ~181 | 8 of 100 · ~104 |
| UFC | moneyline, rounds, distance: Numbered card (0) | **85 of 100 · ~302** | 0 of 100, no rate this season: no line painted |
| UFC | the same, Fight Night (39) | **85 of 100 · ~302** | **39 of 100 · ~121** |
| UFC | the same, Contender Series (10) | **85 of 100 · ~302** | **10 of 100 · ~25, CANNOT CLEAR** |
| UFC | rounds and distance, reasoning pass: Numbered card and Contender Series (0) | 14 of 100, the final count | 0 of 100, the final count |

Unchanged: NFL moneyline (17 of 100 · ~273, its standing questions were
every row), the UFC reasoning pass's Fight Night rounds and distance (14,
final), MLB's reasoning pass hits (2) and home runs (6), and every market
with nothing written (NBA, MLB total bases, NFL passing touchdowns' reasoning
pass). **Four gates the page called reachable cannot clear on their own
counts**: NFL passing yards, rushing yards and passing touchdowns, and the
UFC Contender Series card in each market. Every count that stays past the
100 -- MLB moneyline, spread and total, NCAAF spread, moneyline and total --
is now the N printed beside it in the same row.

### BUILT *(2026-09-27)*

- **The door**: `horizon.standing_questions(conn, *, sport, market,
  predictor, event_tier=None)`. The forecaster is required and refused by
  name (`horizon.PooledCount`, "never pooled") unless it is one of the two
  (`horizon.FORECASTERS`, from `config.FORECASTER_LABELS`); the market is one
  the sport declares, as the record names it ('prop' refused, "every prop
  type in one count"); UFC must name one declared card and a sport that
  splits nowhere may name none. The rows are that forecaster's STANDING
  forecasts, settled or not (`calibration.standing_row_clause(False)`, the
  filters `calibration.resolved` asks for the curve), each with its
  season, slate (`g.week`), question keys and its card read off its own
  bout.
- **The counts**: `_written_so_far(rows, season)` counts the door's rows --
  settled, every season, the curve's n; written, this season's standing
  questions; slates, the distinct `week`s they were written on -- in place
  of its own query. `horizon.bet_of` (the blind question: game, market,
  subject, rung), `count_of_bets` and `settled` are the shared helpers;
  each outlook carries `record`, `predictor`, `event_tier`,
  `distinct_bets`, `distinct_bets_written`, `forecasters_counted`,
  `tiers_counted` and `written_before`, counted beside the door.
- **The builders**: `market_outlook(conn, sport, market, *, predictor,
  event_tier=None, season=None)` -- no default forecaster -- and
  `llm_routed_off_outlook(..., *, event_tier=None)` ask the door once; the
  retired branch reads the same rows. `slates_remaining` takes the card, so
  a UFC card's pace is multiplied by that card's slates to come (every card's
  14, for a Contender Series rate, would have been the unit mismatch the
  ONE UNIT row is about, one level down). `expected_from` works the
  expectation out again from an outlook's own counts.
- **Words**: `language.market_outlook_line` (composed inside `horizon.py`
  until this date, in the same words), with "nothing written in this market
  this season" for a count from an earlier season and no rate, never "yet"
  (item 6's prover found the at-the-line line denying the claims it
  counted); `horizon.outlook_words` is the one composition the builder
  writes and the guard reads again (the retired and routed-off lines keep
  their own functions).
- **The table's builder**: `calibration.blind_categories(conn, *, sport)`,
  taken out of `scorecard`, builds every blind curve with the outlook beside
  it -- the statistical model's on each card, the reasoning pass's final
  count where it is routed off -- and marks each `record: rung`.
- **The guard**: `calibration.assert_no_pooled_outlooks`, inside
  `blind_categories` -- so `/api/scorecard` answers 500 rather than serve a
  pool (a test asserts it through TestClient). It runs
  `assert_no_merged_categories` first, then refuses by name, for each
  outlook: one filed from another record; one naming another forecaster or
  card than its curve's, or none; one counting another forecaster's rows or
  another card's bouts; a settled count, or a pace, on more rows than
  distinct questions; a settled count that is not the curve's n ("two counts
  of one record"); an expectation that is not its own counts' arithmetic;
  and a line stating another count than its own.
- **The gate**: `audit.check_the_blind_outlook_is_never_pooled` builds every
  sport's table on the record's copy (gate step 2: "the blind record's
  outlook counts its curve's standing questions"). The gate built NFL's
  alone, inside the first sport's Record page. Passes on the live record,
  read-only. `audit.horizon_unit_faults` now reads the rate's unit off the
  door (`g.week`) and the count (`week`), as well as `slates_remaining`,
  since `_written_so_far` is no longer a query (the planting of 2026-09-05
  and its test still fire; a test proves the new halves do).
- **The renderer** requires each outlook's N (`requireN`) and its comment
  no longer says the outlook counts only this season.
- **Plantings** (`tools/guards/plant.py`, in the harness and in
  `test_guards.py`'s list): `plant_a_blind_outlook_counting_superseded_passes`
  (the MLB moneyline line of 27 September and eleven more shapes: a
  question's two passes in the settled count, an outlook saying nothing of
  how many questions it holds, 350 beside a curve of 246, a pace from every
  pass, an expectation not its own arithmetic, a line past its counts, no
  forecaster, both forecasters under one name, the statistical line beside
  the reasoning pass's curve, an at-the-line outlook, UFC's three cards
  beside a Numbered-card curve of 0, a card counting another's bouts -- each
  refused by its own reason, the honest payloads passing) and
  `plant_a_blind_outlook_game_counted_twice` (a scratch world, every row
  through the schema's own rules: one MLB game forecast by the statistical
  model's morning and final pass and by the reasoning pass, one UFC bout on
  a Fight Night card forecast twice, one on a Contender Series card, a
  Numbered card still to come; each outlook states its curve's count; the
  count as it stood swapped back in as the door -- asking the forecaster,
  asking nobody in particular, and each card's standing rows under one
  card's name -- is refused by the Record page's builder for MLB and UFC and
  by the gate's check naming MLB).
- **Tests** (`test_outlook.py`, new): nine, all failing on cdaf03c. The
  existing calls in `test_rulings.py` and `test_retired.py` name the
  forecaster.

### RENDERED *(2026-09-27; the browser suite's own world -- `seed_league` and `_build_world` -- on a scratch file, served by this tree and by cdaf03c with the suite's test token and `GRIDIRON_SEASON=2025` so the world's NFL season has a pace; given a final pass on six settled point spread questions, and three UFC cards with settled statistical moneyline forecasts, one bout forecast twice, and a Fight Night, a Contender Series and a Numbered card still to come; never the live app)*

Read as pictures at 1100px and 390px
(`scratchpad/q14/outlook/outlook-{before,after}-{nfl,ufc}-{1100,390}.png`,
with crops of the phone width). On cdaf03c NFL "point spread, statistical"
read "14 of 100 · ~26 expected" beside N 8, and every UFC moneyline card
"4 of 100 · ~10 expected · ... THIS GATE CANNOT CLEAR THIS SEASON" beside N
0, 2 and 1; here point spread reads "8 of 100 · ~16 expected" beside 8, the
Fight Night row "2 of 100 · ~4 expected", the Contender Series row "1 of 100
· ~2 expected", and the Numbered card row no line (nothing written on it
this season). Every other row reads as before. At 390px the line wraps
inside the category column as it did; no horizontal page scroll and no
console error at either width, on either tree.

### READINGS TAKEN *(each reversible in one line)*

- **A distinct bet is the blind question** -- game, market, subject and rung
  (`horizon.bet_of`, the priced record's key) -- not item 6's game and
  market (step 2's key). The outlook's count must be the curve's n, and the
  blind curve counts questions: the standing rule's own words are that one
  subject asked at two rungs is two questions. Counting games would put "17
  of 100" under an NFL point spread curve of 30, and "137" under NCAAF's 182
  -- the two counts of one record the ruling removes -- unless the curve
  changed too, which is not among the three commits. Reversed in
  `horizon.bet_of`; the guard would then refuse every such row until the
  curve counted games as well.
- **The pace counts this season's standing questions and the settled count
  every season's**, as item 6's at-the-line outlook does: the settled count
  is what the gate counts and what the curve beside it says; the pace is a
  rate for this season's remaining slates. The page hides a line with no rate
  this season (as it always did), and the words say "this season" if one
  were shown.
- **A UFC card's pace is multiplied by that card's slates to come**, not
  every card's. Reversed by passing no card to `slates_remaining` in
  `market_outlook` (Fight Night ~121 would be ~230, Contender Series ~25
  ~80, and the Contender card's "cannot clear" would read reachable).
- **The reasoning pass's curve carries no projection in a market it is
  still asked**, as before: the ruling rebuilds the counts the page states
  and adds none. The old reason in the code ("one projection covers both")
  is gone -- the two forecasters' counts differ (MLB moneyline 246 and 134)
  -- and the comment says why instead. Adding it is one `elif` in
  `blind_categories`; the door and the guard already count it (MLB
  moneyline 134 of 100 · ~146, UFC Contender Series 10, cannot clear).
- **The words are the page's own**, moved into `language.py` unchanged but
  for "this season"; "season ends 09-27" keeps its month-day form.

### THE LIVE RECORD AFTER THE RELEASE *(none)*

Nothing is written. The counts are computed on every read, so from the
release the Record page states the lines above, and the gate builds every
sport's table on the record's copy.

### OPEN, found by this step *(2026-09-27)*

- **The at-the-line UFC outlook multiplies one card's pace by every card's
  slates.** `horizon.at_the_line_outlook` (item 6) paces one card's bets,
  as its curve counts them, and asks `slates_remaining` for the sport's
  every card -- 14 on 27 September, where a Contender Series pace has 3 to
  come. It projects nothing today -- no UFC claim has been written at the
  venue's line, so every card's line says there is no rate (read-only, 27
  September) -- but it is the same unit mismatch one level down the first
  time one is. Passing the card is one argument;
  it is item 6's record and was not named by this ruling, so it is not
  changed here: for the operator.
- **Two keys for "a distinct bet" across question 14's three commits** (the
  blind question for the priced record and this outlook, the game and
  market for the line's drift): they differ on the record where a game was
  asked at two rungs (NFL point spread 30 questions on 17 games, NCAAF 182
  on 137, MLB total 199 on 188). Here the key is forced by the curve; the
  operator may prefer one key for all three.
- **The correction gates** (step 2's OPEN entry) still count every settled
  row; untouched here.

### PROVED *(2026-09-27)*

Both plantings ESCAPE on cdaf03c (`git archive HEAD` into the scratchpad;
this tree's `plant.py` loaded against it): "nothing checks a blind outlook",
and the planted world stated (curve, outlook) MLB (1, 2) and each UFC card
(0, 3), (1, 3), (1, 3). Both are CAUGHT here, each of the payload planting's
twelve shapes by its own reason (read one by one, none by a neighbour's).
**Each part is needed**, shown on three copies of this tree with one part
neutralised: the guard a no-op, both plantings escape; the door without the
standing rule (every row not withdrawn, still one forecaster's and one
card's), the world planting escapes (the builder refuses its honest world);
the gate's check a no-op, the world planting escapes on its gate probe. The
2026-09-05 unit planting still fires. Full suite with a dummy access token:
1794 collected, 1786 passed, 8 skipped, exit 0, the planting harness inside
it included; the harness alone 324/324; `audit.prose_reaching_the_raw_side()`
is `[]`. The gate's new check passes on the live record, read-only (newest
prediction 3108), and `audit.horizon_unit_faults()` is `[]`.

## No stored prediction is replaced -- built 2026-09-27 *(operator question 15, its first step; the third set of rulings of 2026-09-27)*

"Q15: first in the order. Fix predictions the same way as Q13, own commit,
planting that gets through on the unfixed code." The question as asked is
`docs/REPAIR_STATE.md` question 15; the hole was found by question 13's build
(above, "A prediction can be replaced"). The precedent is question 13
(9db5582 and its prover): its three rules, its words constant, its order,
its older record and its number read twice. How the brief is read is in
`docs/briefs/2026-09-27-rulings-third-set.md`. The ruling's gate scan and its
read-only measurement of the live record are its next steps, not this one.

### MEASURED FIRST *(2026-09-27; scratch worlds built by 98091d2 -- the released 68b215e plus documents -- and by this tree; the record only through copies made by `db.back_up_the_live_record`)*

- **Every form that took a stored forecast's place on 98091d2**, each on a
  fresh scratch world (two statistical forecasts on games of their own; a
  reasoning forecast citing sent prompt 7, dated before the prompt record
  binds; the final pass of the first forecast's question; a voided
  forecast, the newest; foreign keys on unless said):
  - `INSERT OR REPLACE` and `REPLACE` naming a stored number -- as `id`,
    `rowid`, the text `'1'`, `1.0` -- wrote another game's forecast of 0.99
    under the number of the stored 0.61.
  - `INSERT OR REPLACE` on a stored question and pass
    (`pred_one_answer_per_question_per_pass`) removed the stored forecast and
    wrote the newcomer under a new number -- and so did one giving the pass
    as NULL: `pass_kind` is the key's one column with a default, and under
    OR REPLACE SQLite writes a NULL there as 'early' AFTER the rules have
    seen NULL. `INSERT OR REPLACE ... SELECT` colliding with the second's
    number and the first's question removed both.
  - `INSERT OR REPLACE` citing the sent prompt the stored reasoning forecast
    cites (`pred_cites_one_sent_prompt`, the table's third key) removed it.
  - `INSERT OR REPLACE` onto the voided forecast's number on its own
    question: the void then withdrew the newcomer.
  - `UPDATE OR REPLACE` moving the second onto the first's number by `id`,
    `rowid`, `oid` or `_rowid_` removed the first; `UPDATE OR REPLACE ...
    SET pass_kind = 'early'` (or NULL) on the final pass removed the early
    pass of its question -- `pass_kind` is not a column
    `predictions_no_update` lists.
  - THE NUMBER READ TWICE: a function the connection defines, called twice
    for a one-row insert's number (the rules see the first answer), wrote
    over the first, the second and the voided newest forecast, by `INSERT OR
    REPLACE` and by `REPLACE`; `random()` drawing one to six over five stored
    wrote over one in 58 tries of 64, and NULL-or-the-first by a coin in 32.
  - UPSERTS naming a stored forecast: `DO UPDATE SET pass_kind` (by its
    number, or on its question's key) rewrote its pass, and `DO UPDATE SET
    resolved_utc, outcome` wrote a resolution round the resolver.
  - FOREIGN KEYS: a by-key replacement of a forecast something points at (a
    void here; on the record every forecast has a fingerprint) is held by the
    key with them on -- the newcomer takes a new number and the old one's
    children would point at nothing -- and taken with them off; a
    replacement under the same number is taken either way.
- **Already refused on 98091d2, and why**: an update of what was forecast or
  of the question but its pass (`predictions_no_update`, which also refused
  an upsert rewriting a probability); a second resolution
  (`predictions_resolve_once`); an upsert moving a row onto another's number
  (the key); `UPDATE OR REPLACE ... SET id = NULL` ("datatype mismatch").
- **The table's keys**: its number (`INTEGER PRIMARY KEY AUTOINCREMENT`, no
  automatic index), `pred_one_answer_per_question_per_pass` (six columns)
  and `pred_cites_one_sent_prompt` (an expression, partial on `predictor =
  'llm'`). Its rules on the record's copy, oldest first:
  `voided_prediction_stays_void`, `predictions_no_delete`,
  `predictions_no_update`, `predictions_resolve_once`,
  `reasoning_row_carries_its_prompt`. `predictions_no_update` lists thirteen
  columns, and not `id`, `sport`, `prop_type`, `pass_kind` or `degraded`.
- **Every writer read**: `model.predict.write_prediction` (a plain INSERT
  naming no number, after `already_written`, which mirrors the key, inside
  one savepoint with the prompt record and the fingerprint);
  `resolve.resolve_all` (an UPDATE of `resolved_utc` and `outcome` `WHERE
  resolved_utc IS NULL`); `resolve.void_prediction` and `tools/void_fs5.py`
  write `prediction_voids` only; `db._finish_widening` copies the rows back
  into a rebuilt table by `INSERT ... SELECT`, in number order, into a table
  holding none; `gridiron.rebuild` copies before a table's rules exist and
  never rebuilds this one; `tools/dbcopy.FACT_TABLES` does not carry it;
  backtests write through the pipeline. No package or tool module uses `OR
  REPLACE`, `REPLACE`, `OR IGNORE` or `ON CONFLICT` on `predictions`, and
  none counts an insert's refusal by "UNIQUE" there (the four that count
  "UNIQUE" -- `recommend.record_for`, `at_the_line`, `priced.forecast`,
  `views` -- count it on other tables). So there was no counting to keep.

### BUILT *(2026-09-27)*

- **`predictions_never_replaced`** (BEFORE INSERT): refuses an insert naming
  a stored number, a stored question and pass, or a sent prompt a stored
  reasoning forecast cites -- all three keys -- whatever its conflict clause,
  since a rule cannot see one: a plain second answer to a question (the
  key's "UNIQUE" until now) and an upsert naming a stored forecast are
  refused too, by name. It does not look up the -1 SQLite shows it when the
  number is left to SQLite (question 13's prover).
- **`predictions_never_replaced_by_update`** (BEFORE UPDATE, no column list):
  refuses an update that would take the place of another stored forecast
  by any of the three keys, and nothing else; the resolver's update is
  untouched.
- **`predictions_never_replaced_by_the_number_written`** (AFTER INSERT):
  refuses the number a row landed under at or below `sqlite_sequence`'s mark
  for the table, or below any stored forecast; the abort takes the statement
  back, the removed row with it.
- **A PASS GIVEN AS NULL IS EITHER PASS** in both rules before the row: a
  NULL pass collides with a stored forecast of the question in either pass.
  No writer gives NULL, and a plain insert of one is refused as NOT NULL
  whatever these rules say.
- **Declared after `reasoning_row_carries_its_prompt`**, the table's newest
  rule on the record, so a fresh build runs them in the order the record
  will (SQLite runs a table's rules newest first). All three refuse under
  LAW 3 in words carrying `predict.NEVER_REPLACED` ("a prediction is never
  replaced"), never "UNIQUE"; a test holds the schema to it.
- **`db.PREDICTION_TRIGGERS` names them.** Measured on a scratch record made
  narrow (its sport CHECK without 'ufc', so `db.init` widens the table):
  without their names in that list the rename carried all three away with
  the old table, the schema script found the names taken and made none, the
  drop took them, and the widened table took an `INSERT OR REPLACE` over
  forecast 1. With them, the rules end on the widened table, every row and
  the sequence as they were, and the copy passes them (each row a new
  number in order, into an empty table).
- **No writer changes.** `write_prediction` refuses nothing new: it names no
  number and asks `already_written` first; if another writer answers the
  question between the ask and the insert, the insert is refused -- by the
  key before, by the rule now -- and raises the same `IntegrityError`, the
  savepoint taking the row and its prompt record back.
- **Two test worlds changed, not writers.** `test_voids._the_morning` wrote
  the record's own numbers out of order (2228 after 2294, and 2200 last); it
  now writes the same rows, numbers and stamps in the order of their
  numbers, as SQLite gave them out, and every assertion stands (question
  13's precedent: its `_let_through_world`). And in `test_prompt_record`
  a sent-prompt cite spelled as a real (and as true when the record is
  number 1) IS the first forecast's cite under the one-forecast key, so the
  replace rule, which runs first, refuses it in its words; the text spelling
  is refused by the prompt record's rule as before.
- **Planting** `plant.py::plant_a_replaced_prediction`: 24 forms on the world
  above, each run and rolled back -- the 21 that change the table on
  98091d2 and three held (an update onto another's question by its game, an
  upsert rewriting a probability, a plain second answer); CAUGHT means each
  refused under LAW 3, the 21 in the rules' words, every forecast and void
  as stored; a new forecast, a final pass beside a stored early one, a
  resolution and a void still written; with only the number-written rule
  dropped, the three read-twice forms writing over a stored forecast; with
  all three dropped, each of the 21 changing the table. *(26 forms and 23
  changing from the prover, below.)*
- **Tests** in `tests/test_predictions_never_replaced.py` (40; 44 from the
  prover, below): the 23 forms
  (the planting's without the read-twice three, plus a question and pass
  stamped as stored and an upsert moving a row onto another's number); the
  forms replacing without the rules; a NULL pass removing the early pass
  past rules that compare it as given; every key of the table read by the
  rules (a new unique index fails it); the lawful writes through the
  pipeline (statistical and reasoning early passes with their sent prompts,
  the final pass, the resolver, a void; numbers 1 to 16 in order); a writer
  racing another still raising; the words and the order on a fresh build;
  an older record gaining exactly the three through `db.init`; a widened
  table keeping them; and the number read twice (three forms by each verb),
  `random()`, a free number below one given out, and a forecast moved to -1
  not stopping the next.

### THE REHEARSAL *(2026-09-27 16:18Z; a copy of the record made through `db.back_up_the_live_record`, and a verified copy of that, never the record)*

The copy of the copy verified (`rebuild.verified_backup`: 61 tables,
1,248,349 rows, integrity ok, every sqlite_master row and every table's
count and column checksums equal). Before: 238 objects; 3,120 forecasts,
numbers 1 to 3,120, sequence 3,120; `schema_diff.compare` against a fresh
build of this tree found exactly the three rules missing and nothing else.
`db.init` under this tree then made exactly the three -- no object gone or
changed, no table's count or column checksums moved -- with a fresh build's
text byte for byte, after `reasoning_row_carries_its_prompt`. After: 0
differences in behaviour (241 objects each; 9 differ only in what the
ruling normalises, the same nine as question 13's, the three not among
them); a second `db.init` changed nothing. On the copy's own rows: OR
REPLACE naming forecast 3,120's number, OR REPLACE on forecast 1's question
and pass, UPDATE OR REPLACE moving 2 onto 1 by `rowid`, both read-twice
forms (onto 1, and onto 3,120, the newest), a plain insert naming a free 0,
UPDATE OR REPLACE moving final pass 597 onto early pass 65 by its pass, and
OR REPLACE citing the sent prompt forecast 3,120 cites were each refused in
the rules' words; the resolution of open forecast 1,508 landed, and a plain
insert took 3,121 (both rolled back); the forecasts' column checksums
unchanged throughout.

### PROVED *(2026-09-27)*

- **The planting ESCAPES on 98091d2** (`git archive HEAD` into the
  scratchpad, this `plant.py` copied over it): all 21 changing forms taken,
  each named with the rows before and after, and the plain second answer
  refused by the key's "UNIQUE", not the rules. It is CAUGHT here.
- **Each rule, and each clause, is proved by it** (the rule dropped or
  weakened after `db.init`, the planting run): the insert rule dropped, the
  three inserts on a key (the question and pass, the NULL pass, the cite)
  and the three upserts escape -- the forms naming a stored number fall to
  the number-written rule instead; the update rule dropped,
  its six updates; the number-written rule dropped, the three read-twice
  forms; the update rule listing its columns, the updates by `rowid`, `oid`
  and `_rowid_`; either rule comparing the pass as given, its NULL form;
  the insert rule without the cite, the cite form.
- **The new tests fail on 98091d2** (this file run over the archive): 39 of
  40; the lawful-writes test passes there, as it must.
- **The full suite here** with a dummy access token: 1826 passed, 8
  skipped, exit 0, the planting harness inside it included; the harness
  alone 325/325. An earlier run without the harness had one failure,
  `test_smoke.py::test_nothing_moves_under_reduced_motion`, which passed
  run alone: the known race (question 5's business), not this change.

### READINGS TAKEN *(each reversible in one line)*

- **"The same way as Q13" is Q13's three rules on `predictions`, under names
  of their own** (the brief's reading), and "replaced" is Q13's: a stored
  forecast removed by another's taking its place, by an insert or an
  update. So the insert rule refuses any insert naming a stored key (a rule
  cannot tell OR REPLACE from a plain insert), and the update rule only an
  update that takes another's place.
- **Every key the table has, the prompt cite included.** The brief names "a
  stored prediction's number or any other stored unique key of the table";
  `pred_cites_one_sent_prompt` is one, and OR REPLACE on it removed a stored
  reasoning forecast (measured). A test fails if the table gains a key the
  rules do not read. (Reversal: drop the cite clause from both rules.)
- **A NULL pass is either pass**, the stricter reading of a collision SQLite
  resolves after the rules have looked; it refuses nothing a writer does.
- **An upsert naming a stored forecast is refused whatever it would set**
  (Q13's reading), a resolution included: the resolution has its own
  writer, an update, which is untouched.
- **`db.PREDICTION_TRIGGERS` is not a writer.** It lists the schema's rules
  on the table so a widening recreates them; without the three names the
  first widening would drop them (measured).
- **Two test worlds were changed, and no writer.** Q13's precedent; each is
  said above.
- **The words of a plain second answer moved** from the key's "UNIQUE
  constraint failed" to the rules'; nothing counts either.

### THE LIVE RECORD AFTER THE RELEASE *(no tool)*

No row is written and no tool runs. The scheduler's first open of the record
under the released code (`db.init`, as every schema rule has arrived since
5b) makes the three rules and nothing else; every forecast stays as written.
Afterwards, read through `db.read_the_live_record`: sqlite_master holds
`predictions_never_replaced`, `predictions_never_replaced_by_update` and
`predictions_never_replaced_by_the_number_written`, in that order, after
`reasoning_row_carries_its_prompt`, with `schema.sql`'s text. Until that
first open the record lacks them while the release has them, so the gate's
release comparison runs after it, as with every rule since 5b.

### OPEN, found by this step *(2026-09-27; not built)*

- **A forecast's number can still be changed by a plain UPDATE.**
  `predictions_no_update` lists no `id`, so `UPDATE predictions SET id = <a
  free number>` (or by `rowid`) lands on 98091d2 and here on a forecast
  nothing points at. On the record's copy the newest forecast, fingerprinted
  like every one, is held by the fingerprint's key with foreign keys on, and
  moves with them off. From this step a later insert under the old number is
  refused (`..._by_the_number_written`: it is at or below one given out), so
  no forecast can be written in its place; the move itself is not a
  replacement and is not refused. Question 13 left the recommendation's
  equivalent open ("freezing the number goes past the ruling's words"), and
  "the same way as Q13" leaves this one open too: for the operator. *(From
  the prover, below: a move ABOVE every number given out is refused, because
  it took the forecast out of the number-written rule's reach and a number
  read twice then wrote over it. A move within the numbers given out still
  lands, and stays in reach.)*
- **A forecast's pass, sport, prop and degraded tag can be changed by a
  plain UPDATE** (measured on 98091d2 and here), where no other row takes
  its place: `predictions_no_update` does not list them. The fingerprint
  hashes the sport, the prop and the pass (`fingerprint.PROTECTED`), so the
  gate's fingerprint check would name such a row afterwards; the degraded
  tag is in neither. Which pass a row is decides which forecast stands. Not
  a replacement, so not this ruling's: for the operator.
- **SQLite's own sequence set back first**, as question 13's NOT SEEN: an
  ordinary statement may rewrite `sqlite_sequence`, SQLite refuses a rule on
  it, and after the mark is set below the newest forecast an insert whose
  number reads free to the rules and the newest's to the key writes over it,
  leaving nothing that tells it from a newcomer. Every other forecast stays
  protected by "below any stored one". *(The prover, below: the set-back
  can also be done inside the replacing statement, by a temporary rule the
  connection makes; and "below any stored one" is proved by a planting form
  and a test of its own.)*

### THE PROVER *(2026-09-27; alone in the worktree, the change uncommitted; scratch worlds, and the record only through `db.back_up_the_live_record`)*

- **TRIED, AND REFUSED BY THE RULES** (each on its own copy of the
  planting's world, foreign keys on and again off; the same forms on a `git
  archive` of 98091d2 each changed the table unless said): the table named
  `main.predictions`, `"predictions"`, `[predictions]`, `` `predictions` ``,
  `MAIN."PREDICTIONS"`, `PREDICTIONS`, `"main"."predictions"`, and through
  an attached copy (`aux.predictions`); the number as `oid`, `_rowid_`,
  `"ROWID"`, `Id`, both `id` and `rowid` listed (either order: SQLite writes
  the last named), and spelled `' 1'`, `'+1'`, `1e0`, `0x1`, `'1.0'`,
  `'  1  '`, `CAST('1' AS INTEGER)`, `(SELECT 1)`, `2-1`; the question and
  pass with the pass left to its default, given `(SELECT 'g1')` for the
  game, the final pass, and a pass `CAST(NULL AS TEXT)`; the sent-prompt
  cite spelled `7.0`, `7e0`, `70e-1`, `0.7e1`, with spaces, with a key
  written `reasoning_prompt_id`, duplicated with 7 first, and as a
  blob; an upsert on the cite's own expression index;
  `executescript`; a temporary view whose INSTEAD OF rule writes OR REPLACE;
  temporary rules on `games` writing a plain insert under an outer `INSERT
  OR REPLACE` or `UPDATE OR REPLACE` (the outer clause is inherited); a rule
  on `games` in the schema itself writing OR REPLACE; temporary rules on
  `predictions` that move the stored forecast away first (by its number:
  refused after it lands), or that write OR REPLACE or UPDATE OR REPLACE
  from after an insert; `UPDATE OR REPLACE` onto another's number spelled
  `'1'`, `1.0`, `id - 1`, `(SELECT 1)`, through `... FROM`, through
  `main.predictions`, and moving the final pass onto the early one's
  question and a new number at once; a stored forecast at -1 written over
  by a number named -1, or moved onto by an update; a second row of a
  multi-row VALUES naming a stored number. Refused here too, and NOT
  replacements on 98091d2: `UPDATE OR REPLACE` on every row at once (`6 -
  id`, `id + 1`; held there by the void's foreign key), an upsert with two
  ON CONFLICT clauses and `INSERT OR ABORT`, `OR FAIL`, `OR ROLLBACK` naming
  a stored number (refused there by the key), `INSERT OR IGNORE` and `ON
  CONFLICT DO NOTHING` naming one and `INSERT OR REPLACE ... SELECT *` of a
  forecast onto itself (nothing visible changed there), and
  `recursive_triggers` on (the delete rule refuses there) -- a rule cannot
  see the clause, and no writer uses any of them on this table. A temporary
  rule changing a stored forecast's pass before an insert of its question
  is the pass edit OPEN above, not a replacement: the forecast stays, under
  its other pass.
- **READ ONCE, SO NOT A PATH**: a function in the game, the pass or the
  factors of a one-row insert is called once (measured: only the number is
  read twice); an update works its new values out once. A JSON blob (JSONB)
  or a cite duplicated with another number first is no key to either the
  index or the rules. Incremental blob writes (`Connection.blobopen`) are
  refused on every column of this table by SQLite itself, because it has an
  expression index ("cannot open indexed column for writing").
- **FOUND AND FIXED -- A FORECAST MOVED OUT OF REACH.** The number-written
  rule holds only what is at or below `sqlite_sequence`'s mark, and an
  UPDATE of a number does not move the mark (measured: 2 moved to 10 over a
  mark of 3 left the mark 3). So on the rules as first built a plain `UPDATE
  predictions SET id = 10 WHERE id = 2` landed (it replaces nothing), and a
  one-row `INSERT OR REPLACE` or `REPLACE` whose number read as a free 99 to
  the rules and as 10 to the row wrote another game's forecast over it: the
  rule after the insert saw 10 above the mark and nothing above 10. Also on
  98091d2. `predictions_never_replaced_by_update` now also refuses a move of
  a forecast's number above every number given out, in the rules' words;
  nothing else it refuses is new. It is not a freeze of the number: a move
  within the numbers given out still lands (OPEN above, the operator's) and
  stays in reach -- a number read twice onto it is refused. No writer moves
  a number. The reading: "the same way as Q13" does not mean with its
  holes, and the precedent's own conservative default (refusing a free
  number below one given out, which replaces nothing) refuses what no
  writer does to keep what the ruling protects in reach. (Reversal: take the
  clause out of the update rule.) One test world changed, no writer:
  `test_a_number_below_one_already_given_out_is_refused_and_one_above_lands`
  vacated number 2 by moving the forecast up to 10, and now moves it down,
  to -5; it asks about the same numbers.
- **THE SAME HOLE ON RECOMMENDATIONS, NOT BUILT.** Measured on this tree:
  `UPDATE recommendations SET id = 10 WHERE id = 2` over a mark of 3 lands,
  and a one-row `INSERT OR REPLACE` whose number reads 99 to question 13's
  rules and 10 to the row writes rec 4's forecast over it. Question 13 is
  released and this ruling names predictions: for the operator.
- **NOT SEEN BY ANY RULE, measured** (settings of a connection, never a
  statement a rule is shown; each is taken on this tree):
  - `Connection.setconfig(sqlite3.SQLITE_DBCONFIG_ENABLE_TRIGGER, False)`
    switches every rule in the schema off for that connection, after which
    `INSERT OR REPLACE` naming a stored number, or on a stored question and
    pass, writes over the forecast -- and the delete rule is silent too.
  - `create_function("json_valid", 1, ...)` (or `json_extract`), answering
    the insert rule's reading of a newcomer's factors as not JSON and the
    one-forecast index's as JSON, lets `INSERT OR REPLACE` citing a stored
    reasoning forecast's sent prompt remove that forecast: the rule and the
    index each read the cite once, through the connection's function. A
    truthful redefinition is refused. On the record every forecast has a
    fingerprint, so with foreign keys on the removal fails on that key;
    with them off it is taken, and `PRAGMA foreign_key_check` names the
    orphaned fingerprint afterwards.
  - The sequence set back INSIDE the replacing statement, by a temporary
    rule on `predictions` that rewrites `sqlite_sequence` before the rule
    after the insert reads it: the newest forecast written over, as with a
    statement first.
  - Redefining the `BINARY` collation was tried both ways (every text equal,
    no text equal): the unique indexes compare their keys byte for byte and
    the rules' key lookups go through them, so no forecast was replaced;
    each attempt was refused by another rule or a CHECK the redefinition
    broke.
  - **For the ruling's next step, the gate scan**: shipped code that calls
    `setconfig` with `SQLITE_DBCONFIG_ENABLE_TRIGGER`, or `create_function`
    / `create_collation` naming a built-in the schema uses, is a replacing
    statement's precondition the scan can see and a rule cannot.
- **EACH PART NEEDED** (the planting run against a copy of `schema.sql` with
  one part taken out): the insert rule (the three inserts on a key, the
  three upserts; the plain second answer falls to "UNIQUE"), the update
  rule (its six updates and the move above the mark), the number-written
  rule (the three read-twice forms and the sequence form), the update rule
  listing `OF id, pass_kind` (rowid, oid, _rowid_), either rule comparing
  the pass as given (its NULL form), the insert rule without the cite (the
  cite form), the update rule without the move above the mark (that form),
  the number-written rule without "below any stored one" (the sequence
  form) -- each ESCAPED. Two parts the planting does not need, each held by
  a test instead: the insert rule not looking -1 up
  (`test_a_prediction_given_a_number_below_one_does_not_stop_the_next`
  fails when it does), and the update rule's cite clause, which
  `predictions_no_update` shadows today -- it freezes the factors and the
  forecaster, the two things the cite is read from -- and which
  `test_every_key_of_the_table_is_one_the_rules_read` holds so the update
  rule reads every key the insert rule does.
- **PROVED.** The planting (26 forms: two added, the move above the mark
  and the sequence set back, each in two statements) ESCAPES on a `git
  archive` of 98091d2 with this `plant.py` copied in -- all 23 changing
  forms taken, the two new ones among them, and the plain second answer
  refused by "UNIQUE" -- and is CAUGHT here. The test file (44: the move
  above the mark and the sequence set back, by both verbs) fails 43 of 44
  on that archive, the lawful writes passing there as they must, and
  passes here. Each neutralised part above fails its test here. The
  harness: 325/325, exit 0. Gate step 2's rows run on their own (not
  `verify.py` whole; the harness row left to the run above) with
  `GRIDIRON_VERIFYING` set: 90 PASS, 0 FAIL -- both schema comparisons 0
  registered differences outstanding (9 objects differing only in what the
  ruling normalises), the record's schema as found (238 objects).
  `audit.prose_reaching_the_raw_side()` is `[]`. The full suite with a
  dummy access token: 1830 passed, 8 skipped, exit 0. (A first run with the
  temporary directory set deep inside the scratchpad failed ten tests that
  copy the package or run git there, on `[WinError 3]` and git's exit 128:
  the copied paths passed Windows' 260 characters. All ten passed with the
  default temporary directory, and so did the whole suite; the eleventh,
  `test_smoke.py::test_nothing_moves_under_reduced_motion`, passed alone --
  the known race, question 5's business.)
- **RE-REHEARSED** at 17:10Z on a fresh copy through
  `db.back_up_the_live_record` and a verified copy of it (61 tables,
  1,248,982 rows, integrity ok): before, 238 objects, 3,120 forecasts
  numbered to 3,120, sequence 3,120, exactly the three rules missing
  against a fresh build; `db.init` added exactly the three with a fresh
  build's text after `reasoning_row_carries_its_prompt`, nothing gone or
  changed, no table's checksums moved; after, 0 differences (241 objects
  each, 9 cosmetic); a second `db.init` changed nothing. On the copy's own
  rows every form above was refused in the rules' words, and the move of
  forecast 2 or of the newest above the mark (3,125) with foreign keys on
  and off, the move to 0 followed by a number read twice onto it, and the
  sequence set back followed by a number read twice onto forecast 1 were
  refused too; the sequence set back and a number read twice onto the
  newest was TAKEN (NOT SEEN, as recorded). The resolution of open
  forecast 1,508 landed and a plain insert took 3,121 (both rolled back);
  the forecasts' checksums and the sequence never moved.

## No write replaces a row of an append-only table -- built 2026-09-27 *(operator question 15, its second step: the gate scan; the third set of rulings of 2026-09-27)*

"Then one gate scan that refuses INSERT OR REPLACE, REPLACE and ON CONFLICT
DO UPDATE against every append-only table; any legitimate upsert (cache,
derived table) is named in a register that may only shrink." How the brief
is read is in `docs/briefs/2026-09-27-rulings-third-set.md` ("Q15, the
scan"). Its own commit after the predictions rules (22e182d); one gate
covers both and they release together (Q14's precedent). The ruling's third
part, the read-only measurement of the live predictions, is not this step.

### MEASURED FIRST *(2026-09-27; this tree at 22e182d -- the released 68b215e, documents and the predictions rules; source only, the record not opened)*

- **Every replacing write the shipped code can issue** (the package,
  `tools/` less `tools/guards/`, `desktop/`, `schema.sql`): 36 statements.
  One on an append-only table: `db.set_meta`, an upsert on `meta` ("ON
  CONFLICT(key) DO UPDATE"). The other 35, on 26 tables none of which the
  schema gives a rule: 32 upserts and 3 inserts under OR REPLACE
  (`nba_loader`: `nba_team_games`, `nba_player_games`, `nba_injuries`).
  `games` takes five (the NFL, MLB, NBA and college loaders and the UFC
  mirror), `market_lines_raw` three, `game_conditions` three, `teams` two.
  No REPLACE statement, no update under OR REPLACE, no key declared to
  replace on conflict (every mention in `schema.sql` is a comment), and no
  rule whose body writes a table. `cfb_loader._team_code`'s `ON CONFLICT DO
  NOTHING` on `teams` replaces nothing.
- **The append-only tables, read from the schema**: 22 -- every table a rule
  refuses a delete or an update on, all of them BEFORE rules:
  `at_the_line_claims`, `calibration_corrections`, `factors`,
  `fit_activations`, `market_snapshots`, `meta`, `picks_retracted`,
  `picks_taken`, `prediction_fingerprints`, `prediction_ranks`,
  `prediction_voids`, `predictions`, `priced_forecasts`, `prop_rung_claims`
  (an update rule only), `reasoning_prompts`, `recommendation_closes`,
  `recommendation_regrades`, `recommendation_voids`, `recommendations`,
  `settings`, `task_runs`, `venue_packages`. The same set, rule for rule, as
  a fresh build's own `sqlite_master` gives.
- **Each upserted table read against the schema**: none has a rule. The
  schema's own words call `injuries`, `mlb_lineups` and `weather_forecasts`
  current state, with their history in stamped tables of their own
  (`injury_reports`, `lineup_captures`, the observed weather); `nba_injuries`
  "a SNAPSHOT, not a history ... replaced on each fetch"; the raw line
  tables hold the latest published line, and what a forecast was compared
  with is written once in `market_snapshots`; `team_week_stats` and
  `ufc_ratings` are derived and rebuilt; `session_seen` is a per-browser
  marker; the rest mirror their source. Each is registered with its reason.
- **Connection settings no statement shows** (the predictions prover's
  list): `setconfig`, `create_function`, `create_collation`,
  `create_aggregate` and `recursive_triggers` appear nowhere in the shipped
  code (`git grep`, 2026-09-27).

### BUILT *(2026-09-27)*

- **`audit.check_no_replacing_write_on_an_append_only_table`**
  (`audit.replacing_write_faults`), gate step 2, beside the raw-connect scan.
  It reads, from the syntax tree, every string the package, `tools/` (not
  `tools/guards/`) and `desktop/` can hand SQLite -- a constant, an implicit
  concatenation, a `+` of pieces, an f-string, a `%` or `.format` template, a
  `join` of literal pieces, in an execute, executemany, executescript or a
  variable -- each part worked out at run time read as unknown, and a
  `.format` argument, the values after `%` or a formatted expression read
  as strings of their own; docstrings are not read. And every `.sql` file in
  the package. It reads them as SQLite does: comments and whitespace are not
  words, case is not a difference, a quoted, bracketed or qualified name is
  the name, a string literal is data.
- **What it finds**: an insert under OR REPLACE, a REPLACE statement, an
  update under OR REPLACE, an upsert whose conflict clause updates the stored
  row (its table the insert's), and a table or column key declared to
  replace on conflict (its table the one defined). A part worked out at run
  time where a conflict clause goes (after INSERT or INSERT OR, after UPDATE
  OR, between UPDATE and a named table, after a conflict target) or as the
  statement's whole verb (`{verb} INTO t (...)`) is counted as one that
  replaces.
- **What it refuses**: a replacing write aimed at an append-only table, by
  file, line, function and table, naming the rules that make it append-only
  -- registered or not; one whose table cannot be read (a part of its name,
  or all of it, worked out at run time), counted as aimed at an append-only
  table; a write under OR REPLACE whose table's rules write an append-only
  table (a rule's own writes carry the statement's clause -- none today);
  any other replacing write not in `audit.UPSERTS_REGISTERED`; and a register
  entry no longer found, holding a second statement, naming an append-only
  table, or with no dated reason in words.
- **`audit.UPSERTS_REGISTERED`**: 35 entries, (file, qualified function,
  table), each with a reason dated 2026-09-27 saying why the table is a cache
  or a derived table. It only shrinks.
- **`db.set_meta` written plainly**: an UPDATE of the key, and a plain INSERT
  when no row changed, inside one savepoint, then the one commit it always
  made. Measured side by side with the upsert on two scratch worlds: the
  same rows under the same row numbers, the same writes refused; the update
  takes the write lock before the insert whether the connection is in
  Python's default mode or autocommit (another writer is refused "database
  is locked" between them), so no writer stores the key in between; a
  caller's pending write is committed with it, and a refused call leaves it
  pending, as the upsert did. The release instant is still refused -- by
  `prompt_record_instant_never_moves` now, where the upsert met
  `prompt_record_instant_is_written_once` (nothing reads those words).
- **Plantings** (`plant.py`, each on a copy of the package, each CAUGHT only
  when every planted place is named as the planting says and nothing else
  is): `plant_a_replacing_write_on_an_append_only_table` (OR REPLACE on
  `predictions`, REPLACE on `recommendations`, UPDATE OR REPLACE on
  `market_snapshots`, and a table named at run time);
  `plant_a_replacing_write_hidden_from_a_plain_reading` (one write on
  `predictions` hidden by case, whitespace, comments, an implicit
  concatenation, `+`, and a quoted qualified name through `executescript`);
  `plant_an_upsert_on_an_append_only_table` (`set_meta`'s upsert as it
  shipped, and one rewriting a withdrawal's reason in `prediction_voids`);
  `plant_an_unregistered_upsert` (`sessions`, and OR REPLACE on
  `auth_failures`); `plant_a_registered_upsert_moved_onto_an_append_only_table`
  (`views.mark_seen`'s upsert moved onto `picks_taken`, and left alone while
  `session_seen` is given a no-delete rule); `plant_a_stale_upsert_in_the_register`
  (`mark_seen` written plainly, its entry left); and
  `plant_a_table_that_replaces_on_conflict` (the table-level key of
  `recommendations` and `task_runs`' number declared ON CONFLICT REPLACE in
  `schema.sql`).
- **Tests**: `tests/test_no_replacing_write.py` (76): the shipped code
  passes; the gate runs the scan in step 2; the append-only set is a fresh
  build's own; every registered table is declared, carries no rule and has
  a dated reason; 61 readings of a statement (every form and spelling above,
  every run-time part, and what is not a replacing write -- DO NOTHING, OR
  IGNORE, a literal, a comment, a docstring, a plain insert or update, the
  `replace()` function, prose); each fault by name in a world of its own;
  the register only shrinking; the clause carried through a rule; a key in
  the schema; `tools/` and `desktop/` read, `tests/` and `tools/guards/` not;
  and four of `set_meta` beside the upsert as it shipped.

### PROVED *(2026-09-27)*

- **The plantings ESCAPE on 22e182d** (`git archive` into the scratchpad,
  this `plant.py` copied in): 0 of 7 caught -- there is no scan there, and
  `db.set_meta`'s upsert on `meta` is the shipped code. CAUGHT here, 7 of 7,
  each by name.
- **Each part of the scan is needed** (taken out of a copy of this tree, the
  seven run against it): comments read as words, and the upsert not seen,
  each failed all seven (the schema's comments, and the 35 registered
  upserts no longer found, were named besides); case kept, `+` not
  followed, and quoted names unread, the hidden planting; the schema not
  read, five; stale entries not named, the moved and the stale plantings;
  a registered append-only entry allowed, the moved planting; an unreadable
  table skipped, the first; the register not asked, the unregistered one.
- **The new tests fail on 22e182d** (this file run over the archive): 72 of
  76; the four `set_meta` tests, which hold it to the upsert's behaviour,
  pass on both, as they must.
- **The harness**: 332/332, exit 0. Gate step 2's rows that read no record,
  run on their own with `GRIDIRON_VERIFYING` set (not `verify.py`, and no
  copy of the record): 60 PASS, 0 FAIL, this scan among them;
  `audit.prose_reaching_the_raw_side()` is `[]`. The scan takes about three
  seconds. The full suite with a dummy access token: 1904 passed, 8
  skipped, 2 failed -- `test_smoke.py::test_every_tap_target_on_the_slate_is_big_enough`
  (43.99951171875px, question 20's arrival) and
  `test_smoke.py::test_nothing_moves_under_reduced_motion` (question 5's
  race), each of which then passed alone three runs of three: the known
  flakes, in page code this step does not touch.

### READINGS TAKEN *(each reversible in one line)*

- **`desktop/` is read too** -- shipped code, and the raw-connect scan's
  precedent; it issues no SQL today. (Reversal: drop it from the scan's
  folders.)
- **Docstrings are prose and are not read**, the precedent of every source
  scan here.
- **An append-only table is one a DELETE or UPDATE rule is on, whatever its
  timing**, and a rule written in a Python string counts too. The brief says
  "a no-delete or no-update rule"; every such rule today is BEFORE and in
  `schema.sql`, so the set is the one the brief was read against.
- **The stricter defaults the brief names**: UPDATE OR REPLACE is refused as
  the others; an unreadable table counts as append-only.
- **A run-time part where a conflict clause or the verb goes counts as a
  replacing write** -- the stricter reading of "a formatted part is
  unknown". A run-time table name in a plain update (`UPDATE {table} SET`)
  is not: it is the table's name, and reading it as a clause would refuse
  every such update (none today; NOT SEEN below).
- **A write under OR REPLACE is aimed at what its table's rules write**,
  because a rule's writes carry the outer clause (measured by the
  predictions step's prover). An upsert's clause is not carried.
- **Every key declared to replace on conflict counts**, a NOT NULL one
  included: it changes what is written without a word in any statement.
- **"Only shrinks" read strictly**: an entry names one statement, and a
  second under it fails; an entry must carry a dated reason; an entry whose
  table becomes append-only fails as such.
- **`meta` is append-only** (its rules guard one key, the release instant),
  so `set_meta`'s upsert went, rewritten to the same effect; no ruling was
  needed, because nothing it did changes.

### THE LIVE RECORD AFTER THE RELEASE *(none)*

No schema change and no row. `set_meta` is never run on the record: its
callers are gate step 3's one-week scratch world, `tools/backtest.py` on a
backtest database, the activation door's scratch worlds, and tests.

### OPEN, found by this step *(2026-09-27; not built)*

- **NOT SEEN by the scan**: a statement assembled where no one string shows
  its form (bare words added with `+=` one statement at a time, a list
  joined at run time, a name read from a file, the environment or the
  record); a table name worked out at run time in a plain update, which
  could carry OR REPLACE; and SQL in `tests/` and `tools/guards/`, outside
  it by the brief.
- **Connection settings no statement shows** -- `setconfig` switching rules
  off, `create_function` or `create_collation` redefining a built-in the
  rules read -- let a replacing statement past the schema's rules (the
  predictions step's prover measured each). None is in the shipped code.
  The prover suggested this scan look for them; the ruling's words name
  three statements, so it does not: for the operator.
- **Tables called append-only in words with no rule**: CLAUDE.md's
  convention names `factor_scores` and `llm_calls` ("never updated"), and
  the schema calls `injury_reports`, `lineup_captures` and the observed
  weather "append-only and stamped". None has a rule, so the scan counts
  them ordinary: a replacing write on one fails unless it is registered.
  None takes one today (plain inserts and OR IGNORE). Giving them rules is
  not this ruling's.
- **`mlb_people`'s comment and its loader disagree**: the schema says
  "Handedness does not change, so a row is written once"; `load_people`
  upserts the row from the source on every load. Registered as a cache of
  the source; which is meant is the operator's.

### THE PROVER *(2026-09-27, the same day, before the commit)*

Set to get round the scan by any path the ruling's words cover. Each path
below got a replacing write on an append-only table past the scan as first
built -- measured by probe on its readings, and then by planting: on that
version the scan said `[]` to every one of the five plantings below.

- **FOUND, a template kept in a variable and filled in later**: a
  placeholder was read as punctuation wherever the template was not filled
  in on the spot -- `T = "INSERT OR {} INTO predictions ..."` then
  `T.format(how)`, `T % how` with `%s` or `%(name)s`, `str.format(T, how)`,
  `.format_map`, a `string.Template` (`$how`, `${how}`), and an f-string's
  `{{}}` kept for a later `.format`.
- **FOUND, a statement in pieces**: the clause kept apart with the columns
  formatted after the table (`f"INSERT {clause} INTO predictions {cols}
  VALUES {marks}"` -- the check for SQL after the table wanted a literal
  `(` or VALUES); the clause in a string of its own (`" OR REPLACE "`); a
  hint between INSERT and OR REPLACE, or a verb worked out before it; a
  verb worked out after another part worked out (`f"{cte} {verb} INTO
  ..."`); `UPDATE {clause} {table} SET`; `INSERT OR ` or `UPDATE OR ` with
  the rest added by `+=`; `REPLACE {hint} INTO`; OR IGNORE rewritten by
  `.replace("IGNORE", "REPLACE")`; a bytes literal decoded before it runs;
  and an upsert in two strings -- an insert ending at its `ON
  CONFLICT(key)`, and ` DO UPDATE SET ...` on its own.
- **FOUND, a foreign key's action**: SQLite runs a key's CASCADE, SET NULL or
  SET DEFAULT when a replacing write removes or changes the parent row, and
  no rule of the child's that does not name the column. Measured on SQLite
  3.49.1: with `ledger.k REFERENCES cache (k) ON DELETE SET NULL` and
  foreign keys on (as `db.connect` sets them), `INSERT OR REPLACE INTO cache`
  rewrote the append-only ledger row's key to NULL, its update rule naming
  another column; ON UPDATE CASCADE did the same through an upsert changing
  the key. The scan followed a rule's writes and not a key's. No key in the
  schema or the code declares an action today.
- **FOUND, a rule's target the scan cannot read was dropped**: a rule whose
  body writes a table named at run time did not count at all (and a test
  asserting no rule writes a table used `any`, which a set holding only
  None passes).
- **FOUND, the register could grow**: an upsert written later, with an entry
  added to `UPSERTS_REGISTERED` dated 2026-09-27, passed every check -- the
  statement registered, the entry found and dated. "A register that may
  only shrink" is the ruling's words.
- **FOUND, a misleading entry fault**: a registered statement refused
  because a rule carries it onto an append-only table had its entry called
  "no longer found", though the statement is there.
- **Not a path, measured**: a quoted keyword (`INSERT OR "REPLACE"`, `[REPLACE]`,
  `` `REPLACE` ``, `'REPLACE'`, a quoted OR, UPDATE or CONFLICT) -- SQLite
  refuses each as a syntax error, as the scan's reading of a quoted word as
  a name says; an upsert's DO UPDATE does not carry into a rule's writes (a
  plain insert in the rule met UNIQUE), as the scan as built assumed; a view
  written through an INSTEAD OF rule was already followed.

### BUILT BY THE PROVER *(2026-09-27)*

- **Two readings of a Python string** (`audit._replacing_writes_in`): with
  every template placeholder a part worked out at run time
  (`_placeholders_unknown`, the same length, so a place is the same place),
  and as written, for anything the first finds nothing at the same place --
  so a placeholder that swallows a statement's words (a `{` in one literal,
  a `}` in another) loses nothing. `.sql` files are read as written only.
- **The pieces**: a part worked out at run time after the table, or the
  string ending there, is a statement going on; OR REPLACE where a statement
  could begin (the string's start, after `;`, `)`, BEGIN or a part worked
  out) is a replacing clause, its table the one after the next INTO or an
  update's; a verb worked out may follow another part worked out; INSERT OR
  and UPDATE OR where the string ends; `UPDATE {clause} {table} SET`;
  REPLACE followed by a part worked out, with an INTO ahead or the string
  ending; an insert whose string ends at its ON CONFLICT, or a string that
  begins with one; DO UPDATE SET with no ON CONFLICT before it in its
  string (DO UPDATE SET is SQL for nothing else); a `.replace` of a
  constant read as done, its new text unknown where worked out at run time;
  and a bytes literal read as text.
- **A key's action is a write**: `audit._sql_key_actions` reads every
  REFERENCES with ON DELETE or ON UPDATE and CASCADE, SET NULL, SET DEFAULT
  or an action worked out at run time, in the schema or a string of the
  code, its child the table being created or altered; a replacing write is
  aimed at every table a key's action on its table writes, whatever its
  conflict clause (an upsert's too), and on from there. A name the scan
  cannot read -- a rule's target, a key's child or parent -- counts as an
  append-only table, the brief's reading. REFERENCES is one of the words
  that makes a string worth reading.
- **The register frozen**: `audit.UPSERTS_REGISTERED_ON_2026_09_27` holds
  the 35 entries of this date, and an entry of `UPSERTS_REGISTERED` not
  among them fails by name however it is dated. A later upsert is written
  plainly, or the operator rules.
- **An entry's true reason**: a registered statement refused because a rule
  or key carries it onto an append-only table has its entry named "its
  statement is refused above", not "no longer found".
- **Plantings** (each ESCAPES on 22e182d and on the scan as first built,
  CAUGHT here): `plant_a_replacing_write_in_a_template_filled_later` (six
  shapes: `.format`, `%`, a key holding a space, `string.Template`, an
  f-string's `{{}}`, and a statement a wide placeholder would swallow --
  named on the first version too, a guard of the second reading);
  `plant_a_replacing_write_in_pieces_the_first_scan_missed` (twelve);
  `plant_a_replacing_write_reaching_an_append_only_table_by_a_key` (the key
  in `schema.sql`, and again declared in code); 
  `plant_a_replacing_write_reaching_a_table_the_scan_cannot_read` (a rule
  and a key whose target is named at run time); and
  `plant_an_upsert_registered_after_the_register_was_frozen`.
- **Tests**: `tests/test_no_replacing_write.py` 76 to 146 -- 55 readings of
  a template, a piece or a spelling (38 caught, among them `temp.`, a quoted
  schema, and a single-quoted table name -- SQLite takes one as a name,
  measured, and the scan counts it unread; 17 prose and lawful SQL left alone:
  "Replace {old} with {new}", "keep or replace", "Keep {what} or replace
  it", "(it is safe) or replace it", "Or replace the cache", "insert or
  update", "we do update the page", a percentage, `errors="replace"`, the
  `replace()` function after OR, a JSON literal, `strftime`, plain
  formatted writes, a JOIN ON a formatted condition, DO NOTHING in a
  template -- a bare OR REPLACE counts only at a string's start or after a
  part worked out, and only with SQL after it); a statement
  read both ways counted once under its entry; a key's action measured on
  SQLite and then refused by the scan; six actions read and three that
  write nothing not; a view written through an INSTEAD OF rule; a rule or a
  key onto an unread table; the frozen register, in a world of its own and
  through the gate's own call. One
  assertion of the first build's reworded, not weakened: the refused
  entry's fault is its true reason, and the count of faults is the same.
  The rule-writes assertion strengthened (`all(not ...)`), with no key
  action in the schema today.

### PROVED BY THE PROVER *(2026-09-27)*

- The five plantings: 5/5 CAUGHT here; 0/5 on 22e182d (no scan); 0/5 on the
  scan as first built, which said `[]` to each (the swallowed-statement
  shape, a guard of the new second reading, is named there, the others
  not).
- **Each part needed** (neutralised in a copy of this tree, the five
  plantings and the test file run against it): all nineteen let at least one
  planting through and fail at least one test -- the template reading, a
  part after the table, OR REPLACE apart from its verb, a verb after a part
  worked out, `UPDATE {clause} {table}`, INSERT OR and UPDATE OR where the
  string ends, REPLACE and a part worked out, `.replace`, an insert ending at
  ON CONFLICT, DO UPDATE SET on its own, a bytes literal, a placeholder
  holding a space, the text read again as written, a key's action, the key
  words scanned, a rule's unread target kept, the frozen register, and the
  refused entry's reason.
- The shipped code: 0 faults under the stricter reading, in about two
  seconds. The register names exactly the replacing writes that exist -- 35
  statements under 35 entries (32 upserts, 3 inserts under OR REPLACE), none
  on a table with a rule, none unread; no rule writes a table and no key
  declares an action.
- The harness: 337/337, exit 0 (332 and the five). Gate step 2's rows, run
  as `verify.step_2_guards` runs them but not `verify.py` whole
  (`GRIDIRON_VERIFYING` set, TMP and TEMP in the scratchpad, its plant.py
  subprocess stubbed because the harness ran on its own, and the LAW 5
  credential row handed an empty stand-in for the operator's settings file,
  which this step may not read): 91 PASS, 0 FAIL -- the live record against
  the release (master at 68b215e) and the migrated copy against this tree
  each with 0 differences outstanding, the record checks on a copy made
  through the backup door, and the record's schema as found (238 objects).
  `audit.prose_reaching_the_raw_side()` is `[]`. The full suite with a
  dummy access token: 1975 passed, 8 skipped, 1 failed --
  `test_smoke.py::test_every_tap_target_on_the_slate_is_big_enough`
  (`BUTTON.expand` at 43.99951171875px, question 20's arrival), which then
  passed alone three runs of three: the known flake, in page code this step
  does not touch.

### NOT SEEN, after the prover *(2026-09-27)*

- A statement assembled where no one string shows its form: pieces of a
  list or generator joined at run time, a constant holding the bare verb
  (`"REPLACE"` -- Python's own decoding argument, `.decode("utf-8",
  "replace")` or `errors="replace"`, spells it in a dozen places of the
  shipped code), bare words added one at a time with `+=` (except
  INSERT OR or UPDATE OR ending a string, now read), a keyword split by a
  placeholder, a name read from a file, the environment or the record.
- A `.replace` whose old text is worked out at run time, or applied to a
  statement kept in a variable; a docstring handed to SQLite through
  `__doc__` (docstrings are prose, the precedent); a tail worked out at run
  time after an insert's values (`{tail}`, `ON {x}`) -- though its literal
  pieces, `ON CONFLICT(...)`, `CONFLICT(...) DO UPDATE` or `DO UPDATE
  SET`, are each refused wherever they are written.
- A table part worked out at run time touching a plain update's name
  (`UPDATE {prefix}predictions SET`), which could carry OR REPLACE but reads
  as a schema's prefix; and a connection's own settings (above).

## A panel that holds tap targets arrives by its fade alone -- built 2026-09-27 *(operator question 20, ruled (A); the third set of rulings of 2026-09-27)*

"Q20: (A). The Today panel arrives by fade alone; per-frame whole-pixel check
that fails today, plus a planting; the one test_motion assertion changes.
Side question: not in scope; the old Why panel leaves with the board. The
board merge checks every tap target, links included." It serves the ruling on
the flaky tests (`docs/briefs/2026-09-27-close-out-rulings.md`): "fix the
elements so they render at 44px or more in whole pixels. Never widen a
tolerance. Its own commit, before the board merge." The question as asked,
with the diagnosis, is `docs/REPAIR_STATE.md` question 20; the board merge's
step 2 now carries "arrival motion on any panel holding tap targets is opacity
only" (`docs/briefs/2026-09-27-board-merge.md`), and the scan below is built
so the merge can be held to it.

### MEASURED FIRST *(2026-09-27; this tree at f66fefa -- the released 70ad888 and documents; the repo's own browser test world, never the live app)*

- **The failing reading**: `test_smoke.py::test_every_tap_target_on_the_slate_
  is_big_enough` at 43.99951171875px (44 less 1/2048). The diagnosis
  (scratchpad `flaky/diag/`, reused here): every tap target is laid out at a
  whole number of pixels, 44 or more, at rest, on every view and at both
  widths the tap-target tests use; during an arrival the Today panel sat a
  fraction of a pixel off whole and the browser rounded each control's top
  and bottom apart. Twelve market switches, every frame: 9 of 192 frames off
  whole, 3 readings under 44; the fade alone, 193 of 193 whole; every target
  at 45px, 15 readings still off whole (none under 44) -- a tolerance by
  another name, so not built.
- **Every arrival on the page** (the stylesheet and app.js searched for
  `arrive`/`arriving`, and the motion block read whole):
  - `#today.arriving` (style.css:1765): opacity 0 and `translateY(1%)` -- the
    one transform declared anywhere in the stylesheet.
  - `#today`'s transition (1753-1756): opacity and transform, 200ms,
    ease-out.
  - `arrive(node)` (app.js:2101) adds `arriving`, forces a layout and takes
    the class off on the next frame; its one caller is `renderToday`
    (app.js:1473), on `#today`. No other panel arrives.
  - The panel line, `#rail-body, #rail-match, #rail-pick`: opacity alone, and
    no element with any of those ids exists in index.html or app.js (the
    rail's; left, not this item's).
  - The state-change line (`.tile`, `.seg button`, `.tile-verdict`,
    `.krow`) and the rest (`.card`, `.card-head`, `.market-tab`,
    `.show-all`, `.card-hint`): a colour, a border or an opacity; the live
    pulse is opacity. Nothing else moves.
  So the Today panel was the one panel that moved and the one that arrives;
  nothing else needed the ruling.
- **375 at 2**: none of the existing tap-target tests uses it (all measure at
  390, three device pixels to one), so the per-frame check runs at 390 at 3.

### BUILT *(2026-09-27)*

- **The panel** (`style.css`): `#today.arriving { opacity: 0; transition:
  none; }` and `#today { transition: opacity var(--motion-panel)
  var(--motion-ease); }` -- 200ms and ease-out, as before, and no transform.
- **The words**: the L3 vocabulary's own comment (`:root`) says a panel that
  holds tap targets arrives by its fade alone and why, dated; the motion
  block's R4 comment keeps R4's history and says the Today panel's movement
  went, why, and which scan holds it; `audit`'s L3 bound
  (`MOTION_MAX_TRANSLATE_PCT`) is unchanged -- two per cent still binds any
  movement the page makes elsewhere.
- **The pixels**: `test_smoke.py::test_no_tap_target_leaves_whole_pixels_on_
  any_frame_of_the_slates_arrival`, beside the slate's tap-target test, on its
  `phone` fixture (390x844, 3x, mobile, touch). It redraws the slate 19 times
  in this world -- the hash set to the slate as the flaky test sets it, then
  every market chip, twice round -- and for each installs a sampler before the
  redraw: it starts on the mutation that puts the arrival class on the panel
  (the redraw's start, before a frame of it is drawn), reads the height of
  every tap target the tap-target tests measure (`SLATE_TAP_TARGETS`: the
  slate test's set, `test_cards.py`'s `#view-week a`, the colophon's links)
  on every animation frame, and ends on the arrival's own end (the class gone
  and no transition left running on the panel). No clock is read and nothing
  waits a fixed time; `wait_for_function` carries an upper limit only. It
  fails by name -- the element, its place down the page, the frame, the
  arrival, the reading -- on a height under 44 or not a whole number, and it
  asserts it looked at something (every arrival sampled, the whole slate's
  card controls measured inside the panel, frames read mid-fade). Cards stay
  closed (the side question). `ELAPSED_TIME_HELD` is unchanged.
- **`test_motion.py::test_a_tab_switch_arrives_through_the_motion_block`**:
  its one assertion that the transition names `transform` now asserts it
  names `opacity` and nothing else, with a two-line dated comment. Nothing
  else in the file changed.
- **The gate**: `audit.arrival_movement_faults` (step 2,
  `audit.check_a_panel_holding_tap_targets_arrives_by_its_fade_alone`, beside
  the motion vocabulary) reads style.css with its comments blanked, and
  app.js and index.html. A START STATE -- a rule whose selector carries
  `ARRIVAL_CLASS` or any other class the page's `arrive` adds -- may carry no
  `transform`, `translate`, `scale` or `rotate` but `none`. The TRANSITION
  of the panel such a state names (the selector without the class, its tag
  and classes read from index.html when it names an id, so a rule on
  `.today` or `section` counts), in the state or out of it, and every
  transition at the panel duration, names opacity alone: not a movement, not
  `all`, not a shorthand naming no property (CSS reads that as `all`). It
  names the file, line, rule and declaration. Proved at import on the
  arrival as it shipped and as it ships, a comment naming the old movement
  among the second.
- **The planting**: `plant.py::plant_a_panel_holding_tap_targets_moving_as_
  it_arrives` puts the movement back ten ways -- as it shipped until
  2026-09-27; its start state alone; its transition alone; the `translate`
  property; a transition naming `all`; one naming no property; the movement
  on the panel's class; inside a phone-width media block; the start state
  under a class the script's `arrive` adds in place of `arriving`; and a new
  panel arriving at the panel duration with a movement (the board's case) --
  each must be named as planted; a comment naming the old movement must not
  trip it; and the gate's own call must refuse the first form read from a
  copy of the package. In the harness and `test_guards.py`'s list.
- **CLAUDE.md**: the enforcement table's row, "L3: A PANEL THAT HOLDS TAP
  TARGETS ARRIVES BY ITS FADE ALONE".

### READINGS TAKEN *(conservative defaults, each reversible in a line)*

- **"Holds tap targets" is every panel that arrives.** What arrives in a
  panel is built by the script, which a scan of the stylesheet cannot read,
  so each is taken to hold them -- the stricter default. The Today panel does
  (its markup's fold, and each card's Why control and took button). A panel
  that arrives with none is not something the page has; it would be an
  operator question, not an exemption. (Reversal: a dated register of panels
  holding none.)
- **"Opacity only" is read literally**: a panel's arrival transition naming
  a colour or a border is refused too, not only a movement -- the ruling's
  words and the board merge's.
- **The panel duration marks a panel**: the vocabulary gives 200ms only to
  "a panel swapping its whole contents", so a transition at it is held to
  the rule even where no start state names it -- the way a board panel with
  an arrival of its own is seen. (Reversal: drop `timed`.)
- **The per-frame set** is the union of what the tap-target tests measure on
  the slate, with every card closed; the open Why panel's link is the side
  question, ruled out of scope.

### PROVED *(2026-09-27)*

- **The per-frame test fails on the code before the fix**: 10 runs of 10 on
  `git archive` of f66fefa with this test file copied in (9 to 28 readings a
  run, in about 257 frames of 19 arrivals: `button.took "I took this"` from
  53.99951171875 to 54.00048828125px and `button.expand "Why"` from
  43.99951171875 to 44.00048828125px, about two thousand and four thousand
  pixels down the page, on the whole slate's, the spread's and the
  moneyline's arrivals), and 10 of 10 on this tree before
  style.css changed (its draft, 4 or 5 of 19 arrivals off whole each run).
  **It passes on the fix**: 22 runs of 22 -- 21 alone and once in the full
  suite, about 257 frames a run, not one reading off whole or under 44.
- **Renders** (the repo's browser test world, scratchpad `flaky/q20/render`,
  390 at 3x and 1100): at rest the slate is byte for byte the same image on
  the fix and on f66fefa at both widths; one arrival held half-way (the
  panel's own transitions paused at 100ms of 200ms) shows the fix's panel in
  place at opacity 0.68 with every tap target whole, and f66fefa's 21px
  (390) and 18px (1100) below its place, where at 1100 two `took` and two
  `expand` read 53.9998779296875, 53.99951171875, 43.9998779296875 and
  43.99951171875px.
- **The planting**: NOT CAUGHT on f66fefa (`git archive`, this plant.py
  copied over it: "nothing reads a panel's arrival" -- that tree's
  `motion_faults` and `check_motion_vocabulary` pass its own moving
  stylesheet); CAUGHT here, all ten forms named as planted, the comment not,
  and the gate's own call refusing `#today.arriving`. The harness: 338/338.
- **The tap-target tests keep their floor**: the slate's, the cards', the
  sport tabs' and the settings' tests are unchanged, 44 and no rounding
  added, and pass. The full suite with a dummy access token: 1976 passed, 8
  skipped, 1 failed -- `test_smoke.py::test_nothing_moves_under_reduced_motion`
  (the `Why` it clicked did not open within 10 s: Q5's race with the redraw
  its own hash change starts, the known flake; under reduced motion nothing
  moved before this change either), which then passed alone three runs of
  three.

### NOT SEEN *(FOLLOWUPS)*

- A movement the script sets itself (an inline style, `animate()`); an
  arrival through a class `arrive` does not add or a function other than
  `arrive`; a transition declared under a selector naming none of the panel's
  id, tag or index.html classes (a class the script adds) below the panel
  duration; and a movement on a tap target itself (a pressed control that
  scales), which is not an arrival. The per-frame test reads the slate at 390;
  no other view arrives today.
- **For the board merge**: its panels may arrive by a class or a function of
  their own. The merge should plant a movement on each board panel that
  arrives and see this scan name it, or say which it cannot see.
- Two test comments still describe the old arrival ("one per cent below"):
  `test_cards.py::_open_week`'s and `test_motion.py`'s reduced-motion test's.
  Their waits still hold (the fix's transform is `none`); the ruling changed
  one test_motion assertion and nothing else, so neither was touched.

### THE SIDE QUESTION

Not in scope (ruled): the "How the model works" link inside an open card's
Why panel (`a.face-more`) is 17.4px tall at 390 and 375, and no test measures
it. It leaves with the board, and the board merge's step 3 checks every tap
target, links included, at 390 at rest.

### THE PROVER *(2026-09-27; scratchpad `q20/`; the repo's own browser test world, never the live app)*

- **The per-frame test on the code before the fix**: `git archive` of f66fefa
  with this `test_smoke.py` copied in, 10 runs of 10 FAILED (10 to 26
  readings a run in 256 to 261 frames of 19 arrivals: `button.took` at
  53.99951171875 and 54.00048828125px, `button.expand` at 43.99951171875 and
  43.9998779296875px). **On the fix**: 10 runs of 10 PASSED (reported
  PASSED, not skipped), and once more in the full suite.
- **Every other redraw the page does, every frame** (a sampler of its own,
  started before each act and ended when the page had been quiet for twenty
  frames with no transition running; a wider set than the test's -- every
  `a`, `button`, `select`, `summary`, `input` and `.expand` with a box):
  the hash to the week; Record, Results, Settings and back; each of the nine
  market chips; each option of the market select; each of the three slates
  in the week picker; "This week" opened and shut; Upcoming and Live; three
  cards opened and closed by a real tap (the page scrolled to them); a card
  open when a market chip redraws the slate; "I took this"; each of the five
  sports and back; the Record page's forecaster picker and market select;
  Results' market and outcome filters. 64 redraws at 390 at three device
  pixels to one and 64 at 375 at two, about 2,490 frames and 102,000
  readings each, 30 arrivals of the Today panel each. **On the fix, not one
  reading off whole or under 44** but `a.face-more`, which reads 17.390625px
  on every frame it is open, the same as at rest -- the side question, ruled
  out of scope, not a movement. On f66fefa the same sampler read 45 (390)
  and 21 (375) off whole, 11 and 6 of them under 44, every one inside the
  Today panel on a frame it was moved.
- **Not there to redraw**: the tier filter and the sort toggle went with the
  controls line on 2026-09-08 (THREE_STATES S1): no `#week-sort-seg` and no
  tier button is in index.html, `setTier` has no caller and `wireSortToggle`
  returns at once. This world has no pick below the floor, so the fold was
  not shown. A fractional scroll lands on a whole pixel in this browser;
  scrolled to five places down the slate at rest, nothing read off whole.
- **Seen, not changed (not this item)**: with a card open, a market chip's
  redraw closed it and the page jumped from 855px down to 145px (question 18,
  ruled: fixed in the board).
- **Renders at rest** (`q20/render/`): at 390 (3x) the top of the week and
  the Today panel are byte for byte f66fefa's; at 1100 the Today panel is
  too, and the top differs in 7 pixels by one colour step (x 24-26, y
  513-519, the anti-aliased left edge of the Upcoming button), the same on a
  second render of each tree -- a rasterisation difference, nothing a reader
  sees. At 1100 a `summary` (18.8px) and two colophon links (17px) are under
  44 on both trees; desktop width is outside the 390 rule.
- **The planting ESCAPES on f66fefa** (NOT CAUGHT, "nothing reads a panel's
  arrival"; that tree's `motion_faults` is `[]` on its own moving stylesheet
  and `check_motion_vocabulary` passes it) **and is CAUGHT on the fix.**
  **Neutralised in a copy of the fix, one part at a time**: the scan made
  blind -- its import check refuses the module ("A SCANNER IS BLIND"); blind
  with that check removed, the start-state check dropped, `translate` taken
  out of the movements, `all` let through, a shorthand naming no property
  not read as `all`, index.html's names not read, the classes `arrive` adds
  not read, the panel-duration branch dropped, the gate's own call made a
  no-op, and (below) the gate's row taken out or left as a comment -- each
  NOT CAUGHT, naming the forms it let through.
- **FOUND AND FIXED: THE GATE ROW.** With the row taken out of `verify.py`'s
  step 2, or left there only as a comment, the planting as first built still
  said CAUGHT and no guard said anything: `check_no_orphan_functions` counts
  the planting's own `getattr` of the name as a caller. The planting now
  reads step 2's syntax tree for `audit.check_a_panel_holding_tap_targets_
  arrives_by_its_fade_alone` as an attribute of `audit` (a comment cannot
  stand in for it), as question 15's scan is pinned by
  `test_no_replacing_write.py::test_the_gate_runs_the_scan_in_step_two`.
- **The gate's step 2, dry-run** (the new row and twelve source-only
  neighbours, `GRIDIRON_VERIFYING` set, no record check): 13 of 13 pass.
  `check_no_test_waits_on_the_clock` passes and `ELAPSED_TIME_HELD` is 28
  functions and 44 waits, as on f66fefa. `prose_reaching_the_raw_side()` is
  `[]`.
- **The harness**: `tools/guards/plant.py` whole, 338/338 planted
  violations caught, exit 0. **The suite** (a dummy access token, TMP at its
  default): 1975 passed, 8 skipped, 2 failed --
  `test_nothing_moves_under_reduced_motion` (Q5's known race) and
  `test_the_dumbbell_and_contribution_bars_fit`, which is not a known
  flake. Each passes alone 5 of 5.
- **FOUND, AND HELD FOR A RULING (`docs/REPAIR_STATE.md` question 28): THE
  MOVEMENT WAS HIDING A RACE IN THE TESTS.** Several tests set the hash,
  wait for a card the previous render already drew, and tap its Why. The
  hash change's redraw then rebuilds the panel and closes the card. On
  f66fefa the Why moved while the panel arrived, and Playwright waits for a
  target to stop moving before it taps, so the redraw always came first. A
  scratch copy of the steps, 30 fresh sessions per tree
  (`q20/race/`): on f66fefa the redraw came first 30 of 30 times; on the fix
  it came after the tap 11 of 30 times, and each time the card was closed.
  The whole `test_smoke.py` file failed 2 of 3 runs on f66fefa, only on the
  reduced-motion race, and 4 of 6 runs on the fix, on the dumbbell test
  twice, the bucket-line test once and the phone card-expands test once.
  Q20 is not committed until the operator rules.
