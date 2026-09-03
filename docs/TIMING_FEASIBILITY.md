# Timing probe — when does the information actually land?

**Read-only. Measured 2026-09-02.** Nothing was changed to produce this.

Brief: `docs/briefs/2026-09-02-model-timing.md`, A1 "PROBE FIRST".

---

## The short answer

**The measurement the brief asks for cannot be made from the data we hold, for
three sports out of four.** For the fourth — MLB — it can be made on a sample
of **39 games**, and that sample says the brief's proposed time is **too early
by about an hour**.

| sport | can we measure when information lands? | why |
|---|---|---|
| **MLB** | **Partly** — 39 live captures out of 6,958 | 99.4% of our lineup rows are backfill, recorded *after* the game |
| **NFL** | **No** | the `injuries` table has **no timestamp column at all** |
| **CFB** | **No** | no college injury or depth-chart table exists |
| **NBA** | **No** | `nba_injuries` holds ~75 rows and only a `fetched_utc` |

This is reported before any time is chosen, because the brief asks for times
"chosen from that measurement, dated". For three sports there is no
measurement to choose from, and inventing one would put a real-looking number
where there is no information — the failure the missing-data rule exists to
prevent.

---

## 1. The confound, stated before the numbers

`recorded_utc` is **when we stored a row, not when the league published it.**
Our storage time is bounded below by when our fetch task ran. So every figure
here is an **upper bound** on the true publication time, and where our own
cadence is the binding constraint the measurement describes *us*, not the
league.

That distinction turns out to be the finding, not a caveat on it.

## 2. MLB lineups — 99.4% of what we hold is backfill

Hours between our recording a game's lineup and its first pitch, over all
6,958 games we hold a lineup for:

```
recorded AFTER first pitch:   6,919 of 6,958  (99.4%)
median:                       10,592 hours AFTER the game  (441 days)
```

The reason is visible in one line — the capture batches:

| batch (UTC hour) | games |
|---|---|
| **2026-08-30T04** | **6,902** |
| 2026-08-31T00 | 14 |
| 2026-09-01T21 | 12 |
| 2026-08-31T21 | 10 |
| 2026-09-02T21 | 9 |

**One backfill on 2026-08-30 accounts for 99.2% of the table.** Those rows are
historical fact, loaded long after the games; they carry no information about
when a lineup posts, and averaging them produces the nonsense figure above.

### The 39 that are real

Thirty-nine games — all on **2026-09-01 and 2026-09-02** — have a lineup we
recorded *before* first pitch. This is the entire usable sample:

```
hours before first pitch:  min 0.07   p25 1.66   median 1.75   p75 2.67   max 4.63
```

