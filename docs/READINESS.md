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

## Run log

Each run appends a row. Nothing is overwritten.

| date | 1 gate | 2 recs | 3 CLV | 4 outcomes | 5 broken | 6 coverage | verdict |
|---|---|---|---|---|---|---|---|
| 2026-09-07 | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | not fit to act on |
| 2026-09-07 (2nd) | **PASS** | FAIL | FAIL | FAIL | **PASS** | FAIL | not fit to act on |

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
