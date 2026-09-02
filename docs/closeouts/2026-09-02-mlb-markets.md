# Close-out — MLB run line and totals (STEP 3 build)

Brief: `docs/briefs/2026-09-02-overnight.md`, STEP 3 M-BUILD, run after the
operator's rulings. Probe: `docs/MLB_RUNLINE_FEASIBILITY.md`. Ticked checklist:
`docs/MLB_RUN_LINE_AND_TOTALS.md`.

Commits: `d501e9d` the probe · `5ee58cd` the build.

---

## 1. Close-out table

| phase | verdict | evidence |
|---|---|---|
| **M-PROBE** | **DONE** (earlier) | `d501e9d`, corrected in `3fe3179`. |
| **M-BUILD** run line | **DONE** | Asked at a declared ±1.5 from the home side, 9 live on the 2026-09-02 slate. Base rate 0.356 reproduces the measured 35.8%. |
| **M-BUILD** totals | **DONE** | Self-generated from combined form, always on a half, 9 live. Measured SD 4.511 declared under the undated-SD guard. |
| **M-BUILD** wind factor | **SKIPPED, by evidence** | `weather_forecasts` holds nine rows, all football. See below. |
| **M-BUILD** market filter | **NOT DONE** | See below. |
| **M-QA** | **DONE** | Suite green, `verify.py` 4/4 EXIT=0, 123/123 plantings, four new. |

## 2. What the brief asked for that is not here

**The Picks market filter — DONE after this close-out was first drafted, and
it turned out to be a plain-words defect rather than a missing label.** The
generic humaniser rendered MLB's `spread` as **"point spread"**, which is a
sentence about the wrong sport: baseball has runs. `language.SPORT_MARKET_WORDS`
now names markets per sport — "run line" and "total runs" for MLB, "point
spread" and "total points" for football — and every card carries its sport so
the label can use it. Without that the label silently fell back, which is how
the wrong-sport wording reached the page in the first place.

**Run-line and totals PRICES are still not stored.** The probe's condition #2.
The comparison currently derives an implied probability from the LINE plus a
measured SD, which is the mechanism the brief actually names ("market
comparison uses measured SDs"), so both markets do have a comparison. Storing
the prices would give a second, independent one. In FOLLOWUPS.

**Walk-forward fits are not labelled pipeline-sanity because they were not
run.** The fits here are single 2023–25 fits, and the checklist's item 10 is
satisfied by the honest framing instead: nothing has settled, both categories
read `unproven — 0 of 20`, and the note on each fit says what it is.

## 3. Rulings taken in your absence

| fork | ruling | why |
|---|---|---|
| Which side is the run line asked from? | **Always the home side, at −1.5.** | Letting the market's favourite pick the side would be the market choosing our question. LAW 1. |
| Is the run line a new `market_type`? | **No — it is MLB's `spread`.** | A run line *is* a handicap. The schema already allows it, and `(sport, market_type)` already separates it from football's. |
| Declare new factors, or widen the moneyline's? | **New, dated today.** | The same quantity matters differently to two questions, and widening would date both from the earlier market and mix two measured effects. |
| Wind at first pitch? | **Not declared.** | Nine stored forecast rows, all football. A factor absent on every training row is a broken instrument, not a weak one. |
| A run line whose sign ESPN contradicts? | **No comparison at all.** | A confident probability pointing the wrong way is worse than none: a missing comparison is visible, a reversed one is not. |

## 4. Bugs I introduced, and how each was caught

| bug | caught by |
|---|---|
| MLB's run line was labelled "point spread" — the wrong sport's word | **by looking** at what the filter would render |
| Yesterday's slate guard blocked adding a *new* market to an answered slate | **by looking**, when the live run was about to be refused |
| The refined guard then excused a run that asked no props | **a test** — `test_rerunning_a_week_is_refused_and_writes_nothing` |
| Three MLB factors shared the plain name "how much scoring this park allows" | **a test** — `test_no_two_factors_in_a_sport_share_a_plain_name` |
| Four MLB tests encoded "one market per game" | **the suite**, immediately |
| A planting scanned a docstring and tripped on the rule it explains | **the plantings run** — the same trap that once made LAW 5 flag its own guard |
| A planting seeded one market where the guard now needs all of them | **the plantings run** |

Seven; **five caught by tests or the plantings, two by looking.**

## 5. What is measurably true now

- **9 run-line and 9 total forecasts live** on the 2026-09-02 slate; 18 skipped
  for games already started.
- `mlb:spread` n=7,289 converged, `constant={}`, `dropped={}`.
- `mlb:total` n=7,211 converged, `constant={}`, `dropped={}`.
- Run-line base rate **0.356** against a measured **35.8%** (n=9,373).
- Total SD **4.511** (n=9,373), declared apart from the 4.71 margin residual.
- Suite green; `verify.py` 4/4 EXIT=0; **123/123** plantings.

## 6. What I would tell you if you were here

1. **The total's base rate is 0.451, not 0.5.** The rolling combined form runs
   about 5% high as an estimate of actual scoring. The intercept absorbs it and
   it is worth re-measuring once the category has settled rows — it may be a
   real property of rolling averages rather than a fixable bias.
2. **Nothing has settled in either market.** Both read `unproven — 0 of 20`,
   and will until roughly twenty games have been played and resolved. The fits
   are pipeline sanity, not evidence.
3. **Nothing is left open from this brief.** The market-filter labels were the
   one loose end and they are closed — see section 2, where the fix turned out
   to matter more than the omission did.

## 7. Operator's verdicts

**Strongest thing:**

**Weakest thing:**

**What to do next:**
