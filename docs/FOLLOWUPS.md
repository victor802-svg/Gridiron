# Follow-ups

Work deferred with a date, and lessons that need acting on rather than
remembering. Consolidated here 2026-09-01; earlier entries were scattered
through close-outs and are gathered below with their original dates.

---

## Open

### ~~2026-09-01 — THE SUITE IS TOO SLOW TO RUN WHOLE~~ — CLOSED 2026-09-02

The full suite takes about fifteen minutes. To fit inside a command timeout it
was being split — browser tests in one run, everything else in another — and
**both halves passed while the whole suite failed.**

The failure was real: `test_side_arithmetic` reads the live record, and the
halves happened to run before the college slate was written into it. A guard
that only fails when the pieces are run together is a guard that a person
under time pressure will not see.

**The gate needs to run whole, so the suite needs to get faster.** Two obvious
routes, neither yet measured:

- **parallelise** — `pytest-xdist` across processes. The browser tests hold a
  server and a Chromium each, so this needs the fixtures checked for shared
  state before it can be trusted;
- **tier it** — a fast tier that runs on every change and a full tier that runs
  before a commit, with the split declared rather than improvised. The risk is
  that the tiering itself becomes the place a failure hides, which is exactly
  what just happened, so whichever tier is skipped must be named in the output.

**Measured again 2026-09-01 while gating the desk work: twenty-eight minutes**,
not fifteen. And worse than slow: `verify.py` runs pytest with
`capture_output=True`, so for the whole twenty-eight minutes there is no way to
tell a slow suite from a hung one. The first diagnosis attempted here was "it
is stuck" — the CPU time said six per cent utilisation — and a process was
killed on that reading. It was wrong; the suite was fine and had in fact just
passed. So there are two fixes, not one: make it faster, and **let it report
progress while it runs**. A gate nobody can watch is a gate people learn to
skip, and the wrong guess about why it was quiet cost more than the wait would
have.

**CLOSED 2026-09-02.** The full gate is 6.87 minutes and the suite is 3.16,
serially, with nothing deferred. Neither route in this item was the answer:
parallelism was not needed, and the tiering was built only as a safety net
that names a skipped tier rather than as a mode anything uses.

The cause was two tests fetching a whole college football season on every run
-- 416s and 353s -- because they stubbed three sports' loaders and not the
fourth. Shutting the network by default for every unmarked test then cut the
suite from 14.58 minutes to 3.16, so the silent fetching went well beyond
those two. See `gate: 28 minutes to under 7` and MENTOR section 3.

Still true, and now cheap: **run the whole suite in one process before claiming
it is green.**

### ~~2026-09-01 — `docs/mockup/gridiron_desk.html` is not in the repository~~ — CLOSED 2026-09-05

The desk brief (D1–D5) requires it and stops at its first act without it. A
rendered image was supplied in chat, which shows the layout but not the
measurements the brief cites.

**CLOSED 2026-09-05, overtaken.** The file is in `docs/mockup/` now, and the
desk it described was deleted on 2026-09-04 (cards UI, R1): one layout at
every width.

### 2026-12-01 — the bowls decision

Whether to forecast college bowl games, and if so whether they are their own
calibration category. Neutral sites break the home-field assumption the margin
model rests on, rosters change between the regular season and a bowl so the
ratings describe teams that no longer exist, and about 40 games bolted onto 890
is a small, systematically different sample. Decide in December with the
regular season's forward record in hand.

### 2026-09-14 — read the rung distribution

Two weeks of `prop_rung_claims`. If below-floor claims cluster at 60–69 near
the mean rung, the floor is working as designed rather than the ladder being
mis-set. `gridiron rungs --sport mlb` refuses to read a verdict before then.

### after the gates fill — the third forecaster

The correction machinery is per (sport, market, forecaster) and the LLM
forecaster has no settled rows at all, so its correction cannot be fitted, let
alone graded. Revisit when any category reaches 200 settled.

### the drift question's read-date

