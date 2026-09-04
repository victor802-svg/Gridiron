# Close-out — adjusted form

Brief: `docs/briefs/2026-09-03-adjusted-form.md` (D1–D4). ITEM 3 of the
three-item unattended session.

---

## 1. Close-out table

| phase | verdict | evidence |
|---|---|---|
| **D1** adjusted factor for NBA | **DONE** | `nba_srs_diff`, declared beside the raw one — §3. |
| **D1** adjusted factor for NFL | **ALREADY BUILT** | `srs_diff`, declared 2026-08-28. The brief's premise was wrong here — §2. |
| **D1** variance bookkeeping on both | **DONE** | And it found something bigger than collinearity — §4. |
| **D1** retire one by dated note if near-collinear | **NOT TRIGGERED — measured** | Neither pair is near-collinear (VIF 1.95, 2.67). Both stand, both noted — §4, §5. |
| **D2** refit + standardised coefficients | **DONE** | NBA refitted on the live record, n=4,914 — §6. |
| **D2** walk-forward, labelled | **DONE** | SANITY ONLY. Brier .2468 → .2401 — §6. |
| **D2** version the factor set | **DONE (NBA only, deliberately)** | `nba:spread` → `fs4`; NFL not bumped, and why — §7. |
| **D3** "why" template | **DONE, and it turned into a repair** | §5. |
| **D4** plantings | **DONE** | Three, all caught; 152/152 overall — §8. |
| Renders | **DONE** | 55 NBA cards at desk and 390px; 37 carry the new sentence — §5. |
| Gate | **DONE** | 34 rows PASS, none FAIL; suite 974 tests, 0 failures — §9. |

## 2. The brief's causal claim was half right

> "NFL and NBA form factors are unadjusted for opponent."

**The NFL's already was adjusted.** `srs_diff` — "how good the two teams have
been, adjusted for who they played" — has been declared since **2026-08-28**,
beside `recent_form_diff`, which is exactly the arrangement D1 asks to be
built. No NFL factor was added, because there was nothing to add.

**The NBA half was right**, and its own rationale had said so since the day it
was written: `nba_net_rating_rolling` is "UNADJUSTED FOR OPPONENT, which is a
real limitation over a ten-game window in an unbalanced schedule". A factor
that declares its own limitation and then waits a week for someone to act on
it is the system working.

## 3. What was built

`nba_srs_diff`: the difference between the two clubs' Simple Rating System
ratings, in points, over ten. A club's rating is its average margin plus the
average rating of the clubs it played, solved by iteration — the same four-line
method college football already uses, chosen because it is **fully
inspectable**, not because it is the best available rating.

Solved over every completed game **this season before the game being
forecast**, so it cannot see the result it predicts. Bounded to the season on
purpose, unlike the ten-game form window beside it, which crosses the boundary
backwards: rosters move in the summer, and a rating averaging this October with
last April describes a club that no longer exists.

**ABSENT, not zero, below 150 league games** (`MIN_LEAGUE_GAMES_FOR_SRS`,
declared): on opening night every rating is zero, and a zero difference reads
as "these clubs are equally good", which is a claim nobody has the evidence to
make.

## 4. The bookkeeping found suppression, not collinearity

Standardised — coefficient × factor SD — over the stored record:

| | alone | **together** | r | n |
|---|---|---|---|---|
| nfl `srs_diff` | −0.083 | **−0.211** | 0.698 | 2,454 |
| nfl `recent_form_diff` | +0.048 | **+0.194** | | |
| nba `nba_srs_diff` | +0.200 | **+0.536** | 0.791 | 4,594 |
| nba `nba_net_rating_rolling` | −0.040 | **−0.440** | | |

Neither pair is near-collinear by any conventional bar — **VIF 1.95 and
2.67**, well under the usual 5. So the brief's retirement trigger did not fire,
and the honest answer to "are these collinear?" is no.

**But both members inflate — 2.5× and 4× in the NFL, 2.7× and 11× in the NBA —
and take opposite signs.** That is mutual suppression. The model is using their
**difference**, and once it does, neither coefficient describes its own factor
any more.

**The correlation was the wrong test.** The project's own precedent is the
right one: `cfb_asked_line` was retired because "its coefficient could not be
read as an independent effect, because it was not one." That test is about
**readability**, and these coefficients fail it at r = 0.79 just as surely as
that one did at −0.94.

## 5. Which means the card was about to print a false sentence

The "why" reads each contribution and names its declared phrase. Unmerged, a
reader was going to be told:

> Mostly it comes down to how good the two clubs have been, adjusted for who
> they played. **Pulling the other way, and not by a little: how the two clubs
> have been playing lately.**

It was not pulling the other way. It was carrying half of a difference.

**A sentence that is arithmetically derived and still false is the worst kind
this project can print, because it looks checked.** Every guard in the file
would have passed it: the direction came off the contributions, the ordering
came off the magnitudes, the phrase came off the declaration.

So a jointly-fitted pair is now described as **one reason**, summing the two
contributions — which is what the model actually did with them — under one
declared phrase:

