# Close-out — STEP 4: down the roster

Brief: the overnight session, STEP 4 — "continue down MARKET_ROSTER.md in its
order (MLB batter strikeouts, NFL moneyline, NFL total, then the rest), one
market per close-out, each by the checklist".

Three markets built. **The most valuable output of this step is not a market —
it is two corrections to the roster itself**, §5 and §6.

---

## 1. What was built

| roster # | market | verdict | edge (walk-forward) |
|---|---|---|---|
| **#3** | MLB batter strikeouts | **DONE** | §2 |
| **#18** | NFL moneyline | **DONE** | **+0.0215** |
| **#19** | NFL total | **DONE** | **+0.0016** |

Nothing was DECLINED. **Nothing was skipped for volume either, and §5 explains
why the volume question turned out to be the wrong one.**

## 2. MLB batter strikeouts (#3)

The roster called it "the best-balanced prop measured". Re-measured here over
**125,298 stored batter-games**:

```
mean 0.889   variance 0.754   ratio 0.848   -> POISSON, under-dispersed
over 0.5: 61.7%      over 1.5: 22.2%      over 2.5: 4.6%
```

**A count market, so it goes on Session C's rate form.** Under-dispersed, so a
Poisson is the honest form and a negative binomial would claim a spread the
data does not have.

**Two rungs, 0.5 and 1.5**, exactly as `batter_hits` has. **2.5 is refused**:
4.6% is the one-sidedness the roster's own §4(a) disqualified triples for at
1.3%. Planted.

Fitted: **`RateFit`, n=118,451, converged, nothing dropped or constant.**

Eight factors, the shared batting vocabulary. `mlb_batter_opposing_k_rate` is
widened to it and is the most obviously relevant input on the board — **and its
sign reads the other way round.** The value is unchanged; the coefficient
flips, because a high-strikeout arm is bad news for a hit and the direct cause
of a strikeout. Each market is fitted separately, so this needs no second
factor and no re-signing: **what a shared instrument means is decided by the
fit, not by the name.**

## 3. NFL moneyline (#18)

```
n=2,629  converged  dropped {} constant {}   base rate 0.5466

srs_diff          +0.4103     divisional         -0.0403
recent_form_diff  +0.2037     rest_diff          +0.0386
injury_out_diff   +0.1034     timezone_shift     -0.0200
qb_out_diff       +0.1029     short_week_either  +0.0160
travel_kmiles     -0.0810     neutral_site       +0.0010
```

Walk-forward, trained through 2022, **LABELLED SANITY ONLY**: Brier **.2267**
against **.2482** for always-the-base-rate — **edge +0.0215** — hit rate
**62.7%**, weighted gap 2.48 points over 813 rows.

**The suppression is spread-specific in two sports now.** Session D found
`srs_diff` and `recent_form_diff` mutually suppressing on the NFL spread — both
inflating, opposite signs. On the NFL moneyline they are **+0.4103 and
+0.2037, same sign**, exactly as the NBA pair behaved.
`config.JOINTLY_READ_FACTORS` names only the two spreads, and that scope is now
demonstrated twice rather than assumed once.

**A drawn game voids**, and unlike basketball it is not a bad row: **10 of
2,761 stored NFL finals ended level (0.36%)** — SEA 6-6 ARI, PIT 21-21 CLE, and
eight more. The training set **drops** them and resolution **voids** them, so
the same fact is treated the same way at both ends. The NBA rule is the
opposite one for the opposite reason, and both are stated where the decision is
made.

**What is deliberately not on it**, recorded because an absence nobody argued
for looks like one nobody noticed: `asked_distance` (no rung), and `pace_sum`,
`wind`, `cold`, `precipitation` — those are about *how much* scoring happens,
not *which side* does it.

## 4. NFL total (#19) — built to test a claim

```
n=2,478  converged  base rate (over) 0.4831
dropped {}   constant {'precipitation': 711}

nfl_total_asked_distance  -0.1112     nfl_injury_out_sum   -0.0274
wind                      -0.1028     nfl_total_volatility +0.0099
cold                      +0.0915
pace_sum                  -0.0821
```

**THE CLAIM HELD.**

| market | edge | hit rate |
|---|---|---|
| NBA total | +0.0010 | 53.6% |
| NFL total | +0.0016 | 53.7% |

Two sports, two ladders, two factor sets, the same answer. **A total asked at
one's own rung is a coin flip by construction** — books set totals to be coin
flips, we set ours the same way because LAW 1 forbids us seeing theirs, and the
value in a totals market is disagreeing with somebody else's number. After the
NBA that was a hypothesis; it is now a property of the construction.

