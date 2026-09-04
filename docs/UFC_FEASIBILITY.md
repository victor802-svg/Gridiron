# UFC feasibility probe — U1

**Read-only. Measured 2026-09-03.** Nothing was built from this document.

Brief: `docs/briefs/2026-09-03-ufc.md`, phase U1.

---

## The short answer

**Buildable, from ESPN alone, and better supplied than any sport already in
this record.** The core API carries events, bouts, fighters, results with
**method and round**, and — the finding that matters most — **opening and
closing moneylines plus a posted round total with its price pair**.

| what U1 asked | answer |
|---|---|
| events, fighters, results | **yes**, `sports.core.api.espn.com` |
| method of victory | **yes**, `status.result.name` |
| round the bout ended in | **yes**, `status.period` |
| bout length (3 or 5) | **yes**, `format.regulation.periods` |
| moneylines | **yes**, per athlete, with `favorite`/`underdog` flags |
| round totals | **yes**, `overUnder` with `overOdds` / `underOdds` |
| historical depth | **34 seasons, 1993–2026** |
| a second source for fighter stats | **not needed** — §5 |

---

## 1. The endpoints, and one that must not be used

**Use `sports.core.api.espn.com`.** Events for a year come from:

```
/v2/sports/mma/leagues/ufc/events?dates=2025&limit=500     -> 52 cards
/v2/sports/mma/leagues/ufc/seasons?limit=50                -> 34 seasons, 1993..2026
```

**Do not use `site.api.espn.com`.** It answered the plain scoreboard once and
then returned **403 to every subsequent request, including the one that had
just worked**. That is a rate limit, reached in under twenty requests. The core
API served ~150 requests across this probe without complaint, but the lesson is
recorded as a build constraint rather than a footnote: **the loader must go
through `http_cache` with real pauses, and must never poll the site API.**

Seasons are reachable but `seasons/<year>/types/<n>` carries **no events link**
— the year-filtered `events?dates=` form is the only route to history that
works. Written down because I lost two requests finding it.

## 2. What a bout carries, measured on 94 bouts over 8 cards

Every one of the 94 resolved bouts carried a method and an ending round.

```
format.regulation.periods     3 rounds: 84     5 rounds: 10
status.period (ending round)  1: 27  2: 10  3: 52  4: 1  5: 4
competitors[].winner          boolean, per athlete
```

**The method vocabulary, complete for the sample:**

| `status.result.name` | n |
|---|---|
| `decision---unanimous` | 40 |
| `kotko` | 31 |
| `submission` | 12 |
| `decision---split` | 9 |
| `draw` | **1** |
| `tko---doctors-stoppage` | **1** |

**Both of the awkward cases the brief asked about appear in a 94-bout sample.**
A draw and a doctor's stoppage are not hypotheticals to be handled defensively;
they happen about once per card and a half, and their rules are written in §6
before anything is built.

**A caution about ordering.** `competitions[0]` is **not** the main event —
sampling it across 20 cards returned 3-round bouts 19 times, which is the
prelim shape. The card is ordered from the bottom. `cardSegment` and
`matchNumber` exist on the bout and are the fields to order by; nothing in this
build may assume position 0 means anything.

## 3. The market data — better than any sport we hold

One bout's odds, measured:

```json
"provider": {"name": "ESPN BET"},
"details": "D. Freeman -235",
"overUnder": 1.5, "overOdds": 125.0, "underOdds": -160.0,
"awayAthleteOdds": {
  "favorite": true, "underdog": false, "moneyLine": -235,
  "open":  {"moneyLine": {"american": "-170"}},
  "close": {"moneyLine": {"american": "-235"}}
}
```

**Two providers per bout. 19 of 20 sampled bouts carried an odds reference.**

Three things follow, and the third is the important one:

1. **The moneyline comparison needs no SD.** It is a binary question with an
   explicit favourite flag, so implied probability comes straight off the price
   — no distributional assumption, unlike every spread market in this record.
2. **The round total arrives with its own posted line** (`overUnder`, here 1.5)
   and both prices. The declared ladder can be built from the measured
   distribution of these lines rather than invented.
3. **ESPN CARRIES AN OPENING LINE FOR UFC.** `open` and `close` are both
   present.

That third point deserves more than a bullet. `docs/DIAGNOSIS.md` records H1a —
"the model disagrees most when it is MISSING information the market has" — as
**NOT TESTABLE**, because no free source publishes opening lines for the NFL
seasons in this record and every market number Gridiron holds is a closing
number. **In UFC that hypothesis becomes testable**, on a sport with 52 cards a
year and prices that move. It is not what this brief asked for and nothing here
acts on it; it is the largest thing the probe found.

