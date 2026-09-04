# Close-out — NBA moneyline (MARKET_ROSTER #1)

Brief: the overnight session, STEP 2. Governed by
`docs/NEW_MARKET_CHECKLIST.md`; selected by `docs/MARKET_ROSTER.md`.

---

## 1. The tick sheet

| # | Item | Evidence |
|---|---|---|
| 1 | `mean_vs_line` and volatility factors declared | **N/A, and stated rather than skipped** — §3 |
| 2 | `fit.constant` / `fit.dropped` checked and empty | **Both empty**, n=4,920 — §4 |
| 3 | Alias and identity round-trip measured | **No identity match exists to measure** — §3 |
| 4 | Cross-checks between related numbers | **Passed on 198 real games**, and the first version was wrong — §6 |
| 5 | Missing data explicit-absent; presence recorded | Per-factor presence 3,690–4,920 of 4,920 — §4 |
| 6 | Own category, own gate, never merged | Automatic from the declaration; asserted — §7 |
| 7 | VOID rules written before the first prediction | §5 |
| 8 | Resolution source verified; loader loud on empty | Final scores, 100% of 21,527 games — §5 |
| 9 | Inside the lead horizon; cadence stated | **The horizon refused the first slate** — §8 |
| 10 | Dated activation; backtest labelled; gate respected | §4, §9 |

## 2. Why this market, first

`MARKET_ROSTER.md` ranks it **20th of 21 on volume** and its own §4(b) explains
why it is built first anyway:

> The bottom four entries are the most reliable things on the list. NFL and NBA
> moneyline and total … are the only entries that need **no player identity
> match, no lineup, and no crosswalk**. They resolve from a final score that is
> present for **100% of 21,527 stored games**. Every prop above them depends on
> a name matching a name.

## 3. Two checklist items are N/A, and that is stated rather than skipped

**Item 1 (`mean_vs_line`, volatility).** These are prop instruments: they exist
because a prop is asked at a rung and the model needs to know how far the rung
sits from what it expects. **A moneyline has no rung.** It is the only question
in this project with nothing to choose, so there is no line to be a distance
from and no ladder to fall off. `nba_asked_distance` is therefore declared for
the spread and **not** for the moneyline — and a planting checks that, because
the moneyline's question, features and training set were each written next to
the spread's, which is exactly how a line would get copied across.

**Item 3 (alias round-trip).** There is no name to match. The question is about
two clubs already keyed by tricode in our own tables, and it resolves from the
game's score. This is the item the roster's ordering was built around.

## 4. The fit

```
n = 4,920   converged in 5 iterations
dropped: {}   constant: {}          <- checklist item 2
base rate (home wins): 0.5555
```

Standardised coefficients (coefficient × factor SD):

| factor | standardised | present |
|---|---|---|
| `nba_srs_diff` | **+0.6115** | 4,602 |
| `nba_net_rating_rolling` | +0.2281 | 4,841 |
| `nba_availability_index` | +0.1839 | 4,904 |
| `nba_rest_days_diff` | +0.1255 | 4,904 |
| `nba_b2b_either` | −0.0154 | 4,904 |
| `nba_home_court` | +0.0153 | 4,920 |
| `nba_travel_recent` | +0.0055 | 4,857 |
| `nba_pace_rolling` | +0.0028 | 3,690 |

**Eight factors, all measured, none constant, none dropped.** Presence is
recorded per factor and the two lowest are honest absences: `nba_pace_rolling`
needs enough games for a rolling pace, `nba_srs_diff` needs 150 league games
before an opponent adjustment means anything.

### 4.1 The suppression does NOT happen here, and that is worth recording

Session D found `nba_srs_diff` and `nba_net_rating_rolling` mutually
suppressing on the **spread** — both inflating, opposite signs, neither
coefficient readable alone. On the **moneyline** they behave normally:

| model | `nba_srs_diff` | `nba_net_rating_rolling` | Brier |
|---|---|---|---|
| both declared | **+0.6115** | **+0.2281** | .2128 |
| adjusted only | +0.7806 | — | .2136 |
| raw form only | — | +0.6628 | .2192 |

Same sign alone and together, and the adjusted factor **shrinks** when the raw
one joins rather than inflating. That is ordinary shared variance, not
suppression. `config.JOINTLY_READ_FACTORS` is keyed by `(sport, market)` and
names only `("nba", "spread")` — **which is now demonstrated to be the right
scope rather than merely the cautious one.**

## 5. Void rules, written before the first prediction

- **No score on a final game** → VOID. Already the NBA adapter's rule and it
  applies unchanged.
- **A final game with the scores level** → VOID, with the reason saying that
  the NBA plays overtime until somebody wins, so *the row is wrong rather than
  the game being drawn*, and a wrong row gets no outcome. **There is no draw
  branch, and that is a fact about basketball rather than an omission.**
