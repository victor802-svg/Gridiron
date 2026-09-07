# READINESS — is this engine's output fit to act on?

One question, answered with numbers. Six declared criteria, each with its
current value and a verdict. **The document is expected to be red for a long
time**; a run that reports six failures and the reasons is a successful run.

**A THRESHOLD IS NEVER MOVED TO PRODUCE A PASS.** Changing one requires a dated
operator ruling recorded in this file, with the old threshold still visible
beneath it. There are no such rulings yet.

## The standing answer

**The engine's output is a forecast to read, not a recommendation to follow.**
Every criterion below fails. The app already restricts itself accordingly: one
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
