# Close-out — UFC, all sanctioned events and the market comparison

Brief: `docs/briefs/2026-09-03-ufc-events.md` (E1–E5). ITEM 4.

---

## 1. Close-out table

| phase | verdict | evidence |
|---|---|---|
| **E1** probe: tiers in the payload | **DONE** | There is no tier field. Measured, not assumed — §2. |
| **E1** coverage per tier | **DONE** | All three tiers already loaded; 268 events — §3. |
| **E1** distance base rate per tier | **DONE** | Contender Series 43.6% against 55.3% and 58.0% — §3. |
| **E1** Contender Series cadence | **DONE** | Aug–Oct, 3–5 cards a month, 5 bouts a card — §3. |
| **E2** all tiers ingested, `event_tier` stamped | **DONE** | 259 cards stamped, 8 refused — §4. |
| **E2** rating recomputed walk-forward | **DONE** | K refits at 80.0, still interior — §5. |
| **E2** fighters gaining a first data point | **DONE, and the question was the wrong one** | §5. |
| **E3** categories split by tier, own gates | **DONE** | 6 categories → 18; other sports untouched — §6. |
| **E3** tier on the card | **DONE** | "Fight Night · 9:00 AM", rendered at 1400 and 390 — §6. |
| **E3** planting: merged tiers | **DONE** | Caught; it also broke an older fixture, correctly — §6. |
| **E4** UFC fetcher in the market module | **DONE** | 14 of 14 priced on a 2025 card — §7. |
| **E4** *cards stop reading "no line"* | **DECLINED — UNAVAILABLE BY EVIDENCE** | The source stopped carrying UFC odds in January 2026 — §7. |
| **E5** plantings | **DONE** | Three; 157/157 overall — §8. |
| **E5** renders | **DONE** | 1400 and 390; two truncations fixed — §9. |
| **E5** verify.py | **DONE** | 35 rows PASS, none FAIL — §10. |

## 2. E1 — the payload carries no tier field

R2 asked how the tier is identified in the payload. **It is not.** One event of
each kind, fetched in full and compared field by field:

| field | UFC 324 | UFC Fight Night | Contender Series |
|---|---|---|---|
| `seasonType` | `types/2` | `types/2` | `types/2` |
| `league` | `ufc` | `ufc` | `ufc` |
| `shortName` | `UFC 324` | `UFC Fight Night` | `Dana White's Contender Series` |

No `type`, no `grouping`, no tier marker of any kind. **The name is the only
carrier**, so the ruling's caution is honoured a different way: the tier is
derived from the name because there is nothing else, and then **validated
against card structure**, which is a fact about the event rather than a string.

## 3. E1 — and the ruling was right about the Contender Series

| tier | events | settled | goes the distance |
|---|---|---|---|
| Fight Night | 143 | 1,619 | **55.3%** |
| numbered | 66 | 753 | **58.0%** |
| Contender Series | 50 | 218 | **43.6%** |

**Twelve to fourteen points.** Far too large for one UFC distance curve to
average. Contender Series also carries **no five-round bouts in five seasons** —
five three-round bouts a card, so `ufc_scheduled_rounds` is constant within the
tier and the ladder has exactly one rung there.

Cadence: August to October, three to five cards a month, consistently 4.6–5.3
bouts a card across 2022–2026.

## 4. E2 — the stamp, and the thirteen the name did not fit

Card structure per tier, measured over 268 events:

```
numbered      11.8 bouts/card   1.61 five-round
fight_night   11.9 bouts/card   1.00 five-round
contender      4.6 bouts/card   0.00 five-round
```

Against those norms, the thirteen unclassified resolve:

- **Noche UFC** (3 cards): 11, 14 and 12 bouts, one five-round each — the Fight
  Night shape exactly. Classified as Fight Night.
- **UFC 306 – Riyadh Season Noche UFC**: 10 bouts, two five-round. A numbered
  card wearing a theme, and **the number wins over every other pattern**.
- **UFC Freedom 250**: 7 bouts, two five-round, one Main Card. Two five-round
  bouts says numbered; seven bouts on a single segment says nothing in the
  record. **Left UNCLASSIFIED rather than guessed** — it still feeds the rating
  pool, and it joins no category.
- **The Ultimate Fighter** (8 entries): **one bout each.** No real card in five
  seasons carries fewer than three. Weekly television episodes, whose bouts do
  not appear on a professional record. Refused. *The one bout is the measured
  fact; the unsanctioned part is domain knowledge, and it is labelled as such.*

