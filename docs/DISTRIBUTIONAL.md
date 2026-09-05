# Distributional totals and spreads — the design

**GRIDIRON_18 Session E, Part 1.** Design only. No code was written in the
session that produced this document, by the brief's instruction. Part 2 begins
by reading it.

Brief: `docs/briefs/2026-09-04-distributional.md`.
Ruling: `docs/DECISIONS_MADE.md`, 2026-09-04 ruling 1.

---

> # OUTCOME: THE WALK-FORWARD REFUSED IT. NOTHING SHIPPED.
>
> **Part 2 ran §7's test on 2026-09-04. All four arms said DO NOT SHIP**, on
> **3,947 out-of-sample games.** This document stands as the record of a
> hypothesis that failed its test, which §7 said it would be. The full result
> is **§9**, at the bottom; the sections between are left exactly as they
> were written, because a design edited after its own test is no longer a
> record of what was predicted.
>
> | arm | n | rung gap | **read-out gap** | rung edge | **read-out edge** | PIT |
> |---|---|---|---|---|---|---|
> | NFL total | 768 | 0.35 | **13.24** | +0.0011 | **−0.0281** | flat |
> | NFL spread | 813 | 1.93 | **11.91** | +0.0036 | **−0.0164** | flat |
> | NBA total | 1,223 | 3.98 | **9.60** | −0.0030 | **−0.0147** | flat |
> | NBA spread | 1,143 | 2.57 | **12.39** | +0.0085 | **−0.0197** | flat |
>
> **The structural argument in §0 was right and did not survive contact with
> the market.** The read-out does span 3.4%–93.8% where a rung spans
> 45.8%–54.2%, and 12.4% of its questions do reach 70%. Every one of those
> extra claims is worse than a coin flip: the read-out's edge over
> always-the-base-rate is **negative in all four arms.**
>
> **Every PIT came back flat**, so the distributions were honest about their
> own width. **That is the finding, and §10.2 states it properly:** a
> distribution can be perfectly honest about its own error and still be badly
> calibrated at somebody else's number, because that number is not a random
> point — it is a better forecast.

---

## 0. The causal claim, stated first

> **A binary asked at the model's own expected value is a coin flip by
> construction.**

Not a weak model. Not a hard market. **A question with almost nothing in it,**
and the arithmetic says how little before any model is fitted.

A rung is chosen as the ladder point nearest our own expectation, so the
distance between them is bounded by half a ladder step. Divide that by the
spread of the thing being forecast and you have the entire dynamic range of
the probability the question can carry:

| market | ladder step | max &#124;µ − rung&#124; | forecast SD | max &#124;z&#124; | **P(over) can only ever be** |
|---|---|---|---|---|---|
| NFL total | 3.0 | 1.5 | 14.28 | 0.105 | **45.8% – 54.2%** |
| NBA total | 5.0 | 2.5 | 18.83 | 0.133 | **44.7% – 55.3%** |
| NFL spread | 2.0 (modal) | 1.0 | 13.54 | 0.074 | **47.1% – 52.9%** |

An NFL total asked at its own rung cannot express a claim stronger than 54%
**from the choice of rung alone**. Everything above that has to come from
factors predicting the residual, and a residual 14.28 points wide is not much
moved by wind and pace. The measured edges follow exactly: **NBA total
+0.0010, NFL total +0.0016** walk-forward against always-the-base-rate.

**The fix is not a better ladder. It is not asking the question that way.**

### The blind object becomes a distribution

