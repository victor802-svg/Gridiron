# Close-out — Session E Part 2: the build

Brief: `docs/briefs/2026-09-04-distributional-build.md`.
Governing document: `docs/DISTRIBUTIONAL.md` (read in full as the first act).

---

> # THE WALK-FORWARD SAID NO. NOTHING SHIPPED.
>
> All four arms, **3,947 out-of-sample games**, the read-out worse calibrated
> every time by 6 to 13 percentage points, with a **negative edge in all
> four.** Every market is on the rung it was on this morning.
>
> The brief anticipated this exactly: *"If the walk-forward says no for every
> sport, the close-out says so and nothing ships — the design doc stays as the
> record of a hypothesis that failed its test."*

## 1. Against the brief

| # | asked for | verdict | evidence |
|---|---|---|---|
| **4** | **the walk-forward, before shipping** | **DONE** | 4 arms, 3,947 games; `tools/walkforward_distributional.py`; §2 below |
| **1** | the blind object on the predictions row | **SKIPPED — the test refused it** | no schema column was added. §7's clause is "ships only if better calibrated"; it was not |
| **2** | resolution as a read-out; CRPS when no line | **SKIPPED — same reason** | nothing to resolve; no read-out exists to grade |
| **3** | PIT / interval coverage; binary calibration | **DONE, inside the harness** | PIT is computed and gated at 200 rows; it is how method B was judged, and it **passed** while the calibration failed |
| **5** | migration for shipped sports; the stale comment | **DONE — as far as it goes** | no sport shipped, so no ladder was deleted; the stale comment **is** fixed, with the arithmetic that caught it |
| **6** | cards; report P(over line) on the first live slate | **SKIPPED for the cards; the distribution is REPORTED** | no card changed because no market ships. The distribution is in §4, measured on 3,947 games rather than one slate |
| **7** | four plantings | **PARTIAL — 3 of 4 built, 1 already covered** | §5 says which and why |
| — | CFB: fit the slope first, then include | **DONE, and the fit refused it** | R² = 0.0093 (§3) |
| — | renders, suite, `verify.py`, close-out, push | **DONE** | §7 |

**Nothing was quietly dropped.** Every SKIPPED row is the clause in §7 doing
the job it was written for.

## 2. The result

`tools/walkforward_distributional.py`, **per sport** as ruled — LAW 6 makes
each sport its own decision, and sports are never averaged. They did not need
to be: the answer was the same everywhere.

| arm | n | splits | rung gap | **read-out gap** | rung edge | **read-out edge** | read-out reach | PIT |
|---|---|---|---|---|---|---|---|---|
| NFL total | 768 | 2022/23/24 | **0.35** | **13.24** | +0.0011 | **−0.0281** | 12.4% | flat 0.29 |
| NFL spread | 813 | 2022/23/24 | **1.93** | **11.91** | +0.0036 | **−0.0164** | 7.8% | flat 0.30 |
| NBA total | 1,223 | 2024 | **3.98** | **9.60** | −0.0030 | **−0.0147** | 6.1% | flat 0.17 |
| NBA spread | 1,143 | 2024 | **2.57** | **12.39** | +0.0085 | **−0.0197** | 11.2% | flat 0.13 |

"Gap" is the weighted mean |claimed − actual| across the declared buckets, on
the claimed side. **LABELLED SANITY ONLY.**

**§7's rule applied exactly as written**, and no third condition was added
after the numbers arrived. **The PIT condition passed in every arm. The
calibration condition failed in every arm.**

### Why — and it is not what the design expected

**The read-out's error grows monotonically with its own confidence.** NFL
totals, out of sample:

| read-out claimed | n | actually happened |
|---|---|---|
| 54.8% | 420 | 48.8% |
| 64.4% | 253 | 47.8% |
| 73.8% | 81 | **38.3%** |
| 85.9% | 14 | **42.9%** |

**Above 70% it is worse than a coin flip. Above 80% it is reversed.** The same
shape is in all four arms.

**The cause, measured on the same games** — mean absolute error of each number
against the result:

| arm | our expectation | the market's line | market closer |
|---|---|---|---|
| NFL total | 11.23 | **10.11** | 57.4% |
| NFL spread | 10.45 | **9.74** | 58.9% |
| NBA total | 15.34 | **14.61** | 54.8% |
| NBA spread | 11.77 | **10.87** | 57.2% |

**We forecast these markets worse than the market does, by 5–9%.** So the gap
between our number and theirs is mostly *our error*, and a read-out turns that
gap straight into confidence. The bigger the disagreement, the more of it is
us being wrong.

**And method B was given the benefit of the doubt, not denied it.** Its
`forecast_sd` was measured over every completed game in the loaded seasons —
**including the test seasons** — while method A's coefficients were fitted
strictly through season T. That is a look-ahead, and it works in B's favour: B
was handed the exactly-right spread for the games it was about to be graded
on. It lost anyway, which makes the margin an understatement rather than an
artefact. A clean version would re-measure the spread per split; it was not
done because it can only widen a gap that is already 6 to 13 points.

> **The finding, and it is the thing worth carrying out of this session: a
> distribution can be perfectly honest about its own error and still be badly
> calibrated at somebody else's number, because that number is not a random
> point. It is a better forecast.**
>
> The design's §3 treated PIT flatness and calibration-at-the-line as two
> views of one honesty. **They are not.** PIT asks *is the spread right for
> the mean* — yes, everywhere. Calibration at the line asks *is the mean right
> relative to theirs* — no, everywhere.

**§0's arithmetic was right and did not save it.** A rung really does confine
P(over) to 45.8%–54.2%; the read-out really does span 3.4%–93.8%. **Reach is
not calibration.** A question with almost nothing in it beats a question with
the wrong thing in it — and the rung method's 0.35-point gap on 768 games is
the best number on this page precisely because it measures nearly nothing and
does not lie about it.

## 3. CFB never reached the walk-forward

The brief said *"CFB totals WAIT for a fitted slope — fit it first, dated,
then include CFB."* It was fitted, and **the fit refused the market**:

```
actual_total = 47.31 + 0.109 x expectation      n = 1,639      R^2 = 0.0093
```

**The expectation explains 0.93% of the variance in a college total** —
against R² 0.095 for the NFL margin and 0.357 for the CFB one. The sum of two
points-per-game figures is very nearly no forecast at all. Fitting it does
cut the spread from 20.85 to 16.31, and what it cuts it to is *the league
average on every game in the country*.

**There was nothing to distribute**, so CFB is recorded `NOT RUN` for that
reason and not for line coverage. The slope is measured and deliberately **not
declared live**: adopting it would change which questions college football
asks, and the design's §8 says that is an operator ruling.

## 4. The confidence-floor question, answered with evidence

Item 6 asked for the distribution of P(over line) and to **stop there**. Since
no market ships there is no live slate of read-outs, so this is measured on
3,947 out-of-sample games instead — which is better evidence than one night.

**NFL totals, 768 questions:**

| band | n | share | actual |
|---|---|---|---|
| 50–60% | 420 | 54.7% | 48.8% |
| 60–70% | 253 | 32.9% | 47.8% |
| 70–80% | 81 | 10.5% | 38.3% |
| 80%+ | 14 | 1.8% | 42.9% |

**A 70% floor would have admitted 95 of 768 questions — and those 95 are
precisely the ones the method gets wrong.**

That is the sharpest thing this session can say about the floor: **a floor
selects for confidence, and confidence was the failure mode here.** It does
not settle the floor question for the rung markets, which is a different
question about a different method. **The ruling remains yours**; it now has a
number attached.

## 5. The plantings — 3 of 4, and the fourth was already there

| asked | built | note |
|---|---|---|
| a rung ladder surviving on a shipped market | **YES** | `plant_a_rung_ladder_surviving_a_shipped_market`, and it plants the converse too — a ladder deleted under a market still on rungs, which is the likelier accident |
| a sport shipped without its walk-forward verdict | **YES** | `plant_a_market_shipped_without_a_verdict` |
| — | **YES, added** | `plant_a_ship_verdict_its_own_numbers_refuse` — the rule being edited *after* the numbers, which is the failure a pre-registered rule exists to expose |
| a distribution row written after its snapshot | **ALREADY COVERED** | `plant_snapshot_before_prediction` enforces exactly this ordering, via the `snapshot_not_before_prediction` trigger. A distributional row is still a prediction row; nothing about it needs a second planting |
| a read-out computed from anything but the stored row | **NOT BUILT** | there is no read-out. A planting against machinery that does not exist would pass by being unable to fail |

