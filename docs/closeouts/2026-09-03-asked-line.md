# Close-out — the asked line, redeclared as a distance

Brief: `docs/briefs/2026-09-03-asked-line.md`, including the operator's
mid-session amendment extending R4 to NFL and NBA.

---

## 1. Close-out table

| phase | verdict | evidence |
|---|---|---|
| **First act** save the brief, commit | **DONE** | `8328430`; the amendment recorded verbatim in `e2cc8b3`. |
| **B1** redeclare per sport, dated | **DONE, with a deviation** | New factor NAMES rather than new dates — §2.1. |
| **B1** bump the factor set for spread markets only | **DONE** | The version is now **per market**; measured before deciding — §3.3. |
| **B1** state the counts | **DONE** | 8 settled spread rows against 126 non-spread. |
| **B1** existing rows stand under their old version | **DONE** | Nothing rewritten; MLB's spread stays on `fs2`. |
| **B2** correlation before and after | **DONE** | CFB **0.9816 → 0.0317**. Full table in §3.1. |
| **B2** the independence on NFL/NBA, both reported | **DONE** | And it is not the flattering read — §3.2. |
| **B2** refit; nothing constant, nothing dropped | **PARTIAL** | All three converged, nothing dropped. **One constant remains** on NFL — §4.1. |
| **B2** standardised coefficients | **DONE** | §3.4. |
| **B3** synthetic re-ask, close-out only | **DONE, after correcting it** | My first version credited this session with someone else's change — §4.2. |
| **B3** the "why" template reworded | **DONE** | "the question sits 6 points above what the model expects". |
| **B4** planting: an asked line computed from anything else | **DONE** | Reproduces 0.9816 exactly. |
| **B4** planting: a market value in its path | **DONE** | LAW 1 closure scan. |
| **B4** full suite, verify.py | **DONE** | 939 tests / 0 skips; `verify.py` 4/4; 135/135 plantings. |
| **AMENDMENT** R4 for NFL and NBA, dated today | **DONE** | Both now choose the rung by nearest expected margin. |
| **AMENDMENT** NFL week 1 stands; week 2 onward uses the rule | **DONE** | Nothing rewritten; the rung is computed per question at ask time. |

## 2. Deviations, stated first

### 2.1 A new factor name, not a new date on the old one

The brief said to redeclare `nfl_asked_line`, `nba_asked_line`,
`cfb_asked_line` and date it. **LAW 2's registry refuses to move a factor's
activation date** — `store.sync_registry` raises `RegistryConflict` — and it is
right to.

So `*_asked_line` is **retired** (`active=False`, dated, with a note that it was
replaced rather than refuted) and `*_asked_distance` **declared today**. The
instrument changed; its forward record starts now instead of inheriting a score
earned by a different measurement.

### 2.2 The sign convention, written down rather than guessed

B4 says "rung minus expected margin". Taken literally on the stored rung that
is `-14.5 - 14 = -28.5` — still a copy of the rating, and not orthogonal at
all. B3's own example ("sits 6 points above") settles it: the quantity is the
**residual**.

```
distance = (margin the question demands) - (margin the model expects)
         = -rung - expected
```

A home side expected to win by 14, asked at -14.5, gives **+0.5**. Positive
means the question asks for more than the model expects. **The refit confirms
the sign independently**: the coefficient is negative in all three sports, so a
question above the expectation is less likely to be covered.

### 2.3 Two ladders extended, and MLB's spread deliberately untouched

R4 cannot be applied to a ladder that does not reach. Extended by **addition
only** — the CFB-1 precedent, because rows already stand at the original rungs:

| | rungs | refused before | refused after | busiest rung after |
|---|---|---|---|---|
| NFL | 4 → 11 | 2.28% | **0.26%** | 20.2% |
| NBA | 4 → 12 | 3.84% | **0.12%** | 15.2% |

Each sport keeps **its own** ladder. I briefly routed the NBA through
football's; a test caught it by name within a minute.

## 3. What was measured

### 3.1 The dependency break — the repair the ruling asked for

| sport | old instrument (the rung) | new (rung − expected) |
|---|---|---|
| **CFB** | **0.9816** | **0.0317** |
| NFL | 0.0060 | 0.1424 |
| NBA | 0.0153 | 0.2908 |

CFB is the case the ruling was written for, and it lands: the brief expected
"~1.0 → well under 0.5" and got 0.98 → 0.03.

### 3.2 The independence on NFL and NBA — the unflattering read

**Their old factor correlated ~0.00 with the rating because it was a hash of
the game id.** That is not orthogonality worth having; it is zero information.
Any random number is uncorrelated with everything.

The new factor correlates *more* — 0.14 and 0.29 — and is nonetheless the
better instrument, because it is a real quantity rather than noise. **NBA's
0.29 is the highest and deserves watching**: the residual still tracks the
rating slightly through the ladder's uneven spacing at the extremes.

Reporting these as a "win" would be the flattering reading, and it is not the
true one.

### 3.3 The factor-set version, and why it is now per market

