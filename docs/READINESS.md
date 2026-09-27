# READINESS — is this engine's output fit to act on?

One question, answered with numbers. Six declared criteria, each with its
current value and a verdict. **The document is expected to be red for a long
time**; a run that reports six failures and the reasons is a successful run.

**A THRESHOLD IS NEVER MOVED TO PRODUCE A PASS.** Changing one requires a dated
operator ruling recorded in this file, with the old threshold still visible
beneath it. There are no such rulings yet.

## The standing answer

**The engine's output is a forecast to read, not a recommendation to follow.**
Four of the six criteria below fail, and the two that now pass are both about
whether the machine works, not about whether it is right. The app already restricts itself accordingly: one
flat unit, the same for a 92% claim as for a 62% one, with "no measured edge"
beside it — and that restriction stands until all six pass.

In plain words: **the operator is acting on an unproven signal and should
treat the money as entertainment money.** Nothing in this record yet shows the
model beating a price, and the one market with enough settled questions to
check shows the opposite.

**Finding of 2026-09-26 (operator ruling, below): the model shows no edge.**
In MLB moneyline the market is better beyond noise for both forecasters, and
nowhere does the model beat the market.

## Run log

Each run appends a row. Nothing is overwritten.

| date | 1 gate | 2 recs | 3 CLV | 4 outcomes | 5 broken | 6 coverage | verdict |
|---|---|---|---|---|---|---|---|
| 2026-09-07 | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | not fit to act on |
| 2026-09-07 (2nd) | **PASS** | FAIL | FAIL | FAIL | **PASS** | FAIL | not fit to act on |
| 2026-09-23 | **PASS** | FAIL | FAIL (broken) | FAIL | FAIL | FAIL | not fit to act on |

## 2026-09-07 — the criteria in full

### 1. Gate fully green — **FAIL**

| measure | value |
|---|---|
| verify.py step 1, test suite | FAIL |
| verify.py step 2, planted violations | FAIL |
| verify.py step 3, one week end to end | PASS |
| verify.py step 4, live forward week | PASS |
| plantings caught | 218 of 219 |

The escaping planting, named by running the harness rather than by inheriting
an explanation: **`plant_a_code_name_in_rendered_llm_prose`**, guard
`audit.llm_prose_faults`, law "NO CODE NAME REACHES A READER". It does not
fail its violation — it never plants one. Its own precondition check finds the
shipped view already faulty and stops, and the fault it finds is *"no LLM card
was rendered on any slate, so this scan checked nothing"*.

**The previously inherited explanation for that was wrong.** It was recorded as
an empty-slate artefact of the hours before the daily predict task runs. It is
not: the current slates carry statistical forecasts (baseball's current day has
27 cards, football's week has 107). What is missing is the SECOND forecaster,
and the reason is criterion 5.

### 2. Recommendations produced — **FAIL**

| measure | value | threshold |
|---|---|---|
| recommendations recorded | 0 | ≥ 50 in one coverage entry |
| at-the-line claims (their price source) | 0 | — |
| priced forecasts written | 0 | — |

All three arrived today and none has run through a slate yet. A recommendation
needs a frozen distribution on the prediction and a venue price for the same
proposition; no stored prediction predates today's work with a distribution, so
the first ones appear on the next slate run.

### 3. Closing line value — **FAIL**

| measure | value | threshold |
|---|---|---|
| recommendations with a closing price | 0 | ≥ 50 |
| mean closing-line value | not measurable | positive |

**This is the criterion that decides the others.** It is the fastest honest
read available — about fifty observations, against several hundred for a win
rate — and it is at zero. Nothing about the other five matters if the engine
turns out to be buying rich.

### 4. Outcome evidence — **FAIL**

| measure | value | threshold |
|---|---|---|
| NFL totals settled (the one covered market) | 0 | ≥ 100 |
| NFL settled, any market | 0 | — |

The covered market is football totals and the football season has just begun.
Its gate cannot open this month.

### 5. Open BROKEN findings — **FAIL**

One, found by this session's own investigation and recorded in `FOLLOWUPS.md`:

**THE REASONING PASS HAS BEEN DEAD SINCE 5 SEPTEMBER.** Every call since
`2026-09-05T15:00:03Z` has returned HTTP 401, `"API key is invalid."` The last
successful call was `2026-09-05T02:56:26Z`; ten consecutive failures follow,
including both of today's scheduled prediction runs. A key IS configured (108
characters), so this is a rejected credential rather than a missing one — the
shape of a key that was rotated somewhere else and never updated here.

