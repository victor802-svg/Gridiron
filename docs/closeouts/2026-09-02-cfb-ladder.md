# Close-out — the CFB ladder (STEP 4)

Brief: `docs/briefs/2026-09-02-overnight.md`, STEP 4 MODEL REPAIRS, CFB only.

---

## 1. Close-out table

| item | verdict | evidence |
|---|---|---|
| **CFB-1** measure the 2024–25 expected-margin distribution | **DONE** | 1,618 rated games: mean +12.49, SD 13.84, percentiles at the 80th/90th/95th of +23.2/+30.2/+37.1. |
| **CFB-1** extend so the top rung is under 10% | **DONE** | Two rungs added, none moved. Top rung 27.1% → **3.5%**. |
| **CFB-1** record old and new with the date | **DONE** | Both ladders in `questions.py`, dated, with the measurement that justified the change. |
| **CFB-1** retrain against the new rungs | **DONE** | `cfb:spread` n=1,681, converged, `constant={}`, `dropped={}`. Same factors, same games, nothing re-dated. |
| **CFB-1** synthetic re-ask of Saturday | **DONE** | Below. Computed, never written — Saturday's 177 stand. |
| **CFB-1** planting: a rung beyond the ladder fails loudly | **DONE** | `plant_a_clamped_rung_beyond_the_ladder`; 124/124. |
| **CFB-2** document the asked-line dependency | **DONE, and BLOCKED as intended** | Note on the factor, and in FOLLOWUPS. Nothing changed. |

## 2. The measurement, and what it changed

Over **1,618** completed 2024–25 college games with a rating on both sides:

```
expected home margin   mean +12.49   sd 13.84
percentiles            80% +23.2    90% +30.2    95% +37.1    99% +53.5
```

The old ladder `(-24.5, -14.5, -7.5, -0.5, 6.5)` put **27.1%** of games on its
top rung. **A rung reached by a quarter of games is not a rung, it is a wall**:
every mismatch past it collapses onto one number, so the record stops measuring
whether the model can tell a 25-point favourite from a 45-point one.

Two rungs were **added** and none moved:

```
(-41.5, -31.5, -24.5, -14.5, -7.5, -0.5, 6.5)
```

| | old | new |
|---|---|---|
| top rung's share | 27.1% | **3.5%** |
| busiest rung | 27.1% | 24.2% |
| games refused as beyond the ladder | 0 (clamped) | 4.9% |

**Why add rather than re-space.** A re-spacing to `(-38.5, -28.5, -20.5, …)`
gave a slightly more even distribution — 21.4% on the busiest rung against
24.2% — but it retires numbers that predictions were already asked at. Those
rows stand (LAW 3), so the ladder they were asked against stays on it.

## 3. The synthetic re-ask of Saturday 2026-09-05

**Computed, never written.** Saturday's 177 predictions stand exactly as made.

```
                     old ladder      new ladder
top rung             45 of 58 (78%)   9 of 53
refused as beyond    0                5

the new spread:   +6.5:1  -0.5:2  -7.5:4  -14.5:5  -24.5:19  -31.5:13  -41.5:9
```

The brief's "45 of 60 landed on the last rung" reproduces exactly: **45 of the
58 rated games**. Under the extended ladder the same slate spreads across all
seven rungs.

## 4. What I would put in front of you

1. **The college spread base rate is 0.371, not 0.5, and the extension barely
   moved it** (0.394 → 0.371). The rung is chosen AT the expected margin, so a
   well-calibrated expectation should cover about half the time. It covers 37%,
   which means **`cfb_expected_margin` runs high** — the home side wins by less
   than the ratings say. That is a separate defect from the one this ruling
   fixed, and it is now the larger of the two. In FOLLOWUPS.
2. **4.9% of college games are refused as beyond the ladder** — about 80 a
   season with no spread question, recorded absent. That is the ruling working
   as written. If it proves too many, the answer is another dated extension,
   not a wider tolerance.
3. **CFB-2 is BLOCKED and stays blocked.** `cfb_asked_line` is a coarsened
   function of `cfb_srs_diff` under the nearest-margin rule — the rung comes
   from the expected margin, which comes from the rating difference — so its
   coefficient cannot be read as an independent effect. The extension changed
   the coarseness (five rungs to seven) and not the dependency. What the factor
   is FOR is yours.

## 5. What is measurably true now

- Top rung **3.5%** of 1,618 games, against the ruling's <10%.
- `cfb:spread` refitted: n=1,681, converged, `constant={}`, `dropped={}`.
- Suite green; `verify.py` 4/4 EXIT=0; **124/124** plantings.
- Saturday's 177 predictions untouched.

## 6. Operator's verdicts

**Strongest thing:**

**Weakest thing:**

**What to do next:**
