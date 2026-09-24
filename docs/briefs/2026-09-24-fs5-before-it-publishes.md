# Brief — fs5 before it publishes (2026-09-24)

Saved before execution, as the standing contract requires. The operator's text
is unedited.

---

Before the 15:00Z final pass publishes anything from fits 91–94:

1. Precipitation: report, per training season, how many rows had weather read versus filled. If missing weather became zero, that breaks absent-not-zero. Fix it as class (a): no fill value, and for seasons without weather the factor either drops out or the training set starts at the first cached season. Say which, then retrain. Planting: a training row with no weather can't carry a precipitation value.

2. Gate each fit on out-of-sample: fit on seasons through 2024, score 2025, and put log loss and Brier next to the last trained set on the same holdout. Also report the coefficient table and each factor's share of the prediction. A fit that's worse than the last trained set on holdout doesn't ship. Revert that market to the last trained set, dated, per the 23 September ruling.

3. If the 15:00Z pass would run before 1 and 2 are done, hold NFL and NCAAF spread and moneyline for today and say so on the day strip. Missing a day of forecasts costs nothing. A day of forecasts from an unsound fit costs the clean window.

Item 1: commit when the gate is green. Items 3 onward stay in order.

---

## How this brief is read

**This is GRIDIRON_REPAIR item 2, widened.** Fits 91–94 were written to the
live record at 05:16–05:17Z on 24 September. The released code publishes from
whatever fit is newest, so the next `final:nfl` and `final:cfb` passes (15:00Z)
would forecast from them.

**The hold ships first, on its own commit.** It is the one part with a clock
on it, and it is small. The hold is a dated, declared list of held markets:
a held market is not forecast, the run says so, and the day strip carries a
line saying why. It is lifted by the commit that ships a fit which passed its
holdout, or by the revert.

**"The last trained set"** is, per market: NFL spread fs3 (fit 88), NFL
moneyline fs2 (fit 71), NCAAF spread fs3 (fit 44), NCAAF moneyline fs2
(fit 35). Those fits include 2025, so they cannot be scored on it. The
comparison refits both sets through 2024 on a scratch copy of the record and
scores both on 2025. Nothing in the comparison writes to the live record.