Consequences, measured: the second forecaster has written nothing for two
days; every LLM category's count is final rather than growing; and the guard
that reports it has been firing since, which is the guard working.

The fix is the operator's: put the current key in `.env` under
`ANTHROPIC_API_KEY`. This session does not edit that file.

**Checked again later the same day, after the operator reported updating it:
still rejected.** One live call to the venue returned the same 401. Two things
were measured rather than assumed:

- **`.env` has not changed.** Last modified 2026-09-04 16:47, and the key in it
  is the one being rejected. No `.env` anywhere under the sessions directory
  was modified today.
- **A Windows USER environment variable named `ANTHROPIC_API_KEY` exists and is
  10 characters long.** An Anthropic key is about 108. `config.setting` reads
  the process environment BEFORE the file, so once the app or a scheduled task
  starts in a session that inherits it, that 10-character value wins over
  whatever `.env` says. It has to be corrected or removed as well, or fixing
  the file will change nothing.

Neither was touched: `.env` is not this session's to edit, and a machine-level
environment variable is not either.

### 6. Coverage provenance — **FAIL**

| measurement | date | games | quoted strikes | covered |
|---|---|---|---|---|
| first | 2026-09-07 | 5 (NFL) | 297 | football totals |
| second | 2026-09-07 | 22 (16 NFL, 3 NBA, 3 CFB) | 1,172 | football totals |
| threshold | — | ≥ 200 | — | — |

Both measurements agree, which is worth as much as the numbers: football
totals covered at two cents wide and 442 contracts at the median; the spread
excluded for sitting in the busier half (1,480 against 961); the winner market
excluded for not being measured enough — 44 quoted strikes across 16 games,
because a winner market has two outcomes rather than a ladder, so it needs
roughly twenty games to clear the floor at all.

Basketball is out of season and the venue quotes almost nothing: 47 games
asked, 3 events answered, 37 requests unavailable. Baseball's remaining
scheduled game had no event.

**Two hundred games is not reachable from one sitting of this record.** It
accumulates as slates run, and the third leg of the coverage proxy — how often
a price is repriced — needs two looks at one ladder separated in time, which
the near-start pass has only just begun collecting.

## What would change each verdict

| # | what has to happen |
|---|---|
| 1 | The reasoning pass writes again, so the LLM view has a card to scan. That is criterion 5. |
| 2 | Slates run. Each one writes distributions, claims and any recommendation that clears the fee in a covered market. |
| 3 | Fifty of those recommendations reach a close. At football's one-slate-a-week pace this is a season, not a fortnight. |
| 4 | A hundred settled questions in football totals. Not before December. |
| 5 | A valid API key in `.env`. |
| 6 | Venue ladders for two hundred games, which accumulate at roughly twenty a week from football alone. |


## 2026-09-07, second run — two criteria move, and why the other four cannot yet

Run after the operator replaced the API key and the shadowing environment
variable was removed. **Nothing above is edited**; this section is what
changed and what it cost to find out.

### 1. Gate fully green — **PASS** (was FAIL)

| measure | first run | now |
|---|---|---|
| verify.py step 1, test suite | FAIL | **PASS** |
| verify.py step 2, planted violations | FAIL | **PASS** |
| verify.py step 3, one week end to end | PASS | PASS |
| verify.py step 4, live forward week | PASS | PASS |
| plantings caught | 218 of 219 | **222 of 222** |

Both failing steps were one finding, and the finding was the dead key. With the
reasoning pass writing again, the day's slate carried 22 LLM rows and the scan
that had reported "no LLM card was rendered on any slate" had a card to read.