Fifty drift pairs in one category. MLB moneyline is the only candidate and it
stops accumulating on 2026-09-27, so this may not be readable this year. The
report gives the count and nothing else until the gate clears.

### 2026-08-31 — the dead-but-named sweep (ruling 2, its own session)

Run the shadowed-definition guard's question backwards: what other shapes are
dead but read as live? Include an `app.js` orphan scan — nothing automated
looks at that file, which is how `pickSentence` sat there for two sessions
carrying the K1 verb table.

---

## Lessons that need a mechanism, not a memory

### 2026-09-01 — six of nine bugs in the CFB build were found by LOOKING

Renders and printed numbers are outperforming the test suite on interface and
data-shape work. Not a defect to fix — an argument for rendering earlier and
more often, and for treating "the number disagrees with the other number" as a
first-class check.

### 2026-08-31 — a `\b` in a generated regex has corrupted five guards

Fixed by the scanner-fixture ruling: every compiled pattern declares a
known-positive and a known-negative, checked at import. The fifth instance was
`SNAKE_CASE` itself, which had been matching nothing, so the plain-words law's
shape-detecting half was dead while its explicit name list kept working.

### 2026-08-31 — verify a new measurement against a source that CAN change

The drift pass measured the HTTP cache for its first eight rows. Any future
"second reading" of anything needs the same question asked of it: is the second
read capable of differing from the first?

### 2026-08-31 — a run that writes nothing commits nothing

The only commit in the prediction loop is inside `write_prediction`. Any
side-record written during a run must commit its own rows or be lost, as the
first fifteen rung-log measurements were.

### 2026-08-31 — an inert CSS property is invisible

`grid-column` on a flex child; `flex: none` on an item expected to shrink,
twice. Nothing fails; the layout is simply not what the rule says. Worth a scan
for properties inert against their parent's display mode.

### 2026-08-31 — hardcoded lists of sports go stale silently

Four tests hardcoded three sports and broke when a fourth arrived; the schedule
panel's test hardcoded four tasks and broke when a fifth did. All now derive
from `config.SPORTS` and `tasks.TASKS`.

---

## Measured and carried

- **NFL team names cover 30 of 34 tricodes.** LA, OAK, SD and WAS are
  pre-relocation codes with no row in ESPN's current feed.
- **Thirty-two NFL prop rows carry `prop_type = NULL`** (fs1, before 07:34 on
  2026-08-29). Permanent under LAW 3, handled at the reading end. Any new
  consumer must decide explicitly whether it is reading or querying.
- **One college venue could not be geocoded** — Sacred Heart, Fairfield CT.
  237 of 238. Its games have no travel figure, recorded absent.
- **The FCS scoring bias is unquantified.** A lower-division team enters the
  record only through its games against FBS opposition, so its scoring form is
  understated. Worth measuring once a college season has settled.

## The college spread ladder is too short for its own sport

Found while measuring R4 on 2026-09-01. `CFB_SPREAD_LADDER` spans -24.5 to
+6.5. Under the new nearest-margin rule, **45 of the 60 games on the 2026-09-05
slate landed on -24.5**, the end of the ladder, because cross-division expected
margins reach sixty points. Those questions are still lopsided — the rule
simply has nowhere better to put them.

Widening the ladder is a dated change to a declared constant and needs its own
measurement: the distribution of expected margins across a full season, not one
September slate, which is the most cross-division weekend of the year. Do it
after a few slates of real margins, not from the one that prompted it.

## `cfb_asked_line` now duplicates `cfb_srs_diff`

Same date, same cause. The rung is chosen as a step function of the rating
difference, so the asked line carries no information the rating does not.

**Measured on the refit, rather than predicted:** neither factor was reported
constant and neither was dropped, and the two coefficients shrank together
(`cfb_srs_diff` +0.0851 -> +0.0655, `cfb_asked_line` +0.1003 -> +0.0802) rather
than one absorbing the other. So the fit is stable and this is not urgent. What
remains is that the per-factor "why" now attributes one signal across two
names, and a reader is owed better than that.

