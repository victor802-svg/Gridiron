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

### 2026-09-01 — `docs/mockup/gridiron_desk.html` is not in the repository

The desk brief (D1–D5) requires it and stops at its first act without it. A
rendered image was supplied in chat, which shows the layout but not the
measurements the brief cites.

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

## The header does not fit between 640px and 900px

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

## The slate clock's "in progress" state cannot be reached yet

Found 2026-09-01 while rendering E3's three countdown states. `games.status`
carries a CHECK constraint permitting only `'scheduled'` and `'final'`, so a
game cannot be marked as under way and the middle state — "in progress · 12 of
60 final" — is unreachable. "upcoming" and "complete" both render (the latter
seeded on a COPY of the database; the live record was not touched).

This is not a defect to fix on its own: live status arrives with the L1 live
poll, which is the thing that would set it. **L1 must widen that constraint**,
and the seeded render of the middle state belongs in L1's QA rather than being
left as a gap here. Noted so the phase that needs it finds it.

## The phone shows nothing live

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

## The phone has not received a push yet

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

## 2026-09-02 — GRIDIRON_16

- **NFL week 1 holds two prediction sets.** `predict:nfl` ran twice on
  2026-08-29 (05:55Z and 07:34Z) and wrote a full second set: 104 written,
  78 standing, 26 superseded. Both rows count in calibration, so week 1
  counts 26 questions twice. LAW 3 forbids deleting either. Needs a ruling
  on whether a duplicate run should be refused or flagged at write time.
- **`dumbbell()` in `app.js` has no call sites.** Exported for tests only.
  Pre-existing; left alone under GRIDIRON_16 R3 because it is not on Picks.
- **Rotate the ntfy topic and the Anthropic API key.** Both appeared in a
  session transcript.
- **The ntfy push is ready but unreceived.** The phone app is not set up.
  Carried from BRIEF A phase O5 item 3, which STEP 0 stopped.

## 2026-09-02 — GRIDIRON_13

- **The app and the OS scheduler disagree about football.** `predict:nfl` is
  recorded as 09:00 and the Windows scheduler holds 11:00, and no
  `predict:cfb` task is installed on this machine at all. Both facts are
  stated in words on Settings > When it runs. Which one is right is an
  operator decision, not a bug to be quietly reconciled.
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