**I broke this on the way, and it is the most useful thing in this section.**
The first not-a-card test was `bout_count >= 3` and nothing else. It demoted
**eight upcoming cards** — five Contender Series and three Fight Nights whose
bouts are still being announced — and deleted eighteen real bouts along with
the seven it meant to. **A thin card and an unannounced one are identical from
the bout count; only the date tells them apart.** Restored by reload
(2,738 → 2,749, which is 2,756 minus exactly the seven), and the rule now leads
with an explicit named list and treats every future event as a card.

Nothing LAW 3 protects was touched: the script refused to delete any bout a
prediction pointed at, and none did.

## 5. E2 — the rating, and a question worth rephrasing

Recomputed walk-forward over the whole pool. **K refits at 80.0, unchanged, and
still interior** — 96 and 64 are both worse. Brier 0.2362, hit rate 60.4% over
1,194 held-out bouts. Zero TUF rating rows remain.

E2 asked how many fighters gained a first data point from ingesting all tiers.
**None, because all three tiers were already being loaded** — the existing
loader was never restricted to numbered cards, and what was missing was the
stamp, not the data. The question worth answering is the one behind it, and it
has a large answer:

```
fighters with any bout          1,324
who have fought on a CS card      411
whose ONLY bouts are CS           207   <- 15.6% of the pool
```

**Fifteen per cent of the rating pool exists only because the Contender Series
is included.** That is what R1 actually buys.

## 6. E3 — LAW 6, one level down

`config.SPORT_EVENT_TIERS` declares which sports split below the market (only
UFC). `resolved` and `curve` take an `event_tier`; the scorecard loops over
tiers. **UFC goes from 6 categories to 18. The other four sports are untouched**
— the loop is over `(None,)` for them.

**Each tier carries its own gate.** `MIN_SAMPLE_FOR_EDGE_CLAIM` applies per
category, so three tiers means three separate hundreds rather than one shared
one. Slower, and the point: a Contender Series claim earned on numbered-card
evidence is not earned.

`assert_no_merged_categories` refuses a category that names no tier for a sport
that splits, and one that names a tier nobody declared.

**The tier factor is two indicators and a reference level.** One indicator would
have assumed numbered cards and Fight Nights are one population; a single 0/1/2
code would have claimed the three are ordered and evenly spaced. Fight Night is
the reference. `ufc_is_numbered` is expected to come back near zero — the
measured gap is 2.7 points — and a near-zero coefficient is a useful answer.
Rounds and distance only: a tier indicator is the same value for both fighters,
so it cannot inform a symmetric market.

The card says it in words: **"Over 2.5 rounds · Fight Night · 9:00 AM"**.
`fight_night` is what the column holds and what every query filters on, and it
is never what a reader sees.

**The new rule broke an older planting's fixture, correctly.** ITEM 1's
merged-market planting built "honest" categories with no tier, which are no
longer honest. Fixed rather than exempted — a planting that passes because its
fixture predates a rule proves nothing.

## 7. E4 — the fetcher is built; the line is not there

### 7.1 What was built

`gridiron/market/ufc.py`, inside the LAW 1 quarantine, wired into
`ensure_lines` so quotes are fetched only after the prediction rows exist. On a
14-bout November 2025 card it prices **14 of 14, every one with an opening
price**. Providers are taken in a **declared priority order** rather than
"whichever came first", because feed order can change without notice and would
show up as unexplained movement in a record that exists to measure movement.

### 7.2 Why "cards stop reading no line" is DECLINED

| season | sampled | priced |
|---|---|---|
| 2022 | 18 | 18 |
| 2023 | 18 | 18 |
| 2024 | 18 | 18 |
| 2025 | 18 | 18 |
| **2026** | **18** | **0** |

Month by month across the boundary: full through November 2025, three of five
in December, and **one priced bout in forty-five sampled from January 2026
onward**. The endpoint answers `200` with `count: 0` — not an outage, not a
changed URL. **The source stopped carrying UFC prices.**

Every bout Gridiron currently forecasts is unpriced, so no live UFC card shows a
comparison. This is the PrizePicks precedent: **unavailable by evidence, no
proxies, no bypass.** The fetcher is correct, cached, and starts working the day
coverage returns.

### 7.3 I am correcting my own earlier finding

ITEM 1's probe reported "19 of 20 sampled bouts carried an odds reference" and
its close-out said "the probe proved it is there". **The count was right; the
conclusion was not.** The sample did not span the boundary — it measured a
period of complete coverage and answered a question about a period without it.
`UFC_FEASIBILITY` §3 now carries the correction at its head and §10 carries the
numbers.

### 7.4 The cross-check fired on its first run, and was wrong to

A bout with both fighters at −110 and neither flagged favourite is a **pick'em**
— a real market state, and the most informative comparison there is, because the
market is saying it does not know either. I had refused it as a contradiction.
Equal prices with no flag is agreement now; the genuine contradiction, a price
favouring one fighter and the flag favouring the other, is still refused.