**The escaping planting was then repaired for a second reason.** With the live
record clean it still reported NOT CAUGHT, because it worked by removing the
humaniser and re-scanning the live record -- which only ever planted anything
while some stored row still contained a code name. The prompt repair of
2026-09-05 stopped the model emitting them, so the planting had quietly stopped
planting. **A guard that depends on a defect still being present stops guarding
the moment the defect is fixed.** It now builds its own card in its own
in-memory record and renders it through the view the page uses. Three plantings
were added by the day's other work, which is where 219 became 222.

### 5. Open BROKEN findings — **PASS** (was FAIL)

Zero open. The reasoning pass writes again: the last 401 was
`2026-09-05T15:00:03Z`, the operator replaced the key, a 10-character Windows
user environment variable of the same name was removed on his instruction, and
a freshly started process authenticates. Measured rather than assumed -- 62
predictions written for the day, 22 of them from the second forecaster, $0.1052
spent, and `audit.llm_prose_faults` clean for the first time in two days.

### 2 and 3 were blocked by a clock, and that is now fixed

**The near-start pass fires every four hours against a two-hour window.** It is
the only writer of a near-start venue ladder, an at-the-line claim and a closing
price -- so it is the only thing that can ever move criterion 2 or criterion 3
-- and its only caller was `refresh`, on a four-hourly trigger.

Measured on the day's baseball slate: of twelve games, **three fell in no
firing's window at all** (19:10Z, 23:30Z, 00:10Z) and would have been looked at
once, at prediction time, and never again. That is not a slow start; it is a
quarter of every slate permanently unreachable, and it is why
`at_the_line_claims` and `recommendations` both read zero while `venue_quotes`
read 1,172.

The window's two hours were **not** widened to fit the scheduler. Two hours is a
declared meaning -- late enough that the day's news is priced, early enough not
to race the first pitch -- and widening it to make a number appear is the move
this document exists to refuse. The pass got its own half-hourly clock instead:
task `near-start`, Windows task `Gridiron-NearStart`, registered and fired once
under the scheduler at 02:53 local.

| measure | value | threshold |
|---|---|---|
| recommendations recorded | 0 | ≥ 50 in one coverage entry |
| at-the-line claims | 0 | — |
| priced forecasts written | 22 | — |
| venue quotes stored | 1,172 | — |

The first claims are due when the day's first game comes inside two hours, which
is 15:05Z. **If `at_the_line_claims` still reads zero on 8 September, the cadence
was not the whole story and the next session should say so plainly rather than
waiting another week.**

### 4 and 6 are unchanged, and are about time rather than machinery

Football totals is the one covered market, the season has just begun, and
nothing is settled in it. Coverage accumulates at roughly twenty games a week
against a threshold of two hundred. Neither can move this month.

### The verdict is unchanged: **not fit to act on**

Two criteria moving does not change the standing answer, and saying so is the
point of a run log. What passes now is that the machine works and that nothing
is known to be broken. **Whether its numbers beat a price is still unmeasured**,
and the criterion that will decide it -- the closing line -- is still at zero.


## 2026-09-07, a correction to criterion 2 and 3

Criteria 2 and 3 were recorded as blocked by the near-start pass's four-hourly
cadence against a two-hour window. That was measured and is fixed. **It was not
the whole reason, and the rest is larger.**

**No prediction in this record carries the frozen distribution an at-the-line
claim requires.** Zero, measured 2026-09-07 while rendering a priced card.
Baseball produces none by design — its margins are counts and
`questions.blind_distribution` refuses to invent a spread — the fights have no
margin, and football, which does have one, has not been forecast since the
distribution began to be written on 6 September.

So the first claim cannot appear before the football run on **9 September**, and
criterion 3 — the closing line, the criterion that decides the others — cannot
start counting before then. Neither threshold moves; what moves is the date
this document expects the first number.


## 2026-09-07 — baseball reaches the priced pipeline

**The date, recorded because AT_THE_PRICE Q4 asks for it: 2026-09-07.** The
first at-the-line claims in this project's record were written on this day, and
they are baseball: 43 claims from 31 of the day's 62 questions, 26 of them
line-less and 17 rung-matched.

Two things had to change and only one of them was in the brief.

