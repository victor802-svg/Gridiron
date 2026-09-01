# Session close-out — calibration corrections (C1–C5)

Brief: `docs/briefs/2026-08-31-calibration.md` (saved first, per MENTOR §4a,
in `ee28e59`).

Commits: `3b03990` C1 · `68c20ef` C2 · `2d0e98f` C3 · `43854c6` C4 ·
`ef526d3` C5.

---

## 1. Close-out table

| phase | verdict | evidence |
|---|---|---|
| **C1** the correction engine | **DONE** | `3b03990`. Platt per category; `calibration_corrections` append-only and versioned; `check_correction_is_isolated` + 4 plantings; applied at write time, never retroactively. |
| **C2** activation, honestly | **DONE** | `68c20ef`. Time-ordered 80/20 holdout with a **measured** margin; `shown_claim` as the one door for the floor, tier, gap and sort; per-version forward grading; 4 plantings. |
| **C3** line drift | **DONE** | `2d0e98f`. `market_snapshots.kind`, near-start pass on the refresh task, gated report; `check_the_second_look_is_fresh` + planting. |
| **C4** the record speaks earned numbers | **DONE** | `43854c6`. Both numbers travel on cards, history and detail; earned-number sentence; corrections note on the tier table. Nothing visible changes while every category is raw — which is the requirement. |
| **C5** verification | **DONE** | `ef526d3`. Rehearsal on the real category and two synthetic ones; the render found a defect the suite missed. |

## 2. Deviations from the brief, stated up front

1. **The brief's "verify Brier improves" is a coin flip, so the gate got a
   measured margin.** A planting proved a *perfectly calibrated* category
   activated: with no real effect the corrected Brier lands either side of
   the raw one at random. Measured over 60 trials — null passes 23/60
   (38%), genuine miscalibration 45/60. `HOLDOUT_MIN_GAIN = 0.005` takes
   the null to 2/60 and keeps 35/60.
2. **"Corrections begin at 50 settled" was true of the fit and false of
   the card, so the wording changed.** At 50 settled the holdout is ten
   rows and cannot separate the two cases at all — 13/40 against 11/40.
   `HOLDOUT_MIN = 40` rows, measured, which means a correction is *fitted*
   at 50 and *applied* from about 200. The interface now says exactly
   that. **The brief's number is kept as the fitting bar; what changed is
   the claim made about it.**
3. **The brief's "MLB moneyline, 31 settled" is 25 in the record** —
   non-void statistical rows resolved before now. Reported, not
   reconciled; the gate refuses either way.
4. **C5's "synthetic category at n=60 proving the gate both passes and
   rejects" cannot be done at n=60**, for the reason in (2). The
   demonstration is at n=60 (refused, with the reason) and n=400
   (activated, rendered).

## 3. Bugs I introduced, and how each was caught

| bug | caught by |
|---|---|
| The near-start snapshot never re-read the market, and the fetch would have replayed the cache anyway — every drift pair read exactly zero movement | **by looking** at four numbers that were too equal. No test could have: the rows were real. |
| A corrected card drew its headline from the raw claim while its chip, bucket and sentence used the corrected one | **by looking** at the render, one phase after I wrote the comment predicting this exact failure |
| `rungs`/`correction` imports pulled `calibration` into every prediction closure | **a test** — LAW 1's closure scan, twice, within a minute each time |
| A migration in `db.py` named a market table | **a test** — same scan |
| `categories_in_the_record` enumerated with no time bound and no void exclusion | **a test** — my own isolation guard, before I had thought it through |
| The isolation guard's table regex carried a `\b` that became a literal backspace, so it matched nothing and passed everything | **by looking** at the compiled pattern after a suspiciously clean result |
| A planted-violation fixture violated the games CHECK constraint | the constraint |

Four of these were caught by looking, not by tests. That ratio is the
finding, not the individual bugs.

## 4. Vacuous passes found, and the class fix for each

