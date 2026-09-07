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
