# Close-out — Session E Part 1: the distributional design

Brief: `docs/briefs/2026-09-04-distributional.md`.
Deliverable: `docs/DISTRIBUTIONAL.md`.

**One document. No code.** "Commit the doc, then STOP" was the instruction, and
a design session that ships a helper function has stopped being a design
session.

---

## 1. Against the brief

| § | asked for | verdict | evidence |
|---|---|---|---|
| **0** | the causal claim, stated first | **DONE** | §0, and it is now **measured** rather than asserted — see §2 below |
| **1** | the blind object: what is stored, how the spread is measured, constant or conditional | **DONE** | 3 columns + 3 CHECKs; 8 SDs measured on 24,861 games; conditional variation measured at 1–6% and **constant chosen with the table as evidence** |
| **2** | resolution at the market line; continuous scoring when no line exists | **DONE** | read-out on the snapshot row; CRPS closed form, own table, own gate; **`open_at_predict` declared as the graded snapshot** |
| **3** | PIT / interval coverage, binary calibration, the tier chip, LAW 4 | **DONE** | PIT with a 200-row gate; tier mapping **unchanged**, and the point is that its buckets start filling |
| **4** | what the card shows, with and without a line; the hero; plain words | **DONE** | both cards written out and arithmetically consistent with each other; a said/never-said table |
| **5** | migration: deletions dated, existing rows stand, like-for-like comparison, moneylines | **DONE** | 6 deletions listed; LAW 3 keeps old rows under their version; **moneylines do nothing and are named as the control group** |
| **6** | non-Gaussian spreads, line drift, a line that never posts | **DONE** | **CFB fat tails measured and refuted**; drift declared with its 15-row caveat; unpriced rows become gradeable |
| **7** | a walk-forward plan, and the ships-only-if clause | **DONE** | the clause is stated as a clause; the decision rule is **written before the numbers**, and the split-result tie-break is left to you on purpose |

**Nothing SKIPPED. Nothing DECLINED. Nothing PARTIAL.**

## 2. What was measured

Four scratchpad scripts, nothing entering `gridiron/`.

### The spread of the model's own forecast — 8 measurements, 24,861 games

| sport | market | n | bias | **SD** | skew | excess kurtosis |
|---|---|---|---|---|---|---|
| NFL | total | 2,478 | +0.05 | **14.28** | 0.24 | 0.21 |
| NFL | margin | 2,603 | −0.13 | **13.54** | 0.07 | 0.25 |
| NBA | total | 4,841 | +0.11 | **18.83** | 0.20 | 0.29 |
| NBA | margin | 4,602 | −0.01 | **14.24** | −0.01 | 0.39 |
| CFB | total | 1,639 | **−1.93** | 20.85 | 0.10 | 0.00 |
| CFB | margin | 1,635 | +0.05 | **17.46** | 0.13 | 0.20 |
| MLB | total | 9,319 | +0.00 | **4.65** | **0.64** | 0.55 |
| MLB | margin | 9,319 | +0.02 | **4.63** | −0.06 | 0.82 |

**This is not the SD already in the codebase.** `MARGIN_SD_BY_SPORT` and
`TOTAL_SD_BY_SPORT` hold residuals against **the market's** line. This is the
spread of **our** forecast — a different, wider quantity, and confusing the
two is the mistake that produced the false 4.71-versus-4.534 discrepancy in
the run-line probe. The doc says so where the table appears.

**Two independent cross-checks passed.** NFL margin came back at 13.54 against
the **13.50** already recorded in `EXPECTED_MARGIN_FIT`, and CFB margin at
17.46 against its recorded **17.39** — measured by a different route and
reproducing. And we are 4–6% wider than the market in both sports where both
exist, which is the direction honesty requires.

### The suppression, explained — the finding of the session

Measured on the **same NFL games**, the same two factors, two markets:

| | **spread** (asked at our rung) | **moneyline** (no rung) |
|---|---|---|
| corr(`srs_diff`, label) | **−0.0227** | **+0.2561** |
| corr(`recent_form_diff`, label) | **+0.0409** | **+0.2350** |
| corr(`srs_diff`, `recent_form_diff`) | **0.6982** | 0.7026 |

The two factors are correlated at **0.70 with each other in both markets** —
that is a property of the factors. Against the moneyline's label they each
carry real signal; **against the spread's label, on the same games, both
collapse to nothing and point in opposite directions.**

The rung is chosen from `expected_margin`, which is a linear function of
`srs_diff`, so the label is approximately "was the residual positive" — and a
residual is orthogonal to what it was taken out of by construction. Two
variables correlated at 0.70 and near-orthogonal to the label is exactly the
configuration in which a fit assigns large opposite-signed coefficients that
cancel.

**Demonstrated twice across two sessions and explained never. It now has a
mechanism and a measurement.** It is still a hypothesis; §7 is the test.

### What the redesign is worth — the structural comparison

2,478 completed NFL games with a stored market total:

| | rung method | **read-out** |
|---|---|---|
| P(over) range | 45.8% – 54.2% | **3.4% – 93.8%** |
| share outside 45–55% | 0% | **70.4%** |
| **share reaching 70% either way** | **0%** | **12.8%** |

The market's total sits a median of **3.12 points** from our expectation (p90
8.12, max 26.0, SD 4.97). **That gap is the claim, and a rung discards it.**