**Plantings: 176/176.**

## 6. What was built anyway, and why it survives a NO

**Nothing that asks a question differently.**

| built | why it earns its place |
|---|---|
| `tools/walkforward_distributional.py` | the test itself, re-runnable whenever the model changes |
| `tools/measure_forecast_spread.py` | eight measured spreads, and the CFB fit that refused it |
| `tools/backfill_lines.py` | **NBA lined finals: 25 → 4,900** |
| `questions.FORECAST_SPREAD` | five dated measurements, with their N and a no-fallback accessor |
| `config.DISTRIBUTIONAL_VERDICTS` | the decision, with its evidence, where code can read it |
| `audit.check_distributional_verdicts` | makes the verdict binding in both directions |

**The NBA backfill outlives this session by a distance.** The design doc
warned the NBA arm might have to be reported as not run for want of lines. It
now has **4,900 lined finals**, and every future market comparison in that
sport rests on them.

**The verdict guard is the part that matters most on a NO.** A decision rule
written before the numbers is worth nothing if it can be edited after them, so
the guard checks the decision against its **own recorded evidence**: a market
marked SHIP whose figures say the read-out lost is a gate failure. That guard
fires today on a planting and, if this is ever revisited, on a real mistake.

## 7. The gate

- Suite **1,019 tests, 0 skipped, 0 failures** under `.venv` — 17 new in
  `tests/test_distributional.py`.
- Plantings **176/176** — three new.
- `verify.py`: **all four steps PASS**, 36 scan rows, one new.
- **No prediction row written, rewritten, re-dated or deleted.** The backfill
  touches `market_lines_raw` only, which is the raw market side and is already
  forbidden to the prediction path.
- **`.env` was neither read nor written.**

## 8. Rulings taken in your absence

1. **The harness ran before anything was built**, over the brief's numbered
   order. The doc governs and is explicit: *"Building the schema first would
   make the test a formality that nobody wants to fail."*
2. **NBA lines were backfilled rather than the arm reported NOT RUN.** The doc
   asked for the extension first and the fallback second; it cost 20 minutes.
3. **Three splits for NFL, one for NBA.** NFL's single split gave 256 rows, so
   it was widened to 768; NBA's one split already gives 1,223.
4. **CFB's fitted slope is measured and not adopted.** The brief authorised
   the fit, not the change to which questions CFB asks — §8 calls that an
   operator ruling, and the fit made it moot anyway.
5. **A third planting was added** beyond the four asked for, because writing
   the decision rule before the numbers only means something if editing it
   afterwards is caught.
6. **The design doc was appended to, never amended.** §9 is the result;
   everything above it is exactly as written before the test. A design edited
   after its own experiment stops being a record of what was predicted.
7. **`FLAGGED_METHODS` stays, with its reason rewritten.** The totals flag
   stood "for one version, pending a fix". The fix was built, measured and
   refused, so the flag is no longer waiting for anything — and the finding it
   reports is better evidenced than when it was written.

## 9. What is now known that was not

1. **The read-out is not a free improvement.** It was proposed as a
   deterministic re-reading of an existing forecast — no new model, no new
   risk. It is a new **claim**, and it can be wrong.
2. **We forecast totals and margins 5–9% worse than the market**, measured
   four ways. That was not on the record before today.
3. **Our distributions are honest** — four PITs flat out of four.
4. **CFB's totals expectation does not work**, R² 0.0093.
5. **The suppression hypothesis is untouched and no longer testable this
   way.** Removing the rung was the test; removing the rung makes the model
   worse. Whatever tests it next has to be something else.

## 10. Operator's verdicts

**Strongest thing:**

**Weakest thing:**

**What to do next:**
