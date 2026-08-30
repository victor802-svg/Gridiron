# Adding a market

Every item here was paid for by a real defect in this project. None of it is
theory, and the cost is named beside each one so a future reader can see what
skipping it buys.

**Every new market is built against this list item by item, and the phase that
adds it must show the list ticked.** A checklist written after the work is a
description; written before, it is a constraint. That distinction is why this
document exists in its own commit, before the markets it governs.

---

## 1. The question instruments exist from day one

A model that is not told **which rung it was asked** averages several different
questions into one answer. Two factors are required before any market ships:

- **`mean_vs_line`** — where the asked line sits relative to the subject's own
  recent average. Without it, a line set at −30%, at the mean, and at +30% are
  three different questions the model cannot distinguish.
- **subject volatility** — dispersion over the window. Two players with the same
  average are not the same question: a high-variance subject clears a high line
  more often and misses a low one more often.

> **Paid for by:** NBA props shipped without both. The fit converged, the
> coefficients looked reasonable, and nothing was visibly wrong. Refitted with
> `mean_vs_line`, it became the dominant coefficient in all four markets
> (+2.5 to +3.3) — it had been the largest missing signal in the model.

## 2. Variance bookkeeping on every factor

The fit reports which factors were **constant** across the training set, and a
constant factor is a broken instrument, not a weak one: there is nothing to fit.
Check `fit.constant` and `fit.dropped` on every new market before believing any
coefficient.

> **Paid for by:** three separate cases. `short_week_diff` (NFL) varied in 1 game
> of 544, because the league puts both clubs on a short week together.
> `mlb_home_away` was constant across all 4,859 rows, because every MLB question
> asks whether the home club wins. `nba_back_to_back` never fired at all,
> because a back-to-back is the night *after* a game and "days since" reads 1,
> never 0.

**A differential is only an instrument if the two sides can actually differ**,
and how often they differ is a measurable fact about the sport, not a matter of
opinion. Measure it before declaring the factor.

## 3. Alias and identity round-trip, measured

Subject and team codes must be proven against **both** feeds with a reference set
read from the data, never written from memory. The rule: an alias maps a name
you do **not** use onto one you **do**.

> **Paid for by:** two reversed NBA aliases (`NOP→NO` written backwards,
> `PHX→PHO` rewriting a code both feeds already agreed on) left 7 of 53 games
> unmatched. Then the reference set written *from memory* to check them had MLB
> as `ARI`/`CHW` where the feed gives `AZ`/`CWS` — which would have condemned a
> correct alias as reversed.

## 4. Plausibility cross-checks between related numbers

Where two stored numbers describe the same thing, assert they agree.

> **Paid for by:** the ESPN spread sign. Flipping only when ESPN *also* flagged
> the home team favourite produced correct numbers for home favourites and
> **sign-reversed** ones for home underdogs — a fault that inverts the market
> comparison on half of all games and is invisible in the data. It surfaced only
> because a stored line said Washington was favoured by 15.5 next to a +900
> moneyline. A spread and a moneyline must agree about who is favoured.

## 5. Missing data is explicit-absent, never defaulted

A factor that cannot be measured is **excluded from that row's normal
equations**, never set to zero. The prediction row records which factors were
present, which were absent, and why.

> **Paid for by:** `Factor.default` was removed from this project entirely in
> D2. A defaulted starting pitcher means silently predicting every unannounced
> game as though both arms were league average — a strong claim wearing a
> missing value's clothes.

## 6. Its own calibration category and its own gate

Every market is its own scoring category with its own 100-resolution gate. Never
merged with another market, another forecaster, or another sport.

LAW 6 is written about sports, but **the same reasoning applies to market types
within a sport**: pooling an easy market with a hard one flatters reliably,
because the easy one dilutes the hard one.

> **Paid for by:** NBA's STRONG tier spans two buckets (70–80% and 80%+) and
> each keeps its **own** number for exactly this reason.

## 7. VOID rules written before the first prediction

Decide and document, in advance, what resolves as void and why. Typically:

- the subject did not appear (scratched, benched, did not pitch);
- no stat line exists for a game that was played;
- the game was postponed, suspended, or abandoned.

A void is **terminal** and removes the prediction from every curve. Deciding
this after seeing the results is choosing which losses to keep.

> **Paid for by:** the NFL prop rule — a player who did not play did not answer
> the question either way, and scoring it as an under would credit the model for
> a roster decision it never forecast.

## 8. The resolution source verified to carry the stat

Confirm the feed actually returns the stat line, for the seasons needed, before
building on it. The loader must be **loud on empty** — warn and exit non-zero
when a season that should have games returns none.

> **Paid for by:** nflverse's legacy `player_stats` asset silently stops at 2024.
> Loading from it produced a database that looked fine and had no 2025 box
> scores at all. A source that quietly ends is worse than one plainly missing.

## 9. Timing and cadence

- Predictions are written inside `MAX_FORECAST_LEAD_DAYS` (21).
- The slate's cadence is stated: daily, weekly, per-series.
- A slate that has already started is recorded **MISSED**, never forecast late.

> **Paid for by:** 47 NBA predictions written 52 days before tip, and 6 MLB
> predictions written after first pitch. A question once answered is never
> re-asked, so a late answer permanently occupies the slot the real forecast
> should have had. All 53 were voided.

## 10. A dated activation note, and honest framing

- The factor set carries a dated activation note; scoring starts at activation
  and is never backfitted (LAW 2).
- Any backtest is labelled **pipeline-sanity, not evidence** — it was produced
  over seasons already played, by a factor set chosen with knowledge of how they
  went.
- Nothing claims an edge below 100 resolved in that category (LAW 4).

> **Paid for by:** the rolling-window leak, which made an NBA model appear to
> beat the market by 14%. Corrected, the market wins. **A leak does not only
> inflate scores — it manufactures conclusions about factors**, and it had
> already produced one: `nba_back_to_back` was judged a broken instrument on a
> 4.4% firing rate that was itself an artefact of the leak. The true figure is
> 21.3%.

---

## The tick sheet

Copy into the phase's close-out and mark each one with its evidence.

| # | Item | Evidence |
|---|---|---|
| 1 | `mean_vs_line` and volatility factors declared | |
| 2 | `fit.constant` / `fit.dropped` checked and empty | |
| 3 | Alias round-trip measured against both feeds | |
| 4 | Cross-checks between related numbers | |
| 5 | Missing data explicit-absent; presence recorded | |
| 6 | Own category, own gate, never merged | |
| 7 | VOID rules written before the first prediction | |
| 8 | Resolution source verified; loader loud on empty | |
| 9 | Inside the lead horizon; cadence stated | |
| 10 | Dated activation; backtest labelled; gate respected | |