1. **A guard that matched nothing.** `_SQL_TABLE`'s `\b` became `\x08` in
   transit — the third time this corruption has appeared in this project.
   It reported every module clean. *Class fix:* the pattern uses an
   explicit separator with the reason written beside it, and I now check a
   new scan's pattern against a known-positive string before trusting a
   clean result.
2. **A measurement of the cache.** The drift pass produced eight real-
   looking rows that were byte-for-byte replays of the open snapshot.
   *Class fix:* `check_the_second_look_is_fresh` asserts the near-start
   window is strictly inside the live cache window, with a planting that
   sets them equal. The eight rows were deleted.
3. **A gate that could not discriminate.** The 80/20 holdout at ten rows
   passed a calibrated category as often as a miscalibrated one. *Class
   fix:* both thresholds are now measured numbers with the trial table in
   the source, not chosen ones.
4. **665 green tests over a card whose four numbers disagreed.** Every
   number was individually correct, so nothing failed. *Class fix:* the
   renderer has one door for a card's probability and a test scans for any
   other reader.

## 5. What remains unverified

- **No correction has ever been applied to a real claim.** Every figure
  in C1–C4 is exercised by synthetic categories and the two real ones
  refuse. The engine is verified; its effect on this record is not.
- **The drift question is unanswered and barely begun.** Four pairs exist
  and none is a five-point disagreement, so the count is zero of fifty.
  The mechanism is verified for one run of one sport.
- **The holdout is a thin forward-*shaped* check, not proof**, and is
  labelled that everywhere. At 40 rows it is still 40 rows.
- **`HOLDOUT_MIN_GAIN` and `HOLDOUT_MIN` are measured on synthetic data**
  whose miscalibration is a clean multiplicative shrink. Real
  miscalibration may not have that shape.
- **The near-start pass has run against one sport on one evening.** Its
  behaviour across a full slate, and whether ten minutes is the right
  window, is unmeasured.

## 6. Operator's attention list

1. **The two thresholds are the decision worth reviewing.** 50 to fit and
   ~200 to apply is a bigger gap than the brief assumed, and it means no
   category here activates for months. The measurement supports it; the
   appetite is yours.
2. **Four defects this session were found by looking at output, one by a
   test.** Renders and printed numbers are doing more work than the suite
   on this kind of change.
3. **The drift read-date.** Nothing to look at until fifty pairs
   accumulate in a category; MLB moneyline is the only candidate.
4. **CFB (B1) is paused mid-probe**, read-only, with its findings and its
   unmeasured questions written down. It resumes whenever you say.

## 7. Operator's verdicts

**Strongest thing:**

**Weakest thing:**

**What to do next:**

## 8. FOLLOWUPS delta

Non-zero. Added:

- **2026-08-31 — THE THIRD FORECASTER, dated "after the gates fill."** The
  correction machinery is per (sport, market, forecaster) and the LLM
  forecaster has no settled rows at all, so its correction cannot be
  fitted, let alone graded. Revisit when any category reaches 200.
- **2026-08-31 — THE DRIFT QUESTION'S READ-DATE.** Fifty pairs in one
  category. At the current rate of MLB moneyline that is months away;
  check the count before reading anything into it, and note that the
  gate reports the count and nothing else by design.
- **2026-08-31 — A `\b` in a generated regex has now corrupted three
  guards.** Always check a new scan's pattern against a known-positive
  string before believing a clean result.
- **2026-08-31 — Verify a new measurement against a source that CAN
  change.** The drift pass measured the HTTP cache. Any future
  "second reading" of anything needs the same check: is the second read
  capable of differing from the first?
- Carried forward: the dead-but-named sweep (ruling 2); a run that writes
  nothing commits nothing; what else in `calibration` is not about
  calibration; the inert-CSS-property scan; NFL prop rows with NULL
  `prop_type`; NFL team names at 30 of 34.