The model writes, before any line exists, its **forecast distribution** of the
total or the margin: a mean and a measured spread. Once the market line is
snapshotted, **P(over the market's line) is read off that stored
distribution** — `Φ((µ − line) / σ)`, a deterministic function of a row that
already exists and cannot change.

**That is not a second forecast, so LAW 1 holds exactly.** The blind object is
written first, is append-only, and the read-out adds no information the
distribution did not already contain. Section 1 makes that structural rather
than promised.

### What it is worth, measured

On 2,478 completed NFL games with a stored market total, the read-out at the
market's line would have asked:

| | rung method | **distributional read-out** |
|---|---|---|
| P(over) range | 45.8% – 54.2% | **3.4% – 93.8%** |
| 5th – 95th percentile | — | **27.9% – 70.0%** |
| share outside 45–55% | 0% | **70.4%** |
| share outside 40–60% | 0% | **44.8%** |
| share reaching 70% either way | **0%** | **12.8%** |

The market's total sits a median of **3.12 points** from our expectation, p90
**8.12**, max **26.0**, with an SD of **4.97**. That gap is the claim. A rung
throws it away by construction; a read-out is made of it.

**12.8% is the number that changes the product.** Today no totals card can
reach the STRONG tier — the arithmetic forbids it. Under the read-out, one
totals question in eight would. That also answers, in passing, the open
question from the 2026-09-04 close-out about whether game markets need a
confidence floor: **the floor becomes meaningful the moment the probabilities
can spread out.**

### And it explains the spread-pair suppression

`srs_diff` and `recent_form_diff` mutually suppress on the NFL and CFB
**spreads** — both coefficients inflating, opposite signs — and behave
normally on both **moneylines**. Demonstrated twice, explained never.

Measured this session on the **same NFL games**, same two factors:

| | **spread** (asked at our rung) | **moneyline** (no rung) |
|---|---|---|
| n | 2,632 | 2,629 |
| base rate | 0.4867 | 0.5466 |
| corr(`srs_diff`, label) | **−0.0227** | **+0.2561** |
| corr(`recent_form_diff`, label) | **+0.0409** | **+0.2350** |
| corr(`srs_diff`, `recent_form_diff`) | **0.6982** | 0.7026 |

The two factors are correlated with each other at **0.70 in both markets** —
that is a property of the factors, not of the question. Against the
moneyline's label they each carry real signal. **Against the spread's label,
on the same games, both collapse to nothing and point in opposite
directions.**

**The rung is why.** It is chosen from `expected_margin`, which is a linear
function of `srs_diff`. The label "did the home side cover *our* rung" is
therefore approximately "was the residual positive", and a residual is
orthogonal to the thing it was taken out of **by construction**. The moneyline
has no rung, so nothing is subtracted.

Two variables correlated at 0.70 with each other and near-orthogonal to the
label is **precisely** the configuration in which a fit assigns large
opposite-signed coefficients that cancel: almost any large opposing pair fits
a near-zero relationship equally well, and only the ridge bounds them. That is
what the suppression looks like, and it is what the record shows.

**This is a hypothesis with a mechanism and a measurement, not a proof.**
Section 7 is how it gets tested before anything ships.

---

## 1. The blind object

### What is stored

Three new columns on `predictions`, and nothing that is not a measurement:

| column | type | meaning |
|---|---|---|
| `forecast_mean` | REAL | the model's expected total or margin, in points/runs |
| `forecast_sd` | REAL | the measured spread of that forecast, same units |
| `forecast_family` | TEXT | `normal` \| `negbin` — the distribution's shape |

**On the prediction row itself, not in a side table, and the ordering trigger
is why.** `snapshot_not_before_prediction` ABORTs any snapshot whose
`fetched_utc` precedes its prediction's `created_utc`. So the blind row must
be written **before** the line is fetched — which is what LAW 1 wants anyway —
and a design that wrote the prediction after the snapshot would be rejected by
the database, correctly. One row, one insert, written blind.

**`factors_json` is not the place for it.** That column is the factor payload
and the decomposition reads it; putting a forecast in there would be the kind
of convenient overload this project refuses elsewhere.

### What happens to `model_prob` and `model_side`

Both are `NOT NULL` today, and a distributional row has neither until a line
arrives. The schema must say which kind of row it is holding:

```sql
-- Exactly one of the two forms. A row is a probability at a line we chose,
-- or a distribution with no line at all. Never both, never neither.
CHECK ((model_prob IS NULL) <> (forecast_mean IS NULL)),
CHECK (forecast_mean IS NULL OR (forecast_sd IS NOT NULL
                                 AND forecast_sd > 0
                                 AND forecast_family IS NOT NULL)),
CHECK ((model_prob IS NULL) = (model_side IS NULL))
```

This is the idiom the table already uses — `CHECK ((resolved_utc IS NULL) =
(outcome IS NULL))` — applied to the new shape. **A half-written
distributional row cannot exist**, and neither can a row that is somehow both.

`line_asked` is already nullable and becomes NULL for these markets. That is
the column the whole ruling is about, and it goes quiet rather than away
(section 5).

### Where the read-out is stored

**On the snapshot row**, because the snapshot *is* the moment the line
arrives:

| column | meaning |
|---|---|
| `readout_prob` | `Φ((forecast_mean − line) / forecast_sd)`, the probability of "over" |
| `readout_side` | `over` \| `under` — whichever side that probability exceeds 0.5 on |

`market_snapshots` is already append-only, already carries `prediction_id`,
`line`, `fetched_utc` and `kind`, and is already guarded to come after its
prediction. **Nothing is ever updated.** LAW 3 holds because no row changes;
LAW 1 holds because the distribution predates the line and the read-out is a
pure function of the two.

### How the spread is measured

Measured **2026-09-04**, per sport and per market, as
`SD(actual − the model's own expectation)` over every completed game in the
loaded seasons.

> **This is NOT `market.lines.MARGIN_SD_BY_SPORT` or `TOTAL_SD_BY_SPORT`.**
> Those hold `SD(actual − THE MARKET'S line)` and exist for the market
> comparison. This is the spread of **our** forecast, which is a different and
> generally wider quantity. Confusing the two is the mistake that produced a
> false 4.71-versus-4.534 discrepancy in the run-line probe, and it is written
> here so it is not made a third time.

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

**Two cross-checks that the measurement is right.** NFL margin comes back at
13.54 against the **13.50** already recorded in `EXPECTED_MARGIN_FIT`
(2026-09-03), and CFB margin at 17.46 against its recorded **17.39** — both
measured independently, by a different route, and reproducing.

**Against the market's own residuals, we are wider where we should be:** NFL
13.54 vs the market's 12.70, NBA 14.24 vs 13.95. The market is a better
forecaster than we are, by 4–6% of spread, which is the honest expectation and
a useful sanity check on the whole exercise.

### Constant or conditional

**Constant per (sport, market), for version one.** Measured rather than
assumed — the SD within terciles of the expectation:

| sport / market | low third | middle | high third | spread of spreads |
|---|---|---|---|---|
| NFL total | 13.64 | 13.58 | 14.33 | +5.4% |
| NFL margin | 13.99 | 12.80 | 13.79 | non-monotone |
| NBA total | 18.38 | 18.53 | 19.56 | +6.4% |
| NBA margin | 14.03 | 14.00 | 14.31 | +2.0% |
| MLB total | 4.44 | 4.53 | 4.65 | +4.6% |
| MLB margin | 4.57 | 4.55 | 4.52 | −1.1% |

**The variation is 1–6% and mostly not monotone.** A conditional spread would
be a second fitted object, needing its own factors, its own dated declaration
and its own calibration — for a correction smaller than the difference between
two adjacent ladder rungs. **It is not worth it in version one, and this table
is the evidence rather than the assertion.**

Higher-scoring games do vary slightly more, in three sports out of four, which
is the physically sensible direction. If a conditional spread is ever built,
that is the shape to build, and this table is where it starts.

### The distribution family

**Normal, for NFL, NBA and CFB. Not for MLB.**

The normality check, against a normal's 68.27 / 95.00 / 99.00 / 0.27:

| sport / market | within 1σ | within 95% | within 99% | beyond 3σ |
|---|---|---|---|---|
| NFL total | 67.8 | 95.0 | 98.8 | 0.44 |
| NFL margin | 70.0 | 94.3 | 98.6 | 0.31 |
| NBA total | 68.9 | 95.3 | 98.9 | 0.37 |
| NBA margin | 69.8 | 94.5 | 98.5 | 0.59 |
| CFB total | 67.8 | 95.2 | 99.0 | 0.37 |
| CFB margin | 68.6 | 94.9 | 98.5 | 0.18 |
| MLB total | 68.7 | 95.5 | 98.5 | 0.62 |
| MLB margin | 71.0 | 94.7 | 98.2 | 0.72 |

**The brief asked specifically about fat tails in CFB margins. They are not
there:** excess kurtosis **0.20**, coverage 68.6/94.9/98.5, and **0.18% beyond
3σ against a normal's 0.27%** — the thinnest tail of the eight. The concern
was reasonable and the record does not support it. Football margins are
famously lumpy at 3 and 7, but lumpiness is not weight in the tail, and it is
the tail that a Gaussian would misprice.

**MLB is the exception, and it is skew rather than kurtosis.** The total is
right-skewed at **+0.64**: runs are counts, bounded below at zero, with a long
right tail that a symmetric distribution cannot represent. A normal fitted to
it will systematically underprice deep overs and overprice deep unders.

**MLB's totals go on the count machinery instead.** Session C's rate form
already fits counts with a log link and already distinguishes Poisson from
negative binomial by measured dispersion; `config.MLB_SCORE_DISTRIBUTION`
records mean 8.97 against variance 20.3 (SD 4.511) on 9,373 finals, which is
strongly over-dispersed and therefore negative binomial. **A run total is a
count and should have been a count all along.** The MLB *margin* (skew −0.06,
kurtosis 0.82) is a difference of two counts and is adequately normal.

### CFB's totals expectation is biased, and this is where it shows

CFB total is the one row with a real bias: **−1.93 points**, and its pooled SD
of 20.85 sits well above its within-band SDs of 16.8 to 18.4. **That gap is
not noise — it is a level error that varies with the expectation**, exactly
the defect the CFB margin had before `EXPECTED_MARGIN_FIT` measured its slope
and intercept on 2026-09-03.

`cfb_total_asked` still adds two points-per-game figures and rounds. **It has
never had a slope and intercept fitted to it.** Part 2 should measure them the
same way the margin's were, and the same ruling covers it: calibrating the
instrument that chooses the question is not factor discovery.

**Until then CFB totals should not ship distributionally**, because a
distribution with a 1.93-point bias is a confident claim in the wrong place,
and the read-out would convert that bias directly into miscalibrated
probabilities.

> **A stale comment found on the way.** `questions.py` still says CFB's entry
> in `EXPECTED_MARGIN_FIT` "IS RECORDED AND NOT YET USED" and that
> `cfb_expected_margin` "still runs on its original slope of 1.0 and intercept
> of 9.79". It does not — it returns `expected_margin("cfb", …)`, and this
> session's measurement confirms the fitted version is live (bias +0.05, SD
> 17.46 against the recorded 17.39). The code is right and the comment is
> three days stale. Recorded rather than fixed, because this session writes no
> code; Part 2 should delete those two paragraphs.

