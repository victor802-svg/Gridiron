# Market roster — what we can resolve, and the order to build it

**Measured 2026-09-02.** Every figure here was counted from the stored record.
Nothing is estimated, and nothing is taken from a source we cannot reach.

Governed by the operator's ruling of 2026-09-02: PrizePicks is **unavailable by
evidence** (`docs/DECISIONS_MADE.md`), so the roster is built from **what our
own loaders can already resolve**, ranked by **resolution data × per-slate
count**. Markets are built **one per session**, each governed by
`docs/NEW_MARKET_CHECKLIST.md`.

---

## 1. What this document is, and what it is not

The original brief ranked by *volume × data availability*, where volume meant
how often a book offers a stat. **That half is unavailable and is not guessed
at.** This roster substitutes the axis we can measure: how many questions a
slate would produce *for us*.

**It says nothing about whether anyone prices these markets.** A market on this
list may be unpriced everywhere, which affects the market comparison and
nothing else — LAW 1 has us predict blind regardless, and the record scores
itself on outcomes, not on lines. Where a market has no line, the card says "no
line" and the prediction stands on its own.

## 2. Method

- **Resolution data** — the share of stored rows where the resolving column is
  present. Counted over `mlb_batter_games` (145,497 rows, 2024–2026),
  `mlb_pitcher_starts` (33,596, 2023–2026), `nba_player_games` (105,253,
  2022–2025), `player_week_stats` (182,255, 2016–2025), and `games`
  (21,527; **100% of final games carry both scores in all four sports**).
- **Per-slate count** — qualifying subjects on a real slate, not a projection:
  - **MLB** 2026-09-02, 15 games: **270 batters** in posted lineups, **29
    probable starters**.
  - **NBA** 2026-04-12, 15 games: 311 players, **211 playing 20+ minutes**.
  - **NFL** 2025 week 18, 16 games: counted per stat at a usage floor
    (targets ≥ 3, carries ≥ 5, attempts ≥ 10).
- **Slates to gate** — `100 ÷ (per-slate count × resolution)`, the LAW 4
  threshold for an edge claim in one category. Days assume MLB and NBA play
  daily and NFL weekly.

> **THE "SLATES TO GATE" COLUMN BELOW IS UNREACHABLE AS WRITTEN.** It counts
> qualifying subjects, not questions this project asks: a 25-a-day cap and a
> 70% confidence floor sit between the two. Measured rate: **10 MLB prop
> predictions a day**, with two of four declared markets writing nothing.
> See section 6.

## 3. The ranking, as the ruling defines it

| # | sport | market | per slate | resolution | score | slates to gate | ~days |
|---|---|---|---|---|---|---|---|
| 1 | MLB | batter RBI | 270 | 100.0% | 270 | 0.4 | ~0 |
| 2 | MLB | batter doubles | 270 | 100.0% | 270 | 0.4 | ~0 |
| 3 | MLB | batter strikeouts | 270 | 100.0% | 270 | 0.4 | ~0 |
| 4 | MLB | batter triples | 270 | 100.0% | 270 | 0.4 | ~0 |
| 5 | MLB | batter walks | 270 | 100.0% | 270 | 0.4 | ~0 |
| 6 | NBA | player turnovers | 211 | 100.0% | 211 | 0.5 | ~0 |
| 7 | NFL | receiving TDs | 139 | 100.0% | 139 | 0.7 | ~5 |
| 8 | NFL | targets | 139 | 100.0% | 139 | 0.7 | ~5 |
| 9 | NFL | carries | 65 | 100.0% | 65 | 1.5 | ~11 |
| 10 | NFL | rushing TDs | 65 | 100.0% | 65 | 1.5 | ~11 |
| 11 | NFL | completions | 35 | 100.0% | 35 | 2.9 | ~20 |
| 12 | NFL | pass attempts | 34 | 100.0% | 34 | 2.9 | ~21 |
| 13 | MLB | pitcher batters faced | 29 | 100.0% | 29 | 3.4 | ~3 |
| 14 | MLB | pitcher earned runs | 29 | 100.0% | 29 | 3.4 | ~3 |
| 15 | MLB | pitcher innings | 29 | 100.0% | 29 | 3.4 | ~3 |
| 16 | MLB | pitcher runs allowed | 29 | 100.0% | 29 | 3.4 | ~3 |
| 17 | MLB | pitcher HR allowed | 29 | **73.5%** | 21 | 4.7 | ~5 |
| 18 | NFL | moneyline | 16 | 100.0% | 16 | 6.2 | ~44 |
| 19 | NFL | total | 16 | 100.0% | 16 | 6.2 | ~44 |
| 20 | NBA | moneyline | 15 | 100.0% | 15 | 6.7 | ~7 |
| 21 | NBA | total | 15 | 100.0% | 15 | 6.7 | ~7 |

