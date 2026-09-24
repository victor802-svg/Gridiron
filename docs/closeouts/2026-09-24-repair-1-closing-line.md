# Close-out — GRIDIRON_REPAIR item 1: the closing line (2026-09-24)

Against `docs/briefs/2026-09-23-repair.md`, item 1. Built in a worktree on the
`repair` branch, and merged into the main checkout only after a green gate
(ruled 2026-09-23, `docs/briefs/2026-09-23-worktree-and-cloud.md`).

| part of item 1 | verdict | evidence |
|---|---|---|
| the near-start pass reads every open recommendation on every run inside its window | **DONE** | `tasks._near_start_snapshots` selects open recommendations by kickoff and status on every firing; `tests/test_near_start_reads.py` asserts two consecutive firings both read it |
| the last read before kickoff is the close | **DONE** | `recommend.close_of`: the last near-start read of the recommendation's OWN contract, after its pricing read and before the start. Two plantings |
| retire the once-then-exclude at tasks.py:544 by name | **DONE** | the `RETIRED 2026-09-23` note quotes it; a test fails if it returns to the selection |
| recompute CLV where a true pre-kickoff quote exists | **DONE** | `tools/restate_closes.py --write` on the live record: 55 closes the old closer made (49 at the read, plus recs 50-55 closed overnight) restated on 2026-09-24: MLB spread 23 with a later read of their own contract (mean +0.30c) and 18 unmeasured; MLB total 8 (mean -0.94c) and 6 unmeasured. Shown beside the closing line, never inside it: the line now reads 0 of 50 in both markets |
| mark the 49 as unmeasured, never as zero | **DONE** | every old close is read as unmeasured until restated, and restated closes are shown beside the closing line, never inside its N. See "a reading taken" below |
| planting: two near-start reads close on the later one | **DONE** | `plant_a_close_read_from_the_first_of_two_reads` escaped on unfixed code (it closed on another strike's claim at −16.0¢) and is caught on the fix; `plant_a_close_that_cites_its_own_pricing_read` proves the table itself refuses both old shapes |

## What was built

- **`recommendation_closes`**: an append-only account of how every close was
  measured, written in the same transaction as the close. It records the
  closing quote, or NULL where there was none (**unmeasured**). So a closed
  recommendation with no account row is, by construction, one the old closer
  made. Four triggers make it write-once, never deleted, closed-only, and a
  close must be a later near-start read of the same contract before the start.
  A fifth, `recommendation_close_cites_its_own_priced_read`, requires the
  pricing read to be the one this recommendation was actually priced from,
  and the closing-line value to be the difference between the two prices.
- **A near-start venue read is a fetch or nothing.** `NEAR_START_TTL` went
  from ten minutes to zero, and the pass fetches with no offline fallback. A
  replay of the pricing read, re-stamped as a later read, would otherwise have
  closed a recommendation at 0.00¢ again. `close_of` also skips a read
  identical to the pricing read (same bid, ask, last price and volume) and
  falls back to the read before it.
- **`clv_report`** counts measured closes only. It reports unmeasured,
  restated and not-yet-restated closes beside the count, each in its own words.
- **One claim per prediction wherever claims are counted.** Re-reading the
  venue every firing writes a claim per look. `drift.venue_pairs`, the card's
  "settled at the line" count and the at-the-line outlook now count through
  `at_the_line.standing_claim_clause`, so no gate can clear on duplicates.

## The review, and what it changed

Three local reviewers read the first draft through three lenses. The review
started before the cloud ruling arrived, so it was allowed to finish locally.
They found **two blockers** (the same one twice: a cache replay could be a
close) and nine further defects, and every one was fixed before the commit:

- a replay of the pricing read accepted as the close (the blocker)
- a test and a planting that passed for the wrong reason: neither had two
  reads after the price, so a closer taking the first later read passed both
- words giving a false cause for old closes not yet restated
- a missing kickoff closed as unmeasured before the game had a start
- the dry run was not dry: it applied the schema
- the restatement mixed sports (LAW 6)
- the trigger did not tie the pricing read to its recommendation
- claim counts would inflate about four-fold
- the recommendations read ignored game status
- two firings could race to close one recommendation
- the "ok" detail counted what was asked, not what came back

Recorded in FOLLOWUPS rather than fixed, as out of scope: `INSERT OR REPLACE`
walks past every append-only trigger; predict-time captures file cached bytes
as near-start reads; one test depends on the operator's real `.env`.

## What reached the live record before the commit

The first draft sat UN23cf89bTED in the main checkout from about 22:20Z to
22:47Z on 23 September. `Gridiron-Live` opens the database every 90 seconds,
so `db.init` ran the draft schema: the table and four triggers were created on
the live record. **No row was written.** The 22:35Z near-start firing ran the
old code, and the table held 0 rows. The committed schema keeps those four
objects byte-identical to the live copies (checked). The stronger checks went
into a new trigger, because `CREATE TRIGGER IF NOT EXISTS` never replaces one
the live record already holds.

## A reading taken in the operator's absence

**Do restated closes count toward the closing line's N?** One reading: they are
measurements the record already held, so they count. The other: they were
computed after the games, so they are shown and not counted. Taken: **shown,
not counted**. That is the conservative default, and item 8 restarts the
observation window on the date this ships anyway, which puts every
pre-repair recommendation outside it. The operator may rule otherwise, and
the reader's rule is one clause.

## Gate, release, record

- Gate: PASS on all four steps, 265/265 planted violations caught, on the tree that carried this item, the word-scan fix and the hold together
- Commit 23cf89b, merged fast-forward into the main checkout, pushed, and
  `Gridiron-Serve` restarted: `/api/health` answered 4941fa153c47 (the hold's commit, which landed in the same push).
- Restatement: 55 closes the old closer made (49 at the read, plus recs 50-55 closed overnight) restated on 2026-09-24: MLB spread 23 with a later read of their own contract (mean +0.30c) and 18 unmeasured; MLB total 8 (mean -0.94c) and 6 unmeasured. Shown beside the closing line, never inside it: the line now reads 0 of 50 in both markets
- Awake since the fix: the fix went live at about 06:57Z on 24 September; this close-out was written minutes later, so there is no awake fraction to report yet. The first honest figure comes with item 7's close-out
- Spend: local agents -- the repair map 2,265,274 tokens, this item's review 737,255; plan usage at 06:26Z: 20% of the 5-hour window, 19% of the week; extra usage $0.00