Retiring or reworking a declared factor is a LAW 2 act with a dated note, and
**a repair is not a discovery** — whatever is written must say which this is.
Measure the two factors' correlation on a real training set first; the answer
may be that the asked line stays and the rating is the one that moves.

## The rebuilt bundle could not be launched to confirm it renders

2026-09-01. E0.1 asked for a rebuild "from HEAD, relaunch, and confirm the
compact rows / desk render in the exe". The rebuild succeeded and is stamped
`62e7f3b`; **launching it was blocked by a Windows Application Control
policy** (`WinError 4551`), which is a security control and not something to
work around.

What was confirmed by inspection instead, and it is most of the claim:

- every web asset in `dist/Gridiron/_internal/gridiron/web/` is **byte-identical**
  to the repository's, so the bundle carries the current interface rather than
  the 2026-08-29 one;
- `desk-rail`, `rail-glance`, `tiles` and `slate_title` are all present in the
  bundled assets — the desk, the rail and the date-worded slate title;
- all four sport adapters are in the build graph, including `cfb`, which the
  old spec would have left out;
- the stamp file is inside the bundle and carries the commit and date.

What was NOT confirmed: that the exe starts, serves, and paints those assets.
The operator can check that by running `dist\Gridiron\Gridiron.exe` on a
machine where the policy permits it, or by signing the binary. Until then the
phase is PARTIAL, and it should not be reported otherwise.

## The header does not fit between 640px and 900px — narrower band, 2026-09-05

Measured 2026-09-01 while adding the tab records (E2/R1), and **pre-existing**:
before that change the header needed 941px of content, and it overflowed the
page at 900px and below. Afterwards it needs 892px — slightly better, with the
records added — but the band between the phone breakpoint (640px) and about
900px still pushes the document sideways rather than clipping.

| width | page overflow, before E2 | after E2 |
|---|---|---|
| 1100 | 0 | 0 |
| 1000 | 0 | 0 |
| 900 | 49px | 45px |
| 800 | 149px | 145px |

A brand, four sport tabs carrying records, and four page links do not fit in
that band. The phone breakpoint already collapses the nav for 640px and below;
what is missing is the intermediate step. Not urgent — the declared widths
(1440, 1280, 1279, 1100, 390) all pass — but a tablet in portrait lands
exactly here, and a page that scrolls sideways has lost something off the edge.

Do it with the nav's existing "more" affordance rather than another font-size
reduction; the tabs are already at 8px padding and 10px record type.

**Re-measured 2026-09-05 by the audit, against the live record:** 640, 800 and
900 are clean; **700 still overflows by 80px.** The band has narrowed, not
closed. Still open.

## ~~The slate clock's "in progress" state cannot be reached yet~~ — OVERTAKEN 2026-09-05

Found 2026-09-01 while rendering E3's three countdown states. `games.status`
carries a CHECK constraint permitting only `'scheduled'` and `'final'`, so a
game cannot be marked as under way and the middle state — "in progress · 12 of
60 final" — is unreachable. "upcoming" and "complete" both render (the latter
seeded on a COPY of the database; the live record was not touched).

This is not a defect to fix on its own: live status arrives with the L1 live
poll, which is the thing that would set it. **L1 must widen that constraint**,
and the seeded render of the middle state belongs in L1's QA rather than being
left as a gap here. Noted so the phase that needs it finds it.

**OVERTAKEN.** `games.status` admits `'in'` (verified 2026-09-05), and the desk
whose clock this described was deleted on 2026-09-04.

## ~~The phone shows nothing live~~ — OVERTAKEN 2026-09-05

Found 2026-09-01 in L4's 390px render. L1–L3 gave the desk three game states —
upcoming, live, final — with scores, clocks and verdict chips on the tiles and
in the rail. **The compact rows below the breakpoint have none of them.** A
reader following a slate on a phone sees the same card at kickoff, at half
time and an hour after the final whistle.