**The weather earned its place here and nowhere else.** `wind` at −0.1028 and
`cold` at +0.0915 are the second and third strongest factors — more than the
injury sum. Wind lowering a total is meteorologically plain, and on the spread
those factors were noise because they move both sides. **That is the
sums-not-differences rule paying for itself.**

`precipitation` came back **constant** across its 711 rows and is reported
rather than fitted — checklist item 2 working. A constant factor is a broken
instrument, not a weak one.

## 5. CORRECTION 1: the roster's volume column is unreachable

**§3's table counts qualifying subjects. It does not count questions this
project asks.** Two declared limits sit between the two numbers:

- **`MLB_PROPS_PER_DAY` = 25**, filled by round-robin, one question per subject
  per day. **A new prop market does not add questions; it takes a share of the
  same 25.** Adding batter strikeouts moved the slate from 7/6/6/6 to
  5/5/5/5/5.
- **`PROPS_MIN_CLAIM` = 0.70.** A question the model is not 70% sure of is not
  asked.

**Measured on the record itself**, over the five days it has been running live:
**50 MLB prop predictions written, 10.0 a day, 86% settled** — and **two of the
four declared markets have written nothing at all**, because they do not clear
the floor.

So "**batter RBI · 270 per slate · 0.4 slates to gate · ~0 days**" means *270
subjects would qualify*, not *a hundred settled predictions within a day*. At
the realised rate one MLB prop market reaches its hundred in **roughly a
month**.

`MARKET_ROSTER.md` now carries this at the head of §3 and in full in its own
§6. **The build order is unchanged** — it comes from §4, which ranks on balance
and on what needs no identity match.

**The brief's question, answered directly:** batter strikeouts gets **5 slots a
day**. From 2026-09-04 to the record's last MLB date of 2026-09-27 that is
**23 days × 5 = 115 questions**, before the floor and voids. **It is marginal
against a 100-settled gate and I will not promise it clears.** Nothing was
skipped on that basis, because the roster's own figures say it clears easily —
the figures are what were wrong.

## 6. CORRECTION 2: a declaration and a hardcoded list disagreed, three times

Three separate places held their own copy of "the markets":

1. **`SPORT_PROP_MARKETS` is a second tuple.** Adding `batter_strikeouts` to
   `SPORT_MARKETS` left the day's prop selection walking the old list, so the
   market had a category, a gate, a ladder and a fitted model and **never got a
   question**. Nothing fails when this happens; the only symptom is a scorecard
   row that stays at zero, which looks exactly like a market nobody has settled
   yet.
2. **The MLB adapter's batting loop listed its three markets by hand.** Same
   failure, one layer down. It now reads the declared list.
3. **Four tests asserted remembered market counts.** They now read
   `config.SPORT_MARKETS`, so the next market off the roster does not need them
   edited.

A planting checks every declared prop market has words, a ladder, and a place
in the round-robin.

## 7. And declaring a market silently disabled the rerun refusal

`already_answered` decides "answered once" by comparing what a run **would**
ask against what has rows. **A market that is declared but has no fitted model
is skipped by `predict` every time** — so counting it as a gap means the slate
is never "already answered", the refusal never fires, **and a rerun writes a
second set of forecasts of the same questions.**

The guarantee stopped holding in the direction that **duplicates the record**,
the moment the NFL moneyline was declared. The only sign was one test going
red. It now ignores unfitted markets — the same reasoning the `include_props`
line beside it already used — and a planting checks it against the real record.

## 8. The gate

- Suite **966 tests, 0 failures**. Plantings **168/168** — six new in this step.
- `verify.py` **35 rows PASS, none FAIL**.
- Every market proved end to end on a completed slate in a labelled backtest
  database, with a hand-checked resolution.

**One flaky test observed**, recorded rather than lost:
`test_the_tier_table.py::test_the_table_numbers_equal_the_chip_numbers_to_the_decimal`
failed once in a full run and passed in isolation and on two subsequent full
runs. Not diagnosed. It is a shared-fixture ordering effect rather than a
result of this step's changes, but it is real and it should be chased.

## 9. Rulings taken in your absence

1. **Nothing declined.** No market this step reached is one-sided, thin on
   resolution, or low-volume by the criteria the brief names.
2. **NFL total built despite the NBA's result**, because a finding from one
   sport is a hypothesis and testing it cost an hour.
3. **`batter_strikeouts` at two rungs, not three** — 2.5 refused at 4.6%.
4. **Weather factors widened to the totals markets** and left off the
   moneylines.
5. **The roster corrected rather than the build order changed.**

## 10. Operator's verdicts

**Strongest thing:**

**Weakest thing:**

**What to do next:**