**A claim needed a frozen margin distribution, whatever kind of contract it
was.** Four shapes are now distinguished: a winner contract needs nothing,
because the blind probability answers the venue's question exactly; a rung the
model was asked about needs nothing; a counting stat at a differing strike
reads the blind rate; only a spread or total at a number the model did not ask
about needs the distribution. That last one wrote nothing today, correctly:
baseball has no measured margin spread, because its margins are counts.

**AND BASEBALL HAD NO VENUE QUOTES AT ALL — zero of 1,172.** The venue's
baseball event ticker carries the first pitch, because baseball plays
doubleheaders and date-plus-teams does not identify a game. Ours did not, so it
matched nothing. Measured before the change: 20 of 22 games inside the venue's
open window match exactly, with no code aliases needed. Baseball now holds 290
quotes and **one covered market**: totals, 1.0¢ wide at the middle over 4,760
contracts.

**Criteria 2 and 3 are still FAIL and the reason has moved.** Claims exist now;
recommendations follow coverage, and baseball's moneyline is not measured
enough (26 quoted strikes across 10 games, against a floor of 50 across 3)
while its spread sits in the busier half. Nothing about the thresholds changed.
What changed is that the pipeline they gate is no longer empty.

## 2026-09-08 — the combo record opened, and it opened empty

**The date the combo record opened: 2026-09-08.** `venue_packages` exists from
this day, the daily read fetches every package the venue has open in the
declared series, and every one of them is stored with this project's verdict
beside it — priced, or refused with its reason.

**Which sports had a priceable package on that date: NONE.** Measured against
the venue twice, before building and after:

* The only readable package markets were `KXNCAAMBSGP`, college-basketball
  **same-game** parlays — for instance
  `KXNCAAMBSGP-26APR06CONNMICHSPREAD-MICHU144`, "Michigan covers -7.5 and
  UConn and Michigan collectively score under 144.5 total points", tagged
  `cbb` by the fetcher from its series prefix. That tag is correct: it is the
  men's college basketball final, `cbb` is not this record's `cfb`, and it is
  not in `config.SPORTS`, so the package is refused `unforecast_sport` — there
  is no forecast to price it with. `SAME_GAME_SERIES` also declares the
  venue's SGP naming, so a same-game package in a sport this record DOES
  forecast is refused as same-game rather than by whichever leg failed to
  match a game.
* `KXNBAPREPACK2ML`, `KXNBAPREPACK3ML`, `KXNFLCOMBO` and `KXNCAAMB2ML` list
  historical events and expose no markets in any status.
* **No baseball game package exists at all.** `KXMLBAWARDCOMBO` pairs two
  season awards, which this record does not forecast, and is deliberately
  absent from the declared series map.

So the Combos group ships as a heading, a counts line and one sentence: "The
venue has no package open today in any sport this record forecasts." That is
the answer to the question the operator has, and it is the answer measurement
produced rather than a gap in the work.

**Nothing about the criteria changed.** A package clears the same two
conditions a single does, its record is its own — `combo_2` and `combo_3`, per
sport, never counted toward a leg's N — and its closing line needs a hundred
observations where a single leg needs fifty, because a package's close is the
product of two or three moving quotes. The kill criterion is declared and dated
before the first package exists: at fifty settled in a sport, packages losing to
the close while that sport's singles beat it retires the sport's combo markets.

## 2026-09-08 — three dates the record has to carry (GRIDIRON_NIGHT_AUDIT item 9)

**The date the pipeline became whole: 2026-09-07.** Whole means every stage
had written at least one row: blind forecasts (since 2026-08-29), venue quotes
(NFL and college football from 2026-09-06 09:29Z, baseball from 2026-09-07
19:37Z once the ticker carried the first pitch), at-the-line claims (from
2026-09-07 19:37Z), and recommendations (the first eight, all baseball, from
2026-09-07 20:52Z). The closer had nothing to close until the first two of
those games went final on the night of 2026-09-08; the first closing price
is therefore still to be written as this is recorded.

