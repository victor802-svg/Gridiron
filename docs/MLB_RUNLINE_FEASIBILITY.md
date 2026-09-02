# MLB run line and totals — feasibility probe

**Read-only. Measured 2026-09-02.** Nothing was built from this document; it
exists to say what the evidence supports before anything is.

Brief: `docs/briefs/2026-09-02-overnight.md`, STEP 3 (M-PROBE).

---

## The short answer

**Both markets are feasible, and one stored field is wrong.**

ESPN carries a run line, a total, prices for both, and **explicit side labels**
on every priced MLB game. The side does not need to be derived at all — the
milestone-anchor and monotonicity precedents are not required here, because the
payload states which team is the favourite in a boolean.

The probe also found a **defect in what this project already stores**: the sign
of `market_lines_raw.spread_line` disagrees with the moneyline favourite on
25% of MLB rows. Any build must read the explicit flags rather than that sign.
That is reported below rather than fixed, because fixing it is a separate act
with its own evidence.

---

## 1. What ESPN carries, and at what coverage

From the cached game-odds payload
(`.../baseball/leagues/mlb/events/*/competitions/*/odds/*`):

| field | example | what it is |
|---|---|---|
| `spread` | `1.5` | the home team's run line |
| `overUnder` | `8.0` | the total |
| `overOdds` | `-118.0` | **the over's price** |
| `underOdds` | `-102.0` | **the under's price** |
| `homeTeamOdds.favorite` | `false` | **the side label, stated** |
| `homeTeamOdds.underdog` | `true` | its complement, also stated |
| `homeTeamOdds.moneyLine` | `134` | the moneyline we already store |
| `homeTeamOdds.open.pointSpread` | `"+1.5"` | the run line, as displayed |
| `homeTeamOdds.open.spread` | `{"alternateDisplayValue": "-126", ...}` | **the run line's price** |

**The run line is always ±1.5.** 71 of 71 stored rows, no exceptions. The
brief's premise holds: the market's rung is fixed, so a question asked at that
rung is asking exactly what the market asked.

**Totals** run 7.0 to 11.5, median 8.0. **39 of 71 are whole numbers**, which
can push — a total of 8.0 with 8 runs scored is neither over nor under. The
brief's instruction to round a self-generated asked total to `.5` avoids this
entirely, and that is now a measured reason rather than a stylistic one.

**Coverage, on the slates that carry prices at all:**

| slate | games | priced | run line | total |
|---|---|---|---|---|
| 2026-09-01 | 15 | 13 (87%) | 13 | 13 |
| 2026-08-31 | 12 | 12 (100%) | 12 | 12 |
| 2026-08-30 | 14 | 12 (86%) | 12 | 12 |
| 2026-08-29 | 17 | 12 (71%) | 12 | 12 |
| 2026-08-28 | 15 | 15 (100%) | 15 | 15 |

**Where a game is priced at all, it carries both the run line and the total —
71 of 71.** There is no market here that is present for one question and
missing for the other. Coverage of the slate itself ranges 71–100% on complete
days; a partially-priced slate is the normal case, not a fault.

Future slates carry no prices yet (0 of 15 on 2026-09-27), which is expected:
books post close to the day.

---

## 2. The measured total-runs standard deviation

Dated **2026-09-02**, from every stored final MLB game.

| season | n | mean total | **SD** | median |
|---|---|---|---|---|
| all | **9,373** | 8.97 | **4.511** | 8.0 |
| 2023 | 2,430 | 9.23 | 4.583 | 9.0 |
| 2024 | 2,429 | 8.79 | 4.311 | 8.0 |
| 2025 | 2,430 | 8.89 | 4.593 | 8.0 |
| 2026 | 2,084 | 8.96 | 4.542 | 8.0 |

**Stable across four seasons** (4.31 to 4.59), which is what makes it usable.

### A discrepancy worth recording

The brief says "the existing margin SD 4.71 covers the run line". Measured on
the same 9,373 games, the **margin** SD is **4.534**, not 4.71:

```
margin (home − away): n=9,373  mean=+0.021  sd=4.534
```

The mean margin of +0.021 runs is worth noting on its own: **home advantage in
MLB is essentially zero in this sample**, which is not true of the other three
sports.

Whether 4.71 came from a different window, a different sport or a different
definition is not established here. **A build must not use 4.71 without
re-deriving it**, and the undated-SD guard should refuse it either way.

### What the run line actually asks

```
home wins by 2+ : 35.8%
away wins by 2+ : 36.2%
one-run games   : 28.0%
```

**28% of MLB games are decided by one run.** That is the whole of the run line
question: it is not "who wins" with a handicap, it is "does this game land
outside the one-run band", and the two sides are close to symmetric at 36/36.

---

## 3. The defect this probe found

`market_lines_raw.spread_line` is documented as nflverse convention — positive
when the home side is favoured. On MLB rows it does not hold:

- **53 of 71 rows** are consistent with that convention.
- **18 of 71 (25%)** are consistent with the opposite one.

Examples of the 18, with the moneyline that contradicts them:

```
LAD @ DET   run line +1.5   moneyline home +168, away −180
PHI @ LAA   run line +1.5   moneyline home +212, away −229
BAL @ ATH   run line +1.5   moneyline home +131, away −140
```

In each, the home team is a clear moneyline underdog and the stored line says
the home team is favoured.

**An outcome test could not settle it, and that is worth saying plainly.**
Splitting 65 completed games by the stored sign gives mean home margins of
+1.49 and +1.35 — a separation of 0.14 runs. Splitting the same games by the
moneyline gives +1.82 and +1.00, a separation of 0.82. With a margin SD of 4.5
and about 30 games a side, the standard error is roughly 1.2 runs: **neither
comparison is powered to distinguish the conventions.** The first draft of this
probe read the 0.14 as evidence the sign was uninformative. It is not evidence
of anything.

**What settles it is the payload, which states the side outright.** A build
reads `homeTeamOdds.favorite` and stops guessing.

---

## 4. What the evidence supports

| question | answer |
|---|---|
| Run line available? | **Yes**, ±1.5 on 71 of 71 priced games. |
| Run line priced? | **Yes** — `homeTeamOdds.open.spread`, not currently stored. |
| Total available? | **Yes**, 71 of 71 priced games. |
| Total priced? | **Yes** — `overOdds` / `underOdds`, not currently stored. |
| Side labels present or derived? | **Present.** `favorite` / `underdog` booleans. |
| A market missing or one-sided? | **No.** Both are present wherever either is. |
| Total-runs SD | **4.511**, n=9,373, dated 2026-09-02. |
| Margin SD | **4.534**, n=9,373 — *not* the 4.71 the brief cites. |

**Nothing here argues for shrinking the build.** Both markets are supported by
the evidence, with three conditions:

1. **Read the side from the flags**, never from `spread_line`'s sign.
2. **Store the two prices** (`overOdds`/`underOdds`, and the run line's own
   price) — without them there is a line but no implied probability, and so no
   market comparison.
3. **Re-derive the margin SD** rather than inheriting 4.71.

---

## 5. What was NOT done, and why

**The build was not started.** The probe was run at approximately 05:30 local
on 2026-09-02, after GRIDIRON_16 and GRIDIRON_13 had completed. The brief says
the markets go live tonight if the probe passes; tonight had already gone, and
today's MLB slate was forecast at 11:00 with the markets that exist.

Building two new question shapes properly means void rules written first,
declared factors with dated rationales, a fit, the variance bookkeeping, and
`docs/NEW_MARKET_CHECKLIST.md` ticked item by item — the checklist the brief
itself requires. Half of that, committed against a deadline, is the kind of
thing this project's laws exist to prevent.

**The probe stands on its own and is the thing that had to come first.** It is
committed so the build can start from measured evidence rather than repeating
the measurement.