## 4. Where the ranking is wrong, and why the build order differs

**The ranking counts questions, not answers.** Three corrections apply before
it becomes an order, and each is a rule this project already holds.

**(a) A one-sided market produces volume and no information.** Measured share
landing on the yes side, per subject-game:

| market | yes share | verdict |
|---|---|---|
| MLB batter triples | **1.3%** | **DISQUALIFIED** |
| MLB batter doubles | 13.7% | thin; needs a sub-1 rung it cannot have |
| NFL receiving TDs | 23.7% | usable, one-sided |
| MLB batter RBI | 26.5% | usable, one-sided |
| MLB batter walks | 27.0% | usable, one-sided |
| NFL rushing TDs | 31.7% | usable |
| MLB batter strikeouts | **55.8%** | **best-balanced prop measured** |

A triples question is "no" 98.7% of the time. Two hundred and seventy of those
a night is 270 rows that a model predicting "no" unconditionally would get
right — the category would look calibrated and would have measured nothing.
Counting-stat markets whose only available rung is 0.5 inherit their base rate
as the answer, and doubles at 13.7% is the same failure one step milder.

**(b) The bottom four entries are the most reliable things on the list.** NFL
and NBA moneyline and total rank 18–21 on volume and are the only entries that
need **no player identity match, no lineup, and no crosswalk**. They resolve
from a final score that is present for **100% of 21,527 stored games**. Every
prop above them depends on a name matching a name.

And they fill a real hole. **Both NFL and NBA currently ask only one game
market — `spread`** — while MLB and college football ask all three:

| sport | game markets asked today |
|---|---|
| MLB | moneyline, spread, total |
| CFB | moneyline, spread, total |
| **NFL** | **spread only** |
| **NBA** | **spread only** |

Their real cost is calendar, and it is the only thing separating them: NBA
plays daily and reaches the gate in ~7 days; NFL plays weekly and needs ~44,
because 16 games a week is 16 questions a week.

**(c) MLB's four existing prop markets already compete for a request budget.**
A fifth batter prop is not free — it shares the per-batter game-log fetches
that `MLB_PLAYER_SEASONS` deliberately narrows against `SPORT_LOAD_SEASONS`,
at roughly one request per batter per season. NBA turnovers and the game
markets add no new fetches at all: the rows are already stored.

## 5. The build order

One market per session, `docs/NEW_MARKET_CHECKLIST.md` item by item, item 1
(asked line + volatility) and item 7 (void rules) first.

| order | market | the one-line reason |
|---|---|---|
| **1** | **NBA moneyline** | Resolves from a stored final score, needs no identity match, and closes a real hole — NBA asks only `spread` today. 15 questions a night reaches the gate in about a week, the fastest of any market here that is not already one-sided. |
| **2** | **NBA total** | Same rows, same night, no new fetches; combined score mean 229.17, SD 19.90 over 4,920 games gives a declared ladder real evidence to sit on. |
| **3** | **MLB batter strikeouts** | The best-balanced prop measured (55.8% at ≥1), 270 subjects a night, and it reuses the batter crosswalk that already exists and was measured. |
| **4** | **NFL moneyline** | 100% resolution and no crosswalk; slow to the gate (~44 days), which is exactly why it should start early rather than late. |
| **5** | **NFL total** | Combined score mean 45.68, SD 13.92 over 2,761 games. Same slate, same rows as (4). |
| **6** | **MLB pitcher innings** | 29 starters a night, 100% resolution, and a continuous stat with a real spread (mean 5.09) rather than a near-binary. |
| **7** | **NBA player turnovers** | 211 qualifying players a night, mean 1.68 at 20+ minutes, rows already stored — the cheapest remaining prop. |
| **8** | **NFL targets** | 139 a week, and the volume stat behind receptions, which we already ask. |
| **9** | **MLB batter walks** | 27.0% one-sided but honestly so; a real rung exists at 0.5 and the base rate is far enough off the floor to measure. |
| **10** | **NFL carries** | 65 a week, the volume stat behind rushing yards. |

**Not scheduled, and the reason:**