| a final pass at | would have found a lineup on |
|---|---|
| T-0h30m | 38 of 39 — **97%** |
| T-1h00m | 36 of 39 — **92%** |
| T-1h30m | 33 of 39 — **85%** |
| **T-2h30m** *(the brief's proposal)* | **18 of 39 — 46%** |
| T-3h00m | 9 of 39 — 23% |

**The brief's T-2h30m would miss the lineup on more than half the card.**
T-1h30m is the latest time that clears 80% on this sample.

**n=39 across two days is a thin sample and is not seasonal.** September
lineups are not April lineups, and two days is not a distribution. The number
is offered as the only evidence that exists, not as a settled fact.

## 3. MLB probable starters — the same shape

9,442 games, of which **1.2%** have a probable recorded before first pitch. The
same backfill dominates. Not measurable.

## 4. NFL, CFB, NBA — not measurable at all

- **NFL.** `injuries` columns: `season, week, team, player_id, player_name,
  position, report_status, practice_status`. **There is no timestamp.** The
  table cannot say when a report arrived, only which week it belongs to.
  55,554 rows, and not one of them is dated.
- **CFB.** No college injury or depth-chart table exists.
- **NBA.** `nba_injuries` holds **about 75 rows** with a `fetched_utc` (the
  count moved by one between two reads minutes apart, which says the table is
  being written live and is simply very small). Too few to
  describe a distribution, and the same fetch-time confound applies.

The brief's NBA time — "15:00 local after the 5:30 ET injury report window" —
refers to a real, published NBA rule. **This probe cannot confirm we receive
that report on that schedule**, because we hold no dated record of receiving
it.

## 5. The instrument that already exists, and what it says

`_run_predict` already records `absent_starters` on every run, with a comment
saying in as many words that it is there so this question can be revisited
with data. It has been collecting:

| run | slate size | games with no named starter |
|---|---|---|
| 2026-09-02T18:00 | 27 | 3 (11%) |
| 2026-09-02T06:02 | 23 | 3 (13%) |
| 2026-09-01T18:00 | 21 | 2 (10%) |
| 2026-08-31T18:00 | 22 | 4 (18%) |
| 2026-08-30T18:00 | 22 | 5 (23%) |
| 2026-08-29T21:55 | 17 | 6 (35%) |

**Between 10% and 35% of each MLB slate is forecast without a named starter.**
That is the brief's premise, confirmed by an instrument that was already
running — and it is a stronger piece of evidence than the 39-game lineup
sample, because it spans more days and measures the thing that actually
affects a forecast.

## 6. A slate is not a moment

A single fixed-time daily pass cannot sit at T-2h30m before *every* game,
because a slate is spread across hours:

| sport | median spread, first game to last | p90 |
|---|---|---|
| NBA | 3.00h | 7.00h |
| CFB | 5.00h | 23.50h |
| MLB | 7.47h | 9.33h |
| NFL | **96.00h** (Thursday to Monday) | 97.75h |

On a median MLB night, a pass aimed at T-2h30m before the **first** pitch is
**T-5h30m** before the median game and **T-10h** before the p90 game. The
brief anticipates this for NFL and CFB by scheduling separate weeknight
passes; **for MLB it does not**, and a single daily time inherits the whole
7.47-hour spread.

NFL and CFB day-of-week shape confirms the brief's structure is right for
them:

| NFL (UTC weekday) | games | | CFB (UTC weekday) | games |
|---|---|---|---|---|
| Sun | 2,335 | | Sat | 2,037 |
| Mon | 224 | | Sun | 321 |
| Tue | 189 | | Fri | 137 |
| Fri | 181 | | Thu | 80 |

(UTC weekdays: a 01:00 UTC Monday kickoff is Sunday evening in the US, which
is why Monday and Tuesday both carry counts.)

## 7. The brief's three factual claims, checked

MENTOR §4 requires verifying a brief's factual claims before building on them.

### Claim 1 — "NFL week 1 was written 12 days before kickoff" — **CONFIRMED, and understated**

Lead time between a prediction and its game, live rows only:

| sport | n | min | median | max |
|---|---|---|---|---|
| MLB | 144 | 0.8h | **7.7h** | 28.0h |
| CFB | 194 | 63.0h | **108.5h** (4.5 days) | 112.8h |
| NFL | 104 | 280.8h | **371.1h** (15.5 days) | 402.3h (16.8 days) |
| **NBA** | 47 | 1,246.5h | **1,325.0h — 55 days** | 1,395.0h (58 days) |

NFL week 1 specifically: **11.7 to 16.8 days**. The brief's "12 days" is the
floor, not the typical case.

**The brief does not mention NBA, and NBA is by far the worst: a median lead of
55 days.** Those 47 predictions were written nearly two months before tip-off,
which is before rosters are settled, before any injury is known, and before
most of the factors the model reads have a current value.

### Claim 2 — "MLB predicts before lineups post" — **CONFIRMED**

Of MLB predictions on games we hold a lineup for:

| market | n | written before we recorded the lineup |
|---|---|---|
| moneyline | 88 | 88 (100%) |
| prop | 44 | 44 (100%) |
| spread | 9 | 2 (22%) |
| total | 9 | 2 (22%) |

### Claim 3 — "the lineup-slot factor came back absent on every game for that reason" — **NOT TRUE**

`mlb_batter_lineup_slot` is **present on 44 of 44** prop predictions and absent
on none.

It was never going to be absent, because **it does not read tonight's lineup**.
Its registry rationale says so: it is *"the batter's average batting-order slot
across his most recent five STARTS"* — a measure of the batter's **role**,
computed from history, deliberately independent of whether tonight's card has
posted.

The MLB factors that *are* absent are the ones depending on the announced
starter:

| factor | absent |
|---|---|
| `mlb_starter_rolling_perf` | 23 of 88 (26.1%) |
| `mlb_starter_rest_days` | 12 of 88 (13.6%) |
| `mlb_batter_opposing_hr_rate` | 4 of 32 (12.5%) |
| `mlb_prop_volatility` | 6 of 44 (13.6%) |
| `mlb_batter_lineup_slot` | **0 of 44** |

**The premise survives the correction; the example does not.** MLB does predict
too early, and it does cost the model information — but the cost lands on the
*starter* factors, not on the lineup-slot factor the brief names.

## 8. The structural finding: a later pass alone changes nothing

`_run_predict` **reads stored data. It does not fetch.**

So a final pass scheduled at T-1h30m reads whatever the last `refresh` left
behind. If the lineup fetch has not run, the lineup is not there — no matter
what MLB published or when.

**Moving the prediction without moving the fetch buys nothing.** The 39-game
sample above is itself an illustration: those lineups appeared in our database
at 17:00 and 21:00 UTC because that is when we looked, not because that is when
they posted.

Any final pass must **fetch, then predict**, inside the same run and inside the
blind window. That is a requirement the brief does not state and the build has
to honour for the rest of it to mean anything.

## 9. Times, and the evidence behind each

Recorded as **dated, declared constants**, with the honest provenance of each —
including the three that are not measured.

| sport | final pass | basis | expected catch |
|---|---|---|---|
| **MLB** | **T-1h30m before first pitch**, fetch-then-predict | **measured**, n=39, 2026-09-01/02 | 85% of that sample; unknown seasonally |
| **NFL** | Sunday 08:00, Thu/Mon 14:00 local | **not measured** — brief's proposal, consistent with the Sun/Mon/Thu game shape | unknown |
| **CFB** | Saturday 08:00, Thu/Fri 14:00 local | **not measured** — same | unknown |
| **NBA** | 15:00 local | **not measured** — rests on NBA's published 5:30 ET report rule, which we hold no dated record of receiving | unknown |

**MLB moves from the brief's T-2h30m to T-1h30m**, on the only evidence that
exists. The other three are declared, not measured, and are labelled that way
wherever they appear.

## 10. What would make this measurable

Small, and worth doing before the times are trusted:

1. **Stamp the NFL injuries table.** A `fetched_utc` column and the loader
   writing it. One column turns an unmeasurable question into a measurable one
   within a week of games.
2. **Keep the live lineup captures separate from backfill.** A `source` column
   distinguishing a live capture from a historical load; without it the 39
   real rows are permanently buried under 6,902 that mean something else.
3. **Let `absent_starters` accumulate.** It is already the best instrument
   here. After a month of two-pass runs it can answer the real question
   directly: did the later pass have a starter when the earlier one did not?

That third one is what A2 measures, and it is the reason A2 matters more than
the times chosen today.