**12.8% is the number that changes the product**, and it answers your open
question from the last close-out in passing: no totals card can reach STRONG
today because the arithmetic forbids it, and a confidence floor becomes
meaningful the moment the probabilities can spread out.

### Two things the record said that we were not looking for

**CFB's totals expectation is biased by −1.93 points**, and its pooled SD of
20.85 against within-band SDs of 16.8–18.4 shows the bias moves with the
expectation. That is the same defect the CFB *margin* had before its slope and
intercept were fitted on 2026-09-03; the total has never had either.
**So the doc says CFB should not ship distributionally until it does.**

**MLB's total is right-skewed at +0.64** — runs are counts, bounded below,
with a long right tail no symmetric distribution can hold. `MLB_SCORE_DISTRIBUTION`
records mean 8.97 against variance 20.35, which is strongly over-dispersed.
**A run total is a count and should go on Session C's rate machinery**, not a
Gaussian.

### And the brief's own worry, checked

**"Fat tails in CFB margins — measure."** Measured: excess kurtosis **0.20**,
coverage 68.6 / 94.9 / 98.5 against a normal's 68.27 / 95 / 99, and **0.18%
beyond 3σ against a normal's 0.27% — the thinnest tail of all eight.** The
concern was reasonable and the record does not support it. Football margins
are lumpy at 3 and 7; lumpiness is not weight in the tail, and it is the tail
a Gaussian would misprice.

## 3. A stale comment, recorded and not fixed

`model/questions.py` still says CFB's `EXPECTED_MARGIN_FIT` entry "IS RECORDED
AND NOT YET USED" and that `cfb_expected_margin` "still runs on its original
slope of 1.0 and intercept of 9.79".

**It does not.** The function returns `expected_margin("cfb", …)`, and this
session's measurement confirms the fitted version is live: bias **+0.05**
against the ~9.8-point bias the old constants would produce, and SD 17.46
against the fit's recorded 17.39.

**The code is right and the comment is three days stale.** Recorded rather than
fixed, because this session writes no code. Part 2 deletes those two
paragraphs.

## 4. Rulings taken in your absence

Ten design decisions the brief left open. Each is in the doc with its
reasoning; this is the index.

1. **The spread is constant per (sport, market), not conditional.** Measured
   variation across expectation terciles is 1–6% and mostly not monotone — a
   correction smaller than one ladder step, for a second fitted object with
   its own factors and its own calibration.
2. **Normal for NFL, NBA and CFB; MLB totals go to the count machinery.**
   Seven of eight distributions are boringly Gaussian; MLB's total is the one
   that is not, and skew is the reason rather than kurtosis.
3. **The distribution lives on the `predictions` row**, not a side table.
   Forced, not chosen: `snapshot_not_before_prediction` ABORTs a snapshot
   older than its prediction, so the blind row must be written first — and a
   design that wrote it later would be **rejected by the database, correctly**.
4. **The read-out lives on `market_snapshots`**, because the snapshot is the
   moment the line arrives. Nothing is updated; LAW 3 needs no exception.
5. **CRPS gets its own table.** Resolution may write exactly `resolved_utc`
   and `outcome` past the no-update trigger, and widening that is how an
   append-only guarantee erodes. One join is cheaper than a wider trigger.
6. **`open_at_predict` is the graded snapshot**, and `near_start` is stored,
   read out and not graded. It exists for 560 rows against 15; it is the line
   the card actually showed; and it is the earlier of the two.
7. **CFB does not ship until its totals expectation is fitted** (§2 above).
8. **A card with no line is never the hero.** "The model expects about 52
   points" is not a claim about a question anyone has asked. It reuses
   `heroPool`, which is the second use of a door built for ruling 2.
9. **The §7 decision rule is written before the numbers**, with two conditions
   and an explicit refusal to add a third afterwards.
10. **The calibration comparison was NOT run**, though the data would allow a
    preliminary read. §7 assigns it to Part 2, and **a design session that
    pre-empts its own test is not a design session.** The line drawn: the
    *dynamic range* is structural and is measured here; *performance* is
    Part 2's.

## 5. The gate

- Suite **1,002 tests, 0 skipped, 0 failures** under `.venv`.
- **No code changed**, so the gate is a confirmation rather than a check: the
  only tracked change is three markdown files.
- **`.env` was neither read nor written.**

## 6. What Part 2 begins with

Read `docs/DISTRIBUTIONAL.md`, then build **the measurement harness only** — a
`tools/` script that computes both methods on completed games and writes
nothing to `predictions`. The schema, the read-out, the deletions and the card
come after the walk-forward passes, and **only** if it passes.

> **The change ships only if the distributional read-out is better calibrated
> than the current rung method, on identical games, walk-forward.**
>
> If it is not, this document is the record of a hypothesis the evidence
> refused, and that is a result rather than a failure.

**Blocked on you, and named in the doc's §8:** whether CFB's totals
expectation gets a fitted slope and intercept; whether `near_start` ever
becomes the graded snapshot (answerable at 100 paired snapshots, 15 today);
whether MLB totals move to the count machinery; and the tie-break if the
walk-forward splits by sport — **left to you deliberately, because a tie-break
written by whoever wants the answer is not a tie-break.**

## 7. Operator's verdicts

**Strongest thing:**

**Weakest thing:**

**What to do next:**