This is a scope boundary rather than an oversight: the L2 brief is written
entirely in terms of tiles and the rail, and D4's promise was that the phone
renders exactly as it did before. Extending the row was not asked for, and
doing it unasked would have been a redesign of the primary surface tucked
inside a verification phase.

But it is a hole. The row already has a corner (it shows the chance clause,
"TOLEDO WINS"), and the three states are composed server-side on every card —
`score_line`, `clock_line`, `running_total`, `verdict` are all present in the
payload the phone already receives. So this is placing existing strings, not
building anything: an afternoon, not a phase.

Decide whether the phone follows a live slate. If it should, the row's corner
is where it goes.

**OVERTAKEN 2026-09-04.** The compact rows and the desk were both deleted; one
card layout renders at every width and carries the same states everywhere.

## Live scores for basketball and football need an identity bridge

2026-09-01, from L1. The live poll follows college football and baseball
because their game ids match the feed exactly — a college id IS the ESPN event
id, and a baseball id is statsapi's `gamePk` with a prefix. The other two do
not match at all:

| sport | our id | feed id |
|---|---|---|
| nba | `nba_0022200001` | an NBA-stats id |
| nfl | `2016_01_CAR_DEN` | an nflverse key |

Following them means bridging by team and date. This project has built exactly
one identity bridge — the ESPN-to-MLB player crosswalk — and the rule it set
was that a bridge is **measured**, stored with both match rates, and refuses
ambiguous pairs, because a wrong match attaches a live score to the wrong game
and nothing downstream notices. That is a phase, not a line.

Until then the schedule panel names the two sports and says why, rather than
showing them with blank figures.

**Still open 2026-09-05, and one wider:** the fights are not followed either —
`live.GAME_HOURS` and `live.ESPN_LEAGUE` have no `ufc` entry (audit, B4).

## Drift arrows wait for their snapshots

2026-09-01, deferred deliberately by the live brief. `gridiron/drift.py` needs
`MIN_PAIRS = 50` pairs at `MIN_DISAGREEMENT = 0.05` before it can say anything,
and the near-start snapshots only began being taken for real after the
freshness fix. **Revisit once the record holds fifty usable pairs** — count
them before designing anything, because the arrow is only worth drawing if
there is something behind it.

## Team pages are a separate design

2026-09-01, named by the live brief as out of scope. Not deferred for lack of
data: the record holds ratings, schedules, venues and per-team results for four
sports. It is deferred because "a page about one team" is a design question
(what is it FOR — checking a pick, or browsing?) and answering it inside a
phase about live scores would have produced whatever was easiest to build from
the tables that happened to be open.

## A backup before every schema rebuild

2026-09-01, the lesson from L1 rather than a task. Widening `games` emptied a
live 21,527-row table twice before it worked, and the only reason that is a
footnote is a 700MB copy taken beforehand. Two traps, both now written into
`live.ensure_live_columns`:

- `ALTER TABLE ... RENAME` follows the rename into every child's foreign key;
- `executescript()` commits, so BEGIN/ROLLBACK around it protects nothing.

**Any future table rebuild takes a copy first, and runs `PRAGMA
foreign_key_check` before it commits to anything.** The check is what turns
"it looked fine" into evidence.

## ~~The phone has not received a push yet~~ — CLOSED 2026-09-05

2026-09-02, from GRIDIRON_12 phase O5. The ntfy channel is built and the POST
is accepted — `HTTP 200` from ntfy.sh, recorded in `notifications` — but
**nothing has arrived on a phone, because no device is subscribed to the topic
yet.** The operator has not installed the app.

The distinction is the whole point of recording it: the channel is proven as
far as the server and unproven past it. A `200` means ntfy accepted the
message for a topic; it says nothing about whether anyone was listening.

To finish it:

1. Install ntfy (Android, iOS, or ntfy.sh in a browser).
2. Subscribe to the topic in `.env` under `GRIDIRON_NTFY_TOPIC`.
3. Trigger a real send — the next resolve run that settles anything will do
   it, or force one outside quiet hours.