---

## 2. Resolution

### With a line: the same 0/1 grading, at somebody else's number

`outcome` stays `INTEGER CHECK (outcome IN (0, 1))`. Nothing about
append-only resolution changes.

**What changes is which probability is graded.** For a distributional row,
`model_prob` is NULL and the graded probability is the snapshot's
`readout_prob`. `calibration.resolved()` reads it from there. One query
changes; the Brier, the buckets, the tier table and every LAW 4 gate see a
probability and an outcome exactly as they do today.

The graded question becomes **"did the combined score go over the market's
line?"** — and for the first time it is *the same question the market was
asked*, which is what makes the comparison like-for-like (section 5).

**Which snapshot is graded — declared, not left to the reader.** The record
holds two kinds: `open_at_predict` (560 rows) and `near_start` (15).

> **The `open_at_predict` line is the graded one, from the day this ships.**

Three reasons, in order: it exists for every priced row where `near_start`
exists for fifteen; it is the line the **card actually showed** the reader,
so grading it grades what was claimed; and it is the earlier of the two, so
it cannot be accused of having drifted toward the outcome.

The `near_start` read-out is **computed and stored where a `near_start`
snapshot exists, and is not graded.** It is the drift study's input, and
section 6 says what it is for. A figure that is stored and not graded must say
so wherever it appears.