**The backfilled-claims flag.** Seventeen of the first twenty-nine at-the-line
claims — every one stamped 2026-09-07 19:41Z, on games that had already
started — were priced against a quote taken after first pitch. They stand,
under LAW 3, and no column marks them: the record identifies them only by
`c.created_utc > g.kickoff_utc`, which returns exactly those seventeen and
nothing written since. The `quote_after_first_pitch` guard that forbids the
shape landed fifty minutes after them (commit `25d83b8`, 20:30Z). Anything
that reads the closing-line record should exclude them by that predicate, and
this paragraph is the flag until a column is.

**The combo record opened 2026-09-08 and was WITHDRAWN 2026-09-09.** It ran
for one day and never held a row.

**THE COMBO PRODUCT IS UNMEASURABLE BY CONSTRUCTION, and this is the line that
says so.** Every other product in this record can eventually be scored: a
prediction settles, a recommendation gets a closing price, a claim resolves.
A combo cannot, and not for want of sample size — for want of the one input
scoring needs.

The venue builds a combo to the account holder's order and quotes it back to
that account on request. The public interface carries only a handful of
prepackaged series. So **the app never sees the price the operator was
quoted**, and asking for one would require an account, which LAW 5 forbids and
marks not amendable. With no price paid there is no closing line, no CLV, no
win rate that means anything, and no verdict — now or ever, under any amount
of data.

What was removed on 2026-09-09, rather than left to look like a record waiting
to fill: `config.COMBO_MARKETS`, `combo_market()`, `is_combo_market()`,
`COMBO_KILL_AFTER`, `calibration.MIN_PACKAGES_FOR_CLV` and
`calibration.combo_kill_verdict`. The kill counted SETTLED packages and
nothing could ever settle, so it could not have fired — a criterion that
cannot fire reads as a safety net while being a sign saying one is there.

**What the app does instead**, and it is the honest half: it proposes combos
from legs that each clear the bar alone, prints what the combo is worth and
the highest price worth paying, and leaves the comparison to the person who
can see the quote. The card carries the sentence too, because a reader taught
that every number here arrives with its N will look for one.

**Nothing in the six criteria above moves on this.** A product that cannot be
scored cannot contribute evidence for or against readiness, and counting it
either way would be the mistake this document exists to prevent.

## 2026-09-23 — THE READ: five fail, and the deciding one is broken

Measured read-only for `docs/closeouts/2026-09-23-the-read.md`, where every
number below has its query and its N. Sixteen days after the first
recommendation, **nine and a half of them with the machine switched off**.

| # | now | verdict |
|---|---|---|
| 1 | first run today FAIL: two checks that read the live record assumed its shape of 10 September (fixed in c3c9dc8). After the fix: 4 of 4 steps, 261/261 plantings caught | PASS |
| 2 | MLB spread 41 recommendations (32 distinct bets), MLB total 14 (11). Every other covered market 0 | FAIL |
| 3 | **all 49 recorded closes are 0.00¢ because the close is read from the claim the price came from.** Against the venue's own last near-start price: MLB spread +0.30¢ at n=22, MLB total −0.68¢ at n=11 | FAIL, and the instrument is broken |
| 4 | MLB spread 132 and MLB total 134 settled for the statistical forecaster. 13 of the 14 total recommendations come from the reasoning forecaster, which has 66 | FAIL as defined |
| 5 | two BROKEN findings open (FOLLOWUPS, 2026-09-23): the closing line, and NFL and NCAAF spread and moneyline not forecast since 5 September (fs5 never trained here) | FAIL |
| 6 | MLB 79 games, NFL 33, NCAAF 10, NBA 3, UFC 0 | FAIL |

**Criterion 3 cannot pass as built, at any sample size.** A close that is the
recommendation's own price reads 0.00¢ forever, and "mean CLV positive" never
comes true. At the current rate the recorded count reaches about 42 of 50 by
the season's last game. Had it reached 50, it would have been a gate passed
by a broken instrument, and should not be read as one.

**Where a price sits beside a hundred settled rows, the market scores
better than the model:** MLB moneyline 0.2524 against 0.2403 (n=140), NCAAF
spread 0.1917 against 0.1731 (n=126). The learning panel's "174 past the
100" for MLB moneyline at the venue's line pools two forecasters; per
forecaster on graded rows it is 54.