The brief asked to bump spread markets only. The version was a **single global
string**, and `config.py` already recorded the consequence:

> "a change to one NBA prop factor would bump the version for every MLB market
> too and split records nothing touched... it is much cheaper before a
> single-sport bump is ever needed than after."

**This was that bump.** Measured before deciding:

| | settled rows |
|---|---|
| spread, all sports | **8** (MLB run line only) |
| not spread | **126** (MLB moneyline 80, props 38, total 8) |

A global bump would have split the project's largest single record for a change
that never touched it. `config.factor_set_version(sport, market)` now answers
per market; anything without an entry keeps `fs2`.

**MLB's spread stays on `fs2` deliberately** — its run line is asked at a fixed
±1.5 and has no asked-line factor at all.

### 3.4 The refit — standardised coefficients

Coefficient × the factor's own SD, so factors on different scales compare.

| sport | n | the redeclared factor's rank | standardised |
|---|---|---|---|
| CFB | 1,689 | **2nd of 5** | −0.2454 |
| NBA | 4,891 | 3rd of 8 | −0.1098 |
| NFL | 2,632 | 5th of 15 | −0.0946 |

All three converged. **Nothing dropped.**

The CFB result is the one worth reading twice: the distance is now the second
strongest factor in the model, and `cfb_srs_diff` (−0.1190) has an
interpretable coefficient **for the first time** — it was previously sharing its
effect with a coarsened copy of itself.

## 4. Corrections to my own work in this session

### 4.1 "Nothing constant" is PARTIAL, not DONE

NFL still reports `constant: {'precipitation': 760}`. That is the broken
instrument `docs/DIAGNOSIS.md` already recorded ("no data in 66% of
predictions") and it is untouched here — fixing it is a data-loading job, not
this ruling. **The brief asked for nothing constant and I did not deliver it.**

### 4.2 My first synthetic re-ask credited this session with another ruling's work

It compared today's rung against the **stored** rung and reported that CFB moved
on 48 of 60 games by a median of 24 points. That is wrong as a description of
this session: every college row was written 2026-09-01 under the **old
five-rung ladder**, and the movement is the 2026-09-02 extension, already
reported in its own close-out.

Corrected to compare old rule against new rule on today's code:

| sport | same rung | moved | median shift |
|---|---|---|---|
| NFL | 3 of 16 | 13 | 2.0 points |
| NBA | 4 of 47 | 43 | 7.0 points |
| CFB | — | — | **unchanged by this session** |

## 5. Two pre-existing defects found while doing B2

Neither was mine, both are fixed, and the first is serious.

### 5.1 LAW 6 was broken in the NFL spread training set

`spread_training_set` had **no `sport` filter**. It selected every final REG
game in the loaded seasons, so the NFL spread model was trained on **18,715
games of which 2,639 — fourteen per cent — were football.** The other 16,076
were baseball, basketball and college games, each handed the NFL's factor
vector and asked whether the home side covered an NFL rung.

Present since `9c0bc64` ("s1: multi-sport"). Nothing failed: the fit converged
and a bigger training set reads as a better one. **What gave it away was the
base rate** — 0.4265 where a nearest-margin rung should sit near 0.500, against
NBA's 0.4983 on the same rule. Fixed; NFL's base rate moves to **0.4867**.

### 5.2 The duplicate-slate guard has never run for NBA or CFB

`run.already_answered` calls `sports.get(sport).markets()`, and **neither
`sports/nba.py` nor `sports/cfb.py` defined it** — the guard raised
`AttributeError` before it could refuse anything. Ruling R4's protection
against forecasting a slate twice covered two sports out of four. Both now have
`markets()`, and the guard runs for all four for the first time.

## 6. What I would put in front of you

1. **CFB's expected margin is measurably wrong, and this session quantified it
   for the first time.** `cfb_expected_margin` uses slope 1.0 and intercept
   9.79. Least squares over 1,625 games says **+4.848 + 0.9351 × rating_diff** —
   the intercept is nearly double what the data supports. That is the
   documented 0.371 base-rate defect, now with a number on it. **I did not
   change it**: it would change which questions college football asks, which is
   beyond this ruling. It needs yours.
2. **A rating difference does not buy its own value in margin.** Ten points of
   rating buys **4.4** in the NFL and **6.0** in the NBA. Any future instrument
   assuming a slope of 1.0 will expect blowouts that do not arrive.
3. **NBA's new factor correlates 0.29 with the rating** — the highest of the
   three, and worth a second look once the NBA record has settled rows.

## 7. What is measurably true now

- Suite **939 tests, 0 skips**, EXIT=0; `verify.py` **4/4**; **135/135**
  plantings (three new this session).
- CFB's asked-line dependency: **0.9816 → 0.0317**.
- All three spread models refit, converged, nothing dropped.
- NFL spread training set is NFL-only for the first time since `9c0bc64`.
- No prediction row was rewritten, re-dated, or deleted.

## 8. Operator's verdicts

**Strongest thing:**

**Weakest thing:**

**What to do next:**
