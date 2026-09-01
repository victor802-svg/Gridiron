# College football

Three team markets — **spread, moneyline, total** — and no player props. The
feasibility probe is in `docs/CFB_FEASIBILITY.md`; everything here rests on it.

---

## What is different about this sport

| | why it matters |
|---|---|
| **A slate is a DAY** | `week` is null on every 2026 event, so it cannot be read from the feed. Saturday holds ~60 games, Sunday ~16, Friday ~8 — three slates a week ordinal would merge. |
| **The schedule is a UNION** | The league-wide weekly endpoint returns ~20 events a week against 888 a season. Building on it would forecast a third of the sport and look complete. |
| **Margin SD 22.46** | Against the NFL's 12.70. Its own ladder, its own market comparison. |
| **Totals are a new question shape** | Their own calibration family, never pooled with margins. |
| **One id space** | Schedule, scores and lines all come from ESPN. No crosswalk, no aliases. |
| **No player props** | Zero rows at the only provider. Not built. |

## The questions

Per game, per slate:

- **Spread** — the home team against one rung of `CFB_SPREAD_LADDER`
  (`-24.5, -14.5, -7.5, -0.5, +6.5`), chosen by a stable hash of the game id.
  Declared 2026-08-31 from the measured margin quintiles.
- **Moneyline** — does the home team win.
- **Total** — do the two teams combine for more than a line **we generate**
  from their own stored scoring form, rounded to a half point. Absent when
  either side has no completed games yet.

Every line we ask at is ours. No published line is consulted before a
prediction is written (LAW 1), and the half-point on a total is deliberate: a
whole number can push, and a pushed question has no answer to score.

---

## VOID RULES, written before the first prediction

Decided and recorded **in advance**, per checklist item 7. Deciding this after
seeing results is choosing which losses to keep.

### These VOID

- **The game was cancelled.** No result exists. Scoring it would credit or
  punish the model for a schedule decision it never forecast.
- **The game was postponed** out of its slate and has no final score. The
  forecast was for a game on a date; a game played weeks later under different
  conditions is a different question.
- **The game was abandoned** — started, never finished, no official final.
- **The game left the record.** If the feed no longer carries it, there is
  nothing to grade and nothing may be inferred from the absence.

A void is **terminal**: the prediction is removed from every curve, keeps its
row, and can never later be given an outcome.

### These do NOT void — the forecast stands

- **The line disappeared before kickoff.** This is the one worth stating
  plainly, because the temptation runs the other way. A prediction is a claim
  about the world, not about the market: it was written blind, before any line
  was fetched, and whether a book later pulled its price changes nothing about
  whether the home team covered. **Only the comparison is absent.** LAW 3
  applies — the prediction stands exactly as written, and the record shows
  "no line" beside it.
- **The line moved.** Same reasoning, and the drift machinery exists precisely
  to measure that movement rather than to react to it.
- **A game against an FCS opponent.** It was played and it had a result. A
  factor may know the opponent is non-FBS; the question still resolves.
- **A blowout with no moneyline quoted.** The spread and total questions were
  asked and answered; the moneyline one either was not asked or has no
  comparison. Neither is a void.

### One bias worth stating: an FCS opponent's record is only its FBS games

The loader walks the 136 FBS schedules, so a lower-division team enters the
record **only through the games it played against FBS opposition** — which are
disproportionately the ones it loses badly. Its scoring form here is therefore
lower than its real form, and a total generated from it will sit low.

This is not a defect to be corrected by inventing the missing games; it is
what our record actually contains, and pretending otherwise would be the worse
error. Two things follow:

- `CfbContext` carries `home_is_fbs` / `away_is_fbs`, so a factor can know it
  is looking at a cross-division game rather than averaging it in blind (B3).
- A total asked at, say, 31.5 for an FBS-vs-FCS game is a question about a
  number we generated from partial information, and its record will say so:
  the market comparison on those games is what shows whether it was fair.

### Cadence

- CFB's slate is a **day**, and the forward slate is written on **Friday** for
  Saturday — inside `MAX_FORECAST_LEAD_DAYS` (21) with room to spare, and
  after most lines have posted, which matters only for the comparison and never
  for the forecast.
- A slate that has already started is recorded **MISSED**, never forecast late.
