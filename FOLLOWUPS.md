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
  lands.)* *(And from 2026-09-28, question 24: a change ABOVE every number
  given out is refused -- it took the row out of that rule's reach; a
  change within them still lands, and stays in reach.)*
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
  *(2026-09-28, question 24, measured: only while the mark is set back in
  one step and nothing newer is moved. With its row deleted first, or set
  forward, a row moved beneath it, and set back -- or, its prover found,
  set back in one step and every newer recommendation moved down beneath
  it -- any recommendation can be made the newest and then written over;
  not seen by any rule, below.)*
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
  protected by "below any stored one" *(2026-09-28, question 24, measured
  on this tree's rules: only while the mark is set back in one step and
  nothing newer is moved; with its row deleted first, or set forward, a
  forecast moved beneath it, and set back -- or set back in one step and
  every newer forecast moved down beneath it (question 24's prover) -- any
  forecast can be made the newest and written over -- "No recommendation
  moved above every number given out", below)*. *(The
  prover, below: the set-back can also be done inside the replacing
  statement, by a temporary rule the connection makes; and "below any
  stored one" is proved by a planting form and a test of its own.)*

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
  released and this ruling names predictions: for the operator. *(Ruled
  2026-09-28, question 24, and built the same day: "No recommendation
  moved above every number given out", below.)*
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
  Q20 is not committed until the operator rules. **RULED (A) on 2026-09-28;
  built in Q20's commit, below.**

### THE TESTS THAT TAPPED BEFORE THEIR OWN REDRAW -- built 2026-09-28 *(operator question 28, ruled (A); docs/briefs/2026-09-28-rulings.md; in Q20's commit; the repo's own browser test world, never the live app; scratchpad `q28/`)*

The ruling: "(A). In Q20's commit, the affected tests wait inside the page for
their own redraw's arrival to start and end. One shared helper, no clock, no
fixed wait; Q5's signal replaces it later."

- **THE HELPER**: `tests/conftest.py::wait_for_the_redraw_it_starts(page)`,
  beside the browser fixtures -- conftest is where this tree keeps what more
  than one test file shares (`asks_only`, `seed_a_sent_prompt`, `_serve`). A
  context manager, so the arming cannot come after the action: entering it
  installs a MutationObserver on the Today panel's class (`_ARM_THE_REDRAW`);
  the action that redraws the slate runs inside the block; leaving it,
  `page.wait_for_function` waits for the page's own flag, with an upper limit
  of 15 s (`REDRAW_LIMIT_MS`, the slate's own waits' limit) and nothing else.
  THE START is the `arriving` class going on, or set again while on, after
  arming -- read from each mutation record's old value and the next one's, so
  a class that went on and off between two callbacks is still seen, and the
  class coming OFF (an arrival already under way when armed, such as the boot
  render's) is never a start. THE END is the class gone and
  `#today.getAnimations()` empty, read on each animation frame after the
  start -- the per-frame check's own reading (`WATCH_ONE_ARRIVAL`). Under
  reduced motion no transition runs, and the end is the frame the class comes
  off. An action that starts no redraw fails at the limit by name ("THE REDRAW
  THIS TEST STARTED NEVER STARTED ..."), never on the render before it. No
  clock read, no sleep and no fixed wait, in Python or in the page:
  `check_no_test_waits_on_the_clock` passes and `ELAPSED_TIME_HELD` is
  unchanged, 28 functions and 44 waits (no test changed here held a wait, so
  none lost one). Its comment is dated and says Q5's render-finished signal
  replaces it.
- **THE TESTS POINTED AT IT, found by the shape** -- a redraw the test starts,
  a wait the render before it already satisfies, then a tap inside `#today` --
  read in every browser test file. Each changed only where it sets the hash;
  no assertion, tolerance or wait of its own changed. `test_smoke.py`:
  `_open_first_card` (so `test_the_pick_states_model_market_and_gap_in_words`,
  `test_no_graph_is_drawn_anywhere_on_picks`,
  `test_the_bucket_line_never_shows_an_accuracy_without_its_n` and the skipped
  `test_a_card_with_no_market_line_says_so_in_words`),
  `test_a_card_expands_and_shows_its_detail`,
  `test_nothing_moves_under_reduced_motion` (Q5's known race: nothing moves
  under reduced motion, so it raced before Q20 too),
  `test_the_phone_layout_does_not_overflow`,
  `test_a_card_still_expands_on_a_phone` and
  `test_the_dumbbell_and_contribution_bars_fit`;
  `test_prompt_disclosure.py::test_a_reasoning_card_shows_its_prompt_inside_why`
  (both widths); and ONE NOT ON THE PROVER'S LIST,
  `test_cards.py::test_a_card_expands_in_place_and_shows_the_why`. Its
  `_open_week` waits for the week's response, then for a face and the panel
  at opacity 1, both met by the render before it until the new one lands, and
  it clicks the Why inside the page, where nothing waits for stillness. A
  probe of its steps (`q28/race/test_cards_probe.py`) saw the click land
  before that redraw 2 times in 90 fresh sessions on the fix and 0 in 90 on
  f66fefa: a narrower window than the others', and not shown to be Q20's.
  Unchanged, the real test passed alone 20 of 20. The call in that one test is
  wrapped; `_open_week` and its other callers, none of which taps inside
  `#today`, are not.
- **SEEN WITH A LIKE SHAPE, NOT CHANGED**:
  `test_smoke.py::test_a_pending_row_shows_five_things_and_hides_the_rest`
  (skipped since 2026-09-08, RE-POINT NEEDED: it reaches the old grid card's
  `.card-head`, and its re-point is its own act);
  `test_smoke.py::test_every_tap_target_on_the_slate_is_big_enough` and
  `::test_every_moving_thing_is_inside_the_motion_vocabulary` (they set the
  hash and measure, with no tap; with the fade alone every frame measures the
  same); `test_motion.py::test_a_tab_switch_arrives_through_the_motion_block`
  (it presses a market chip, which is outside `#today`). **For Q5, not this
  item:** `test_prompt_disclosure.py::test_results_shows_each_reasoning_row_the_prompt_it_carries`
  picks the reasoning pass on Results, waits for a prompt box the unfiltered
  table may already hold, and opens it. That is the Results table's redraw,
  not the Today panel's: it has no arrival class to wait on, and Q20 touched
  nothing there. The phone test beside it already waits for the filtered
  table (its Forecaster column gone).

### PROVED *(2026-09-28; scratchpad `q28/`)*

- **Each changed test alone, 5 runs of 5**: the nine in `test_smoke.py` (the
  skipped one skipped each time), the Why test in `test_prompt_disclosure.py`
  (both widths each run) and the card test in `test_cards.py`.
- **The whole of `test_smoke.py`, 6 runs of 6**: 73 passed and 4 skipped each
  (the fix without the helper failed 4 of 6, the prover's count).
  `test_cards.py` whole, 3 of 3 (27 passed, 4 skipped);
  `test_prompt_disclosure.py` whole, 3 of 3 (7 passed).
- **THE RACE COPY** (`q28/race/test_race.py`: the prover's `q20/race` steps,
  30 fresh sessions at 390 (3x), with the helper armed before the hash is
  set and waited on after it): with the helper, 0 of 30 cards lost and 0
  redraws after the tap, both at normal motion and under reduced motion.
  Without the helper, on the same tree, 17 of 30 cards were lost (the prover
  counted 11), and 24 of 30 under reduced motion. Every lost card was one
  whose redraw landed after the tap.
- **THE HELPER'S EDGES** (`q28/race/test_helper_edges.py`): under reduced
  motion it saw the start and the end one frame apart, and returned with the
  class off, no transition and opacity 1 (5 of 5). At normal motion the same
  took 14 or 15 frames (5 of 5). The hash set to what it already was failed
  at the 15 s limit with "NEVER STARTED". The class taken off after arming
  was not counted as a start.
- **The clock**: `plant.py::plant_a_test_that_waits_on_the_clock`, run
  alone on this tree: CAUGHT, and it named only its own four planted tests,
  none of the changed ones.
- **The full suite** (a dummy access token, TMP at its default), once: 1977
  passed, 8 skipped, 0 failed, in 18 minutes. The prover's run on the fix
  without the helper had 1975 passed and 2 failed.

### THE PROVER OF Q20 + Q28 *(2026-09-28; scratchpad `q20/p28/`; the repo's own browser test world, never the live app)*

- **THE RACE COPY, REBUILT** (`p28/race/test_race.py`): the Q20 prover's
  steps, 30 fresh signed-in sessions at 390 (3x) -- the hash set to the week
  inside the tree's own `wait_for_the_redraw_it_starts`, a face waited for,
  the first Why clicked -- then let settle in the page (an arrival seen and
  the panel at rest) and 1.5 s more (scratch only, for any later redraw). On
  this tree: 0 of 30 cards lost at normal motion and 0 of 30 under reduced
  motion; in every run the helper returned with the hash change's arrival
  seen and over (class off, no transition) and the tap came after it. On a
  copy of this tree with the helper made a no-op (`p28/nohelp`; the same test
  code): 10 of 30 lost at normal motion and 23 of 30 under reduced motion,
  each exactly a run whose redraw landed after the tap.
- **THE HELPER IS WHAT DOES IT**: `test_smoke.py` whole on that copy FAILED
  6 runs of 6 -- 15 failures across eight of the nine tests changed here
  (the phone card-expands test 4, the model-market-gap test 3, the no-graph
  and bucket-line tests 2 each, the card-expands, reduced-motion,
  phone-layout and dumbbell tests once each), every one a Why panel that
  never became visible. On this tree: 6 runs of 6 passed.
- **ITS EDGES, BUILT TO PASS EARLY OR HANG** (`p28/race/test_edges.py`; the
  week's response HELD by a route until released, never delayed by a
  clock). Armed while an earlier render's class was still on (armed inside
  the page, on that class going on), 5 of 5, and while its fade still ran
  (the real context manager), 5 of 5: the helper had not started when that
  arrival was over and the action's response was still held, and ended only
  after the release and the action's own arrival (13 to 15 frames). An
  action that redraws nothing, and a payload with no Today block (the panel
  hidden, no arrival): each fails by name at the 15 s limit, "NEVER
  STARTED". Reduced motion: started and ended one frame apart, 5 of 5. A
  redraw with no cards (every list emptied): started and ended, 13 frames.
- **ONE CASE PASSES EARLY, AND NO CALLER CAN REACH IT**: a redraw asked for
  BEFORE arming, still in flight, landing after arming and before the
  action's own render begins. The observer cannot tell one render from
  another, and the helper returned with the action's response still held.
  Once the action's render has begun the page drops any earlier one
  (`weekSeq`; built: the earlier response released after the action's
  request, no arrival from it, the helper ended on the action's), so the
  window is only between arming and the action. Every caller arms after
  `ready`, which boot sets once its own render has landed, and nothing
  redraws the slate unasked (the live tick patches in place), so nothing is
  pending at any caller. Not changed in code -- telling renders apart takes
  the page's own word -- and written into the helper's comment and
  docstring as its precondition, and into CLAUDE.md's row. **For Q5**: the
  render-finished signal should say WHICH render finished, which is the one
  thing this helper cannot see.
- **Whole files on this tree**: `test_smoke.py` 6 of 6,
  `test_prompt_disclosure.py` 3 of 3, `test_cards.py` 3 of 3, exit 0 each.
- **The per-frame check**: on `git archive` of f66fefa with this tree's
  tests and `plant.py` (`p28/head`), FAILED 3 of 3 (22, 14 and 18 readings
  in 262 or 263 frames); on this tree PASSED 3 of 3, and in the suite.
  **The planting**: NOT CAUGHT on f66fefa ("nothing reads a panel's
  arrival"), CAUGHT here. `plant_a_test_that_waits_on_the_clock`: CAUGHT,
  naming only its own four planted tests.
- **The clock**: `check_no_test_waits_on_the_clock` passes, `ELAPSED_TIME_
  HELD` 28 functions and 44 waits before (e016e93) and after, its source
  identical. `prose_reaching_the_raw_side()` is `[]`.
- **The harness, WITHOUT OPENING THE LIVE RECORD** (this step's hard
  constraint; `p28/plant_whole_isolated.py`: the state in a scratch
  directory, `db.read_the_live_record` and `back_up_the_live_record`
  refused, the network shut in-process, `plant.main()` unchanged): 327/338.
  The eleven not proved are the ten plantings that read the live record's
  rows (reported NOT RUN) and `plant_a_test_that_opens_the_live_record`,
  whose scratch stand-in sits under the temp directory, which the guard
  exempts by design. None of the eleven reads a file this commit changes;
  on the Q20 tree with the record's read-only door the harness caught
  338/338 (the Q20 prover, 2026-09-27). SEEN, NOT CHANGED:
  `plant_double_resolution`'s `run.run_week` reached for the network 48
  times with an empty state (refused in-process; still CAUGHT). With the
  operator's state a cache may answer it; not measured.
- **The full suite** (a dummy access token, TMP at its default): 1977
  passed, 8 skipped, 0 failed, 1092 s.

## No recommendation moved above every number given out -- built 2026-09-28 *(operator question 24; docs/briefs/2026-09-28-rulings.md)*

"Q24: fix after Q20, same basis as Q15, own commit and planting." The
question as asked is `docs/REPAIR_STATE.md` question 24; the hole was found
by question 15's prover ("THE SAME HOLE ON RECOMMENDATIONS, NOT BUILT",
above). The basis is question 15's: its update rule's clause refusing a move
above every number given out, and its two forms -- the move above the mark,
and the sequence set back, which proves the rule on the number written's
"below any stored one". Question 13's rules are the ones released on this
table and are not touched.

### MEASURED FIRST *(2026-09-28; scratch worlds in memory built by 8b569dc -- the released 724a72d plus documents -- and by this tree; `scratchpad/q24/measure.py`; foreign keys on and off; SQLite 3.49.1)*

The planting's world: recs 1 and 2 standing on games of their own, rec 3
withdrawn and the newest, two forecasts with nothing recommended; the mark
(`sqlite_sequence` for the table) is 3.

- **THE HOLE, on 8b569dc.** A plain `UPDATE recommendations SET id = 10
  WHERE id = 2` lands (it takes no other row's place, so question 13's
  update rule lets it), and the mark stays 3. A one-row `INSERT OR REPLACE`
  whose number a function of the connection's answers 99 to the rules and
  10 to the row then writes another game's recommendation over rec 2: the
  rule on the number written sees 10 above the mark and nothing stored
  above 10. Taken the same way, foreign keys on and off: the move by `id`,
  `rowid`, `oid` and `_rowid_`, under `UPDATE`, `OR REPLACE`, `OR IGNORE`,
  `OR FAIL`, `OR ABORT` and `OR ROLLBACK`; followed by `REPLACE` instead;
  the number read as nothing to the rules; the number spelled `'10'`,
  `10.0`, `1e1`, `' 10'`, `(SELECT 10)`, `id + 8`, `CAST('10' AS
  INTEGER)`; a move to one above the mark (4); a move of rec 1, the oldest;
  an upsert whose number reads as a free one to the rules and rec 2's to
  the key, its `DO UPDATE SET id = 10` moving rec 2; and a temporary rule
  of the connection's own moving rec 2 inside an update of rec 1's close.
- **Held by a foreign key, with them on**: withdrawn rec 3 (its withdrawal
  points at it), and every row moved at once (`id + 10`). With them off,
  rec 3 moved and was written over from another game; on its own game the
  one-per-game rule refused the newcomer (the moved row stood, its
  withdrawal pointing at nothing). On the record's copy (below), only 65, 78
  and 111 of 111 have nothing pointing at them.
- **The hole closes itself at the next recommendation**: a plain insert
  after the move took 11, the mark followed, and a number read twice onto
  the moved row was refused. A move within the numbers given out (to 0)
  landed, and a number read twice onto it was refused -- the rule on the
  number written holds it.
- **The mark rewritten by statements** (the NOT SEEN family of questions 13
  and 15): with the table's row in `sqlite_sequence` deleted, a move of rec
  1 above every stored number landed and a number read twice wrote over it;
  and with the mark set forward to 100, rec 1 moved to 10, and the mark set
  back to 3, the same. Both are taken on predictions too, under question
  15's rules (the forecast moved and written over): one clears the mark
  (its rule reads NULL), the other moves the forecast while the mark is
  high. Either way the moved row is then the newest. The one-step set-back
  question 15 tested is still held for every row but the newest -- while
  no newer row is moved down beneath it (the prover, below, found that
  third way).
- **Lawful, unchanged**: a plain insert leaving the number to SQLite took 4
  (the mark 4); the close of an open recommendation landed.

**THE OTHER RULE SETS OF QUESTION 13'S SHAPE** (the brief asked; measured on
the same trees, NOT BUILT -- the ruling names recommendations):

- **`market_snapshots_never_replaced` / `..._by_update`**: no rule reads
  the number after an insert, so a number read twice writes over ANY stored
  snapshot with no move at all -- a free 99 or nothing to the rules and
  snapshot 1's number to the row (`INSERT OR REPLACE`), and `REPLACE` onto
  the newest -- foreign keys on and off. The move above the mark lands too
  (the update rule lists `id, prediction_id, kind` and replaces nothing).
  So there is no above-the-mark hole as such: the table has question 13's
  read-twice hole whole, never closed there. (Its update rule's
  `rowid`/`oid`/`_rowid_` gap is question 13's OPEN, above.)
- **`reasoning_prompts_never_replaced`**: the same -- a number read twice
  writes a new sent record over stored record 1 (free and nothing forms),
  foreign keys on and off. No move is possible: `reasoning_prompts_no_
  update` refuses every update.
- **`recommendation_regrades_never_replaced`**: the table's number is
  `recommendation_id`, a rowid alias with no AUTOINCREMENT, so no mark. No
  rule reads it after the insert: `INSERT OR REPLACE` and `REPLACE` whose
  recommendation reads as an eligible unlabelled no-side pick (X) to the
  rules -- its arithmetic, stamp and bar checked against X -- and as a
  labelled one (Y) to the row wrote X's figures over Y's label, foreign keys
  on and off. No move: `recommendation_regrades_no_update` refuses every
  update.
- **`predictions_never_replaced*`** (question 15): the move above the mark
  is refused; the mark-rewritten family above is taken.

### BUILT *(2026-09-28)*

- **`recommendations_never_moved_above_the_mark`** (BEFORE UPDATE, no
  column list): refuses an update whose new number is not its old one and
  is above `sqlite_sequence`'s mark for the table -- question 15's clause,
  word for word but the table's name -- in `recommend.NEVER_REPLACED`'s
  words under LAW 3: "An update may not move one above every number already
  given out, where a new one could be written over it". Nothing else is
  refused: a move within the numbers given out lands and stays in reach.
- **A RULE OF ITS OWN**, not a clause added to question 13's update rule:
  the record holds that rule, and a rule's text is never replaced on a
  record that holds it (`CREATE TRIGGER IF NOT EXISTS` would leave the old
  text; dropping it to restate it would leave the table unguarded
  meanwhile).
- **Declared last of the table's rules**, after `recommendations_never_
  replaced_by_the_number_written`: the record gains it on its first open
  after the release, after that rule, and SQLite runs a table's rules
  newest first, so a fresh build runs them in the order the record will.
  It runs first on every update, the closer's included, and asks one
  lookup of `sqlite_sequence`.
- **Dated notes, outside any rule's text**, in `schema.sql`'s comments on
  question 13's update rule and rule on the number written ("every stored
  recommendation is at or below that mark" was not so until this rule).
- **No writer changes.** `record_for` inserts naming no number; the closer
  updates the close, the number unchanged. No package, tool or planting
  moves a recommendation's number.
- **One test world changed, and one test's order.**
  `test_a_number_below_one_already_given_out_is_refused_and_one_above_lands`
  vacated number 4 by moving it up to 10, now refused; it moves it down, to
  -5, and asks about the same numbers (question 15's precedent). And
  `test_the_replace_rules_carry_the_words_and_run_first` now finds question
  13's three rules together before this one, where they were last.
- **Planting** `plant.py::plant_a_recommendation_moved_above_every_number_
  given_out`, its own: eleven moves above the mark (by id, rowid, oid,
  _rowid_, under OR REPLACE, spelled as text, one above the mark, the
  oldest, the withdrawn newest with foreign keys off, by an upsert read
  twice, by a temporary rule inside a close), each followed by the number
  read twice onto the moved row, and the sequence set back (held). CAUGHT
  means each refused under LAW 3 -- each move in this rule's words -- the
  recommendations, the withdrawals and the mark as stored; a new
  recommendation, a close and a move within the numbers given out still
  written, and a number read twice onto that one refused; and the proof:
  with this rule dropped, each move lands and the moved recommendation is
  written over; with the rule on the number written stripped of "below any
  stored one", the sequence form writes over rec 1.
- **Tests** in `test_recommend.py` (44 new): 37 moves refused in the words
  with the table, withdrawals and mark as stored (six conflict clauses by
  four names of the number, seven spellings, one above the mark, the
  oldest, the withdrawn newest and every row at once with foreign keys off,
  the upsert read twice, the temporary rule); the hole and what closes it
  by each verb (the move refused, a move within the mark landing in reach,
  and with the rule dropped the two statements writing over rec 2); the
  boundary (onto the mark lands, in reach; one past it refused); the
  sequence set back by each verb (every recommendation below the newest
  held, a move refused, the closer's update landing, and without "below
  any stored one" rec 1 written over); the words, no column list, and the
  order on a fresh build; and an older record gaining exactly the rule
  through `db.init`.

### THE REHEARSAL *(2026-09-28, 10:44-10:46Z; a copy of the record made through `db.back_up_the_live_record`, and a verified copy of that, never the record; `scratchpad/q24/rehearse.py`)*

The backup (1,078,771,712 bytes) verified into a second copy
(`rebuild.verified_backup`: 61 tables, 1,267,325 rows, integrity ok, every
sqlite_master row and every table's count and column checksums equal).
Before: 241 objects; 111 recommendations numbered 1 to 111, sequence 111;
`schema_diff.compare` against a fresh build of this tree found exactly this
rule missing (the reference holding it) and nothing else, 9 objects cosmetic.
`db.init` under this tree then made exactly the rule -- nothing gone or
changed -- with a fresh build's text byte for byte, last of the table's
rules after the rule on the number written; no table's count or column
checksums moved (60 tables, 1,267,312 rows), the sequence unchanged. After:
0 differences (242 objects each; the same 9 cosmetic: at_the_line_claims,
market_lines_raw, mlb_pitcher_starts, notifications, prediction_voids,
recommendations, sessions, teams, venue_quotes); a second `db.init` changed
nothing. On the copy's own rows, foreign keys on and off: the newest (111),
rec 2 and the newest with nothing pointing at it moved to 118 by `id`,
`rowid`, `oid` and `_rowid_`, and rec 1 to 112 (one above the mark) by
`UPDATE OR REPLACE`, were each refused in this rule's words; rec 111 moved
to 0 landed and a number read twice onto 0 was refused by the rule on the
number written; the close of open rec 111 landed and a plain insert took 112
(all rolled back); the recommendations' checksums and the sequence never
moved. **Deleted afterwards** (the operator's ruling of 2026-09-28): the
backup `record_backup.db` (1,078,771,712 bytes) and the `-shm` (32,768) and
`-wal` (0) SQLite kept beside it, the verified copy `record_verified.db`
(1,078,771,712), and the fresh build `fresh.db` (749,568; not a copy of the
record) -- about 2.16 GB. No other copy of the record was made.

### PROVED *(2026-09-28)*

- **The planting ESCAPES on 8b569dc** (`git archive HEAD` into
  `scratchpad/q24/head/`, this `plant.py` copied over it): all eleven moves
  taken, each named with the rows before and after (rec 2, or rec 1, or rec
  3, gone and the newcomer under the moved number); the sequence form was
  refused there, by question 13's rule on the number written, as it must be.
  It is CAUGHT here.
- **Each part is needed** (the planting and the file run against a copy of
  this tree with one part changed in `schema.sql`): this rule listing its
  column (`BEFORE UPDATE OF id`) -- the planting ESCAPES on the moves by
  `rowid`, `oid` and `_rowid_`, and 18 of the 37 forms and the words test
  fail; the rule without "its number is not its old one" -- the planting
  still catches (no move is refused that way), and both sequence tests fail,
  the closer's update refused once the mark is set back below it: held by
  the test, as question 15 holds its two parts the planting does not need;
  and the rule on the number written without "below any stored one" -- the
  planting ESCAPES on the sequence form, and both sequence tests fail.
- **The new tests fail on 8b569dc** (this `test_recommend.py` run over the
  archive): all 44, and the changed order test; the changed test world
  passes there, as it must.
- **The harness**: 339/339 caught, exit 0 (this planting the 339th).
  **The full suite** with a dummy access token and the temporary
  directory at its default: 2021 passed, 8 skipped, 0 failed, exit 0,
  10:48-11:07Z, no rerun needed (1977 before, and the 44 new). After two
  comment-only edits (`schema.sql`, the planting's docstring) the files
  they touch were run again -- `test_recommend.py`, `test_schema.py`,
  `test_the_schema_matches.py`, `test_no_replacing_write.py`,
  `test_schema_diff.py`, `test_predictions_never_replaced.py` and the
  harness list: 381 passed, exit 0 -- and the harness alone again,
  339/339.

### READINGS TAKEN *(each reversible in one line)*

- **"Same basis as Q15" is question 15's clause, as a rule of its own.**
  The same text but the table's name, NULL mark included: with the table's
  row in `sqlite_sequence` removed the rule reads nothing and lets the move
  through, exactly as question 15's does. Treating a missing mark as 0
  would close that one variant and not the others (the mark set forward and
  back around the move; the mark set back and the newer rows moved down
  beneath it, the prover's), and would make the two tables' rules differ;
  all are NOT SEEN, below. (Reversal: `coalesce((SELECT seq ...), 0)`.)
- **Its own planting**, as the ruling says, not forms added to question
  13's (`plant_a_replaced_recommendation` is unchanged and still CAUGHT).
- **Question 15's second form is applied here as well** (the sequence set
  back, proving "below any stored one" on this table's rule on the number
  written): the brief names both forms; it is refused on 8b569dc too, and
  is held so a later change cannot open it.
- **The other rule sets were measured, not built**: the ruling names
  recommendations. Each is reported above and below for the operator.

### THE PROVER *(2026-09-28, 19:15-20:15Z -- a second run: the first, 11:15-12:00Z, ended before its commit, and every figure below is this run's own; alone in the worktree, the change uncommitted; scratch worlds in memory built by a fresh `git archive HEAD` of 8b569dc into `scratchpad/q24/prove/head/` and by this tree; the record only through `db.back_up_the_live_record`; `scratchpad/q24/prove/`)*

- **173 forms, adversarially** (`probe_r2.py`: the first run's 136 and 37
  of this run's own; `probe2.py` to `probe5.py` and `probe_pred.py`;
  foreign keys on unless named), most a move of a stored
  recommendation followed by the number read twice onto it by `INSERT OR
  REPLACE` or `REPLACE`: the move by `id`, `rowid`, `oid`, `_rowid_`, `ID`, `"id"` and
  `[rowid]` under each of the six conflict clauses; the number spelled 24
  ways (`'10'`, `10.0`, `1e1`, `' 10'`, `'10 '`, `'+10'`, `'10.0'`,
  `'1e1'`, `'0010'`, `0xA`, `+10`, `- -10`, `10 * 1.0`, `abs(-10)`,
  `CAST`, `COLLATE`, `coalesce`, `iif`, `CASE`, `likely`, `unlikely`,
  `(SELECT 10)`, a query of the table itself, `id + 8`); one above the
  mark; the oldest; the withdrawn newest, and every row at once both ways
  round (keys off); `UPDATE ... FROM`; `RETURNING`; a temporary view's
  INSTEAD OF rule; temporary rules on the table, after and before an update
  of a close, and on a temporary table; upserts moving the row they land on
  (a number read twice, `excluded.id + 8`, the forecast-and-stamp key);
  `executescript`; an attached database; a number worked out by a
  connection's function INSIDE the update, six pairs of answers --
  measured: an update works out its new number once, and the rule sees the
  number the row gets --; `random()`, 300 tries; a move within the numbers
  given out (0, -1, -5, onto a vacated mark) then read twice onto it; and
  the sequence set back first. This run's own: a sequence row for the
  table in the connection's temporary store, and a temporary AUTOINCREMENT
  table or a temporary view named `recommendations` (the move made on the
  main table, the write read twice after); the number as a blob, `'0x0A'`,
  `'  10  '`, a real a hair off 10, a compound query, `(VALUES (10))`,
  NULL, or a connection's function; `RETURNING` left unread on an insert
  of two rows; temporary rules on another table, and a temporary view's
  INSTEAD OF rule, moving rec 2 above the mark and writing over it inside
  one statement; the move in a savepoint, released; the move and the write
  in one `executescript`; the world's own file attached under a second
  name, the move and the write made there; an insert from a query and a
  `REPLACE` of several rows whose number reads twice; `UPDATE OR FAIL`
  moving rec 1 within the numbers given out and rec 2 above them; and
  `random()` moving and writing, 300 tries. On 8b569dc 108 of the 169 in
  `probe_r2.py` wrote over a stored recommendation, and 2 of its 4
  temporary-rule forms (`random()`: 24 times in 300; `probe2.py`'s own
  `random()` loop 45 in 300). On this tree every move above the mark is
  refused in this rule's words, or fails before it (a datatype mismatch: a
  number given as NULL, a blob, or text that is no number); every move
  within lands, and a number read twice onto it is refused by the rule on
  the number written; `random()` wrote over nothing in 300 tries (and in
  `probe2.py`'s 300). An update works out its new number once, and the
  rule sees the number the row gets (a connection's function inside the
  update, six pairs of answers: one call each). A sequence row for the
  table in the connection's own temporary store does not reach this rule
  -- a rule of the main schema reads the main schema's sequence
  (measured) -- and a temporary table or view named `recommendations`
  shadows the connection's statements, never the rules. `UPDATE OR FAIL`
  keeps nothing when this rule refuses a row: its abort takes the whole
  statement back, the move within with it. `RETURNING` left unread still
  writes the mark back (5 after two rows).
- **Taken on this tree, 11 of `probe_r2.py`'s 169, none a move the ruling
  covers:** the mark rewritten three ways -- its row deleted, set forward
  and back around a move, set forward and back by temporary rules inside
  the moving update -- the NOT SEEN below; the sequence set back and the
  newest written over, question 13's NOT SEEN; five forms of THE OR FAIL
  FINDING below; and, FOUND BY THIS RUN, two of a fourth way round the
  mark: **the sequence set back in one step and every newer recommendation
  moved down beneath it** -- moves within the numbers the mark then shows,
  which this rule lets -- after which an older one is the newest and a
  number read twice writes over it (rec 2, after the newest was moved to 0
  under a mark set back to 1; rec 1, after recs 3 and 2 were moved below 0
  under a mark of 0; foreign keys off, since the withdrawn rec 3 is
  otherwise held by its withdrawal's key). The same on predictions under
  question 15's rules (`probe_pred.py`, both trees: forecast 2 and forecast
  1 written over the same way; with the sequence intact the same move and
  write are refused). So question 15's "every other is still held" is true
  only while nothing newer is moved: corrected, dated, where the change
  said "only while the mark is set back in one step" (CLAUDE.md's rows for
  questions 15 and 24, `schema.sql`'s comments on question 13's rule on the
  number written and on this rule, and this file's notes above). It needs
  the mark rewritten first, so it is the NOT SEEN family, not the move this
  ruling names; nothing is built for it.
- **FOUND: A STATEMENT STOPPED UNDER OR FAIL LEAVES ITS ROWS ABOVE THE
  MARK** (not a move; open, for the operator). SQLite writes the sequence
  back only when an insert statement ends, and a statement stopped under
  `OR FAIL` keeps the rows it wrote before it stopped and never writes it
  back. `INSERT OR FAIL INTO recommendations (...) SELECT <a lawful row>
  UNION ALL SELECT <a row whose side is 'maybe'>` -- or the same as
  `VALUES (...), (...)`, or a second row with no forecast (NOT NULL) --
  stops at the second row with the first stored as rec 4 over a mark of 3;
  committed, a one-row `INSERT OR REPLACE` whose number reads 99 to the
  rules and 4 to the row then writes another game's recommendation over
  rec 4. A temporary rule raising FAIL after a one-row insert does the
  same, and so does a first row naming its number, 10, above the mark (kept
  at 10). Taken on 8b569dc and on this tree alike, and on predictions under
  question 15's rules (a forecast kept by `INSERT OR FAIL ... SELECT` whose
  second row failed NOT NULL, then written over). On the record's copy (the
  rehearsal, below; `orfail_copy.py`, after `db.init` under this tree) the
  same two statements on two forecasts of different games kept rec 112 over
  a mark of 111, and a number read twice wrote over it (rolled back). Held:
  a second row failing a foreign key, a datatype mismatch or a function
  that raises (SQLite takes the whole statement back), `OR IGNORE` (the
  statement ends, and writes the mark), `OR ROLLBACK`, a plain insert, and
  an interrupt from a progress handler at eight points (the statement is
  taken back). No writer writes under `OR FAIL` or raises FAIL (searched
  again: the package, `tools/`, `desktop/`), and the hole closes at the
  next insert that ends (`probe5.py`: a plain insert took 5, the mark
  followed, and a number read twice onto 4 was refused). It is not a
  move, so question 15's clause cannot
  close it, and what could is not question 15's basis: a rule refusing an
  insert while a stored row stands above the mark would also refuse the
  second row of every insert of several rows (the mark is written back only
  at the statement's end); a scan refusing `OR FAIL` against an
  append-only table is question 25's kind. Recorded in `schema.sql`'s
  comments and in CLAUDE.md's row.
- **Not a stored recommendation**: one statement inserting a row and, by a
  temporary rule after it, writing a second over the first under a number
  read twice -- the first never stood at the end of a statement, and
  nothing stored before the statement changes (measured, both trees).
- **The other rule sets, measured again on this tree** (`measure.py` whole,
  and `probe4.py`): the snapshot table -- a number read twice as a free 99
  or as nothing to the rules and snapshot 1's to the row wrote over
  snapshot 1, `REPLACE` over the newest, and a move above the mark then the
  same; the prompt record -- record 1 written over both ways, every move
  refused by its no-update rule; the re-grades -- X's figures written over
  Y's label by both verbs; foreign keys on and off -- as reported above.
- **A shipped writer of the sequence** (found by this run; the change said
  none): `rebuild._rebuild_one` deletes a rebuilt table's row in
  `sqlite_sequence` and writes it again with the value it read before the
  rebuild. It carries the mark exactly, so it opens nothing on a record
  whose rows are all at or below it -- the record's copy: recommendations
  1-111 under 111, predictions up to 3152 under 3152 -- but a scan for the
  NOT SEEN's precondition would name it (corrected in NOT SEEN, below).
- **The planting ESCAPES on 8b569dc** (this `plant.py` copied into the
  fresh archive as `tools/guards/plant_q24.py`, the archive's own left as
  it was; `run_planting.py`): 11 of 11 moves taken, each named with its
  rows before and after; the sequence form refused there. CAUGHT on this
  tree and on a copy of it, its first refusal the move by id in this
  rule's words.
- **Each clause neutralised in a copy of this tree** (`neutralise.py`, on
  fresh copies of the working tree; the planting, and `test_recommend.py`
  whole): the rule never firing -- the planting ESCAPES (11 moves), 43
  tests fail; `BEFORE UPDATE OF id` -- ESCAPES on `rowid`, `oid`,
  `_rowid_` (3 moves), 19 fail (18 forms, the words); without "its number
  is not its old one" -- CAUGHT, 2 fail (the sequence set back: the
  closer's update refused); without "above the mark", a freeze -- the
  planting fails on the move within the numbers given out, 6 fail; `>=`
  for `>` -- CAUGHT, 1 fails (the move onto the mark); the mark looked up
  under another table's name -- ESCAPES (11 moves), 43 fail; question
  13's rule on the number written without "below any stored one" --
  ESCAPES on the sequence form, 2 fail. Each part is held by the planting
  or a test.
- **The new tests on 8b569dc** (this `test_recommend.py` over the archive
  as `tests/test_recommend_q24.py`, 131 tests): 45 fail -- the 44 new and
  the changed order test -- and every other passes, the changed test world
  among them. Here the file passes, 131 of 131 (19:29-19:34Z).
- **The harness** alone (19:34-19:40Z): 339/339 caught, exit 0; this
  planting the 339th, CAUGHT.
- **Gate step 2's rows, run alone** (`step2_dry.py`, the question 15
  prover's driver: `verify.step_2_guards` with its harness row stubbed and
  `GRIDIRON_VERIFYING` set; the temporary directory pointed at
  `scratchpad/q24/prove/gate_tmp/`, so the gate's copy went through the
  backup door there, and the gate dropped it itself; 19:41-19:44Z): 92
  PASS, 0 FAIL; the live record against master (724a72d) and the migrated
  copy against this tree each 0 registered differences outstanding (9
  objects cosmetic); the live record's schema as found, 241 objects.
- **The rehearsal again** (19:44-19:47Z; `rehearse_r2.py`: a new backup
  through the door, 1,081,335,808 bytes, and a verified copy of it: 61
  tables, 1,280,217 rows, integrity ok, nothing mismatched): one sequence
  row each for recommendations (111; rows 1-111) and predictions (3152;
  highest 3152), nothing stored above either mark; before, exactly this
  rule missing against a fresh build; `db.init` added exactly it, nothing
  gone or changed, a fresh build's text byte for byte, last of the table's
  rules; no table's count or column checksums moved (60 tables, 1,280,204
  rows), the sequence unchanged; after, 0 differences (242 objects each, 9
  cosmetic); a second `db.init` changed nothing; every move of the copy's
  own rows above the mark (111, 2 and the newest with nothing pointing at
  it, to 118 by `id`, `rowid`, `oid`, `_rowid_`; rec 1 to 112 by `UPDATE
  OR REPLACE`) refused in this rule's words, keys on and off; rec 111
  moved to 0 landed and a number read twice onto 0 was refused; the close
  of open rec 111 landed; a plain insert took 112; and the OR FAIL finding
  as above (rec 112 kept over 111 and written over); all rolled back, the
  recommendations' checksums and the sequence never moved. Only 65, 78 and
  111 have nothing pointing at them. **Deleted afterwards**:
  `record_backup.db` (1,081,335,808 bytes), its `-shm` (32,768) and `-wal`
  (0), `record_verified.db` (1,081,335,808), and `fresh.db` (749,568; a
  fresh build, not a copy); no file of a database is left under
  `scratchpad/q24/`.
- **`audit.prose_reaching_the_raw_side()`** is `[]`.
- **The full suite** on the change with this run's comment and document
  corrections (a dummy access token, the temporary directory at its
  default; 19:49-20:08Z): 2021 passed, 8 skipped, 0 failed, exit 0. No
  known-racy browser test failed, so none was rerun; the one test listed as
  reaching the network is `test_the_network_is_shut.py::test_a_marked_test_
  is_allowed_out_and_is_named`, which is written to.

### THE LIVE RECORD AFTER THE RELEASE *(no tool)*

No row is written and no tool runs. The scheduler's first open of the
record under the released code (`db.init`, as every schema rule has arrived
since 5b) makes the one rule and nothing else; every recommendation stays as
written. Afterwards, read through `db.read_the_live_record`: sqlite_master
holds `recommendations_never_moved_above_the_mark` after
`recommendations_never_replaced_by_the_number_written`, with `schema.sql`'s
text. Until that first open the record lacks it while the release has it,
so the gate's release comparison is run after it, as with every rule since
5b.

### NOT SEEN, AND OPEN *(2026-09-28; not built)*

- **The mark rewritten by ordinary statements, on this table and on
  predictions.** SQLite lets a statement rewrite or delete its own sequence
  row and refuses any rule on that store. With the row deleted, this rule
  (and question 15's) reads the mark as nothing and lets a move above every
  stored number through; with the mark set forward, a move beneath it
  lands, and set back afterwards the moved row is above it; and set back in
  one step, with every newer row moved down beneath it -- moves within the
  numbers the mark then shows, which this rule and question 15's let --
  an older row is left on top (the prover, measured on both tables with
  foreign keys off: rec 2 and forecast 2 written over after the newest was
  moved to 0 under a mark set back to 1, and rec 1 and forecast 1 after the
  two above them were moved below 0). Each way that recommendation or
  forecast is then the newest, and a number read twice writes over it
  (measured, both tables, above) -- question 13's and 15's NOT SEEN,
  reaching any row rather than only the newest. No rule can
  see it. What a scan could see is its precondition: a statement writing
  `sqlite_sequence` in the shipped code, as question 25's ruled scan will
  see a connection switching the rules off (tests and plantings write it on
  purpose; and one shipped writer, the prover found: `rebuild._rebuild_one`
  deletes a rebuilt table's sequence row and writes it again with the value
  read before the rebuild, so a scan would name it and need it registered).
- **OPEN, NOT A MOVE: a statement stopped under OR FAIL** (this rule's
  prover, above; measured on both tables, on 8b569dc and on this tree, and
  on the record's copy). The rows an insert wrote before it stopped under
  `OR FAIL` -- or before a temporary rule raised FAIL -- are kept, and
  SQLite never writes the mark back for it, so they stand above the mark
  until the next insert that ends, and a number read twice writes over
  them. A LAW 3 finding, for the operator's queue: question 15's clause
  cannot close it, and no writer writes that way.
- **The read-twice hole on the other rule sets of question 13's shape**
  (above): `market_snapshots`, `reasoning_prompts` and
  `recommendation_regrades` have no rule reading the number after an
  insert, so a number a connection's function reads one way to the rules
  and another to the key writes over any stored row. Each would need its
  own rule on the number written (the snapshot and prompt tables have a
  mark; the re-grades' number is a recommendation's, with none). For the
  operator: they break LAW 3 only through a function the connection defines
  (question 25's scan refuses one under a built-in's name, not every one)
  or `random()`.
- **Found in passing: the record's older rules on this table run in another
  order than a fresh build's.** On the copy, `recommendation_correction_is_
  frozen` (2026-09-26) comes after `recommendations_no_delete`, and on a
  fresh build before `recommendation_closes_once`: an update touching both
  the correction and a written close is refused in the one rule's words on
  the record and the other's on a fresh build. Both refuse it; nothing
  counts either's words. Not this ruling's.

## One function defines a distinct bet -- built 2026-09-28 *(operator question 17, step 1 of 2: the Record page's four gate records; with question 21; docs/briefs/2026-09-27-rulings-third-set.md and 2026-09-28-rulings.md)*

"Q17: one function defines a distinct bet: forecaster + the venue's question
(game, market, line). Morning and final pass of one question count once;
which pass counts stays each record's standing rule; alt lines are separate
questions. Q12's, Q14's and Q16's counts all use it. List every released
number that moves." And "Q21: the line the forecaster was asked (the rung).
Two rungs on one game are two questions." The brief of 2026-09-28 read the
key as the forecaster, the game, the market (`market_type`, and the prop
type for a prop), the subject and the rung asked (`line_asked`, NULL one
value). This step puts the function in and moves the four records the
Record page states gate counts for onto it -- at the venue's line, the
priced record, where the line went, and the line beside each blind curve.
Question 12's recommendation counts (question 22) are step 2. **A
MEASUREMENT RULE, NOT AN EDIT**: no row, table, column or schema object
changes; nothing is written.

### MEASURED FIRST *(2026-09-28, ~21:00Z; one copy of the record made through `db.back_up_the_live_record` into `scratchpad/q17/step1/`, read through `db.read_only`; deleted at the end of the step)*

- **Six keys counted a bet.** The standing clause, the priced door and the
  outlook door: the question (game, market, subject, rung), per forecaster.
  `drift.bet_of`: the game and market (the player for a prop) -- no rung.
  The at-the-line door: a window over game, market and side -- no rung, no
  subject. Its coverage line: the game alone. (Question 12's pairs: game
  and market across forecasters -- step 2.)
- **Games asked at two rungs, all passes, per forecaster**: NCAAF point
  spread 45 (statistical), MLB total 11 (statistical) and 8 (reasoning
  pass), NFL point spread 13, NFL total 1. Two players' lines of one game
  are two subjects, as they always were.
- **No forecaster's claims at the venue's line sit on two rungs of one game
  yet**: every at-the-line cell holds as many ruled keys as game-market-side
  keys (NCAAF spread 46, MLB moneyline 113 and 114, MLB spread 105, ...), and
  no claim's game or market differs from its forecast's.
- **The prop type.** Every stored prop's subject names its type, so the
  standing clause's question (game, market, subject, forecaster, rung)
  already carried it. 32 NFL week-one props of 29 August (fs1) have no
  prop type at all; 10 of their questions were answered again under fs2
  with one, and keyed by the prop type they are two keys. No count reads a
  prop with no type (every count asks a prop by its type), and with the
  prop type in the key, written `IS`, every blind curve of every sport
  counts what it did (2110 settled standing rows either way) and SQLite
  searches the question index as before (0.05 s against 0.06 s).
  **Not so (found by the numbers step, fixed 2026-09-29, "A prop's
  question is named by its subject" below):** three readers count a
  sport's markets together -- the factor table, the pick card's worst
  band, the tier table's pace -- and the eight settled pairs stood twice
  in them.

### EVERY FIGURE THAT MOVED, before and after *(the same copy each side; 088e538 archived and this tree, each building every at-the-line curve, ledger, coverage line and edge, every priced category, the gate list and learning panel of where the line went, the venue's own pair, and every blind curve with its line, for every sport; 799 figures, 45 moved; `scratchpad/q17/step1/{before,after}.json`, `diff.py`)*

| sport | where on the Record page | before | after | why |
|---|---|---|---|---|
| NCAAF | Where the line went, point spread, statistical (gate list and learning panel) | **65 pairs: "moved toward it 22% of the time over 65 games"** | **78 pairs: "28% ... over 78 questions"** | two rungs of one game are two questions (Q21); the step choosing between them is gone |
| NFL | Where the line went, point spread, statistical | 9 of 50 pairs | 10 of 50 pairs | the same |
| NCAAF | Where the line went, total, statistical | "15% ... over 54 games" | "15% ... over 54 questions" | the noun: a count of questions says questions |
| MLB | Where the line went, moneyline, statistical | "27% ... over 52 games" | "27% ... over 52 questions" | the same |
| NCAAF | At the venue's line, coverage, point spread, statistical | "46 of 142 games it forecast (32%)" | "46 of 187 questions it answered (25%)" | one per distinct bet, as the curve beside it |
| NFL | coverage, point spread, statistical | "14 of 29 games (48%)" | "14 of 42 questions (33%)" | the same |
| MLB | coverage, total, statistical / reasoning pass | "25 of 202 games (12%)" / "25 of 133 (19%)" | "25 of 213 questions (12%)" / "25 of 141 (18%)" | the same |
| NFL | coverage, total, statistical | "1 of 17 games (6%)" | "1 of 18 questions (6%)" | the same |
| every sport | every other coverage line (16 of the 21) | "... games it forecast" | "... questions it answered", the same numbers | the noun |
| MLB | the venue's own pair, point spread, statistical (in the payload, not painted) | 55: "27% ... over 55 games" | 56: "29% ... over 56 questions" | the opening read at the claim's own strike (alt lines are separate questions) |
| NFL | the venue's own pair, point spread, statistical (not painted) | 12 of 50 | 11 of 50 | the same |
| MLB | the venue's own pair, moneyline, reasoning pass (not painted) | "... over 57 games" | "... over 57 questions" | the noun |

**Unchanged, 754 figures**: every at-the-line curve, gate line, outlook,
ledger and edge (no claim sits on a second rung of its game yet); every
priced count (the priced door already kept the rung); every blind curve and
the line beside it (the outlook door already kept the rung; the prop type in
the key moves nothing). **No gate crossed a threshold either way**: NCAAF
point spread's drift was past the fifty and stays past it, its share moving
from 22% to 28%.

### BUILT *(2026-09-28)*

- **`gridiron.bet`, the one function.** `bet.KEY` is the key written once;
  `bet.of(row)` and `bet.count(rows)` in Python, `bet.columns(alias)` (a
  SELECT, so a door's rows carry the key off the forecast itself, and a
  window's PARTITION BY) and `bet.same(a, b)` (the SQL match, `IS`) in SQL,
  all from the tuple. A row without the key is refused by name
  (`bet.NotABet`). Closure-clean -- it imports nothing of the package and
  names no market data -- because question 16's correction, inside the
  blind import closure, will read it.
- **The doors.** `calibration.standing_row_clause` matches the question by
  `bet.same` both times it asks. `at_the_line.standing_claims` partitions
  its window by `bet.columns('p')` and selects the key off the forecast
  (the at-the-line record's own standing rule unchanged: the last claim
  before the start, the id breaking a tie). `priced.forecast.standing_forecasts`,
  `drift.standing_pairs` and `horizon.standing_questions` select
  `bet.columns`; drift's step keeping one pair per game is gone. The four
  `bet_of`, four `count_of_bets` and `calibration.distinct_bets` are gone;
  every `distinct_bets` is `bet.count`. The coverage line counts one per
  standing question, read when its key holds a standing claim, and says
  "questions it answered"; `language.drift_line` says "over N questions"
  past the fifty ("player lines" for a prop, as before), as the venue
  pair's line does.
- **The venue's own pair at one strike.** `drift._pairs_of` reads the
  opening ladder at the claim's own strike (`at_the_line.home_view_line`,
  both sides in the claim's view; a moneyline has none on either), and a
  claim whose strike the opening read did not quote has no pair: until
  this date the open half was the opening ladder's own line, so when the
  venue's line moved between the open and the start the pair compared two
  questions. `drift.venue_report` now carries its pairs' `distinct_bets`
  and `forecasters_counted`, how many standing claims the door handed it
  (`claims_read`) and the recount's (`recounted`).
- **THE RECOUNT** (`gridiron.recount`): each record's count worked out
  again from rows read straight off their tables -- no door, no standing
  clause, no window -- grouped by `bet.of`, by the record's standing rule
  restated in Python (`standing_of`: the blind record's; `standing_claims_of`:
  the at-the-line record's). Each builder asks it beside its door inside one
  read (`db.one_instant`: one read transaction, so a claim or forecast
  written between the two reads cannot make an honest count look pooled and
  the page answer 500) and puts it on the payload: `recounted` on every
  at-the-line curve, ledger and edge, priced category, drift category and
  blind outlook; `read_recounted` on a coverage line; `recounted_written` on
  an outlook; `claims_read`/`recounted` on the venue's pair. A priced market
  the recount holds is a category even where the door found none, and so is
  a coverage market, so a door that lost a whole market is seen.
- **The guards recount on it.** `calibration.assert_no_pooled_claims`,
  `assert_no_pooled_priced_counts`, `assert_no_pooled_outlooks` and
  `drift.assert_no_pooled_drift_counts` refuse by name a count the recount
  does not make, or a payload carrying none; the drift guard now also reads
  the venue's own pair, which had no guard. A door keyed without the rung,
  or across forecasters, agrees with its own `distinct_bets` -- only a
  count made without it sees it.
- **The source scan** (`audit.check_every_count_keys_one_bet`, gate step 2,
  "every count keys a distinct bet by the one function (question 17)"):
  refuses a function named as a key (`bet_of`, `count_of_bets`,
  `distinct_bets`), a `distinct_bets` counted by anything but `bet.count`, a
  window partitioned by anything but `bet.columns` (plain string or
  f-string), a standing clause not matching by `bet.same`, and a `bet.KEY`
  that is not the key as ruled (`audit.RULED_DISTINCT_BET`). On 088e538's
  source it names 18 places.
- **The gate names an at-the-line refusal.** `audit.check_the_at_the_line_record_is_never_pooled`
  (a step-2 row of its own, as the other three records have); the advice
  scan's build of the same payload (`tools/verify.py::_at_the_line_payload`)
  now fails its step by name where a guard's refusal ended the gate in a
  traceback; the three question-14 checks also name `bet.NotABet`.

### PROVED *(2026-09-28; each planting run by this tree's `plant.py` against a `git archive` of 088e538 in `scratchpad/q17/step1/head/`, and against this tree; `prove/`)*

- **`plant_a_door_keyed_without_the_rung`** (one NCAAF game asked at -14.5
  and -24.5, every record's rows): on 088e538 it ESCAPES at the honest
  world -- the Record page states 1 at the venue's line and 1 where the line
  went, 2 priced and beside the curve -- and each of its 13 doors swapped in
  past that (the at-the-line window as it stood, into the Record page, the
  curve, the ledger, the edge, the coverage line and the venue's pair; the
  priced and drift doors on a standing rule without the rung, the gate list
  and the learning panel; that rule as the blind clause itself, under the
  curve and its line, the coverage line, the priced record and the drift
  record) escapes too. Here, two bets in every record, and all 13 refused
  by name ("counts 1 where the recount made without its door finds 2").
- **`plant_a_door_keyed_without_the_forecaster`** (one MLB moneyline game,
  the reasoning pass a second after the statistical model): 088e538 states
  one bet each and lets all 13 doors through (the statistical model's
  question vanishing from its count); here all 13 are refused ("counts 0
  where the recount ... finds 1").
- **`plant_a_distinct_bet_keyed_by_hand`**: ESCAPES on 088e538 (no scan);
  here the shipped package passes and six planted keys are named -- a
  `bet_of`, a set-counted `distinct_bets`, a window keyed in a plain string
  and in an f-string, a standing clause matching by hand, and `bet.KEY`
  with the rung dropped.
- **The harness**: 342 of 342 caught (339 on 088e538, plus these three).
- **Flipped by the ruling, each said in its own text**: `plant_an_at_the_line_game_counted_twice`
  (its statistical spread at -1.5 and +1.5: one bet to two, the curve and
  the coverage line); `plant_a_drift_game_counted_twice` (its NCAAF game at
  two rungs: one bet to two; the probe "the standing rule without the bet"
  is the ruled count now and gives way to "one pair per game, the rung left
  out", refused by the recount); `plant_an_at_the_line_curve_pooling_two_forecasters`
  (a probe renamed: "a coverage line counting more questions than distinct
  bets"); the payload helpers of the four question-14/item-6 plantings
  carry an honest builder's recount. `tests/test_at_the_line.py` (the
  two-rung world is three bets, not two: `..._counts_one_claim_per_distinct_bet`;
  the withdrawal test asks one question twice; the refusals), `tests/test_drift.py`
  (`test_two_standing_rungs_of_one_game_are_two_bets`; the prop test's two
  rungs are two; "over N questions"; `test_two_rungs_counted_as_two_questions_are_refused`
  becomes `test_a_door_keyed_without_the_rung_or_the_forecaster_is_refused`),
  `tests/test_outlook.py` (two recount refusals added).
- **THE PROVER** (`prove/prove1.txt`, `prove_race.txt`): five more ways
  at a pooled count, each refused -- the at-the-line window keyed by the
  venue's strike and labelled the rung (the recount), the priced rows with
  the rung blanked (distinct bets), a drift door counting a question's two
  passes (distinct bets), the outlook door handing the reasoning pass's
  rows under the statistical model's name (the curve beside it), the
  ledger reading a question's every look (distinct bets). What got
  through, and was fixed before the commit: **a write between the door's
  read and the recount's made an honest curve refused** ("counts 2 where
  the recount ... finds 3": a 500 on the Record page while a scheduled task
  writes) -- the two now read one instant (`db.one_instant`), and
  `test_bet.py::test_a_write_between_the_door_and_the_recount_is_no_pooled_count`
  fails with it taken away and passes with it; **`bet.KEY` itself** could
  lose the rung and move door and recount alike -- the scan holds it to
  `RULED_DISTINCT_BET`; **the drift recount asked a wider cell** than its
  door for a market that is not a prop (no prop type, or any) -- it asks
  the door's own; and **the Record page stops at its first refusal**, so
  the plantings now swap each door under each figure it feeds (13 probes
  apiece). Not a count and not closed: a door choosing another pass of the
  same question keeps every count (the key's guards are about how many);
  each record's own standing-rule tests hold which.

### RENDERED *(2026-09-28; the browser suite's own world -- `seed_league` and `_build_world` -- on a scratch file, served by 088e538 and by this tree with the suite's test token; never the live app; `scratchpad/q17/step1/render.py`, `render/`)*

The world was given a second look at the line for every statistical NFL
forecast with a first look, seven final passes at seven other rungs for
each early point spread question with a first look (each under a factor-set
label of its own; so the drift count passes its fifty), and a claim before
the start for every standing statistical point spread forecast of a
settled game (the settled games' starts moved past today in the scratch
world, since its forecasts are written today). Read at 1100px and 390px:

- **At the venue's line**: 088e538 says "point spread, statistical: the
  venue's line could be read for 8 of 12 games it forecast (67%)" beside a
  curve of "8 of 100"; this tree "64 of 96 questions it answered (67%)"
  beside a curve of "64 of 100" and a ledger of 56. The coverage lines wrap
  inside the panel at 390px.
- **What the record has taught it**: point spread's drift line on 088e538
  "8 of 50 disagreements have a second look at the line ..."; here "When the
  model disagreed by 5% or more, the market moved toward it 81% of the time
  over 64 questions." -- the new noun in its sentence, readable at both
  widths.
- **What else is still counting**: "Where the line went after point spread,
  statistical · 64 pairs · enough pairs to report a direction" (088e538: 8
  of 50).
- No horizontal page scroll and no console error at either width, on
  either tree; no sentence contradicts another.

### READINGS TAKEN *(each reversible in one line)*

- **The prop type is a column of the key**, as the brief reads the ruling,
  `IS`-compared: a prop written with no type and one written '' are two
  questions. Reversal: drop `"prop_type"` from `bet.KEY` and
  `audit.RULED_DISTINCT_BET` (the subject carries it on every stored prop).
  **REVERSED 2026-09-29** ("A prop's question is named by its subject"
  below): it split ten week-one questions in two, and counted the eight
  settled ones twice.
- **The at-the-line record keeps its own standing rule**: a question's
  claim is its last claim before the start, whichever pass wrote it -- not
  the claim of the blind record's standing forecast ("which pass counts
  stays each record's standing rule"). Reversal: filter the door's claims
  to those whose forecast stands (`standing_row_clause`) before the window.
- **"Alt lines are separate questions" reaches the venue's own pair**: the
  opening read is taken at the claim's strike, and a claim whose strike
  the open did not quote has no pair. Reversal: `rung_for(ladder)` for the
  whole ladder in `drift._pairs_of`.
- **The recount restates each standing rule in Python**, beside the one SQL
  door: it is the guard, not a second door -- nothing counts through it --
  and it reads the key from `gridiron.bet` like every door, so the two
  differ only where a door keys or keeps otherwise. `RULED_DISTINCT_BET`
  holds the key itself to the ruling, since a key changed in `bet` would
  move door and recount alike. Reversal: drop the `recounted` checks.
- **A count and its recount read one instant** (`db.one_instant`), on the
  API's handle too; a connection already in a transaction is left as it is.
- **Plain words**: the coverage line says "questions it answered" and a
  drift line past the fifty "over N questions" ("games" was false for a
  game asked at two rungs; "question" is the slate headings' word).
- **The card beside a pick on the slate** counts through the at-the-line
  door (so from the one function) and is not recounted on the slate itself:
  the Record page's curve, which reads the same door, is.

### OPEN *(found by this step; none of them a count it states)*

- **`calibration.early_vs_final`** pairs a question's early and final pass
  by a join written out by hand (game, market, subject, forecaster, factor
  set, rung) -- a pairing, not a count of bets; it has no caller in the
  package and states nothing on the Record page. For the re-read, or
  question 16 if it is read there.
- **The pick card's at-the-line sentence** (`views._at_the_line`) chooses a
  forecast's claim by `created_utc = MAX(created_utc)`, so two claims of one
  forecast in one second both match and the dictionary keeps whichever
  comes last -- the 2026-09-10 tie the door fixed by id, on a sentence, not
  a count.
- **Step 2** moves question 12's recommendation counts onto `gridiron.bet`,
  per forecaster (question 22); question 16 the correction gates.
- **For question 27 (ruled in the second set of 28 September, ordered after
  question 16): the blind standing rule lives in two texts now** -- the one
  door, `calibration.standing_row_clause`, and the guard's restatement,
  `recount.standing_of`. Choosing the standing pass by pass (a final pass
  before the start stands, else the latest early one) changes both, in one
  commit: changed in the clause alone, every count it moved would be
  refused by its recount, by name -- the guard doing its work, not a
  defect -- and the at-the-line record's own rule (`standing_claims` and
  `recount.standing_claims_of`) is read by the ruling's "the at-the-line
  claims through it" too.

## The recommendation counts, per forecaster, on the one key -- built 2026-09-28 *(operator question 17, step 2 of 2; with question 22; docs/briefs/2026-09-27-rulings-third-set.md and 2026-09-28-rulings.md)*

"Q22: (A). Recommendation counts split per forecaster, like every other
count. This reverses Q12 for 45/46: each counts once in its own
forecaster's line, and the 'Both sides, no position' row goes. Same-side
pairs count once only within one forecaster. List every released number
that moves." On question 17's one function (`gridiron.bet`, step 1). **A
MEASUREMENT RULE, NOT AN EDIT**: no row, table, column or schema object
changes; nothing is written. Item 5's write rule (one recommendation per
game and market, across forecasters) is untouched.

### MEASURED FIRST *(2026-09-28, 22:34Z; one copy of the record made through `db.back_up_the_live_record` into `scratchpad/q17/step2/`, read through `db.read_only`; deleted at the end of the step)*

- **111 recommendations, 107 standing** (62, 63, 64 and 66 withdrawn), by
  forecaster: MLB spread 69 and total 2 the statistical model's, total 14
  the reasoning pass's; NFL spread 16 the model's, total 1 the reasoning
  pass's (65); NCAAF spread 9 the model's. Every row's `market` is its
  forecast's prop type or market type.
- **The eighteen game-markets holding two standing rows**: each of the
  seventeen same-side pairs is ONE forecaster's morning and final pass on
  ONE question at ONE rung (14 the model's, 3 the reasoning pass's: 4/12,
  23/28, 43/49) -- one distinct bet, still a pair. 45/46 are two
  forecasters' (45 the model's over 7.5, 46 the reasoning pass's under):
  two distinct bets. **No distinct bet on the record holds two sides**, so
  nothing stops for a ruling.

### BUILT

- **The door takes the forecaster.** `recommend.counted_once(conn, alias,
  *, predictor)` -- required, refused by name unless one of the two
  (`recommend.PooledCount`, `refuse_a_pooled_count`), read through the
  forecast the recommendation was made from -- so a count across both
  cannot be written by leaving an argument out. Its rule
  (`_an_earlier_row_of_the_same_bet`, `pairs_with`) pairs a standing row
  with another only on one distinct bet (`bet.same` over the two
  forecasts) and one side; the earlier (stamp, then number) counts.
  `not_counted_once`, `regraded` and `withdrawn` take the forecaster too.
  `BOTH_SIDES`, `BOTH_SIDES_LABEL`, the "other_side" rule,
  `calibration._both_sides_groups` and `language.both_sides_recommendations_line`
  are gone.
- **The closing line** (`calibration.clv_report`, `_closing_line_of`): one
  block per forecaster (`forecasters`: its window line, N, buckets,
  awaiting, withdrawn and re-grade lines, repeats, set-aside tallies) and
  one line per market and forecaster (`markets`, labelled
  `language.closing_line_label`: "total, reasoning pass"); no total over
  both. The window line says whose ("12 recommendations from the model");
  a repeat says "this forecaster's earlier recommendation on the same
  question and side". The renderer draws each forecaster's window line,
  market lines, withdrawn and re-grade lines, requires each block's N, and
  no both-sides row.
- **The kill criterion** (`priced.coverage.stopped`) is keyed by market and
  forecaster, each stop labelled; `priceable(..., predictor=...)` is
  required, and `recommend.for_predictions` passes the pick's own.
- **`tools/empty_bar.py`**: one forecaster's days (a day counts when one of
  its forecasts had a claim written that day, and clears when one of its
  recommendations counted once was).

### EVERY RELEASED NUMBER THAT MOVES *(the released code -- f0a4418, and c57354c, the same for these counts -- against this tree, on the one copy; `before.json` / `after.json`; 281 and 465 figures)*

| Sport | Figure | Released | This tree |
|---|---|---|---|
| MLB | window line | "16 recommendations priced against a close since" | statistical "15 recommendations from the model"; reasoning pass "1 recommendation from the reasoning pass" |
| MLB | point spread line | 15 of 50 · 23 with no later read · 17 restated · 14 repeats | "point spread, statistical": the same numbers (every spread is the model's); the repeat words now "this forecaster's earlier recommendations on the same question and side" |
| MLB | total line | 1 of 50 · 4 with no later read · 6 restated · 3 repeats | "total, statistical": 0 of 50 · 2 with no later read (45 and 81); "total, reasoning pass": 1 of 50 · 4 with no later read (46 among them) · 6 restated · 3 repeats |
| MLB | beside the lines | 27 unmeasured, 23 restated, 17 repeats; set aside 19 (3 measured) | statistical 25, 17, 14; set aside 14 (3 measured) -- reasoning pass 4, 6, 3; set aside 3 (0 measured) |
| MLB | "Both sides, no position" | 2 (45 and 46), counted nowhere | gone; 45 in the model's total, 46 in the reasoning pass's |
| MLB | "Would not have cleared" | 2 (recs 3 and 56) | "Would not have cleared, statistical" 2; the reasoning pass none |
| MLB | counted once | 66 rows | 68: the model's 57, the reasoning pass's 11 (45 and 46 added) |
| MLB | read on 15 October (not painted before it) | spread -0.27c, 47% beat, n 15; total 0.0c, 0%, n 1 | the model's spread the same; the model's total n 0, no figure; the reasoning pass's total 0.0c, 0%, n 1 |
| MLB | empty bar (days nothing cleared) | before 9 Sep 0 of 2; from 9 Sep 1 of 10 (22 Sep) | the model's the same; the reasoning pass's 1 of 2 (8 Sep) and 6 of 10 (10, 22, 23, 24, 25, 27 Sep) |
| NFL | window line | 10 | the model's 10; the reasoning pass's 0 |
| NFL | awaiting a close | 2 | the model's 1 (78); the reasoning pass's 1 (65) |
| NFL | withdrawn | 4 (62, 63, 64, 66) | "Withdrawn, statistical" 4 |
| NFL | point spread line | 10 of 50 · 1 with no later read; +0.3c, 40% on 15 October | "point spread, statistical", the same |
| NFL | empty bar | from 9 Sep 5 of 6 (9, 23, 25, 27, 28 Sep) | the model's 4 of 5 (9, 23, 27, 28 Sep); the reasoning pass's 2 of 3 (23, 25 Sep) |
| NCAAF | window line; awaiting | 8; 1 | the model's 8 and 1; the reasoning pass's 0 and 0 |
| NCAAF | point spread line | 8 of 50; +0.12c, 25% on 15 October | "point spread, statistical", the same |
| NCAAF | empty bar | from 9 Sep 1 of 4 (28 Sep) | the model's 1 of 4 (28 Sep); the reasoning pass's 4 of 4 (25-28 Sep) |
| NBA, UFC | window line | 0 | two lines, 0 each |
| every sport | kill criterion | stops nothing (before 15 October, and read then) | the same, per forecaster |

Nothing else the closing line, the kill criterion, "Would not have
cleared" or the empty-bar tool states moved. No count of any other record
reads recommendations.

### PROVED *(each new planting run by this tree's `plant.py` against a `git archive` of c57354c in `scratchpad/q17/step2/head/`, and against this tree; `prove/`)*

- **`plant_a_recommendation_count_pooling_two_forecasters`** (thirty of each
  forecaster's MLB totals, every close -1.0c, read on 15 October): ESCAPES
  on c57354c -- one total line of 60, a window line of 60, the payload's
  totals, and the kill stopping the market for both. Here each line counts
  its own 30, nothing is stopped; a door that forgets whose (each line
  counting both forecasters' sixty, the kill stopping both) is refused
  naming the reasoning pass's rows in the model's line, and a total over
  both is refused.
- **`plant_a_same_side_pair_across_two_forecasters_counted_once`** (the two
  forecasters a minute apart on one side of one MLB spread question): ESCAPES
  on c57354c -- the reasoning pass's pick a repeat in one pooled line. Here
  two bets, each in its own line; question 12's rule put back is refused,
  naming the reasoning pass's row.
- **`plant_recs_45_and_46_counted_zero`**: question 22's reversal of
  `plant_both_sides_of_one_total_counted` (renamed for what it now plants;
  its world kept). ESCAPES on c57354c, which counts the total zero under the
  both-sides label. Here each counts once in its own total; question 12's
  rule put back is refused, naming 45's shape in the model's line and 46's
  in the reasoning pass's.
- **Changed with the ruling, each said in its text**: `plant_a_same_side_pair_counted_twice`
  (reads the model's line; the rule removed with the forecaster kept);
  `plant_a_withdrawn_recommendation_in_the_closing_line`,
  `plant_a_closing_line_verdict_before_its_first_clean_read` and
  `plant_a_close_from_before_the_window_counted` read a forecaster's block
  and a stop keyed by market and forecaster; three stand-ins for
  `coverage.priceable` take the forecaster. `tests/test_counted_once.py`
  rewritten: its two-forecaster same-side pair (`test_first_is_by_stamp_then_number...`)
  counted once is two bets now; 45/46's shape counts once each; the
  fixture's pairs are one question (same subject and rung, a pass each).
  Test doubles given forecasts of their own game (`test_recommend._recorded`,
  whose rows shared one forecast on another game), and the closing-line
  tests in `test_closing_line_window.py`, `test_priced.py`,
  `test_recommend.py` and `test_voids.py` read a forecaster's block.
- **The harness**: 344 of 344 caught.

### THE PROVER *(`prove/`; each got past the guards as first built, and is closed)*

- **A door counting a pair's LATER row** keeps every count -- one row of
  each pair counted, one set aside -- and moves only the mean ("3.75 where
  the rows the rule counts give 3.0"): the recount compared counts alone.
  It now works out every bucket, the mean, the share, the renderable flag
  and the finding from the rule's own rows (`audit._buckets`), and the
  source scan pins the earlier row in `pairs_with`'s text -- before 15
  October no figure moves with it, and the pin is all that sees it.
- **A sentence stating another count than its figure**, a window line
  saying both forecasters' sum, a line labelled for nobody: the recount
  checked figures, not words. The words and labels are now written again
  from the recount's figures (`language.clv_line`,
  `closing_line_window_line`, `closing_line_label`) and compared.
- **A total over both under a new name** (`recommendations_so_far`) passed a
  list of what totals used to be called: the top level is now an
  allow-list (`audit.CLOSING_LINE_KEYS`).
- **`bet.same(...) OR <game and market>`** carried the key's text and paired
  across forecasters and rungs: the scan now wants the key as the rule's
  first term and no OR beside it.
- **A close written between the line and its recount made an honest page
  refuse itself** ("reports 1 ... holds 2", a 500) -- as it could since
  ruling 1's recount (2026-09-24) and question 12's (2026-09-27): the two
  recounts ran in `views.scorecard`, after the whole page was read. They
  run in `calibration.scorecard` now, in one instant with the line and the
  kill read of it (`db.one_instant`), and a check building its own report
  builds and recounts in one instant too;
  `test_a_close_written_between_the_line_and_its_recount_is_no_fault`
  failed before and passes after.
- Tried and refused as built: the rule removed (every repeat counted), the
  door without the forecaster (each line both), question 12's key restored
  (a cross-forecaster pick set aside), a key without the rung (a two-rung
  pick set aside), a report with a pooled `n`, a market line naming nobody,
  two sides of one question (named as needing a ruling), a forecaster that
  is not one of the two (`PooledCount` in every door and in `priceable`).

### RENDERED *(the browser suite's own world -- `seed_league` and `_build_world` -- on a scratch file with NFL recommendations added, served by c57354c and by this tree with the suite's test token; never the live app; `scratchpad/q17/step2/render.py`, `render/`)*

Read at 1100px and 390px, today and with the render process's clock set to
15 October. Released: "Since the repair ... 57 recommendations", one
"point spread" line (54, 1 repeat), one "total" line (3), "Withdrawn",
"Both sides, no position" (2) and "Would not have cleared". This tree:
"Since the repair, statistical" (55 from the model) and "..., reasoning
pass" (4), "point spread, statistical" (54, 1 repeat of "this forecaster's
earlier recommendation on the same question"), "total, statistical" (1),
"total, reasoning pass" (4), "Withdrawn, statistical", "Would not have
cleared, statistical", and no both-sides row; on 15 October the stop reads
"point spread, statistical: stopped after 54 recommendations ..." and the
finding sits under the model's spread line. The counts agree with each
other (54 + 1 = 55); every label names whose line it is; no horizontal page
scroll and no console error at either width, on either tree. (The screenshot
lets the sticky header scroll away; the panel's heading still carries the
priced blend's version, "b1" -- question 19, fixed in the board.)

### READINGS TAKEN *(each reversible in one line)*

- **The withdrawn line is split too**: it counts recommendations, and
  question 22 splits "recommendation counts". Reversal: `withdrawn()`
  without the forecaster and one pooled line beside the closing line.
- **Both forecasters' window lines are drawn on every sport's page**, a
  forecaster with none saying 0 (ruling 8's "said on every sport's Record
  page"). Reversal: draw a block's window line only when it has
  recommendations.
- **The kill criterion stops one forecaster's picks** in a market, as
  "reads each forecaster's line" reads.
- **The closing line is split per market and forecaster, not per UFC
  card** (question 22 says forecaster; no UFC recommendation exists).
- **Two sides of one distinct bet** would each count (the rule pairs a
  side with itself) and the recount refuses the page, naming them, as
  needing the operator's ruling; none exists and item 5 cannot write one.
- **The recounts moved into `calibration.scorecard`** so the line, the kill
  and both recounts share one instant; `views.scorecard` no longer calls
  them. Reversal: call them in `views.scorecard` again (and take the race
  back).

### OPEN *(found by this step)*

- **A UFC closing line would pool cards.** Every other count splits per
  card for UFC (question 14); the closing line splits per forecaster only.
  No UFC recommendation has been written. For the re-read.
- **The kill criterion's stop sentence names no forecaster** ("stopped
  after 54 recommendations ..."); its label does ("point spread,
  statistical"). A sentence, not a count.
- **A door choosing another pass of a question** keeps every count; the
  earlier-row pin in the source is what holds it before 15 October, and the
  recount's mean after.

## A prop's question is named by its subject -- fixed 2026-09-29 *(operator question 17's key; the defect its numbers step found, scratchpad `q17/numbers/moves.md` section E)*

"Morning and final pass of one question count once" (question 17). Step 1
put the prop type in the key beside the subject, `IS`-compared (READINGS
TAKEN of that step: "The prop type is a column of the key ... Reversal:
drop `"prop_type"` from `bet.KEY` and `audit.RULED_DISTINCT_BET`"). The
numbers step found it split ten NFL week-one questions in two:
`predict:nfl` wrote them at 05:55Z on 29 August under fs1 with no prop type
(the subject names it) and asked the same player, prop and rung again at
07:34Z under fs2 with the type set. The released standing rule counted each
once, the later row standing; the key made both stand, and 14 NFL figures
moved that no ruling names. Eight of the ten are settled (9/68, 18/76,
23/91, 24/92, 27/95, 29/102, 33/66, 41/104; 29's and 41's questions were
asked a third time by the final pass, 613 and 614, which stand); the other
two (20/78/602, 35/88) are withdrawn and count nowhere. This takes the
reversal step 1 named; nothing else changes. **A MEASUREMENT RULE, NOT AN
EDIT**: no row, table, column or schema object changes.

### MEASURED FIRST *(2026-09-29 ~00:10Z, read-only through `db.read_the_live_record`; scratchpad `q17fix/subjects.py` and `ten.py`, their `.txt`)*

- 3152 predictions, 284 of them props (NFL 124, 32 with no prop type; MLB
  160); no row of another market carries a prop type, and none carries ''.
- Every one of the 252 typed props' subjects ends with its prop type; each
  of the 32 untyped ones names a prop type as its last word
  (passing_yards 15, receiving_yards 11, rushing_yards 6).
- No game holds one subject under two prop types (0 groups), so the
  subject tells every prop question apart.
- The key without the prop type joins exactly ten groups, each one question
  with its untyped row: the eight pairs above and the two withdrawn. Distinct
  bets over every row: NFL 229 to 219, every other sport unchanged.

### THE FIX *(2026-09-29)*

- `bet.KEY` and `audit.RULED_DISTINCT_BET` are the forecaster, the game,
  `market_type`, the subject and the rung asked: the question is named by
  its subject, as `calibration.resolved` has said since ruling R4
  (2026-09-02, the same two runs: "keying on it split ten questions that
  are plainly the same one").
- Every door still keys through `bet`: the standing clause by `bet.same`,
  the at-the-line window by `bet.columns`, the priced, drift, outlook and
  coverage doors and the recounts by `bet.columns` and `bet.of`, the
  closing line's pairs by `bet.same`. Two doors named a row's prop type
  from the key's columns and now select it beside them: `drift.standing_pairs`
  (each pair's `prop_type`) and `recount.forecasts` (`recount.priced` names
  a row's market by it). `calibration.AtTheLineResolved` no longer carries a
  prop type (nothing read it). Every count of one prop type filters by it
  in its WHERE (`p.prop_type = ?`; drift's and the recount's
  `IFNULL(p.prop_type, '') = ?` for a market that is not a prop), untouched.
- The key's text: `gridiron.bet`, the standing clause's, `AtTheLineResolved`'s,
  `audit._closing_line_rows`' and `market.recommend`'s descriptions of it,
  and CLAUDE.md's ONE DISTINCT BET and COUNTED ONCE rows.

### PROVED

- `test_bet.py::test_a_prop_asked_without_its_type_and_again_with_it_is_one_question`:
  a prop asked early with no prop type, again with one, and a second such
  question with a final pass after -- one distinct bet each and one
  standing row, the latest before the start, for the clause, the recount
  and `calibration.resolved` over every market; a count of one prop type as
  before; another stat of the same player another question. On 1949730
  (`git archive`) it fails, and its behaviour alone fails too (the clause
  keeps ids [1, 2, 3, 4, 6] against [2, 3, 6]). `test_the_sql_and_the_python_forms_are_one_key`
  now holds a prop with no type and one with it as one bet;
  `test_the_key_is_the_forecaster_and_the_question_with_its_rung` the five
  columns.
- `plant.py::plant_a_distinct_bet_keyed_by_hand`, a new form: the one
  function's key split by the prop type (the key of 2026-09-28) must be
  refused by the source scan, and the shipped key must keep the shape as
  one standing row. On 1949730 it ESCAPES ("the shipped key keeps 2
  standing rows of one prop question asked with no prop type and again
  with one; the one function's key split by the prop type, a column the
  early rows lack (2 standing rows of one question)"); here it is CAUGHT.
- ONE VERIFIED COPY of the record (`rebuild.verified_backup`, read between
  2026-09-29T00:17:46Z and 00:18:32Z; deleted), every figure the numbers
  step built (its `measure.py`: the Record page whole, the learning panel,
  factors, tier tables, over time, calendar, digest, slates, history, the
  closing line and kill on 15 October, the recommendation doors, the empty
  bar) by the released tree f0a4418, Q17's 1949730 and this fix, at one
  held instant: **193 values move from 1949730 to the fix, all NFL, every
  one back to its released value** -- the factor table's N, effects, Brier
  figures, shares and words (76, "scored over 162" back to 154), the tier
  tables' "settled in the last 14 days" (17: 192 back to 184) and the 100
  pick cards' worst-band footnote ("right 69.7% ... across 33" back to
  "67.7% ... across 31") -- and **nothing else moves**: the 1,891 values
  questions 17, 21 and 22 moved against the released tree are as they were.
  The standing rows: the fix keeps exactly the released tree's, every
  sport, with and without the factor set (NFL 203; 1949730 kept 211, the
  eight untyped rows).
- The gate, dry: the step-2 rows this touches (the source scan, every
  record's pooled-count guard, the closing line's recounts, the closures,
  orphans, docstrings, one answer per question) pass on the copy with
  `GRIDIRON_VERIFYING` set; `plant.py` whole 344/344 caught;
  `audit.prose_reaching_the_raw_side() == []`; the full suite green (2045 passed, 8 skipped, the same eight as before).

### READING TAKEN *(reversible in one line)*

- The reversal step 1 named. Reversal of it: put `"prop_type"` back in
  `bet.KEY` and `audit.RULED_DISTINCT_BET` after `"market_type"` (and the
  planting's new form out) -- which splits the ten in two again.

## Each correction gate's count, per forecaster and bet; the fits fitted below their gate -- built 2026-09-29 *(operator question 16, ruled (B) 2026-09-27, with question 23, ruled (A) 2026-09-28; question 31's default taken 2026-09-29 ~01:50Z, and question 31 ruled (B) and (B) the same day -- the nine, no placeholder; docs/briefs/2026-09-27-rulings-third-set.md, 2026-09-28-rulings.md and 2026-09-29-rulings.md)*

"Q16: (B), after Q17, on its key. Each correction gate's count per
forecaster and distinct bet, planting each." -- "Q23: (A). The page's count
and the fit's own gate both move to the key, for fits from the release
forward. The 63 existing fits stay as written; any that falls short of its
gate on the corrected count is labelled 'fitted below its gate' and can
never be activated." Built as one change, uncommitted, for the orchestrator
to gate and release; the labels are written on the live record by the tool,
with `--live`, after the release.

### MEASURED FIRST *(2026-09-29 ~01:55Z, read-only through `db.read_the_live_record`: `scratchpad/q16/measure.py` -> `measure_0929.txt`, the same as 28 September's `measure.txt`; and `measure4.py` -> `measure4.txt`)*

- **89 correction rows** (1-63 written 31 August to 21 September 22:11Z,
  before Q23 was ruled at 01:50:37Z on 28 September; 64-89 by the weekly
  refit at 13:00:01Z on 28 September). **Every fit's gate** is `MIN_TRAIN`
  = 50 (unchanged since 31 August) over every settled forecast of its
  category (sport, market type, forecaster) resolved before its fitted
  instant, voids left out -- read off the fit's own record: its category,
  its `fitted_utc`, its `n_train`. Recounted, that is exactly `n_train` for
  all 48 fitted rows (voids read as of now or as of the fit: the same).
- **The corrected count** -- the distinct bets on question 17's key among
  those forecasts -- is the same for every fit read as distinct keys or
  through the blind record's standing rule.
- **Fitted, short of fifty on the key (9):**

| Fit | Category | Version | Fitted | Gate | Count used (`n_train`) | Corrected | In force |
|---|---|---|---|---|---|---|---|
| 33 | MLB total, reasoning pass | 1 | 21 Sep 06:29:40Z | 50 | 76 | 48 | no |
| 59 | UFC distance, statistical | 3 | 21 Sep 22:11:39Z | 50 | 56 | 32 | no |
| 61 | UFC moneyline, statistical | 3 | 21 Sep 22:11:39Z | 50 | 56 | 32 | no |
| 63 | UFC rounds, statistical | 3 | 21 Sep 22:11:39Z | 50 | 56 | 32 | no |
| 81 | NFL point spread, statistical | 3 | 28 Sep 13:00:01Z | 50 | 60 | 41 | no |
| 85 | UFC distance, statistical | 4 | 28 Sep 13:00:01Z | 50 | 85 | 49 | no |
| 86 | UFC moneyline, reasoning pass | 4 | 28 Sep 13:00:01Z | 50 | 63 | 49 | no |
| 87 | UFC moneyline, statistical | 4 | 28 Sep 13:00:01Z | 50 | 85 | 49 | no |
| 89 | UFC rounds, statistical | 4 | 28 Sep 13:00:01Z | 50 | 85 | 49 | no |

- **Fitted and clear on the key (39)**, e.g. 71 (MLB moneyline,
  statistical, v8, **the one fit in force**, 364 forecasts, 260 questions),
  67 (NCAAF spread, statistical, 192/185), 74 (MLB spread, 306/202), 76 (MLB
  total, 306/213), 64 and 66 (NCAAF moneyline and spread, reasoning pass,
  60/60 and 58/58). **Placeholders (41)**: `n_train` 0, slope 1, intercept
  0, never fitted, the count only in their words; never labelled.
- **No labelled fit is in force**: of the four ruled, none carries an
  activation; the only fit in force (71) is clear. Nothing stopped for a
  ruling. (Of the nine ruled on 2026-09-29, none carries one either.)
- **The category is not split**: every prop type is one category under
  'prop' and UFC's cards are one, as each fit was fitted; the page says so
  in words ("every prop type together", "every card together"). Splitting
  it would be a model change no ruling names -- not built.

### BUILT *(2026-09-29)*

- **One count** (`correction.settled_rows`, read by `bet.count`): a
  category's settled forecasts before an instant, withdrawn by no void on
  the record (from the prover: whatever its stamp; only a fit's own count,
  `as_it_stood`, leaves out just the voids stamped by its instant), each
  carrying `bet.columns`. Read by the page's
  line, the fit's own gate (`refit_all`, at the fit's instant: fifty settled
  QUESTIONS), a version's forward count (`version_report`) and the learning
  panel's row. The rows a fit is trained on are unchanged
  (`training_rows`, every settled forecast; `n_train` is still that count):
  until this release the gate WAS `len(training_rows(...))`, one query;
  now the gate and the training are two reads, because the ruling moves the
  gate and not what a correction is fitted on (LAW 2: no model change beyond
  what is named).
- **The guard** (`calibration.assert_no_pooled_correction_counts`) inside
  `views.corrections_report` and `views.learning` -- both API routes answer
  500 on a pooled or duplicated count -- and the gate row
  `audit.check_the_correction_counts_are_never_pooled` building both for
  every sport on the record's copy (`tools/verify.py` step 2). The recount
  without the door is `recount.correction`, in the builder's
  `db.one_instant`.
- **The label** (`correction_gate_labels`, append-only, the re-grade's
  shape) and its rules; `calibration_corrections_labelled_never_replaced`;
  the activation door passing over a labelled fit; the selection by rule
  (`correction.below_their_gates`), the writer (`correction.write_labels`)
  and the tool (`tools/label_corrections_below_the_gate.py`). The page names
  a labelled fit beside its gate, with both its counts.
- **The isolation scan reads f-strings** (`audit.FSTRING_PART`), so the
  count door's query -- `bet.columns('p')` in an f-string -- is read for its
  tables and bounds; `CORRECTION_TABLES` gains `correction_gate_labels`.
- `tests/test_no_replacing_write.py`: the schema's append-only tables are
  23 (the labels), where the test pinned 22.

### EVERY CORRECTION COUNT THE PAGE STATES, before and after *(one verified copy of the record, `rebuild.verified_backup`, read 2026-09-29T02:03:54Z-02:04:38Z; before: the released tree, HEAD 97febf7 = master's code, on the copy; after: this tree on the same copy after `db.init` and the tool's `--write`; `scratchpad/q16/page_counts.py`, `before.json`, `after.json`, `side_by_side.txt`)*

"What else is still counting" -- the gate rows (`A correction for ...`):

| Sport | Category (after's name) | Before | After |
|---|---|---|---|
| NFL | moneyline, reasoning pass (was "moneyline, LLM") | 29 of 50 settled | 15 of 50 settled questions |
| NFL | moneyline, statistical | 31 of 50 settled | 31 of 50 settled questions |
| NFL | player props, every prop type together, statistical (was "prop, statistical") | 95 settled, cleared | 65 settled questions, cleared |
| NFL | point spread, reasoning pass | 23 of 50 settled | 12 of 50 settled questions |
| NFL | point spread, statistical | **60 settled, cleared** | **41 of 50 settled questions**, 9 more |
| NFL | total, reasoning pass | 32 of 50 settled | 16 of 50 settled questions |
| NFL | total, statistical | 32 of 50 settled | 17 of 50 settled questions |
| MLB | moneyline, reasoning pass | 202 settled | 148 settled questions |
| MLB | moneyline, statistical | 364 settled | 260 settled questions |
| MLB | player props, every prop type together, reasoning pass | 8 of 50 settled | 8 of 50 settled questions |
| MLB | player props, every prop type together, statistical | 99 settled | 80 settled questions |
| MLB | point spread, statistical | 306 settled | 202 settled questions |
| MLB | total, reasoning pass | 187 settled | 141 settled questions, and "Version 1, fitted on Monday 21 September, was fitted below its gate: its 76 settled forecasts are 48 questions, under the 50 it needs, so it can never be in force." |
| MLB | total, statistical | 306 settled | 213 settled questions |
| NBA | point spread, statistical | 0 of 50 settled | 0 of 50 settled questions |
| NCAAF | moneyline, reasoning pass | 60 settled | 60 settled questions |
| NCAAF | moneyline, statistical | 197 settled | 142 settled questions |
| NCAAF | point spread, reasoning pass | 58 settled | 58 settled questions |
| NCAAF | point spread, statistical | 192 settled | 185 settled questions |
| NCAAF | total, reasoning pass | 67 settled | 67 settled questions |
| NCAAF | total, statistical | 198 settled | 144 settled questions |
| UFC | distance, every card together, reasoning pass | 14 of 50 settled | 14 of 50 settled questions |
| UFC | distance, every card together, statistical | **85 settled, cleared** | **49 of 50 settled questions**, 1 more; and version 3 named "fitted below its gate" (56 forecasts, 32 questions) |
| UFC | moneyline, every card together, reasoning pass | **63 settled, cleared** | **49 of 50 settled questions**, 1 more |
| UFC | moneyline, every card together, statistical | **85 settled, cleared** | **49 of 50 settled questions**, 1 more; version 3 named |
| UFC | rounds, every card together, reasoning pass | 14 of 50 settled | 14 of 50 settled questions |
| UFC | rounds, every card together, statistical | **85 settled, cleared** | **49 of 50 settled questions**, 1 more; version 3 named |

"What the record has taught it" -- the learning panel's correction row
(the statistical model's), its count and its words:

| Sport | Row | Before | After |
|---|---|---|---|
| NFL | point spread | 41 -- "not yet fitted: 41 of 50 settled rows" | 41 -- "41 of 50 settled questions; fitted on Monday 28 September on 60 settled forecasts, and NOT in force" (fit 81 stands; it was "not yet fitted" beside a fit) |
| NFL | moneyline, total | 31, 17 -- "not yet fitted ... settled rows" | 31, 17 -- the same in "settled questions" |
| NFL | passing yards, receiving yards, rushing yards, receptions, passing touchdowns | 10, 10, 9, 9, 8 -- each its own type's standing forecasts, "not yet fitted" | 65 each -- "65 settled questions, every prop type together; fitted on Monday 28 September on 95 settled forecasts, and NOT in force" |
| MLB | moneyline | 260 -- "in force since Monday 28 September, fitted on 260 settled rows" (fit 71 was fitted on 364) | 260 -- "260 settled questions; in force since Monday 28 September, fitted on 364 settled forecasts" |
| MLB | point spread, total | 202, 213 -- "fitted on 202 [213] settled rows" | 202, 213 -- "... fitted on Monday 28 September on 306 settled forecasts, and NOT in force" |
| MLB | hits, total bases, home runs, batter strikeouts, pitcher strikeouts | 31, 0, 31, 10, 8 -- "not yet fitted" | 80 each -- "80 settled questions, every prop type together; fitted on Monday 28 September on 99 settled forecasts, and NOT in force" |
| NBA | seven rows | 0 each | 0 each; the four prop rows say "every prop type together" |
| NCAAF | point spread, moneyline, total | 185, 142, 144 -- "fitted on 185 [142, 144] settled rows" | 185, 142, 144 -- "... fitted on Monday 28 September on 192 [197, 198] settled forecasts, and NOT in force" |
| UFC | moneyline, rounds, distance | 49 each -- "not yet fitted: 49 of 50 settled rows" (fits 87, 89, 85 stand) | 49 each -- "49 of 50 settled questions, every card together; fitted on Monday 28 September on 85 settled forecasts, and NOT in force" |

The tier table's corrections note (every sport, every category): "A
correction is fitted at 50 settled predictions" -> "... at 50 settled
questions"; MLB moneyline, statistical (fit 71 in force): "(version 8,
fitted 2026-09-28, 364 settled)" -> "(version 8, fitted 2026-09-28 on 364
settled forecasts)". The learning payload's unpainted `n` (a sum of its
rows' counts: NFL 135, MLB 755, NCAAF 471, UFC 147) is its row count (8, 8,
3, 3; NBA 7). No other figure the page states reads a correction count.

### THE REHEARSAL *(a copy of the verified copy, through the backup door; never the record; `scratchpad/q16/rehearse_init.py` -> `rehearse_init.txt`, `rehearse_tool.txt`)*

- `db.init` of this tree: exactly the eight new objects (the table
  `correction_gate_labels`, its six rules, and
  `calibration_corrections_labelled_never_replaced`), each with a fresh
  build's text, in a fresh build's order; nothing gone or changed; **no
  table's row count or column checksum moved**; **0 differences** from a
  fresh build of this tree with an EMPTY register; a second open changes
  nothing.
- The tool, as the default built it (question 31's ruling moved it the same
  day: QUESTION 31, RULED, below): the dry run selects nine (33, 59, 61, 63,
  81, 85, 86, 87, 89),
  verifies the ruled four among the 63 written before 01:50:37Z on 28
  September, lists 81, 85, 86, 87 and 89 as waiting for question 31, and
  writes nothing; `--write` writes 4 in one transaction; again, 0 written
  and 4 already labelled; `--live` on the copy refused; the live record
  without `--live` refused before it is opened; a record without the table
  (the verified copy, never migrated) refused by name.

### PROVED

- Each planting run by this tree's `plant.py` against a `git archive` of
  HEAD 97febf7 (`scratchpad/q16/head/`) and against this tree
  (`run_q16_plantings.py`): all six ESCAPE on HEAD -- the page's line "68
  settled" for 38 questions; the statistical moneyline fitted on 60
  forecasts that are 30 questions; a forward count of 30 for 20 questions;
  prop rows stating 30 and 25 beside a category of 55; a fit short of its
  gate written in force in its own place and served by the door; no label
  at all -- and all six are CAUGHT on this tree.
- `tests/test_correction_gate.py`: 24 tests; 23 fail on HEAD's package (the
  24th reads only the tool's own `check`).
- `plant.py` whole: 350/350 caught (344 and these six). The full suite, a
  dummy token, TMP/TEMP at their defaults: 2069 passed, 8 skipped (the
  same eight), none failed, first run. On the rehearsed copy, the whole
  Record page payload and the learning panel built for every sport with
  their guards inside, and the new gate row passed (`whole_page.py`).

### RENDERED *(the browser suite's own world -- `seed_league` and `_build_world` -- on a scratch file, with 28 NFL moneyline questions answered twice and a fit of their 56 forecasts labelled through the tool's door; served by this tree with the suite's test token; never the live app; `scratchpad/q16/render_q16.py`, `render_q16_rows.py`, `render/`)*

- 1100 and 390 px, both panels read: "A correction for moneyline,
  statistical -- 35 of 50 settled questions · 15 more settled questions --
  Version 1, fitted on Wednesday 1 January, was fitted below its gate: its
  56 settled forecasts are 28 questions, under the 50 it needs, so it can
  never be in force."; "A correction for player props, every prop type
  together, statistical"; each prop row of the learning panel "11 of 50
  settled questions, every prop type together". No horizontal scroll, no
  console error, the muted line legible, nothing clipped.

### READINGS TAKEN *(each reversible in one line)*

- **The count is the distinct keys among the rows the gate counts**, not
  the standing rule: this module may not name `games`
  (`audit.check_correction_is_isolated`), and the two give the same count
  for all 89 fits. Reversal: none needed unless they part; the recount
  would then be the standing rule's.
- **A void counts from its stamp ONLY for a fit's own count, read as its
  gate read it** (`as_it_stood`: the label's selection, and the label rule
  in the schema); the page, a forward count and the fit being made leave
  out every void on the record, whatever its stamp, as `training_rows`
  does (the prover, 2026-09-29: a void stamped after now left its forecast
  counted everywhere, the recount agreeing). Reversal: `as_it_stood`'s
  clause out of `settled_rows` and `recount.correction`.
- **The training rows are not moved** (`training_rows`, every settled
  forecast). Reversal: fit on `settled_rows`' standing rows -- a model
  change, the operator's.
- **No label on a fit carrying an activation** (schema rule, writer and
  tool): the ruling says a labelled fit can never be activated, not that one
  in force is taken out of force. None is. Reversal: drop
  `correction_gate_label_never_on_a_fit_in_force`.
- ~~**The population is read by instant**: the fits written before 01:50:37Z
  on 28 September, checked to be 63; the ruled set is the four every reading
  of question 31 covers. Reversal: a ruling on question 31 changes `RULED`
  and the population constant, and the tool is run again.~~ RULED
  2026-09-29 (question 31 (i)(B) and (ii)(B)): the population is "every
  fitted row written before Q16's release", read as every fit on the record
  with no instant (a fit from the release on is gated on the key and never
  selected); `RULED` is the nine, `LEFT_BY_RULING` empty; the instant, the
  size check and `population()` are gone (QUESTION 31, RULED, below).
- **The door passes over a labelled fit** (the newest activation not
  labelled is in force) rather than raising. Reversal: raise by name in
  `active_correction`.
- **"Reasoning pass"** names the second forecaster on the correction gate
  rows, as on the drift rows beside them, where they said "LLM"; and
  **UFC's rows say "every card together"**, as the prop rows say "every prop
  type together". Reversal: `language.correction_category_label`.
- **The learning payload's `n` is its row count**, not a sum. Reversal: one
  line in `views.learning`.

### OPEN *(found by this step; by the queue rule, for the re-read unless it breaks LAW 1 or LAW 3 or makes a gate count false)*

- ~~**Question 31** stays the operator's: 81, 85, 86, 87 and 89 are fitted
  below their gate on the key and unlabelled; the page states their
  categories' counts on the key (NFL point spread, statistical, 41 of 50;
  UFC 49 of 50) beside versions fitted on the forecasts. The placeholders
  are never labelled.~~ RULED 2026-09-29, (i)(B) and (ii)(B): the five are
  labelled with the four, and no placeholder (QUESTION 31, RULED, below).
- ~~**The label table's own replacing insert whose number reads twice**~~
  CLOSED by the prover (2026-09-29, below): the table is WITHOUT ROWID, so
  the number is worked out once. `recommendation_regrades` keeps the hole
  (its label keyed by the rowid): a one-row insert whose number reads as
  one recommendation to its rules and another to the row stores a re-grade
  its rules never checked -- for the re-read (no code writes one; Q15's
  scan).
- **The learning panel's heading prints the refit's date as a key**
  ("What the record has taught it 2026-09-28": `renderLearning` slices
  `last_refit`) -- PLAIN WORDS, found in the render, not new.
- **The forward Brier figures average forecasts** (a question's passes
  each) while `n` counts questions; `forecasts` stands beside them. Not
  painted; no forecast carries a correction version yet.

### THE PROVER *(2026-09-29, 02:50-03:45Z; memory worlds, copies of this tree, and one fresh verified copy of the record deleted after use; `scratchpad/q16/prove/`)*

WHAT GOT THROUGH THE CHANGE AS FIRST BUILT, each measured, each fixed here
with a test that fails on the change as first built and a planting form
(`attack1.py`; `neutralise.py` -> `neutralise.txt`, `neutralise_tests.txt`):

- **A false label on the fit in force, in one statement.** The label table
  was keyed by its rowid (`correction_id INTEGER PRIMARY KEY`, as
  `recommendation_regrades` is), and SQLite works a rowid out twice for one
  row of values -- once for the rules before the row, once for the row
  (question 13's finding; measured on 3.49.1: a function of the
  connection's own was asked twice, and an ordinary column once). A label
  every rule read as a short fit's (56 forecasts, 28 questions) landed on
  the fit in force, and `active_correction` then passed over it: the only
  correction in force switched off, and on the record fit 71 was reachable
  the same way (rules shown 81, the row given 71). And under OR REPLACE, a
  number read as an unlabelled twin with the same counts wrote over a
  stored label's stamp. FIXED: `correction_gate_labels` is WITHOUT ROWID --
  the key is an ordinary column, worked out once, a text or real number
  arrives as the integer it stores, and there is no rowid to name -- so
  every rule reads the row that lands. On the verified copy: the number
  asked once, the label landed on 81, the door still served 71 (rolled
  back). `test_a_labels_number_is_read_once_so_the_rules_read_the_row_that_lands`;
  the label planting's two new forms.
- **A label stamped in 2099, or '2026-06-02 by hand'** (which sorts after
  the fit), was stored. FIXED: `correction_gate_label_comes_after_its_fit`
  also refuses a stamp after now or outside `YYYY-MM-DDTHH:MM:SSZ`.
  `test_a_label_is_stamped_when_it_is_written_in_the_one_format`; two forms.
- **A withdrawn forecast counted.** The door read only voids stamped at or
  before its instant, so a question withdrawn by a void stamped after now
  (by hand, or a clock) stayed on the page's line, in the recount beside it
  -- which read it the same way, so the guard saw nothing -- in a forward
  count and in the fit's own gate, while `training_rows` left it out:
  forty-nine totals and a withdrawn fiftieth were fitted. FIXED: the door
  and `recount.correction` leave out every void on the record; only a fit's
  own count read as its gate read it (`as_it_stood`, the label's selection)
  keeps to the voids stamped by its instant. The record holds no void
  stamped after now or outside the format (the verified copy, 03:10Z), so
  no count the page states moves.
  `test_a_forecast_withdrawn_by_a_void_stamped_after_now_is_never_counted`,
  `test_a_row_counts_if_settled_before_the_instant_and_never_if_withdrawn`;
  a form in the page's planting and one in the fit's.
- **An honest learning panel answering 500.** Each row read its count in an
  instant of its own, and the guard refuses one category stated two ways,
  so a prop settled between two prop rows made the panel say 10 on one
  row and 11 on the next (the test's world).
  FIXED: one `db.one_instant` for the whole panel (question 22's precedent).
  `test_a_prop_settled_between_two_prop_rows_is_no_fault` (a test, not a
  planting: nothing is let through, an honest page is refused).

NOT SEEN, AND WHY NOT BUILT (each is outside what the ruling names; for the
re-read):

- **A raw insert of a NEW version, in force, carrying a labelled fit's
  numbers** (or any numbers) is served by the door; so is a fit written by
  `record_fit` with a model its category's questions never gated. The
  labelled fit itself can never be put in force, and `refit_all` -- the one
  writer -- gates on the key; the schema has held no gate for a correction
  since 31 August. A rule refusing a fitted row whose category is short of
  fifty questions at its instant would close both, and every test world
  that writes a synthetic fit (test_correction, test_recommend, three
  plantings) would be rebuilt: the operator's, not this step's.
- **A label's reason is free words** (ten characters or more), as the
  re-grade's is; the page composes its line from the label's numbers, never
  its reason.
- **A void stamped back before a fit that cleared on the key** makes the
  rule select that fit; the schema refuses its label (the count used is no
  longer the record's) and so does the tool, by name.

PROVED:

- **HEAD escapes** (`git archive` of 97febf7 with this tree's `plant.py`,
  `escapes_on_head.txt`): all six ESCAPE. This tree: all six CAUGHT.
- **Each guard part neutralised in a copy** (`neutralise.txt`): the
  builders' guard off -- the page's, the forward count's and the learning
  row's plantings escape; the gate row off -- the page's planting escapes
  at the gate; the guard's recount comparison off -- the door keyed without
  the rung escapes; `refit_all`'s gate on the forecasts -- the fit's
  planting escapes; the forward `n` on the forecasts -- its planting
  escapes; `calibration_corrections_labelled_never_replaced` off -- the
  replacing insert by number escapes (by category and version the foreign
  key still refuses it); the door's label filter off -- the door serves the
  labelled fit; each of the label's six rules off, and WITHOUT ROWID out --
  the label planting escapes on exactly that rule's forms; the voids as
  first built -- the page's and the fit's plantings escape. BELT AND
  BRACES, said as found: the guard's forecasters-counted check off lets
  nothing through (the recount sees a door without the forecaster); the
  learning row put back on one prop type is refused inside its builder
  (the planting errors rather than escapes); `write_labels`' own check off
  errors on the first stray fit, and the schema refuses the label anyway.
- **The schema, again, on a fresh verified copy** (`rebuild.verified_backup`
  03:10:11-03:10:56Z; `rehearse.py` -> `rehearse.txt`): 242 -> 250 objects,
  exactly the eight, each a fresh build's text, in a fresh build's order;
  nothing gone or changed; no table's count or checksum moved; 0
  differences from a fresh build, EMPTY register; a second open changes
  nothing. The tool: 9 selected, the four verified among the 63, 81, 85,
  86, 87, 89 waiting; `--write` 4, again 0 and 4 already; the refusals.
  Every sport's page, panel and scorecard built with their guards; the new
  gate row passed. The next weekly refit, run on the copy: 26 categories,
  13 past fifty questions, none selected by the rule (NFL point spread and
  UFC's statistical categories, 41 and 49, recorded unfitted). The page's
  counts on the copy equal the build's `after.json` (0 differences). The
  copies were deleted.
- **Step 2's touched rows** on a copy migrated by this tree
  (`step2_rows.py` -> `step2_rows.txt`): 22 of 22 passed.
  `prose_reaching_the_raw_side()` is `[]`.
- **`plant.py` whole: 350/350 caught**, rc 0 (the six carry the prover's
  new forms). **The full suite**, a dummy token, TMP/TEMP at their defaults:
  2073 passed, 8 skipped (the same eight), none failed, first run;
  `tests/test_correction_gate.py` has 28 tests.
- **Rendered again** from the test world (`render_q16.py`,
  `render_q16_rows.py` -> `prove/render/`), 1100 and 390 px, read: the
  labelled gate row and the learning rows word for word as the build's, no
  horizontal scroll, no console error.

### QUESTION 31, RULED *(2026-09-29; docs/briefs/2026-09-29-rulings.md; `scratchpad/q31/`)*

"Q31 (i): (B). Label every fitted row written before Q16's release that
falls short on the key: 33, 59, 61, 63, 81, 85, 86, 87, 89." -- "Q31 (ii):
(B). No labels on placeholders; they were never fitted." The brief's
reading: the tool's ruled set is the nine, "written before Q16's release" is
the population, a fit the weekly recalibration writes before the release that
falls short on the key is selected by the same rule, and if the selection at
the live run is not exactly the nine the tool refuses and reports the
difference.

- **The tool** (`tools/label_corrections_below_the_gate.py`): `RULED` = 33,
  59, 61, 63, 81, 85, 86, 87, 89; `LEFT_BY_RULING` = (). The population is
  every fit on the record, with no instant: a fit written from the release
  on is gated on the key at its own instant (`refit_all`), so it cannot be
  short as of it and the rule never selects it, and the rule's selection
  over every fit IS the pre-release population. `RULED_AMONG_THE_FITS_WRITTEN_BEFORE`,
  `RULED_POPULATION_SIZE`, `population()` and the "waiting for question 31"
  line are gone; `POPULATION` holds the ruling's words for the output. It
  writes only when the selection is exactly the nine, and otherwise refuses,
  naming each fit selected and not ruled on, or ruled on and not selected
  (a selection the weekly refit of 5 October would widen, if it landed
  before the release, is refused until ruled). The placeholders: never
  selected, and the schema refuses a label on one, as built. The words
  moved with it in `correction.py` (module and `below_their_gates`
  docstrings), CLAUDE.md's Q16 row and a schema comment ("none of the nine
  ruled is in force"; a comment between statements, no object's text).
- **Tests** (`tests/test_correction_gate.py`, 29): the tool's test asserts
  the nine, `LEFT_BY_RULING` empty, the ruling's words, the instant, the
  size and `population()` gone; its four refusals kept and three more
  (86 unselected, 87 in force, 89's count not given back); and a tenth fit,
  written 5 October and short on the key, refused naming it.
  `test_the_nine_are_what_the_rule_selects_on_the_rehearsal_shape` builds
  the record's 89 rows in its order, each written as its refits wrote it
  (fitted on the forecasts at fifty settled, a placeholder below): the rule
  selects exactly the nine, in their categories, versions and counts (76/48;
  56/32 x3; 60/41; 85/49 x3; 63/49), four before question 23 was ruled; no
  placeholder, one short on any count among them (15 questions); fit 71 in
  force; the tool says it would write 9, writes 9, then 0 and 9 already; and
  a refit from the release on, gated on the key, adds nothing the rule
  selects. Both tool tests FAIL on HEAD's tool (RULED is the four;
  `scratchpad/q31/old/`), and pass on this one.
- **Run**: `pytest tests/test_correction_gate.py tests/test_guards.py`, a
  dummy token, TMP at its default: 145 passed, rc 0. The schema, rebuild,
  replacing-write, one-way-in, correction, at-the-line and audit-surface
  modules (a schema comment moved): 300 passed. `plant.py` whole: 350/350
  caught, rc 0.
- **On one verified copy of the live record** (`rebuild.verified_backup`,
  read 04:10:23Z-04:11:21Z: integrity ok, 61 tables proved equal, none
  mismatched; opened under this tree's schema by `db.init` -- the label
  table added; 89 correction rows, 48 fitted, 1 in force: 71): the dry run
  lists the nine (33 mlb total, llm, v1, 76/48; 59, 61, 63 ufc distance,
  moneyline, rounds, statistical, v3, 56/32; 81 nfl spread, statistical,
  v3, 60/41; 85, 87, 89 ufc, statistical, v4, 85/49; 86 ufc moneyline, llm,
  v4, 63/49), verifies them as the ruling's set and says "--write would
  label 9"; `--write` wrote 9 (0 already); again, 0 written, 9 already; the
  dry run after, "--write would label 0"; `--live` on the copy refused. Read
  back: nine labels, gate 50, each with its fit's own counts; fit 71 still
  served; each sport's correction lines built with their guard and name the
  nine ("Version 4, fitted on Monday 28 September, was fitted below its
  gate: its 85 settled forecasts are 49 questions, under the 50 it needs, so
  it can never be in force."). The copy was deleted.
- **After the release**, from the main checkout: the dry run
  `python tools/label_corrections_below_the_gate.py --database var/gridiron.db`
  (the read-only door; refused by name until a scheduled pass or the
  server's start has opened the record under the schema), then
  `python tools/label_corrections_below_the_gate.py --database var/gridiron.db --write --live`
  -- nine written, or a refusal naming the difference.

## A correction is in force only by its own dated row -- built 2026-09-29 *(operator question 32; the second set of rulings of 29 September, docs/briefs/2026-09-29-rulings-second-set.md)*

The ruling: "Q32: corrections activate through the same gate as model fits.
Every correction row is written inactive. Activation is its own dated
append-only row, written only when the holdout bootstrap interval of the Brier
improvement excludes zero, measured on distinct bets by the key, per
forecaster; a tie goes to the uncorrected probability. The recalibration task
never activates anything; fix its docstring to say what it does." And: "Fit
71: withdrawn now by a dated append-only row, reason 'activated under the
pre-Q32 rule: single holdout comparison, pooled rows'. Then run the new gate
on it read-only and report the interval. If it passes, activation is a new
dated row; if not, it stays withdrawn." What was built is CLAUDE.md's row A
CORRECTION IS IN FORCE ONLY BY ITS OWN ROW and the activation section's
paragraph; what follows is the evidence, the readings taken, and what is left.

- **The first step (read-only, the brief's 05:46Z; again on the verified copy
  of 06:27Z):** no forecast and no recommendation carries fit 71 or any
  correction (0 and 0); no MLB moneyline statistical forecast was written at
  or after fit 71's instant (0); the newest MLB forecast is 3088, 27 September
  05:48:42Z. Nothing to label.
- **FIT 71 UNDER THE NEW GATE (the verified copy, after its withdrawal):** its
  category's settled questions before its instant (2026-09-28T13:00:01Z),
  each once on the key: **260** (its 364 settled forecasts); refit on the
  earliest **208**, scored on the latest **52**; Brier raw **0.247471**,
  corrected **0.247620**; improvement **-0.000149**; paired bootstrap 95%
  interval **[-0.015132, +0.016931]** (1000 resamples, seed 20260923). The
  interval touches zero: **a tie -- it does not pass, and it stays
  withdrawn.** Each of the 260 questions stands on the forecast the blind
  record's standing rule keeps (`recount.correction_standing`, 260 of 260).
  Under the rule before, on the same instant, the refit's own point check
  held out 73 FORECASTS and read a gain of 0.005202 (row 71's
  `holdout_brier_raw` 0.250413 -> 0.245211).
- **The rehearsal (scratchpad `q32/rehearse.txt`; one verified copy through
  `rebuild.verified_backup`, 45.8 s, integrity ok, 62 tables proved equal,
  none mismatched; a copy of it opened under this tree):** `db.init` added
  exactly the new table and its fifteen rules (250 -> 266 objects), none gone
  or changed, no table's count or column checksums moved, the new table
  empty; 0 differences from a fresh build of this tree with an EMPTY
  register; the rules of the three correction tables in a fresh build's
  order; a second open changes nothing; fit 71 served by nobody. Then the
  tool, as it will run on the record: the withdrawal's dry run named fit 71
  and the ruled reason and wrote nothing; `--write` wrote it (seq 1,
  `withdrawn`, the reason exactly as ruled); again, "already withdrawn, as
  ruled"; the gate read-only reported the interval above; `--write` exited 1,
  "NOT ACTIVATED, NOTHING WRITTEN ... so it stays withdrawn", twice; `--live`
  on the copy refused. Read back: one row; the door serves nothing for MLB
  moneyline, statistical; the page says "Version 8 has been withdrawn since
  Tuesday 29 September: it was put in force by the weekly refit under the
  rule before 29 September, on one comparison with no interval that counted
  each pass of a question separately; nothing is in force." (no plain-words
  fault); both correction gate checks pass on the copy; 0 forecasts and 0
  recommendations carry a correction. Every copy was deleted.
- **The plantings:** eight new, each ESCAPES on the unfixed tree (db2960f,
  exported with this `plant.py` placed in it) and is CAUGHT here: a
  correction in force with no row of its own (the weekly refit on 500
  questions, and a new row written with `active_from`), one activated on a
  tie, one with no interval or no measurement, a labelled fit or a
  placeholder activated (by the gate and by a scratch row), a scratch
  activation on a live record (and the scratch door on a record), a row
  edited, deleted or replaced (and the correction a row names written over),
  the door reading `active_from` (the in-force door and the latest-row door
  each swapped), and a measurement on pooled rows (a row stating the
  forecasts' counts, and the measurement's door swapped for every
  forecast). The three "CORRECTIONS ACTIVATE ONLY ON THEIR MERITS" plantings
  now ask the gate (a placeholder, a tie, a genuine pass on 500 questions);
  item 3's and question 16's plantings put a correction in force by its own
  row. Scratchpad `q32/plantings_head.txt`, `q32/plantings_fix.txt`.
- **Tests:** `tests/test_correction_activation.py` (16); the correction,
  correction-gate, recommendation and Today tests moved to a correction put
  in force by its own row (a scratch activation in a test world); one test
  used an activation stamped 2099 to stand for "not in force yet" -- a stamp
  ahead of now is refused from this release, and the test says so.
- **The render (scratchpad `q32/render/`, the browser suite's world, 1100 and
  390 px):** the three states read in plain words on the gate list and the
  learning panel, no horizontal scroll, no page error. THE RENDER CAUGHT ONE
  FALSE SENTENCE: "measured on the latest 100 of 500 settled questions, which
  it was not fitted on" -- the version in force WAS fitted on them (it is
  fitted on every settled forecast); only the gate's refit was not. It now
  reads "on the 500 settled questions before it was fitted, one fitted on the
  earliest 400 lowered the Brier score on the latest 100 by ...", and the
  not-in-force words and the Record tab's note say the same thing the same
  way.

**Readings taken (the conservative default each time; one line to reverse):**
1. THE MEASUREMENT'S INSTANT is the correction's own fitted instant -- the
   record the fit saw -- not the moment the tool runs: a correction is
   measured on what it could have been fitted on, and the measurement is the
   same whenever it is made (reverse: `holdout_questions` reads
   `settled_rows` at now; the schema's recount would read now too).
2. WHAT IS SCORED is the correction's method refit on the earliest four
   fifths, as the old check and the model gate's `tools/holdout.py` score a
   refit; the stored fit, fitted on all of them, would be scored in-sample.
3. WHICH ROW OF A BET STANDS: the latest written, withdrawn by no void,
   because the correction may not read `games`; the tool refuses a
   measurement where that is not the blind record's standing row (question
   27 will change the standing pass; the check is where it will show).
4. THE BOOTSTRAP is the model gate's own: 1000 resamples, seed 20260923, the
   same two percentiles (tested equal), per question.
5. A WITHDRAWAL names the correction in force -- the category's latest row's,
   or, before any row, the newest written in force under the old rule (fit
   71) -- so a withdrawal cannot take out of force a correction it does not
   name.
6. ACTIVATION IS A SEPARATE ACT, as for model fits: nothing writes a measured
   row but `activate_measured`, which the tool calls; the weekly refit never
   does (the ruling's "the recalibration task never activates anything").
   So from this release no correction comes into force until someone runs
   the tool on it.
7. The tool exits 1 when `--write` was asked and the gate did not pass --
   nothing written -- as `tools/holdout.py --activate` does on a tie.
8. The ruled withdrawal reason is stored as ruled and said on the page in
   plain words (`language.RULED_WITHDRAWAL_WORDS`: "the pre-Q32 rule" and
   "pooled rows" are the repair's own terms); any other reason is shown as
   written.
9. A PLACEHOLDER is a row whose `n_train` is under the gate of 50, as the
   label's rule reads it.
10. `refit_all` no longer runs the old point check or stores holdout columns
    on new rows: the gate's measurement is the activation's; the columns
    stay on the rows written before, labelled on the payload as the refit's
    own check before 29 September.

**Found on the way, to the re-read (the queue rule: none breaks LAW 1 or LAW 3
or makes a gate count false):**
- **`correction.fit_platt` can diverge on a narrow claim range.** Measured
  2026-09-29 on synthetic rows: claims 0.80-0.95 with coin-flip outcomes,
  240 rows -> slope 80.7, intercept 2.2e8 (a claim of 85% corrected to
  100%); Newton's step has no damping. On the live record the refit of fit
  71's category converged (a corrected Brier of 0.247620 beside 0.247471
  raw). Under the new gate a divergent refit scores worse and cannot pass,
  so it errs toward the uncorrected probability; but a fit the weekly refit
  STORES could be such a fit, and would then be refused by the gate forever.
  What would settle it: a damped step or a line search, which changes every
  slope and intercept fitted after it -- a model change no ruling names
  (LAW 2), so the operator's.
- **The learning panel's header states the last refit as an ISO date**
  ("2025-01-15" in the render), where every other date on the page is in
  words. The renderer places `last_refit.slice(0, 10)`; a plain-words line
  from the server would settle it. (The Record tab's corrections note said
  "fitted 2026-09-28" the same way; it says the day in words from this
  release, since the line was being rewritten.)
- **Only a category of 200 distinct settled questions or more can be
  measured** (forty held out at four fifths): on the verified copy of 29
  September, three of the 26 categories -- MLB moneyline 260, total 213 and
  spread 202, all statistical (college point spread, statistical, next at
  185; every reasoning-pass category under 150). That is the old floor, now
  counted in questions; said so the page's "fitted - in force only once its
  measurement is clear of zero" is not read as a promise for a small
  category.

- **NOT SEEN: a measured row written by hand with an interval the
  measurement did not make.** The numbers on a measured row are the
  measurement's own when the door writes it (`activate_measured` measures in
  the same transaction and takes no numbers from its caller), and the schema
  checks their shape, their consistency and their count of distinct bets --
  but a rule cannot recompute a bootstrap, so a raw insert stating a passing
  interval for a tie, with the right counts, would land. The model fits'
  `fit_activations` has the same limit. What would settle it: a gate check
  measuring every measured row on the record's copy again and comparing
  (deterministic, seeded) -- with a reading for a void written after the
  activation, which would move an honest measurement; the operator's.

**After the release**, from the main checkout, in this order (the ruling's:
withdrawn now, then the gate, activation only on a pass):

    python tools/correction_holdout.py --database var/gridiron.db --correction 71 --withdraw
    python tools/correction_holdout.py --database var/gridiron.db --correction 71 --withdraw --write --live
    python tools/correction_holdout.py --database var/gridiron.db --correction 71
    # only if the line above says PASSES:
    python tools/correction_holdout.py --database var/gridiron.db --correction 71 --write --live

Each is refused by name until a scheduled pass or the server's start has
opened the record under this schema (`db.init` adds the table); the dry runs
read through the read-only door. On the copy the third reports the tie above,
so the fourth is not run and fit 71 stays withdrawn.

### Its prover (2026-09-29): getting a correction in force any other way

Tried on the change as first built, each on a scratch world: the weekly refit
(writes inactive, no row), `record_fit` with `active_from` (no such parameter),
a raw insert carrying `active_from` (refused), an edit, a delete and a
replacing insert on the activation table (refused), a number read twice (the
table is WITHOUT ROWID: a function in the statement ran once, so the rules and
the key read one value, and nothing lands in a stored row's place), a labelled
fit and a placeholder (refused by the gate and by a scratch row), a scratch row
on a live-kind record (refused), an interval touching zero or reversed
(refused), a measurement on every forecast (refused by the recount), and the
door's four readers -- the card's model chip, a recommendation's
`calibrated_fair_value`, a forecast's `calibrated_prob`, the learning line --
each through `shown_proposition` / `shown_claim` / `latest_activation`, none
reading `active_from`.

**GOT THROUGH, AND FIXED** (each with a test form, and a planting that escapes
on 428e1cb and on the change as first built -- shown by taking each part out
alone in a copy, when exactly its own planting escaped and the other twenty
correction plantings stayed caught):

1. **One resample, or another seed.** `measure(conn, id, draws=1, seed=6)` on a
   tie of 260 questions gave the "interval" [+0.0107, +0.0107], and the door's
   own writer wrote it, every number true to its drawing; any seed was taken,
   so a tie could be drawn again until one passed. The measured row is now
   refused unless drawn as the gate draws it: 1000 resamples from seed
   20260923 (`correction_activation_carries_its_measurement`, pinned and tested
   equal to `correction.BOOTSTRAP_DRAWS` and `BOOTSTRAP_SEED`).
   `plant.py::plant_a_correction_measured_by_another_bootstrap`.
2. **Dated back.** `activate_measured(..., now=<a day after the fit, months
   back>)` wrote a row the door served from that day; the page corrects a
   finished game's claim by the correction in force when the claim was written
   (`recommend.correction_instant`), so it would have reached every claim of
   those months on the page. A withdrawal dated back takes one off: fit 71's
   ruled withdrawal dated 2026-09-28T13:00:02Z was accepted on the rehearsal
   copy. On a record -- a live kind, or a record's own rows -- a row is now
   refused more than a minute before it is written
   (`correction_activation_is_stamped_when_written`); a scratch world dates its
   rows as it likes. `plant.py::plant_a_correction_activation_dated_back`.
3. **The kind set by hand.** `UPDATE meta SET value = 'scratch' WHERE key =
   'kind'` on a record holding a correction written in force the old way, then
   a raw scratch row: it landed and the door served it. The scratch rule now
   refuses a database holding a record's own rows -- a measured row, a
   withdrawal, a correction written in force the old way -- whatever its kind
   says (`correction_activation_scratch_is_never_live`; the Python door already
   did). `plant.py::plant_a_scratch_correction_activation_on_a_live_record`,
   its third form.

**GOT THROUGH, HELD BY A TEST AND NOT BY A RULE (NOT SEEN by the schema): which
questions a measurement held out, and which forecast of each it scored.** The
rules recount the count and the fifth, not the set. A measurement that
shuffled its questions (two shuffles of five passed the gate on a world of 250
questions and were written), split them by number, kept each question's FIRST
pass (written: measured on the morning passes, the count right), or mixed in
another forecaster's questions keeping the count, writes a row every rule
accepts -- and the suite as first built passed a random split and a split by
number (200 of 200 correction, recommendation and Today tests).
`test_correction_activation.py::test_the_measurement_scores_the_latest_fifth_as_they_settled_drawn_as_the_gate_draws`
works the measurement out again from the rows -- each question's latest
written forecast, the latest fifth as they settled held out, a refit on the
rest, `tools/holdout.py`'s own bootstrap of the differences -- on a world whose
questions settle in another order than they were written, and fails on all
four. What would close it in the schema: a rule recomputing the raw Brier of
the latest fifth on each question's latest written forecast. It is not built:
question 27 is ruled to change the standing pass (a final pass before the
start stands, else the latest early pass), and a rule holding "the latest
written" would refuse the measurement question 27 makes -- a rule's text is
never replaced on a record that holds it. For question 27's build.

**Found on the way, to the re-read** (the queue rule: none breaks LAW 1 or LAW 3
or makes a gate count false):
- **The model fits' scratch rule has the same hole.**
  `fit_activation_scratch_is_never_live` reads only the meta kind, so the kind
  set to scratch by hand lets a scratch activation of a model fit land on the
  record; `model.activation.activate_in_a_scratch_world` refuses a record in
  Python, and a raw statement goes round it. Question 32's rule (a record known
  by its own rows) would carry over; the model gate is not the ruling's.
- **`schema.sql`'s column comment on `calibration_corrections.active_from`**
  still says "NULL means fitted but NOT ACTIVE. A correction is inert until
  this is set" -- false from this release (it is history, read as in force by
  nothing). It sits inside the table's declaration, whose text the record
  stores, so it is left as written rather than make a fresh build's stored
  text differ from the record's; the block above question 32's rules says what
  the column is now.

**The prover's rehearsal** (a fresh verified copy through
`rebuild.verified_backup`, 44.5 s, integrity ok, 62 tables proved equal, none
mismatched, read 07:59:33Z to 08:00:18Z; a copy of it opened under this tree):
`db.init` 250 -> 266 objects, exactly the table and its fifteen rules, none
gone or changed, no table's count or column checksums moved, the new table
empty, the rules in a fresh build's order, 0 differences from a fresh build
with an EMPTY register, a second open changing nothing; fit 71's withdrawal
dated back refused before anything was written; the tool: the dry run wrote
nothing, the gate asked before the withdrawal refused ("the ruling's order"),
the withdrawal written once and "already withdrawn, as ruled" after; the gate
read-only: 260 questions, refit on 208, scored on 52, Brier raw 0.247471,
corrected 0.247620, improvement -0.000149, 95% interval [-0.015132, +0.016931]
(1000 resamples, seed 20260923) -- a tie, the implementer's figures exactly;
`--write` exit 1 twice, nothing written; `--live` on the copy refused; on the
record's own path, `--write` and `--withdraw --write` without `--live` refused
before any open. Then on the rehearsed copy a row of one resample, a row from
another seed, a row dated back, a scratch row after the kind was set by hand,
and the scratch door: all refused, the one withdrawal unchanged. The door
serves nothing in any category; both correction gate checks pass; 0 forecasts
and 0 recommendations carry a correction. Every copy was deleted.

## The standing pass is chosen by pass; no early pass over a final one -- built 2026-09-29 *(operator question 27, ruled 2026-09-28, second set; the brief's reading confirmed by the operator 2026-09-29; docs/briefs/2026-09-28-rulings-second-set.md and 2026-09-29-rulings.md)*

The ruling: "Q27: the standing pass is chosen by pass, not by write time: the
final pass stands whenever one exists before the start; otherwise the latest
early pass. A read rule -- no row changes. The 16 NFL totals are re-scored
under it and every moved number listed. Separately, a catch-up may not run an
early pass for a question whose final pass exists; it is a
SlateAlreadyAnswered noop. Own commit, planting." What was built is CLAUDE.md's
ONE CLAUSE row (the rule) and THE JOBS row (the noop); what follows is the
evidence, the readings taken, and what is left. A first attempt, stopped
part-way when question 32 was ruled ahead of it, is on branch `q27-held`
(80108c1); it was read, not merged, and this was built on 6eae162.

### THE SIXTEEN, RE-SCORED *(one verified copy of the record through `rebuild.verified_backup` into `scratchpad/q27/`, read 2026-09-29T09:34:40Z-09:35:27Z, integrity ok, 63 tables proved equal, none mismatched; read-only; `scratchpad/q27/v2/rescore.py` -> `rescore.json`)*

Every one is an NFL week-3 total asked of the reasoning pass (factor set fs2),
the final pass written by `final:nfl` (run 2052) on 23 September at
19:30-19:31Z and the early pass by the catch-up's `predict:nfl` (run 2336) on
24 September at 05:32-05:36Z, both before the start, at the same rung, neither
withdrawn. All sixteen have settled (PHI at CHI on 29 September). Each stated
the over. Brier and log loss are the question's own contribution, the claim
against whether its side happened.

| game (start) | rung | score | STOOD: early pass | STANDS: final pass |
|---|---|---|---|---|
| ATL at GB (25 Sep 00:15Z) | 41.5 | 35-14, over | 2227: 54%, hit; 0.2116 / 0.6162 | 1999: 52%, hit; 0.2304 / 0.6539 |
| CAR at CLE (27 Sep 17:00Z) | 47.5 | 18-21, under | 2232: 50%, miss; 0.2500 / 0.6931 | 2009: 50%, miss; 0.2500 / 0.6931 |
| CIN at PIT (27 Sep 17:00Z) | 29.5 | 27-30, over | 2237: 52%, hit; 0.2304 / 0.6539 | 2015: 50%, hit; 0.2500 / 0.6931 |
| HOU at IND (27 Sep 17:00Z) | 50.5 | 17-19, under | 2242: 50%, miss; 0.2500 / 0.6931 | 2021: 50%, miss; 0.2500 / 0.6931 |
| KC at MIA (27 Sep 17:00Z) | 47.5 | 24-10, under | 2247: 50%, miss; 0.2500 / 0.6931 | 2027: 52%, miss; 0.2704 / 0.7340 |
| LAC at BUF (27 Sep 17:00Z) | 53.5 | 16-24, under | 2250: 50%, miss; 0.2500 / 0.6931 | 2033: 50%, miss; 0.2500 / 0.6931 |
| NE at JAX (27 Sep 17:00Z) | 29.5 | 6-35, over | 2253: 52%, hit; 0.2304 / 0.6539 | 2039: 50%, hit; 0.2500 / 0.6931 |
| NYJ at DET (27 Sep 17:00Z) | 35.5 | 24-31, over | 2258: 54%, hit; 0.2116 / 0.6162 | 2045: 54%, hit; 0.2116 / 0.6162 |
| SEA at WAS (27 Sep 17:00Z) | 32.5 | 31-33, over | 2263: 50%, hit; 0.2500 / 0.6931 | 2051: 52%, hit; 0.2304 / 0.6539 |
| TEN at NYG (27 Sep 17:00Z) | 38.5 | 7-12, under | 2268: 50%, miss; 0.2500 / 0.6931 | 2057: 50%, miss; 0.2500 / 0.6931 |
| ARI at SF (27 Sep 20:05Z) | 32.5 | 30-36, over | 2273: 52%, hit; 0.2304 / 0.6539 | 2063: 52%, hit; 0.2304 / 0.6539 |
| MIN at TB (27 Sep 20:05Z) | 35.5 | 23-16, over | 2278: 50%, hit; 0.2500 / 0.6931 | 2068: 52%, hit; 0.2304 / 0.6539 |
| BAL at DAL (27 Sep 20:25Z) | 41.5 | 34-31, over | 2283: 50%, hit; 0.2500 / 0.6931 | 2070: 50%, hit; 0.2500 / 0.6931 |
| LV at NO (27 Sep 20:25Z) | 44.5 | 35-27, over | 2286: 52%, hit; 0.2304 / 0.6539 | 2072: 52%, hit; 0.2304 / 0.6539 |
| LA at DEN (28 Sep 00:20Z) | 35.5 | 26-30, over | 2291: 50%, hit; 0.2500 / 0.6931 | 2074: 50%, hit; 0.2500 / 0.6931 |
| PHI at CHI (29 Sep 00:15Z) | 41.5 | 7-27, under | 2296: 52%, miss; 0.2704 / 0.7340 | 2076: 50%, miss; 0.2500 / 0.6931 |

Summed over the sixteen: Brier 3.8652 (early) against 3.8840 (final), log loss
10.8204 against 10.8581 -- the final pass scores better on 3 (SEA-WAS,
MIN-TB, PHI-CHI), worse on 4 (ATL-GB, CIN-PIT, KC-MIA, NE-JAX) and the same on
9. No outcome and no hit changed (every pair states the same side). The
curve they sit in, NFL total, reasoning pass (17 settled questions): Brier
**0.2409 -> 0.2420**, log loss **0.6750 -> 0.6772**, hit rate 0.6471 unchanged;
week 3 alone (16): Brier 0.2416 -> 0.2427, log loss 0.6763 -> 0.6786. None
of the sixteen early passes carried a price or a second media look; PHI-CHI's
early pass carries four claims at the venue's line and recommendation 65
(below), its final pass one claim. The one copy of the record behind every
figure here (`scratchpad/q27/record_q27.db`, 1.08 GB, and the `-shm` and
`-wal` SQLite kept beside it) was deleted at the end of the step; no other
copy was made.

### EVERY MOVED NUMBER *(the released code -- 6eae162, whose code is master's c5dbd3b -- against this tree, both built in one process each on the one copy with the clock held at 09:35:27Z; every payload the Record page and its gate list read, every sport's slate, NFL week 3's slate asked by name in both views, and the gate's measurement of every fitted correction; `scratchpad/q27/v2/measure.py` -> `m_head.json`, `m_new.json`, `flatten_diff.py` -> `diff.json`, `summarise.py` -> `summary.txt`; 282,687 figures compared, 0 errors either side)*

Which rows move, on the whole record (`standing_moves.py` -> `standing_moves.json`):
the standing forecast of **16 questions** (the sixteen; no other question's
standing forecast moves in any sport, and within one factor set no other
early pass on the record was written after its final pass) and the standing
claim at the venue's line of **8 questions**, each from its early pass's later
claim to its final pass's own last claim before the start: NFL total,
reasoning pass, PHI at CHI (claim 1720 on 2296, 28 Sep 22:35Z, venue 48.5% ->
claim 650 on 2076, 23 Sep 19:31Z, 47.5%); MLB point spread, statistical, six
(mlb_823411 PHI, 824707 BOS, 823816 MIA, 824057 KC, 823245 SD, 823083 SEA:
the same claim of 29.4-37.5% each, the venue's price the same but SEA's,
39.5% -> 40.5%); MLB moneyline, statistical, one (mlb_824866 ATL, the same
claim and price). The seven MLB questions' final pass already stood on the
blind record; the near-start reader kept claiming on the early pass after
the final pass was written -- six of them carry a recommendation, which it
reads on every firing until the start (recs 60, 61, 85, 98, 100, 101), and
ATL's early pass its media line's second look.

- **Record by category, NFL total, reasoning pass** (n 17): Brier 0.2409 ->
  0.2420, log loss 0.6750 -> 0.6772; the 50-60% band's claimed 0.5118 ->
  0.5106 and its gap 0.1353 -> 0.1365 (n 17 and actual 0.6471 unchanged);
  the version table's fs2 row the same two; over time, the week-3 point
  Brier 0.2416 -> 0.2427, claimed 0.5112 -> 0.5100, gap 0.1138 -> 0.1150.
- **At the venue's line, NFL total, reasoning pass** (n 1: PHI-CHI): the
  model's Brier 0.2704 -> 0.2500, log loss 0.7340 -> 0.6931, its band's
  claimed 0.52 -> 0.50 (gap -0.52 -> -0.50); the market's on the same
  question Brier 0.2352 -> 0.2256, log loss 0.6636 -> 0.6444. **MLB point
  spread, statistical** (n 102): the market's Brier 0.2613 -> 0.2611, log loss
  0.7165 -> 0.7162; the model's unchanged (0.2085, 0.6075). MLB moneyline:
  nothing moved.
- **Where the line went at the venue, MLB point spread, statistical** (56
  pairs, unchanged): the mean movement 0.019732 -> 0.019554 (SEA's pair).
- **The NFL slate, reasoning pass** (the page's own week, week 3, and week 3
  asked by name, the same): the sixteen cards are the final passes (1999,
  2009, ... 2076) in place of the early passes (2227, 2232, ... 2296), each
  with its own claim, time written and figures; the shortlist 38 -> 42
  questions ("the other 7" -> "the other 3": the final passes' ranks put 14 of
  the sixteen on it where the early passes' put 10), the total tab 10 -> 14,
  the all tab 38 -> 42, the recommendation panel's considered 38 -> 42 and
  "23 carried a venue price and none cleared its fee" -> 27, the Today
  panel's "38 questions watched" -> 42 (its settled and watching headings the
  same), today's median venue price 47c -> 46c; fifteen other cards'
  shortlist places move by one or two. The early view shows the same sixteen
  early cards, each with its band's record as the curve now reads it. **THE
  FORECASTER COUNT beside the slate** (`forecasters`, on both forecasters'
  pages): the reasoning pass 72 -> 45. The card now reads the one clause --
  one row per question across factor sets -- where its own rule dropped only
  a row a later row of the SAME factor set replaced, so it counted week 3's
  reasoning-pass moneylines and spreads under two factor sets each (fs2 and
  fs3 final passes of 25 September beside fs5 early passes of 24 September:
  31 and 25 rows for 16 and 13 questions) while the page showed each once;
  45 is the cards it shows. The statistical model's count did not move.
- **The gate's correction measurement** (48 fitted corrections measured, on
  no page): no number moved -- fit 71 still 260 questions, 52 held out, Brier
  0.247471 raw against 0.247620, interval [-0.015132, +0.016931], a tie;
  fits 74 and 76 as they were -- because no settled question of a fitted
  category has an early pass written after its final. Only the words of
  what was held out: "one forecast each (its latest written)" -> "(its final
  pass if one settled, otherwise its latest written)". And the measurement
  and its check still agree: `tools/correction_holdout.py --correction N`,
  read-only on the copy under this tree, for 71, 74 and 76 -- "each of the
  260 / 202 / 213 questions stands on the forecast the blind record's
  standing rule keeps", each a tie, nothing written.
- **Nothing else moved**: no count anywhere (no curve's n, gate line,
  outlook, priced count, drift count, coverage line, closing line, kill
  criterion, correction count or empty-bar day), no other blind curve, no
  other sport's slate. **CORRECTED 2026-09-29 by the numbers step** (the
  released c5dbd3b against 2eda91a on one verified copy read 11:03Z, every
  slate of every sport built; `scratchpad/q27/numbers/moves.md`): the list
  above measured only the current week and week 3, and it left out four
  moves, each the same mechanism as the 72 -> 45 it lists (a question asked
  under two factor sets was counted once per set on the slate; the card now
  reads the one clause):
  - NFL week-1 slate: the statistical forecaster's count, on both
    forecasters' pages and in the words "statistical made N", 128 -> 101
    (27 questions asked under two factor sets).
  - NCAAF slate of 5 September: the statistical count 250 -> 243 (7
    questions under two sets). So "no other sport's slate" was untrue.
  - NFL week-2 NYG-LA total card (1796 on the standing view, 1769 on the
    early view): its band's claimed 0.5118 -> 0.5106.
  - The Today panel: "Settled - 38 questions" -> "Settled - 42 questions",
    and "Watching - 38 more" -> "Watching - 42 more" (watching_n 38 -> 42);
    the "45 settled" count is unchanged.
  None breaks LAW 1 or LAW 3 or makes a gate count false (the queue rule):
  the counts are now right; only this list was short.

### BUILT
- **The rule, one door.** `calibration.standing_pass_order(forecast, game,
  row)` -- a final pass written before the start (or on a game with no start
  recorded) first, then the latest written, then the number -- orders the
  standing clause's candidates (`standing_row_clause`, both forms) and the
  at-the-line window (`at_the_line.standing_claims`, its claims by their
  forecast's pass). Which rows may stand is unchanged. `views.week` reads the
  clause. `recount.standing_of` and `standing_claims_of` restate it
  (`_final_before_the_start`; `recount.forecasts` and `claims` select the
  pass and the forecast's write time). `correction.holdout_questions` keeps a
  question's final pass if one settled, else the latest written
  (`settled_rows` selects `pass_kind`), and its holdout words say so;
  `tools/correction_holdout.py`'s check is unchanged, its words updated.
- **The guard.** `audit.standing_pass_faults` / `check_the_final_pass_stands`
  (gate step 2, `tools/verify.py`): a world of six questions
  (`audit.STANDING_PASS_WORLD`) on one settled NFL total, two near-start
  looks and a claim per forecast at each, asked of nine doors; each door
  that keeps another row is named, with the pass and time it kept.
- **The noop.** `predict.final_pass_written` (the one door; `bet.given`, a
  fourth form of the key); `predict_slate` asks it before each early write
  and before each reasoning call, and names the question in
  `BlindRun.final_pass_answered`; `write_prediction` asks it again;
  `run.run_slate` raises `SlateAlreadyAnswered(final_pass_answered=...)` for
  a run left with nothing else to write and carries the names in its result;
  `tasks._run_predict` records the refusal 'noop' in its own words and the
  names in the payload, and an ok run the names beside what it wrote;
  `run_task` keeps them on a run failed for want of a model; the words are
  `language.final_pass_answered_words` and `final_pass_answered_refusal`.

### PROVED *(`scratchpad/q27/v2/`)*
- **The plantings** (`run_plantings.py`, this tree's `plant.py` placed in a
  `git archive` of 6eae162, `plantings_head.txt`; and this tree,
  `plantings_fix.txt`, `plantings_fix_all.txt`):
  `plant_a_standing_rule_keeping_a_later_early_pass` ESCAPES on 6eae162 ("the
  standing clause keeps forecast [2] for a question whose final pass (1, 23h
  before the start) was written before its early pass (2, 13h before), and no
  check asks which pass stands") and is CAUGHT here, each of five plantings
  named by its door (the one order put back to the write time -- the clause,
  the outlook's door, the at-the-line window, the card; the at-the-line
  window alone; the recount's forecasts; its claims; the correction's
  measurement); `plant_an_early_pass_written_over_its_final_pass` ESCAPES on
  6eae162 ("the early pass wrote 8 forecasts over the 8 questions the final
  pass had answered") and is CAUGHT here (refused as already answered naming
  8; the open market written, 4, and 8 named; the task's record 'noop' in
  plain words). Fourteen plantings the change touches stay CAUGHT.
- **The tests:** `tests/test_standing_pass.py` (22; `tests_on_head.txt`: 18
  fail on 6eae162, and the 4 the ruling leaves as they were pass on both --
  an early pass then a final pass, two early passes and no final, a final
  pass written after the start, the backtest fallback);
  `test_correction_activation.py`'s measurement test now scores each
  question's final pass on a world where a fifth of the early passes were
  written after their final, and its tool test parts the two rules on a
  FINAL pass written after the start (an early one no longer parts them);
  both fail on 6eae162.
- **THE HARNESS CAUGHT ONE THING THE BUILD BROKE** (the full suite's first
  run: 2113 passed, 1 failed -- `test_the_planted_violation_harness_catches_everything`,
  361 of 362 caught). `plant_the_check_moved_back_after_the_call` escaped:
  `audit.reason_before_check_faults` holds the slate loop's FIRST
  `already_written` call before `llm.reason`, and the noop's check in the
  statistical half, asked inline, was now that first call -- so with the
  reasoning pass's own check taken out the scan still passed, and a resumed
  run could have paid for every question twice unseen. The check is asked
  through `predict._left_to_its_final_pass`, outside the loop, and the
  planting is caught again (`plant_all.txt`, then the second full run).
- **The full suite, second run** (a dummy access token, TMP and TEMP at their
  defaults; `suite2.txt`): **2114 passed, 8 skipped**, in 21 minutes, the
  planting harness among them, 362 of 362 caught. No browser test flaked.

### READINGS TAKEN *(each reversible in one line)*
1. AT THE VENUE'S LINE a claim on a final pass written before the start
   stands over any claim on an early pass, and within the pass its last
   claim before the start; a final pass with no claim before the start is no
   candidate there, as a withdrawn one is not, so its question keeps its
   early pass's last claim (reverse: the window ordered by the claim's time
   alone, as before).
2. THE CARD reads the clause, so it shows one row per question across factor
   sets, and the forecaster count beside the slate counts those rows
   (reverse: its own write-time rule back in `views.week`'s fetch).
3. THE NOOP'S QUESTION is the one function's key -- forecaster, game,
   market, subject, rung -- whatever factor set wrote the final pass; another
   rung is another question and is written (reverse: `already_written`'s key
   with the pass flipped).
4. "EXISTS" is read as written: a withdrawn final pass still exists, so no
   early pass is written over it either (reverse: `final_pass_written` skips
   a voided row).
5. IT BINDS EVERY RUN THAT WRITES AN EARLY PASS (the confirmed reading): the
   door is asked in the writer, not in the catch-up.
6. A RUN LEFT WITH NOTHING TO WRITE is refused as answered only when nothing
   else was left unanswered: a market with no model still fails the run by
   name (item 2), and an unavailable reasoning pass is a degradation the
   ordinary result keeps (reverse: drop the two conditions in `run_slate`).
7. THE SKIP IS COUNTED by name: `final_pass_answered` in the run's result and
   the task's payload, its length the count, and one line in `skipped`.
8. THE CORRECTION reads the pass alone, not the start (it may not name
   `games`), and the tool holds it to the blind record's rule.
9. NOT A STANDING-ROW CHOICE, left as they are: `recommend.counted_once` and
   its recount count a same-side pair's EARLIER recommendation (question 12's
   words, "the earlier row"); item 5's write rule keeps the forecast written
   first when one pass takes one side twice; `views._superseded_ids` labels
   an early row that has a final pass (question 30, its key its own); each
   forecast's own claims are chosen by time (`views._at_the_line`, a
   recommendation's pricing claim, the closer), which is one forecast's
   looks, not a question's rows; `calibration.early_vs_final` pairs by pass
   (below). The priced, drift and outlook doors, the coverage line and the
   ranker read the clause and move with it.

### OPEN *(found by this step; the queue rule: none breaks LAW 1 or LAW 3 or makes a gate count false)*
- **Recommendation 65 stands on PHI-CHI's early pass (2296)**, which no longer
  stands on the blind record: the reasoning pass's only NFL total
  recommendation (the over 41.5 at 47.5c, CLV +6.0c). Recommendations are
  counted by bet, per forecaster (questions 12 and 22), and read no standing
  rule, so it counts as before and nothing moved; its forecast is now the
  record's superseded pass.
- **PHI-CHI's standing claim at the venue's line is now five days old** (the
  final pass's only claim, 23 September 19:31Z), where the early pass's claims
  were read near the start (28 September 22:35Z): the near-start reader
  claims on a forecast carrying a recommendation or a media line, and the
  final pass carried neither. The ruling's order, and the at-the-line
  record's design; for the re-read.
- **The timing comparison (`calibration.early_vs_final`, on no page) pairs by
  pass**: NFL's 55 pairs include the sixteen, whose "early" pass was written
  about ten hours AFTER their "final" -- without them 39, under its fifty.
  It states nothing on any page (FOLLOWUPS above: no caller); the noop keeps
  another such pair from being written.
- **`audit.reason_before_check_faults` reads the first `already_written` call
  in the slate loop, whatever forecaster it asks about** (found by the
  harness, above): any check asked inline before the reasoning call --
  the statistical half's own, one day -- blinds it. Holding the call that
  names the reasoning pass would settle it; the scan is item 1's of
  2026-09-05, not this ruling's, and today nothing inline stands before it.

### THE PROVER *(2026-09-29, alone in the worktree; `scratchpad/q27/prove/`)*

Asked adversarially: which count or page still picks a question's row by
write time; a pass given as NULL; a final pass withdrawn, or written after the
start; UFC cards; props at two rungs; an early pass written by another path.

- **NO DOOR LEFT CHOOSING BY WRITE TIME.** Every `ORDER BY ... created_utc`,
  `MAX(created_utc)` and latest-before-the-start over the forecasts, the
  package and `tools/` both, is either the one clause (the blind curves, the
  version table, the priced, drift and outlook doors, the coverage line, the
  ranker's `is_standing`, the login page's open count, and now the card), the
  one order (the at-the-line window), its Python spelling (`recount`), the
  correction's by-pass measurement -- or a choice among ONE forecast's own
  claims or ONE recommendation's reads (`views._at_the_line`, the pregame
  figure, the pricing claim, the closer), or a recommendation count
  (question 12's earlier row), none of which chooses a question's row. A
  pass given as NULL cannot be stored (`pass_kind` is NOT NULL, default
  'early'; the schema's replace rules read a NULL as either pass). UFC's card
  and a prop's rung sit outside the order and inside the key: two rungs are
  two questions to the clause, the window, the recount, the correction and
  the noop alike. Every early pass is written by `run.run_slate` ->
  `predict.predict_slate` -> `write_prediction` -- the scheduled predict, the
  catch-up (which runs it), a hand `cli predict` (refused loudly, as ruling
  R4's rerun is), a rerun after a failure and the backtest tool -- and the
  insert in `write_prediction` is the one statement that writes a forecast.
  Stored ranks keep the `is_standing` the clause gave when each was written
  (append-only, read as written; no early pass can now be ranked over a
  final one).
- **FOUND AND FIXED: THE NOOP'S PLANTING NEVER RAN THE REASONING PASS**, the
  sixteen's own forecaster. Neutralised in a copy, predict_slate's reasoning
  check (paid for, thrown away by `write_prediction`, and not named) and that
  check with `write_prediction`'s second one (reasoning early passes written
  over their final passes: the record's own shape) both passed the planting
  as built, and only the suite saw them. The planting now runs week 8 with
  both forecasters, the reasoning pass answered by a stub that spends
  nothing (`plant._Q27Reasoner`), the final pass answering the total alone
  and the early pass asked everything: caught only if it writes no total,
  asks the reasoning pass once for each reasoning forecast it writes (8) and
  names every total it left, the reasoning pass's 4 among them. Both
  neutralisations are now NOT CAUGHT by it (12 requests for 8 forecasts; 4
  totals written over their final pass). `write_prediction`'s second check
  alone changes nothing a run does -- `predict_slate` asks first -- and is
  held by `test_standing_pass.py::test_no_early_pass_is_written_over_a_final_pass`
  (fails with it taken out).
- **FOUND AND FIXED: SIX DOORS STILL SAID "THE LATEST WRITTEN BEFORE THE
  START"** of the rule they read -- the at-the-line door's own docstring,
  `drift.standing_pairs`, `horizon.standing_questions`,
  `priced.forecast.standing_forecasts`, `shortlist.settled_for_gate` and
  `config`'s account of the final pass. Each now says the final pass before
  the start comes first, dated; no code changed.
- **SEEN BY THE GUARD, NOT BEFORE:** the card's old rule (put back in a copy)
  kept a final pass written AFTER the start over the early pass before it --
  the fetch kept both and its Python step kept the later -- where the clause
  never lets such a row stand. None on the record (the missed rule writes
  none); the card reads the clause now.
- **EACH PART NEUTRALISED IN A COPY OF THE FIXED TREE** (`neutralise.py`,
  results `res_*.txt`, `res2_*.txt`): the one order put back to the write
  time -- the check names the clause (both forms), the outlook's door, the
  at-the-line window and the card; the window alone, the recount's
  forecasts, its claims, the correction's measurement, the card's old rule
  -- each named by the check, alone; predict_slate's statistical check --
  not refused, the open market's run naming none; with `write_prediction`'s
  too -- 8 early passes written over 8 final passes; the refusal in
  `run_slate` -- not refused; the task's own words -- recorded in the rerun's
  words; `bet.given` with `=` for `IS` -- the moneyline's absent rung never
  matched, 4 early passes written over their final pass; the reasoning check,
  and with the second check -- above. Every one NOT CAUGHT by the planting or
  named by the check, but the second check alone (the test above).

### OPEN, FROM THE PROVER *(the queue rule: none breaks LAW 1 or LAW 3 or makes a gate count false)*
- **The early-view label reads no withdrawal and no start**
  (`views._superseded_ids`, question 30's). With the card on the clause, a
  standing early row whose final pass was withdrawn, or written after the
  start, would show "Early view ... A later forecast stands in its place."
  on the standing card; before this change the first case took the question
  off the slate and the second was already so. Read on the record
  (read-only, 2026-09-29): 0 standing early rows labelled that way, in every
  sport.
- **The sixteen's early rows, asked for in the early view, say "A later
  forecast stands in its place"** of a final pass written about ten hours
  BEFORE them ("later" meant the later pass). Words on a view that must be
  asked for, on NFL week 3, played; the noop writes no more such rows.
- **The gate's world asks the outlook's door for the doors that read the
  clause**; the priced and drift doors read the same clause text (read, not
  asked), so one rewritten to a rule of its own would be seen only by a
  recount, and only where one pass carried a price or a second look the
  other did not.

## The board merged into the repair -- built 2026-09-29 *(the board-merge checklist, step 2 with its third-set additions; operator questions 18 and 19, question 20's side question; docs/briefs/2026-09-27-board-merge.md and 2026-09-27-rulings-third-set.md)*

`origin/board` at a63463a (16 commits from fe4dc58) merged into `repair` at
8ce66d2 with `git merge --no-commit --no-ff`, left uncommitted for the
prover. `board` itself was read and merged, never checked out, committed to
or moved. Every conflict went to repair's behaviour; the board restyles, and
removes and recounts nothing repair released. CLAUDE.md's THE BOARD, MERGED
row says what the merge's own guards are; this is the record of how it went.

### THE CONFLICTS -- 7 files, 16 hunks, each and how it resolved

1. **`gridiron/audit.py`, one hunk at the end of the file.** Repair appended
   question 12/22's recount of the closing line, question 13's and 24's
   rules' checks and question 15's replacing-write scan; the board appended
   its three guards (a signal carries its badge, no typed club hex, the board
   speaks plain) with their import-time check. Both kept, repair's first; the
   board's are separate functions and names. In the board's block afterwards:
   a tooltip may carry a version name (question 19), and the advice scan
   reads a sentence with the declared factor phrases taken out (below).
2. **`gridiron/calibration.py`, one hunk in `clv_report`.** The board added
   a `series` (every measured close, in the order it closed) and `gate_words`
   ("12 of 50") to the one loop over a sport's markets -- both forecasters
   pooled, the closes from before the repair included, drawn once a market
   had fifty. Repair had split that loop per forecaster into
   `_closing_line_of` (question 22), read through `recommend.counted_once`
   (question 12) and counted from the window (ruling 8). RESOLVED to repair's
   loop; the series, the chart's words and its title are made inside
   `_closing_line_of` from `got` -- this forecaster's counted closes since the
   window opened -- and there are none until the first clean read (a point is
   a figure): the area says "N of 50 · nothing is drawn before Thursday 15
   October" (`language.chart_gate_words`, `closing_chart_title`).
3. **`gridiron/language.py`, one hunk at the end.** Repair's prompt-record
   words; the board's board words. Both kept.
4. **`gridiron/web/app.js`, hunk 1.** Repair's `promptDisclosure` (the prompt
   a reasoning forecast was sent, 2026-09-25) and the head of `todayCard`, the
   old card; the board's `signalClass` and `tip`, having deleted `todayCard`
   with the old route. `promptDisclosure` kept, the board's taken; `todayCard`
   goes with the old Picks route (step 4 removes it in this release).
5. **`app.js`, hunk 2.** Repair's end of `todayCard`: the Why panel holding
   the prompt disclosure and the "How the model works" link; the board's
   `probBar`. The board's taken: the old Why panel leaves with the board
   (question 20's side question). The prompt disclosure is RE-HOMED on the
   tile of every reasoning-pass question on a game's open row (the board's
   blocks carry `prompt` now, the other forecaster's rows' included, through
   `views._prompts_for`); the link to the workings is on the open row already
   (the board's `.game-more-link`), made a 44px target.
6. **`app.js`, hunk 3.** Repair's `phraseWithPrompt` (Results' rows) against
   the board's blank. Repair's kept.
7. **`gridiron/web/style.css`, hunk 1.** Repair's `#today` arriving by its
   fade alone (question 20); the board's `#games-rows, #props-tiles`
   transitioning opacity AND transform. RESOLVED: the board's panels, opacity
   alone. The Today panel is gone.
8. **`style.css`, hunk 2.** Repair's `#today.arriving` with no transform; the
   board's `#games-rows.arriving, #props-tiles.arriving` one per cent below,
   and its updating state. RESOLVED: the board's panels with no transform, the
   updating state (dimmed, untouchable, busy, instant) kept.
9. **`style.css`, hunk 3, at the end.** Repair's prompt-disclosure rules; the
   board's whole block. Both kept, then the board's motion put under question
   20: each row and tile's stagger and an opened row's expansion arrive by
   opacity (the board's were `translateY(1%)` with a transform transition);
   no row lifts on hover (the tap that opens a row leaves it hovered on a
   phone, off whole pixels at rest); the bar's one first-load fill fades
   instead of scaling (`audit.bar_fill_faults` re-ruled to a fade, the
   MOTION row). `.prompt-commit` went (question 19).
10. **`tests/test_guards.py`, one hunk.** Both sides appended planting names
    to the harness's list; both kept, and the merge's three added.
11-16. **`tests/test_smoke.py`, six hunks** -- `test_a_card_expands_and_shows_
    its_detail`, `test_nothing_moves_under_reduced_motion`, `test_the_phone_
    layout_does_not_overflow`, `test_a_card_still_expands_on_a_phone`,
    `test_the_dumbbell_and_contribution_bars_fit` and `_open_first_card`.
    Repair wrapped each hash change in question 28's `wait_for_the_redraw_it_
    starts` on `#/week` and `#today .face`; the board re-pointed each at
    `#/games` and `#games-rows .game`, with no wait. RESOLVED: the board's
    selectors inside repair's wait, the helper re-pointed at the Games rows.

And one not a conflict: `.gitattributes`. The board vendored two licences,
hashed in `web/fonts/SOURCE.md`, from a machine with no CRLF conversion; on
this one the merge checked both out with carriage returns and
`audit.check_vendored_fonts` failed, as it did for OFL.txt on 2026-09-04.
The two files are declared `-text` beside it.

### WHAT MOVED WITHOUT A CONFLICT -- the board's code, through repair's doors

Every file git merged cleanly was read for code going round a door. What was
found, and where it goes now:

- **The badge** (`board._settled_n`) counted `calibration.resolved` itself --
  the same rows as the edge gate, so no number moves -- and now asks the
  gate's own door, `shortlist.settled_for_gate`, by name: one forecaster's
  standing rows on question 17's key, question 27's order.
  (`test_every_badge_counts_the_edge_gates_own_questions` is a pin: it
  passes on the board's code too.)
- **The other forecaster's rows on an open row** (`_other_forecaster_rows`)
  kept a rule of their own -- the latest written before the start, keyed
  without the prop type through `IFNULL(line_asked, -1e9)` -- which is the
  write-time rule question 27 replaced. Now `calibration.standing_row_clause`
  (on `bet.same`), and the number shown is the one stored for the reader
  (`calibrated_prob`). Proved: an early pass written after a final one stood
  on the board's code.
- **A priced question's chance** read the card's stored number; the old
  card's model chip read the Today entry's `fair_value`, corrected through
  `correction.shown_proposition` by what question 32's door puts in force.
  Now the entry's, turned to the side the question names. The same number
  today: nothing is in force.
- **A live row's blocks** carried `prob` and `prob_words`, never drawn. Gone
  (LIVE TAB, below).
- **"Taken, passed over, every forecast"** (`calibration.taken_comparison`,
  on a page for the first time): a tap was matched to the standing row's
  number, so a question tapped on one pass and standing on another was
  "passed over"; now by `bet.of`, a tap on a withdrawn forecast taking
  nothing (the released `test_voids.py` test holds that). The board asked
  every prop market twice -- as a market type, finding nothing, and as a
  prop -- so the panel said "Nothing settled yet in passing yards, ..." above
  a passing-yards block with its count (found by looking at the render);
  each market is asked once now. Each block says whose ("passing yards,
  statistical"), the empty list says it once, and the panel's total over
  every market is gone (nothing read it; questions 14 and 22 took the like
  off every panel).
- **`loader.load_rosters`** was an `ON CONFLICT ... DO UPDATE` upsert on the
  new `player_numbers`; `audit.UPSERTS_REGISTERED` is frozen at 35 and only
  shrinks. Written plainly (an update, then a plain insert where no row
  changed, the one transaction); `test_load_rosters_writes_the_rows_the_
  upsert_wrote` runs the board's statement beside it.
- **`player_numbers`** -- a loaded roster, refreshed at each load, not
  append-only, and display only (the operator's ruling of 2026-09-29; "The
  roster's numbers are display only", below) -- reaches the record through
  `db.init` alone. Rehearsed
  2026-09-29 on ONE verified copy of the live record
  (`rebuild.verified_backup`, 1,086,259,200 bytes, integrity ok, 63 tables,
  1,296,172 rows, nothing mismatched): db.init added exactly the table and
  its automatic index, each byte for byte a fresh build's; no table's count
  or column checksums moved (62 tables, 1,296,159 rows); the sequence
  unchanged; 0 differences from a fresh build of the tree (9 cosmetic, as
  before); a second db.init changed nothing. The copy and the fresh build
  were deleted by the script (`scratchpad/board/step2/rehearsal.txt`).
  And `board._player_number` reads a record the release has not reached --
  no table -- as no number: three released tests that read the record
  read-only failed on it in the first run of the merged suite.
- **The board's own scans on the live record** (read-only, through
  `db.read_the_live_record`, 2026-09-29): the plain-words scan of the NFL
  slate failed twelve times -- the tooltip carrying a pick's reasons is the
  old Why panel's sentences, built from declared factor phrases, and the
  advice scan read "plays" in "how many plays both offences run" as a verb.
  The board spared that phrase as `factor_words` and not inside a sentence;
  the scan now takes every declared phrase (the registry's `why`) out of the
  text before the advice scan reads the rest. After it: every sport's slate
  passes the badge, plain-words, live-row and live-card scans.
- **The tooltip was unreadable**: its words were `--ink`, the page's own
  colour, on `--card` (contrast 1.07 to 1; found by looking at the render).
  The text colour now, held by the tooltip test at 4.5 to 1.
- **Found by the full run, in its order** (a pick taken on the shared world
  by an earlier test): on a phone a row with YOURS and the checkmark wraps
  its count onto three lines of 11px type at its normal line height, and the
  row's head stood at 265.9375px -- `.game-count` has 16px lines now, and the
  per-view test takes a pick first whatever ran before it; and a taken
  checkmark wears the board's one-shot `pop`, which the browser's motion test
  refused as "not the live pulse" -- it holds `audit.ONE_SHOT_KEYFRAMES` now
  as the stylesheet scan does (once, within 200ms). The pop replays on every
  redraw of a taken mark, not only when it is taken (the board's; left).
- **The Record page's words** paint no version name (question 19): the
  blend's and the ordering's are their headings' titles; the correction
  lines say "the correction fitted on Monday 28 September ..." where they
  said "version 8 ..." (Q32's, Q16's and Q31's sentences: the same facts,
  the number in the row's title); Settings says the factor set by its day.
- **The clock.** The board brought 18 fixed waits into the browser tests
  under function names the register did not hold: 8 in its own
  `test_board.py`, and 10 in tests it re-homed and renamed (`test_motion.py`
  1, `test_rapid.py` 5, `test_tabs.py` 4). Each is rebuilt on an in-page
  signal -- the redraw helper with a panel and a count, the rail's verdict
  naming its multiple, the scroll itself, the Record view on screen, the
  slate's request going out -- and the nine entries they replaced are gone
  from `audit.ELAPSED_TIME_HELD` (28 functions and 44 waits to 19 and 27).

### EACH NEW TEST, PROVED ON THE CODE WITHOUT ITS FIX *(scratchpad `board/step2/prove.py`: a copy of the tree, one fix undone, the tests run there)*

- question 18's two tests: both fail with the redraw drawing the row closed
  ("a redraw the reader did not start landed and the row they had opened is
  closed"; "the sort closed the open row");
- the per-frame check with the board's rising arrivals put back: 110
  readings off whole pixels in 426 frames (a row's head at 241.99994px);
- the per-view tap tests with the board's line heights and link: three views
  fail (the link to the workings 17px, a row's head at 245.05px); and with
  the count's line height alone put back, three fail (a row's head at
  265.9375px beside YOURS);
- the live row's chance put back: both live tests fail;
- the board's doors put back (its standing rule, the stored chance, the
  taken split by row number): three tests fail, the badge pin passes;
- the chart drawn before the window: its test fails;
- the tooltip's old colour: its test fails at 1.07 to 1.

### READINGS TAKEN, BY THE CONSERVATIVE DEFAULT *(none breaks LAW 1 or LAW 3 or makes a gate count false: FOLLOWUPS by the queue rule)*

- **What a tap target is**: a control -- every link, button, select, field,
  summary, the label a checkbox is tapped through, and a row's head, which
  opens the row. A number carrying an explanation in a tooltip on hover or
  focus (a chance, a badge, a price) is text that explains itself; it opens
  and changes nothing, and is not counted. Counted, every such number would
  have to stand 44px tall.
- **"Removed"** is read as the board built it: `#/week`, `#/picks`,
  `#/live` and `#/today` render nothing of their own and redirect to Games
  (R4's precedent: an old address lands, never a 404; `audit.nav_faults`
  requires the redirects).
- **The hover lift** is dropped, not only the arrival's rise: on a phone the
  tap that opens a row leaves it hovered, so the row sat a fraction of a
  pixel off whole at rest.
- **Question 19's version names**: the app's own -- every factor set, the
  blend's, the ordering's, a correction's number, and the reconstruction's
  commit. The model's name in the prompt disclosure stays verbatim (a
  provider's name, not a version this app coins), as does the prompt's text.

### NOT SEEN, AND OPEN

- **The version scans' limits**: a version name the renderer paints from a
  field not named `..._version`, and one inside a `.code-literal` block
  (the rendered pages' scan leaves those out, for the prompt's verbatim
  text), are seen by nothing but the browser tests' visible-text scan.
- **A redraw fades the whole slate in again**, the board's design: the took
  button's redraw blinks every row, and a render nobody asked for (none is
  scheduled today) would too; an open row stays open through it. Question
  5's render-finished signal is the place to look.
- **My day's counts** -- CORRECTED BY THE PROVER (2026-09-29, below): two
  taps on two passes of one question are not two chips; the board shows one
  standing block per question per forecaster, so a question tapped on its
  morning pass and standing on its final one shows NOT taken on the rows and
  on My day, and its checkmark can be tapped again (`views.taken_ids` matches
  a tap to the standing row's number, as the released Today card did; the
  Record page's taken comparison matches by `bet.of`). The page disagrees
  with its own Record page about such a question. Not a gate count;
  question 30's class.
- **`calibration.ranker_scorecard`'s `n`** sums every market's count (older
  than the board; not painted).
- **The board's own open ends** stand in `docs/FOLLOWUPS.md` (2026-09-25):
  the csrf test's order dependence, and no test of the My day chip's painted
  fill.

### THE PROVER OF THE MERGE (2026-09-29) -- what got through, and what did not

Each repair behaviour walked through the merged board on real payloads (the
browser suite's world; test_recommend's priced world; every row opened at
390px), before the merge was committed.

GOT THROUGH, FIXED, each with a test, a guard in gate step 2 and a planting:

- **A priced row's numbers were not the card's (GRIDIRON_REPAIR item 3; the
  wrong-side rule of 2026-09-07).** The merge's "a priced chance is the Today
  entry's corrected fair value" read `fair_value` and
  `question_takes_the_proposition` from `views._today_card`'s cards, which
  carried neither, so the branch never ran on a real payload (its test built
  the entry by hand, and `prove.py`'s `doors` variant undid a line that was
  dead anyway). And the board drew the entry's price and payout as they came:
  the claim's fixed proposition's. On test_recommend's world (the away side
  at 57%, a 48.5c home price, a correction in force making the home side
  53.58%) the merged row read "57%", "48c", "2.06x" and wore the clears
  outline, where the old card's chip read 46c against 52c. The card carries
  both numbers now (popped on a live card with the chip), and
  `board._question_block` turns the chance, the price and the payout to the
  side the question names; a priced chance's tooltip is its own sentence,
  not the slate's numbers line, which states the stored figure.
  `audit.board_price_side_faults` holds every upcoming priced block to its
  card: the chip's number, the card's price and payout turned by the card's
  own answer, and a priced card that carries no `fair_value` refused by
  name. `test_board.py::test_a_priced_row_is_its_cards_corrected_number_on_the_side_it_names`,
  `plant.py::plant_a_board_row_priced_off_the_other_side` (three forms: the
  merge's card, the price left on the proposition, the chance left at the
  stored number). On the record today no correction is in force, so the
  chance moves nowhere; the price and payout move on every priced question
  that names the away side or the under.
- **My day counted a taken prop twice.** A prop question is on its game's
  row and is a tile, and `_my_day` read both: one tap, two chips, "2 taken".
  One chip now, marked a prop and wearing its player's club; a chip scrolls
  to its tile on Props and to its game's row where no tile is drawn.
- **A game row's count pooled the forecasters.** "4 questions on this game"
  over three of the model's and one of the reasoning pass's: one figure over
  both under the word "question". Each forecaster's standing questions on
  the game are counted apart on question 17's key (`bet.count`) and said so
  -- "3 questions from the model · 1 from the reasoning pass" -- and the
  payload carries `questions_n` per forecaster.
- **Results' settled heading counted one set and headed another.** The
  Today block's "Settled -- 15 questions" (the page forecaster's shortlisted
  or taken questions on finished games) stood over every question on every
  finished row, both forecasters'. The tiles are the heading's own questions
  again (`board.settled_ids`), restyled, never recounted. Equal on the
  browser world; apart wherever a reasoning pass answered a finished game.
  These three: `audit.board_count_faults`, `test_board.py::test_my_day_counts_a_taken_prop_once`,
  `::test_a_rows_questions_are_counted_for_each_forecaster_apart`,
  `::test_results_settled_tiles_are_the_questions_its_heading_counts`,
  `plant.py::plant_a_board_count_counting_a_bet_twice` (five forms).

WHAT THEY MOVE ON THE RECORD, read through `db.read_the_live_record` on
each sport's current slate (2026-09-29, the fixed code; nothing written, no
copy): NFL week 3 -- Results' heading counts 46 settled questions and the
finished rows hold 100, both forecasters', which the merge drew beneath it;
16 rows carry both forecasters' questions (each said apart now). MLB -- 42
against 72; 14 rows. College football -- 6 priced upcoming questions, 2 of
them naming the other side of the claim's proposition, whose price and
payout the merge drew for the side they do not name; 2 rows. UFC -- 15
priced, none turned; 5 rows. NBA -- no slate. No taken prop on any slate
(My day's double count waits for one). Both new scans pass on every slate,
and gate step 2, dry-run on one verified copy of the record (deleted after),
passes every row, both schema comparisons with no difference in behaviour.

HELD, AND CHECKED: the regrade and withdrawn lines beside the closing line
(each forecaster's); no closing-line point, mean or finding before 15
October (the chart's area says the date); the taken comparison per
forecaster on the key, gated at the hundred; the badge on the edge gate's
door; one recommendation per game and market (a write rule; question 11:
the page need not follow it); corrections through question 32's door and
the "fitted below its gate" words with both counts; the prompt disclosure on
a reasoning tile (its summary measured at 44px at 390 with that row open);
no replacing write (`load_rosters`); arrivals by opacity; an open row open
across every redraw the tests start; no internal version name in visible
text; the clock register 28/44 to 19/27, none grown.

A READING, CORRECTED IN ITS LABEL: "what a tap target is" (above) was
taken BY PRECEDENT, not by the conservative default -- the released
tap-target tests and question 20's per-frame check define a tap target as
what `SLATE_TAP_TARGETS` measures, controls, and "links included" widened
that to every link, which the merge did. The stricter reading would count
every focusable number that shows a tooltip: measured at 390, a tap on a
badge focuses it and shows its tooltip, and on a row's head the same tap
opens the row, whose layout shift hides the tooltip again -- so on a phone
the head's tooltips are unreadable (below). Were they counted, the badge
stands 21px, the chance 18px and the price tick 2px wide.

NOT FIXED, FOUND ON THE WAY (not a gate count, no law):

- **A live score is patched where nobody reads it.** `applyLive` writes the
  live tick's score into `.game-score`, which the stylesheet puts off-screen
  (`left: -9999px`), and never into the team lines' `.tscore`, so a live
  row's visible score stands still until the next render of the slate.
- **A tooltip on a row's head cannot be read on a phone** (above).
- **"Model's pick"** labels the row's pick whichever forecaster the page is
  showing (`?forecaster=llm` included).
- **A prompt disclosure opened inside an open row closes on a redraw**: the
  row stays open (question 18), its `<details>` is a new node.
- **The pick's `payout_words` on the released Today card** were the
  proposition's while its price words were turned (the card is gone; the
  board turns both).
- **"At rest" can read true before a redraw has begun.** `test_smoke.py`'s
  `_AT_REST` (no finite animation running) held on the render before a hash
  change's own redraw, whose rows then arrived at opacity 0 while the probe
  read them: measured at 390, the condition passed with every row and the
  panel at opacity 0 and five transitions running a moment later. The tap
  sizes it guards are layout, and every arrival is opacity alone, so the
  heights read are the heights at rest; the per-frame test covers the frames.
  The merge's own screenshots (`scratchpad/board/step2/shots`) were taken
  mid-arrival -- rows dimmer down the page -- and `tools/board_shots.py`
  waits a fixed 600ms: step 3's captures should wait for the arrival's end
  (question 5's signal is the place).
- **Two vocabularies on one row**: a tile's head says "STATISTICAL" or "LLM"
  (`config.FORECASTER_LABELS`, the Record page picker's labels) while the
  row's count and the Record page's sentences say "the model" and "the
  reasoning pass" (`language.FORECASTER_WORDS`, whose own note calls "LLM"
  an acronym a reader did not ask about).

## The roster's numbers are display only -- built 2026-09-29 *(the operator's ruling of 29 September, given during the board merge; docs/briefs/2026-09-29-player-numbers.md)*

"player_numbers: a loaded roster table, refreshed each load, not
append-only; say so in its description. Plain UPDATE then INSERT is fine. It
is display only: nothing that forecasts, grades, fits or measures may read
it, and a scan refuses any such read." CLAUDE.md's THE ROSTER'S NUMBERS ARE
DISPLAY ONLY row says what the guard is; this is how it was built.

### MEASURED FIRST: WHAT NAMES THE TABLE

Read with the scan's own readers over the package, `tools/` less
`tools/guards/`, and `desktop/`, before anything was written (scratchpad
`fixes/probe_names.py`): seven names in three files and nothing else --
`gridiron/schema.sql` (its declaration), `gridiron/data/loader.py`
(`load_rosters`: the update and the insert; `load_all`: the refresh's tally,
keyed by the table's name, twice) and `gridiron/board.py` (`_player_number`:
the helper asked whether the table exists, and the query). No name partly
worked out at run time could be the table's (three written letters or
more). `db.py` names none: `db.init` makes the table from `schema.sql`.
Tests name it and are not read.

### BUILT

- **The description**, in `schema.sql`'s comment above the table (no word
  there opens a declaration), in `loader.load_rosters`'s docstring, in
  CLAUDE.md's board row and its own row, in the board-merge bullet above
  and in `docs/FOLLOWUPS.md` (2026-09-25, ruling a): a loaded roster from
  nflverse, refreshed at each load, not append-only (a row is the roster as
  last loaded; no rule refuses its update), display only.
- **The write** is the merge's, untouched: an update, then a plain insert
  where no row was updated, one transaction.
- **The scan**, `audit.check_the_roster_numbers_are_display_only` in gate
  step 2 (`audit.roster_numbers_read_faults`): see the CLAUDE.md row. The
  file list is question 15's, now one helper both scans read
  (`audit._shipped_python_files`). An import-time check proves the
  classifier sees what it should (`audit._check_the_roster_scan_can_see`).
  2.8 seconds on this machine.
- **The plantings**, each escaping on 4df9153 (there is no scan, and LAW 1's
  closure scan passes a read of the table in the model) and caught here, by
  function, with nothing else named: three reads in `calibration.py` and one
  in `model/baseline.py`; a read in `views.py` and one inside
  `load_rosters`; and `calibration.py` listed in the allow-list with a
  dated reason, the read and the entry both refused.

### READINGS TAKEN *(none breaks LAW 1 or LAW 3 or makes a gate count false)*

- **"A name the scan cannot place counts as a read"** is read as: a bare
  string holding the name (whatever the code then does with it -- a key, an
  argument to a helper that builds the statement), a name in a string
  literal of a statement, and a name partly worked out at run time whose
  written letters could be the table's. A statement whose table is WHOLLY
  worked out at run time names nothing and is not counted: 32 such places
  in the shipped code (the copy and count helpers in `rebuild`, `db`'s
  migration, `repo.counts`, `tools/dbcopy.py`, and prose the lexer reads as
  SQL words), 17 of them in six modules that may never name the table
  (`db`, `rebuild`, `data/repo`, `data/mlb_repo`, and a sentence each in
  `model/baseline` and `priced/shape`), which the stricter reading would
  have failed with no way to list them.
- **`loader.load_all`'s tally** is listed as a read: its key is the table's
  name, it issues no statement, and the scan cannot tell a key from a read.
  Renaming the key would have changed the refresh's printed report.
- **The db door's init or migration code** is not listed: it needs no name,
  and `db` is in the prediction closure, which may never name the table.
- **The scan's own constant** (`audit.ROSTER_NUMBERS_TABLE`, at module level)
  is listed as a read, not exempted: every other string in `audit.py` is
  built on it, so a read planted in any function of the audit is still
  refused (the precedent, `BETTING_SCAN_EXEMPT`, exempts the whole module).
- **"The ranker"** is `shortlist.py` (`calibration` imports it as `ranker`).

### ITS PROVER (2026-09-29): THE NAME BY ANOTHER NAME

Probed on copies of the package, `tools/` and `desktop/`, one planted read
at a time (scratchpad `fixes/prover/probe_scan.py`). CAUGHT by the scan as
first built: a plain read, a SQL join, a view made at run time, a view, an
index and a rule in the schema, an f-string of constants, a `join` of a
literal list, an upper-case constant lowered, a bytes literal, and a read in
`cli.py`, a tool and `desktop/`. GOT PAST IT, the scan saying nothing:

- **The scan's own constant.** `from gridiron.audit import
  ROSTER_NUMBERS_TABLE as shirts` in the calibration, then
  `f"SELECT * FROM {shirts}"`; and `audit.ROSTER_NUMBERS_TABLE` read off the
  module. The string readers see a part worked out at run time, and the
  constant, allow-listed where it is written, carried the name anywhere.
- **The jersey's own reader.** `from gridiron.board import _player_number`
  in the calibration, or `getattr(board, "_player_number")` in the
  shortlist: the listed function reads the table for whoever calls it.
  (Called by attribute from the resolver it was refused, but only because
  the import put `board` in the prediction closure.)
- **A template filled in with constants.** `"SELECT * FROM {}_{}".format(
  "player", "numbers")` and its `%` twin: the string readers read each
  argument as a part worked out at run time, and no piece carries three
  letters of the name on both sides.
- `loader.load_rosters` called from the calibration (a write, through the
  listed writer).

FIXED, each by name: a value of `audit` holding the name
(`_ROSTER_NAME_HOLDERS`: the constant, the allow-list and the scan's two
patterns; proved complete at import) named anywhere but the scan's own
functions (`_ROSTER_SCAN_ITSELF`, whose entries must be found) -- by name,
attribute, import under any alias or a string that is its name -- is a read
by the function it is in, judged like any other (so a function of the audit
that is not the scan is refused too); a function the allow-list lets name
the table (`_player_number`, `load_rosters`, `load_all`), named in a module
that may never name it, is refused there; and a template filled in with
constants alone (`.format`, `%` with a constant, a tuple or a dict) is read
again whole. A page may still call the jersey's reader. Held by
`plant.py::plant_a_read_of_the_roster_numbers_by_another_name` (seven forms:
the alias, the attribute, the import and the `getattr` of the reader, the
two templates, and the constant in an audit function that is not the scan;
ESCAPED on 4df9153 -- no scan -- and on the scan as first built, "the scan
said []"; CAUGHT here) and
`test_board.py::test_the_roster_scan_sees_the_name_by_another_name` (fails
on both, passes here).

### NOT SEEN, AND OPEN

- A name read from the record (`sqlite_master`, a `LIKE 'player_n%'`
  pattern), a file or the environment, or built where the scan renders no
  string of it (a list joined at run time, a slice, a reversal, character
  codes, a docstring handed over through `__doc__`, a `string.Template`
  filled in by `substitute`). The copy, count and migration helpers take
  every table's name that way. Measured by the prover: a list joined at run
  time, a reversal, a docstring handed over and a `LIKE` pattern read from
  the record each still get past.
- A read through a function the allow-list does not name that calls one it
  does -- a measuring module calling a page's function that draws the
  jersey. An import is no sign (nine of the thirteen places that may never
  name the table reach `board` and the loader by import -- the calibration
  through `audit` and `views` -- measured by the prover,
  `fixes/prover/probe_reach.py`), and the scan does not read the call
  graph.
- `tools/guards/` is not read, as the brief rules.
- A query of the record's own catalogue for the table's columns
  (`PRAGMA table_info` over every table) names no table and is not read.
- The browser's files are not read: they issue no SQL, and the payload's
  `number` is the display.

## The board merge, step 3: every difference from the fixture captures (2026-09-29)

The board-merge checklist's step 3 captured Games, Props, My day, one game
expanded, Record, Results, Settings, the updating state, the first-load
placeholder and the empty states from ONE verified copy of the live record
(deleted after), and a test world with a game in progress, at 1300px and
390px, and listed every difference from the fixture captures (scratchpad
`board_captures_digest.txt`; the captures in `board/captures/shots/`). Each
is below as the step tagged it -- **data**, **repair behaviour kept**, or
**DEFECT**. The three tap-target defects are **FIXED** here, each with a
test that fails on 4df9153 and passes on the fix. **Everything else is OPEN
for the re-read, under the queue rule.**

### FIRST: THE NCAAF WRONG SIDE -- OPEN, NOT FIXED HERE; IT WAITS FOR THE OPERATOR (reported to them now)

**RULED AND BUILT 2026-09-30** (the operator's rulings of 30 September): see
"The side is placed in one place, and a side it cannot place is refused",
at the end of this file, for the fix and the list of every past
recommendation and card shown with the wrong side's numbers.

In the step's own words: **WRONG SIDE on a live, sized, green-outlined
recommendation (NCAAF, UNT at TLSA, Thursday 1 October): the board reads
'North Texas -6.5 · 24% · 48¢ · 2.06x', but the record's numbers for that
side are 76% and about 51.5¢.** The one clearing, sized row of the college
slate, under the green outline with '$15 · one flat unit'; the record's own
numbers for North Texas -6.5 are 76% (recommendation 111, side 'no', fair
value 0.2398 for 'TLSA covers +6.5') and about 51.5¢ (1.94x). **Cause: 93
NCAAF spread predictions store `model_side` 'fail to cover'** (every other
sport stores 'not_cover'). `priced/shape.py::blind_probability`
(home_margin) has no rule for that side, so `question_takes_the_proposition`
is None; `views._today_card` and `board._question_block` turn only on
`is False`, and `audit.board_price_side_faults` (also `is False`) passes the
block. Recommendations 88, 90, 104 and 111 sit on such rows. The released
Today card already has the same wrong-side price; the board adds a chance in
% beside the wrong side. The step routed it to FOLLOWUPS by the queue rule
(not LAW 1 or LAW 3) and flagged it before step 4 (release), since the
operator wagers from this page.

### EVERY DIFFERENCE, AS THE STEP TAGGED IT

1. Every capture: no 'BACKTEST DATABASE' banner, because the copy's meta kind
   is live. **data**
2. Every capture: the sport tabs carry the record's season records (NFL
   193-119, MLB 832-640, NBA 0 settled, NCAAF 577-195, UFC 184-162) where the
   fixture had 25-7 and 0. At 390 the counts run into the next tab's label
   ('193-119MLB', '577-195UFC'), measured 1-3px of overlap. **DEFECT exposed
   by the data: the tab's content is wider than the tab.** OPEN.
3. Every capture: the pulse reads 'daily run 22h ago · venue read 2-3h ago ·
   reasoning pass 25h ago' in plain ink where the fixture had bold 'has
   never run'. Nothing is past its threshold. **data**
4. Every capture: My day reads 'Nothing taken on this slate yet.' in every
   sport. **data** (the record's only taken row is a package from
   2026-09-08, on no slate)
5. Every capture: the footer reads '3,152 predictions on record · 22,255
   completed games loaded (2016-2026) · market comparison for 156 of 427'.
   **data**
6. app-games: the slate is 'WEEK 3, 2026', 16 games all FINAL with scores and
   won/lost fills; the fixture had Week 18, 2025, four upcoming games (NFL
   week 4 is loaded with 16 games and 0 forecasts). The day line reads
   'MONDAY 28 SEPTEMBER · NFL' where the fixture had 'NFL'; the counts read
   'the model has 13 picks that clear the bar · 33 questions watched · 55
   settled'; the fee line reads 'At today's median venue price of 50¢...'.
   **data**
7. app-games: club bands carry full names ('ATLANTA FALCONS') where the
   fixture repeated the code ('GB GB') -- **data**. Washington and the Rams
   have no name ('WAS WAS', 'LA LA'), and a combo reads 'WAS covers +7.5'
   beside 'Philadelphia covers +15.5': **DEFECT, pre-existing:
   `language.team_name` has no name for nflverse's WAS and LA.** OPEN.
8. app-games: each row's count reads '4 questions from the model · 3 from the
   reasoning pass' where the fixture had '4 questions on this game' --
   **repair behaviour the merge kept** (Q22 per forecaster, the prover's
   `board_count_faults`). Record badges are 32/100 and 18/100; a settled row
   has no take box, only a small hollow circle, as in the fixture's
   settled-games. **data**
9. app-games, empty-clears-games, updating-games: the NFL combos panel
   proposes three combos, each with '$7.50 · half a flat unit' and 'worth
   taking only below 16¢/10¢/15¢', and every leg is on a FINAL game (LV-NO,
   CIN-PIT, PHI-CHI, SEA-WAS, MIN-TB, ATL-GB); the fixture had 'no two NFL
   picks clear the bar today'. **DEFECT, pre-existing server behaviour: the
   Today block builds its combos from `clears`, which on a finished slate are
   settled picks; the old Picks panel rendered the same `today.combos` and
   the merge re-homed it.** OPEN. The card title also joins its legs with no
   space: 'Las Vegas covers +15.5+Pittsburgh covers +7.5'. **DEFECT,
   rendering.** OPEN.
10. app-games: the footer strip reads 'Yesterday: 7 right, 3 wrong · NFL
    193-119' where the fixture had 'Today: 25 right, 7 wrong'. **data**
11. expanded-games: the detail shows 'LAST FIVE' in the form ink, 'INJURIES +
    8', the weather sentence and a different factor list; 'Every bet on this
    game' has 4 model tiles and 3 reasoning-pass tiles, all won/lost fills,
    where the fixture had 4 upcoming model tiles. **data**
12. expanded-games, expanded-mlb, settled-games: on a filled (won/lost) tile
    the forecaster word ('STATISTICAL', 'LLM') and the reasoning tile's prompt
    summary ('The prompt, reconstructed ▾' / 'The prompt it was sent ▾') are
    drawn in a faint ink on the green or red fill and are barely legible.
    **DEFECT, contrast**: the faint 'STATISTICAL' is also on the fixture's
    settled-games; the summary on a fill is new, the fixture having no
    reasoning tile. The summary is a tap target, and its size passes. OPEN.
13. expanded-*: reasoning-pass tiles are labelled 'LLM'
    (`config.FORECASTER_LABELS`) while the row and the Record page say
    'reasoning pass'. **Pre-existing label**, first shown on a board tile
    here; a plain-words inconsistency. OPEN (the merge's "Two vocabularies
    on one row", above).
14. expanded-*: the 'How the model works' link measures at least 44px at 390.
    **repair behaviour** (the merge fixed Q20's side question).
15. app-props: 9 settled tiles on real players (Baker Mayfield, Bijan
    Robinson, ...) with names on the jersey backs and NO jersey numbers; the
    fixture had 3 upcoming tiles numbered 80, 81 and 10. **data**:
    `player_numbers` has 0 rows on the record (`db.init` just made it and no
    roster load has run); display only per the 2026-09-29 brief. Settled tiles
    have no take box. **data**
16. app-props, props-mlb at 1300: the tile's name column breaks names
    mid-word ('BAKE R MAYF IELD', 'CHRI S OLAV E', 'MICH AEL BUSC H').
    **DEFECT**: present in the fixture as 'RECE IVER' and 'QUAR TERB ACK',
    worse on real names; at 390 the names fit. OPEN.
17. props-mlb: Zack Wheeler's jersey is drawn in the neutral grey -- **data**
    (the prop's club colours are unknown for that tile). The entry rail says
    'Tap a tile to mark it taken' on a finished slate with no tile to tap --
    **minor wording**. OPEN.
18. app-record: headings read 'Priced, and against the close' and 'Did the
    ordering earn its place'; the fixture had '... b1' and '... r3'. **repair
    behaviour: Q19**
19. app-record: per-forecaster lines ('A correction for moneyline, reasoning
    pass' where the fixture said '..., LLM'; 'player props, every prop type
    together'); NFL point spread's 'fitted below its gate' line (Q31); 'not in
    force ... by a dated row of its own' (Q32); the 'Since the repair,
    statistical / reasoning pass' window lines, and closing-line chart panels
    reading 'N of 50 · nothing is drawn before Thursday 15 October' (item 8,
    Q22); 'Withdrawn, statistical'; 'Taken, passed over, every forecast'
    headings that name the forecaster. **repair behaviour the merge kept, all
    present**
20. record-mlb: 'Would not have cleared, statistical: 2 recommendations ...
    3.34% and 4.97%' is present (item 4/Q9); so are the per-forecaster MLB
    total lines with repeats counted once, and there is no 'Both sides, no
    position' row (Q22). **repair behaviour kept**
21. app-record: 'What the record has taught it 2026-09-28' now carries a date,
    because a fit exists -- **data**. Factor set versions has four sets, and
    at 1300 each set's table clips its 'HIT RATE' column ('HIT RAT', '43.8'
    cut off): **DEFECT, layout, exposed by the data** (the fixture's three
    sets fit). OPEN. The code names under each factor card and 'At the
    venue's line kalshi' are the same as the fixture. **pre-existing** OPEN.
22. app-results: the page opens with 'Settled — 46 questions' and board
    tiles, then 'The season so far 312 settled over 8 days' calendar, then the
    table; the fixture had the table only, and its world drew no calendar --
    **merge, plus data**. At 390 each calendar day button is 48.296875px:
    **TAP-TARGET DEFECT -- FIXED** (below).
23. app-settings: Health shows the real task runs, 'Predict MLB is recorded
    as 11:00 here, but the scheduler holds 22:00' (the view read the
    machine's scheduler, read-only) and a unit of 15 -- **data**. The access
    token reads 'smok...uite (33 characters)', the test server's SMOKE_TOKEN
    -- **expected**. 'Default forecaster: whose questions Picks shows' names
    the Picks page that leaves in this release: **DEFECT in the words,
    pre-existing in the fixture, stale after the release.** OPEN.
24. empty-games and empty-props (NBA): 'The NBA season starts on 2026-10-20,
    21 days from now. 1,200 games are loaded and waiting...' and 'Next NBA
    games on 2026-10-20 at 19:00 UTC', where the fixture said the schedule was
    not published -- **data** (the NBA schedule is loaded). There is an ISO
    date and a UTC clock in the prose -- **pre-existing server words**. OPEN.
    empty-props matches the fixture apart from the header and footer.
25. empty-clears-games (no fixture counterpart): with 'clears the bar only'
    on the finished NFL slate, 0 rows and an EMPTY dashed box with no words,
    directly under 'the model has 13 picks that clear the bar'. **DEFECT,
    board**: the filter keys on signal 'clears', which settled picks never
    carry; `nothing_clears_words` is None on an unpriced finished slate and
    the fallback words are None, so the box is blank. OPEN.
26. empty-props-family (no fixture counterpart): 'No alt lines: a venue's
    alternate lines are not read yet, so there is nothing here to rank.'
    **works as built**
27. updating-games and updating-props (no fixture counterpart): the old rows
    and tiles stay at opacity 0.45 with pointer-events none, aria-busy true,
    and an 'UPDATING' label above them; the market select already shows the
    new choice; the props chips still show ALL pressed until the answer
    arrives. **matches the 2026-09-25 ruling**
28. loading-games and loading-props (no fixture counterpart): 'Loading
    today's games/props' is static, with no animation and no spinner. But
    before the first answer the controls bar draws an EMPTY sort select
    (40x44px, under 44 wide), unlabelled sort and market controls and an
    unlabelled checkbox; Props draws an empty entry-rail card with an
    unlabelled number field; the pulse and My day are hidden. **DEFECT: a tap
    target under 44 and unlabelled controls -- FIXED** (below).
29. settled-games: the adjacent week is Week 2, 2026, with one game (NYG at
    LA) and 4 predictions; the fixture had week 7, 2025 with four games --
    **data**. The greeting reads 'Next NFL games on 2026-10-02 at 00:15 UTC'
    -- **data; ISO date in the words**. OPEN.
30. games-mlb (no fixture counterpart): a finished 14-game slate. Badges past
    the gate read '202/100', '213/100', '260/100'. **data; the badge keeps
    its n/100 form past 100.** OPEN.
31. games-cfb and expanded-cfb (no fixture counterpart): the one clearing,
    sized row, UNT at TLSA -- **the WRONG-SIDE DEFECT at the top of this
    section, OPEN, waiting for the operator**. Moneyline tiles also show a
    price and a payout beside 'no price to compare against yet': **a
    contradiction in the words; data: a quote with no claim.** OPEN.
32. games-ufc and expanded-ufc (no fixture counterpart): fighter names sit in
    the narrow club-code cell and overflow into the name band ('Opponent TBA',
    'Zaurbek Sabanov', 'Erick Visconde') at both widths: **DEFECT, layout,
    exposed by the data** (the fixture had no UFC slate). OPEN. One bout
    reads 'OPPONENT TBA / TBA'. **data**
33. myday-testworld, games-testworld, props-testworld (TEST WORLD, the
    fixture's live-* shape): two chips, 'KC TO WIN · UPCOMING · 7/100' and
    'DAL RECEIVER OVER 40.5 RECEIVING YARDS · UPCOMING · 5/100', and '2
    taken'; the fixture showed the taken prop twice and '3 taken' -- **repair
    behaviour: the merge prover's one-chip-per-question fix**. At 390 the live
    row's head is 277.140625px tall: **TAP-TARGET DEFECT -- FIXED** (below).

### THE STEP'S DEFECT LIST, AND WHERE EACH STANDS

- **TAP TARGET, Results at 390 -- FIXED.** The calendar's day buttons were
  48.296875 x 48.296875px on the test's phone (45.859375 at one device
  pixel), off whole pixels: `.cal` (`repeat(7, 1fr)`) with `.day` at
  `aspect-ratio: 1`. The fixture world draws no calendar, which is why the
  per-view test passed. The columns are whole pixels now -- 50px, and 44px
  at 430px and under (seven of 50 with their gaps would run past a 375px
  screen). Measured at 390 (3x): every day 44 x 44; at 1100: 50 x 50; no
  sideways scroll at 431 with a scrollbar, 403, 375 or 360.
  `test_smoke.py::test_every_tap_target_on_the_views_the_fixture_world_never_drew_is_44px_at_rest[results, its calendar drawn]`
  -- on 4df9153: "2 tap targets ... button.day.has-result.up "12-3" is
  48.296875 x 48.296875px"; passes on the fix.
- **TAP TARGET, the first-load placeholder -- FIXED.** `select#games-sort`
  and `select#props-sort` were 40 x 44px (no options until `fillSelect` ran
  after the first answer), beside unlabelled sort and market controls, an
  unlabelled checkbox and, on Props, an unlabelled number field. CHOSEN: the
  controls are not drawn until they can act, rather than a 44px minimum on
  an empty select -- the plain choice the first-load ruling's words support
  ("before any slate answer exists the page says so in words ... the first
  answer replaces it"): the Games and Props control bars and the entry rail
  are `hidden` in the page's own file and shown by `renderGames`,
  `renderProps` and `renderEntryRail` once the server's options and label
  words are in them, so each control is drawn with a name a screen reader
  reads (the label's words; checked in the browser's accessibility tree).
  `test_smoke.py::test_the_first_load_placeholder_draws_no_control_it_cannot_act_with[games]`
  and `[props]`, the slate's request held with `page.route` and read once it
  is out (no fixed wait) -- on 4df9153: "select#games-sort is 40 x 44px ...
  3 controls a screen reader reads as nothing: a combobox, select#games-sort
  / a combobox, select#week-market / a checkbox, input#games-clears", and on
  Props "select#props-sort is 40 x 44px ... a combobox, select#props-sort /
  a spinbutton, input#entry-pays"; pass on the fix, and the controls are
  there and named once the answer lands.
- **TAP TARGET, a live row at 390 (test world) -- FIXED.** `.game-head` was
  360 x 277.140625px: the status column (LIVE at 11px on the normal line
  height, '3rd Quarter · 8:41' at 18px on a line height of 1.1, 'read just
  now' at 11px) wraps in its 78px column and is the tallest thing in the
  head's first line. Every line in the column has a whole-pixel line height
  now (20px and 16px; the type unchanged); the head measures 360 x 278.
  `test_smoke.py::test_every_tap_target_on_the_views_the_fixture_world_never_drew_is_44px_at_rest[games, a game in progress]`
  and `[games, a game in progress, its row open]`, on a copy of the browser
  world in play (every game on its league day, the unplayed slate's first
  game in progress, the score's read time the world's own latest forecast's:
  no clock read) -- on 4df9153: "div.game-head ... is 360 x 277.140625px";
  pass on the fix.
- **WRONG SIDE (NCAAF)** -- OPEN, at the top of this section; waits for the
  operator.
- **Combos proposed and sized on FINAL legs** (NFL week 3), and combo titles
  joining their legs with no space ('+15.5+Pittsburgh') -- OPEN (item 9).
- **'Clears the bar only' on a finished slate** draws 0 rows and an empty
  dashed box under '13 picks that clear the bar' -- OPEN (item 25).
- **Sport tabs at 390**: the record's counts overflow each tab into the next
  label -- OPEN (item 2).
- **UFC rows**: fighter names overflow the club-code cell at both widths --
  OPEN (item 32).
- **Faint forecaster words and prompt summaries on won/lost filled tiles**
  (the summary is a tap target) -- OPEN (item 12).
- **Factor set version tables clip HIT RATE at 1300** with four sets -- OPEN
  (item 21).
- **Prop tile names break mid-word at 1300** (pre-existing in the fixture) --
  OPEN (item 16).
- **Washington (WAS) and the Rams (LA) have no club name** -- OPEN (item 7).
- **Settings still says 'whose questions Picks shows'** -- OPEN (item 23).

The step's own record, kept: the repair behaviour the merge had to keep was
all present in the captures (the re-grade line; the closing-line window --
no mean or chart before 15 October; per-forecaster, per-distinct-bet counts
with no 'Both sides' row; the 'fitted below its gate' label and Q32's
in-force wording; plain headings, no b1 or r3; one chip per taken question;
the prompt disclosure on reasoning tiles; the updating and first-load states
as ruled on 2026-09-25). Its one copy of the record (1,086,259,200 bytes, the
verified backup of 2026-09-29) and its two test worlds were deleted; no
network, no real token, the live app on 8848 never contacted; the Settings
view read the machine's Task Scheduler, read-only.

### RE-MEASURED AFTER THE FIXES: EVERY BOARD VIEW AT 390 AT REST

At 390px, three device pixels to one, links included, every tap target 44px
or more tall in whole pixels and 44px or more wide: the eight views of
`test_every_tap_target_on_every_board_view_is_44px_at_rest` (games; a row
open; every row open; props; record; results; settings; the menu), the
three in play (Results with its calendar; a game in progress, shut and
open), and the two placeholders -- thirteen views, all whole and 44 or more
(the tap-target tests, the per-frame arrival check and the five no-overflow
routes: 20 passed, 2026-09-29).

AND BY ITS PROVER (2026-09-29), EVERY VIEW THE CAPTURES SHOT, on ONE
verified copy of the live record (`rebuild.verified_backup`, 1,086,455,808
bytes, integrity ok, 63 tables, nothing mismatched; deleted after) and on
the board's own test world with a game in progress (`tools/board_shots.py`,
every game on its league day so Results draws its calendar; deleted after),
at 390px, three device pixels to one, mobile and touch, with the suite's
own selector and measure (scratchpad `fixes/prover/measure_all.py`): for
every sport, Games, a row open, the live row open, every row open, every
row open with every disclosure open (the reasoning tiles' prompts), the
week picker open, Props and each of its family chips, Record and Record
with every disclosure open, Results with its calendar and with every
disclosure open; and 'clears the bar only', the adjacent settled week with
a row open, Settings, the menu, both first-load placeholders (the slate's
request held) and both updating states (held; not at rest, measured
anyway). 137 views, 3,749 readings: every tap target on every board view
44px or more tall in whole pixels and 44px or more wide, no page wider than
the screen. The five new browser tests fail on 4df9153 as reported and
pass here (22 passed with the tap, overflow and tab tests).

### FOUND ON THE WAY *(not a gate count, no law: FOLLOWUPS by the queue rule)*

- **Below 360px the calendar runs past the panel.** Seven squares of 44 and
  their gaps are 332px; at 320 the panel is 292px and the page scrolls
  sideways by 26-27px. So it did before the fix, in any season with a
  settled day in every column: the global `button { min-height: 44px }`,
  carried across each day's square by its aspect ratio, already held every
  column that holds a button at 44 (measured with the old columns put back
  at 320: the same 44px columns, the same overflow). A calendar that fits
  under 360px needs smaller squares, which the 44px floor forbids, or a
  calendar that scrolls inside itself.
- **At 1100px the header's sport tabs are 48.1875px tall, the week picker's
  summary 18.84375px and the colophon's links 15px**; the rule is 390px,
  where all three pass. Not a defect under the
  rule; recorded because a desk reader clicks them too.
- **The sign-in page's token field is 340 x 43px at 390** (three device
  pixels to one; measured by the prover, 2026-09-29): `.signin input` in
  `login.html` is 11px of padding each side of 15px type with no
  `min-height`, where its button has `min-height: 44px`. The sign-in page is
  not a board view, the captures did not shoot it and the merge did not
  touch it (last changed in "prog 6: entry"), so it is here under the queue
  rule, not fixed: a `min-height: 44px` on the field is the likely fix, for
  the re-read.

## The side is placed in one place, and a side it cannot place is refused -- built 2026-09-30 *(the operator's ruling of 30 September on rec 111 / the NCAAF wrong side; docs/briefs/2026-09-30-rulings.md)*

"Rec 111 / NCAAF wrong side: fix it, now, own commit and gate, released before
2 October 01:00Z. Read 'fail to cover' as the no side in the one place the
side is worked out; the page and the check refuse any side they can't place
instead of passing it; planting. List every past rec shown with the wrong
side's numbers." Built on `repair` at 8121a9a (whose code is the released
cb8c7da), uncommitted for the prover.

### MEASURED FIRST *(read-only: `db.read_the_live_record` for the spellings, 2026-09-30 ~03:40Z, `scratchpad/wrongside/measure_spellings.py` -> `spellings.json`; then ONE verified copy of the record through `rebuild.verified_backup`, 2026-09-30T03:41:45Z, integrity ok, 64 tables, nothing mismatched, read with `db.read_only` by the released code -- a `git archive` of 8121a9a in `scratchpad/wrongside/head/` -- and deleted after)*

**Every stored side, per sport and market** (both forecasters): spread
`cover` / `not_cover` (MLB, NBA, NFL) and `cover` / `fail to cover` (NCAAF:
93 rows, 65 statistical and 28 reasoning pass); moneyline `win` / `lose`
(every sport, UFC included); total `over` / `under`; prop `over` / `under`
(MLB, NFL); UFC rounds `over` / `under`, UFC distance `yes` / `no`. No other
spelling is on the record. Totals store `under`, moneylines `lose`: both
were placed by the released numbers. The sports declare the same labels on
their questions (`Question(yes_label=..., no_label=...)`, 36 of them, read
from the source), and college football's spread is the only one declaring
`fail to cover`.

**What the released code could place** (`priced.shape.
question_takes_the_proposition`, every forecast on the record): every
spelling except `fail to cover` (all 93 NCAAF rows, 26 of them priced) and
the UFC rounds and distance questions (224 rows, none ever priced: the
recommendation engine declares no quantity for those markets, so no claim,
no price and no number from a claim is ever drawn for them -- they stay
unplaced and are refused only if a number would be drawn). Every
recommendation's side: 4 unplaced (88, 90, 104, 111, all NCAAF `fail to
cover`); 109 placed.

**Every place that decided which side a question takes**, each on its own
rule until this build:

1. `priced.shape.blind_probability` -- THE NUMBERS: the claim writer's
   line-less and rung-matched claims, `question_takes_the_proposition`, and
   through it every turn the page made. Listed `cover`/`not_cover`,
   `win`/`lose`, `over`/`under`; anything else None. This is the one the
   ruling names, and the hole.
2. `language.is_no_side` (through `subjects.YES_SIDE`) -- THE WORDS: any
   spelling but the yes one is the no side. So the words named North Texas
   while the numbers were Tulsa's.
3. `language`'s own composers: totals and rounds said "over" for anything
   but `under`; the distance phrase listed `no`, `under`, `not_cover` as the
   no side; the moneyline phrases and clauses tested `== "lose"`.
4. The resolvers: `resolve.resolve_nfl_outcome` (`== "over"/"win"/"cover"`),
   `sports/mlb.py` and `sports/nba.py` (the same), `sports/cfb.py` (its own
   dict of yes spellings) -- all "anything but the yes spelling is the no
   side" -- and the fight resolver in `resolve.py`, which listed `lose`,
   `under`, `no`, `not_cover` and graded ANY OTHER spelling as the YES side:
   the opposite default. Right on every stored spelling; two defaults
   pointing opposite ways on the next one.
5. `market/lines.py`'s snapshot (the book's implied probability for the
   model's side; `== "win"/"over"/"cover"`), and its prop quote's other side.
6. `calibration.factor_report`'s `outcome_yes` -- compares with the
   forecast's OWN stored `yes_label`, no table of its own (left as it is:
   it reads the question's declaration, not a spelling list).
7. `tools/diagnose.py`'s "which side the model took" buckets:
   `== "not_cover"`, which left `fail to cover` out.
8. `language.WHY_YES_SIDE`: a second literal of the yes spellings (unused
   beyond its definition).
9. The page's own turns: `views._today_card`, `views._favours_home`,
   `views._edge_side_words`, `views._opening_price`'s `flip`, the live
   card's pregame figure, and `board._question_block` -- all on
   `question_takes_the_proposition is False`; and the gate's
   `audit.board_price_side_faults` on the same `is False`.

Readers that do NOT decide a question's side (checked, left alone): the
recommendation's own `side` ('yes'/'no' on the claim's proposition:
`recommend.side_for`, `clv_cents`, `close_of`, `_cost_of`), the package legs
(`views._leg_reading`, oriented by the club the venue's leg names), the
at-the-line sentence (it names the proposition itself), the renderer
(`app.js` prints the stored side's name in one chip and decides nothing).

**The claim writer never refused a claim for want of a side**: every look at
the 93 college `fail to cover` forecasts was a rung-differs margin claim
(101 looks), which reads the frozen distribution and never asks the side;
none was rung-matched (`measure_claims.py`). So no count of the at-the-line
record moved, and from this build a rung-matched look at one would be
claimed rather than refused.

### THE LIST: EVERY PAST RECOMMENDATION (AND EVERY CARD) SHOWN WITH THE WRONG SIDE'S NUMBERS

Reconstructed by running the RELEASED builders (`recommend.for_predictions`,
`views._today_card`, `board._question_block`, `combos.propose`,
`views._pregame_probability`, `views.week`) on the verified copy, and from
each recommendation's own stored row and every claim written before the
start (`measure_list.py` -> `list.json`, `measure_live.py` -> `live.json`,
`measure_open.py` -> `open.json`, `measure_combos.py` -> `combos.json`). No
correction was ever in force at any of these stamps, so each chance is the
raw claim. "Should" is the same number on the side the question names: one
minus the chance, one minus the price, and the payout of that price. The
record cannot say which of these the operator had open; each is what the
page drew whenever it was open then. None of these rows was taken (the
record's only tap is a 2026-09-08 package).

**A. The priced rows of the four recommendations the released code could not
place** (NCAAF `fail to cover`; statistical; each one flat unit, $15, "measured
and NOT ahead"). The recommendation's own side was stored correctly every
time (the no side of the question as asked), and its close and CLV are on
that stored side, unaffected.

- **rec 88** -- forecast 2478, ARMY at TEM, 2026-09-25 20:00Z, "Army covers
  +0.5". Drawn 43% (chip 43¢), 48.5¢ (48¢), pays 2.06x; should be 57%,
  51.5¢ (52¢), 1.94x. Two looks, 19:33 and 19:35Z, on the old Today card.
  Settled: WON (Army 21 - 17). Close 48.5¢, CLV 0.0¢.
- **rec 90** -- forecast 2490, NAVY at UAB, 2026-09-25 23:00Z, "Navy covers
  -6.5". Drawn 20%, 49.5¢ (50¢), 2.02x; should be 80%, 50.5¢ (50¢), 1.98x.
  Six looks, 19:33 to 22:35Z, the old Today card. Settled: LOST (Navy 20 -
  24). Close 49.5¢, CLV 0.0¢.
- **rec 104** -- forecast 2874, TA&M at LSU, 2026-09-26 23:30Z, "Texas A&M
  covers +0.5". Drawn 27%, 48.5¢ then 49.5¢ (48¢, 50¢), 2.06x then 2.02x;
  should be 73%, 51.5¢ then 50.5¢, 1.94x then 1.98x. Five looks, 16:17 to
  23:05Z, the old Today card. Settled: LOST (TA&M 6 - 35). Close 49.5¢,
  CLV -1.0¢.
- **rec 111** -- forecast 3115 (the early pass), UNT at TLSA, 2026-10-02
  01:00Z, "North Texas covers -6.5". At its write (2026-09-27 16:00Z) and
  while that pass stood: 24%, 49.5¢ (50¢), 2.02x; should be 76%, 50.5¢,
  1.98x. From 2026-09-28 15:00Z its final pass, forecast 3147, stands on the
  slate (the recommendation stays on 3115 -- one per game and market) and is
  the row's pick: 24% (chip 24¢), 48.5¢ (48¢), 2.06x, "$15 · one flat unit"
  under the green outline; should be 76%, 51.5¢ (52¢), 1.94x -- on the old
  Today card until the board's release (2026-09-29 19:09Z), on the board
  since ("North Texas -6.5 · 24% · 48¢ · 2.06x", the step-3 capture). NOT
  SETTLED; the game is 2 October 01:00Z. After this build, on the same copy:
  "North Texas covers -6.5 · 76% · 52¢ · 1.94x", the check passing.

**B. The live rows' pregame figure -- every card whose question names the
claim's other side, not only college football's** (found by this build; the
refusal could not ship without it). A live card is built from an entry that
carries no side at all, so `flip` was never True on a live card, and from
the pregame figure's release (fb6dcdf, 2026-09-09 21:36Z) every live row --
the old Live tab, then the board's live rows -- whose question names the
claim's other side showed the PROPOSITION's pregame chance. Proved on the
released code: "BBB to win" beside "pregame 43%" where the forecast's own
side is 57% (`test_the_side_is_placed.py::test_a_live_cards_pregame_figure_
is_on_the_side_its_question_names` fails on 8121a9a). 116 cards on 13
slates, 57 of them recommendations, from 2026-09-09 22:35Z to 2026-09-29
00:15Z (each forecaster's standing shortlisted cards with a claim, on games
that started after fb6dcdf; the release that carried fb6dcdf may have come
after the first of these). The numbers are the claim's, read at the venue's
line; the recommendation's own side and price were never touched by this.
Where the venue's line is not the question's rung (the NFL and NCAAF
spreads: rec 67's "Atlanta covers +15.5" beside a figure about Atlanta at
the venue's own number), neither figure is the question's own chance: that
is pick-number finding 2, below, and not this list.


**C. The opening read on an unplaced side** (reasoning pass, the Watching
group, no price at the line yet). A card with no price at the line shows the
venue's latest opening read, turned on `is False` alone, so on a `fail to
cover` question it was the proposition's opening price and payout:

- forecast 3148 (UNT at TLSA, final pass, "North Texas covers -6.5"): from
  2026-09-28 15:00Z, 51¢ · pays 1.96x (the 05:11Z read), then 48.5¢ · 2.06x
  (the reads of 09-28 21:12Z and 09-29 13:12Z); should be 49¢ · 2.04x, then
  51.5¢ · 1.94x. On the old Today card until 2026-09-29 19:09Z; since the
  board, only in the payout's tooltip ("2.06 times"), the row reading "venue
  has not listed this yet".
- forecast 2503 (CLEM at CAL, "Clemson covers -6.5"): 50.5¢ · 1.98x from
  2026-09-25 21:01Z to the start; should be 49.5¢ · 2.02x.
- forecast 2917 (TLSA at ARK, "Tulsa covers +14.5"): 53.5¢ · 1.87x from
  2026-09-26 17:01Z to the start; should be 46.5¢ · 2.15x.
- forecast 2923 (FAU at ULM, "Florida Atlantic covers -6.5"): 50.5¢ · 1.98x
  from 2026-09-26 17:01Z to the start; should be 49.5¢ · 2.02x.

**D. The combos panel** (statistical, NCAAF), three proposals built on recs
88, 90 and 104: "Rutgers covers -24.5 + Navy covers -6.5" worth 2.3%, "pay
below 1¢" (the recommended sides' product is 71.1%); "California covers
+6.5 + Army covers +0.5" 14.3%, below 12¢ (38.0%); "Florida International
covers -14.5 + Texas A&M covers +0.5" 3.8%, below 2¢ (62.8%). Each number is
wrong for a reason beyond this ruling -- a proposal multiplies every leg's
yes-side number whatever side its recommendation is on (the pick-number
findings below) -- and the unplaced legs are refused by the page now.

THE FULL LIST OF B, each card with what the live row showed and should have:

RECOMMENDATIONS (57):

- rec 25 (forecast 1530), MLB CLE at BAL, 2026-09-09T22:35Z, "Cleveland covers +1.5" [not_cover]: live pregame 36%, should be 64%; lost
- rec 26 (forecast 1535), MLB HOU at PHI, 2026-09-09T22:40Z, "Houston covers +1.5" [not_cover]: live pregame 35%, should be 65%; lost
- rec 27 (forecast 1545), MLB LAA at BOS, 2026-09-09T22:45Z, "Los Angeles covers +1.5" [not_cover]: live pregame 37%, should be 63%; won
- rec 28 (forecast 1567, reasoning pass), MLB AZ at KC, 2026-09-09T23:40Z, "under 8.5 total runs" [under]: live pregame 38%, should be 62%; won
- rec 29 (forecast 1572, reasoning pass), MLB PIT at CWS, 2026-09-09T23:40Z, "under 8.5 total runs" [under]: live pregame 41%, should be 59%; won
- rec 30 (forecast 1581), MLB TB at ATL, 2026-09-10T16:15Z, "Tampa Bay covers +1.5" [not_cover]: live pregame 33%, should be 67%; lost
- rec 31 (forecast 1586), MLB HOU at PHI, 2026-09-10T17:05Z, "Houston covers +1.5" [not_cover]: live pregame 37%, should be 63%; won
- rec 33 (forecast 1658), MLB COL at NYY, 2026-09-10T23:05Z, "Colorado covers +1.5" [not_cover]: live pregame 45%, should be 55%; lost
- rec 34 (forecast 1663), MLB PIT at CWS, 2026-09-10T23:40Z, "Pittsburgh covers +1.5" [not_cover]: live pregame 39%, should be 61%; won
- rec 35 (forecast 1704), MLB KC at BOS, 2026-09-11T23:10Z, "Kansas City covers +1.5" [not_cover]: live pregame 36%, should be 64%; won
- rec 36 (forecast 1706, reasoning pass), MLB KC at BOS, 2026-09-11T23:10Z, "under 8.5 total runs" [under]: live pregame 42%, should be 58%; won
- rec 37 (forecast 1709), MLB PHI at ATL, 2026-09-11T23:15Z, "Philadelphia covers +1.5" [not_cover]: live pregame 36%, should be 64%; won
- rec 38 (forecast 1719), MLB CLE at MIN, 2026-09-12T00:10Z, "Cleveland covers +1.5" [not_cover]: live pregame 33%, should be 67%; won
- rec 39 (forecast 1729), MLB SEA at ATH, 2026-09-12T01:40Z, "Seattle covers +1.5" [not_cover]: live pregame 33%, should be 67%; won
- rec 40 (forecast 1739), MLB SD at SF, 2026-09-12T02:15Z, "San Diego covers +1.5" [not_cover]: live pregame 36%, should be 64%; won
- rec 44 (forecast 1811), MLB TOR at BAL, 2026-09-21T22:35Z, "Toronto covers +1.5" [not_cover]: live pregame 34%, should be 66%; won
- rec 46 (forecast 1816, reasoning pass), MLB TOR at BAL, 2026-09-21T22:35Z, "under 7.5 total runs" [under]: live pregame 43%, should be 57%; won
- rec 47 (forecast 1819), MLB WSH at DET, 2026-09-21T22:40Z, "Washington covers +1.5" [not_cover]: live pregame 42%, should be 58%; lost
- rec 48 (forecast 1824), MLB MIN at SF, 2026-09-22T01:45Z, "Minnesota covers +1.5" [not_cover]: live pregame 38%, should be 62%; lost
- rec 49 (forecast 1826, reasoning pass), MLB MIN at SF, 2026-09-22T01:45Z, "under 8.5 total runs" [under]: live pregame 38%, should be 62%; won
- rec 50 (forecast 2106), MLB MIL at PHI, 2026-09-23T22:40Z, "Milwaukee covers +1.5" [not_cover]: live pregame 31%, should be 69%; won
- rec 51 (forecast 2126), MLB CWS at KC, 2026-09-23T23:40Z, "Chicago covers +1.5" [not_cover]: live pregame 28%, should be 72%; won
- rec 52 (forecast 2131), MLB MIA at CHC, 2026-09-23T23:40Z, "Miami covers +1.5" [not_cover]: live pregame 34%, should be 66%; won
- rec 53 (forecast 2136), MLB NYM at TEX, 2026-09-24T00:05Z, "New York covers +1.5" [not_cover]: live pregame 32%, should be 68%; won
- rec 54 (forecast 2141), MLB AZ at COL, 2026-09-24T00:40Z, "Arizona covers +1.5" [not_cover]: live pregame 31%, should be 69%; won
- rec 55 (forecast 2146), MLB LAA at ATH, 2026-09-24T01:40Z, "Los Angeles covers +1.5" [not_cover]: live pregame 29%, should be 71%; lost
- rec 56 (forecast 2165), MLB STL at PIT, 2026-09-24T16:35Z, "St. Louis covers +1.5" [not_cover]: live pregame 34%, should be 66%; won
- rec 57 (forecast 2170), MLB CWS at KC, 2026-09-24T18:10Z, "Chicago covers +1.5" [not_cover]: live pregame 37%, should be 63%; won
- rec 58 (forecast 2175), MLB MIA at CHC, 2026-09-24T18:20Z, "Miami covers +1.5" [not_cover]: live pregame 33%, should be 67%; won
- rec 59 (forecast 2185), MLB AZ at COL, 2026-09-24T19:10Z, "Arizona covers +1.5" [not_cover]: live pregame 26%, should be 74%; won
- rec 67 (forecast 2305), NFL ATL at GB, 2026-09-25T00:15Z, "Atlanta covers +15.5" [not_cover]: live pregame 80%, should be 20%; won
- rec 70 (forecast 2311), NFL HOU at IND, 2026-09-27T17:00Z, "Houston covers -0.5" [not_cover]: live pregame 42%, should be 58%; lost
- rec 71 (forecast 2315), NFL NE at JAX, 2026-09-27T17:00Z, "New England covers +9.5" [not_cover]: live pregame 67%, should be 33%; lost
- rec 72 (forecast 2317), NFL NYJ at DET, 2026-09-27T17:00Z, "New York covers +15.5" [not_cover]: live pregame 70%, should be 30%; won
- rec 74 (forecast 2323), NFL ARI at SF, 2026-09-27T20:05Z, "Arizona covers +15.5" [not_cover]: live pregame 73%, should be 27%; won
- rec 75 (forecast 2325), NFL MIN at TB, 2026-09-27T20:05Z, "Minnesota covers -7.5" [not_cover]: live pregame 21%, should be 79%; lost
- rec 76 (forecast 2328), NFL LV at NO, 2026-09-27T20:25Z, "Las Vegas covers +15.5" [not_cover]: live pregame 84%, should be 16%; won
- rec 77 (forecast 2330), NFL LA at DEN, 2026-09-28T00:20Z, "LA covers +5.5" [not_cover]: live pregame 62%, should be 38%; won
- rec 78 (forecast 2332), NFL PHI at CHI, 2026-09-29T00:15Z, "Philadelphia covers +15.5" [not_cover]: live pregame 86%, should be 14%; lost
- rec 79 (forecast 2335), MLB MIL at PHI, 2026-09-24T22:05Z, "Milwaukee covers +1.5" [not_cover]: live pregame 35%, should be 65%; won
- rec 80 (forecast 2338), MLB CLE at BOS, 2026-09-24T22:45Z, "Cleveland covers +1.5" [not_cover]: live pregame 29%, should be 71%; won
- rec 82 (forecast 2341), MLB TB at NYY, 2026-09-24T23:05Z, "Tampa Bay covers +1.5" [not_cover]: live pregame 43%, should be 57%; lost
- rec 83 (forecast 2353), MLB SD at LAD, 2026-09-25T02:10Z, "San Diego covers +1.5" [not_cover]: live pregame 33%, should be 67%; won
- rec 88 (forecast 2478), CFB ARMY at TEM, 2026-09-25T20:00Z, "Army covers +0.5" [fail to cover]: live pregame 43%, should be 57%; won
- rec 90 (forecast 2490), CFB NAVY at UAB, 2026-09-25T23:00Z, "Navy covers -6.5" [fail to cover]: live pregame 20%, should be 80%; lost
- rec 92 (forecast 2515), MLB TB at PHI, 2026-09-25T22:40Z, "Tampa Bay covers +1.5" [not_cover]: live pregame 35%, should be 65%; won
- rec 93 (forecast 2525), MLB NYM at WSH, 2026-09-25T22:45Z, "New York covers +1.5" [not_cover]: live pregame 33%, should be 67%; won
- rec 94 (forecast 2545), MLB CLE at KC, 2026-09-25T23:40Z, "Cleveland covers +1.5" [not_cover]: live pregame 34%, should be 66%; won
- rec 95 (forecast 2555), MLB TEX at MIN, 2026-09-26T00:10Z, "Texas covers +1.5" [not_cover]: live pregame 30%, should be 70%; lost
- rec 96 (forecast 2565), MLB HOU at ATH, 2026-09-26T01:40Z, "Houston covers +1.5" [not_cover]: live pregame 32%, should be 68%; won
- rec 97 (forecast 2609), MLB ATL at MIA, 2026-09-26T20:10Z, "Atlanta covers +1.5" [not_cover]: live pregame 36%, should be 64%; won
- rec 104 (forecast 2874), CFB TA&M at LSU, 2026-09-26T23:30Z, "Texas A&M covers +0.5" [fail to cover]: live pregame 27%, should be 73%; lost
- rec 106 (forecast 2987), MLB TB at PHI, 2026-09-26T23:15Z, "Tampa Bay covers +1.5" [not_cover]: live pregame 37%, should be 63%; won
- rec 107 (forecast 3002), MLB HOU at ATH, 2026-09-27T01:40Z, "Houston covers +1.5" [not_cover]: live pregame 32%, should be 68%; won
- rec 108 (forecast 3065), MLB ATL at MIA, 2026-09-27T19:10Z, "Atlanta covers +1.5" [not_cover]: live pregame 38%, should be 62%; lost
- rec 109 (forecast 3070), MLB CLE at KC, 2026-09-27T19:10Z, "Cleveland covers +1.5" [not_cover]: live pregame 27%, should be 73%; won
- rec 110 (forecast 3080), MLB COL at CWS, 2026-09-27T19:10Z, "Colorado covers +1.5" [not_cover]: live pregame 41%, should be 59%; lost

THE OTHER 59 CARDS (shortlisted, no recommendation):

- forecast 1540 (statistical), MLB NYM at MIA, 2026-09-09T22:40Z, "New York covers +1.5" [not_cover]: 39%, should be 61%
- forecast 1555 (statistical), MLB TB at ATL, 2026-09-09T23:15Z, "Tampa Bay covers +1.5" [not_cover]: 34%, should be 66%
- forecast 1560 (statistical), MLB CHC at MIL, 2026-09-09T23:40Z, "Chicago covers +1.5" [not_cover]: 37%, should be 63%
- forecast 1570 (statistical), MLB PIT at CWS, 2026-09-09T23:40Z, "Pittsburgh covers +1.5" [not_cover]: 34%, should be 66%
- forecast 1580 (reasoning pass), MLB TB at ATL, 2026-09-10T16:15Z, "Tampa Bay to win" [lose]: 43%, should be 57%
- forecast 1583 (reasoning pass), MLB TB at ATL, 2026-09-10T16:15Z, "under 8.5 total runs" [under]: 44%, should be 56%
- forecast 1591 (statistical), MLB TEX at SEA, 2026-09-10T20:10Z, "Texas covers +1.5" [not_cover]: 33%, should be 67%
- forecast 1662 (reasoning pass), MLB PIT at CWS, 2026-09-10T23:40Z, "Pittsburgh to win" [lose]: 46%, should be 54%
- forecast 1684 (statistical), MLB NYM at NYY, 2026-09-11T23:05Z, "New York covers +1.5" [not_cover]: 34%, should be 66%
- forecast 1688 (reasoning pass), MLB BAL at TOR, 2026-09-11T23:07Z, "Baltimore to win" [lose]: 42%, should be 58%
- forecast 1689 (statistical), MLB BAL at TOR, 2026-09-11T23:07Z, "Baltimore covers +1.5" [not_cover]: 35%, should be 65%
- forecast 1810 (reasoning pass), MLB TOR at BAL, 2026-09-21T22:35Z, "Toronto to win" [lose]: 44%, should be 56%
- forecast 1823 (reasoning pass), MLB MIN at SF, 2026-09-22T01:45Z, "Minnesota to win" [lose]: 42%, should be 58%
- forecast 1825 (statistical), MLB MIN at SF, 2026-09-22T01:45Z, "under 8.5 total runs" [under]: 46%, should be 54%
- forecast 2116 (statistical), MLB CLE at BOS, 2026-09-23T23:10Z, "Cleveland covers +1.5" [not_cover]: 34%, should be 66%
- forecast 2145 (reasoning pass), MLB LAA at ATH, 2026-09-24T01:40Z, "Los Angeles to win" [lose]: 38%, should be 62%
- forecast 2164 (reasoning pass), MLB STL at PIT, 2026-09-24T16:35Z, "St. Louis to win" [lose]: 42%, should be 58%
- forecast 2180 (statistical), MLB NYM at TEX, 2026-09-24T18:35Z, "New York covers +1.5" [not_cover]: 33%, should be 67%
- forecast 2183 (statistical), MLB AZ at COL, 2026-09-24T19:10Z, "Arizona to win" [lose]: 40%, should be 60%
- forecast 2184 (reasoning pass), MLB AZ at COL, 2026-09-24T19:10Z, "Arizona to win" [lose]: 38%, should be 62%
- forecast 2337 (statistical), MLB CLE at BOS, 2026-09-24T22:45Z, "Cleveland to win" [lose]: 45%, should be 55%
- forecast 2344 (statistical), MLB CIN at ATL, 2026-09-24T23:15Z, "Cincinnati covers +1.5" [not_cover]: 48%, should be 52%
- forecast 2347 (statistical), MLB LAA at SEA, 2026-09-25T01:40Z, "Los Angeles covers +1.5" [not_cover]: 41%, should be 59%
- forecast 2349 (statistical), MLB HOU at ATH, 2026-09-25T01:40Z, "Houston to win" [lose]: 46%, should be 54%
- forecast 2481 (reasoning pass), CFB ARMY at TEM, 2026-09-25T20:00Z, "Army to win" [lose]: 48%, should be 52%
- forecast 2492 (statistical), CFB NAVY at UAB, 2026-09-25T23:00Z, "Navy to win" [lose]: 31%, should be 69%
- forecast 2493 (reasoning pass), CFB NAVY at UAB, 2026-09-25T23:00Z, "Navy to win" [lose]: 23%, should be 77%
- forecast 2530 (statistical), MLB CIN at TOR, 2026-09-25T23:07Z, "Cincinnati covers +1.5" [not_cover]: 38%, should be 62%
- forecast 2564 (reasoning pass), MLB HOU at ATH, 2026-09-26T01:40Z, "Houston to win" [lose]: 43%, should be 57%
- forecast 2569 (reasoning pass), MLB LAA at SEA, 2026-09-26T02:10Z, "Los Angeles to win" [lose]: 43%, should be 57%
- forecast 2570 (statistical), MLB LAA at SEA, 2026-09-26T02:10Z, "Los Angeles covers +1.5" [not_cover]: 34%, should be 66%
- forecast 2504 (statistical), CFB CLEM at CAL, 2026-09-26T02:30Z, "Clemson to win" [lose]: 40%, should be 60%
- forecast 2505 (reasoning pass), CFB CLEM at CAL, 2026-09-26T02:30Z, "Clemson to win" [lose]: 28%, should be 72%
- forecast 2668 (statistical), CFB ND at PUR, 2026-09-26T18:00Z, "Notre Dame to win" [lose]: 12%, should be 88%
- forecast 2594 (statistical), MLB CIN at TOR, 2026-09-26T19:07Z, "Cincinnati covers +1.5" [not_cover]: 42%, should be 58%
- forecast 2598 (reasoning pass), MLB LAD at SF, 2026-09-26T20:05Z, "Los Angeles to win" [lose]: 42%, should be 58%
- forecast 2971 (reasoning pass), MLB STL at MIL, 2026-09-26T23:10Z, "St. Louis to win" [lose]: 46%, should be 54%
- forecast 2972 (statistical), MLB STL at MIL, 2026-09-26T23:10Z, "St. Louis covers +1.5" [not_cover]: 42%, should be 58%
- forecast 2977 (statistical), MLB CLE at KC, 2026-09-26T23:10Z, "Cleveland covers +1.5" [not_cover]: 35%, should be 65%
- forecast 2992 (statistical), MLB AZ at SD, 2026-09-27T00:40Z, "Arizona covers +1.5" [not_cover]: 37%, should be 63%
- forecast 2997 (statistical), MLB LAA at SEA, 2026-09-27T01:40Z, "Los Angeles covers +1.5" [not_cover]: 38%, should be 62%
- forecast 3001 (reasoning pass), MLB HOU at ATH, 2026-09-27T01:40Z, "Houston to win" [lose]: 42%, should be 58%
- forecast 2306 (statistical), NFL CAR at CLE, 2026-09-27T17:00Z, "Carolina to win" [lose]: 35%, should be 65%
- forecast 2308 (statistical), NFL CIN at PIT, 2026-09-27T17:00Z, "Cincinnati to win" [lose]: 35%, should be 65%
- forecast 2310 (statistical), NFL HOU at IND, 2026-09-27T17:00Z, "Houston to win" [lose]: 44%, should be 56%
- forecast 2312 (statistical), NFL KC at MIA, 2026-09-27T17:00Z, "Kansas City to win" [lose]: 11%, should be 89%
- forecast 2318 (statistical), NFL SEA at WAS, 2026-09-27T17:00Z, "Seattle to win" [lose]: 28%, should be 72%
- forecast 2321 (statistical), NFL TEN at NYG, 2026-09-27T17:00Z, "Tennessee covers +3.5" [not_cover]: 55%, should be 45%
- forecast 2451 (reasoning pass), NFL CAR at CLE, 2026-09-27T17:00Z, "Carolina to win" [lose]: 38%, should be 62%
- forecast 2453 (reasoning pass), NFL CIN at PIT, 2026-09-27T17:00Z, "Cincinnati to win" [lose]: 42%, should be 58%
- forecast 2455 (reasoning pass), NFL HOU at IND, 2026-09-27T17:00Z, "Houston to win" [lose]: 38%, should be 62%
- forecast 2457 (reasoning pass), NFL KC at MIA, 2026-09-27T17:00Z, "Kansas City to win" [lose]: 28%, should be 72%
- forecast 2463 (reasoning pass), NFL SEA at WAS, 2026-09-27T17:00Z, "Seattle to win" [lose]: 32%, should be 68%
- forecast 3068 (statistical), MLB CLE at KC, 2026-09-27T19:10Z, "Cleveland to win" [lose]: 44%, should be 56%
- forecast 2324 (statistical), NFL MIN at TB, 2026-09-27T20:05Z, "Minnesota to win" [lose]: 26%, should be 74%
- forecast 2469 (reasoning pass), NFL MIN at TB, 2026-09-27T20:05Z, "Minnesota to win" [lose]: 38%, should be 62%
- forecast 2326 (statistical), NFL BAL at DAL, 2026-09-27T20:25Z, "Baltimore to win" [lose]: 18%, should be 82%
- forecast 2471 (reasoning pass), NFL BAL at DAL, 2026-09-27T20:25Z, "Baltimore to win" [lose]: 35%, should be 65%
- forecast 2075 (statistical), NFL PHI at CHI, 2026-09-29T00:15Z, "under 41.5 total points" [under]: 49%, should be 51%

### BUILT

- **The one place: `subjects.side_taken(market_type, side)`** -> "yes" or
  "no", with `subjects.SIDES`: every spelling the record holds or a sport
  declares, per market, on its side -- `fail to cover` on the no side beside
  `not_cover`. A market with no declared sides or a spelling it does not
  know raises `subjects.UnplaceableSide`, naming both; never a default.
  `subjects.YES_SIDE` is read off it. In `subjects`, which imports nothing,
  because the resolvers and the sport modules are on the prediction path and
  LAW 1 refuses `gridiron.priced` there (`audit.check_prediction_closure`),
  so the table could not live in `priced.shape`.
- **Every other place goes through it.** `priced.shape.blind_probability`
  places the side by its quantity's market (`QUANTITY_MARKET`); a spelling it
  cannot place is still None with the reason -- the claim writer's ordinary,
  counted refusal (`unmappable_side`). `language.is_no_side` asks the one
  place (a question with no stored side, or of a market with no declared
  sides, is said as asked, as before), and so do the total, rounds,
  distance and moneyline phrases and clauses and `side_named`'s total;
  `language.WHY_YES_SIDE` is read off `YES_SIDE`. The resolvers
  (`resolve._yes_side` for the NFL's and the fights', and the college,
  baseball and basketball ones), `market/lines.py`'s snapshot and its prop
  quote's other side, and `tools/diagnose.py`'s buckets all ask
  `subjects.takes_the_yes_side`: the same answer on every stored spelling,
  and a spelling it does not know refused by name rather than graded, which
  under LAW 3 is written once.
- **The page refuses a side it cannot place.** `views._on_the_question`:
  every number on a Today card about the claim's proposition -- the chance
  chip, the price, the opening read, the pregame figure -- is kept on True,
  turned on False, and anything else raises by name.
  `views._edge_side_words` raises for an edge beside an unplaced side (it
  said the edge was on the question's own side). A combo leg and a
  recommendation line on an unplaced side are refused
  (`views._combo_block`, `views._recommendations_block`).
  `board._question_block` raises on a priced block whose side is not True or
  False (the tiles, the rail and My day are built from it). `/api/week`
  answers 500 with the refusal's words. `views._placed` places a live or a
  settled card from its own forecast through `question_takes_the_proposition`
  -- the live pregame fix of B.
- **The check refuses it.** `audit.board_price_side_faults` fails a priced
  card whose `question_takes_the_proposition` is not True or False (it read
  `is False`); the module's own self-check holds it to
  `BOARD_PRICED_FIXTURE_UNPLACED`, rec 111 as the released payload carried
  it. `audit.check_every_side_is_placed` (gate step 2, on the record's copy;
  `audit.sides_not_placed`, `audit.declared_sides`) fails a stored side the
  one place cannot place and a label a sport declares that it cannot place
  or places off its declared side.
- **Tests:** `tests/test_the_side_is_placed.py`, 43. Rec 111's shape shows
  about 76% and about 51.5¢ for North Texas -6.5 (0.7602, 0.515, 1.94x, the
  pick the same, the check passing); each stored spelling of each sport (33,
  as measured) placed on one side by the one place, the words, the numbers
  and the resolvers alike; every declared label on its declared side; a
  declared no side read as yes caught; the college resolver grades `fail to
  cover` as the no side and refuses an unknown spelling; an unknown spelling
  refused by name in the one place, the words, the page, `/api/week` (500)
  and the gate; each builder refusing a priced unplaced side (and not an
  unpriced one); the check refusing it; rec 111 painted on Tulsa's numbers
  named; a live card's pregame figure on its question's side.
  `test_board.py`: the hand-made priced entry now carries its side (a
  priced entry with none is refused), and the merge's shape is refused by
  the builder and still named by the check.
- **Plantings** (`tools/guards/plant.py`, in `main()` and in
  `tests/test_guards.py`'s list; `LAW_THE_SIDE_IS_PLACED`):
  `plant_a_side_the_one_place_does_not_know_shown_with_numbers` (rec 111's
  shape spelled "fails to cover"), `plant_rec_111_painted_on_the_other_sides_
  numbers`, `plant_an_unplaceable_side_the_check_passes`. And
  `plant_a_board_row_priced_off_the_other_side` takes the builder's refusal
  of the merge's shape as caught, and still holds the check to the merge's
  payload.

### EVERY NUMBER THE FIX MOVES *(both trees on the one verified copy, the clock held at its instant 2026-09-30T03:41:45Z: every sport's current slate and all 20 slates that ever carried a price or an opening read, both forecasters, with each sport's history and digest; `measure_moves.py` -> `m_head.json`, `m_fix.json`, `flatten_diff.py` -> `moves.json`)*

1,174,395 figures compared, 1,885 moved, no errors either side.

- **The numbers:** only the `fail to cover` rows of A and C. Rec 111's row
  (3147): chance 0.2398 -> 0.7602 ("24%" -> "76%"), price 0.485 -> 0.515
  ("48¢" -> "52¢"), pays 2.062 -> 1.942, their tooltips; the Today card's
  chip 24¢ -> 76¢ and its venue words; 88, 90 and 104's Today cards on their
  finished slates (43¢ -> 57¢, 20¢ -> 80¢, 27¢ -> 73¢, and the venue words);
  3148's opening read (2.06x -> 1.94x, its tooltip and venue words).
- **Fields no view draws:** `question_takes_the_proposition` on the Today
  cards, None -> True or False (666: MLB 361, NFL 208, NCAAF 89 -- the
  settled cards, and the unplaced priced rows above -- UFC 8, moneylines
  only; its rounds and distance stay None); and the settled cards'
  `favoured` / `favoured_colour` / `favoured_on_white` (the accent), which
  followed a guess by the subject and follow the placed side now (1,160).
  Nothing in `app.js` reads either. The other 59 moved figures are the
  numbers above: rec 111's rows (42, its pick included), 3148's 10, and 88's,
  90's and 104's Today cards (7).
- **No word moved** in any history, digest or card phrase: the words already
  placed every stored spelling where the one place does.
- No live game was on the copy, so B's pregame figure is not in this diff;
  its test proves it on a world in play.

### PROVED *(`scratchpad/wrongside/`)*

- The three plantings, run alone by this tree's `plant.py` against the
  `git archive` of 8121a9a (`head/`, `run_plantings.py`): all three ESCAPE --
  "the page drew the unplaceable side with numbers: 'UNT covers -6.5' at
  '24%', price 0.485, pays 2.062 | the gate has no check that every stored
  side is placed"; "the shipped row is not North Texas's own numbers: '24%'
  at 0.485 | the row painted on Tulsa's 24%, 48c and 2.06x passed";
  "board_price_side_faults passed a priced card whose side is None" -- and
  all three are CAUGHT on this tree.
- `tests/test_the_side_is_placed.py` on 8121a9a's package: 43 of 43 fail --
  rec 111's shape ("assert None is False"), the live pregame ("'pregame 43%'
  == 'pregame 57%'"), the painted row (no fault) by their numbers; the rest
  for want of the one place.
- This tree's builders on every priced slate of the verified copy and every
  sport's current slate, both forecasters (`measure_after.py`): 50 slates
  built, none refused, no error, `board_price_side_faults` and
  `board_count_faults` empty on every one, `check_every_side_is_placed`
  passing on the record.
- `plant.py` whole: 387/387 caught (384 and these three), twice, the second
  on the tree as left for the prover (`plant_all2.txt`). The full suite, a
  dummy token, TMP/TEMP at their defaults, on the tree as left: 2227 passed,
  4 skipped, exit 0 (`suite3.txt`). One run before it (`suite2.txt`, beside
  a whole `plant.py`) failed one test,
  `test_smoke.py::test_the_weekly_strip_renders_with_hit_targets` ("the
  weekly strip is blank"): a race that is not this build's -- run alone it
  fails 3 times in 4 on 8121a9a's package and 3 in 4 here (below).
- The one copy of the record (1,090,383,872 bytes) was deleted at
  2026-09-30T04:21:54Z; no network, no real token, the live app on 8848
  never contacted, nothing written to the record.

### READINGS TAKEN *(the conservative default; none breaks LAW 1 or LAW 3 or makes a gate count false)*

- **"The one place"** is `subjects.side_taken`, which
  `priced.shape.blind_probability` -- the place the brief names -- now asks.
  The table could not sit in `priced.shape`: the resolvers had to go through
  it too, and `gridiron.priced` may not be imported on the prediction path.
- **"If others decide it independently, route them through the one place"**
  reached the resolvers. Their answer is the same on every spelling the
  record holds and every label a sport declares (tested); what changes is a
  spelling nobody declared: refused, not graded. `calibration.factor_report`
  compares with the forecast's own stored `yes_label` and was left alone.
- **"Refuse" means raise, and only where a number would be drawn:** an
  unpriced card on an unplaceable side (the UFC rounds and distance
  questions) is drawn as before, with the model's own number on its own
  side; a priced one is not drawn at all.
- **The live pregame figure** was fixed here, not queued: placing the side
  was the only way the refusal could ship without refusing every live row
  whose question names the claim's other side.
- **The combos' orientation, the rung under the chance, the Today card's
  payout words and the recommendation line** (below) are pick-number
  findings met outside this fix: reported to the operator for the queue, not
  built.

### PICK-NUMBER FINDINGS, FOR THE QUEUE FIRST *(the amended queue rule of 2026-09-30: each could show the operator a wrong number on a pick; not built here)*

1. **A proposed combo is worth the product of its legs' YES-SIDE numbers,
   whatever side each leg's recommendation is on.** `combos.propose`
   multiplies `fair_value` (the claim's proposition) and prices the singles
   line off `price` (the yes price), and `views._proposal_card` labels each
   leg with its question's words. On the record's priced slates 34 of 35
   proposals carry a no-side leg: 25 MLB ones drawn at 9-20% worth and "pay
   below 7-17¢" where the recommended sides multiply to 35-50%; NFL week
   3's three at 12-18% (below 10-16¢; the sides 63-73%), among them "Las
   Vegas covers +15.5 + Pittsburgh covers +7.5" at 17.9%, whose Las Vegas
   leg's recommendation is on the proposition's side -- the other side of
   the words it is drawn with; four NCAAF (D above) and two NBA. The panel
   is drawn on the board today. (`combos.json`)
2. **A priced spread or total row names the question's rung and draws the
   venue contract's chance and price at another line.** A rung-differs claim
   is the frozen distribution read at the venue's number, and the row's
   words are the question's: rec 111's numbers (now 76% and 51.5¢) are the no
   side of "Tulsa by more than 1.5" (KXNCAAFSPREAD-26OCT01UNTTLSA-TLSA2,
   home line -1.5), drawn under "North Texas -6.5"; the live row's pregame
   figure likewise. 262 of the record's 274 NFL and NCAAF spread claims are
   rung-differs (NCAAF 103 of 103, NFL 159 of 171). A reader could buy North
   Texas -6.5 at the venue on a chance and a price that belong to North
   Texas +1.5.
3. **The Today card's `payout_words` and `payout` are the proposition's**
   on a turned card (the chip beside them is turned). No view draws them
   since the board; they are in `/api/week`'s payload.
4. **`recommendation_line`** (`payload.recommendations.lines[].words`)
   states the proposition's fair value and price after the question's words
   and calls the sides "the yes side" and "the other side" of the
   proposition. Not drawn; in the payload.

### NOT SEEN, AND OPEN

- A live board row on the record: none was in play on the copy. B is proved
  on a world in play and by reading the released code, not on a live page.
- The payload's `question_takes_the_proposition` and accent on settled cards
  changed and nothing draws them; if a later view does, it draws the placed
  side.
- The claim writer: from this build a rung-matched look at a `fail to cover`
  question is claimed rather than refused. None has ever occurred.
- **FOUND ON THE WAY (not a gate count, no law: FOLLOWUPS by the queue
  rule) -- `test_smoke.py::test_the_weekly_strip_renders_with_hit_targets`
  races the page.** It reads the Record page's weekly strip as soon as the
  view is shown, while `/api/over-time` is still in flight (traced: the view
  shows about 40-60ms before the strip's answer lands, on both trees). Run
  alone it failed 3 of 4 on 8121a9a's package and 3 of 4 on this tree; in
  the whole suite it passed twice here and failed once beside a whole
  `plant.py`. A wait on the condition (the strip painted) rather than on the
  view would close it; not a fixed wait, so `ELAPSED_TIME_HELD` would not
  move. The release gate may meet it.

### THE PROVER *(2026-09-30, alone in the worktree; ONE verified copy of the record through `rebuild.verified_backup` at 06:14Z -- 1,092,984,832 bytes, integrity ok, 64 tables, none mismatched -- read with `db.read_only` except where the test server took its sign-in rows, and deleted with its -wal and -shm at 2026-09-30T06:37:21Z; scripts and outputs in `scratchpad/wrongside/prover_*`)*

**THE ONE PLACE AGAINST AN ORACLE.** Every forecast on the copy (3,434)
placed by this tree and by 8121a9a's package, each held to an oracle written
apart from `subjects.SIDES` (its own table of spellings, the subject against
the home and away sides): this tree disagrees with it on none. The released
code differs from it only on `('cfb', 'spread', 'fail to cover')`, 93
forecasts, 26 of them priced (a claim or a recommendation), recommendations
88, 90, 104 and 111 among them -- the implementer's count. UFC rounds and
distance are unplaced by both, and none is priced. No priced forecast is
unplaced by this tree.

**THE LIST, RE-CHECKED ON THE COPY.**
- **A** -- each look at the line, the released and the fixed `_today_card`
  and `board._question_block` run on the entry the page held at that look
  (the look's claim corrected at its instant -- nothing was in force for
  NCAAF spreads -- and its price): rec 88 (Army covers +0.5; 2 looks) drawn
  43% · 48.5c · 2.06x, should be 57% · 51.5c · 1.94x, WON; rec 90 (Navy
  covers -6.5; 6 looks) 20% · 49.5c · 2.02x, should be 80% · 50.5c · 1.98x,
  LOST; rec 104 (Texas A&M covers +0.5; 5 looks) 27% at 48.5c then 49.5c,
  should be 73% at 51.5c then 50.5c, LOST; rec 111 (North Texas covers
  -6.5): its own forecast 3115 carried 0.2398 at 49.5c from its write
  (2026-09-27T16:00Z) until the final pass 3147 stood (2026-09-28T15:00Z;
  3115 is not on the slate now, so its row is worked from the rec's own
  stored numbers), and 3147's last look is 24% · 48.5c · 2.06x, should be
  76% · 51.5c · 1.94x; not settled. Exactly the implementer's figures.
- **B** -- worked again from this tree's slates and the oracle: 116 cards,
  57 recommendations, the same cards and the same figures as the
  implementer's `live.json`, card for card (recs 25-31, 33-40, 44, 46-59,
  67, 70-72, 74-80, 82, 83, 88, 90, 92-97, 104, 106-110).
- **C** -- forecasts 2503, 2917, 2923 and 3148 are reasoning-pass "fail to
  cover" spreads with no claim and opening reads before their start (26, 31,
  32 and 145 of them); 3148 on the fixed page now: "52¢ · pays 1.94x", the
  proposition's latest open 48.5c turned.
- **D -- NOT REPAIRED BY THIS COMMIT.** The fixed page still proposes the
  three NCAAF combos on their yes-side numbers: "Rutgers covers -24.5 + Navy
  covers -6.5" worth 2% (the recommended sides multiply to 71.1%), "California
  covers +6.5 + Army covers +0.5" 14% (38.0%), "Florida International covers
  -14.5 + Texas A&M covers +0.5" 4% (62.8%) -- and Rutgers', California's and
  Florida International's picks (the side each entry clears the bar on) are
  on the OTHER side of the words their legs are drawn with. Pick-number finding 1; its sides are placed, so
  no refusal applies.

**THREE PATHS THE BUILD LEFT OPEN, FOUND AND CLOSED.** Probed on scratch
worlds (`prover_probe.py`, `prover_probe2.py`, `prover_probe_ufc.py`): every
market (NFL spread, moneyline, total, prop; UFC moneyline, rounds,
distance), spelled every way a writer could get it wrong ('', mixed case, a
trailing space, another market's word, an unknown verb), priced and
unpriced, upcoming, live and finished, as the page's forecaster and as the
other forecaster's row on an open row. On 8121a9a's package 32 of 42, 24 of
32 and 36 of 54 were drawn with a number. On the build as first written:
1. **An empty stored side was said as asked.** `language.is_no_side` read
   `not side`, so '' took the yes side's words and an unpriced card drew the
   model's number under them -- "over 44.5 total points · 62%", "HOM covers
   -3.5 · 62%", a prop likewise (a priced one was refused by the numbers; a
   moneyline failed on `UnknownSide`, not by the ruling's name). Only a
   question with no side at all (None) is said as asked now; `model_side` is
   NOT NULL on the record.
2. **The other forecaster's prop was drawn on a side nobody can place.** Its
   light card (`board._other_forecaster_rows`) is built from
   `language.phrase` alone, and the prop branch never asked the one place:
   it printed an unknown spelling as itself -- "Some Player Over 55.5
   receiving yards · 62%", "pregame 62%" live -- and '' likewise. It asks
   `is_no_side` before it words a prop now.
3. **The check passed a live pregame figure on an unplaced side.**
   `audit.board_price_side_faults` walked the priced upcoming blocks only; a
   live card carrying the claim's pregame chance with no placed side -- the
   released shape of all 116 cards in B -- passed. It fails now
   (`BOARD_LIVE_FIXTURE_UNPLACED`, rec 88's live row, in the module's
   self-check beside a placed live card that must pass).
After: every unplaceable probe refused by `subjects.UnplaceableSide`, naming
the spelling; every declared spelling drawn, on every state and forecaster.
Each has a test (`test_the_side_is_placed.py`, the last three: failing on
the build as first written, passing here) and a planting form
(`plant_a_side_the_one_place_does_not_know_shown_with_numbers` gains the
empty total and the other forecaster's "Over" prop;
`plant_an_unplaceable_side_the_check_passes` gains the live row), each
ESCAPING on 8121a9a and on the build as first written and CAUGHT here.

**REC 111 RENDERED** from the copy served by the test server (this tree's
app on a free local port, a dummy token; never the live app), Chromium at
1300px and 390px (`render/rec111-*.png`, read): the row reads "MODEL'S PICK
NORTH TEXAS -6.5 · 76% · 52¢ · 1.94x · $15 · one flat unit, measured and
NOT ahead", and the open row's tile "POINT SPREAD STATISTICAL North Texas
-6.5 · 76% · +22.5¢ · 1.94x" (52¢ is the 51.5c price as the chip rounds
it). No page error, no sideways scroll.

**THE GATE, DRY RUN.** The nineteen step-2 rows the fix touches, read out of
`step_2_guards` and called with `GRIDIRON_VERIFYING` set on the copy: all
pass (the one place, every side has words, both side-in-prose scans, LAW 1's
closures, no orphans, no shadowed definitions, the five board and live
checks on every sport's slate, the docstring, raw-open, replacing-write and
clock scans). `prose_reaching_the_raw_side()` is []. This tree's page on
every slate holding a claim or a recommendation and every sport's current
slate, both forecasters: 44 builds, none refused, no fault. `plant.py`
whole on the tree as committed: 387/387 caught, exit 0
(`prover_plant_all.txt`). The full suite, a dummy non-secret token,
TMP/TEMP at their defaults: 2230 passed, 4 skipped, exit 0
(`prover_suite.txt`; the weekly-strip race above passed this run).

**PICK-NUMBER FINDINGS THE PROVER ADDS, FOR THE QUEUE FIRST** *(not built)*:
5. **The opening read is the venue's main rung, not the question's.**
   `at_the_line.rung_for` takes the rung nearest 50c, so an unpriced card's
   opening read is another line's price under the question's words: on the
   copy, "Under 60.5 total" (UNT at TLSA) carries the 57.5 rung's 48.5c,
   turned -- "52¢ · pays 1.94x" in the Today card and "1.94 times" in the
   board's payout tooltip -- where under 60.5 costs about 58.5c (1.71x).
   The same family as finding 2.
6. **My day names the question's subject's club on a no-side pick.**
   `board._my_day` picks the club by the subject, not the side: a taken
   "not_cover" spread on PHI -3.5 is the chip "PHI · DAL +3.5", a taken
   "lose" moneyline "PHI · DAL to win" (scratch world). No game-market pick
   on the record is taken, so none has been drawn yet.
And finding 2, made concrete on the rendered row: the statistical tile reads
76% for "North Texas -6.5" where that forecast's own number for the
question is 62.6% (the reasoning pass's tile beside it reads 62%), and
"North Texas to win" reads 76% too. The ruled "about 76% and about 51.5¢"
are the numbers of the venue's -1.5 contract -- North Texas +1.5 -- under
the words North Texas -6.5; this build draws them as ruled.

**SEEN, NOT MEASURED:** in the 390px capture the sport tabs in the header
run together ("NFL 193-119MLB 832-640NBA 0NCAAF ..."); not this fix's, and
not measured whether the capture or the page is at fault.

## Every pick names its own side: the payout, the recommendation line and My day -- built 2026-09-30 *(pick-number step C; the queue rule as amended on 30 September, docs/briefs/2026-09-30-rulings.md; uncommitted for its prover)*

The reading taken (docs/REPAIR_STATE.md, the conservative default): a number
on a pick is always stated under the words of the exact contract it belongs
to -- its line and its side. Step C is findings 3, 4 and 6 of the wrong-side
fix's builder and prover (above, "PICK-NUMBER FINDINGS"), and a sweep of
every other place a pick's side, price, probability or size is stated. Step A
(the line) stopped on operator question 36; nothing here changes which line
or contract a spread claim's price belongs to, `at_the_line.home_view_line`,
the claim writer, or how a spread row draws a priced number.

### MEASURED FIRST *(ONE verified copy of the record through `rebuild.verified_backup`, 2026-09-30T08:18:10Z, 1,092,984,832 bytes, integrity ok, 64 tables, none mismatched; read with `db.read_only`; `scratchpad/picknum/C/`; deleted after -- see PROVED)*

- **Which side each recommendation buys, against its words**
  (`measure_sides.py` -> `measure_sides.json`): of the 113 recommendations,
  16 buy the OTHER side of their question's words -- MLB 47 and 82 (read at
  the question's own rung: the model's "Washington covers +1.5" at 58%, the
  recommendation Detroit -1.5 at 37.5¢ worth 41.6%, +2.06¢; "Tampa Bay covers
  +1.5", New York -1.5 at 37.5¢ worth 42.5%, +3.03¢), NFL 67-69, 71-74, 76-78
  and NCAAF 89, 91, 102, 103 (every one a spread read at the venue's line
  where it is not the question's: finding 2, question 36). All final; none
  taken. None in a moneyline or a total. The other 97 buy the side their
  words name (4 of them withdrawn).
- **Prices**: no claim's `venue_implied` (1,746) has more than four places,
  and the payout of the price rounded to four places is the payout of the
  price on every one -- so the card's payout on a question naming the
  proposition is the same number whichever the builder reads.

### BUILT

- **The Today card's payout (finding 3).** `views._today_card` states
  `payout` and `payout_words` for the side its question names: the payout of
  the price the card states (`_payout_for` of the turned price, as the venue
  words have since 2026-09-07), and on a question naming the proposition the
  entry's own payout. They were the entry's -- what the claim's fixed
  proposition pays -- beside a turned chip: rec 111's card said "52¢ · pays
  1.94x" and "2.06x" at once. The card's `price` and `fair_value` stay the
  proposition's: they are the board's inputs, `question_takes_the_proposition`
  beside them, and `board._question_block` turns them (its comment says so).
- **The recommendation line (finding 4).** `views._the_side_bought` places
  the side a recommendation buys once: its question's words when the side
  bought is the one they name, else `language.phrase_of_the_other_side` (the
  other spelling through the one place, `subjects.other_side_spelling`), with
  that side's number and what it costs (`views._cost_of_the_side_bought`,
  `recommend._cost_of`'s orientation), turned as the card turns them so the
  line and the card round a half-cent one way (first built rounded to four
  places, nine lines of the copy rounded a half-cent otherwise than their
  cards; found by the gate's check on the copy, fixed). `language.recommendation_line`
  takes `words` and says "... and it is worth +X¢", never "the yes side" or
  "the other side". The line carries `side_words`, `fair_value` and `price`.
- **My day (finding 6).** Each board block carries `named_club`
  (`language.club_named`: by `side_flips`, the words' own flip; in
  `audit.SIDE_ALLOWLIST` with its date), and `board._my_day` wears that club.
  A total names no club and wears the home club as the game's mark, as it
  did (the render below).
- **From the sweep, two fixes.** THE PAYOUT FLOOR folds by what the side
  bought pays (`views._today_block`): it read the proposition's payout, so a
  no-side pick was folded, or left out of the fold, on the other side's
  payout, and the day strip counted "N of them below your floor" by it -- an
  away +1.5 bought at 70¢ pays 1.43x and was held to the home -1.5's 3.33x.
  A MONEYLINE "LOSE" WITH NO OPPONENT was said "PHI to win" by
  `language.phrase` and `tile_line` (the chance clause beside it said "PHI
  loses"): both ask `side_flips` now, "PHI to lose". Every card on the
  record carries an opponent, so nothing drawn moved. *(CORRECTED BY ITS
  PROVER: a Results row -- `views.history` -- carries no opponent, and the
  Results table drew 403 moneyline "lose" rows as "<club> to win"; this fix
  is what mends them. See THE PROVER below.)*
- **The gate.** `audit.pick_side_faults` works each out again from the
  payload: the payout of the price a Today card states turned by its own
  `question_takes_the_proposition`, and its payout words; for each
  recommendation line, the side it buys from its question's Today card (the
  proposition's number and price, and which side the words name), that
  side's words, number and cost, no "the yes side / the other side", and the
  fold by what it pays; for each My day chip, the club its forecast's stored
  side names through `subjects.side_taken` and the game's two clubs (never
  the builder's `club_named`), and the row's line words.
  `audit.check_every_pick_names_its_side` raises, called in gate step 2 on
  every sport's slate (the record's copy). Its fixtures
  (`PICK_SIDE_FIXTURE_GOOD`, the four `PICK_SIDE_FIXTURES_AS_RELEASED`) are
  held at import.
- **Tests:** `tests/test_pick_names_its_side.py`, 10, each failing on
  401d059's package (run there with this module copied in): the turned
  payout (and the released shape named), a card naming the proposition keeps
  its payout, the line on the words' side (57¢ / 52¢, BBB), the line on the
  other side (AAA at 30¢, 43¢), the line's own words, My day on both no sides
  and a yes side and a total, the floor, the moneyline with no opponent, the
  other side through the one place, and the gate making the call.
  `test_recommend.py::test_the_card_the_line_sentence_and_the_pregame_figure_
  read_one_number` hands the line a real card and asserts it names AAA, the
  side the corrected 54% buys; `::test_the_words_are_plain_and_recommend_
  without_tipping` takes `words`.
- **Plantings** (`tools/guards/plant.py`, in `main()` and in
  `tests/test_guards.py`'s list; `LAW_THE_PICK_NAMES_ITS_SIDE`):
  `plant_a_payout_on_the_propositions_side` (and the fold on the
  proposition's payout), `plant_a_recommendation_line_on_the_proposition`
  (on the words' side and on the other side),
  `plant_a_my_day_chip_wearing_the_subjects_club`.

### EVERY NUMBER THE STEP MOVES *(both trees on the one verified copy, the clock held at 2026-09-30T08:18:10Z: every sport's current slate and all 20 slates that ever carried a price or an opening read, both forecasters, with each sport's history and digest; `measure_moves.py` -> `m_head.json` (401d059), `m_fix.json`; `flatten_diff.py` -> `moves.json`)*

1,179,547 figures compared, 5,625 moved, no errors either side. Every moved
figure is one of:

- **A turned card's `payout` and `payout_words`**: 146 Today cards (MLB 104,
  NFL 25, NCAAF 14, NBA 3), each now the payout of the price it states --
  e.g. rec 111's 2.062/"2.06x" -> 1.942/"1.94x", rec 104's "2.02x" -> "1.98x",
  forecast 2493's "3.28x" -> "1.44x". Payload only: nothing draws them.
- **The recommendation lines**: 87 lines' words (MLB 60, NFL 13, NCAAF 9, NBA
  5), with their new `side_words`, `fair_value` and `price`. 70 name the
  same side as before with that side's numbers (rec 111: "North Texas covers
  -6.5 -- the model makes it 24¢, the venue is at 48¢, and the other side is
  worth +22.5¢" -> "... 76¢, the venue is at 52¢, and it is worth +22.5¢");
  17 now name the other side of their question's words, the side they buy:
  forecasts 1819 (Washington -> Detroit -1.5), 2341 (Tampa Bay -> New York
  -1.5), 2305, 2307, 2309, 2315, 2317, 2319, 2321, 2323, 2328, 2330, 2332
  (NFL), 2484, 2502, 2744, 2808 (NCAAF) -- sixteen recommendations and one
  page line with no stored recommendation (forecast 2321, "Tennessee covers
  +3.5" -> "New York covers -3.5"). Payload only.
- **`named_club`**, a new field on every board block (the rest of the 5,625).

No figure the board draws moved (every row's and tile's chance, price,
payout, size and edge are as they were); no fold moved (the day strip's
counts are unchanged on all 50 payloads); no My day chip moved (no game pick
on the record is taken). `pick_side_faults` names 893 faults on the 50
payloads 401d059 builds and none on this tree's; `board_price_side_faults`,
`board_count_faults` and `live_card_faults` are empty on both
(`check_payloads.py`).

### THE SWEEP: EVERY PLACE A PICK'S SIDE, PRICE, PROBABILITY OR SIZE IS STATED *(the payload `/api/week` builds, and the page where it draws it; read from the code and from the 50 payloads above)*

- **The Today card** (payload; the board reads it): `question`, the chip
  (`model_words`), `venue_words`, `price_words` -- the side the question
  names, correct; `payout`, `payout_words` -- FIXED (finding 3); `price`,
  `fair_value` -- the proposition's, the board's inputs beside
  `question_takes_the_proposition`, stated under no words (left: turning
  them on the card would have the board turn them twice); the edge and its
  label -- the better side's edge, labelled "on the other side" where it is
  (true, relative words); `size_words` -- the recommendation's size, under
  the question's words: correct where the side bought is the words' side,
  QUESTION 37 where it is not; the opening read (unpriced) -- finding 5,
  the venue's main rung (step A's family); `pregame_words` on a live card --
  placed (the wrong-side fix), at the venue's line on a rung-differs claim
  (finding 2); `settled_words` -- the model's own number on its own side,
  correct.
- **The Today block's fold and the day strip's counts** ("N of them below
  your floor", drawn) -- FIXED (the floor by what the side bought pays).
- **The taken list** ("<question> · +X¢ when marked", payload): the
  recommendation's edge at the tap under the question's words -- correct
  where the side bought is the words' side, QUESTION 37 otherwise (no game
  pick on the record is taken).
- **The recommendation lines** (payload) -- FIXED (finding 4); a
  rung-differs line names the side it buys at the QUESTION's line with the
  venue line's numbers ("Howard covers +24.5 -- 89¢" for rec 89): finding 2,
  step A.
- **The board's rows and tiles** (drawn): the pick's words, chance, price,
  payout and their tooltips -- the side the question names, turned once in
  `board._question_block`, correct, and at the venue's line on a rung-differs
  spread (finding 2, step A, out of this step's scope); `size_words`,
  `edge_words` and the green outline -- the recommendation's: QUESTION 37
  where it buys the other side of the words; the live row's pregame figure
  -- placed; the settled verdict -- correct.
- **My day** (drawn) -- FIXED (finding 6); a total's chip wears the home
  club as the game's mark, its words naming no club (unchanged, and read in
  the render).
- **The other forecaster's rows on an open row** (drawn): `language.phrase`
  and the stored number, placed by the one place -- correct.
- **Combos** (drawn): the proposals -- finding 1, step B; the graded
  packages -- each leg's number and price turned to the side the venue's leg
  names (`views._leg_reading`), correct.
- **The slate's cards** (payload): `phrase`, `shown_prob`, `rail_line`,
  `side_word` -- the model's side, correct; the at-the-line sentence --
  names its own contract (the proposition at the venue's line) with its own
  numbers, correct apart from question 36's sign on an away contract;
  `priced_line` -- the blind and priced numbers against a market snapshot
  oriented to the model's side (`lines.snapshot_prediction`), correct.
- **The words** (`language`): `phrase` and `tile_line` on a moneyline no
  side with no opponent -- FIXED; `chance_clause` already said it right.
- **Results, history, the digest and the Record page**: the model's side and
  number on a settled question, and counts; no price or size of a pick.
  *(CORRECTED BY ITS PROVER: the Results table's words named the other side
  on every moneyline "lose" row -- see THE PROVER below.)*

### READINGS TAKEN *(the conservative default)*

- **"The picked side"** is, for the Today card's payout, the side its
  question names (the side every other number on the card states); for a
  recommendation line, the side it buys; for My day, the side the taken
  pick's words name.
- **The payout floor** ("picks that clear the bar but pay less than this")
  is read as what the side bought pays: the fold is of recommendations.
- **The line's words keep the question's line**: a claim read at the venue's
  line is step A's (question 36), and this step changes no line.

### NOT SEEN, AND OPEN

- **Question 37** (docs/REPAIR_STATE.md): a recommendation that buys the
  OTHER side of its question's words is drawn on the board and the Today
  card with its size, edge and outline under the model's own side's words
  -- 16 on the record, all spreads, 14 of them rung-differs. Which contract
  such a row headlines is not settled by the rulings; nothing built.
- A taken game pick on the record: none, so My day's fix is seen on a
  scratch world only (the render below), not on a live page.
- SEEN, NOT THIS STEP'S: the reasoning pass's prose in the board's
  tooltips trips the plain-words scan ("boost", "play") on the reasoning
  pass's own slates of the copy -- NFL week 3 (the current slate) 24, week 2
  2, NBA 15, seven MLB slates 1 to 6 each -- on 401d059 and on this tree
  alike; the gate reads the statistical model's slates only. Not a number
  on a pick.

### THE RENDER *(a scratch world -- no game pick on the record is taken -- served by the test server on a free local port with a dummy token, never the live app on 8848; Chromium at 1100px and 390px; `scratchpad/picknum/C/render_myday.py`, `render/`)*

Four taken questions: PHI -3.5 "not_cover", PHI moneyline "lose", NYG -7.5
"cover", and the DAL at PHI total "under". On 401d059 the chips read "PHI ·
DAL +3.5", "PHI · DAL TO WIN", "PHI · UNDER 44.5 TOTAL", "NYG · NYG -7.5"; on
this tree "DAL · DAL +3.5" and "DAL · DAL TO WIN" in Dallas's own colour, the
total and New York's as they were. Every chip 44px tall, no page error, no
sideways scroll at either width; the words read.

### PROVED *(`scratchpad/picknum/C/`)*

- The three plantings, run alone by this tree's `plant.py` against the `git
  archive` of 401d059 (`head/`, `run_plantings.py` -> `escape_on_head.txt`):
  all three ESCAPE -- "the shipped card says 2.062 and '2.06x' where BBB to
  win pays 1.942 | the shipped card is not folded under the 2.0x floor ... |
  the gate has no check that a pick names its own side"; "at 0.485: the
  shipped line reads 'BBB to win -- the model makes it 43¢, the venue is at
  48¢, and the other side is worth +3.5¢ ...' | at 0.3: ... 'and the yes side
  is worth +11.0¢' ..."; "the shipped chips wear ['PHI'] beside ['DAL +3.5',
  'DAL to win']" -- and all three are CAUGHT on this tree
  (`caught_on_fix.txt`).
- `tests/test_pick_names_its_side.py` on 401d059's package: 10 of 10 fail.
- The one copy of the record was deleted, with its -wal and -shm, at
  2026-09-30T08:53:59Z. It was only read (`db.read_only`); the render used
  scratch worlds. No network, no real token, the live app never contacted,
  nothing written to the record.
- `plant.py` whole: 390/390 caught (387 and these three), "Every law has a
  guard, and every guard has now fired at least once", exit 0
  (`plant_all.txt`; again on the tree as left, `plant_all_final.txt`). The
  full suite, a dummy non-secret token, TMP/TEMP at their defaults, on the
  tree as left: 2240 passed, 4 skipped, exit 0 (`suite.txt`; 2230 and this
  module's 10).

### THE PROVER *(2026-09-30, alone in the worktree; ONE verified copy of the record through `rebuild.verified_backup` at 2026-09-30T09:36:00Z -- 1,092,984,832 bytes, integrity ok, 64 tables, none mismatched -- read with `db.read_only`, except where the test server took its sign-in rows and the render's one tap; deleted after, below; scripts and outputs in `scratchpad/picknum/C/prover/`)*

**The builder's claims, checked on the copy.** HEAD (401d059, a `git
archive`) and this tree each built the 50 payloads again (every sport's
current slate and the 20 slates that ever carried a price or an opening read,
both forecasters, the clock held at the copy's instant; `measure_moves.py`):
`pick_side_faults` 893 faults on HEAD's and none on the builder's tree, the
board's other checks empty on both, and every moved figure of the builder's
list (the turned payouts, the 87 lines, `named_club`) moved as listed; the
three plantings escape on HEAD and are caught on the tree; its ten tests fail
on HEAD. One claim was wrong (next).

**FOUND AND FIXED: THE RESULTS TABLE NAMED THE OTHER SIDE ON EVERY "LOSE"
ROW.** `views.history` -- the Results page's table, drawn as "Prediction |
Date | Week | Model | Market then | Tier | Result", and the reasoning pass's
prompt list -- builds each row with no opponent, so `language.phrase` could
not restate a no side as the other club, and its moneyline branch then said
the SUBJECT "to win": "KC to win · 52.0% · LOSS" for a pick of KC to LOSE at
52% (KC won, the pick lost), "Camila Reynoso to win · 70.3% · WIN" for her to
lose (she lost). On the copy (`probe_history.py`), 403 of 3,434 rows, every
moneyline "lose" row the record holds, in every sport: NFL 30, MLB 172, NBA
33, NCAAF 61, UFC 107 -- on every release since the table was built. The
sweep's fix 2 (said as asked, `side_flips`) mends every one ("KC to lose",
"Camila Reynoso to lose"); the builder recorded it as moving nothing drawn
("every card carries an opponent"), measured before that fix was made. Now
HELD: `audit.pick_side_faults` reads a history payload's rows (a row with no
opponent is said as asked: a moneyline "to win" / "to lose", a spread
"covers" / "does not cover", a total "over" / "under", each by its stored side
through `subjects.side_taken`), gate step 2 hands it each sport's latest 500
rows ("every Results row names the side its number is for"), and
`plant_a_results_row_naming_the_other_side` plants it. Spreads and totals were
said as asked already ("KC does not cover -1.5", "under 9.5 total runs").

**FOUND AND FIXED: THE EDGE FIGURE'S SIDE.** The edge figure is the better
side's (`recommend.side_for`), and the Today card labels it "on the other
side" where that is not the side its question names -- reading `edge_side`,
which is None when neither side clears the fee. So a watched card whose
figure was the OTHER side's was labelled as the question's own, and the
board's tile, which draws the figure where the price is (`q.edge_words ||
q.price_words`), drew it bare in every case. On the copy
(`edges_count.py`): 10 cards -- MLB 1296, 1560, 2344, 2570, 2594, 2972, 2992,
3065 (final; 3065 showed "+0.6¢" where its own side was worth -4.56¢), NFL
2075 (final) and NBA 3166, upcoming, drawn on the reasoning pass's board:
"San Antonio to win · 54% · -1.5¢", San Antonio's own -2.5¢. BUILT:
`side_for` returns `better_side` (the figure's side, with or without a side
chosen), `for_predictions` carries it as `edge_cents_side` beside
`edge_side` (unchanged: no side, no return, `test_recommend`'s own test
holds), `views._edge_figure_side` reads it for the label, the quiet line and
the card's new `edge_on_the_other_side`, and `language.board_edge_words`
puts "on the other side" after the tile's figure -- on a moneyline or total
row. A SPREAD TILE KEEPS ITS BARE FIGURE: a spread claim is read at the
venue's line, often not the question's (finding 2), so "the other side" of
the question's words would name another contract again; how a spread row
draws a priced number is step A's (question 36). Held by the same check (the
figure's side worked out again from the card's own number and price, each
side by `recommend.edge_cents`, a tie within the rounding naming neither;
the card's label, and a non-spread tile's words) and planted
(`plant_an_edge_on_the_other_side_drawn_as_the_questions`).

**EVERY NUMBER THE STEP MOVES, WITH ITS PROVER'S FIXES** *(HEAD against this
tree on the one copy, after the render's tap; `m_head2.json`, `m_fix2.json`,
`moves2.json`)*: 7,228 of 1,180,857 figures -- the builder's list, and: 300
Results rows' words in each sport's latest 500 (the table's first pages; 403
on the whole record); the edge label of the 10 cards above (13 figures:
three of the cards are on two slates each); forecast 3166's tile and its row's pick,
"-1.5¢" -> "-1.5¢ on the other side" (the one drawn board figure that moved);
`edge_on_the_other_side` on every card (new); and rec 111's My day chip --
the prover TAPPED rec 111 on the copy (a scratch copy, deleted after; no game
pick on the record is taken) to draw My day from the record's own rows: HEAD
wears TLSA in Tulsa's blue beside "North Texas -6.5", this tree UNT in North
Texas's green. `pick_side_faults`: 909 faults on HEAD's 50 payloads (366 a
payout, 527 a recommendation line, 12 an edge's label, 2 a tile's edge, 2 My
day -- rec 111's chip, on its two slates) and 300 on its Results rows; none
on this tree's.

**THE RENDER** *(the copy served by the test server on a free local port,
this tree's app, a dummy non-secret token, never the live app on 8848;
Chromium at 1300px and 390px; `render.py`, `render_results.py`,
`render_fix/`, and `render_head/` for the Results rows on HEAD's code)*: My
day's chip "UNT · NORTH TEXAS -6.5 · UPCOMING · 185/100" in North Texas's
green, 44px tall at both widths; rec 111's row and open tiles (the tile's
"+22.5¢" is North Texas at the venue's +1.5: finding 2, step A); NBA 3166's
tile "54% · -1.5¢ on the other side · 1.83x", wrapping inside the tile at
390px; the Results rows "KC to lose · 52.0% · LOSS" and "Camila Reynoso to
lose · 70.3% · WIN" (HEAD: "KC to win", "Camila Reynoso to win" beside the
same numbers). No page error, no sideways scroll at either width. Read: the
words and numbers agree on every changed element; nothing is hard to read.

**PROVED.** The five plantings (`run_plantings.py`), run by this tree's
`plant.py` against the `git archive` of 401d059: all five ESCAPE -- the
builder's three as before, "the shipped Results row of the moneyline says
'PHI to win' where its side reads 'PHI to lose'", "the shipped card labels
'-1.0¢' 'Edge after fees' under 'BBB to win', where -1.0c is AAA's and BBB's
own is -3.0c | the shipped tile draws '-1.0¢'" -- and all five are CAUGHT
here (`escape_on_head.txt`, `caught_on_fix.txt`).
`tests/test_pick_names_its_side.py`, 15 (the builder's 10 and five more):
all 15 fail on 401d059. Gate step 2's touched rows, dry-run with
GRIDIRON_VERIFYING set on the copy (`step2_dry.py`, not verify.py whole): 30
of 30 pass, the two pick-side rows among them; `prose_reaching_the_raw_side()`
is empty. `plant.py` whole: 392/392 caught (the builder's 390 and these two),
"Every law has a guard, and every guard has now fired at least once", exit 0
(`plant_all.txt`). The full suite, a dummy non-secret token, TMP/TEMP at
their defaults: 2245 passed, 4 skipped, exit 0 (`suite.txt`; the builder's
2240 and the five new tests); the only line under "tests that reached the
network" is the network guard's own self-test. The one copy of the record
was deleted at 2026-09-30T10:44:20Z (it had no -wal or -shm left); it was
read with `db.read_only`, and written only by the test server serving it
(sign-in rows, and the one tap on rec 111 for the render). Nothing was
written to the record; no network, no real token, the live app never
contacted, nothing run from the main checkout.

**SEEN, NOT FIXED (named for the queue; none is this step's to build):**
- A watched row's RED OUTLINE ("costs the operator after fees") is decided by
  the better side's figure: where the question's own side costs and the other
  side's figure is above nothing but below the fee's bar, the row wears none
  -- MLB 1540 ("New York covers +1.5", +1.3¢ on the other side, its own
  -5.3¢) and 3065 (+0.6¢, its own -4.56¢), both final. A signal, not a
  number; question 37's family (the outline).
- Question 37 as its prover's note says: the size, the green outline and
  the headline of a recommendation that buys the other side of its words, and
  every spread tile's edge (step A).
- The no-side SIZE above a market's gate is sized on the yes side's number
  and price (`recommend.size_for`) -- question 10, already queued; every
  market is below its gate or not measured ahead, so every size is a flat
  unit today.
- rec 111's tile edge "+22.5¢" and every rung-differs spread figure: finding
  2, step A.

## A combo is worth the product of its picked sides, each leg named on its picked side -- built 2026-09-30 *(pick-number step B; the queue rule as amended on 30 September, docs/briefs/2026-09-30-rulings.md; uncommitted for its prover)*

The reading taken (docs/REPAIR_STATE.md, the conservative default): a number
on a pick is always stated under the words of the exact contract it belongs
to -- its line and its side. Step B is finding 1 of the wrong-side fix's
builder and prover (above, "PICK-NUMBER FINDINGS"). Step A (the line) stopped
on operator question 36; nothing here changes which line or contract a spread
claim's price belongs to, `at_the_line.home_view_line`, the claim writer, or
how a spread row draws a priced number. LAW 5's combo clause is unchanged:
proposed, never priced at the venue, a same-game combo refused.

### MEASURED FIRST *(ONE verified copy of the record through `rebuild.verified_backup`, started 2026-09-30T11:31:49Z, finished 11:32:35Z: 1,092,984,832 bytes, integrity ok, 64 tables, none mismatched; read with `db.read_only`; both trees -- the `git archive` of 8318650 and this one -- built every sport's current slate and all 17 slates that carried a price at the line, both forecasters, the clock held at 11:31:49Z; `scratchpad/picknum/B/measure_combos.py` -> `m_head.json`, `m_fix.json`; `summarise.py`, `before_after.py` -> `before_after.txt`; deleted after -- see PROVED)*

35 proposals on the record's priced slates (CFB 4, MLB 26, NBA 2, NFL 3;
30 the statistical model's, 5 the reasoning pass's). 34 had a leg bought on
the claim's no side, and all 34 were drawn at a worth that was not the
product of the sides their legs' recommendations buy; 8 named a leg on the
other side of the one it is picked on. The one proposal already right in
its worth (MLB 1812 + 1819, both legs on the yes side) named its Detroit -1.5
leg "Washington covers +1.5" (rec 82's question).

### BUILT

- **The leg as the contract it is picked on.** `combos.leg_on_its_side` is
  the one place: the side of the claim's proposition the leg buys, the
  model's number for that side (the entry's `fair_value` on the yes side,
  one minus it on the no side) and what one contract of that side costs
  (`recommend._cost_of`: the yes price, or the rest of the dollar), so the
  leg's worth less its cost and the fee on it is its own `edge_cents`. A
  side that is neither is refused by name (`ValueError`).
- **The proposal.** `combos.propose` multiplies those numbers
  (`fair_value`), works the ceiling out from the product (`price_ceiling`)
  and prices the singles line on those sides at those costs
  (`singles_alternative`). Each leg carries `side`, `worth` and `cost`; the
  proposition's own number and price are no leg's. The pairing, the order
  (the legs' own edge), the per-sport limit, "no leg reused" and "different
  games" are as they were.
- **The words.** `views._proposal_card` names each leg through
  `views._the_side_bought`, the function the recommendation line reads
  (step C): the question's words where the side bought is the side they
  name, else `language.phrase_of_the_other_side` through the one place. Its
  `fair_cents` is the side's number; `side`, `worth` and `cost` travel on the
  leg (payload only; the card draws the words, the worth and the ceiling).
- **The gate.** `audit.combo_side_faults` works each proposal out again from
  the payload: each leg's side from its recommendation line (every leg clears
  the bar alone, so every leg has one; a leg without one is named), its number
  and cost from its question's Today card turned by the card's own
  `question_takes_the_proposition`, its words, `fair_cents`, `side`, `worth`
  and `cost`; the combo's worth, its chip's words, the ceiling (cents and
  words), the singles line and fee ratio, and the group's fee sentence, from
  those sides alone. `audit.check_every_combo_is_its_picked_sides` raises,
  in gate step 2 on every sport's slate (the record's copy). Its fixtures
  (`COMBO_SIDE_FIXTURE_GOOD`, five `COMBO_SIDE_FIXTURES_AS_RELEASED`) are held
  at import.
- **Tests:** `tests/test_combo_sides.py`, 11. Nine fail on 8318650's package
  (run there with this module copied in): the leg on its side (and its edge
  its own), a side that is neither refused, the product of the picked sides
  with its ceiling and singles line (the singles edge the legs' own edges),
  the page on the sides bought (0.57 x 0.57 = 32%, where it drew 18%), each
  leg named on the side it buys (in its recommendation line's words), each
  released shape of the page named, the fixtures, a leg with no
  recommendation line, and the gate's call. Two hold what was right and pass
  on both: a yes-side leg keeps its numbers, and the combo clause (a
  same-game pair refused on any sides; no venue price, edge or payout).
- **Plantings** (`tools/guards/plant.py`, in `main()` and in
  `tests/test_guards.py`'s list; `LAW_THE_COMBO_IS_ITS_PICKED_SIDES`):
  `plant_a_combo_worth_its_legs_yes_sides` (the worth, the ceiling, the
  singles line and a leg's number of the yes sides; the gate's step 2 making
  the call) and `plant_a_combo_leg_named_on_the_side_it_does_not_buy`.

### EVERY PROPOSAL, BEFORE AND AFTER *(8318650 -> this tree; "below" is the ceiling; `before_after.txt`)*

34 worths, 34 ceilings and 34 singles lines moved; 8 proposals' words moved.
`combo_side_faults` names 259 faults on the 44 payloads 8318650 builds (40
proposal cards drawn, the current slates repeating their week's) and none on
this tree's.

- CFB 25 Sep (model): "Rutgers covers -24.5 + Navy covers -6.5" 2.3%, below
  1¢ -> "Howard covers +24.5 + Navy covers -6.5" 71.1%, below 65¢.
- CFB 25 Sep (model): "California covers +6.5 + Army covers +0.5" 14.3%,
  below 12¢ -> "Clemson covers -6.5 + Army covers +0.5" 38.0%, below 34¢.
- CFB 26 Sep (model): "Florida International covers -14.5 + Texas A&M covers
  +0.5" 3.8%, below 2¢ -> "Long Island University covers +14.5 + Texas A&M
  covers +0.5" 62.8%, below 57¢.
- CFB 26 Sep (model): "North Texas covers -41.5 + Buffalo covers -24.5"
  24.8%, below 21¢ -> "North Texas covers -41.5 + Robert Morris covers
  +24.5" 31.2%, below 27¢.
- MLB, the model's 22 run-line and mixed combos (days 164-183), words
  unchanged but for one: 8.7-19.5% -> 34.5-49.5%, ceilings 7-17¢ -> 30-45¢
  (e.g. day 180 "Chicago covers +1.5 + New York covers +1.5" 8.7%, below 7¢
  -> 49.5%, below 45¢); day 178 "over 7.5 total runs + Washington covers
  +1.5" -> "over 7.5 total runs + Detroit covers -1.5", 22.8% and below 19¢
  unchanged (both legs on the yes side).
- MLB, the reasoning pass's four "under ... total runs" combos (days 165,
  166, 166, 178): 14.4-16.8% -> 34.8-38.4%, ceilings 12-15¢ -> 31-34¢.
- NBA day 1 (drawn on today's board): the model's "Detroit to win +
  Philadelphia to win" 32.2%, below 28¢ -> 37.9%, below 34¢; the reasoning
  pass's "Philadelphia to win + Boston to win" 23.0%, below 20¢ -> 27.0%,
  below 23¢.
- NFL week 3 (the model; the current slate): "Minnesota covers -7.5 +
  Atlanta covers +15.5" 17.2%, below 15¢ -> "Minnesota covers -7.5 + Green
  Bay covers -15.5" 62.8%, below 57¢; "Las Vegas covers +15.5 + Pittsburgh
  covers +7.5" 17.9%, below 16¢ -> "New Orleans covers -15.5 + Cincinnati
  covers -7.5" 66.3%, below 61¢; "Philadelphia covers +15.5 + WAS covers
  +7.5" 12.5%, below 10¢ -> "Chicago covers -15.5 + Seattle covers -7.5"
  73.2%, below 67¢.

### READINGS TAKEN *(the conservative default)*

- **"The picked side"** of a leg is the side its recommendation buys (the
  entry's `side`), the side the leg's number, cost and edge were chosen on.
- **"Named in the words of the side it is picked on"**: the words the
  recommendation line uses for the side it buys (step C's
  `_the_side_bought`), so a combo leg and its line never say two things.
  Question 37 asks which contract a BOARD ROW headlines; a combo leg is the
  contract bought by the step's own words, and no row changes here.
- **The line** stays the question's, as on the recommendation line: step A's.

### NOT HERE, AND NAMED

- **The line a spread leg's numbers belong to (finding 2, operator question
  36; step A).** Of the 56 spread legs, 12 in 7 proposals were priced at the
  venue's line where it is not the question's -- CFB 2484 (claim -41.5,
  question -24.5: "Howard covers +24.5" at 88.6% is Howard +41.5's number),
  2502, 2478, 2808, 2874, 2898, 2744; NFL 2325, 2305, 2328, 2309, 2332 -- and
  37 in 22 proposals were priced off an away contract read at the wrong sign
  (question 36: the model's number at one line, the cost at its mirror; 30
  MLB run-line legs, CFB 2490, 2502, 2478, NFL 2325, 2309, 2332, 2319). Their words keep the question's line, through the
  function the recommendation line reads, and their worth multiplies the
  numbers the claims carry; step A settles both.
- **A venue package's graded legs** (`today.combos.graded`, `views._leg_reading`):
  oriented to the side each venue leg names since 2026-09-08, and not
  touched.
- **SEEN, NOT THIS STEP'S (display, not a number):** the proposal card's legs
  are drawn "LAD to win+BOS to win" -- `.combo-and` has no rule in the
  stylesheet, so the "+" sits against both legs (on 8318650 too; the render
  below). *(Fixed by its prover, below: the legs one to a line.)*

### THE RENDER *(a scratch world -- two baseball moneylines, "BOS to win" bought on the side its words name at 48.5c, "SF to win" bought as LAD at 30c -- served by the test server on a free local port with a dummy token, never the live app on 8848; Chromium at 1100px and 390px; `scratchpad/picknum/B/render_combos.py`, `render/`)*

On 8318650 the card read "SF to win+BOS to win · MODEL 18¢ · PAY BELOW worth
taking only below 16¢ · as singles: +1.8¢ a leg, fee 5.4% · as one package:
fee 6.9%"; on this tree "LAD to win+BOS to win · 25¢ · worth taking only
below 21¢ · as singles: +7.2¢ a leg, fee 5.3% · as one package: fee 6.5%", and
the group's fee sentence "about 1.2 times" where it said 1.3. No page error,
no sideways scroll at either width; the words read.

### PROVED *(`scratchpad/picknum/B/`)*

- The two plantings, run alone by this tree's `plant.py` against the `git
  archive` of 8318650 (`headp/`, `run_plantings.py` -> `escape_on_head.txt`):
  both ESCAPE -- "the shipped combo is worth 0.1849 where its legs' picked
  sides (BBB and DDD, 57% each) multiply to 0.3249 | ... the gate has no
  check that a combo is its legs' picked sides | the gate's step 2 does not
  call ..."; "the shipped combo names ['BBB to win', 'DDD to win'] worth
  0.1849, where its legs are bought as BBB to win (57%) and CCC to win (43%)
  | ..." -- and both are CAUGHT on this tree (`caught_on_fix.txt`).
- `tests/test_combo_sides.py` on 8318650's package: 9 of 11 fail (the two
  that hold what was right pass on both).
- Gate step 2's touched rows, dry-run with GRIDIRON_VERIFYING set on the
  copy (`step2_dry.py`, step C's prover's shape; not verify.py whole): 26 of
  26 pass, the new combo row among them (8.6s), with the orphan, docstring,
  side, prose, plain-words, LAW 5 and scan rows; `prose_reaching_the_raw_side()`
  is empty.
- `plant.py` whole: 394/394 caught (392 and these two), "Every law has a
  guard, and every guard has now fired at least once", exit 0
  (`plant_all.txt`). The full suite, a dummy non-secret token, TMP/TEMP at
  their defaults: 2256 passed, 4 skipped, exit 0 (`suite.txt`; 2245 and this
  module's 11; again on the tree as left, `suite_final.txt`, the same); the
  only line under "tests that reached the network" is the network guard's
  own self-test.
- The one copy of the record was deleted at 2026-09-30T12:24:12Z (it had no
  -wal or -shm left). The measurements read it with `db.read_only`; the
  step-2 dry run read it through the gate's own handle on its copy. Nothing
  was written to the record; no network, no real token, the live app never
  contacted, nothing run from the main checkout.

### THE PROVER *(2026-09-30, alone in the worktree; ONE verified copy of the record through `rebuild.verified_backup`, started 12:53:33Z, finished 12:54:20Z -- 1,092,984,832 bytes, integrity ok, 64 tables, none mismatched -- read with `db.read_only`, except where the test server took its sign-in rows; deleted after, below; scripts and outputs in `scratchpad/picknum/B/prover/`)*

**The builder's claims, checked on the copy.** A fresh `git archive` of
8318650 and the build as left each built the 44 payloads again, WHOLE (every
sport's current slate and the 17 slates that carried a price, both
forecasters, the clock held at 12:53:33Z; `dump_payloads.py`, `analyse.py`):
40 proposal cards, 35 distinct; `combo_side_faults` 259 faults on HEAD's and
none on the build's; on every one of the 80 legs the worth less its cost and
the fee on it is its recommendation line's edge to the cent; `pick_side_faults`
and `board_price_side_faults` empty on both; the before/after list above is
what the copy gives. The builder's two plantings escape on HEAD and are
caught; 9 of its 11 tests fail on HEAD. Every sport, market and forecaster
the record proposes from was read (legs: 62 spreads, 10 totals, 8
moneylines; MLB, NFL, NBA, college football; both forecasters; no prop or
fight leg on the record -- a prop's and a fight's other side's words were read
for every stored spelling, `probe_other_side.py`, and none refuses).

**FOUND AND FIXED: A LEG NAMED NO GAME.** The proposal card draws its legs
and nothing around them -- no row, no game heading, no club colour -- and
the build named each leg in the words of the side it buys and nothing more
(8318650: its question's words, nothing more). On the copy:

- THREE PROPOSALS WHOSE TWO LEGS READ ALIKE, each with one worth for two
  contracts nobody could tell apart: the reasoning pass's "under 8.5 total
  runs + under 8.5 total runs" on MLB 165 (Rays at Braves, Astros at
  Phillies; 36.0%) and twice on MLB 166 (Diamondbacks at Royals and Twins at
  Tigers, 38.4%; Pirates at White Sox and Nationals at Padres, 34.8%) --
  drawn so on the 390px and 1300px renders of both HEAD and the build.
- TEN TOTAL LEGS IN SIX PROPOSALS named no game at all ("over 7.5 total
  runs", "under 7.5 total runs"), and SEVEN BASEBALL LEGS IN SIX PROPOSALS
  named a city two clubs share -- "Chicago covers +1.5" (the White Sox, the
  Cubs), "Los Angeles covers +1.5" (the Angels), "New York covers +1.5" (the
  Mets) -- where the club had to be guessed: MLB 165, 166, 180 (three), 181,
  182. A fight's distance or rounds leg would name no fight in the same way.

A worth has to stand under the words of the exact contracts it multiplies,
and these named none: the reading covers it. BUILT: `language.combo_leg_words`
-- a leg is its side's words and the game it is in, "under 8.5 total runs ·
Rays at Braves", the shape a prop's pick line already had ("Josh Allen over
245.5 passing yards · Packers at Bills"): the game as the board heads that
game's row ("Hooker vs Parnasse" for a fight, which has no home side), and a
prop's matchup, since a prop's row title is its player. `_proposal_card`
draws it; the side's words alone travel as `side_words` (payload). The card
draws its legs ONE TO A LINE, the plus between them in the muted ink
(`.combo-face .face-head`, `.combo-face .combo-and`): the plus had no rule and
sat against both legs ("LAD to win+BOS to win", on 8318650 too), and a leg
naming its game is a whole phrase. HELD: `combo_side_faults` works the words
out as `combo_leg_words` of the side's words and the slate's card, names a leg
drawn in its side's words alone ("without the game it is in") and a leg whose
`side_words` are another side's; the fixture's cards carry their row titles
and two more released shapes are held at import (the leg without its game,
and the other side's words with the game named). Planted:
`plant_a_combo_leg_that_names_no_game` (two unders on two games; the shipped
legs, and the planted ones in their sides' words alone). Tests:
`test_combo_sides.py::test_each_leg_names_the_game_it_is_in` (a totals
world: the two legs differ, each ending in its row's title, the check names
both planted legs) and `::test_a_leg_names_its_game_by_the_rows_title_or_a_props_matchup`.
On the copy: `combo_side_faults` names 324 faults on HEAD's 44 payloads, 80
on the build as first written (every leg of its 40 cards) and none on this
tree's; no proposal's legs read alike (`words_before_after.txt` has every
proposal's words before and after).

**THE RENDER** *(the copy served by the test server on a free local port,
the named tree's app -- this tree's, and HEAD's from its archive -- a dummy
non-secret token, never the live app on 8848; Chromium at 1300px and 390px,
the panel and each card centred; `render.py`, `render_fix/`,
`render_head/`)*: the Combos panel on NBA's current slate (drawn on the board
today: "Detroit to win · Celtics at Pistons + Philadelphia to win · 76ers at
Knicks · 38¢ · worth taking only below 34¢"), MLB 166's reasoning pass ("under
8.5 total runs · Diamondbacks at Royals + under 8.5 total runs · Twins at
Tigers · 38¢ · below 34¢", where HEAD drew "under 8.5 total runs+under 8.5
total runs · 14¢ · below 12¢ · as singles: -15.5¢ a leg"), college football
25 September ("Howard covers +24.5 · Howard Bison at Rutgers Scarlet Knights +
Navy covers -6.5 · Navy Midshipmen at UAB Blazers · 71¢ · below 65¢", where
HEAD drew "Rutgers covers -24.5+Navy covers -6.5 · 2¢ · below 1¢"), and NFL's
current slate. No page error, no sideways scroll at either width; the legs
one to a line, a college leg wrapping to two lines at 390px inside the card.
Read: every leg names its game and the side it buys, and every worth, ceiling
and singles line is those sides'.

**READ ON THE RENDER, STEP A'S (named, not changed here; `probe_nfl.py`):**
every leg on NFL's current slate is a number of the venue's contract at
ANOTHER line than its words'. "Chicago covers -15.5 · Eagles at Bears" at 86%
is Chicago -3.5's number (the claim was read at -3.5; and it was priced off
an away contract, so by question 36 its 52.5¢ is about +3.5); the model's
own number for Chicago -15.5 is 42% (its question,
"Philadelphia covers +15.5", 58%). The same for "New Orleans covers -15.5"
at 84% (New Orleans -3.5's; its own 32%), "Green Bay covers -15.5" at 80%
(-4.5's; 35%), "Seattle covers -7.5" at 85% (Seattle +7.5's; 45%),
"Cincinnati covers -7.5" at 79% (+3.5's; 40%) and "Minnesota covers -7.5" at
79% (+1.5's; 50%). The worths (63-73%) multiply the numbers the claims
carry, on the sides the recommendations buy; the words carry the question's
line. 8318650 drew
"Philadelphia covers +15.5" beside Chicago -3.5's 86% and "WAS covers +7.5"
beside WAS -7.5's 15% -- the side and the line both another contract's.
Which line a spread leg's numbers belong to is step A's (finding 2, and
operator question 36 for the four of these off an away contract), as the
builder named; the reading's "the pick names the VENUE's contract" is not
applied to a leg here for that reason. Those games are final.

**SEEN, NOT FIXED (named; none is a number on a pick of this step's):**
- The taken rail names a total the same way ("under 8.5 total runs · +11.5¢
  when marked", `language.taken_entry_words`): no game. Nothing is taken on
  the record, so nothing is drawn; and the rail's edge on a recommendation
  that buys the other side of its words is question 37's.
- At 390px the sport tabs' records run into the next tab's name ("NFL
  193-119MLB", "577-195UFC": each button's text 1-3px wider than the
  button), on 8318650 too (`render_head/top-390.png`). The header, not a
  pick.
- A doubleheader's two games are two games with one title; a combo of their
  two unders would read alike again (none on the record).
- The combos panel proposes on finished games (NFL week 3, the current
  slate, is final), as it did before this step; the Today block prices a
  finished game's question by design (`recommend.for_predictions`).

**PROVED.** The three plantings, run by this tree's `plant.py` against the
`git archive` of 8318650 (`run_plantings.py`): all three ESCAPE -- the
builder's two as before, and "the shipped combo names its legs ['under 8.5
total runs', 'under 8.5 total runs'], where they are the unders of two games,
BBB at AAA and DDD at CCC | ... the gate has no check ... | the gate's step 2
does not call ..." -- and all three are CAUGHT here (`escape_on_head.txt`,
`caught_on_fix.txt`); the new one escapes on the build as first written too
("... both legs 'under 8.5 total runs' passed", `escape_on_impl.txt`).
`tests/test_combo_sides.py`, 13: 11 fail on 8318650's package (the builder's
nine and the prover's two); on the build as first written (a scratch copy of
this tree with the two behaviour changes put back, `make_impl.py`) the new
page test and the two page tests that now ask for each leg's game fail. Gate step 2's touched rows,
dry-run with GRIDIRON_VERIFYING set on the copy (`step2_dry.py`, not
verify.py whole): 38 of 38 pass -- the builder's 26 and the stylesheet's
rows (the files parse, the bar, the motion vocabulary, the arrival, the
colour law, prices that do not move, every selector built, no tile
truncates, hidden means not painted, no club colour typed) and the no-hurry
scan of the day's words; `prose_reaching_the_raw_side()` is empty.
`plant.py` whole: 395/395 caught (the builder's 394 and this one), "Every law
has a guard, and every guard has now fired at least once", exit 0
(`plant_all.txt`, 13:21:50-13:29:38Z). The full suite, a dummy non-secret
token, TMP/TEMP at their defaults: 2258 passed, 4 skipped, none failed, exit
0 (`suite.txt`, 13:29:52-13:54:40Z; the builder's 2256 and the prover's two
tests; run with `-q` over the ini's own, so its summary line is not printed
and the count is the progress marks'); the only line under "tests that
reached the network" is the network guard's own self-test. The one copy of
the record was deleted, with its -wal and -shm, at 2026-09-30T13:30:11Z; it was
read with `db.read_only` and written only by the test server serving it
(sign-in rows). Nothing was written to the record; no network, no real
token, the live app never contacted, nothing run from the main checkout.

## An away contract is read at the line it sells -- built 2026-09-30 *(operator question 36 (i), ruled 2026-09-30 -- the order's second message, "Order: Q36.1 -> step A -> item 1 -> ..."; uncommitted for its prover)*

The ruling (`docs/REPAIR_STATE.md` question 36 (i)): "the writer -- read an
away contract at +s (the stored number as it is) from the release, with a
planting that escapes on the released code; a baseball look at an away
contract then becomes the writer's ordinary refusal." (ii) -- the 269 stored
claims and 54 recommendations -- and (iii) -- what the page draws for a row
priced off one -- are NOT ruled: nothing stored changes here, and no page
draws anything new. LAW 1 unchanged (the claim is written after the forecast
exists); LAW 3 unchanged (no row edited, voided or labelled).

A first build agent for this step ran about 25 minutes and was cut off when
its session ended (nothing run, proved or committed). Its partial change was
read whole and kept where right; what was replaced is under THE PARTIAL
BUILD below. Everything here was measured and run again by this build.

### MEASURED FIRST *(ONE verified copy of the record through `rebuild.verified_backup`, made 2026-09-30T16:04:46Z in 47 s: integrity ok, 64 tables, none mismatched; read with `db.read_only`; the released code a `git archive` of 8662205 in `scratchpad/q36/head/`; `measure.py` -> `measure.json`, `q3.py`, `mlbdist.py`, `atl_record.py`; deleted after -- see PROVED. The partial build's own copy, made 15:37Z, was deleted before this one was made)*

**What the venue sells.** The record caches 208 spread payloads with
markets; all 3,109 contracts in them are worded "<team> wins by over <s>
points" (NFL 845, NCAAF 1,555) or "... runs" (MLB 709), no other wording, and
each `floor_strike` is its words' s. `kalshi.parse_markets` stored every home
contract at -s (8,923 quotes: 4,415 near-start, 4,508 opening) and every away
one at +s (7,923: 3,826 and 4,097); every total quote is an over (15,168).
The line each contract's words sell -- "<home> wins by over s" the home side
covering -s, "<away> wins by over s" the complement of the home side covering
+s -- is its stored number for all 3,109; the released reading put 1,408 of
them (every away one) at the other sign.

**One proposition read twice.** 8,286 times a look quoted a home and an away
contract at one strike (NFL 5,237, MLB 1,614, NCAAF 1,435). Read the released
way both are "the home side covers -s": the home contract's mid and one minus
the away contract's stood 41.18 points apart on average, the same way in
99.96%, and only 32 agreed within the spread. Read at the lines they sell,
covering -s is below covering +s in all 8,286, within the spread. Of the 854
looks quoting both sides, 759 fell somewhere by more than the spread when
sorted by the released reading (3,080 steps), and none by this one.

**Every place a venue contract becomes a line and a side, and what each did
with an away contract (8662205).**
- `kalshi.parse_markets`: the side from the ticker's club, a home contract at
  -s and an away one at +s. Right, unchanged.
- `at_the_line.implied_of`: complements any price not the home side's or the
  over's. Right, unchanged; the claim, the close and the opening read price
  through it.
- `at_the_line.home_view_line`: negated an away row -- THE DEFECT, "A LATENT
  SIGN ERROR, FOUND BEFORE THE FIRST CLAIM WAS EVER WRITTEN" in its words.
- `at_the_line.rung_for`: the contract priced nearest an even chance, with no
  line; its docstring already said "the stored line is already written from
  the home side's view".
- The claim writer, `at_the_line.evaluate`: the claim's line from
  `home_view_line`, so an away rung was written at -s -- its model number the
  blind number where -s was the question's rung, else the distribution read
  at -s -- beside the complemented price, which is about +s.
- The near-start reader, `lines.refresh_venue_ladder`: asks the venue, then
  writes claims through `at_the_line.evaluate` alone (`snapshot_many` too).
  The same.
- The opening read, `views._opening_price`: the rung's price only, no line --
  right on the price; the card draws no line.
- Drift, `drift._pairs_of`: kept the opening ladder's contracts whose
  released reading equalled the claim's line -- a claim at -s matched the home
  contract at -s AND the away one at strike s, and opened at whichever was
  nearer an even chance; a claim at +s (none was stored) would match nothing.
- The closer, `recommend.close_of`: the same ticker's later near-start read,
  priced through `implied_of`. Right on either reading.
- `lines.py`: reads the media lines (`market_snapshots`, `repair_run_line_signs`
  are theirs) and the venue only through `kalshi.capture_for_predictions` and
  `at_the_line.evaluate`; it turns no venue contract into a line of its own.
- Every reader of a claim's stored line (the resolver's `spread_outcome`,
  the at-the-line sentence's `_signed`, `recommend`'s `venue_line`, the
  record's items, `recount`) reads it as the home side's line whatever its
  sign. On the released reading every stored spread claim is at or below
  zero; a claim at +s is new from this release, worded "covering +7.5".

**The claims and recommendations.** 269 of the 567 spread claims were priced
off an away contract: MLB 139 of 293, NFL 90 of 171, NCAAF 40 of 103 -- all
the statistical model's, all settled, the first written 2026-09-07T19:41:47Z
and the last 2026-09-29T00:05:02Z; none since (1,746 claims in all, as at the
first measurement). Where this reading puts each: MLB 139, stored as
rung-matched at the question's -1.5, are +1.5, another rung, with no
distribution -- refused; NFL 77 and NCAAF 34, stored rung-differs at -s, are
the distribution read at +s; NFL 13 and NCAAF 6 are the question's own line
(+s) -- the price at the question's line, the model's number at the other
sign, question 36's "19". 54 of the 113 recommendations were priced from one
(MLB 6, 8, 11, 14, 16, 20, 25, 30, 32, 34, 38-42, 44, 48, 50, 51, 53-55, 57,
59, 60, 79, 84-87, 93-98, 100, 106-109; NFL 62, 63, 66, 68-70, 73, 75, 77, 78;
NCAAF 88, 90, 91): 41 of the 69 MLB run-line recommendations. The record's
own examples: SEA at WAS was asked at +7.5 (forecast 2319, "cover" 54.8%),
and its rung, "SEA Seahawks wins by over 7.5 points", sells exactly Washington
+7.5 -- the released writer stored claim 1662 at -7.5 with the distribution
read at -7.5 (14.6%) beside 47.5%; TOR at BAL (forecast 1811, "not_cover"
66.3% at -1.5), rung "Toronto wins by over 1.5 runs", claims 612 and 613 at
-1.5 with 33.7% beside 63.5%.

**The distribution.** None of the 308 MLB spread forecasts carries a margin
distribution (235 carry the key empty, 73 lack it), and every one was asked
at -1.5; NBA none of 141; NFL 26 of 99; NCAAF 63 of 259. All 9,720 MLB games
on the record are the regular season's, the last started 2026-09-27T19:10Z,
the last MLB forecast was written 2026-09-27T05:48:42Z, and none is still to
start: FROM THE RELEASE THE BASEBALL REFUSAL STOPS NO CLAIM.

**What the fix reaches today.** Unstarted games with a spread forecast:
NCAAF 2 (8 forecasts), NBA 47 (141, the first 2026-10-20T19:00Z). Only UNT at
TLSA (2026-10-02T01:00Z, asked at +6.5) has spread quotes, and its latest
near-start look's rung (2026-09-28T15:00:44Z) and latest opening read's
(2026-09-30T05:11:42Z) are both "Tulsa wins by over 1.5 points", a home
contract: no claim or opening read on the record today reads differently. No
NBA spread quote has ever been read.

### BUILT

- **The one place.** `at_the_line.home_view_line` reads the stored number as
  it is, for each side it has a rule for (`at_the_line.CONTRACT_SIDES`: a
  home contract at -s, an away one at +s, a total's over or under at its
  number), and refuses any other side by name (`at_the_line.UnreadContract`),
  never reading it as either. Its docstring keeps what it replaced.
- **The rung carries its line.** `rung_for` adds `line` from the one place,
  so the price and the line come from one contract by one rule.
- **The claim writer** (`at_the_line.evaluate`) takes the rung's `line`: an
  away rung is written at +s with its complemented price, the question's own
  number where +s is the question's rung, the distribution read at +s where
  it is another, and -- a baseball forecast carrying none -- the writer's
  ordinary `no_distribution` refusal where it is another and none was frozen
  (the schema's `at_the_line_requires_a_frozen_distribution` behind it). The
  near-start reader writes through it and is unchanged.
- **The opening read** (`views._opening_price`) returns the line its rung
  sells beside the price. The card draws the price alone, as it did; which
  line a card names beside it is step A's.
- **Drift** (`drift._opening_at_the_claims_line`, through
  `at_the_line.quotes_selling`) sets a claim beside the opening read of the
  contract that sells its own line: a home contract at -s and an away one at
  +s are two lines, never one rung.
- **The test that asserted the negation**,
  `tests/test_at_the_price.py::test_the_venue_line_is_read_from_the_home_side`,
  asserts +3.5 for "<away> wins by over 3.5", and its words say why the old
  assertion was the error; `test_at_the_line.py`'s rung test asserts the
  rung's line.
- **The gate, by fixtures and not on the record** (a record check would fail
  on the 269 as written, which are question 36 (ii)'s; one held to claims
  written from the release would pass until the next away rung, since none
  has been written since 2026-09-29T00:05Z): `audit.contract_line_faults`
  builds a scratch world from the venue's own contracts, cut from the three
  cached payloads -- UNT at TLSA, TOR at BAL, SEA at WAS, four contracts each,
  bids and asks as cached (`audit.VENUE_SPREAD_CONTRACTS_AS_SOLD`) -- asked the
  record's own statistical final-pass questions on those games (forecasts
  3147, 1811, 2319: rung, stored side and number, frozen distribution) and one
  constructed (2319's distribution asked at -1.5). Each contract's sold line
  is worked out by hand from its words, and each question's claim from the
  fixture alone (the rung by its prices, the model's number at the line it
  sells, or no claim), never by the code under test. It names `parse_markets`
  and the one place, the rung, the claim writer (line, price, the model's
  number, or the refusal), the near-start reader (by its source: it calls
  the claim writer, and no function of the package but the claim writer
  inserts a claim -- running it would ask the venue), the opening read and
  drift. `audit.check_every_venue_contract_is_read_at_the_line_it_sells`,
  gate step 2, raises. It runs in about 1.6 s.
- **Plantings** (`tools/guards/plant.py`, `LAW_THE_CONTRACT_LINE`, in `main()`
  and in `tests/test_guards.py`'s list): `plant_an_away_contract_read_at_minus_s`
  (the one place put back to the negation; the rung carrying the negated line
  past it; the gate's call) and `plant_a_ladder_matched_across_the_two_signs_in_drift`
  (drift matched by the strike alone; by the released reading; the gate's
  call). On a package with no check (the released one) each builds the
  record's two games itself and reports what that code writes.
- **Tests:** `tests/test_away_contract_line.py`, 17.

### THE PARTIAL BUILD *(the first agent's change, read whole)*

Kept: `rung_for`'s line, `quotes_selling`, the claim writer's use of the
rung's line, drift's `_opening_at_the_claims_line`, the opening read's line,
the fixed `test_at_the_price` test and `test_at_the_line`'s assertion, the
step 2 row, the plantings' names in `main()` and the harness list.
Replaced:
- `home_view_line` worked the line out again from the side and the strike
  (`-abs(line)` for a home contract, `abs(line)` for an away one). The
  ruling's words are "(the stored number as it is)": it reads the stored
  number now. The two agree on every stored quote (home at or below zero,
  away at or above), and the check runs `parse_markets` too, so a storage
  change there is named.
- Its fixture asked questions of its own (UNT at TLSA at -6.5, SEA at WAS at
  -1.5, a distribution of its own). They are the record's own now, so the
  released code writes the record's own claims back (1662; 612 and 613).
- Its check held every claim's model number to the distribution, which a
  rung-matched claim does not read (SEA at WAS at +7.5 is one now), and took
  the rung from the code under test; both are worked out from the fixture.
- The near-start reader was said to write through the claim writer and not
  checked; it is checked by its source, and a test runs it.
- Its CLAUDE.md row carried figures from its own unproven run (the planting's
  "0.3646" came from its own world); every figure here is this run's.
- Its FOLLOWUPS section was a scratch draft never written to this file.

### EVERY NUMBER THE FIX MOVES *(both trees on the one verified copy, the clock held at 16:04:46Z: every sport's Record, learning, drift, history (latest 500) and digest payloads, the current slates and the 20 slates that carried a price or an opening read, both forecasters; `measure_moves.py` -> `m_head.json`, `m_fix.json`; `compare.py` -> `moves.json`; pair by pair, `drift_pairs.py` -> `drift_head.json`, `drift_fix.json`, `drift_compare.py`)*

1,194,726 figures compared; one moves -- MLB spread's venue drift, the
statistical model's, on the Record page's drift panel and in the scorecard's
drift block: "Between the venue's opening read and its price at the line,
and where the model disagreed by 5% or more, the price moved toward the model
29% of the time over 56 questions" -> "36 of 50 disagreements have both the
venue's opening read and its price at the line. Nothing is reported about
direction until there are enough." (The build identity's `head` differs
because the archive has no repository; not a figure.) No claim,
recommendation, price, card, combo, board figure or Results row moves. Pair by
pair:
- MLB (102 standing claims, 39 off an away contract): 56 pairs -> 36. Of the
  56, 31 were claims off an away contract and 4 more were home-contract claims
  the released matching had opened at the away contract; 20 leave (16 and
  those 4, their open now their own contract, within 5 points of the model),
  none join, and 15 opens move (all off an away contract).
- NFL (14, 6): 11 -> 11; opens move on 6 (5 off an away contract, one a
  home-contract claim opened at the away contract).
- NCAAF (46, 20): 26 -> 26, one pair off an away contract out and one in;
  opens move on 10 (all off an away contract).
- The reasoning pass has no spread claim.

### WHAT THE AT-THE-LINE RECORD'S SPREAD FIGURES INCLUDE UNTIL QUESTION 36 (ii) IS RULED

The 269 claims stay in every count, curve and pair as written. Each carries
the model's number at -s, the price about +s, and settles at -s, its stored
line: its market number is the other line's price, scored against this
line's outcome. The statistical model's settled standing spread claims (the
at-the-line record's one door, this tree):
- MLB 102, 39 of them off an away contract -- past its gate of 100, so the
  page prints the model's Brier and log loss beside the market's: 0.2085 and
  0.6075 against 0.2611 and 0.7162. On the 63 priced off a home contract they
  are 0.2245 and 0.6406 against 0.2317 and 0.6559; on the 39, 0.1826 and
  0.5539 against 0.3088 and 0.8136. The 39 make the model look far better
  than the market than the 63 do.
- NFL 14, 6 of them (under the gate): the model 0.2563 against the market
  0.2463 (0.3303 against 0.2406 on the 8 home; 0.1576 against 0.2540 on the
  6).
- NCAAF 45, 20 of them (under the gate; 46 standing with UNT at TLSA's
  unsettled home-contract claim): 0.2314 against 0.2526 (0.2853 against
  0.2533 on the 25; 0.1640 against 0.2517 on the 20).
- The hypothetical ledger (MLB 67, NFL 13, NCAAF 38 disagreements) and the
  edge (1, 8 and 8) are under their 100 and not shown. Drift's venue pairs
  are above.
Question 36 (ii)(A) would leave them out of this record by a dated rule;
(B) and (C) keep them. Nothing here chooses.

### READINGS TAKEN *(the conservative default)*

- **"The stored number as it is"** is read literally: the one place returns
  the stored line for every side it has a rule for, and the check holds the
  storage and the reading to the venue's words together.
- **"A baseball look ... becomes the writer's ordinary refusal"**: the
  `no_distribution` refusal already counted by name; nothing new refuses.
  The same reading reaches basketball, whose forecasts carry no distribution
  either (below).
- **"With a planting"**: two, the ruling's one and the task's drift one, each
  escaping on 8662205 and caught here.
- **Drift** reads the stored claims by their stored line through the one
  place, as the task orders; that moves MLB's venue-drift line (above), a
  measurement of stored rows, and no stored row.
- **The gate** is by fixtures, not on the record, and says why.

### FOR THE QUEUE, NOT BUILT *(the amended queue rule of 2026-09-30: each could show the operator a wrong number; reported, not built)*

- **The Record page's MLB spread at-the-line comparison is past its gate and
  flattered by the 39 away-contract claims** (above: the market's 0.2611 with
  them, 0.2317 without). Question 36 (ii).
- **Basketball, from 2026-10-20.** 141 NBA spread forecasts on 47 games are
  waiting, asked at rungs from -14.5 to +10.5, none carrying a distribution.
  An NBA claim is written only where the look's rung sells the question's own
  line; the released reading took an away contract at strike s for a question
  asked at -s (a claim with the model's -s beside +s's price) and refused one
  asked at +s. From the release the reverse, which is the contract's own
  line. How many NBA spread recommendations that makes cannot be counted
  before the venue lists the games.
- **A claim at +s beside a question's words at another line** (rung-differs,
  now also off away contracts) is drawn under the question's line: finding 2,
  step A, as before -- and SEA at WAS's kind (an away contract at the
  question's own line) is now rung-matched, the question's own number.
- **The opening read on a Today card** is the venue's main rung's price, its
  line not named: finding 5, step A.
- **The 269 claims, the 54 recommendations, the 37 combo legs in 22
  proposals priced off one, and THE LIST's rows priced across two contracts**:
  question 36 (ii) and (iii).

### FOUND ON THE WAY *(not a pick number, no law broken: FOLLOWUPS by the queue rule)*

- **The at-the-line curve omits every claim below 50%.** Its buckets start at
  50% (`calibration.BUCKETS`, the sub-50 rule for forecasts, which are stored
  on their confident side), but a claim is about the fixed proposition and
  is often below 50%. MLB spread's 102 settled claims all sit below 50%, so
  the category says "102 settled comparisons, past the 100 this record needs"
  beside "Nothing has resolved yet, so there is no calibration to report" --
  a count and its denial; NFL's 14 put 8 in buckets, NCAAF's 45 put 10. On
  8662205 too.

### PROVED *(`scratchpad/q36/`)*

- **The two plantings**, run alone by this tree's `plant.py` against the
  `git archive` of 8662205 (`head/`, `run_plantings.py` ->
  `escape_on_head.txt`): both ESCAPE -- "nfl asked at +7.5: a claim off 'SEA
  Seahawks wins by over 7.5 points' stored at -7.5 with the model's 0.1458
  beside 0.4750 | mlb asked at -1.5: a claim off 'Toronto wins by over 1.5
  runs' stored at -1.5 with the model's 0.3366 beside 0.6350 | no check asks
  which line a contract sells" (the record's claims 1662, 612 and 613), and "a
  claim at -1.5 opens at 0.245 (the price of 'SEA Seahawks wins by over 1.5
  points', Washington +1.5) where its own contract, 'WAS Commanders wins by
  over 1.5 points', opened at 0.195; a claim at +1.5 has no pair". Both are
  CAUGHT here (`caught_on_fix.txt`): the one place put back to the negation,
  23 faults naming the one place, the rung, the claim writer, the opening read
  and drift; the rung carrying the negated line past it, 7 naming the rung,
  the claim writer and the opening read and no other; drift matched by the
  strike alone, 6, and by the released reading, 10, each naming drift alone.
- **`tests/test_away_contract_line.py`, 17**, on a copy of this tree with the
  three readers' files -- `at_the_line.py`, `drift.py`, `views.py` -- put back
  to 8662205 (`released_readers/`): 13 fail (the three payloads' contracts,
  the same-strike pair, the one place, the claims off an away contract, the
  near-start reader, the baseball refusal, the opening read on three games,
  drift's pairs, the gate's check and call, drift across the signs named, a
  second writer named -- the last two because the released readers are named
  as well); 4 pass, holding what was right (a home contract at -s, the
  fixture's words and questions, the released one place named at every
  reader, one claim writer). All 17 pass here.
- **The full suite**: 2,275 passed, 4 skipped, none failed (a dummy
  non-secret `GRIDIRON_ACCESS_TOKEN`, TMP and TEMP at their defaults,
  16:24:05-16:48:40Z; `suite.txt`).
- **`plant.py` whole**: 397/397 caught (`plant_all.txt`, 16:49-16:57Z).
- **Gate step 2's touched rows**, dry-run with `GRIDIRON_VERIFYING` set (not
  `tools/verify.py` whole; `step2_dry.py` -> `step2_dry.txt`): 14 of 14 pass --
  the prediction closures (LAW 1), no orphan function, market sources in the
  market module, every recommendation reader through the door, no raw
  connect, no replacing write, the roster numbers, every count on the one
  key, the prompt record's one door, the new check; and on the copy, read
  only: claims priced at the line, where the line went, the at-the-line
  record's counts, the at-the-line words.
- **No render**: nothing new is drawn. The one moved figure is MLB's
  venue-drift line, in the sentence NFL's and NCAAF's already carry.
- **The copy**: made 16:04:46Z, deleted with its -wal and -shm at
  2026-09-30T17:00:20Z; never written (its -wal empty, its size and time as
  made). The partial build's copy of 15:37Z was deleted at 16:03:48Z, before
  this one was made.

### THE PROVER *(2026-09-30, alone in the worktree; one local commit. ONE verified copy of the record through `rebuild.verified_backup`, made 2026-09-30T17:11:04Z in 46.8 s: integrity ok, 64 tables, none mismatched, 1,094,451,200 bytes; read only with `db.read_only`; deleted after -- below. The released code a fresh `git archive` of 8662205 in `scratchpad/q36/head/`. Scripts and outputs in `scratchpad/q36/prover/`)*

**Every reader hunted, and what each does with an away contract on this tree.**
- `kalshi.parse_markets`: right. Of the 3,109 contracts in the record's 208
  cached spread payloads, 3,036 were placed on their game's home or away club
  by the words' club name ALONE (the teams table's names, never the ticker or
  the crosswalk); every one is stored on the side its words name, at the line
  they sell ("<home> wins by over s" at -s, "<away> wins by over s" at +s),
  and the one place reads that line; the released negation misread 1,394 of
  them, every away one. The other 73 carry the venue's own abbreviations
  ("Los Angeles R" 30, "A's" 18, "LA Rams" 14, "Louisiana-Monroe" 11), which a
  name match cannot place (`pairs.py`).
- TOTALS DO NOT SHARE THE SHAPE: all 3,011 contracts in the cached total
  payloads read "Over N points", "Over N points scored" or "Over N runs
  scored" -- no under, no club -- and are stored as the over at their number.
  A moneyline contract has no line.
- The one place, the rung, the claim writer, the opening read and drift: as
  built. The near-start reader (`lines.refresh_venue_ladder`) and the daily
  snapshot (`lines.snapshot_many`) write claims through the claim writer
  alone; no other function of the package inserts a claim.
- The closer (`recommend.close_of`) and the restatement: by the contract's
  ticker. The venue's packages (`kalshi.capture_packages`,
  `views._leg_reading`): moneyline legs only, no line. Coverage
  (`priced/coverage.py`): bid and ask widths, no line. The ranker and the
  opening-read task: whether a quote exists.
- Every reader of a claim's stored line -- the resolver
  (`questions.spread_outcome`), the at-the-line sentence
  (`language.at_the_line_side_words`), `recommend`'s `venue_line` (carried,
  drawn nowhere), the record's items -- reads it as the home side's line
  whatever its sign: right for +s ("covering +7.5").
- The board reads no venue contract and draws no claim's line; its tooltips
  (`price_tip`, the numbers line) name none. `tools/board_shots.py` writes a
  screenshot world's own home quotes at the question's line (a scratch world,
  not a reader). No fixture in `tests/` or `plant.py` stores an away contract
  at -s.
- MLB: the loader reads the regular season only (`mlb_loader.GAME_TYPES =
  ("R",)`), so no postseason game joins the record; the refusal stops no
  run-line claim until the 2027 regular season.
No reader on this tree turns an away contract at the wrong sign.

**Found and fixed here: the gate blamed the one place for a storage flip.**
The ruling's words are "read an away contract at +s (the stored number as it
is)", so the reading is exactly as right as what `parse_markets` stores. As
built, an away contract STORED at -s (or placed on the home side at -s) was
caught -- 23 faults -- but six of them named `at_the_line.home_view_line`
("... stored at -1.5 on the away side is read at -1.5") and none named
`kalshi.parse_markets`, the function that was wrong; the docstring said the
check names `parse_markets`. `audit.contract_line_faults` now compares each
contract's storage with its words first and names `kalshi.parse_markets`
for a contract stored at another line or side, and the one place only where
it misreads a contract stored as its words sell. Held by a third form of
`plant_an_away_contract_read_at_minus_s` (the storage at -s, the one place
untouched: CAUGHT only if the storage, the rung, the claim writer, the
opening read and drift are named and the one place is not -- NOT CAUGHT on
the check as first built, "refused without naming ['kalshi.parse_markets']")
and `test_away_contract_line.py::test_an_away_contract_stored_at_minus_s_is_named_at_the_storage`
(two forms, both failing on the check as first built, `prover/asbuilt/`).

**The same-strike pairs, re-derived (`pairs_rows.py`, `pairs.py`).** 8,286
pair ROWS (NFL 5,237, MLB 1,614, NCAAF 1,435: a look's home and away quote
rows at one strike) -- 6,177 distinct pairs, because the looks hold 1,661
ticker rows written twice. Read the released way, all 8,286 are one line;
the two prices 41.18 points apart on average (40.97 over the distinct
pairs), the same way in 99.96% (3 level), 32 agreeing within the spread --
the builder's figures exactly. Read at the lines they sell, none is one line,
and in all 8,286 the bid for covering -s is at or below the complemented
ask for covering +s: one rising curve within the spread, no inversion. Of the
854 looks quoting both sides, 404 have a higher line priced wholly below a
lower one (both spreads apart; 3,409 steps) sorted by the released reading,
and none at the lines sold. (The builder's 759 looks and 3,080 steps count
"falls by more than the spread" another way.)

**A dry claim-writer run over the record's quotes (`dry_writer.py`,
`dry_compare.py`).** An in-memory world made from the copy -- the 192 games
with a spread forecast and a spread quote, their 1,584 forecasts as stored
(381 spread), their 14,930 spread quotes as stored -- each game's status set
to scheduled and its score cleared in memory only, its start kept (so a quote
read after the start is still refused); then each tree's own
`at_the_line.evaluate` over the 381:
- THE FIX: 615 claims. None off an away contract at -s; every claim's line
  is its contract's stored number; 172 off an away contract (NFL 126, NCAAF
  46), each at +s; none off an MLB away contract (546 `no_distribution`
  refusals, 355 on the release).
- THE RELEASE (8662205): 806 claims, 363 of them off an away contract at -s
  (MLB 210, NFL 113, NCAAF 40). It gives back 564 of the record's 567 stored
  spread claims exactly -- line, shape, the model's number and the price --
  so the world is the record's; the other three (claims 9, 12 and 15,
  written 2026-09-07T19:41:47Z) were priced off quotes read after the first
  pitch, which both writers refuse now.
- On the 567 stored: the fix writes the 297 home-contract claims
  identically, refuses all 139 MLB away ones, and writes the 130 NFL and
  NCAAF away ones at +s with the same price (NFL 77 and NCAAF 34 the
  distribution read at +s, NFL 13 and NCAAF 6 the question's own line) --
  the builder's figures.

**Drift's venue pairs, contract by contract (`drift_check.py`).** The fix:
MLB 36, NFL 11, NCAAF 26 (as built; MLB 56 on 8662205). Every pair of a claim
priced off a home contract opens at that same contract (42). Every pair of a
STORED claim priced off an away contract -- 31 of the 73 (MLB 15 of 36, NFL
5 of 11, NCAAF 11 of 26) -- sets its near price (the away contract, about +s)
beside the home contract's opening read at -s, the line its stored model
number is about: its disagreement is one line's, its movement spans two
contracts. On 8662205 those claims' 47 pairs opened at their own contract
(the disagreement then spanning two lines) and 5 home-contract pairs (MLB 4,
NFL 1) opened at the away contract. No direction is reported in any of the
three (each under its 50), but the counts include them. A claim written from
the release opens at its own contract, since one contract sells each line.
What the 31 are is question 36 (ii): not built.

**The plantings (`run_plantings.py`).** Both ESCAPE on 8662205 (the archive
with this tree's `plant.py` copied in, `escape_on_head.txt`: the record's
claims 1662, 612 and 613 come back, and a claim at -1.5 opens at the
Seahawks' 0.245); on the check as first built the third form escapes
(`on_asbuilt.txt`); here both are CAUGHT with all five forms
(`caught_on_fix.txt`).

**The gate and the suite.** Gate step 2's rows, dry-run on this tree (not
`tools/verify.py` whole; `step2_dry.py` -> `step2_dry.txt`, 17:22-17:27Z):
the rows read out of `verify.step_2_guards`' own syntax tree, every record
row on the copy through a read-only handle, `GRIDIRON_VERIFYING` set, an
empty scratch file standing for the env file (the operator's `.env` never
read): 108 of 110 pass, none fails -- among them a claim priced at the line,
where the line went, the at-the-line record's counts and words, the priced
record, every slate's board, pick and combo checks, the side placed by the
one place, and the new check; the two schema rows were not run (no schema
changes here, and they build the release and read the record itself). No
record row fails on the 269 stored claims: the new check reads fixtures,
and every other row reads them as stored. `audit.prose_reaching_the_raw_side()`
is `[]`. `plant.py` whole: 397/397 caught (17:27-17:35Z, `plant_all.txt`).
The full suite: 2,277 passed, 4 skipped, none failed, exit 0 (a dummy
non-secret `GRIDIRON_ACCESS_TOKEN`, TMP and TEMP at their defaults,
17:35:21-17:59:59Z, `suite.txt`); the only test that reached the network
is the suite's own marked one.

**The copy**: made 17:11:04Z, read only, deleted with its -wal and -shm at
2026-09-30T17:27:56Z; never written (its -wal empty, its size and time as
made). No copy of the record remains under `scratchpad/q36`.

## Every number on a pick names the line it belongs to -- built 2026-09-30 *(pick-number step A; the queue rule as amended on 30 September, docs/briefs/2026-09-30-rulings.md; the order of 30 September's second message, "Q36.1 -> step A -> item 1 -> ..."; uncommitted for its prover)*

Findings 2 and 5 of the wrong-side fix's builder and prover, the live
pregame figure, and operator question 36's default for (ii) and (iii), which
are not ruled. The reading taken (the conservative default, recorded in
`docs/REPAIR_STATE.md`): a number on a pick is always shown under the words
of the exact contract it belongs to -- its line and its side. Where a
recommendation was priced on the venue's contract at a line other than the
question's, the pick names the VENUE's contract (the one the numbers, the
price and the size belong to) and says beside it what the model was asked;
nothing pairs one line's words with another line's numbers. A row priced
across two contracts is drawn without the price, the payout, the edge and
the size, with one plain sentence saying why.

### MEASURED FIRST *(ONE verified copy of the record through `rebuild.verified_backup`, started 2026-09-30T18:51:38Z, finished 18:52:24Z: integrity ok, 64 tables, none mismatched; read with `db.read_only`; the release before this step a `git archive` of 4422403 in `scratchpad/picknum/A/head2/`; every sport's current slate and every slate carrying a claim or an opening read -- 52 payloads, both forecasters -- built by each tree on the copy with the clock held at 18:52:24Z; `measure_lines.py` -> `m_head.json`, `m_fix.json`; `dump_payloads.py` -> `d_head.json`, `d_fix.json`; `check_payloads.py` -> `c_head.json`, `c_fix.json`; `diff_dumps.py`, `summarise_moves.py`; deleted after -- see PROVED)*

**How the line of a number is worked out** -- from the record alone, never
from the payload: the claim the page reads (the latest written before the
start for a priced row, `recommend.for_predictions`' rule; the latest written
for a live card's pregame figure), the line its model number was read at
(the claim's `line`) and the line its contract sells (the quote's stored
number, read as it is: Q36.1). A number the page drew from no claim is the
question's own, at the question's own line. The line the WORDS name is parsed
from the drawn words: the signed number after the club, turned to the home
side's view by the side the words name; a total's number.

**On 4422403, numbers under another line's words** (distinct questions over
the 52 payloads): 56 Today cards (14 priced at the venue's rung, 42 across
two contracts), 56 recommendation lines (14 and 42), 16 combo legs (8 and 8),
73 at-the-line sentences (across two contracts: a model number about one line
beside a price about another); on the current slates the board drew 4 rows
(rec 111 "North Texas -6.5 · 76% · 52c"; rec 117 "Atlanta +9.5 · 32% · 48.5c"
priced at New Orleans -2.5's contract; recs 114 and 115, below) and 3
opening reads under the question's words (UNT at TLSA: "North Texas -6.5" at
the TLSA -1.5 rung's 52c, and both forecasters' "Under 60.5 total" at the
57.5 rung's 52c). The new check (`audit.number_line_faults`) names 289
faults on those payloads.

**THE LIST -- every recommendation drawn under another line's words while it
was live: 69 of the 117 on the record.**
- *Priced at the venue's rung, another line than its words' (13)* -- the
  question's line, then the claim's, from the home side's view: NFL 64 (LV at
  NO, -15.5 / -3.5; withdrawn), 67 (ATL at GB, -15.5 / -4.5), 71 (NE at JAX,
  -9.5 / -2.5), 72 (NYJ at DET, -15.5 / -6.5), 74 (ARI at SF, -15.5 / -8.5), 76
  (LV at NO, -15.5 / -3.5), 117 (ATL at NO, -9.5 / -2.5; upcoming, 6 October);
  NCAAF 89 (HOW at RUTG, -24.5 / -41.5), 102 (RMU at BUFF, -24.5 / -28.5), 103
  (LIU at FIU, -14.5 / -35.5), 104 (TA&M at LSU, -0.5 / -8.5), 105 (HCU at UNT,
  -41.5 / -38.5), 111 (UNT at TLSA, +6.5 / -1.5; upcoming, 2 October).
- *Priced across two contracts (56)*: MLB 6, 8, 11, 14, 16, 20, 25, 30, 32, 34,
  38-42, 44, 48, 50, 51, 53-55, 57, 59, 60, 79, 84-87, 93-98, 100, 106-109 (41);
  NFL 62, 63, 66, 68-70, 73, 75, 77, 78, 114, 115 (12); NCAAF 88, 90, 91 (3) --
  question 36's 54 and the two below.
- None of the 69 was taken.

**Live pregame figures** (every shortlisted or taken spread or total whose
game started from 2026-09-09, the latest claim's number): 60 drawn under
another line's words -- 13 at the venue's rung (NCAAF 5, NFL 8), 47 across two
contracts (MLB 35, NFL 9, NCAAF 3) -- and 60 at the question's own line.

**Opening reads** (every read of a shortlisted spread or total before its
first claim): 855 at another rung than the question's -- 491 where the venue's
opening ladder listed the question's own contract, 364 where it did not --
and 75 at the question's own.

**SIX CLAIMS PRICED ACROSS TWO CONTRACTS ON GAMES STILL TO START.**
`predict:nfl` (task run 8464, 18:00:00-18:05:02Z) wrote NFL week 4's claims
with the released code, before Q36.1 was released at 18:44Z, and six are off
an away contract stored at -s: claim 1749 (forecast 3446, PIT at CLE, off
"PIT3", Pittsburgh by over 2.5), 1752 (3464, IND at WAS, "IND4"), 1755 (3482,
ARI at NYG, "ARI3"), 1761 (3517, GB at TB, "GB4"), 1780 (3565, KC at LV,
"KC5"), 1786 (3577, DET at CAR, "DET4"); two were recommended -- rec 114 (PIT
at CLE, 2 October 00:15Z: "Pittsburgh -0.5 · 62% · 52c · 1.91x · $15", the
green outline, where 62% is Pittsburgh +2.5's and 52c Pittsburgh -2.5's) and
rec 115 (GB at TB, 4 October: "Green Bay +7.5 · 41% · 50c", its line
"Tampa Bay covers -7.5 -- the model makes it 59c"). Question 36's "nothing
upcoming carries one" was true when measured (16:04Z) and is not now.

### BUILT

- **The one door for a pick's words, `views._the_contract`.** It decides which
  line the numbers on a pick belong to -- the claim's line where they are the
  claim's (`numbers_line`, set by `views._as_the_page_draws`), the latest
  claim's for a live figure, the stored recommendation's claim for the taken
  rail's edge, the rung read for an opening read, the question's own where
  they are the question's -- and `language.at_the_contract` asks the question
  again at that line on the same side (a spread's line is its subject's, from
  the home club's view), so every composer words that contract. A claim's
  numbers reaching the door without a line are refused by name
  (`language.LineNotNamed`), and so is a board block drawing a Today card's
  numbers without the card's words; `/api/week` answers 500 with the words.
- **`views._as_the_page_draws`** is the one reader of a priced entry on the
  page (the Today block, the board through it, the combos, the
  recommendation lines). `recommend.for_predictions` carries the claim, its
  contract's line and whether the two agree
  (`at_the_line.priced_across_two_contracts`), and the game's clubs; it prices
  nothing differently, and `record_for` writes what it wrote before.
- **The Today card** carries the contract's words (`question`, `line_words`),
  the line they are asked at (`words_line_asked`) and, where they moved, what
  the model was asked (`asked_words`: "The model was asked about North Texas
  -6.5 and gives it 63%."). **The board** draws the card's words beside the
  card's numbers, and the chance's tooltip says what the chance is and what
  the model was asked. **The recommendation line and a combo's leg** name the
  side bought at that line ("North Texas covers +1.5 -- the model makes it
  76c, the venue is at 52c"; "New Orleans covers -2.5"). **The live figure**
  stands under its claim's words ("North Texas +1.5 · pregame 76%"). **The
  taken rail** names its recommendation's claim's contract.
- **The opening read** asks the question's own contract (`at_the_line.rung_at`,
  read through the one place) and, where the venue's opening ladder lists
  none, reads the main rung as before and names the contract it is ("Under
  57.5 total opened at 52c · pays 1.94x", "1.94x on Under 57.5 total"; the
  board's payout tooltip: "The venue's opening read lists no contract at this
  line. At Under 57.5 total a dollar returns 1.94 times ..."). The claim
  writer's rung is not touched.
- **A claim priced across two contracts** gives the page none of its
  numbers: the model's own number for the question as asked; no price,
  payout, edge, size, side or outline, so no recommendation line and no combo
  leg (counted in `recommendations.across`, and said in the empty list's
  sentence); no opening read either; and on the face of the row and the tile
  one sentence, "Priced across two contracts before 30 September; no single
  contract carries these numbers.", with "no single contract" where the price
  would be and the longer reason in its tooltip. A live figure off one is the
  forecast's own pregame number. The at-the-line sentence states the model's
  number at its own stored line and no price.
- **A spread's tile says "on the other side" of its edge** like any other
  tile: its words name the figure's own contract now (step C held the bare
  figure for this step).
- **The gate.** `audit.number_line_faults` works the line out again from the
  record (`audit.pick_contracts`) and from the drawn words, never from the
  payload's own line fields, and names a number under another line's words on
  the board's rows and tiles, the Today cards, the recommendation lines, the
  combo legs, the taken rail and the at-the-line sentence; a claim across two
  contracts drawn with a price, or without its sentence; and an opening read
  of another rung under the question's words or unnamed.
  `audit.check_every_number_names_its_line` (gate step 2: every sport's slate,
  both forecasters, on the record's copy) raises; `NUMBER_LINE_FIXTURE_GOOD`
  and ten `NUMBER_LINE_FIXTURES_AS_RELEASED` are held at import. Step C's
  checks work out the other side's words at the card's line
  (`audit._at_the_cards_line`), and hold a spread's tile to "on the other
  side".

### WHAT MOVED *(4422403 -> this tree, the same 52 payloads; `summarise_moves.py`, `diff_head_fix.txt`: 13,562 of 315,500 figures, most of them two cards moving group and the new fields)*

- **On the current slates**: rec 111 "North Texas -6.5" -> "North Texas +1.5",
  76%, 52c, 1.94x and $15 unchanged; rec 117 "Atlanta +9.5" -> "Atlanta +2.5",
  32%, 48.5c, 2.06x unchanged, its edge "+15.0c" -> "+15.0c on the other
  side"; recs 114 and 115 "Pittsburgh -0.5 · 62% · 52c · 1.91x · $15" and
  "Green Bay +7.5 · 41% · 50c · 2.02x · $15", both outlined -> "Pittsburgh
  -0.5 · 56% · no single contract" and "Green Bay +7.5 · 60% · no single
  contract", with the sentence, no size, no outline, among the watched, and
  no recommendation line; the opening reads of UNT at TLSA: "North Texas
  -6.5" (the reasoning pass) 52c · 1.94x -> 29c · 3.51x, "Under 60.5 total"
  (both forecasters) 52c · 1.94x -> 58c · 1.71x.
- **On the past slates** (payload; a finished row draws its question's own
  number): 42 recommendation lines priced across two contracts are gone and 14
  are worded at their claim's line ("Howard covers +41.5", "Green Bay covers
  -4.5"); 25 proposed combos are gone or changed and 6 are new (legs priced
  across two contracts dropped); 73 at-the-line sentences drop their price.

### READINGS TAKEN *(the conservative default)*

- The words move to the numbers, never the numbers to the words; the model's
  own question and number are said beside the chance, in its tooltip (the
  reading's "may say beside it") and in the card's `asked_words`.
- The SIDE is the one the page already drew (the question's side, at the
  claim's line). A recommendation that buys the other side of its words
  keeps the side it had: operator question 37, not ruled.
- A claim priced across two contracts is detected by its own row (its stored
  line is not the line its contract sells), not by a date; only claims
  written before Q36.1 are.
- The opening read reads the question's own contract where listed; where not,
  the main rung, named. A winner market has no line and reads as before.

### NOT HERE, AND NAMED

- **Operator question 37, now on a game still to start**: rec 117 (ATL at NO,
  6 October) buys New Orleans -2.5, and the row, now "Atlanta +2.5 · 32% ·
  48.5c", still wears New Orleans -2.5's "$15 · one flat unit" and the green
  outline (its edge says "on the other side"). Which contract such a row
  headlines is question 37's.
- **Question 36 (ii)**: the stored rows -- the 275 claims priced across two
  contracts (269 and the six above) and the 56 recommendations -- are as
  written, and the at-the-line record's spread figures still count them.
- **The writer.** `record_for` still prices from the latest claim before the
  start. The four other claims of 18:05Z (forecasts 3464, 3482, 3565, 3577,
  early passes, not recommended) would be read by a later pass over those
  forecasts until a newer claim is written; the near-start reader writes a
  claim at each look, through Q36.1's reading, so a newer one normally stands
  first. Changing what the writer writes is outside this step (FOLLOWUPS, for
  question 36 (ii)).
- **The reasons beside a moved pick** are the forecast's own ("the question
  sits 4 points above what the model expects", about the question as asked);
  the line's tooltip now names that question first ("The model was asked
  about North Texas -6.5 and gives it 63%. Mostly it comes down to ..."),
  found reading rec 111's render. The Why sentences themselves are not
  re-worded for the venue's line.

### THE RENDER *(the ONE verified copy served by the test server on a free local port with this tree's app and a dummy, non-secret token -- never the live app on 8848; Chromium at 1300px and 390px; `render_rows.py` -> `render/rows-fix.json`, `render/*-fix-*.png`, and the same from the `git archive` of 4422403 -> `render/*-head-*.png`; the copy took the test server's sign-in rows and nothing else)*

- **Rec 111 (UNT at TLSA)**, the row and the open row's tile, at both widths:
  "MODEL'S PICK · NORTH TEXAS +1.5 · 76% · 52c · 1.94x · $15 · one flat unit,
  measured and NOT ahead ...", the tile "North Texas +1.5 · 76% · +22.5c ·
  1.94x", the price tick at 51.5c on the bar; the chance's tooltip "The
  statistical forecaster's chance for this contract, 76%, read from the
  forecast it wrote before any price was seen, at the venue's line. The model
  was asked about North Texas -6.5 and gives it 63%." On 4422403 the same row
  read "NORTH TEXAS -6.5 · 76% · 52c · 1.94x".
- **Rec 114 (PIT at CLE) and rec 115 (GB at TB)**: "PITTSBURGH -0.5 · 56% · no
  single contract" and "GREEN BAY +7.5 · 60% · no single contract", no
  outline, no size, the sentence in the method note's quiet italic under the
  pick and on the tile ("... no single contract · not recorded" in the tile's
  price and payout slots); the price slot's tooltip gives the longer reason.
- **Rec 117 (ATL at NO)**: "ATLANTA +2.5 · 32% · 48c · 2.06x · $15" with the
  green outline, the tile's edge "+15.0c on the other side" -- the size and
  outline New Orleans -2.5's (question 37, above).
- No page error, no sideways scroll at either width. (The first 390px captures
  of the NFL rows caught a row under the sticky header and one mid-fade; the
  capture was redone with the row centred and its fade finished -- the
  picture's wait, not the page's.)

### PROVED *(`scratchpad/picknum/A/`)*

- **The measurement's own tool on this tree** (`m_fix.json`): 0 numbers under
  another line's words on the 52 payloads (4422403: the figures above).
- **The new check** (`check_payloads.py`): 289 faults on 4422403's payloads,
  0 on this tree's (`c_head.json`, `c_fix.json`).
- **The three plantings** (`run_plantings.py`): each ESCAPES on the `git
  archive` of 4422403 with this tree's `plant.py` copied in -- the shipped
  row "North Texas -6.5 · 76% · 0.515", the card "52c · pays 1.94x" under
  "under 60.5 total points", the row "Pittsburgh -0.5 · 62% · 0.525", sized
  and outlined, and no check (`escape_on_head.txt`) -- and is CAUGHT here
  (`caught_on_fix.txt`).
- **`tests/test_every_number_names_its_line.py`, 15**: all fail on the
  archive of 4422403 (`tests_on_head.txt`), all pass here.
- **`plant.py` whole**: 400/400 caught, 20:00:39-20:08:41Z (`plant_all.txt`).
- **The full suite**: 2,292 passed, 4 skipped, none failed, exit 0 (a dummy
  non-secret `GRIDIRON_ACCESS_TOKEN`, TMP and TEMP at their defaults,
  20:10:21-20:35:28Z, `suite2.txt`); the only test that reached the network
  is the suite's own marked one. (A first run, `suite1.txt`, failed three
  tests because files were edited while it ran -- two board fixtures updated
  mid-run and `inspect.getsource` reading `audit.py` after its lines moved;
  each passed alone, and the clean run above is the record.)
- **Gate step 2's rows**, dry-run on this tree with every record row on the
  copy through a read-only handle, `GRIDIRON_VERIFYING` set and an empty
  scratch file for the env file (not `tools/verify.py` whole; `step2_dry.py`
  -> `step2_dry.txt`, 20:35:44-20:40:30Z): 109 of 109 pass, the new check
  among them on every sport's slate for both forecasters; the two schema
  rows not run (no schema changes here). A first run had named a raw subject
  in the new opening-read refusal's words ("the side, in prose, anywhere");
  the words no longer carry it.
- **The copy**: made 18:52:24Z, read only except the test server's sign-in
  rows during the render, deleted with its -wal and -shm at
  2026-09-30T20:40:37Z. No copy of the record remains under
  `scratchpad/picknum/A`.

### THE PROVER *(alone in the worktree, 2026-09-30; ONE verified copy of the record through `rebuild.verified_backup`, started 20:49:25Z, finished 20:50:12Z: integrity ok, 64 tables, none mismatched; read through `db.read_only`, written only by the test server's sign-in rows during the render; step A as first built snapshotted to `built/` and 4422403 archived to `head/`; everything in `scratchpad/picknum/A/prover/`)*

**How it was hunted.** Every slate that carried a claim or an opening read
and every sport's current slate, both forecasters -- 52 payloads -- built by
this tree on the copy in three readings (`dump.py`): as the record holds
them; THE TIME MACHINE, every game read as still to start
(`views.card_state` answering "upcoming" inside the dumping process;
nothing written), so each priced row the record ever held is drawn as it
was before its start, with its claim (the latest before the start), its
opening read, its recommendation line and its combo legs; and every finished
game read as being played, so each live pregame figure is drawn. And the
early passes' pages, in the second reading. Two checks read every payload:
the gate's own (`audit.number_line_faults`, `gatecheck.py`) and one written
apart from it (`independent.py`), which reads the club and the signed
number, or over or under and the number, from the drawn words alone, turns
them to the home side's view, and holds each NUMBER to the contract its
words name -- line, side and value: each priced row's chance and price
against its claim, each Today card's model and venue chips, each
recommendation line's two numbers, each combo leg's worth and cost, each
opening read's price against the look's contract at the line it names, each
live figure's line against the latest claim, and a finished card's figure
and verdict against its claim's settled outcome.

**What step A built holds.** In the time machine: 135 priced board blocks,
47 Today cards that clear the bar, 47 recommendation lines, 32 combo legs,
158 opening reads and 111 rows priced across two contracts drawn with no
price -- none under another contract's words, by either check (on 4422403
the independent check names 531 and the gate's 710).

**FOUND AND FIXED**, each measured on step A as first built (`built/`;
`checks_built.txt`, `moved.py`):
- **A finished game's card is still priced** -- `recommend.for_predictions`
  skips a game in play, not a finished one -- so its card in CLEARS
  (payload; the board's finished row is the settled group's card, the
  question's own) named the claim's contract and carried the claim's chance,
  and said "the model had this at 67% and it happened" of the QUESTION:
  "New York covers +6.5 · 30c · the model had this at 67% and it happened",
  where 67% is New York +15.5's and New York did not cover +6.5 (DET 31-24).
  12 cards (NFL week 3 and NCAAF), 3 with the other verdict (forecasts 2317,
  2330, 2808). The figure is the chance the card shows now, and the verdict
  its claim's, settled at the claim's own line and turned to the side the
  words name (`views._claim_outcome_on_the_words`); a claim not settled
  says so.
- **The forecast's own sentences beside words moved to the claim's line.**
  The Today card's numbers line ("The model says 63%. The market implies 36%
  -- 27 points apart.") and why block ("Why North Texas", "The market has
  North Texas at 36%") stood bare beside "North Texas covers +1.5" (payload;
  14 questions, recs 111 and 117 among them); and a live row's reasons
  tooltip, the forecast's, spoke of "the question" -- New York +15.5's "the
  question sits 2 points above what the model expects" -- under "New York
  +6.5 · pregame 30%" (drawn; 12 questions on the finished slates read as
  live): the prefix naming the question was asked only of a priced chance.
  Each names the question it is about now: "For North Texas -6.5, as the
  model was asked: The model says 63%. ..." (`language.as_the_model_was_asked`),
  "Why North Texas -6.5, as the model was asked"
  (`language.why_heading_as_asked`), and on a live row "The model was asked
  about New York +15.5 and gives it 67%. ..." first.
- **A row priced across two contracts left its payout slot empty**, and a
  tile draws an empty payout "not recorded" -- "56% · no single contract |
  not recorded" on the tiles of recs 114 and 115, at both widths (step A's
  own render read it and passed it) -- false of a price the venue listed and
  the record kept. It says "not shown" (`language.across_two_contracts_pays_words`),
  the sentence beneath it and its tooltip why (42 questions' rows in the time
  machine, recs 114 and 115 on the current slate).
- **The check refused a true drawing.** It demanded the sentence of every
  live tile beside a claim priced across two contracts, where the page draws
  the sentence with the Today card's figure; a live tile with no Today card
  -- the other forecaster's question on an open row, or one off the
  shortlist -- draws the question's own pregame figure under its own words,
  which is what the default asks. 196 faults on the record's finished slates
  read as live (138 on the reasoning pass's pages, 58 on the model's); on the
  current slate the gate's step 2 would have failed during PIT at CLE (2
  October 00:15Z) and during IND at WAS, ARI at NYG, GB at TB, KC at LV and
  DET at CAR. It asks the sentence where the Today card carries the figure,
  as it already did of an upcoming row.
- **The check read an opening read against the first read of a contract in
  an unordered look.** A look holds some tickers written twice at two prices
  (DET7 at 54.5c and 53.5c in one NFL week-1 look); the page reads the first
  it meets. On the record the two orders agreed; the check now holds the
  read to any read of the question's contract in the look.
- The check now also names a finished card's figure or verdict, a numbers
  line, a why heading or a row's reasons tooltip that does not name the
  question beside words moved to the claim's line, and an across row's price
  or payout slot that does not say so; `NUMBER_LINE_FIXTURES_AS_RELEASED` has
  fifteen shapes, and the good fixture a finished card and a live tile off
  the shortlist beside an across claim. On the first-built payloads it names
  60 (as held), 180 (the time machine) and 62 (as live); here none.

**WHAT MOVED** (step A as first built -> this tree, the same readings): as
held, 48 of 230,192 figures -- 16 numbers lines and 16 why headings on
Today cards, 12 finished cards' settled words and 4 across rows' payout
slots (recs 114 and 115, row and tile); in the time machine 77 of 184,062
(45 payout slots, 16 and 16); as live 49 of 173,202 (12 live rows' reasons,
the Today cards' lines and headings, 4 payout slots). Nothing else on the
board moved.

**NOT HERE, AND NAMED** (for the operator; no question -- the words are
true of their numbers):
- **A pick drawn at the venue's contract settles, on the board, at its
  question's.** Rec 111 reads "North Texas +1.5 · 76% · 52c · $15" before
  its start; once finished its row is the settled group's card, the forecast
  graded on its own question -- "North Texas -6.5 · the model had this at
  63% and it ..." -- and a taken pick's My day chip moves from the one to
  the other with it; the claim's own verdict is on the Today card in CLEARS,
  payload only. Which contract a finished pick is read as is a companion to
  question 37; nothing on the record is taken.
- **Props.** The checks read spreads and totals; no prop claim is on the
  record and no venue prop series is read. `at_the_contract` would word a
  prop at its claim's rung; a check over props would need a half-unit
  prop's words ("no home run") read.
- **Claims written in one second.** 11 questions hold two or three claims
  stamped in one second at different lines (a near-start pass writing
  several looks at once); `for_predictions`, the live figure and the check
  take the higher number, and `views._at_the_line` keeps the last row of an
  unordered read -- on the record, the same one.

**PROVED** *(`scratchpad/picknum/A/prover/`)*:
- **The four plantings** (`run_plantings.py`): each ESCAPES on the `git
  archive` of 4422403 with this `plant.py` copied in -- no check
  (`plant4_head.txt`); on step A as first built the builder's first two are
  caught, and the across planting (its new payout-slot form) and the prover's
  ESCAPE -- the shipped finished card "the model had this at 63% and it did
  not" under "North Texas covers +1.5", the three forms passed, the live
  tile refused (`plant4_built.txt`); all four are CAUGHT here
  (`plant4_fix.txt`).
- **`tests/test_every_number_names_its_line.py`, 21**: the prover's six fail
  on step A as first built (`tests_on_built.txt`); all pass here.
- **`plant.py` whole**: 401/401 caught, exit 0, 21:23:45-21:31:56Z
  (`plant_all.txt`).
- **Gate step 2's rows**, dry-run on this tree (`step2_dry.py`, not
  `tools/verify.py` whole): every record row on the copy through a read-only
  handle, `GRIDIRON_VERIFYING` set, an empty scratch file for the env file:
  109 of 111 pass, none fails, the two schema rows not run (no schema change
  here), 21:24:34-21:29:27Z (`step2_dry.txt`). `audit.prose_reaching_the_raw_side()`
  is empty.
- **The full suite**: 2,298 passed, 4 skipped, none failed, exit 0, with a
  dummy non-secret `GRIDIRON_ACCESS_TOKEN` and TMP and TEMP at their
  defaults, 21:32:49-21:58:02Z, no file edited while it ran (`suite.txt`);
  the only test that reached the network is the suite's own marked one.
- **The render** (`render.py`: the copy served by the test server on a free
  local port with this tree's app, never the live app on 8848, a dummy
  non-secret token; Chromium at 1300px and 390px; `render/`, read): rec 111
  "NORTH TEXAS +1.5 · 76% · 52c · 1.94x · $15", its line's and chance's
  tooltips naming North Texas -6.5 at 63%; recs 114 and 115 "PITTSBURGH -0.5
  · 56% · no single contract · not shown" and "GREEN BAY +7.5 · 60% · ...",
  the sentence beneath, the tile's payout chip "not shown" where it read "not
  recorded"; rec 117 "ATLANTA +2.5 · 32% · 48c · 2.06x · $15" with the green
  outline and the tile's edge "+15.0c on the other side" (question 37); and,
  the time machine in the server process only, NYJ at DET under way -- its
  tile "New York +6.5 · pregame 30%", its reasons tooltip opening "The model
  was asked about New York +15.5 and gives it 67%." (the row's "no score has
  been read yet" is the reading's, the game's record holding a final score and
  no live one). No page error and no sideways scroll at either width.
- **The copy**: made 20:50:12Z, read only except the test server's sign-in
  rows during the render, deleted with its -wal and -shm at
  2026-09-30T21:58:18Z. No copy of the record remains under
  `scratchpad/picknum/A`. Nothing was written to the live record; no network
  but the suite's own marked test; the live app on 8848 and `.env` untouched.

## The close window: every game is read until its listed start -- built 2026-09-30 *(GRIDIRON_REPAIR item 1; the operator's ruling of 30 September, docs/briefs/2026-09-30-rulings.md; the re-read's item 1 PARTLY and its F3, docs/closeouts/2026-09-29-the-re-read.md; built fresh on 747a6c7, the partial build on `item1-held` read as a reference only; uncommitted for its prover)*

The ruling: "Item 1 (close window): first after the wrong-side fix. The
near-start run keeps every game until its start, so the close is the last
read before the start. Measure read-only first whether NFL and NCAAF closes
show the same 35-minute gap. Must be released before 15 October; if it can't
be, tell me." Built on 30 September after Q36.1 and step A (the order's
second message); nothing in it stands in the way of a release well before
15 October.

### MEASURED FIRST *(ONE verified copy of the record through `rebuild.verified_backup`, 2026-09-30T22:48:13Z to 22:48:59Z: integrity ok, 64 tables, none mismatched; read only through `db.read_only`, the clock held at 22:48:13Z, the copy's newest task row 22:48:01Z; scratchpad `item1/v2/m01_shapes.py` to `m09_minute.py`, outputs beside them)*

Every close the repaired closer wrote (`recommendation_closes.restated` = 0;
item 1 on master from 2026-09-24T06:49:12Z) against every firing of the pass
inside its recommendation's window -- the near-start task and the refresh
task, which runs the same pass: 332 firings since item 1 (291 near-start,
72 'ok' and 219 'noop'; 41 refresh). A firing asked for a recommendation
when near-start reads of its game were written during that run, or when the
venue answered nothing at all to a firing whose payload asked for it; a
firing whose payload asked for fewer recommendations than were open in its
window, and which wrote no read of a game, left that game out. No close has
been written since 29 September 00:35:01Z, so these are the figures the
first build measured at 14:42Z, measured again.

| sport | closes since item 1 | measured | unmeasured | measured closes on the last firing's read | minutes out, measured closes | (recommendation, firing) pairs inside a window | left out |
|---|---|---|---|---|---|---|---|
| MLB | 30 | 19 | 11 (56-61, 79-83) | 5 of 19 | 5.0 (86, 94); 9.7-9.9 (84, 93, 106); 34.5-35.0 (the 14: 85, 87, 92, 95-101, 107-110) | 116: 64 read its own contract, 38 asked when the venue answered nothing (24 September) | 14, by nine firings, every one five minutes before the listed start |
| NFL | 13 | 12 | 1 (67) | 12 of 12 | 10.0 (65, 78); 15.0 (77); 20.0 (76); 24.9-25.0 (68-73); 30.0 (74, 75) | 50: 48 read its own contract, 2 asked when the venue answered nothing | none |
| NCAAF | 8 | 8 | 0 | 7 of 8 | 24.7-25.0 (88-91, 102, 104, 105); 49.0 (103) | 33: 32 read its own contract, 1 read the game and the venue's answer held no quote of the contract (103, 25 minutes out) | none |
| NBA | 0 (112, 113 open, starting 20 and 21 October) | | | | | | |
| UFC | 0 (no UFC recommendation has been written) | | | | | | |

**NFL AND NCAAF DO NOT SHOW THE 35-MINUTE GAP.** Every NFL close and seven of
eight NCAAF closes are the read of the last firing before the start, 10 to 30
minutes out as the schedule gives (below). NCAAF rec 103 closed 49 minutes
out because the firing 25 minutes out read its game and the venue's answer
held no quote of its contract -- the rule's fallback, not a selection. Every
(recommendation, firing) pair inside a window was asked for in NFL and in
NCAAF.

**THE 14 (all MLB, all on 25-27 September).** Run 3504 (25 Sep 22:35:01Z,
rec 92), 3525 (23:05, 85), 3568 (26 Sep 00:05, 87 and 95), 3633 (01:35, 96),
4431 (20:05, 97), 4561 (23:05, 98 and 99), 4625 (27 Sep 00:35, 100), 4669
(01:35, 101 and 107) and 5405 (19:05, 108, 109, 110). Eight of them wrote 38
to 230 near-start reads of the games they did ask for, and none of these;
4669 asked for nothing (both open recommendations were the two left out).
Each of the 14 closed on the read 35 minutes out (34.5 to 35.0). MLB was
asked five minutes out four times (57 and 59 on 24 September, when the venue
answered nothing; 86 and 94 on 25 September) and at every other lead every
time.

**WHY -- THE SELECTION RULE, AND WHAT IS INFERRED.** `tasks._near_start_
snapshots` kept a recommendation only while `g.status IS NULL OR g.status IN
('scheduled', 'pre')` (the table's CHECK admits 'scheduled', 'in' and
'final'; 'pre' was never stored) and its listed start, compared as text, was
in (now, now + 2h]; a drift row only while 'scheduled'; and the claim writer
(`at_the_line.evaluate`) refused a game whose status was anything else
whole. The live poller maps statsapi's `abstractGameState` 'Live' to 'in'
(`live.MLB_STATES`) and opens its window ten minutes before a listed start
(`live.WINDOW_LEAD`); the league's feed gives a game in its warm-up 'Live'.
At each of the nine firings the MLB poll ten minutes before the start
(hh:m0:0x) saw the new games and changed 3 to 8 -- and `live.apply_event`
counts a game only when its status, score, period or clock changed, so a
game still in 'Preview' newly in the window is not counted -- while on 24
September the polls before 18:05 and 19:05 changed none, and those firings
asked for 57 and 59. Not every game warms up by then: the 23:30:02Z poll on
25 September changed 8 and the 23:35 firing still asked for 86 and 94. The
record keeps only a game's current status, so "left out because it was
marked 'in' in its warm-up" remains inferred -- from the release, each
firing names every forecast it reads while its game says 'in' or 'final'
(`near_start_marked_under_way`), so the next one is seen. NFL is not polled
live (`live.LIVE_SPORTS` is college football and baseball) and its loader
writes 'scheduled' or 'final' only; ESPN's feed, which college football is
polled from, keeps a game `STATUS_SCHEDULED` until kickoff, and only its
`STATUS_DELAYED` and `STATUS_RAIN_DELAY` map to 'in' before it (no NCAAF
recommendation was left out by a firing) -- which is why neither sport shows
the gap.

**THE UNMEASURED.** MLB 56-61 and 79-82 and NFL 67: on 24 September all 17
firings that asked the venue got 0 prices back (the re-read's F4); 83 and 67
started while the machine was off (no firing in 83's window; 67's last two
firings did not run). None of them was left out by a firing.

**A START STORED TO THE MINUTE (`m09_minute.py`).** Every 2026 UFC start is
stored to the minute ("2026-12-13T02:00Z"), every other sport's to the
second, and every read, claim and look to the second. As text, a read in the
start's own minute after it sorted before it. On the copy no near-start look,
venue read or claim exists on a game whose start is stored to the minute
(no UFC recommendation, no UFC drift row), so nothing on the record was
taken that way; latent. And every one of the record's distinct starts is
read by `db.instant`.

### BUILT

- **`db.instant`**: a stored instant as an aware UTC datetime, to the second
  or to the minute as stored; None for nothing stored; an unreadable stamp,
  or one that names no zone, refused by name (`ValueError`), never taken for
  "no start" and never guessed into UTC. The parse the pass, the claim writer
  and the close read, so they agree with operator question 35 when it lands.
- **`tasks._near_start_selection(conn, now)`** is what every firing reads:
  every drift row and every open, standing recommendation
  (`recommend.not_withdrawn`) whose game's LISTED START is after `now` and
  within `NEAR_START_HOURS`, as instants, WHATEVER THE GAME'S STATUS SAYS.
  `_near_start_snapshots` asks it; the noop line counts the same window
  (`tasks._games_starting_within`, every game whatever its status, where it
  counted games still 'scheduled'). `audit.RECORD_READERS`' entry moved to
  it, dated.
- **The payload names the status** (`near_start_marked_under_way`, on the
  near-start task's and the refresh task's rows): each forecast a firing
  read while its game said 'in' or 'final', with the game, the status and
  the listed start. The one new key; nothing that reads a payload reads it.
- **`at_the_line.evaluate`**: its status refusal is gone; a read taken
  before the listed start is claimed whatever the status, and one at or
  after it never (`quote_after_first_pitch`), as instants. Without this the
  read five minutes out on a game in its warm-up would be taken and claim
  nothing. (`game_under_way` stays in its counts, at zero.)
- **`recommend.close_of`**: the pricing claim is the latest written by the
  recommendation's stamp and before the start, and the close the last
  near-start read of its own contract after the pricing read and before the
  start -- every comparison an instant, the id breaking a tie as the text
  order did; `record_closing_prices` closes once the start instant has
  passed; `_minutes_between` reads instants. As text, a start stored to the
  minute sorted a read thirty seconds after it before it: the pass read the
  game then, the claim writer claimed the in-play read, the close took it,
  and `_minutes_between`, parsing to the second, raised -- which would have
  stopped the closer, and with it every near-start firing of every sport
  (the closer runs first), at the first UFC recommendation with a measured
  close, until fixed by hand.
- **Tests.** `tests/test_near_start_reads.py`, the close-window block (12,
  14 with the statuses): a game read until its listed start whether
  scheduled, 'in' or 'final' and named in the payload when not scheduled;
  never at or after it, nor further out than the window; a start to the
  minute read as an instant; a withdrawn recommendation still not read; a
  drift row of a game marked 'in' given its look; the noop line counting it;
  the firing writing its claim on a game in its warm-up (the shipped reader
  and claim writer, the venue a stub); the fourteen's shape end to end (the
  close is the read five minutes out, +9.0c, 5.0 minutes); of reads held 35
  and 5 minutes out, at the start and after it, the close the one five
  minutes out; a read in the start's own minute after it never the close;
  the closer waiting for a start to the minute; `db.instant` itself.
  `tests/test_at_the_price.py`, 3 (15 with their cases), replacing
  `test_no_claim_is_written_on_a_game_already_under_way`, which pinned the
  status refusal the ruling removes: a game marked 'in' or 'final' claimed
  before its listed start; no claim at or after it whatever the status (to
  the second, and to the minute: at it and thirty seconds after); a read in
  the minute before a start to the minute claimed. Every clock is held
  (`_hold`: `db.utcnow` and the name each market module imported); no
  wall-clock read, sleep or fixed wait added. On 747a6c7 (`git archive`, the
  two files laid over it): 12 of the 14 near-start cases fail and 13 of the
  15 claim cases; the four that pass there hold what was right -- the close
  on reads the record already holds, the closer waiting, and a read at or a
  second after a start stored to the second on a scheduled game.
- **Plantings** (`tools/guards/plant.py`, in `main()` and in
  `tests/test_guards.py`'s list; `LAW_THE_CLOSE`; the clock held at each
  firing and the venue a stub, `_HeldFirings`; the near-start reader, the
  claim writer and the closer the shipped ones):
  `plant_a_game_marked_live_before_its_start_left_out` (a total and a
  moneyline recommended on games marked 'in', one on a game marked 'final',
  and a drift row on a game marked 'in', five minutes before the listed
  start: all four asked, the moneyline's read claimed, the media look taken,
  each named with its status), `plant_a_close_from_a_read_before_the_last_
  one_before_the_start` (the fourteen's shape end to end: priced that
  morning, 50c at the firing 35 minutes out, marked 'in', 55c on offer five
  minutes out -- the close must be the 55c read; and a second game's held
  reads 35 and 5 minutes out, at its start and a second after, closed on the
  one five minutes out), `plant_a_read_after_a_start_to_the_minute_taken_as_
  before_it` (a start stored to the minute, 89c on offer thirty seconds after
  it). ALL THREE ESCAPE on 747a6c7 (`run_plantings.py` over its `git archive`
  with this `plant.py`): "the venue was asked for [] (of [1, 2, 3, 4]), the
  media looked at for [] (of [4]), 0 claim written on the moneyline's read,
  and the payload named nothing"; "closed on 0.5 (4.0c) from the read at
  2026-09-27T18:35:01Z, 35.0 minutes out, where the venue answered 55c five
  minutes out (that firing asked for nothing)"; "the venue was asked 1
  time(s) thirty seconds after the start, 1 claim(s) written off that in-play
  read ... the pass stopped: ValueError: time data '2026-09-27T02:00Z' does
  not match format '%Y-%m-%dT%H:%M:%SZ'" -- and all three are CAUGHT here.

### BEFORE AND AFTER *(the copy; the fixed `close_of`, read-only; `m06_before_after.py`, `m07_check.py`)*

**No close on the record moves.** The fixed `close_of` gives every one of the
106 closes again unchanged -- the same pricing read, closing read and price
(51 since item 1: MLB 30, NFL 13, NCAAF 8; and the 55 restated MLB closes).
By the fixed rule every one of the 14 would have been asked at the firing
five minutes out (it reads the listed start alone, and each was open, not
withdrawn and inside the window); but THE VENUE WAS NOT READ AT ALL for
their games at those firings, so the read that would have been the close was
never taken and cannot be recovered from the record. The only reads of their
games after the closing read and before the start are that same firing's
other ladders one second later (98: 13, 100: 13, 108: 2). The 14 stand as
written, their CLV as recorded (92 +0.0c, 85 -2.5, 87 +2.5, 95 +0.0, 96
+2.0, 97 -2.5, 98 -3.0, 99 +0.0, 100 -1.5, 101 +5.0, 107 +0.5, 108 -2.5, 109
-4.5, 110 +5.0), each still the last read taken before its start (the rule
held; the price is earlier than the ruling means). Baseball's regular season
is over, so no MLB close is waiting; NFL's and NCAAF's closes did not have
the gap. From the release, a game in its warm-up, 'in', delayed or anything
else is read on every firing until its listed start, and its close is the
last of those reads. What the page and the record say about closes is
unchanged in shape: no column, table, Record-page payload key or word was
added (the one new key is the near-start run's own payload), and the schema
is untouched.

### THE SCHEDULE *(read-only: `tools/schedule_install.ps1`; `m08_schedule.py`)*

`Gridiron-NearStart` fires every 30 minutes from 00:05 local -- on the record
289 of its 291 firings since item 1 started at :05 or :35 UTC -- and
`Gridiron-Refresh`, which runs the same pass, on the hour every four hours
(01, 05, 09, 13, 17, 21Z). The last near-start firing before a listed start
is therefore (minute - 5) mod 30 minutes before it, 30 where that is 0 (a
firing at hh:05:01 is after an hh:05 start). For the 2026 games on the
record: NCAAF 25 minutes for 850 of 892 (starts on :00 and :30); NFL 25 for
161 of 272, 10 for 33 (:15), 15 for 20 (:20), 20 for 36 (:25), 30 for 22
(:05); MLB 5 for 1,403 of 2,430 (:10 and :40), 10 for 362 (:15 and :45), 30
for 430 (:05 and :35), 2-3 for 153, 15 for 63, 25 for 18, 7 for 1; NBA 25
for all 1,200 and UFC 25 for all 517. Of the games still to start on the
copy: NCAAF 547 of 561 at 25, NFL 136 of 224 at 25 (17 at 30, 28 at 10, 16
at 15, 27 at 20), NBA all 1,200 and UFC all 59 at 25.

**THE SCHEDULE IS NOT MOVED (the reading taken, the conservative default).**
The ruling defines the close as the last read before the start and has the
run keep every game until then; it names no lead, and the schedule gives a
last read before every start. Moving it would be a change the ruling does
not name, so nothing is built in the installer. For the operator, not a
question: after this fix a college, NBA or UFC close -- and most NFL ones --
will be the read 25 minutes before the start, as NFL's and NCAAF's already
are; if he wants the last read nearer the start, that is one trigger line in
the installer (firings at :25 and :55 would put every :00 and :30 start 5
minutes out, a :05 start 10 and a :10 start 15; every 15 minutes would put
every start 15 or nearer at twice the no-op rows) and his to rule.

### NOT HERE, AND NAMED

- **A game that really starts before its listed start** is now read, and its
  reads claimed, until its listed start, so its close could be an in-play
  read: the status refusal this removes stood against that (its comment
  named a doubleheader's second game). The record cannot say how often a
  game starts early (the status history is not kept); from the release the
  payload names every read of a game marked under way, so it can. A live row
  draws no price, so no number on a pick moves with it: the close and the
  at-the-line record are measurements, FOLLOWUPS rather than the queue. And
  the check stood only while the live poll could see the game, which opens
  ten minutes before a listed start (`live.WINDOW_LEAD`); before that a game
  started early read 'scheduled' and was read on every release. The one
  doubleheader of the record's September whose games are listed together
  (BAL at NYY, 25 September: 20:05Z and 20:10Z) points the other way: its
  second game's listed start is earlier than it was played, so the pass
  stops reading it early, as it always did.
- **Other starts compared as text** are operator question 35's (next in the
  order): the at-the-line door's window (`at_the_line.standing_claims`,
  `c.created_utc < g.kickoff_utc`), `recommend.for_predictions`' claim
  window and `correction_instant`, `tasks._opening_read`'s horizon (and its
  'scheduled' filter), the catch-up's missed-slate reads
  (`tasks._record_missed_slates`, `_missed_slate`), `live.open_windows`,
  the forecast passes' standing clause, and the schema trigger
  `recommendation_close_is_a_later_read_of_its_own_contract` -- which, as
  text, admits a superset of what the fixed `close_of` takes (a read in a
  minute-start's own minute after it), so it never refuses a close the rule
  now writes. This change reads instants where the ruling reaches: the
  near-start selection, its claims and the close.
- **A read the venue answered without the recommendation's own contract**
  (rec 103) falls back to an earlier read, by the rule; not this ruling's.

### THE CHECKS

- **Gate step 2's rows**, dry-run on this tree on the copy (`step2_dry.py`,
  not `tools/verify.py` whole): every record row through a read-only handle,
  `GRIDIRON_VERIFYING` set, an empty scratch file for the env file: 109 of
  111 pass, none fails, the two schema rows not run (no schema change here)
  (`step2_dry.txt`). Every record-free check `verify.py` names passes on the
  tree but `check_the_default_never_hides_the_count`, which needs a record's
  teams and was handed none (`source_checks2.py`).
- **`plant.py` whole**: 404/404 planted violations caught, exit 0,
  23:29:03-23:37:20Z (`plant_all.txt`); the three here re-proved on the
  final `plant.py` against 747a6c7's `git archive`, escaping there and caught
  here (`plantings_proof.txt`).
- **The full suite**: 2,326 passed, 4 skipped, none failed, exit 0, with a
  dummy non-secret `GRIDIRON_ACCESS_TOKEN` and TMP and TEMP at their
  defaults, 23:29:08-23:54:39Z, no file edited while it ran (`suite2.txt`);
  the only test that reached the network is the suite's own marked one. (A
  first run, 23:02-23:28Z, failed one test only --
  `test_refresh.py::test_catch_up_refreshes_before_it_resolves`, whose
  `inspect.getsource` read `tasks.py` from disk after a docstring was added
  above it mid-run; it passes alone and in the run above.)
- **The copy**: made 22:48:13-22:48:59Z, read only, deleted with its -wal and
  -shm at 2026-09-30T23:28:18Z. No copy of the record remains under
  `scratchpad/item1`. Nothing was written to the live record; no network; the
  live app, the main checkout, every scheduled task and `.env` untouched.

### THE PROVER *(2026-09-30/10-01; ONE verified copy of the record through `rebuild.verified_backup`, made 2026-09-30T23:59:56Z to 2026-10-01T00:00:42Z: integrity ok, 64 tables, none mismatched; read only through `db.read_only`, the clock held at 23:59:56Z; deleted after; scratchpad `item1/prover`, `p01` to `p09`)*

**THE GAP TABLE, MEASURED AGAIN** by scripts written apart from the
builder's (`p02_gap.py`: every close the repaired closer wrote against every
near-start and refresh firing that started inside its recommendation's
window, after it was written; a firing READ the game when it wrote a
near-start read of it between its start and finish, and LEFT IT OUT when it
wrote reads of other games and none of this one, or asked for nothing --
`p03_silent.py` reads each such firing's payload). 334 firings since item 1
(293 near-start, 41 refresh). Every figure stands:

| sport | closes | measured | on the last firing's read | minutes out, measured | pairs in a window | read its contract | venue answered nothing | left out |
|---|---|---|---|---|---|---|---|---|
| MLB | 30 | 19 | 5 | 5.0, 5.0, 9.7, 9.9, 9.9; the 14 at 34.5-35.0 | 116 | 64 | 38 (24 September) | 14, by runs 3504, 3525, 3568 (2), 3633, 4431, 4561 (2), 4625, 4669 (2: it asked for nothing) and 5405 (3), each five minutes before the listed start |
| NFL | 13 | 12 | 12 | 10.0 to 30.0 | 50 | 48 | 2 | none |
| NCAAF | 8 | 8 | 7 | 24.7 to 25.0; 103 at 49.0 | 33 | 32 (103's last firing read its game, and the answer held no quote of its contract) | 0 | none |

NFL AND NCAAF DO NOT SHOW THE 35-MINUTE GAP. No close has been written since
29 September 00:35:01Z; recommendations 114-117 (NFL, open) were written
after the builder's copy, and NBA 112 and 113 and NCAAF 111 are open. The
fixed `close_of` gives all 106 closes back, read for read (`p05`); none of
the 14 has a later read of its own contract before its start, and only 98,
100 and 108 have any later read of their game -- the same firing's other
ladders, one second after the closing read. Every measured close's read was
written inside a near-start or refresh firing (`p07`).

**FOUND, AND FIXED: ONE START NOBODY CAN READ STOPPED THE RUN FOR EVERY
GAME.** `_near_start_selection` read every candidate's listed start through
`db.instant`, which refuses by name a stamp with no zone or no time, and the
refusal raised in the selection -- before the closer -- for a start on ANY
game a drift row or open recommendation sits on, of any sport and any date
(the drift candidates are 1,297 forecasts over the whole record): every
firing stopped, every game left out until its start and every finished game
left unclosed, until the row was mended by hand. The claim writer raised on
it too (and with it a predict pass's whole slate), the closer raised on an
open recommendation's, and the noop count (`_games_starting_within`, every
game of the record) raised on it -- and on an EMPTY start, which the college
loader stores for an event with no date (`None` compared with an instant).
The games table has no rule on the column's form, and no loader refuses a
stamp; on the copy every stored start is readable (cfb, mlb, nba, nfl to the
second, ufc to the minute), so it was latent. Now: such a forecast is not
read (whether its start is ahead cannot be told, and it is never guessed)
and is NAMED on every firing it would have been asked about, with its
listed start as stored (`near_start_unreadable_start`, and in the detail
line: "1 forecast not read: the listed start of 1 game cannot be read as an
instant"); the closer holds its recommendation open with the starts still
ahead; the claim writer writes no claim on its game (`start_unreadable`);
the noop count skips it and an empty start; every other game is read as the
ruling says. `plant_an_unreadable_start_that_stops_the_near_start_run`: a
game in its warm-up five minutes out beside two moneylines on games whose
start cannot be read ("2026-09-27T19:40:00", "2026-09-27"); on 747a6c7 the
warm-up game was left out, the zoneless one read and its later read claimed
(UTC guessed), and the dateless one CLOSED (as text "2026-09-27" sorts
before any instant that day); on the change as first built the pass stopped
("ValueError: the stored instant '2026-09-27T19:40:00' names no zone");
caught here. Five tests (`test_near_start_reads.py`, four;
`test_at_the_price.py`, one in two cases) fail on the change as first built.

**PROVED.** The four plantings (`run_plantings.py`, `plantings_proof.txt`):
all four ESCAPE on 747a6c7's `git archive` with this `plant.py`, the
builder's three are caught on the change as first built and the prover's
escapes there, and all four are CAUGHT here.

**NAMED, NOT BUILT** (none is LAW 1, LAW 3 or a false gate count; one is
for the queue and is with the orchestrator):

- **A start the feed has not set is stored as its placeholder.** 292 of the
  561 college games still to start are listed at 04:00Z or 05:00Z --
  midnight Eastern -- and none of the 331 played this season was (`p09`):
  ESPN's date for a kickoff not yet announced, which `cfb_loader` stores as
  given (it reads no "time valid" flag). None carries a forecast's
  recommendation, and the first is 10 October; the loader refreshes every
  four hours and times are usually set days ahead. If one reached its
  placeholder still unset with an open recommendation, the run would read it
  until the placeholder and the closer would close it then, hours before it
  is played -- by the listed-start rule this ruling and question 35 both
  use. How a start the feed has not set is stored is question 35's ground.
- **A UFC bout's listed start is its card segment's** (one to four distinct
  starts per card on September's cards), so a bout's close would be the last
  read before its segment begins, not before it is fought. No UFC contract is
  read at the venue (0 UFC venue quotes, no series), so latent.
- **The read identical to the pricing read** (`close_of`, item 1's build of
  2026-09-23: same bid, ask, last price and volume, skipped as a cached body
  re-stamped). On the copy it skipped 12 reads later than the close (`p06`):
  10 before item 1 (restated 11, 12, 44-47) and 60 and 61 (24 September
  21:30:11Z, not a near-start firing: a predict pass's capture, which reads
  the venue through a six-hour cache with `read_kind` 'near_start' and
  stamps the body anew) -- replays, as the rule intends; none of the 39
  measured closes since item 1 moved. Since 23 September a near-start firing
  reads past the cache, so a read there identical to the pricing read is a
  market that did not move (a 304, or the same answer); with a differing read
  between the two the close would be the earlier read. Not seen on the
  record; whether such a read closes it at 0.0c is the close rule's (and the
  predict pass's 'near_start' stamp on a cached body is the cause), not this
  ruling's.
- **A game that really starts before its listed start** (the builder's
  note): its reads until the listed start are claimed, and a FINISHED game's
  pick is still priced (`recommend.for_predictions` skips a game in play,
  not a finished one) from the latest claim before the listed start -- so
  such a pick's side, price and edge could be an in-play read's. The status
  refusal this removes stood only in the ten minutes the live poll sees
  before a listed start (before that such a game read 'scheduled' on every
  release); none is measurable on the record, and from the release every
  read of a game marked under way is named. Reported to the orchestrator
  under the amended queue rule.
- **The media look's cache.** `espn.fetch_for_games` stores a sport's UTC
  day for good (`immutable`) once no game that day says 'scheduled'. From
  this fix a drift row is read on a game in its warm-up, when its day may
  hold no 'scheduled' game any more: its own look is as fresh as the
  near-start media window allows (ten minutes), and the day is then stored
  for good, so a drift row whose first look came later that day would read
  that stored day. Drift only; none on the record.

**THE CHECKS.** `plant.py` whole: 405/405 planted violations caught, exit
0 (2026-10-01T00:17:14Z to 00:25:29Z, `plant_all.txt`). Gate step 2's rows,
dry-run on this tree on the prover's copy (`step2_dry.py`, not
`tools/verify.py` whole; `GRIDIRON_VERIFYING` set, every record row through
a read-only handle on the copy, an empty scratch file for the env file):
109 of 111 pass, none fails, the two schema rows not run -- this change
touches no schema (`step2_dry.txt`). `audit.prose_reaching_the_raw_side()`
is `[]`. The full suite: 2,332 passed, 4 skipped, none failed, exit 0, with
a dummy non-secret `GRIDIRON_ACCESS_TOKEN` and TMP and TEMP at their
defaults, 00:25:56Z to 00:51:31Z, no file of the tree edited while it ran
(`suite.txt`). The prover's tests hold every clock (written instants, never
the machine's), add no fixed wait or sleep, and `ELAPSED_TIME_HELD` is
untouched. The copy was deleted, with its -wal and
-shm, at 2026-10-01T00:26:03Z; no copy of the record remains under
`scratchpad/item1`. Nothing was written to the live record; no network but
the suite's own marked test; the main checkout, the live app, every
scheduled task and `.env` untouched.

## A pass written at or after the start is not blind; a start is an instant -- built 2026-10-01 *(operator question 35, ruled 2026-09-30, docs/briefs/2026-09-30-rulings.md; the re-read's G3, docs/closeouts/2026-09-29-the-re-read.md; built on a9c5193, item 1 released as e159be2; uncommitted for its prover)*

The ruling: "Q35: a pass written at or after the start is not blind. Store
and compare starts as instants, never as text. The 18 are voided by
append-only rows under the existing void rule, and Q27's standing rule then
falls back to their early passes. Report why a final pass ran at the start
time and move that schedule so every final pass lands before its start."

### MEASURED FIRST *(ONE verified copy of the record through `rebuild.verified_backup`, 2026-10-01T01:40:24Z to 01:41:09Z: integrity ok, 64 tables, none mismatched; read only through `db.read_only`; scratchpad `q35/measure1.py` to `measure3.py`, outputs beside them)*

**How every start is stored.** No start is NULL and every one is read by
`db.instant`; every one is UTC and says so with a Z.

| sport | games | stored form | still to start |
|---|---|---|---|
| NFL | 3,033 | to the second, `2026-09-27T17:00:00Z` | 224 |
| MLB | 9,720 | to the second | 2 |
| NBA | 6,120 | to the second | 1,200 |
| NCAAF | 2,654 | to the second | 562 |
| UFC | 2,783 | TO THE MINUTE, `2026-09-05T19:00Z` (as ESPN's core API sends it) | 63 |

The UFC source tables are to the minute too (`ufc_bouts.bout_utc` 2,783,
`ufc_events.event_utc` 269). Every other instant the starts are compared
with is to the second: 3,660 forecasts, 1,789 claims at the venue's line,
35,676 venue reads, 1,489 rung claims, 117 recommendations.

**Where a start was compared as text** (the new scan run on a9c5193): 67
places in the shipped code and one schema rule -- the standing clause's
order and both its tests (`<=`), the at-the-line window, the
recommendation's claim window and `correction_instant`, every sport's
`next_slate` and the college repo's (`kickoff_utc > ?`), the predict path's
question check (`kickoff_utc <= now`) and its horizon (`MIN`), the
missed-slate reads, the opening read, the live window, the lineup capture,
the college factors' bounds and orders (form, rest, ratings, swing), the
UFC fighter history and rating order, the slates' orders and first starts on
four pages, the recount's four Python comparisons, the board's sort,
`views.next_start_utc`'s `min`, the college weather's past-or-future,
`is_sanctioned_card`, `audit.pick_contracts`, three tools, and the schema's
`recommendation_close_is_a_later_read_of_its_own_contract`. Item 1 had
already made the near-start selection, the claim writer, the close and the
closer read instants.

**Every forecast written at or after its start, by the instant: 24.** Six
MLB early passes (105-110, written 2026-08-29T19:17:55Z after first pitches
of 17:05-19:07Z) withdrawn at 19:19:07Z that day for that reason, and the
18 (1014-1031), withdrawn by nothing. None was written at its start's own
second. Compared as text the record finds 6 (the re-read's "24 where the
text comparison finds 6").

**WHY THE FINAL PASS RAN AT THE START TIME (the report the ruling asks
for).** `Gridiron-Final-UFC`, read read-only from the scheduler: a daily
trigger, start boundary 2026-09-05T12:00:00-07:00, `pythonw -m gridiron.cli
task final:ufc`, WakeToRun, last run 30 September 12:00:01 local, next 1
October 12:00:00 -- the installer's "Final-UFC at 12:00 local", registered
by the audit of 2026-09-05 (until then no UFC task was registered), whose
first firing was 5 September. 12:00 local is 19:00Z while the machine is on
summer time. That day's card, UFC Fight Night: Hooker vs. Parnasse (Paris),
listed its eight prelims at 16:00Z and its six main-card bouts at 19:00Z,
to the minute. Run 131 began at 19:00:01Z: the slate selection
(`ufc.next_slate`, `kickoff_utc > ?`) and the question check
(`kickoff_utc <= now`) each compared "2026-09-05T19:00Z" with a clock to the
second as text, where a colon sorts below a Z, so the main card read as
still to come; the prelims (16:00Z) were correctly skipped; eighteen final
passes were written at 19:00:02-03Z and the run finished 19:00:04Z, "ok,
re-forecast 18 questions ... close to start". And 12:00 local was never the
declared three hours before the first bout (`config.FINAL_PASS["ufc"]`, 180
minutes, not measured): of the 103 cards of 2025-2026, 18 list their first
bout before 12:00 local (Riyadh, London, Baku, Abu Dhabi, Shanghai, Paris,
Doha, Perth, Macau, Belgrade) and 2 at it; every other 'ok' final pass, 6
to 30 September, was written 23 to 73 hours before its card's first start
still ahead (runs 159, 225, 1566, 1676, 1848, 2049, 3359, 5401, 8510; 8510
wrote 54 for 3 October at 19:00:01Z on 30 September). The other card listed
at 19:00Z exactly (UFC Fight Night: Rosas Jr. vs. Barcelos, 26 September)
was not written at its start only because its final passes were already
written (run 4383 at 19:00:01Z: "found nothing new to write"). The other
sports' final passes all landed before their starts: the least lead MLB 4.6
minutes, NCAAF 59.1, NFL 123.2, NBA 30,060 (pre-season).

### BUILT

- **STORED (`db.stored_start`, `db.stored_instant`, `db.INSTANT_FORM`).**
  Every loader writes a start to the second: the NFL, MLB, NBA and college
  loaders, the UFC loader's card (`event_utc`) and bout (`bout_utc`), and
  the UFC mirror into `games`. A stamp a feed sends that cannot be read is
  kept as sent -- never guessed, never NULL -- and every reader of a start
  refuses it by name. THE RECORD'S 2,783 UFC STARTS reach the form through
  the loader's own door, not a rewrite tool: `ufc.mirror_bouts` rewrites
  every bout's start on every refresh (`kickoff_utc = excluded.kickoff_utc`,
  as it always has), so the first UFC refresh after the release writes each
  as the same instant to the second (rehearsed below). No schema rule on the
  column's form (the tests' and plantings' worlds, and item 1's unreadable-
  start guards, store other forms on purpose), and no separate rewrite of
  stored values is needed: every comparison reads an instant meanwhile.
  (`ufc_bouts`/`ufc_events` rows of seasons the loader no longer reads keep
  the feed's minute; every reader compares them as instants.)
- **COMPARED: `db.instant` in Python; in SQL `julianday(<start>)` against
  `julianday(<instant>)`, the one expression.** Every place above, the 67.
  The standing clause and its order read "before the start" STRICTLY (`<`):
  a pass at the start's own second is not before it. A first start is the
  earliest instant (`ORDER BY julianday(...) LIMIT 1`, or
  `strftime(<the stored form>, MIN(julianday(...)))` where grouped). A start
  that cannot be read is before nothing (`julianday` NULL) and is never
  guessed: `correction_instant` takes it as begun (the claim's own instant),
  the board sorts it last, the college weather reads no wind.
- **THE SCHEMA: `recommendation_close_is_read_before_the_start_instant`**,
  a rule beside `recommendation_close_is_a_later_read_of_its_own_contract`
  (whose text compares as text and is never replaced on a record that holds
  it -- the precedent written beside it): a close whose read was taken at or
  after its game's start, each read by `julianday()`, is refused. It reaches
  the record through `db.init` exactly as a fresh build has it (rehearsed
  below). The old rule's text is held in `audit.START_TEXT_COMPARISONS_HELD`,
  dated, frozen on 2026-10-01; the register only shrinks.
- **NEVER WRITTEN AT OR AFTER THE START (`predict.PassAtOrAfterTheStart`,
  `predict.not_before_its_start`).** On a live record `write_prediction`
  reads the row's stamp once and refuses the row when it is at or after its
  game's listed start, read as an instant, or the start cannot be read; the
  row is stamped with that same instant. `predict_slate` asks each question
  by the clock now (it read a clock once, when the run began), before the
  reasoning pass is paid for, and names each question it did not write. A
  backtest is not asked.
- **THE SCHEDULE: the UFC final pass fires by its lead.**
  `config.FinalPass.fires_by_lead` (True for UFC alone; the 180 minutes
  unchanged and still "not measured"); `tasks.final_pass_window` is the
  window -- 180 minutes before the slate's first start still ahead, read as
  an instant (the main card's once the prelims have begun), until it;
  `_run_final_pass` writes nothing outside it and records a noop saying when
  it opens; the installer's Final-UFC fires every thirty minutes from 00:20
  local (clear of NearStart's :05 and :35). So the pass lands 150 to 180
  minutes before the card's first bout wherever the card is, and no pass
  lands at or after its start whatever fires it. The other sports keep
  their wall-clock triggers (their passes all landed before their starts)
  and are held by the same refusal.
- **THE GATE.** `audit.check_every_start_is_compared_as_an_instant` (step 2;
  `audit.start_text_comparison_faults`): every string the shipped code
  hands SQLite (question 15's readers), every `.sql` file, and every Python
  comparison, sort key, `min` and `max`; a start compared, ordered or taken
  the least or greatest of as text, or read as an instant and compared with
  a value that is not one, is named by file, line and function or rule; a
  day taken off a start (`substr(start, 1, 10)`) and an upsert's `SET start
  = excluded.start` are not comparisons. Proved at import
  (`_check_the_start_scan_can_see`). And `audit.check_the_final_pass_stands`
  asks every door again on a world whose start is stored to the minute
  (`STANDING_PASS_WORLD_TO_THE_MINUTE`).
- **THE 18: `tools/void_passes_written_at_the_start.py`.** Selects BY RULE
  every forecast written at or after its game's start (`julianday` and
  `db.instant`, which must agree) that no void withdraws, with any this
  ruling's reason already withdraws (so a second run selects the same set);
  writes one `prediction_voids` row each, dated when written, its reason in
  words ("written at or after its game's start, read as an instant: the
  bout's start was stored to the minute and compared as text, so this pass
  stood as one written before it. A pass written at or after the start is
  not blind (operator ruling on question 35, 2026-09-30)"); only when the
  selection is exactly `RULED` (1014-1031) and no recommendation stands on
  one; refused on the record without `--live` and `--live` on anything else
  (`db.is_the_live_record_file`); refused on a backtest; one transaction;
  idempotent. Listed beside them and left: the six MLB passes already
  withdrawn for their own reason. Its read of `recommendations` round the
  door is registered (`audit.RECOMMENDATION_DOOR_EXEMPT`, dated).

### THE REHEARSALS *(the copy; never the record)*

- **The void tool** on a scratch copy of the verified copy (`voided.db`):
  dry, it lists the 24 and the ruled 18, "--write would void 18"; written,
  "wrote 18 void(s) at 2026-10-01T02:09:01Z"; again, "wrote 0 void(s) ... 18
  already voided by this ruling"; `--live` on the copy refused.
- **The mirror** (`mirror_rehearsal.py`, on `mirrored.db`): 2,783 bouts
  mirrored; 2,783 UFC `kickoff_utc` values changed, every one to the same
  instant in the stored form; no other column of any row changed; every one
  of the 24,310 starts then 20 characters, to the second.
- **The schema** (`schema_rehearsal.py`, on `migrated.db`): this tree's
  `db.init` on the copy added exactly one object, the new rule; no object
  lost or changed; no table's rows or column checksums moved; the gate's
  tree row (the migrated copy against this tree built from nothing): 0
  differences, 9 cosmetic; its release row (the copy against master,
  e159be27f663, built from nothing): 0 differences.

### THE NUMBERS THAT MOVE *(every payload of every sport -- the Record page, learning, record line, meta, factors, tier tables, over time, calendar, versions, timing, digest, every slate both forecasters standing and early, history, the closing line and kill on the first clean read, the recommendation doors, empty bar, every correction's measurement, the eighteen re-scored -- built by a9c5193's `git archive` and by this tree on the copy, the clock held at 01:40:24Z; `measure.py`, `flatten_diff.py`; 2,956,332 figures)*

- **This tree against a9c5193, before the voids: 11,041 figures move**, all
  UFC and all the 5 September slate's eighteen questions: the standing rows
  of those questions are their early passes (520-537) for their final passes
  (1014-1031) in the clause, the recount, the outlook's door and the slate's
  card (the 5 September slate's cards, Today blocks and board rows: 9,135
  figures for the model, 864 each on the reasoning pass's board, standing
  and early view); and THE UFC RANKER SPLIT in each of moneyline, rounds and
  distance, "53 settled on the shortlist and 0 off it" -> "47 settled on the
  shortlist and 6 off it" (the re-read's 49/0 -> 43/6, four more settled
  since), with the shortlisted scores (moneyline Brier 0.2362 -> 0.2416,
  rounds 0.2628 -> 0.2598, distance 0.2511 -> 0.2515) and the outranked
  side's first figures (0 -> 6 each). NO CURVE, PRICED, DRIFT, CORRECTION
  OR OUTLOOK COUNT OR SCORE MOVES: each early pass carries its final pass's
  probability exactly (18 of 18), and the curve's n counts one row per
  question either way. And the correction measurements' agreement check
  names the early pass, not the final, as the blind rule's row for the 18.
- **The 18 voided, on top: 623 more.** UFC 378 settled -> 360 (198-180 ->
  189-171, "18 withdrawn") on the record line, the sport tabs, the sign-in
  page, every slate's "yesterday" line; the calendar's 5 September 102 ->
  84 settled, "18 withdrawn"; the digest 378 -> 360 resolved, its 50-60%
  bucket 294 -> 279 and 60-70% 60 -> 57 ("43 more before calibration
  speaks"); the weeks chooser 102 -> 84; the timing comparison 133 -> 115
  games; each UFC correction category's forecasts 93 -> 87 (its questions
  unmoved); the slate's "superseded" label 18 -> 0; and the void count
  beside each UFC curve (FOUND, below).
- **The voids alone, on a9c5193, end in the same pages** as this tree with
  the voids: of 2,948,928 figures none differs between the two. The
  comparison is what keeps the next one out.
- **The mirror's rewrite (the first UFC refresh after the release), on top
  of this tree: 2,802 figures, all strings** -- the UFC starts on the slates
  written to the second, and each UFC slate's glance now places its games in
  kickoff windows (14 slates said "windows unknown": `reference.eastern_hour`
  could not read a minute stamp). No count moves.

### FOUND, NOT BUILT *(none is LAW 1, LAW 3 or a false gate count; the first is for the orchestrator)*

- **THE VOID COUNT BESIDE A UFC CURVE IS THE MARKET'S, ACROSS EVERY CARD.**
  `calibration.curve` hands the card to `resolved` and not to `void_count`,
  so once the 18 are voided the Record page reads "6 withdrawn" beside the
  Contender Series and the Numbered card curves of each UFC market, none of
  whose forecasts is withdrawn (the Numbered card's void rate 1.0 on 0
  settled), as well as beside Fight Night's, which is right. Latent until
  now (no UFC forecast was voided); drawn (`app.js`, the curve's line and the
  category table's cell). Question 34's ground ("every UFC count is per
  card tier") -- running the void tool before it is built puts the false
  count on the page. **BUILT 2026-10-01**, ahead of question 34, on top of
  this change: "A UFC category counts its own card's voids", below.
- **The UFC final pass's pre-pass refresh reads the NFL schedule.**
  `tasks._refresh_one_sport` has no UFC arm and falls to the NFL loader, so
  the final pass forecasts the card as the four-hourly refresh last left it.
- **`ufc_bouts` never updates a bout's start** (its upsert sets status and
  result only), so a bout moved after it was first loaded keeps its first
  start, and the mirror copies it.
- **The standing clause's backtest fallback** stands a question's latest row
  when nothing of it was written before its start -- on a live record too,
  where such a row is not a forecast. None on the record once the 18 are
  voided (the six MLB rows are withdrawn), and the write refusal keeps any
  new one out; Q27's reading kept the fallback as it was.
- **A start the feed has not set** (item 1's prover: 292 college games listed
  at midnight Eastern) is stored as the placeholder instant; a UFC bout's
  start is its segment's. Neither is in the ruling's words.
- **The other sports' final passes fire by the wall clock**: MLB's 14:30
  local serves the evening card (its day games get none, as declared), NFL
  and college 08:00, NBA 15:00. All landed before their starts; any that
  would not is refused now.

### THE CHECKS

- **Tests**: `tests/test_starts_are_instants.py`, 24 -- all 24 fail on
  a9c5193 (the file laid over its `git archive`), the behaviour ones for the
  right reason (the early pass not standing, the in-play claim pricing the
  pick, `correction_instant` None, `next_slate` 20260905, the passes written).
- **Plantings** (`tools/guards/plant.py`, `LAW_STARTS_ARE_INSTANTS`, in
  `main()` and `tests/test_guards.py`'s list): `plant_a_start_compared_as_
  text` (the standing order put back as released in a copy of the package,
  and a slate bound, a first start by MIN, a card order, the question check
  in Python and a schema rule, each in its own function or rule: each named,
  the shipped tree clean, step 2 making the call), `plant_a_pass_written_at_
  the_start_standing` (the eighteen's world: every door keeps the early pass
  over a final pass two seconds after a minute start and one at its second,
  the final pass a second before stands, no claim thirty seconds into the
  game stands, and the gate's check names the clause put back as released),
  `plant_a_final_pass_written_after_its_start` (the harness league as a live
  record, week 17 listed to the minute: the task `final:nfl` a second after
  the start, the pass run on the slate a second after it, and the pass asked
  a second before it whose rows would be stamped a second after; nothing
  written after the start, every question named). ALL THREE ESCAPE on
  a9c5193 (`run_plantings.py`): "there is no scan for a start compared as
  text ..."; "the standing clause kept forecast 2 for EIGHTEEN where 1
  stands ... the at-the-line window kept claim 4 for EIGHTEEN where 1
  (before the start) stands ..."; "(A) 12 forecasts written at or after
  their start ... (B) ... (C) ..." -- and all three are CAUGHT here.
- **Gate step 2's rows**, dry-run on this tree on the copy (`step2_dry.py`,
  not `tools/verify.py` whole; `GRIDIRON_VERIFYING` set, every record row
  through a read-only handle on the copy, an empty scratch file for the env
  file): 110 of 112 pass, none fails; the two schema rows were run apart
  (`schema_rehearsal.py`, above: 0 differences each). The first dry run
  found two rows failing on the change as first built, both in this
  change's own audit code and both mended: the side-in-prose scan on a fault
  sentence naming a claim's raw subject, and the replacing-write scan on the
  start scan's own upsert fixture (now an UPDATE).
- **`plant.py` whole**: 408/408 planted violations caught, exit 0,
  2026-10-01T02:55:50Z to 03:05:54Z.
- **The full suite**: 2,356 passed, 4 skipped, none failed, exit 0, with a
  dummy non-secret `GRIDIRON_ACCESS_TOKEN` and TMP and TEMP at their
  defaults, 03:06:08Z to 03:32:47Z; no file of the tree edited while it ran
  (every changed file's hash the same before and after); the only test that
  reached the network is the suite's own marked one. (A shakedown run during
  the build failed two: the harness, on the replacing-write fixture above,
  and `test_the_schema_matches.py::test_the_normaliser_is_the_one_door`,
  whose `inspect.getsource` read `audit.py` while it was being edited; both
  pass in the run above.)
- **The copies**: the ONE verified copy (made 2026-10-01T01:40:24Z to
  01:41:09Z) and the three scratch copies made from it through `db.back_up`
  for the rehearsals (`voided.db`, `mirrored.db`, `migrated.db`; never from
  the record) were deleted, with their -wal and -shm, at 03:33:11Z, and the
  fresh builds of the schema rehearsal with them. No copy of the record
  remains under `scratchpad/q35`. Nothing was written to the live record; no
  network; the main checkout, the live app, every registered scheduled task
  (read only) and `.env` untouched.

### THE PROVER *(2026-10-01; ONE verified copy of the record through `rebuild.verified_backup`, made 03:45:01Z to 03:45:48Z, integrity ok, 64 tables, read only through `db.read_only`; four scratch copies of it through `db.back_up` for the rehearsals; every one deleted after, below)*

**MEASURED AGAIN, and the build's measurement stands.** Every start is read
by `db.instant` and by `julianday()` as the same instant (24,310 of 24,310;
none NULL, none empty, none unreadable); UFC's 2,783 games, `ufc_bouts`'
2,783 and `ufc_events`' 269 to the minute, every other sport's to the
second. 24 forecasts written at or after their start by the instant -- MLB
105-110, withdrawn on 29 August, and the 18 (1014-1031), withdrawn by
nothing -- and none at its start's own second; read as text, 6. Run 131
began 19:00:01Z and ended 19:00:04Z ("re-forecast 18 questions"), its 18
written 19:00:02-03Z on bouts stored "2026-09-05T19:00Z" (the card's eight
prelims "...T16:00Z"); their early passes 520-537 were written on 4
September at 02:04-02:05Z. Run 4383 (26 September, 19:00:01Z, a card listed
at 19:00Z) wrote nothing because its finals already existed. The registered
`Gridiron-Final-UFC`, read read-only: one daily trigger, start boundary
2026-09-05T12:00:00-07:00, `pythonw -m gridiron.cli task final:ufc` from the
main checkout, WakeToRun, last run 30 September 12:00:01 local, next 1
October 12:00:00. Of the 103 cards of 2025-2026, 18 list their first bout
before 12:00 local and 2 at it. No recommendation, claim or taken pick on
any of the 18.

**HUNTED: no start is compared as text anywhere in the shipped code.**
Every one of the 380 lines of the package, `tools/` (less `tools/guards/`)
and `desktop/` that names a start, read by hand, and three scans of the
prover's own beside the gate's (scratchpad `q35/prover_hunt.py`, `_hunt2`,
`_hunt3`): every ordering comparison, sort, `min` and `max` in a function
naming a start; every ordering comparison of anything named like a time,
whoever holds it; and every mention of a start column in every string the
shipped code hands SQLite, and every `.sql` file, that is not plainly
harmless. What is left is the held rule. `app.js` compares no start: it
reads one only to format it, through `Date`. The final pass writes through
`predict.write_prediction` alone (the only writer of `predictions` outside
the gate's probe worlds and `tools/board_shots.py`'s scratch world), which
refuses a pass at or after its start on a live record; the live record's
meta kind is `live`.

**FOUND AND FIXED (each measured on the change as first built, with a test
and a planting form):**

- **A START NOBODY CAN READ STOOD A QUESTION ON ITS EARLY PASS.**
  `julianday()` of a start it cannot read -- an empty one, or a feed's text
  that `db.stored_start` keeps as sent ("TBD") -- is NULL, so
  `calibration.standing_pass_order`'s first term was NULL for a final pass
  on such a game and 0 for an early pass, and `ORDER BY ... DESC` puts NULL
  last: the clause (and the outlook's door through it) stood the question's
  latest EARLY pass, where the recount (`recount._before_the_start`, False)
  and the rule's own fallback -- nothing shown to come before the start, so
  the latest row stands -- keep the final. On a9c5193 the stored text kept
  it right by accident (every stamp sorts before "TBD"; an empty start
  failed every `<=`). The term is `IFNULL(julianday(...) < julianday(...),
  0)`. None on the record: no start is unreadable. Test:
  `test_starts_are_instants.py::test_a_start_nobody_can_read_stands_its_
  latest_row_in_the_clause_and_the_recount` (an empty start and "TBD", each
  with an early pass and a later final pass; fails on the change as first
  built: the clause kept both early passes). Planting: a form in
  `plant_a_pass_written_at_the_start_standing` (a game of the next week
  listed "TBD"; "the standing clause kept forecast 7 ... where its latest
  row, 8, stands; the outlook's door kept forecast 7" on the change as first
  built; caught here).
- **THE GATE'S SCAN SAW A START ONLY BY ITS OWN NAME, AND ONLY BARE.** Each
  of these got past `audit.start_text_comparison_faults` as first built,
  which said nothing: in Python, a start handed to a local of another name
  (`listed = row["kickoff_utc"]; listed <= now`) or to a loop over a list
  of starts, `str()` or a string method of one (`.replace`, `.rstrip`
  ...), and one cut short anywhere but at its day (`kickoff[:16] <=
  now[:16]`, in the comparison or through a local); in SQL, a start inside
  a call that keeps it text -- `COALESCE`, `IFNULL`, `datetime`, a `substr`
  short of the day -- compared, ordered, or taken the greatest of, a start
  in brackets compared, and a scalar subquery whose only column is a start
  compared with a stamp. Now named (`audit._start_handed_on`,
  `_start_text_ordered`, `_start_keeps_text`, `_start_text_wrapped`, proved
  at import by fourteen SQL and ten Python fixtures more); not named, as before:
  a day cut off a start (`substr(start, 1, 10)`, `start[:10]`, `date()`), a
  count of starts, a start handed on and then read as an instant, and
  `julianday()` of what keeps it text compared with another instant. The
  strengthened scan finds nothing in the shipped tree, and on a9c5193 the
  same 67 and the one rule the scan as first built found. Test:
  `::test_the_scan_names_a_start_compared_by_another_road` (ten forms named
  and the lawful forms not; fails on the change as first built). Planting:
  four forms in `plant_a_start_compared_as_text` (`planted_handed_on`,
  `planted_cut_short`, `planted_wrapped_bound`, `planted_subquery_start`:
  on the change as first built "not named: ['(planted_handed_on)',
  '(planted_cut_short)', '(planted_wrapped_bound)',
  '(planted_subquery_start)']", with the order's anchor as first built;
  caught here).

**FOUND, NOT BUILT** *(none LAW 1, LAW 3 or a false gate count; none a number
on a pick)*:

- **THE EIGHTEEN EARLY PASSES ARE LABELLED SUPERSEDED IN THE SLATE'S
  PAYLOAD.** With the clause standing 520-537, each of those cards on the 5
  September slate carries `is_early_view: true` and a `pass_note` ending "A
  later forecast stands in its place." -- false: no later forecast stands.
  `views._superseded_ids` reads no start and no withdrawal (question 30,
  ruled 29 September: FOLLOWUPS), so the voids do not clear it (measured on
  the copy before and after the voids). The board draws neither field (no
  reader in `board.py` or `app.js`); the slate's `superseded` count goes 18
  -> 0 with the voids, as the build measured.
- **THE POOLED UFC VOID COUNT, as the build found it, measured again**:
  after the voids, each UFC market's Contender Series category reads
  "voided 6, void rate 0.3", the Numbered card's "voided 6, void rate 1.0"
  on no settled forecast, Fight Night's "voided 6, void rate 0.1333" (the
  right one), and the headline's "voided 6". Question 34's ground.
- The build's other findings stand as written above (the UFC pre-pass
  refresh loading the NFL schedule; `ufc_bouts` never moving a start; the
  standing clause's backtest fallback; unset starts; the other sports'
  wall-clock final passes).

**THE REHEARSALS** *(scratch copies of the verified copy; never the record)*:

- **The void tool**: dry, it lists the 24 and the ruled 18, MLB 105-110 left
  as withdrawn for their own reason, "--write would void 18" (exit 0);
  `--write --live` on the copy refused ("--live names the operator's
  record ... not the same file", exit 2); `--write`, "wrote 18 void(s) at
  2026-10-01T04:01:34Z"; again, "wrote 0 void(s) ... 18 already voided by
  this ruling"; dry again, "--write would void 0". Before the voids and
  after, the standing clause stands 18 of 520-537 and none of 1014-1031.
- **The schema** (`db.init` of this tree on a copy): exactly one object
  added, `recommendation_close_is_read_before_the_start_instant`, appended
  after every object the record holds, whose order is unchanged; none lost
  or changed; no row or column checksum of the 63 tables moved; `meta`
  unchanged. Gate step 2's tree row (the migrated copy against this tree
  built from nothing): 0 differences (9 cosmetic). Its release row (the
  verified copy against master, e159be27f663, built from nothing): 0
  differences.
- **The mirror** (`ufc.mirror_bouts`, the first UFC refresh after the
  release): 2,783 bouts mirrored; only `games` moved, only its UFC
  `kickoff_utc`, 2,783 values, each the same instant in the stored form;
  every one of the 24,310 starts then 20 characters.

**THE NUMBERS** *(every payload of every sport, the build's harness, the
clock held at 03:45:01Z; released a9c5193 against this tree with the
prover's fixes)*: the fix alone moves 11,041 of 2,956,332 figures (UFC
10,940, the eighteen's own re-scoring 101): the UFC ranker split "53
settled on the shortlist and 0 off it" -> "47 ... and 6 off it" in each of
moneyline, rounds and distance, shortlisted Brier 0.2362 -> 0.2416, 0.2628
-> 0.2598, 0.2511 -> 0.2515, and the 5 September slate's cards on their
early passes; the voids on top move 623 of 2,949,288 (UFC 378 -> 360
settled, "198-180" -> "189-171", "18 withdrawn"; the calendar's 5
September 102 -> 84; the digest; the weeks chooser 102 -> 84; the timing
comparison 133 -> 115; each UFC correction category's forecasts 93 -> 87;
the slate's superseded count 18 -> 0; the pooled void counts above); the
voids alone on a9c5193 against this tree with the voids: 0 of 2,948,928.
The same counts as the build's: the prover's fixes move nothing on the
record.

**THE CHECKS**: the three plantings each escape on a9c5193's archive and
are caught here; the prover's forms escape on the change as first built
(its copy, scratchpad `q35/prover_asbuilt`); `plant.py` whole 408/408,
exit 0, 04:11:07Z to 04:21:19Z; gate step 2's rows dry-run on this tree on
the copy (`GRIDIRON_VERIFYING` set, every record row through a read-only
handle, an empty scratch file for the env file): 110 of 112 pass, none
fails, the two schema rows run in the rehearsal above (0 differences each);
`audit.prose_reaching_the_raw_side()` is `[]`. The full suite: 2,358
passed (the build's 2,356 and the prover's two), 4 skipped, none failed,
exit 0, with a dummy non-secret `GRIDIRON_ACCESS_TOKEN` and TMP and TEMP
at their defaults, 04:23:27Z to 04:50:29Z; no file of the change edited
while it ran (every changed file's hash the same before and after); the
only test that reached the network is the suite's own marked one.

**THE COPIES**: the verified copy and its four scratch copies
(`prover_voided`, `prover_voidtest`, `prover_migrated`, `prover_mirrored`),
each with its -wal and -shm, and the rehearsal's fresh builds
(`gridiron-fresh-2u73uxbr`), were deleted at 04:21:46Z, and the raw payload
dumps with them. Nothing was written to the live record; no network; the
main checkout, the live app, every registered task (read only) and `.env`
untouched.

## A UFC category counts its own card's voids -- built 2026-10-01 *(the first of operator question 34's counts, ruled 2026-09-30, docs/briefs/2026-09-30-rulings.md; found by question 35's prover; built on 3cb376e -- question 35, committed locally, not yet gated or released -- and AHEAD of question 34, because question 35's own voids make this count false; committed locally, not pushed)*

The ruling this is the first count of: "Q34: every UFC count is per card
tier: tier table, ranker, taken record, edge figure, board badge. Planting
each." Question 34 is later in the order (Q33 + Q34, after the entry
check). This one count -- the void count beside each UFC curve, the void
rate made from it, and every figure the Record page, the scorecard and the
gate list build from it -- is built now: question 35's release is followed
by its void tool on the record, and the tool's eighteen voids would put a
false count on the Record page the moment they were written.

### THE FINDING *(question 35's prover, 2026-10-01)*

`calibration.curve` handed the card to `resolved` (the curve's rows) and
not to `void_count` (the count beside it), so the void count beside a UFC
curve was its market's across every card. Latent while no UFC forecast was
voided; false once the eighteen final passes 1014-1031 (all Fight Night) are.

### MEASURED *(ONE verified copy of the record through `rebuild.verified_backup`, made 2026-10-01T05:29:53Z to 05:30:41Z: integrity ok, 64 tables, none mismatched; one scratch copy of THAT copy through `db.back_up` for the void tool, never of the record; both read only through `db.read_only` for the measurement; HEAD is `git archive` of 3cb376e; scratchpad `voidcard/measure.py`, `compare.py`, `compare.txt`)*

**The void tool, rehearsed on the scratch copy** (never on the record):
dry, it lists the 24 and selects the ruled 18 (1014-1031), "--write would
void 18"; with `--write`, "wrote 18 void(s) at 2026-10-01T05:30:56Z; 0
already voided by this ruling"; again, "wrote 0 void(s) ... 18 already
voided by this ruling". (`--live` was also tried once ON THE SCRATCH COPY,
to see the refusal: exit 2, "REFUSED, NOTHING WRITTEN: --live names the
operator's record, and <the copy> is not the same file as it". It was
never given the record.)

**Every UFC void figure, each blind category** (each market alike --
moneyline, rounds and distance; settled counts are the curves', unchanged
by this change):

| statistical category | settled | HEAD, as is | here, as is | HEAD, the 18 voided | here, the 18 voided |
|---|---|---|---|---|---|
| Fight Night | 39 | 0 withdrawn | 0 withdrawn | 6 withdrawn, void rate 0.1333 | 6 withdrawn, 0.1333 |
| Contender Series | 14 | 0, rate 0.0 | 0, 0.0 | **6 withdrawn, void rate 0.3** | 0, 0.0 |
| Numbered card | 0 | 0, no rate | 0, no rate | **6 withdrawn, void rate 1.0** | 0, no rate |

The reasoning pass's nine categories (Fight Night 39, 14, 14 settled;
Contender Series moneyline 14; the rest 0) have no withdrawal either way.

**The line under the Record page's chart** (app.js `findCurve`: the first
category of the chosen market and forecaster, the Numbered card's for every
UFC market): HEAD with the 18 voided, "0 resolved, 6 withdrawn" in each
statistical market; here, "0 resolved". As is, "0 resolved" on both.

**The headline curve** (`scorecard.headline`, UFC moneyline, statistical,
every card): 53 settled; 0 withdrawn as is, 6 withdrawn and void rate
0.1017 with the 18 voided -- on HEAD and here alike. Every card's curve
with every card's voids: one population, so not false against its own
curve. It is drawn only where no category matches the chosen market and
forecaster, which for UFC never happens. A UFC curve pooled across cards is
question 34's ground (FOUND, below).

**The gate list** (`scorecard.gates`: the correction, drift and
read-window rows): 15 rows for UFC; none carries a void figure, on either
tree or either copy. Nothing there to move.

**Every other sport**: no category's settled count, void count or void
rate moves, on either copy (NFL 16 categories, 53 withdrawn across them;
MLB 16, 67; NBA 14, 47; NCAAF 6, 2), and each category's recount agrees.

**The whole UFC `/api/scorecard` payload** (`views.scorecard`), HEAD
against here: as is, 4,831 figures on HEAD and 4,849 here -- the 18 new
`voids_recounted` (one per category) and nothing else; with the 18 voided,
12 figures move -- the six statistical Contender Series and Numbered card
categories' void count 6 -> 0 and void rate 0.3 -> 0.0 and 1.0 -> none --
and 22 are new (the 18 `voids_recounted`, and `void_tiers_counted`
naming Fight Night in its three statistical categories and the headline).
(One build-identity string, `meta.build.head`, is None in the archive,
which is no checkout.)

### BUILT

- **`calibration.category_filter`, THE ONE DOOR for which forecasts a
  category holds**: its sport, its card (through the bout to its event's
  tier), its market, prop type, forecaster and factor set, as SQL terms.
  `resolved` reads it (settled rows only) and so does
  **`calibration.withdrawn_forecasts`**, the void count -- `void_count`
  until this date, which took no card. Every withdrawn row of the
  category, whichever pass, as before; the card is the one change.
- **`curve` asks both of one cell, in one instant** (`db.one_instant`), so
  the card a curve counts is the card its void count counts and a void
  written between the two reads cannot be counted on one side only.
  `calibration.void_rate` is the one arithmetic of the rate. Each curve
  carries `void_tiers_counted`, the cards its void count counted, read off
  each withdrawn row's own bout (none named outside UFC; a card the source
  left unnamed is None, which is no category's).
- **The recount** (`recount.voids`, `recount.voids_in`): every withdrawn
  forecast of the sport read straight off the tables with its own card,
  placed in each category by restating the cell in Python -- asked once per
  sport by `calibration.blind_categories`, inside the same instant as the
  curves (`voids_recounted` on each category). Per row, as the page counts
  a void; not by `bet.of`.
- **The guard, inside the payload builder**:
  `calibration.assert_each_void_count_is_its_cards`, run by
  `blind_categories` after the outlook's guard. Refused by name
  (`calibration.PooledVoidCount`, a `MergedCurve`, so `/api/scorecard`
  answers 500): a void count that is not a whole number; one counted on
  another card than the category's, on a card the source left unnamed, or
  on any card in a sport that does not split by card; one the recount
  made without the door does not make; and a void rate that is not its own
  counts' arithmetic.
- **Gate step 2**: `audit.check_a_ufc_void_count_is_its_cards` builds each
  carded sport's table (UFC) on the record's copy and fails by name, its
  row registered after the outlook's in `tools/verify.py`.
  `audit.check_the_blind_outlook_is_never_pooled` leaves a
  `PooledVoidCount` to it rather than filing it as an outlook's pool.
- Nothing stored changes, and no interface code: app.js draws the
  category's own `voided` in the "Withdrawn" cell and under the chart.

### THE CHECKS

- **Tests**: `tests/test_void_count_per_card.py`, 10 -- all 10 fail on
  3cb376e (the file laid over its archive): the behaviour ones for the
  right reason (the eighteen's world: Contender Series (2, 6, 0.75) and
  Numbered card (0, 6, 1.0) where (2, 0, 0.0) and (0, 0, None) stand; the
  drawn Numbered card (0, 6); a card the source left unnamed counted
  under all three cards, 7, 7 and 7), the rest for the door, the guard and
  the gate row that are not there. `tests/test_multisport.py`'s LAW 6
  readers name `withdrawn_forecasts` and `category_filter` in place of
  `void_count`; `tests/test_guards.py`'s harness list names the planting.
  The touched and neighbouring modules (`test_void_count_per_card`,
  `test_multisport`, `test_guards`, `test_outlook`, `test_props`,
  `test_voids`, `test_calibration`, `test_api`, `test_standing_pass`,
  `test_counted_once`): all pass, exit 0.
- **The planting** (`tools/guards/plant.py`, `LAW_VOIDS_PER_CARD`, in
  `main()` and `tests/test_guards.py`'s list):
  `plant_a_pooled_void_count` -- the eighteen's shape on a scratch world (a
  Fight Night card whose three final passes are withdrawn and whose early
  passes stand, a Contender Series card with none, a Numbered card still to
  come). ESCAPES on 3cb376e (the fixed `plant.py` laid over its archive):
  "the Record page states (settled, withdrawn, void rate) {'numbered': (0,
  3, 1.0), 'fight_night': (3, 3, 0.5), 'contender': (2, 3, 0.6)} ...; and
  nothing checks a void count's card". CAUGHT here: each card states its
  own (Fight Night 3, rate 0.5; Contender Series 0; Numbered card 0), and
  the count as it stood, the curve asking its void count without the card,
  and every card's withdrawals named as the asked card's are each refused
  by the Record page's builder (two by the gate too: the third is seen by
  the recount alone), and six pooled payload shapes and a card named in a
  sport that declares none are each refused by name.
- **Gate step 2's rows this touches, dry-run on this tree on both copies**
  (`voidcard/gate_rows.py`, a read-only handle, not `tools/verify.py`
  whole): the new row, the outlook's, the priced record's and the
  at-the-line record's, as is and with the 18 voided -- 8 of 8 pass; and
  the source scans the change could trip (orphans, shadowed definitions,
  the one distinct-bet key, starts as instants, no replacing write, no raw
  open, the side in prose and its one door, the recommendation door, the
  counted-once door, the renderer's prose) -- 11 of 11.
- **`plant.py` whole**: 409/409 planted violations caught (question 35's
  408 and this one), exit 0, 2026-10-01T05:37:36Z to 05:46:28Z.
- **The full suite**: 2,372 passed, 4 skipped, none failed, exit 0
  (question 35's 2,358, this change's 10, and `test_multisport`'s four
  for `category_filter`), with a dummy non-secret `GRIDIRON_ACCESS_TOKEN`
  and TMP and TEMP at their defaults, 05:46:42Z to 06:13:56Z; no file of
  the change edited while it or `plant.py` ran (every changed file's hash
  the same before and after; this section's two results were written in
  after); the only test that reached the network is the suite's own
  marked one.
- **The copies**: the verified copy and its one scratch copy (`voided.db`),
  each with its -wal and -shm, were deleted at 2026-10-01T05:35:08Z, and the
  measurement's four payload dumps at 06:14:19Z (`compare.txt`, the
  figures above, kept). Nothing was written to the
  live record; no network; the main checkout, the held branches, the live
  app, every scheduled task and `.env` untouched; nothing pushed.

### FOUND, NOT BUILT *(for question 34; none is LAW 1, LAW 3 or a gate count)*

- **The headline curve is every card's.** `calibration.scorecard`'s
  `headline` for UFC is the moneyline curve across every card (53
  settled), with every card's voids -- consistent with itself, drawn only
  where no category matches the chosen market and forecaster (never for
  UFC), and not among question 34's five names; a UFC curve pooled across
  cards all the same, which question 34's first words reach.
- **The line under the chart names no card.** For UFC it draws the first
  category of the market and forecaster, the Numbered card's ("Moneyline,
  statistical. 0 resolved."), without saying whose card it is -- words,
  not a count; beside question 34's tier table and badges.
- **A withdrawn pass whose question still stands.** The void count counts
  withdrawn FORECASTS, as it always has (R4): Fight Night's 6 are final
  passes whose early passes stand in the curve's 39, so its void rate
  (0.1333) counts six questions that were not lost. A reading for the
  operator if "void rate" should mean questions.