## 4. Cadence

```
52 cards in 2025          ~4.3 a month
bouts per card            min 5, median 12, max 14
sampled span              2025-09-03 .. 2025-12-14 (20 cards in 14 weeks)
```

Roughly **600 bouts a year**. Against the roster's other candidates that is
thin per slate and steady across the year — a category reaches LAW 4's hundred
settled rows in about ten weeks of moneylines.

## 5. Fighter stats: no second source is needed

The brief asked for a second free source for reach, stance and finish rates,
and to check whether it is bot-blocked the way PrizePicks was. **The question
is moot: ESPN's own athlete record carries them.**

```
id=4848646  Denzel Freeman   weight 257.0  height 73.0  reach 77.5
            stance Southpaw  dateOfBirth 1991-11-10  age 34
id=5324401  Marek Bujlo      weight 265.0  height 76.0  reach 77.0
            stance Orthodox  dateOfBirth 1993-10-10  age 32
```

Reach, stance, height, weight and date of birth are all present, which covers
the reach gap and age gap factors U3 asks for. **Finish rates are computed from
results history, not fetched** — the method vocabulary in §2 is exactly what a
finish rate is made of.

**So the build uses ESPN only, and not because an alternative was blocked.**
No second source is contacted, and none needs to be.

### Identity

188 distinct fighter ids across 94 bouts, and **every competitor arrives with a
numeric ESPN athlete id** (`/athletes/4848646`). The identity problem the brief
worried about — "fighters share names more than teams do" — **does not arise on
this path**, because nothing is matched by name: the bout references the athlete
by id directly.

That is a materially better position than the MLB prop crosswalk, which had to
be measured and can refuse. **The rule stands anyway**: if a future source ever
requires a name match, two fighters sharing a normalised name are ambiguous and
refused, exactly as the crosswalk does.

## 6. Void rules, written before anything is built

The brief asks for these first, and §2 shows two of them are common enough to
have appeared in a small sample.

| case | rule |
|---|---|
| **Cancelled bout** | The question is VOID. A bout removed from the card was never fought; it is not a loss for either side. |
| **Weight-miss replacement** | If either competitor id changes after the prediction row exists, the prediction is VOID. It was a forecast about two named fighters, and one of them is not there. |
| **No contest** | VOID for all three markets. Nothing was decided, including how long it lasted. |
| **Draw** | **Moneyline VOID** — neither fighter won. **Rounds and distance RESOLVE NORMALLY**: a draw is a decision, the bout went its full length, and both of those are facts about time rather than about who won. |
| **Doctor's stoppage between rounds** | The bout ENDED, so it resolves. The rounds market uses `status.period` as the round it ended in; the distance market resolves NO. The stoppage is a TKO in the vocabulary (`tko---doctors-stoppage`) and needs no special case beyond this sentence saying so. |
| **A bout declared before the final card is set** | Predict it only once the bout carries both athlete ids and a date. A card is built up over weeks; a question asked against a placeholder is not a question. |

**The rounds market's one genuine ambiguity, decided here:** a bout that ends
*between* rounds — corner stoppage, doctor's stoppage — completed the round it
last finished. `status.period` reports the round in progress when it ended, and
`status.clock` the time. **A total of "over 1.5 rounds" needs 1.5 rounds
elapsed**, so a stoppage at the end of round 2 is OVER 1.5 and UNDER 2.5. This
is written down because guessing it later, from the sign of a price, is exactly
what the no-guessed-sides rule forbids.

## 7. What would stop this build

Nothing found. For completeness, the three things that would:

1. **The core API rate-limiting the way the site API did.** It did not across
   ~150 requests, but the loader must cache and pause regardless.
2. **Odds disappearing for older seasons.** Measured on 2025 only; a
   walk-forward fit reaching back further should confirm coverage per season
   before trusting a market comparison that far back.
3. **`cardSegment` / `matchNumber` proving unreliable** for ordering a card,
   which would make "main event" unidentifiable. Not tested here beyond noting
   that position is not it.

## 8. What this probe did not measure

- Odds coverage **before 2025**. Everything in §3 is a 2025 measurement.
- Whether a bout's announcement date is available anywhere, which U3's
  short-notice factor needs. **Not found on the bout object**; if it is not
  carried, that factor is ABSENT rather than estimated.
- Live status shape during a bout in progress, which U5's live tile needs.

---

## 9. Event tiers (E1 probe, 2026-09-03)