- **MLB batter triples** — disqualified at 1.3%. Not a question, a formality.
- **MLB batter doubles** — 13.7% with no rung below 0.5 available. Revisit only
  if a fractional rung is ever justified by measurement.
- **MLB pitcher HR allowed** — **73.5% resolution**, the only incomplete column
  on this list. Build the loader first or do not build the market; a category
  that silently drops a quarter of its rows is a category whose N is a fiction.
- **NFL completions / pass attempts** — 34–35 a week, and both are
  near-duplicates of passing yards, which we already ask. Low information for
  the slot.
- **NFL receiving TDs / rushing TDs** — buildable (23.7% / 31.7%) but they are
  the same near-binary shape as passing TDs, which we already ask and which is
  77.1% one-sided. Worth one session only after the record shows how the
  existing TD market actually calibrates.
- **CFB player props** — no player-stat table is stored for college at all, so
  resolution data is **zero**, not thin. `docs/CFB_FEASIBILITY.md` §6 records
  that the stats exist upstream; loading them is its own session and its own
  decision.

## 6. What would change this document

- A loader that fills `mlb_pitcher_starts.home_runs_allowed` to 100% moves that
  market from "not scheduled" into the order.
- A college player-stat loader adds a whole sport's worth of rows.
- A lawful, documented PrizePicks feed restores the volume axis the original
  brief wanted, and this roster would be re-ranked against it rather than
  replaced by it.


---

## 6. CORRECTION, 2026-09-04: the "slates to gate" column is unreachable

**Section 3's table counts qualifying subjects. It does not count questions
this project will ask.** Two declared limits sit between the two numbers, and
neither is in the arithmetic:

- **`config.MLB_PROPS_PER_DAY` = 25.** The whole sport asks at most 25 prop
  questions a day, filled by round-robin across the declared prop markets, one
  question per subject per day. **A new prop market does not add questions; it
  takes a share of the same 25.** Adding `batter_strikeouts` moved the slate
  from 7 / 6 / 6 / 6 to 5 / 5 / 5 / 5 / 5.
- **`config.PROPS_MIN_CLAIM` = 0.70.** A question the model is not 70% sure of
  is not asked at all.

**Measured on the record itself**, over the five days it has been running
live: **50 MLB prop predictions written, 10.0 a day, 86% of them settled** —
and **two of the four declared markets have written nothing at all**
(`batter_total_bases` and `pitcher_strikeouts` both stand at zero, because they
do not clear the floor).

So the column reading "**batter RBI · 270 per slate · 0.4 slates to gate · ~0
days**" should be read as **270 subjects would qualify**, not as *a hundred
settled predictions arrive within a day*. At the realised rate, one MLB prop
market reaching its hundred takes **roughly a month of daily slates**, and only
if it wins a fair share of the cap against the markets already there.

**This does not change the build order.** The order comes from §4, which ranks
on balance and on what needs no identity match, and §4(b)'s reasoning is
unaffected. What it changes is the expectation of when any of these markets
will have earned a verdict.

**It applies to the NBA and NFL prop markets too**, which have their own caps
and the same floor. The figure to plan with is the realised one, and the record
now carries five days of it.

---

## Build log

| built | market | close-out |
|---|---|---|
| 2026-09-04 | **NBA moneyline** | `docs/closeouts/2026-09-04-nba-moneyline.md` |
| 2026-09-04 | **NBA total** | `docs/closeouts/2026-09-04-nba-total.md` |
| 2026-09-04 | **MLB batter strikeouts** | `docs/closeouts/2026-09-04-roster-step4.md` |
| 2026-09-04 | **NFL moneyline** | `docs/closeouts/2026-09-04-roster-step4.md` |
| 2026-09-04 | **NFL total** | `docs/closeouts/2026-09-04-roster-step4.md` |

**A WARNING THE ROSTER DID NOT CARRY.** The NBA total is built, balanced and always resolvable, and it measures almost nothing: a walk-forward edge of +0.0010 over always-the-base-rate. A total asked at OUR OWN rung is a coin flip by construction -- the value in a totals market is disagreeing with someone else's number, and LAW 1 forbids us seeing one before we predict. **NFL total (#19) is the same construction and should be expected to behave the same way.** See `docs/closeouts/2026-09-04-nba-total.md` section 4.

**The order is the roster's own §4(b), not its volume ranking.** The bottom
four entries need no player identity match, no lineup and no crosswalk, and
they resolve from a final score present for 100% of stored games. Every prop
above them depends on a name matching a name.