### With no line: a continuous score

A slate has questions before it has prices, and some never get one at all —
every UFC bout in 2026, on this record. Today those questions are simply
absent from the score. Under a distribution they need not be.

**CRPS, the continuous ranked probability score.** For a normal forecast it
has a closed form and needs no numerical integration and no numpy:

```
z = (y − µ) / σ
CRPS(N(µ, σ²), y) = σ · [ z·(2Φ(z) − 1) + 2φ(z) − 1/√π ]
```

It is in the same units as the forecast — points, or runs — and it collapses
to `|y − µ|` as σ → 0, so a sharpened forecast is rewarded only if it is also
accurate. **It is a proper score**, which is the property that matters: a
model cannot improve it by claiming a spread it does not have.

**Mean absolute error is recorded beside it and is not the score.** `|y − µ|`
ignores σ entirely, so it cannot tell an honest wide forecast from an
overconfident narrow one. It is kept because it is the number a person can
read — "the model is off by 10.4 points on a typical NFL game" — and CRPS is
not.

**Its own table, and its own gate.**

```sql
CREATE TABLE prediction_scores (
    prediction_id INTEGER PRIMARY KEY REFERENCES predictions (id),
    scored_utc    TEXT NOT NULL,
    actual        REAL NOT NULL,
    crps          REAL NOT NULL,
    abs_error     REAL NOT NULL
);
```

Not a column on `predictions`, and deliberately: resolution is permitted to
write exactly `resolved_utc` and `outcome` past the no-update trigger, and
widening what that update may touch is how an append-only guarantee erodes.
A separate append-only table costs one join and keeps the trigger narrow.

**LAW 4 applies unchanged and needs a threshold of its own.** A mean CRPS is a
figure shown to a human, so it renders with its N, and no comparison between
two CRPS figures is claimed below `MIN_SAMPLE_FOR_EDGE_CLAIM` (100) in that
category. **Declared with the date it opens**, like every other constant here.

> **A CRPS is not a Brier and the two never appear in one number.** They score
> different questions in different units. LAW 6's reasoning — a figure that
> mixes two things describes neither — applies exactly.

---

## 3. Calibrating a distribution

Two checks, because a distribution can fail in two independent ways: it can be
in the wrong **place**, or it can claim the wrong **width**.

### The honesty check: PIT

For every resolved distributional forecast, the probability integral
transform:

```
u = Φ((y − µ) / σ)
```

**If the distribution is honest, `u` is uniform on [0, 1].** That is the whole
test, and its failure modes are legible on sight:

| PIT histogram | what it means |
|---|---|
| ∪-shaped (piles at 0 and 1) | **too narrow** — the model is overconfident, reality lands outside its range too often |
| ∩-shaped (piles in the middle) | **too wide** — the model is hedging |
| sloped | **biased** — the mean is systematically off |
| flat | honest |

Rendered as a ten-bin histogram per (sport, market), beside the calibration
chart, with its N — one bar per decile, and a flat line drawn at N/10 so the
shape is read against the thing it should be.

**Central-interval coverage is the same fact as a table**, and it is the one
to put in words because a person can check it — *"the model said half of games
would land within 10 points of its number, and 51% did"* is a sentence a
reader can hold against the record. (An illustration: 9.6 points is the 50%
central interval at NFL's measured spread of 14.28, and the 51% would be the
live figure.) The measurements in
section 1 are that table computed on the training data — 67.8% within 1σ
against a normal's 68.27%, and so on — and the live version is computed on
resolved forward rows only.

**PIT needs its own gate.** A ten-bin histogram on twenty rows is two per bin
and is noise wearing the shape of a finding. It renders provisional below
`MIN_SAMPLE_FOR_BUCKET_POINT × 10` = **200 resolved rows**, and says so.

### The tier chip: unchanged, and that is the point

`calibration.TIERS` maps a probability bucket to a name — 50–60% LEAN, 60–70%
SOLID, 70%+ STRONG — and `tier_from_bucket` refuses to state an earned
accuracy below `TIER_MIN_SETTLED` (20) settled rows in that bucket.

**None of that changes.** The chip maps from `readout_prob` exactly as it maps
from `model_prob` today, because a probability is a probability and the bucket
does not care where it came from.