### 7.5 What is here that exists nowhere else in this project

**Opening prices.** `docs/DIAGNOSIS.md` records H1a — "the model disagrees most
when it is MISSING information the market has" — as NOT TESTABLE, because every
market number this project holds for its other sports is a closing number. UFC's
historical record carries `open` and `close` on the same object, on 2022–2025
bouts. Nothing acts on it yet; it is counted, not stored, because a column
written by nothing will be wrong when something finally reads it.

## 8. The bug the fetcher found, which was worse than its own subject

Its first INSERT failed with `no such table: main.games_narrow`.

Widening the sport CHECK on `games` in ITEM 1 renamed the table aside; SQLite
rewrote every referencing table's foreign key to **follow** the rename, and
creating a fresh `games` and dropping the aside copy left them pointing at
nothing. **Twelve tables, 311,655 rows, foreign keys naming a table that did not
exist.**

**Nothing noticed for hours.** Every read worked. The suite was green. Five
sports rendered. `PRAGMA foreign_key_check` was reporting violations the whole
time and nothing was asking it. **A schema fault that only breaks on write is
the worst kind for a project that mostly reads.**

Repaired by rewriting the schema text — the SQLite-sanctioned fix for exactly
this, and it touches not one data row, which matters when the last rebuild in
this project is what caused the problem. Backup taken first. Verified the way
the widening was:

```
12 schema entries rewritten     integrity_check: ok
foreign_key_check: 0 violations (it was reporting them before)
predictions 561, fingerprint BYTE-IDENTICAL, no row count changed
```

`audit.dangling_reference_faults` is now in the gate. The planting reproduces
the rebuild shape exactly — and **not** a rename-and-rename-back, which SQLite
repairs, a fact worth knowing and the reason the first version escaped.

## 9. E5 — what the renders found

**The closure planting escaped first, and the escape is the finding.** It used
the default entrypoint, which walks `gridiron.model.predict` and never reaches a
sport adapter. Every sport is its own root; the planting now walks all of them.
**A closure scan is exactly as wide as the entrypoints it is given.**

**Two truncations at 390px, and I had just made one worse.** `.row-title` and
`.row-pick` carried `text-overflow: ellipsis` — the defect recorded in FOLLOWUPS
during the count markets and deferred. Adding the event tier to that same pick
line enlarged it, and deferring twice would have been a choice to ship a defect
I had grown. `.prob small` truncated too: a fighter's name is longer than a
tricode, so a UFC card read "NATHANIEL W…". Both wrap now. Verified: **no
ellipsis element anywhere in the frame, no clipped text, no overflow.**

**And a false sentence.** "Over 2.5 rounds" read *"Nathaniel Wood vs Pavel
Andrusca covers"*. A bout does not cover, and the subject of a rounds question is
the whole matchup, so the spread branch produced both errors at once.

**This is the fourth time `chance_clause` has been wrong in the same shape**, and
its own docstring predicted it: props read "goes over" whichever side was taken;
then spreads read "covers" whichever side was taken, on 34 cards, at high
confidence, with a correct decomposition underneath contradicting the headline;
now rounds and distance inherited the spread's verb. Each was fixed by adding a
branch; **none removed the reason a next one was possible** — the last line of
the function *was* the spread branch. It now refuses by name, and the fifth
market's turn will land in the gate.

## 10. What is measurably true now

- **974 tests, 0 skips, 0 failures. 157/157 plantings** — five new.
- `verify.py`: **35 rows PASS, none FAIL**; steps 2, 3, 4 PASS.
- 259 cards stamped with a tier, 8 refused as television, 1 left unclassified.
- 2,749 bouts; **UFC categories 6 → 18**, each with its own hundred.
- Rendered at 1400 and 390: the tier in plain words, no truncation, no overflow,
  no identifier leak.
- No prediction row rewritten, re-dated or deleted.

## 11. Rulings taken in your absence

1. **TUF refused entirely** — not among R1's three tiers, one bout per entry,
   and its bouts are not on a professional record.
2. **Noche UFC classified by structure, not name**; a numbered card's number
   beats its theme.
3. **UFC Freedom 250 left unclassified** rather than guessed. It feeds the
   rating pool (R1) and joins no category (R2).
4. **"Cards stop reading no line" declined on evidence**, per the PrizePicks
   precedent, with the coverage measurement recorded.
5. **Rounds and distance not registered as priced markets.** `overUnder` sits on
   the same object, but nothing has measured whether its posted line matches the
   rungs the declared ladder asks at, and a comparison against a differently
   worded question is not a comparison.
6. **The 390px truncation fixed rather than deferred again**, because this
   session's own change enlarged it.

## 12. Operator's verdicts

**Strongest thing:**

**Weakest thing:**

**What to do next:**
