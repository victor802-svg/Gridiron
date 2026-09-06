# Close-out — GRIDIRON_AT_THE_LINE (2026-09-06)

Against the brief saved at `docs/briefs/2026-09-06-at-the-line.md` and the
operator's rulings of the same day. One row per phase, one per decision.

| # | phase or decision | verdict | evidence |
|---|---|---|---|
| FIRST ACT | Save the brief and the rulings before executing them | **DONE** | `docs/briefs/2026-09-06-at-the-line.md` holds the brief, both operator messages verbatim, and how each was read (commit 6451f1a). |
| D1 | Hypothetical unit accounting, option (b) | **DONE** | LAW 5 amended in `CLAUDE.md` in the shape of the PrizePicks ruling; `gridiron/market/paper.py` carries one unit per qualifying settled comparison, fee-adjusted with the venue's formula, gated at 100, labelled "hypothetical" as the first word of every sentence; `tests/test_paper.py` covers the arithmetic, the fee, the gate and the label; the staking scan is still clean with it in the tree (commit 161bf3d). |
| D2 | NFL and CFB first; daily MLB keeps scheduler priority | **DONE** | E2 built the NFL rating first, then the college one, and nothing in the scheduler moved: the daily baseball tasks run on the cadence they already had (commits 04283f8, 0f96968). |
| D3 | Kalshi ratified as a read-only source | **DONE** | `gridiron/market/kalshi.py` reads the public trade API with no key, stores each ladder in `venue_quotes` behind a LAW 1 trigger, and the crosswalk is measured and aliased by name; the roster entry records the terms as UNVERIFIED because the venue's terms page would not load that day (commit 7efe688). |
| E1 | Route the reasoning pass to game markets only | **DONE** | `config.LLM_MARKETS_BY_SPORT` dated 2026-09-06; the prediction pass skips an unrouted market and counts it; `audit.llm_routing_faults` refuses a prop on the roster and `plant.py` proves it fires; an unrouted category's outlook now says its count is final rather than counting toward a gate it will never reach (commit 252a896). |
| E2 | Ratings core — NFL, then college | **DONE** | `nfl_rating_decayed_diff` and `cfb_rating_decayed_diff`: opponent-adjusted, recency-decayed on a declared half-life, margin-capped at four touchdowns, with the home adjustment MEASURED at declaration (NFL 1.76 over 2,639 games; college 8.84 over 1,761) rather than assumed. The two older rating factors were retired as REPLACED, not refuted; factor set fs5 declared and the model refit (commits 04283f8, 0f96968). |
| E3 | The margin distribution written blind | **DONE** | Every game question carries its own distribution — mean, measured spread, family, and the date that spread was declared — written inside the blind window and frozen with the row by the fingerprint. Absent, never guessed, where there is no rating or no measured spread. `tests/test_blind_distribution.py` (commit d780fdc). |
| E4 | At-the-line evaluation | **DONE** | `gridiron/market/at_the_line.py` reads the frozen distribution at the venue's own line; three triggers refuse a claim with no frozen distribution, one stamped at or before its prediction, and one stamped before its quote. Separate curves, separate gate, separate pace projection, and `assert_the_records_stay_apart` with a planted violation. An advice-word scan on every string this project composes, plus a shorter list on the model's quoted prose; both on the gate, both planted. The card sentence and the Record section were rendered and read (commit cc858e4). |
| E5 | Wire the new source | **DONE** | Captured after the blind window closes and again near the start, past the cache, with the venue switched off under the suite's network guard so a slate run inside a test asks nothing rather than failing quietly. NFL week 1 matched 16 of 16 event tickers with two named aliases; the open college events 47 of 50 with six; the last three are lower-division games this record does not carry (commit 7efe688). |
| Close-out | This table, the follow-ups, the gate and the renders | **DONE** | `tools/verify.py` green with every planting caught; renders of the card sentence and the Record section at 1100 and 390 pixels wide; three defects the renders caught are fixed and recorded below. |

## Rulings taken in the operator's absence

Ordinary decisions, recorded because nobody was asked.

1. **The venue's quotes live in a table of their own.** A venue quotes a
   LADDER per game — twenty-five strikes on one match — and `market_snapshots`
   holds one line per prediction per look. Putting them together would have
   made the snapshot count disagree with itself. `venue_quotes` names the
   venue on every row.