**The topic should be rotated first.** It was printed to a terminal during
this session and is therefore in the session transcript. Anyone holding it can
read the messages — counts and team names only, but still.

```
python tools/make_token.py --ntfy --rotate
```

**CLOSED 2026-09-05.** The topic was rotated by the operator, the new one is
read from `.env`, and one test push was sent through `notify.send` and
accepted (`HTTP 200`, recorded `sent`) so the phone could re-subscribe.
Receipt on the phone is the operator's to confirm; nothing here can.

## 2026-09-02 — GRIDIRON_16

- ~~**NFL week 1 holds two prediction sets.**~~ **OVERTAKEN 2026-09-03.** The
  standing-forecast rule (latest row before start, per question and
  forecaster) grades one row per question, and `predict.already_written`
  refuses a rerun at write time. The audit of 2026-09-05 confirmed no
  superseded row enters a scorecard, and made the version table and the
  pace line use the same clause (they had not).
- **`dumbbell()` in `app.js` has no call sites.** Exported for tests only.
  Pre-existing; left alone under GRIDIRON_16 R3 because it is not on Picks.
  Still there 2026-09-05 (`app.js:688`); nothing scans `app.js` for orphans.
- ~~**Rotate the ntfy topic and the Anthropic API key.**~~ **CLOSED 2026-09-05.**
  Both rotated by the operator and verified: one probe call through the
  budget ledger returned 200; git history, docs and tracked files hold
  neither value (audit, A7).
- ~~**The ntfy push is ready but unreceived.**~~ **CLOSED 2026-09-05**, see the
  push item above.

## 2026-09-02 — GRIDIRON_13

- **The app and the OS scheduler disagree about football.** `predict:nfl` is
  recorded as 09:00 and the Windows scheduler holds 11:00, and no
  `predict:cfb` task is installed on this machine at all. Both facts are
  stated in words on Settings > When it runs. Which one is right is an
  operator decision, not a bug to be quietly reconciled.
  **2026-09-05:** Predict-CFB is installed (09:00). The machine holds 11 of
  the app's tasks; Capture, Recalibrate and both UFC passes are not
  registered, and re-running the installer is the operator's act. See
  `docs/AUDIT-2026-09-05.md`.
- **The digest's own page is gone** (GRIDIRON_13 P5). Its data still feeds the
  greeting, and a particular day is a click on the Results calendar. If a
  day-by-day narrative is wanted back, it is a new page rather than a
  restoration.

## 2026-09-02 — the MLB run line and totals

- **Wind at first pitch is not a declared totals factor.** The Open-Meteo path
  exists but `weather_forecasts` holds nine rows, all football: there is no
  stored history for a fit to see, so the factor would be absent on essentially
  every training row and would be the broken instrument the constant-factor
  check exists to catch. Revisit once MLB kickoff forecasts are being stored.
- **The rolling combined form runs about 5% high** as an estimate of actual
  game scoring: asking the total at that form, rounded down to a half, still
  goes over only 45.1% of the time over 7,211 games. The fit's intercept
  absorbs it. Worth re-measuring once the totals category has a settled record.
- **Run-line and totals PRICES are not stored.** ESPN carries them
  (`overOdds`, `underOdds`, `homeTeamOdds.open.spread`) and the comparison
  currently derives an implied probability from the LINE plus a measured SD
  instead. Storing the prices would give a second, independent comparison.

## 2026-09-02 — the CFB ladder

- **BLOCKED, by design: what `cfb_asked_line` is FOR.** Under the
  nearest-margin rung rule the asked line is a coarsened function of
  `cfb_srs_diff` — the rung is chosen from the expected margin, which is
  computed from the rating difference — so the factor carries almost nothing
  the ratings do not, and **its coefficient cannot be read as an independent
  effect**. Whether it should be retired, kept as the question's own label, or
  replaced by the residual between the rung and the expected margin is an
  operator ruling. Documented on the factor's note and here; not changed. The
  2026-09-02 extension changed the coarseness, not the dependency.