**The standing answer is unchanged: a forecast to read, not a recommendation
to follow.**

## 2026-09-26 — the edge read: no edge, and the market ahead where it can be seen

**A DATED FINDING, recorded by operator ruling of 2026-09-26**
(`docs/briefs/2026-09-26-edge-read.md`): **the model shows no edge. In MLB
moneyline the market is better beyond noise, for both forecasters. Nowhere
does the model beat the market.**

Measured read-only on 2026-09-26 at about 07:00Z through
`db.read_the_live_record`. For every sport, market and forecaster separately
(LAW 6; never pooled): the graded rows `calibration.resolved` returns -- one
standing row per question, voided forecasts left out -- that carry a market
price for the model's own side (the first snapshot of the forecast; moneyline
prices with the margin removed by `lines.devig_pair`). On those rows, the
Brier score of the model's probability for its side and of the market's
implied probability for the same side, and their paired difference with a
bootstrap 95% interval (4,000 resamples of the rows). Lower Brier is better;
a positive difference is the market ahead.

| sport · market · forecaster | rows with a price | model | market | model − market (95% interval) |
|---|---|---|---|---|
| MLB moneyline · statistical | 170 | 0.2527 | 0.2409 | +0.0118 (+0.0006, +0.0227) -- **market ahead, beyond noise** |
| MLB moneyline · reasoning | 90 | 0.2585 | 0.2368 | +0.0217 (+0.0038, +0.0392) -- **market ahead, beyond noise** |
| NCAAF spread · statistical | 131 | 0.1919 | 0.1731 | +0.0188 (−0.0093, +0.0470) -- market ahead, within noise |
| NCAAF moneyline · statistical | 62 | 0.0991 | 0.0850 | +0.0141 (−0.0111, +0.0359) -- market ahead, within noise |
| NCAAF total · statistical | 89 | 0.1310 | 0.1312 | −0.0003 (−0.0192, +0.0179) -- even |
| NFL spread · statistical | 30 | 0.2411 | 0.2393 | +0.0018 (−0.0363, +0.0357) -- too few to say |

Categories with fewer than 30 priced rows are not listed as findings: NCAAF
total for the reasoning pass (12 rows; market ahead), NCAAF spread and
moneyline for the reasoning pass (5 and 4), NFL spread for the reasoning pass
(1) and MLB batter hits (2). **No category has the model ahead.**

**Where there is no price there is no measurement, not a hidden edge.** MLB run
line (175 graded) and MLB total (182 graded, 110 for the reasoning pass), UFC
(37 per market), the NFL total and props, and every MLB prop but batter hits
have graded forecasts and no market price beside them in this comparison.

**The closing line** (`calibration.clv_report`, which needs 50 per market):
MLB spread 9 measured closes, mean −0.17¢, the close beaten 3 times in 9;
NCAAF spread 4 closes, +0.62¢. Nothing else is measured. The instrument was
repaired on 2026-09-24, and by the operator's ruling of 2026-09-23 the first
clean read is 21 days after that.

**MLB's regular season ends on 27 September**, so the strongest sample above
barely grows this year.

**What follows from it, queued by the same ruling for after the repair's
close-out and not before:** (1) the Record page states "market ahead" per
sport and market with its interval; (2) the market blend (model plan M3)
moves to the front of the model plan.

## 2026-09-27 — two BROKEN findings recorded, and the closing line counts again from its repair

**RULED 2026-09-23 (operator; ruling 8 of `docs/briefs/2026-09-23-repair.md`,
built as GRIDIRON_REPAIR item 8):** "READINESS: two BROKEN findings recorded;
the observation window restarts on the date item 1 ships; the first clean CLV
read is 21 days after that, not before."

Nothing above is edited. **This is the first dated operator ruling recorded
against a criterion** (the rule at the top of this file said there were none
yet). It adds a date before which criterion 3 is not read, and it moves no
threshold: fifty closes in one coverage entry and a positive mean, as declared
on 2026-09-07, and fifty for the kill criterion.

### The window

