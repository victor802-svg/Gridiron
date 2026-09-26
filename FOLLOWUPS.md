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

### Both sides of one total were recommended *(measured 2026-09-23)*

Recs 45 and 46, 2026-09-21T22:13:03Z, game `mlb_824787` (Toronto at
Baltimore): over 7.5 from the statistical forecaster, under 7.5 from the
reasoning forecaster, both at 48.5¢. Taking both is a certain loss of two
fees. Nothing reconciles two forecasters' opinions about one question.

**What would settle it:** a rule, the operator's, for which forecaster
recommends when both clear. Then a planting that fails on two sides of one
question.

### Duplicate recommendations inflate the closing-line count *(measured 2026-09-23)*

13 game-market pairs carry more than one recommendation, because the morning
and final passes each write a prediction for the same question. **35 closed
spread recommendations are 26 distinct bets; 14 totals are 11.** The gate of 50
counts rows. `standing_row_clause` exists for exactly this and is not used
here.

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

### `final:cfb` leaves `running` rows and exits 1 *(measured 2026-09-23, cause not proven)*

4 of its rows never recorded an ending: 2026-09-09T19:41:45Z,
2026-09-21T06:29:42Z, 22:11:39Z, 2026-09-23T19:30:06Z. Windows reports exit 1
for the last. **Hypothesis:** the closing `UPDATE task_runs` in `run_task`
(`tasks.py:268`) is outside the `try`, and each orphan started inside a burst
of catch-up firings after a wake. A locked database on that one write leaves
the row `running`. Not reproduced, because reproducing it writes.

### Two counts of one record on the learning panel *(measured 2026-09-23)*

MLB spread at the venue's line: the outlook says "128 of 100 · ~228
expected" and the gate line says "80 of 100 settled comparisons · 20 more".
The outlook counts claims; the gate counts standing comparisons. The first
reads as cleared and is not. This is the ONE CLAUSE failure again.

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

### The machine was off for nine days *(measured 2026-09-23, not a code defect)*

Shut down 2026-09-11T21:18Z, booted 2026-09-21T06:23Z. Awake 6.2 of 285.8
hours since the 12th, and 17 slates were missed for good. Every `Gridiron-*`
task has `WakeToRun = False`. Sleep, wake timers and whether the tasks may
wake the machine are the operator's to set. Recorded so nobody reads the
missing days as the model's.

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