- **The college spread base rate is 0.371, not 0.5.** The rung is chosen AT
  the expected margin, so a well-calibrated expectation should cover about
  half the time. It covers 37%, which means `cfb_expected_margin` runs high —
  the home side wins by less than the ratings say. Worth measuring properly
  once the college record has settled rows; the fit's intercept absorbs it in
  the meantime.
- **4.9% of college games are refused as beyond the ladder** and recorded
  absent rather than clamped. That is the ruling working, but it is also 80
  games a season with no spread question. If that proves too many, the answer
  is another dated extension, not a wider tolerance.
- **A dead selector shipped and nothing failed.** `applyLive` fetched
  `.tile-mkt` after the class was renamed `.tile-score` (bd7ac2f), so every
  live tick threw and the desk's scores silently stopped moving. Fixed
  2026-09-02, with `audit.dead_selector_faults` and a browser test that drives
  a real poll. **The lesson is the coverage shape, not the typo**: every desk
  test asserted on the FIRST render, and a complete slate never polls — so the
  live path had no coverage from either direction. Worth asking which other
  paths are only ever exercised at first paint.
- **NCAAF puts 15 of 17 picks in STRONG (88%), NFL 24 of 78.** Under ruling R2
  Picks opens on STRONG, so an over-confident college model is now the first
  thing a reader sees. Same root cause as the 0.371 base rate above.
- **A prose claim nobody tests is where my bugs land.** Three of six bugs in the
  2026-09-03 timing build were caught by looking, not by a test, and all three
  were sentences: a note claiming a forecast had been superseded when none
  existed, an installer comment claiming two MLB passes where one was
  registered, and a time that read plausibly and was after most first pitches.
  The suite checked behaviour; nothing checked what the prose asserted about it.
  Worth a scan that pairs a claim with the thing it claims.
- **The NFL `injuries` table has no timestamp column.** 55,554 rows, none dated,
  so NFL report timing cannot be measured and the final-pass time for football
  is a judgement rather than a measurement. One `fetched_utc` column plus the
  loader writing it makes it measurable within a week of games.
- **A daily MLB final pass cannot serve a 7.47-hour card.** At 14:30 local the
  afternoon games have started, so roughly the 10:00-local cluster (1,101 games
  in the record) is out of its reach and keeps its early forecast. The proper
  fix is a per-game trigger rather than a daily one.
- **Live lineup captures are buried under backfill.** 6,902 of 6,958 stored MLB
  lineups came from one historical load on 2026-08-30; only 39 are real
  pre-game captures. A `source` column separating a live capture from a
  backfill would keep the measurable rows findable as they accumulate.
- **CFB's expected margin is measurably wrong, and now has a number on it.**
  (2026-09-05: measured again in Session E, the fitted slope was recorded
  and NOT adopted — `DECISIONS_MADE.md`, 2026-09-04. Still an operator ruling.)
  `cfb_expected_margin` uses slope 1.0 and intercept 9.79; least squares over
  1,625 completed games says **+4.848 + 0.9351 x rating_diff**. The intercept is
  nearly double what the data supports, which is the documented 0.371 spread
  base rate expressed as a coefficient. Not changed on 2026-09-03: correcting it
  changes which questions college football asks, which needs an operator ruling.
- **A rating difference does not buy its own value in margin.** Measured
  2026-09-03: ten points of rating difference buys 4.4 points of margin in the
  NFL (n=2,725) and 6.0 in the NBA (n=4,841). Any future instrument that assumes
  a slope of 1.0 will expect blowouts that do not arrive.
- **`precipitation` is still constant on the NFL spread fit** (760 rows, one
  value). DIAGNOSIS recorded it as a broken instrument; the LAW 6 training-set
  repair of 2026-09-03 made it more visible rather than fixing it. It is a
  data-loading job.