Appended for ITEM 4. Read-only; nothing here was written to the record.

### 9.1 THE PAYLOAD CARRIES NO TIER FIELD. Measured, not assumed.

R2 asked how the tier is identified in the payload. It is not. One event of
each kind was fetched in full and compared field by field:

| field | UFC 324 | UFC Fight Night | Contender Series |
|---|---|---|---|
| `seasonType` | `seasons/2026/types/2` | `seasons/2026/types/2` | `seasons/2026/types/2` |
| `league` | `.../leagues/ufc` | `.../leagues/ufc` | `.../leagues/ufc` |
| `season` | `seasons/2026` | `seasons/2026` | `seasons/2026` |
| `shortName` | `UFC 324` | `UFC Fight Night` | `Dana White's Contender Series` |

There is no `type`, no `grouping`, no tier marker of any kind. `seasonType` is
identical across all three and means regular season, not card class. **The
name is the only carrier**, and `shortName` carries it more cleanly than
`name`.

So the ruling's caution has to be honoured a different way: the tier is derived
from the name because there is nothing else, and the derivation is then
**validated against card structure**, which is a fact about the event rather
than a string.

### 9.2 Coverage per tier, over 268 stored events

| tier | events | settled bouts |
|---|---|---|
| Fight Night | 140 | 1,619 |
| numbered | 65 | 753 |
| Contender Series | 50 | 218 |
| **unclassified** | **13** | **48** |

All three declared tiers are already in the record — the existing loader was
never restricted to numbered cards. What was missing is the STAMP, not the
data.

### 9.3 GOES THE DISTANCE, BY TIER — and the ruling was right

| tier | settled | goes the distance | three-round | five-round |
|---|---|---|---|---|
| Fight Night | 1,619 | **55.3%** | 56.3% (n=1,485) | 44.0% (n=134) |
| numbered | 753 | **58.0%** | 57.9% (n=653) | 59.0% (n=100) |
| **Contender Series** | 218 | **43.6%** | 43.6% (n=218) | — none |

**Contender Series finishes 12 to 14 points more often than either other
tier**, which is what R2 predicted and is a large enough gap to matter to every
rounds and distance question asked on one. A single UFC distance curve would
average a 43.6% population with a 58.0% one and describe neither.

Contender Series carries **no five-round bouts at all** in five seasons — the
format is five three-round bouts, so `ufc_scheduled_rounds` is constant within
the tier and the ladder has exactly one rung there.

### 9.4 Cadence

Contender Series runs **August to October, three to five cards a month, five
bouts a card** — consistently 4.6 to 5.3 bouts per card across 2022–2026. The
2026 season is in progress: weeks 1–7 are complete, weeks 8–10 are scheduled.

### 9.5 The 13 unclassified, resolved by structure

Average bouts per card, and average five-round bouts per card, are the two
numbers that separate the tiers:

```
numbered      11.8 bouts   1.61 five-round
fight_night   11.9 bouts   1.00 five-round
contender      4.6 bouts   0.00 five-round
```

Against those norms:

| event | bouts | 5-round | segments | reading |
|---|---|---|---|---|
| Noche UFC ×3 (2023, 2025, 2026) | 11, 14, 12 | 1 each | Prelims + Main Card | **Fight Night** |
| UFC 306 – Riyadh Season Noche UFC | 10 | 2 | Prelims + Main Card | **numbered** |
| UFC Freedom 250 | 7 | 2 | Main Card only | numbered-like, **not certain** |
| The Ultimate Fighter ×7 | **1 each** | 0 | Main Card | **not a card at all** |

**The Ultimate Fighter entries are one bout each.** No UFC card in five seasons
has fewer than three. These are weekly television episodes, and the bouts
inside them are tournament fights in the TUF gym — not sanctioned bouts on a
professional record. *The structure is measured; the reason is domain
knowledge, and it is labelled as such.*

**Seven of those bouts are currently in the rating pool**, contributing 14
`ufc_ratings` rows. They should not be, and E2 removes them.

`UFC Freedom 250` is the honest doubt: two five-round bouts says numbered, and
seven bouts on a single Main Card says nothing in the record. It is left
UNCLASSIFIED rather than guessed.

### 9.6 What this probe did not measure

- **Odds coverage per tier.** §3 measured odds on 2025 events without
  separating them. Whether Contender Series carries the same two providers is
  the open question for E4, and it is likely to be the weakest tier — a
  prospect card is priced by fewer books than a pay-per-view.
- Whether ESPN ever renames a tier mid-season, which would move an event
  between categories. Nothing in the record suggests it has.