**What changes is that the buckets fill.** Today an NFL total cannot produce a
number above 54.2%, so its 70%+ bucket is empty by construction and STRONG is
unreachable. Under the read-out, **12.8% of NFL totals questions land beyond
70/30** — the tier table gets rows it can never have today, and the tier gate
starts meaning something for game markets.

**LAW 4's gates are untouched:** 20 settled for a bucket point or a tier's
earned accuracy, 100 for an edge claim, every figure with its N. A
distribution changes what is asked, not what may be claimed about it.

---

## 4. What the card shows

The plain-words law applies to every sentence below: composed in
`language.py`, never in the browser, and no internal identifier reaches any of
them.

### Once a line exists

The card looks like it does today, because the claim has the same shape:

> **Chiefs / Bills over 48.5** · STRONG
> **61%** chance the two teams combine for more than 48.5
> *the market's number, and the model's is 52.4*

The probability is the read-out. **The line in the headline is the market's,
which is new**: today it is a rung of ours that the reader has no reason to
care about. The model's own expectation is shown beside it, because the reader
should be able to see the disagreement that the probability is made of.

**Two numbers, and neither is a second probability.** The cards brief's R2 —
one number and the word for what it is a number of — is about probabilities on
a collapsed face. 48.5 and 52.4 are points, they are labelled as points, and
the difference between them is the entire claim.

### Before a line exists

The expectation, in words, and no probability at all:

> **Chiefs / Bills** · no line yet
> **the model expects about 52 points between them**
> *give or take 14 — a line will sharpen this into a pick*

**The two cards above are the same game.** 52.4 expected, a spread of 14.28,
and a market line of 48.5 give `Φ((52.4 − 48.5) / 14.28)` = **61%** — the
number on the first card, arrived at without a second forecast.

**No percentage on the second, because there is nothing to be a percentage
of.** A probability with no line is either a rung we invented — which is the
thing this whole design deletes — or a claim about nothing. The honest card
says what the model thinks and says that it is waiting.

**"Give or take 14" is the spread, in the one form a reader can check.** It is
`forecast_sd` rounded to whole points, and it is on the card because a
forecast of 52 points means something different at ±5 than at ±14, and a
reader shown only the 52 has no way to know which they are looking at. It is
the same argument as showing the N.

**Rounding is not decoration.** A mean is shown to the nearest point and a
spread to the nearest point, because a total carried to one decimal claims a
precision the fit does not have — the same ruling `rate_line` already follows.

### The hero

**A distributional card with a line is eligible for the hero like any other**,
and the flag from ruling 2 comes off the moment this ships (section 5).

**A card with no line is never the hero.** The hero is the largest claim on
the page and "the model expects about 52 points" is not a claim about a
question anyone has asked yet. It belongs in the grid, where a reader browsing
the slate can see it.

`heroPool` already filters on a field the server writes — it needs no new
mechanism, only the same one pointed at the absence of a read-out. **That is
the second use of a door built for the first**, which is the argument for
having built it that way.

### What plain words look like here

| said | never said |
|---|---|
| "the model expects about 52 points between them" | "µ = 52.4" |
| "give or take 14" | "σ = 14.28", "±1 SD" |
| "the two teams combine for more than 48.5" | "over 48.5", "O/U" |
| "the market has it 4 points higher than we do" | "the residual is −4.0" |
| "how often reality landed inside the model's range" | "PIT", "coverage" |

**PIT is the hardest word in this document and it never reaches a reader.**
The histogram's caption is a sentence about what the model promised and what
happened, and the acronym stays in the code where it belongs.

---

## 5. Migration

### What is deleted, and when

On the day Part 2 ships, dated in the registry and in `DECISIONS_MADE.md`:

| deleted | why it existed |
|---|---|
| `NFL_TOTAL_LADDER`, `NFL_TOTAL_MIN/MAX`, `nfl_total_asked` | to pick a rung |
| `NBA_TOTAL_LADDER`, `nba_total_asked` | to pick a rung |
| `cfb_total_asked`, `mlb_total_asked` | to pick a rung |
| `SPREAD_LADDER`, `CFB_SPREAD_LADDER`, `cfb_spread_rung`, `assert_on_ladder` for spreads | to pick a rung |
| `asked_line` and every `*_asked_distance` factor | **to measure the rounding residual of our own choice** |
| `config.FLAGGED_METHODS`'s totals entries | the caveat this design removes the need for |

**The asked-distance factors are the point of the whole exercise.** They exist
to tell the model how far the question sits from what it expects — which is
information about the ladder, not about the game. When the question is the
market's number, the distance from our expectation **is** the forecast, and it
does not need a factor to carry it.

**The prop ladders stay.** `MLB_PROP_LADDER` and every prop rung are untouched:
a prop line is genuinely posted by a source, and a prop asked at a declared
rung is not asking at its own expectation. **UFC's `rounds` also stays** — its
rung is the bout's scheduled length, which is nobody's expectation of
anything.

### What happens to the rows already written

**Nothing. They stand.** LAW 3 is append-only and a prediction is never
re-scored, so every existing totals and spreads row keeps its `line_asked`,
its `model_prob` and its outcome, under the `factor_set_version` it was
written with.

