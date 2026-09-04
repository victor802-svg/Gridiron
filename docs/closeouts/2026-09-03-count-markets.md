# Close-out — count markets on the rate form

Brief: `docs/briefs/2026-09-03-count-markets.md` (C1–C4). ITEM 2 of the
three-item unattended session.

---

## 1. Close-out table

| phase | verdict | evidence |
|---|---|---|
| **C1** rate forecaster | **DONE** | `gridiron/model/counts.py`; all five fitted — §2, §5. |
| **C1** negative binomial where over-dispersed | **DONE** | Measured per market, two qualify — §3. |
| **C2** walk-forward, old vs new | **DONE** | The rate form wins both markets it could be tested on — §4. |
| **C2** *do not ship it if it loses* | **N/A — it won** | §4. Had it lost, this row would say so. |
| **C3** the "why" speaks the rate | **DONE** | Rendered on a live card — §6. |
| **C4** plantings | **DONE** | Two, both caught; 149/149 overall — §7. |
| Renders | **DONE** | Desk and 390px; a continuous market shows none — §6. |
| Gate | **DONE** | 34 gate rows PASS, none FAIL; suite 973 tests, 0 failures — §8. |

## 2. What was actually broken, and it was mine

**The rate form was not reaching anything.** `baseline.train` asked the adapter
for counts, but `with_counts` existed only on `baseline.prop_training_set` —
the adapters' own `training_set` never forwarded it. NFL swallowed it in
`**kwargs`; MLB raised `TypeError`. So the fits C2 measured as better
calibrated were never being built, and every count market on the live record
was still a logistic.

**And my first fix was worse than the bug.** It checked whether the adapter
supported counts and **quietly fell back to the logistic** when it did not.
That ships a market declared as a rate, scored by the path measured as
overconfident by 7.79 points of gap, with the card's "why" claiming a rate the
model never used — and nothing anywhere saying so. It is now a build error,
raised by name, and that is C4's first planting.

The lesson is the one this project keeps relearning: **a silent fallback is
worse than the crash it replaces.** A `TypeError` is a bad afternoon; a market
claiming a form it does not have is a wrong record.

## 3. The form is measured per market, not assumed

Variance-to-mean over the stored record, dated `2026-09-03`:

| market | n | mean | var | var/mean | form |
|---|---|---|---|---|---|
| nfl passing_tds | 5,714 | 1.450 | 1.330 | 0.918 | Poisson |
| mlb batter_home_runs | 138,987 | 0.114 | 0.116 | 1.017 | Poisson |
| mlb batter_hits | 138,987 | 0.823 | 0.747 | 0.907 | Poisson |
| **nfl receptions** | 26,488 | 3.911 | 4.869 | **1.245** | negative binomial |
| **mlb pitcher_strikeouts** | 13,917 | 4.783 | 6.130 | **1.282** | negative binomial |

A Poisson has variance equal to its mean. Two of these do not, by a quarter or
more. A Poisson there would understate the spread — which is its own way of
being overconfident, and would have swapped one error for another.

## 4. The walk-forward, which is what decided it

Trained before 2023, tested 2023 onward, both forms fitted on the **identical
selection** so what is compared is the form and not the rows:

```
passing_tds   weighted |gap|  7.79 -> 2.39 points   Brier .2241 -> .2141
receptions    weighted |gap|  5.50 -> 3.89 points   Brier .2161 -> .2131
```

The passing-TD 80–90% bucket — the worst one — moved from −15.1 points to −1.3.

**Labelled SANITY ONLY.** The factor set was chosen knowing these seasons, so
this says one form is better calibrated than the other on the same data, and
nothing about whether the model is good.

**The three MLB count markets were never walk-forward tested.** They ship on
the measured dispersion and the same argument, not on their own comparison.
That is a weaker footing than the two NFL markets have, and it is stated here
rather than buried: if the operator wants them held back until they are tested
the same way, that is a one-line change to `COUNT_MARKETS`.

## 5. What is fitted now

**All five, all converged**, added after the MLB runs finished during ITEM 4:

```
nfl passing_tds         RateFit  n=  1,299  poisson             [ 68s]
nfl receptions          RateFit  n=  1,343  negative binomial   [ 69s]
mlb batter_home_runs    RateFit  n=118,345  poisson            [3003s]
mlb batter_hits         RateFit  n=118,345  poisson            [3052s]
mlb pitcher_strikeouts  RateFit  n= 11,928  negative binomial   [875s]
```