- **A game not final** → not resolvable yet, never voided.

Resolution source: `games.home_score` / `games.away_score`, present for **100%
of 21,527 stored final games across four sports** — the figure `MARKET_ROSTER`
was built on.

## 6. Checklist item 4, and the first version of it was wrong

**What it checks now.** Writing the margin as M:

```
P(home wins)   = P(M > 0)
P(home covers) = P(M + rung > 0) = P(M > -rung)
```

A home club **giving** points covers only in games it also wins, so it cannot
be likelier to cover than to win. One **receiving** points wins only in games
it also covers, so it cannot be less likely. **There is no estimation in this**
— a model that breaks it is contradicting itself.

**Result: PASSED on 198 real games.** Reported by `gridiron train` whenever the
moneyline is fitted, so it runs on the record rather than on a fixture.

**The first version compared the moneyline to `expected_margin` and fired on 9
of 200 games.** Every one was two instruments legitimately disagreeing:
`expected_margin` is deliberately blind and rating-only — it exists to choose a
rung *before* the model runs — while the moneyline reads eight factors. **A
cross-check between numbers that are not comparable is a check that will be
silenced rather than believed**, so it was replaced rather than widened.

## 7. Its own category and its own gate

Declaring the market gives it both: `calibration.scorecard` loops
`config.SPORT_MARKETS`, so `nba / moneyline / statistical` is a category of its
own with its own hundred, and `assert_no_merged_categories` refuses anything
else. **No floor**: `config.PROPS_MIN_CLAIM` applies to props, and it should —
a moneyline slate offers one question per game, they are the whole slate, and
dropping the close ones would leave a record made only of blowouts, which is
the flattering selection LAW 4 exists to prevent. **Every game is asked.**

## 8. Timing, and the horizon refusing the first slate

The 2026 season opens **2026-10-20**, forty-six days out. `run_slate` refused
it:

> nba 2026 slate 1 starts in 46 days, beyond the 21-day forecast horizon.
> Nothing was written: a forecast made from a previous season's form is not the
> forecast this slate will get.

**That is checklist item 9 working, not a failure.** The market is built and
fitted; the first live slate becomes writable on **2026-09-29** and is written
by `predict:nba` if the scheduler is installed — which it is not, and that is
carried forward.

Cadence once it opens: roughly **11 games a night**, 47 in the first week. At
15 questions a slate the category reaches its hundred in **about seven days**.

## 9. Proved end to end, retrospectively

Because the horizon refuses a forward slate, the pipeline was proved on a
completed one in a backtest database, labelled as such:

```
written 110 (55 moneyline + 55 spread), skipped 0
resolved 110, voided 0, unresolvable 0
settled moneyline 55, right 41
rows carrying a line: 0
```

Spot-checked by hand: `HOU 123 @ WAS 118`, model side `lose`, outcome 1 —
correct.

## 10. Walk-forward sanity, LABELLED

Trained through 2023, tested on 2024–2025, 2,460 rows each:

```
Brier          0.2062
always-base-rate 0.2477      edge +0.0415
hit rate       67.85%        (base rate 56.18%)

50-60%   n=891  said 55.0%  hit 56.2%  gap +1.2
60-70%   n=733  said 64.9%  hit 66.3%  gap +1.4
70-80%   n=517  said 74.7%  hit 78.7%  gap +4.0
80-90%   n=281  said 84.0%  hit 84.7%  gap +0.7
90-100%  n= 38  said 91.2%  hit 97.4%  gap +6.2

weighted |gap| 1.88 points over 2,460 rows
```

**LABELLED SANITY ONLY.** The factor set was chosen knowing these seasons, so
this says the market is coherent and well-calibrated *on data the factors were
selected against*. It is not evidence of an edge and is not reported as one —
**the gate is a hundred settled forward predictions, and there are zero.**

Two things are worth saying about the shape. **Every bucket is
under-confident** — the model wins more than it claims — which is the safe
direction to be wrong in. And the weighted gap of 1.88 points compares well
with the spread's, which is the sibling market fitted from largely the same
factors.

## 11. Rulings taken in your absence

1. **Checklist items 1 and 3 marked N/A with reasons**, not ticked and not
   skipped.
2. **No confidence floor** on a game market — §7.
3. **The cross-check compares the two markets to each other**, not the model to
   the rung-chooser — §6.
4. **`nba_asked_distance` excluded** from the moneyline's factor set, and
   planted.
5. **`GAME_MARKETS` declared once** rather than widening eight decorators by
   hand, because editing eight and forgetting the ninth is how a factor set
   comes to differ from the rationale describing it.

## 12. Operator's verdicts

**Strongest thing:**

**Weakest thing:**

**What to do next:**