| | date (UTC) | from |
|---|---|---|
| **the observation window restarts** | **2026-09-24** | item 1, the closing line (commit `23cf89b`), reached the released main checkout at 2026-09-24T06:49:12Z -- that checkout's reflog, the fast-forward to `4941fa1` -- and was served from about 06:57Z. "Ships" is read as reaching the released checkout; the date is the 24th at either instant |
| **the first clean read of the closing line** | **2026-10-15** | 21 days after it, "not before" |
| the first window's start, kept | 2026-09-07 | `calibration.CLV_DECLARED`. Nothing counted from it was a measurement (BROKEN 1 below) |

**What the app does from item 8's release** (`config.CLOSING_LINE_WINDOW_START`,
`config.CLOSING_LINE_FIRST_CLEAN_READ`, one door,
`calibration.closing_line_window`): a close counts toward the closing line's
N only if its recommendation was written on or after 24 September, and a
measured close on an older one is named beside the count. Until 15 October no
market gives a mean, a share that beat the close or a finding, the kill
criterion stops nothing, and the Record page says in words when the first
clean read is, with every count and its N. Planted twice
(`plant_a_closing_line_verdict_before_its_first_clean_read`,
`plant_a_close_from_before_the_window_counted`), each seen to escape on the
code before it and caught on it.

### 3. Closing line — **FAIL**; the observation window restarts (RULED)

Measured read-only through `db.read_the_live_record` on 2026-09-27 at about
00:15Z, the window's fourth day:

| measure | value | threshold |
|---|---|---|
| closes counted since 2026-09-24 | MLB spread 12, NCAAF spread 8, MLB total 1, NFL spread 0 (1 closed unmeasured), NBA 0, UFC 0 | ≥ 50 in one coverage entry |
| mean closing line | not read before 2026-10-15 | positive |
| first clean read | 2026-10-15 | not before |
| written before 2026-09-24, not counted | 55 (MLB spread 41, MLB total 14): every one closed by the old closer on its own price, restated beside the count on 2026-09-24 (31 with a later read of their own contract, 24 with none) | -- |
| measured closes on recommendations written before 2026-09-24 | 0 | -- |