**Which is precisely why the version exists.** The old rows are the forward
record of the rung method, the new rows are the forward record of the
read-out, and the two are never pooled into one curve — the same rule that
keeps two sports apart, applied to two methods. `calibration` already filters
by `factor_set_version`; it needs a new version string, not new machinery.

**The scorecard will show both for a season**, and it should. A reader
comparing them is doing the thing this project is for.

### The market comparison becomes like-for-like

Today the market comparison converts the market's line into a probability *at
our rung* using `implied_cover_probability` and a residual SD, so that two
different questions can be put on one axis. **That conversion exists only
because the questions differ.**

Under the read-out, both sides are answering "over the market's number", and
the comparison is direct: our probability against theirs, no SD in the middle,
no conversion to argue about. `MARGIN_SD_BY_SPORT` and `TOTAL_SD_BY_SPORT`
**stay** — they are still needed to turn a moneyline price into an implied
probability, and they remain what they always were, residuals against the
market's line.

### What the moneylines do

**Nothing.** A moneyline has no line to be asked at — the question is "did the
home side win", which is fixed by the sport. There is no rung, nothing is
subtracted, and section 0's table shows those markets behaving normally
already. They are the control group, and they should stay untouched so they
can keep being one.

---

## 6. What could go wrong

### The distribution is the wrong shape

**Measured, section 1.** Seven of eight are close enough to normal that the
coverage table is boring, which is the result you want. **MLB's total is
right-skewed at +0.64 and goes on the count machinery instead** — that is a
design decision taken here, not a risk left open.

**The residual risk is that a season changes shape.** A rule change, a
different ball, an expansion team. The PIT histogram in section 3 is the
instrument that would show it: a distribution that stops being normal stops
being flat. **It is a monitor, not a one-off check**, and that is why it goes
on the page rather than into a probe.

### The line moves between snapshot and close

**The record already holds both**: `open_at_predict` (560 rows) and
`near_start` (15). Section 2 declares that **`open_at_predict` is graded** and
`near_start` is stored, read out, and not graded.

**The honest caveat is the sample.** Fifteen `near_start` snapshots is not
enough to say anything about drift, and the drift study is not evidence of
anything yet. Whether the final pass should grade `near_start` instead is a
question the record cannot answer today; it becomes answerable at 100 paired
snapshots, and **it is an operator ruling when it does**, not a quiet switch.

**A read-out is cheap, which changes the economics.** Today a line that moves
requires nothing because the question is ours. Under this design the same
stored distribution can be read out at every snapshot it ever gets, at no
cost and with no new forecast — so the drift study gets better for free, and
the graded one stays the declared one.

### The line never posts

**Then the row is graded continuously**, by section 2's CRPS, and it is scored
rather than invisible.

**This is a strict improvement on today**, where an unpriced question is a
prediction nobody can grade. It is also the answer to a problem this project
already has and has recorded: every UFC bout it currently forecasts is
unpriced, and the entire 2026 sample scores nothing. A distributional UFC
market is out of scope here — `rounds` is a count with a fixed rung — but the
**mechanism** that makes an unpriced question gradeable is built in this work.

**The gradeable population changes when a line appears, and the record must
not pretend otherwise.** A row scored continuously and a row scored at a line
are in different families and are never pooled. If a question gets a line
late, it is graded at the line and its continuous score is kept beside it,
labelled — never averaged in.

### The read-out is confused for a forecast

The failure this design is most likely to produce, and it is a **social**
failure rather than a technical one: someone reads `readout_prob` as the
model's opinion, and wonders why it changes when the line moves.

**It changes because the question changed.** The forecast did not.

The mitigations are the ones this project already uses: the read-out lives on
the snapshot row and not on the prediction, so its position in the schema says
what it is; the card shows the model's own number beside the market's; and a
planting should assert that **the same stored distribution read out at two
different lines produces two different probabilities and one unchanged
forecast**. That is the law made structural.

### The spread is measured on the wrong population

`forecast_sd` is measured on completed games in the loaded seasons. **A model
whose factors change has a different residual spread**, and a spread measured
before a refit describes the old model.

Two guards, both in this project's existing idiom: the spread is **declared
and dated per (sport, market)** like every other measured constant, and it
carries the `factor_set_version` it was measured under. A distribution written
under one version and a spread measured under another is a mismatch a guard
can see and refuse by name.

### CFB ships with a known bias

**It should not ship at all until its expectation is fitted** (section 1).
Recorded here so that a Part 2 that ships all four sports at once is
recognisably wrong rather than plausibly complete.

---

## 7. The walk-forward plan for Part 2

> ### The clause
>
> **The change ships only if the distributional read-out is better calibrated
> than the current rung method, measured on identical games, walk-forward, and
> labelled sanity only.**
>
> **If it is not better, it does not ship**, and this document is the record
> of a hypothesis the evidence refused. That outcome is not a failure of the
> session; shipping a redesign that measured worse would be.

### What is compared

**Identical games, both methods, same fit window.** For every completed game
that carries a stored market line:

| | method A (today) | method B (proposed) |
|---|---|---|
| question | over our rung | over the market's line |
| probability | fitted logistic at the rung | `Φ((µ − line) / σ)` |
| trained on | seasons ≤ T | seasons ≤ T |
| tested on | season T+1 | season T+1 |

**Two sports:** NFL and NBA — the two whose totals measured +0.0016 and
+0.0010 and therefore the two the claim is about. **NFL has 2,761 finals with
a stored line; NBA has 13.** NBA's line coverage must be extended before the
comparison is possible, and if it cannot be, **the NBA arm is reported as not
run rather than quietly dropped.**

CFB is excluded until its expectation is fitted. MLB is excluded because its
totals belong on the count machinery, which is its own piece of work.

### What is measured

Both methods are scored on **their own questions**, because they are not the
same question — which is exactly why the comparison needs care:

1. **Brier, each method on its own question.** Reported side by side and
   **explicitly not** as a head-to-head: a lower Brier on an easier question
   is not a better model. It is context.
2. **Calibration, which is the decidable one.** Weighted mean |claimed −
   actual| across the buckets, and the bucket table beside it. **A method that
   says 70% and is right 70% of the time is calibrated whatever its Brier**,
   and calibration is comparable across questions in a way Brier is not.
3. **Edge over always-the-base-rate**, per method, per sport. Method A's is
   already known: +0.0016 NFL, +0.0010 NBA.
4. **Reach.** What share of questions clear 70% either way. Method A's is
   **zero by construction**; method B's is measured at 12.8% structurally and
   must be confirmed on out-of-sample rows.
5. **PIT uniformity for method B**, on the test season only. A read-out cannot
   be better calibrated than the distribution it is read from, so if the PIT
   is ∪-shaped the answer is already no.

### The decision rule, written before the numbers

**Ships if, on the test season, both hold:**

- **B's weighted calibration gap ≤ A's**, in both sports where the arm ran;
- **B's PIT is flat within its gate** — no decile more than 50% above or below
  the uniform expectation, at N ≥ 200.

**Does not ship if either fails.** No third condition gets added after the
numbers arrive, which is the point of writing the rule here.

**And a result that is neither** — B better calibrated in one sport and worse
in the other — **is an operator ruling, not a judgement call for the session
that runs it.** The tie-break is not written here because a tie-break written
by the person who wants the answer is not a tie-break.

### What gets built before the test, and what after

**Before:** the measurement harness only. It reads the record, computes both
methods on completed games, and writes nothing to `predictions`. It is a
`tools/` script, like `measure_margin_sd.py`.

**After, and only on a pass:** the schema columns, the read-out on the
snapshot, the deletions in section 5, the card, the PIT histogram, the CRPS
table.

**The order matters and is the whole reason for two sessions.** Building the
schema first would make the test a formality that nobody wants to fail.

---

## 8. What this document does not decide

- **Whether CFB's totals expectation gets a fitted slope and intercept.** It
  needs one (section 1) and that is a measurement, but changing which
  questions a sport asks is an operator ruling — the same one the CFB margin
  needed on 2026-09-03.
- **Whether `near_start` becomes the graded snapshot.** Answerable at 100
  paired snapshots; 15 today.
- **Whether MLB totals move to the count machinery.** Recommended here on the
  skew, and it is its own piece of work with its own checklist.
- **The tie-break if the walk-forward splits by sport.** Deliberately left to
  the operator, by section 7.

## 9. WHAT THE TEST SAID (Part 2, 2026-09-04)

Everything above this line is as it was written **before** the test. Nothing
in it has been edited to agree with the result, because a design amended after
its own experiment stops being a record of what was predicted.

### 9.1 The result

`tools/walkforward_distributional.py`, per sport as the operator ruled — LAW 6
makes each sport its own decision and sports are never averaged to reach a
verdict.

| arm | n | splits | rung gap | **read-out gap** | rung edge | **read-out edge** | read-out reach | PIT worst |
|---|---|---|---|---|---|---|---|---|
| NFL total | 768 | 2022/23/24 | 0.35 | **13.24** | +0.0011 | **−0.0281** | 12.4% | 0.29 flat |
| NFL spread | 813 | 2022/23/24 | 1.93 | **11.91** | +0.0036 | **−0.0164** | 7.8% | 0.30 flat |
| NBA total | 1,223 | 2024 | 3.98 | **9.60** | −0.0030 | **−0.0147** | 6.1% | 0.17 flat |
| NBA spread | 1,143 | 2024 | 2.57 | **12.39** | +0.0085 | **−0.0197** | 11.2% | 0.13 flat |

"Gap" is the weighted mean |claimed − actual| across the declared buckets, in
percentage points, read on the claimed side. **LABELLED SANITY ONLY** — a
retrospective comparison on completed games, not evidence of an edge.

**§7's decision rule, applied exactly as written.** B ships only if its
calibration gap is ≤ A's *and* its PIT is flat. **The PIT condition passed
everywhere. The calibration condition failed everywhere.** No third condition
was added after the numbers, and none was needed.

### 9.2 Why it failed — and it is not what §0 expected

**The read-out's error is monotone in its own confidence.** NFL totals:

| read-out claimed | n | actually happened |
|---|---|---|
| 54.8% | 420 | 48.8% |
| 64.4% | 253 | 47.8% |
| 73.8% | 81 | **38.3%** |
| 85.9% | 14 | **42.9%** |

**Above 70% the read-out is worse than a coin flip, and above 80% it is
reversed.** The same shape appears in all four arms.

**The cause, measured.** The mean absolute error of each number against the
result, on the same games:

| arm | our expectation | the market's line | market closer |
|---|---|---|---|
| NFL total | 11.23 | **10.11** | 57.4% |
| NFL spread | 10.45 | **9.74** | 58.9% |
| NBA total | 15.34 | **14.61** | 54.8% |
| NBA spread | 11.77 | **10.87** | 57.2% |

**The market forecasts better than we do.** So the gap between our number and
theirs is mostly *our error*, not our edge — and a read-out converts that gap
directly into confidence. The bigger the disagreement, the more of it is us
being wrong, which is exactly the monotone pattern above.

> **The lesson, stated so it cannot be misread: a distribution can be
> perfectly honest about its own error and still be badly calibrated at
> somebody else's number, because that number is not a random point. It is a
> better forecast.**
>
> §3 treated PIT flatness and calibration-at-the-line as two views of one
> honesty. **They are not.** PIT asks "is the spread right for the mean" —
> answered yes, everywhere. Calibration at the market's line asks "is the mean
> right *relative to theirs*" — answered no, everywhere. The design conflated
> them, and the test separated them.

### 9.3 What §0 got right, and why it did not save the design

The arithmetic in §0 stands: a rung asked at our own expectation confines
P(over) to 45.8%–54.2%, and the read-out spans 3.4%–93.8%. **Both are true.
Reach is not calibration.** The read-out reaches 70% on 12.4% of NFL totals
and is right on 38% of those.

**A question with almost nothing in it is still better than a question with
the wrong thing in it.** The rung method's calibration gap of 0.35 points on
768 games is the best number on this page. It measures nearly nothing and it
does not lie about it — which is the whole of what LAW 4 asks.

### 9.4 The suppression, still unexplained

§0's second claim — that the rung causes the `srs_diff` / `recent_form_diff`
suppression — is **untouched by this result.** The correlations it rests on
were measured directly and stand: those factors carry +0.26 and +0.24 against
the moneyline's label and −0.02 and +0.04 against the spread's, on the same
games, correlated at 0.70 with each other throughout.

**But the fix that was supposed to test it did not ship**, so the hypothesis
is where it was: a mechanism and a measurement, no proof. Removing the rung is
no longer the way to test it, because removing the rung makes the model worse.
**Whatever tests it next has to be something else.**

### 9.5 CFB never reached the walk-forward

The brief said *"CFB totals WAIT for a fitted slope — fit it first, dated,
then include CFB."* It was fitted, and the fit refused the market:

```
actual_total  =  47.31  +  0.109 x expectation      n=1,639   R^2 = 0.0093
```

**The expectation explains 0.93% of the variance in a college total.** The sum
of two points-per-game figures is very nearly no forecast at all — against
R² 0.095 for the NFL margin and 0.357 for the CFB one. Fitting it does reduce
the spread from 20.85 to 16.31, and what it reduces it to is *the league
average on every game in the country*.

**So there was nothing to distribute**, and CFB's total is recorded NOT RUN
for that reason rather than for line coverage. The slope and intercept are in
`tools/measure_forecast_spread.py`'s output and are deliberately **not**
declared as a live constant: adopting them would change which questions
college football asks, and §8 says that is an operator ruling.

### 9.6 What was built anyway

**Nothing that asks a question differently.** Every market is on the same rung
it was on before.

| built | why it survives a NO |
|---|---|
| `tools/walkforward_distributional.py` | the test itself, re-runnable when the model changes |
| `tools/measure_forecast_spread.py` | the eight spreads, and the CFB fit that refused it |
| `tools/backfill_lines.py` | NBA line coverage: **25 → 4,900 lined finals** |
| `questions.FORECAST_SPREAD` | five dated measurements with their N |
| `config.DISTRIBUTIONAL_VERDICTS` | the decision, with its evidence, where code can read it |
| `audit.check_distributional_verdicts` | makes the verdict binding in both directions |

**The NBA backfill outlives this session by a distance.** The doc said the NBA
arm might have to be reported as not run for want of lines; it now has 4,900
lined finals, and every future market comparison in that sport rests on them.

### 9.7 What is now known that was not

1. **The read-out is not a free improvement.** It was proposed as a
   deterministic re-reading of an existing forecast — no new model, no new
   risk. It is a new *claim*, and it can be wrong.
2. **We forecast totals and margins worse than the market, by 5–9%**, measured
   four ways. That number was not on the record before today.
3. **Our distributions are honest.** All four PITs flat is a real result about
   the model, and it is what makes `FORECAST_SPREAD` worth keeping.
4. **CFB's totals expectation does not work**, at R² 0.0093.
5. **Reach and calibration trade off**, and this project's laws already choose:
   LAW 4 exists to stop a number being shown that has not earned itself.

## 10. Operator's verdicts

**Strongest thing:**

**Weakest thing:**

**What to do next:**