- **NBA's `nba_asked_distance` correlates 0.2908 with the rating**, the highest
  of the three sports and worth re-measuring once the NBA record has settled
  rows. The residual still tracks the rating slightly through the ladder's
  uneven spacing at the extremes.
- ~~**The reasoning pass stopped writing on 2026-09-02 and the key is BLOCKED.**~~
  **CLOSED 2026-09-05.** Key rotated and verified; the pass wrote 42 UFC rows
  that day. The slates that were answered while the key was blocked keep
  their statistical-only halves for ever under the answered-once rule:
  baseball days 160 and 161 and college football 2026-09-04. Football week
  1 has not started, so its final pass can still write the second half.
- ~~**`injuries` holds nothing for 2026.**~~ **WITHDRAWN the same day, and it
  was my error.** I reported this as a defect while building the capture pass.
  It is the correct state: the nflverse 2026 injuries release 404s because the
  season has not started -- the first NFL kickoff is 2026-09-10 -- and the
  loader handles that properly, returning zero and warning only for seasons
  that have completed games. The 2025 file fetches fine at 695KB. Nothing is
  wrong here, and the capture pass will have rows to stamp from week 1.
- ~~**UFC is loaded but not declared.**~~ **OVERTAKEN 2026-09-03**: declared,
  84 forecasts written. Its two scheduled passes were registered in the
  installer only on 2026-09-05 (audit, A4).
- **ESPN carries an OPENING moneyline for UFC.** DIAGNOSIS records H1a as NOT
  TESTABLE because no free source publishes opening lines for the NFL seasons we
  hold. In UFC it is testable, on 52 cards a year. Nothing acts on this yet.
- **The weather repair is unfinished by design.** `weather_observed` exists and
  is deliberately empty: no observed-weather source is wired. Until one is, the
  college wind coefficient is still fitted on observed and applied to forecasts.
  S5's fourth planting waits on the same thing.
- ~~**The compact rows truncate their own titles at 390px.**~~ **FIXED
  2026-09-03**, on the day the event tier was added to the same pick line:
  deferring a defect I had just enlarged was not a defence. Both that line and
  the side name under the percentage wrap now, and a 390px render shows no
  ellipsis element anywhere in the frame. Original entry:
-  `.row-title` and
  `.row-pick` carry `text-overflow: ellipsis`, so a phone reader sees
  "BRISSETT · PASSI…" and "SF DOES NOT…". That is exactly what the no-tile-
  truncation law forbids — the card says there is something it is not showing
  and then does not show it — and the existing guard misses it because it scans
  the frame at desk width, where nothing truncates. Present since `24212a6`
  (2026-08-30), found while rendering the count markets at 390px on
  2026-09-03. The fix is to let the row grow, as the desk tiles do, and to
  widen the truncation scan to every breakpoint the suite already visits.

## 2026-09-05 — the audit

Everything the audit found is ranked in `docs/AUDIT-2026-09-05.md`, with the
fixes it made and the decisions it left. The decisions, in one line each:

- **The installer has not been re-run** since Capture was added; Recalibrate,
  Predict-UFC and Final-UFC were added to it on 2026-09-05. Running
  `tools/schedule_install.ps1` is the operator's act.
- **Tasks run in a console as the logged-on user** and two have died with a
  control-C exit (Refresh 2026-09-05 03:00Z, Predict-MLB). Whether they should
  run hidden is a machine decision.
- **College football and UFC file a game under its UTC day**, so a late
  Saturday kickoff is a Sunday slate. The slate key is stamped on every
  prediction; changing the convention is a ruling.
- **No stored fingerprint of the record exists.** The audit recorded one
  (`b15a9f6f…`, 765 rows); a mechanism that keeps one is a design.
- **Settings > Health cannot show Gridiron-CatchUp**, the one task that has
  never fired, because it is not a `TaskSpec`.
- **42 UFC reasoning rows quote encoded numbers** ("a combined finish rate of
  0.3333") — written before the factors-in-words fix, append-only, and
  answered once.
