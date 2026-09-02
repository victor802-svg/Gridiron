# MLB run line and totals — the build

Built **2026-09-02** against `docs/MLB_RUNLINE_FEASIBILITY.md`, which measured
what the market carries before anything here was written.

Governed by `docs/NEW_MARKET_CHECKLIST.md`, item by item. The tick sheet is at
the foot of this file.

---

## What was built

**THE RUN LINE** — "does the home side win by two runs or more", asked at
`-1.5` from the home team, on every game, every slate.

The rung is a declared constant (`questions.MLB_RUN_LINE`), dated, measured
from history: every MLB run line ESPN carries is ±1.5, 71 of 71 in the probe.
So the question is asked at exactly the rung the market asks at **without
consulting the market to find it**. Which club the market makes the favourite
is never read at prediction time — that would be the market choosing our
question, and LAW 1 forbids it. The market's own side is read afterwards, when
the comparison is drawn.

**THE TOTAL** — "do these two produce more than N runs between them", where N
is **ours**: the two sides' combined runs per game, rounded down to a half.

`questions.mlb_total_asked` takes two scoring rates and nothing else. It cannot
reach a market module, and a test asserts both its signature and that its body
names none. The half is not decoration: the probe found **39 of 71** published
MLB totals are whole numbers, which can push, and a pushed question has no
answer to score.

## The numbers this rests on

| quantity | value | n | measured |
|---|---|---|---|
| total-runs SD | **4.511** | 9,373 | 2026-09-02 |
| margin residual SD (market comparison) | 4.71 | 2,110 | 2026-08-29 |
| home wins by 2+ | 35.8% | 9,373 | 2026-09-02 |
| one-run games | 28.0% | 9,373 | 2026-09-02 |

**The two SDs are different quantities and are declared apart.** 4.511 is the
spread of the total; 4.71 is a residual against the run line. Confusing them
produced a false discrepancy in the first draft of the probe, which is why
they now sit in different tables with different names and different dates.

## What the fits found

```
mlb:spread  n=7,289  converged  intercept -0.4106  base rate 0.356
mlb:total   n=7,211  converged  intercept +2.6064  base rate 0.451
```

**The run line's base rate reproduces the measured one exactly** — 0.356
against 35.8% over 9,373 games. That is checklist item 4 and it is the
strongest evidence here that the question is being asked and graded the way it
is described.

**The total's base rate is 0.451, not 0.5**, and that is a finding rather than
a bug: asking at the combined rolling form rounded down still goes over less
than half the time, so the rolling form runs about 5% high as an estimate of
actual game scoring. The fit's intercept absorbs it. Worth revisiting when
there is a settled record to check it against.

## Void rules, written before the first prediction

Recorded in `gridiron/model/questions.py` before any run line or total existed.
Deciding after seeing results which non-answers count is choosing which losses
to keep.

| case | outcome |
|---|---|
| game never finished, 4+ days after its date | **VOID** |
| game shortened before regulation but official | **settles on the league's ruling** |
| game suspended and completed later | **settles on the final score** |
| game marked final with no score recorded | **VOID**, reason stated |
| game not played yet | *unresolvable*, stays open |

The shortened-game rule is the one that could reasonably have gone the other
way. It goes this way because **the league's own answer is the answer**:
inventing a second standard would mean the record disagreed with the sport.

## What was NOT built, and why

**Wind at first pitch is not a declared factor.** The brief asks for it via the
existing Open-Meteo path. That path exists, but `weather_forecasts` holds
**nine rows, all football** — there is no stored history for a fit to see, so
the factor would be absent on essentially every training row. Declaring it
would produce exactly the broken instrument the constant-factor check and the
missing-data rule exist to catch. In FOLLOWUPS with this reason.

**Today's snapshots carry no market comparison.** Snapshots are taken once, at
prediction time, and are append-only. The 18 written this afternoon predate the
declaration of MLB's total SD by minutes, so their `implied_prob` is NULL. The
mechanism is verified working on real priced games (below); the next slate gets
it.

**A contradicted run-line sign yields no comparison at all.** Three stored rows
carry a direction ESPN's own flag and its own price disagree about. Reading one
would produce a confident probability pointing the wrong way on a coin-flip
game — worse than no comparison, because a missing one is visible and a
reversed one is not.

## Live proof

Both markets are live on the 2026-09-02 slate: **9 run-line and 9 total
forecasts written**, 18 questions skipped for games that had already started
(a slate that has begun is never forecast late).

The comparison, verified on real priced games:

```
TOR @ CLE   market total 8.0, run line +1.5 (espn-flag)
              -> P(over 8.5) = 0.456   P(home wins by 2+) = 0.500
MIA @ KC    market total 9.0, run line -1.5 (espn-flag)
              -> P(over 8.5) = 0.544   P(home wins by 2+) = 0.262
MIL @ CHC   market total 8.0, run line -1.5 (CONTRADICTED)
              -> no run-line comparison is drawn
```

---

## The tick sheet

| # | Item | Evidence |
|---|---|---|
| 1 | `mean_vs_line` and volatility factors declared | **spread:** `mlb_runline_volatility` (combined run environment) is the spread instrument; the rung is fixed so there is no asked-line factor to declare — one would be constant. **total:** `mlb_total_vs_line` (the rounding residual) and `mlb_total_volatility`. |
| 2 | `fit.constant` / `fit.dropped` checked and empty | Both fits: `constant={}`, `dropped={}`, `converged=True`. |
| 3 | Alias round-trip measured against both feeds | No new identity: subjects are team tricodes and a matchup string, already round-tripped by the moneyline. No player crosswalk is involved. |
| 4 | Cross-checks between related numbers | Run-line base rate **0.356** against the independently measured **35.8%**. Total base rate 0.451, reported as a finding. |
| 5 | Missing data explicit-absent; presence recorded | `mlb_total_asked` returns None on an absent scoring rate and the question is not asked; every factor returns None rather than a default; `presence` is recorded in both fit payloads. |
| 6 | Own category, own gate, never merged | `spread` and `total` appear as their own categories in `scorecard()`, each with its own 20/100 gates. `assert_no_merged_categories` runs inside it. |
| 7 | VOID rules written before the first prediction | In `questions.py` above the instruments, and in the table above. |
| 8 | Resolution source verified; loader loud on empty | `games.home_score` / `away_score`, the same source the moneyline settles on. A final game with no score raises `Void` with its reason; a level final raises `Void`. |
| 9 | Inside the lead horizon; cadence stated | Same `predict:mlb` task, daily at 11:00 local, well inside `MAX_FORECAST_LEAD_DAYS`. No new cadence. |
| 10 | Dated activation; backtest labelled; gate respected | Factors dated `2026-09-02`; fits noted "STEP 3: the run line and the total, declared 2026-09-02"; the 2023–25 fit is a **pipeline sanity fit, not evidence of an edge** — nothing has settled, both categories read `unproven — 0 of 20`. |