**Because no close was ever measured on a recommendation written before the
24th, counting by when a recommendation was written, rather than by when its
close was taken, changes no figure today.** It is the reading taken (the
repair's own close-out: the restart "puts every pre-repair recommendation
outside it"), and it is the stricter one: every close since the repair is
measured after the start as well.

**What the window holds, said now so it is not found at the first read.**
The ruling dates the window from item 1, and the rules items 3, 4 and 5
changed reached the released checkout on 26 September (06:34Z, 08:23Z and
10:48Z, its reflog). Of the 48 standing recommendations written since the
24th, 42 were written before those releases, under the rules they replaced:
the bar dividing a no-side edge by the yes price, more than one allowed per
game and market, and no way for a correction to reach a pick (none has been
activated on the record, so none would have reached one yet). Five of
the window's MLB spread game-markets hold two standing recommendations each
(60/79, 61/80, 84/93, 86/94, 87/95; counted as written until
`docs/REPAIR_STATE.md` question 12 is answered). Eleven were written on the
24th before item 1 reached the checkout: MLB spread 56-61, each closed
afterwards by the repaired closer as unmeasured and so outside the count;
NFL 62, 63, 64 and 66, withdrawn by ruling 1; and 65, an NFL total that
stands, still open, whose close will count if it is measured.

**The edge read's closing-line figures (2026-09-26, above)** -- a mean at 9
closes and at 4 -- were read from the report before this was built. They are
diagnostics far below the gate, recorded as they were read, and not a read of
criterion 3; from item 8's release the report gives no mean before 15
October.

**What would change 3 now:** fifty recommendations written on or after
2026-09-24 reach a measured close in one coverage entry, **and** the date is
2026-10-15 or later. Neither alone. Baseball's regular season ends on 27
September, so the fifty must come mostly from football, and only while the
machine is on. If no market has fifty on the 15th, the line reads "N of 50 ...
nothing is claimed from a sample this size": a FAIL, not a pass waiting to
happen.

### 5. Open BROKEN findings — the two THE READ recorded, dated

Both were found on 2026-09-23, both are recorded in `FOLLOWUPS.md` under "THE
READ, 2026-09-23", and both have since been repaired. **A finding is not
erased because it was fixed**; these are the record of each.

**BROKEN 1 -- THE CLOSING LINE COMPARED A PRICE WITH ITSELF.**

| | |
|---|---|
| what broke | `recommend.record_closing_prices` took the last claim written before kickoff, and for a recommended forecast that was the claim it had been priced from; the near-start pass never looked at a recommended contract again. Every close was the price paid, read back |
| from | the first close, 2026-09-08T20:35:08Z (the recommendations it closed were written from 2026-09-07T20:52:31Z) |
| to | the last close the old closer wrote, 2026-09-24T02:05:01Z; the repair reached the released checkout at 06:49:12Z the same day |
| repaired by | `23cf89b` (the close is the last near-start read of the recommendation's own contract before kickoff, or unmeasured, never its own price; `recommendation_closes` and its triggers refuse the old shapes), released with `d782380` and `4941fa1`; `tools/restate_closes.py` restated the old closes on the record at 06:49:48Z |
| what it cost the record | **55 of 55 closes at exactly the price paid, 0.00c** (THE READ counted 49; recommendations 50-55 closed that night). They stand as recorded, under LAW 3. Worked out again afterwards and shown beside the closing line, never in it: 31 had a later read of their own contract -- MLB spread 23 at +0.30c on average, MLB total 8 at -0.94c -- and 24 had none. **Criterion 3 measured nothing from 2026-09-07 to 2026-09-24, sixteen days,** and its window starts again (above) |
| since the repair | 33 closes by the repaired closer to 2026-09-26T23:35Z: 21 on a later read of the recommendation's own contract, which the schema checks, and 12 unmeasured, none of them at zero |
| status | **REPAIRED 2026-09-24** |

**BROKEN 2 -- NFL AND NCAAF SPREAD AND MONEYLINE WERE NOT FORECAST FROM 5
SEPTEMBER.**

| | |
|---|---|
| what broke | `config.FACTOR_SET_VERSIONS` declared factor set fs5 for the four markets from 2026-09-06; fs5 had never been trained on the live record, so `baseline.load_fit` found no model, and `run.py:99` dropped a market with no model in silence. Every predict run since reported success on props and totals alone |
| from | the last forecast: NFL spread and moneyline 2026-09-04T18:40:24Z, NCAAF 2026-09-05T15:00:57Z |
| to | the first standing forecast after: all four markets at 2026-09-24T15:00Z (the 15:00Z passes), from the incumbents the revert restored. fs5 was trained on the record at 05:16Z that morning (fits 91-94), and 31 forecasts and recommendations 62, 63, 64 and 66 were published from it before the hold |
| repaired by | `d93c466` (ruling 1: the 31 forecasts and 4 recommendations withdrawn, never counted; released 09:58Z on the 24th); `ff7e5ab` (the activation gate: a fit is inactive until activated with its holdout; 11:28Z); `4c3bda4` (the fs5 revert: fits 88, 71, 44 and 35 back as incumbents, the hold lifted; 12:59Z); `d7b4dfa` (item 2's remainder: a run fails by name for a market it cannot forecast, and the day strip says so; 2026-09-26T04:48Z) |
| what it cost the record | **16 NFL games and 165 NCAAF games kicked off with no forecast in either market** (measured: games from the last forecast to 2026-09-24T15:00Z with no standing statistical forecast in the market). 15 and 160 of them kicked off during the nine days the machine was switched off (11-21 September), so this finding is not the only reason they were missed, but no forecast could have been written for any of them. And 31 forecasts and 4 recommendations published from fits that had not beaten their incumbents, withdrawn |
| status | **REPAIRED 2026-09-24** (forecast again) **and 2026-09-26** (never skipped in silence again) |

**Criterion 5's verdict is not re-read here.** Neither finding THE READ
recorded is open, and whether any other is is what a run measures. This
section records two findings and a ruling and re-reads no criterion, so no
run row is appended: the next row is the re-read's, which the repair brief
orders once the repair is done ("Then the read again, on the repaired
record").