2. **One claim per prediction per look, and one standing claim per
   prediction.** The record's existing standing-row rule, applied one level
   down: a ladder read twice would otherwise put two correlated rows in one
   curve and call the sample twice the size it is.
3. **The rung read is the strike priced nearest an even chance** — the
   venue's own line — declared and dated before any claim was written.
   Picking the strike where the model looks best is choosing the comparison
   after seeing the answer.
4. **Every claim is one fixed proposition**: the home side of a spread, the
   over of a total, the home side of a winner market. The record therefore
   holds two probabilities for one question and never a side to take, which is
   what makes the advice scan a check rather than a hope.
5. **The at-the-line record does not reach the hero.** The brief put the card
   line "one tap away"; the hero is the opposite of one tap away, so the
   comparison stays in the card body and the Record section.
6. **A level game leaves a winner claim open and says so.** The rung record
   voids those rather than inventing an answer; a claim has no void table, so
   the row stays open and the settle count names it.
7. **The claim step settles through `tasks.settle_everything`, not
   `resolve.resolve_all`.** A sport adapter imports `resolve`, which puts that
   module inside a prediction closure, and the closure scan reads the syntax
   tree: a function-local market import was caught by the planting within the
   minute.
8. **The ladder reader shipped with its caller.** A public reader written in
   E5 had nothing calling it; rather than an allowlist line for a helper that
   gets a caller in the next phase, E5's test reads the rows with SQL and the
   reader arrived with the code that needed it.
9. **The fee formula is declared, not measured.** The venue's schedule page
   answered HTTP 429 twice on the day, so the formula is recorded from the
   brief, marked NOT VERIFIED in the payload, and every line that uses it says
   so where it is read.
10. **Rung selection stays on the plain rating.** Changing which questions get
    asked is an operator ruling (DISTRIBUTIONAL, section 8), so the decayed
    rating scores the questions and does not choose them.

## What the renders caught

Three things no test would have failed on, found by looking at the page.

1. **The card sentence was painted in `--ink`**, which in this palette is the
   PAGE and not the text on it: #0F1114 on a #171A1F card, invisible in the
   screenshot that was supposed to prove the feature worked. It is `--muted`
   now, like the numbers line above it.
2. **"There is no line to compare it with" sat two lines above the venue's
   price.** True of the published-line sources and false to a reader. The
   sentence now says no published line prices this market and points at the
   comparison below it.
3. **Three ledger rows read identically.** "one unit carried on each of 130
   settled comparisons" appeared three times over with nothing to say which
   market each row was about. Every ledger line names its market after the
   label now, and the fee's provenance appears only under a row that has a
   figure to explain.

A fourth, found in the payload rather than the picture: **a card carries two
probabilities for the same event** — the fitted model's own percentage and the
frozen distribution read at the venue's number. They are different
calculations and they disagree. The sentence names which one it is now ("from
the model's margin forecast"), and the gap between them is a real finding,
recorded in `docs/FOLLOWUPS.md`.

## Proved against the live venue, once

One game, three requests, because the venue publishes no rate limit for
unauthenticated reads and a slate's worth of them would have been a guess about
what it tolerates. `KXNFLSPREAD-26SEP09NESEA` and its two siblings answered
without a key, and the record now holds 46 real quote rows for that game: 25
spread strikes from -20.5 to +14.5, 19 totals from 23.5 to 65.5, and both
winner markets. Nothing was unreadable, the crosswalk matched, and the LAW 1
trigger accepted every row because the predictions were written first. The
closest strike to an even chance was the home side at -3.5, quoted 0.48 / 0.49.

No claim came of it, and that is the system working: the predictions on the
record were written before E3, so none carries a frozen distribution, and a
claim without one is refused. The first claims will be written on the next
slate run.

## What is not here

- **No at-the-line claim exists on the live record yet.** The venue's ladder
  is captured on the next slate run, so every figure in the new section reads
  "0 of 100" today. The renders were made against a synthetic database in the
  scratchpad; nothing synthetic touched the record.
- **The distributional verdicts still stand.** Nothing in this work promotes
  the distributional prop scorer, and the read-out at the market's number was
  refused in all four arms on 2026-09-04. The at-the-line record is a FORWARD
  record with its own gate; the earlier refusal is not contradicted by it, and
  the venue is expected to lead until the ratings move the mean.