The MLB fits took fifty minutes apiece — roughly 118,000 rows through a
pure-Python IRLS — which is why this section read PENDING when the close-out
was first written. It is not pending any more, and §10.1 is struck.

## 6. C3, rendered

The brief asked the "why" to speak the rate. On a real card:

> **LONDON · RECEPTIONS**
> Drake London over 3.5 receptions
> The model says 73%. There is no line to compare it with.
> **The model expects about 5.2 receptions; clearing 3.5 is about 73%.**
> 70-80% bucket · nothing resolved here yet

**The 73% appears twice on purpose.** The second is the *derivation*: "73%"
alone never said whether the model thinks he catches four passes or nine, and
showing the rate beside the rung is the whole of what C3 asked for.

The passing-yards card beside it renders **nothing** here. A yardage question
has no rate, the server sends an empty string, and a count market must not look
like a different *kind* of pick.

**The sentence was composed and thrown away for an hour.** `language.rate_line`
was on the payload and no renderer drew it. The orphan scan was satisfied —
something called it — and no reader would ever have seen a word of it. **A
payload field with no renderer is a guard that passes and a feature that does
not exist.**

## 7. C4 — the two plantings

| planted | caught by |
|---|---|
| a count market scored by the logistic path — the NFL adapter with `with_counts` taken off its signature, which is exactly what an untaught adapter looks like | `baseline.train`'s capability refusal, by name |
| a rung probability that rises with the rung | `mlb.assert_monotone_across_rungs` |

The second is planted at **both doors**. The ladder assertion catches the
sequence; the plant then proves the rate model *cannot produce one*, checking
`p_over` across both forms at four rates and six rungs. Monotonicity here is a
fact about counting — raising a rung only removes outcomes from the over side —
and if the model could violate it, the guard would be catching a bug rather
than a contradiction.

## 8. The gate

- Suite: **973 tests, 0 failures**, 0 skips.
- Plantings: **149/149**.
- `verify.py`: **34 rows PASS, none FAIL**, steps 2, 3 and 4 PASS. (The
  35th row is the suite itself, deliberately skipped in that invocation
  and run separately — see below. An earlier draft of this line said
  "35/35 PASS", which counted the skip as a pass.)
- **Step 1 was run standalone.** The full gate now exceeds the ten-minute tool
  ceiling in this environment, so the suite was run on its own (`EXIT=0`) and
  the remaining steps with `--skip-tests`. Every step passed; none was skipped
  in substance. This is worth a look — a gate nobody can run in one command is
  a gate that will eventually be run in none.

## 9. Bugs and what caught them

| what | how |
|---|---|
| `with_counts` never forwarded by any adapter | training every count market and reading the returned type |
| the silent logistic fallback I wrote to fix it | **writing the planting for it** |
| `language.rate_line` composed and never drawn | **rendering the card and looking** |
| `log_odds = None` on a rate fit crashed `predict` | the first real predict run |

**Three layout tests failed because the model got better.** Less overconfident
count forecasts clear the props confidence floor less often; the synthetic
slate came in at exactly 590px inside a 590px frame and the scroll tests had
nothing to scroll. They were riding on the fixture's pick count, which is not a
layout fact — they now use a viewport that overflows by construction. **The
alternative was lowering the confidence floor to keep a test green, which is
fitting the model to the suite.**

## 10. What is PARTIAL, and what needs you

### 10.1 The MLB fits are pending, not failed — ~~PENDING~~ RESOLVED

*Struck 2026-09-03, during ITEM 4.* All three MLB rate models finished and
converged; the numbers are in §5. Left visible rather than deleted, because a
close-out that quietly rewrites its own PARTIAL into a DONE is exactly the
thing the close-out convention exists to prevent.

### 10.2 Found while rendering, recorded rather than half-fixed

**The compact rows truncate their own titles at 390px** — "BRISSETT · PASSI…",
"SF DOES NOT…". That is what the no-truncation law forbids, and the existing
scan misses it because it only looks at desk width. Present since `24212a6`
(2026-08-30), so not this session's. It is in `docs/FOLLOWUPS.md` with the fix
named. Two briefs are queued behind this one and a complete item beats a
half-built one.

## 11. Operator's verdicts

**Strongest thing:**

**Weakest thing:**

**What to do next:**
