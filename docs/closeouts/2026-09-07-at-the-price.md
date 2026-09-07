# Close-out — GRIDIRON_AT_THE_PRICE (2026-09-07)

Against the brief saved at `docs/briefs/2026-09-07-at-the-price.md`. One row
per phase, then what the shapes turned up on their first contact with a live
venue.

| # | phase | verdict | evidence |
|---|---|---|---|
| FIRST ACT | Save the brief before executing it | **DONE** | `docs/briefs/2026-09-07-at-the-price.md`, with how it was read beneath the operator's text. |
| — | One unit is fifty dollars | **DONE** | Recorded through the settings page, not in code: `unit_dollars`, empty to `50`, dated, with the previous value kept. A flat unit now reads "$50 · one flat unit". |
| Q1 | Classify every question, refuse the unclassifiable | **DONE** | `priced/shape.py`: `claim_shape` returns one of four shapes or a named refusal, and the writer dispatches on it. Six refusal reasons are counted separately. |
| Q2 | The direct path | **DONE** | Line-less and rung-matched claims are the blind probability against the venue's price, with the side mapped explicitly. `shape` is stored on every claim row; the table's CHECK admits the four and nothing else. |
| Q3 | The count path | **DONE, and it has no live input yet** | A counting-stat prop at a differing rung reads `expected_count` through `counts.p_over` at the venue's strike, and is refused when the rate was not written blind. **The venue's declared series carry no prop market**, so this path runs only in its tests today. |
| Q4 | Backfill nothing | **DONE, read differently from the brief's words** | No distribution is invented and no claim precedes its inputs. The brief expected standing baseball to get nothing; it got 43 claims, and the ruling below says why that is not a backfill. |
| Q4 | READINESS records the date | **DONE** | Baseball reached the priced pipeline on 2026-09-07. |
| — | The gate | **DONE** | Four steps of four PASS, 233 of 233 plantings caught, five of them new. |

## Today's questions, by shape

The brief asks for this count. It is baseball's whole slate, and it is the
first claim of any kind in this project's record.

| shape | claims |
|---|---|
| line-less (a winner contract) | 26 |
| rung-matched (the venue quotes our number) | 17 |
| rung-differs, count | 0 |
| rung-differs, margin | 0 |

| refused, and why | questions |
|---|---|
| no frozen margin distribution, at a differing rung | 21 |
| no venue quote for that market (every prop) | 12 |
| the quote was taken after first pitch | 17 |

**43 claims from 31 of today's 62 baseball questions.** The margin shape wrote
nothing, which is correct: baseball has no measured margin spread by design,
because its margins are counts.

## The finding that outranks the brief

**The brief's diagnosis was half right, and the missing half was bigger.** It
says baseball produces no claim because a claim needs a frozen margin
distribution. True, and not the binding constraint: **baseball had no venue
quotes at all** — zero of the 1,172 in the record.

Asked directly, the venue answers 42 open baseball events, every one shaped

```
KXMLBGAME-26SEP071310NYMMIA
```

against the `KXMLBGAME-26SEP07NYMMIA` this project was building. **The first
pitch is in the ticker**, because baseball plays doubleheaders: one pair of
teams can meet twice on a date, so date and teams do not identify a game.
Football never does, which is why the same builder matched 16 of 16 football
events and 0 of 22 baseball ones.

Measured before anything was changed, as the module's own header demands: **20
of 22** games inside the venue's open window match exactly on date, start time,
away and home, with **no code aliases needed**. The two misses are a 2024 row
still marked scheduled and one game the venue had not opened. Baseball now has
290 quotes and one covered market — totals, 1.0¢ wide at the middle over 4,760
contracts.

## What the first live run got wrong, and how

Both were live in the record for part of an afternoon. Both are planted now.

**A moneyline side can be `lose`.** Sixteen of today's twenty-two baseball
moneylines say `win` and six say `lose`. The first mapping read which team the
question named and not what it said about them, so "the home side loses, 62%"
became a claim that it wins with probability 0.62. **Five claims were written
that way; one was readable before its kickoff.** This is the defect this
project has had more often than any other, arriving through the one door built
to stop it.

**A claim was written against a live price.** The ladder fetch does not ask
whether a game has started, so **17 of the first 29 claims** compared a
pre-game probability with an in-play price — one of them a home side the model
made 59.6% against a venue price of 3.5%, which is not a disagreement, it is
the fourth inning. LAW 5 refuses to size in-game; nothing refused to *claim*
in-game.

**Nothing was deleted, and nothing had to be.** A claim is append-only, so the
wrong rows stand and are superseded: `standing_claims` reads the last claim
written before kickoff, so the corrected rows written from a fresh ladder
replace them for every reader, exactly as a re-asked question supersedes its
earlier answer. The in-play rows were already outside that clause. The record
now shows 8 standing moneyline claims, 4 spread and 2 total, all correct.

## Two more found on the way

**A sign error in a function nobody had ever called.** `rung_for` says the
stored line is written from the home side's view. It is not: the quote parser
stores the home strike on a home row and the *away* strike on an away row. The
price was already complemented for an away row and the line was not, so a
claim from one would have integrated the distribution at +3.5 while pricing
−3.5. Nothing in the record is wrong, because nothing had ever been written
through that path. It would have been wrong on the first row.

**A migration that dropped a table and could not put it back.** Splitting
`schema.sql` on `;` cuts a trigger into fragments, so the first widening
dropped the old claim table, renamed the new one, and then failed to restore
its guards — leaving a claim table with no append-only trigger on it. The
splitter reads a trigger to its `END;` now, the restoration is unconditional
and idempotent, and both widenings drop the triggers that name the table they
rename. The second widening hit the same wall from the other side and was
repaired by hand with all 1,512 quote rows intact.

## Rulings taken in the operator's absence

1. **Q4 is read as "invent nothing", not "write nothing".** The brief expects
   standing baseball to carry no shape and get no claim. Shape is *computed*
   from the question and the quote, so a standing prediction does carry a
   determinable one — and for the two direct shapes there is no distribution
   involved at all, so there is nothing to backfit. What the ordering laws
   forbid is a claim that precedes its inputs, and the triggers already refuse
   that. Writing them today rather than tomorrow costs nothing and delays
   nothing. **If the operator meant the literal reading, the fix is one
   constant and the claims already written stand as a record of the day the
   pipeline opened.**
2. **The venue quote table admits a prop.** The claim table learned `prop` and
   `count`; without the same widening on the quote table the count shape is
   unreachable even in a test. The venue's declared series carry no prop
   today, which is why this went unnoticed and is exactly why it was widened
   now.
3. **A claim is refused on a game under way, by status and by timestamp.** Two
   checks rather than one, because a status is only as fresh as the last
   refresh and a kickoff time is a fact.
4. **The unit went in the settings page, not into `config.py`.** The field
   added yesterday exists for this, and it carries a date and a previous
   value; a constant in code would carry neither.

## What to check next

- **Coverage.** Baseball totals are covered; the moneyline is not measured
  enough (26 quoted strikes across 10 games against a floor of 50 across 3)
  and the spread sits in the busier half. Recommendations follow coverage, so
  the daily sport still produces none until that moves.
- **The football run on 9 September**, which is the first slate that can
  produce a margin-shape claim.
- **Prop quotes.** The venue may carry strikeout markets under series this
  project has not declared. Q3's path is built and untested against a live
  ladder; declaring a prop series is a separate measured piece of work.