> Mostly it comes down to how good the two clubs have been, against who they
> played and how lately. How much rest each club had points the same way.

The second sentence is a real reason that the false one had been crowding out.

**Nothing is hidden.** The Factors page still decomposes both separately,
because somebody auditing the model needs the parts. This is about the sentence
on the card, which is a claim about *why*, and a claim about why must be true.

**And the merge does not reach backwards.** It applies only where **both**
halves actually contributed to that row. A prediction written before the
adjusted factor existed carries only the raw one; describing it with the joint
phrase would tell a reader the model weighed "who they played" when it had no
such input — the reading equivalent of editing an old row. Planted.

Rendered: **55 NBA cards, 37 carrying the joint sentence, 0 still showing the
split reading**, at 1400px and 390px, no horizontal overflow.

## 6. D2 — the refit and the walk-forward

Refitted on the live record: **n = 4,914, converged in 4 iterations, nothing
dropped and nothing constant.**

Walk-forward, trained through 2023 and tested on 2024–2025, both models fitted
on the **identical selection**:

```
without nba_srs_diff   Brier .2468    84 of 2,453 test rows above 60%
with    nba_srs_diff   Brier .2401   835 of 2,453 test rows above 60%
```

**The weighted calibration gap moves 1.69 → 1.82 points, and that comparison is
not like for like.** The old model barely left the 50–60% bucket, so it was
being graded on a far easier distribution; the new one makes ten times as many
confident claims and is scored on those too. Reporting the gap as a regression
without that sentence would be the more flattering error, not the safer one.

**Labelled SANITY ONLY.** The factor set was chosen knowing these seasons.

`nba_srs_diff` is the **largest standardised coefficient in the NBA model**
(+0.536), and `srs_diff` is the largest in the NFL's (−0.211) — with the
suppression caveat in §4 attached to both.

## 7. Why only the NBA factor set was versioned

`nba:spread` → **fs4**. A model with a factor the previous one did not have is
a different model and its rows belong to a different curve.

**`nfl:spread` stays fs3, deliberately.** No NFL factor moved — what changed
for the NFL is prose. Versioning it would split a curve for a change that
cannot affect a probability, and **a version bump that means nothing is worse
than none: it teaches a reader that the marker is decorative.**

## 8. D4 — the plantings

| planted | caught by |
|---|---|
| an adjusted factor that reads raw margin | `context.srs_ratings` |
| a suppressed pair read as two reasons | `language.merge_jointly_read` |
| the merge reaching back onto a pre-fs4 row | the same |
| both form factors active with no dated note | the registry note check |

The first is planted as a **league where the answer is known**: four clubs, two
of which carry the identical −5.0 raw margin, one having lost twice to the best
club in the league and the other twice to the worst. Raw margin cannot separate
them; the adjustment rates them +4.17 and −9.17. A factor that promised
adjustment and returned raw differential would be invisible any other way — the
numbers would look reasonable and rank the clubs plausibly.

## 9. The gate

- Suite: **974 tests, 0 failures**, 0 skips.
- Plantings: **152/152**.
- `verify.py`: **34 rows PASS, none FAIL**; steps 2, 3 and 4 PASS. Step 1 run
  standalone — the full gate exceeds the ten-minute tool ceiling here, which is
  flagged in ITEM 2's close-out and still true.

## 10. Rulings taken in your absence

1. **NFL treated as already done rather than rebuilt.** The brief asked for an
   adjusted factor in both sports and the NFL had one. Adding a second would
   have been a duplicate under a new name.
2. **Neither pair retired.** The brief permits retirement "if near-collinear";
   measured, neither is, and the pair predicts better than either half (NBA
   Brier .2403 both, .2448 adjusted only, .2467 raw only). Retiring the raw
   member would cost real accuracy. **It was the reading that was wrong, not
   the fit** — so the reading was repaired and both stand, by dated note on all
   four factors, for the one version the brief scoped.
3. **NFL factor set not versioned**, per §7.
4. **The suppression repair was treated as in scope.** D3 asked for a "why"
   template; a template that produces a false sentence is not one.

## 11. What is PARTIAL, and what needs you

**Nothing in D is partial.** Two things carried in from earlier work:

- **ITEM 2's MLB rate fits are still landing.** `batter_home_runs` finished
  during this item — `RateFit`, n=118,345, Poisson, base rate 0.089 — and two
  remain. Each is ~139,000 rows through a pure-Python IRLS at roughly fifty
  minutes apiece.
- **The 390px title truncation** recorded in ITEM 2 is still open, in
  `docs/FOLLOWUPS.md`.

**The decision that is yours:** whether the suppressed pairs stay past this
version. The measurement is in `config.JOINTLY_READ_FACTORS` and on all four
factor notes. The case for keeping both is accuracy; the case against is that
no reader of the factor list can take either coefficient at face value, and a
note is a weaker guard than an absence.

## 12. Operator's verdicts

**Strongest thing:**

**Weakest thing:**

**What to do next:**
