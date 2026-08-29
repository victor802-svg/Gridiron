# Gridiron — methodology

What this predicts, how, what the numbers mean, and what would have to be true
before any of it deserved trust.

Read the last section first if you only read one.

---

## 1. What it predicts

Two kinds of question, both stated as a probability, both resolvable to exactly
0 or 1.

### Spreads

For every game in a week, one question: **does the home team cover
`line_asked`?**

`line_asked` is *ours*, not the market's. It is drawn from a ladder of four
pre-declared rungs — **−7.5, −3.5, +0.5, +3.5** relative to the home side — and
which rung a given game is asked at is decided by a CRC32 of the game id. That
rule is fixed, deterministic, reproducible across runs and machines, and depends
on nothing but the game's identity. It cannot be influenced by the model, by the
market, or by what would make the record look good.

**One question per game.** The alternative — asking all four rungs of every game
— would quadruple the sample while adding almost no information, because four
rungs of one result are four correlated looks at the same game. Every N on the
scorecard would then overstate how much had actually been learned. Rotating the
rung across games instead means that over a season all four are exercised and
the whole confidence range gets tested, without inflating anything.

Every rung ends in `.5`, so no question can push.

### Props

Five markets, each its own scoring category: **passing yards, receiving yards,
rushing yards, receptions, passing touchdowns.** For each, one question:
**does this player exceed `line_asked` in this stat?**

There is no combined "props" number and there will not be. Receptions and
passing touchdowns are different questions with different difficulty, and an
average across them describes neither. Each market has its own calibration
curve, its own fitted model, and its own 100-resolution gate.

**The slate is capped at 40 props a week, at most three per game,** filled by
round-robin across the markets in descending order of real-world liquidity. So
the cap bites on the thinnest market first, and the slate is never all
quarterbacks. Quality of resolution beats quantity of predictions: a forecast
nobody reads is not a forecast anybody can check.

The player is chosen by usage — the highest-volume qualifying player at the
position, with at least three prior games — never by how interesting the answer
might be. The line is the player's own rolling average over their last eight
games, shifted by one of three pre-declared offsets (−30%, 0%, +30%) chosen by a
CRC32 of the game, player and stat, then rounded to the nearest five and given a
trailing `.5`.

The offsets exist because asking exactly at a player's average would make every
honest answer 50%, and a scorecard of coin-flips teaches nothing.

**A prop whose stat cannot be read is VOID, not a loss.** If the player did not
appear, or the box score carries no value for him, the prediction reaches a
terminal void state with a stated reason and is excluded from every curve.

This reverses an earlier choice and the reversal is on the record. It used to
settle as a loss, on the reasoning that a player who did not play recorded zero,
so "more than 180.5 yards" was false. True as arithmetic, wrong as measurement:
it scores a *production* forecast on whether somebody was **active**, which is a
different question from the one asked.

Two things keep that from becoming an excuse. Selection excludes players already
ruled Out and players who have not appeared within two completed weeks, so a
non-appearance is a genuine surprise rather than something walked into — that
rule alone cut the measured void rate from 11.7% to 4.2%. And the **void count
is printed beside every prop curve**: a model that keeps choosing players who do
not play is telling you something, and burying it in the loss column would hide
it.

### Two forecasters, scored separately

Every question is answered twice and recorded as two independent rows:

- **statistical** — logistic regression on the declared factors.
- **llm** — a language model given the factor *values only*, which writes a
  narrative and states its own probability.

Neither sees the other. Their curves are never merged.

---

## 2. Blind first, and why it is the whole design

**The model's probability is computed and written to the database before any
market line is fetched.**

This is the single most important property of the project, and it is the one
most easily lost. A forecaster that has seen the line will anchor on it —
unavoidably, whether it is a regression with the line as a feature, or a
language model that has read the number, or a person who glanced at it. The
resulting calibration curve looks excellent. It is a measurement of the market's
accuracy with a little noise added, and it says nothing about the forecaster.

The point of Gridiron is the scorecard. An anchored scorecard is not a weaker
version of the product; it is a different product that resembles it closely
enough to be mistaken for it. So the ordering is enforced in four independent
ways:

1. **Schema.** The `games` table has no spread, total or moneyline column. Those
   values are split out at ingest into `market_lines_raw`, which only
   `gridiron.market` reads. The prediction path cannot find a line in the tables
   it queries because there is none there.
2. **Static analysis.** `gridiron.audit` walks the *transitive import closure* of
   `gridiron.model.predict` and fails if any module in it imports
   `gridiron.market`, or names a market column anywhere in code. Docstrings are
   exempt: a module must stay free to explain in prose what it refuses to do.
   The closure is currently 16 modules. `gridiron.audit` deliberately sits
   OUTSIDE it: the module holds the list of forbidden market identifiers, so
   importing it from the prediction path would make the guard flag itself.
3. **Runtime.** `blind.blind_window()` installs an import sentinel that raises if
   `gridiron.market` is imported while a prediction is being formed, and refuses
   to open at all if that package is already loaded. This forces the market
   import in `gridiron/run.py` to be lazy and to sit *below* the window, where
   the ordering is visible on one page.
4. **Database triggers.** A `market_snapshots` row is rejected if its prediction
   does not exist, or if its `fetched_utc` precedes the prediction's
   `created_utc`.

The ordering, in full:

```python
with blind_window():          # gridiron.market cannot be imported in here
    run = predict_week(...)   # probabilities computed AND WRITTEN
                              # window closes
from .market import lines     # ... only now does a line exist
lines.snapshot_many(...)      # attached to rows that already exist
```

A second, quieter form of the same discipline: every historical query in
`data/repo.py` takes an explicit `(season, week)` cutoff and returns only rows
strictly before it. A week-7 context is assembled from weeks 1–6. A factor
cannot read the result of the game it is predicting, because the query does not
return it.

---

## 3. The factors

Every factor is declared in one registry (`gridiron/factors/registry.py`) with
an activation date and a rationale saying **why it should causally matter**.
None were found by scanning history for what correlates. That method works — it
reliably finds things — and most of what it finds is noise wearing a suit. A
model built that way is not merely wrong; it is confidently wrong, and its
confidence is what makes it dangerous.

A factor's score runs from its activation date forward and is never backfitted
onto predictions made before it existed. `store.sync_registry` refuses to move an
activation date.

### Spread factors

| Factor | Added | Why it should matter |
|---|---|---|
| `asked_line` | 2026-08-28 | The question's own reference point. Our questions rotate across four rungs; a model that cannot see which rung it was asked is averaging four different questions into one answer. This is our line, never the market's. |
| `home_field` | 2026-08-28 | Home teams win more than away teams and always have: no travel, a familiar surface and snap count, crowd noise on the opposing offence, and the officiating tilt crowd noise produces. |
| `neutral_site` | 2026-08-28 | A neutral site removes home advantage from the home-listed team while still costing both sides a trip — a different game from the one `home_field` describes. |
| `rest_diff` | 2026-08-28 | Recovery time is physical: more healing, more practice reps, more film. The differential is what matters, since both clubs on a short week cancels out. |
| `short_week_diff` **(deactivated 2026-08-29)** | 2026-08-28 | A Thursday game after a Sunday is a categorically different preparation. Retired as a broken instrument, not a refuted idea: see below. |
| `short_week_either` | 2026-08-29 | REPAIR of the above. The short-week effect is a property of the GAME, not an asymmetry between the clubs: when both sides come off six days, both installs are cut and neither side's knocks have settled. Invisible to a differential that cancels. |
| `travel_kmiles` | 2026-08-28 | Distance flown costs sleep and adds logistics, for the visitor only. In thousands of miles; a cross-country trip is about 2.5 units. |
| `timezone_shift` | 2026-08-28 | Crossing time zones desynchronises the body clock independently of distance. A west-coast club at a 1pm Eastern kickoff is playing at what its body calls breakfast. |
| `srs_diff` | 2026-08-28 | Points for minus points against, adjusted for opponent quality, is the plainest statement of how good a team has been. Adjusting matters because an easy schedule inflates a raw differential. |
| `recent_form_diff` | 2026-08-28 | Rosters and schemes change through a season, so the last four games carry information the full-season average has diluted. Scored separately so we find out whether it adds anything over `srs_diff`. |
| `pace_sum` | 2026-08-28 | Plays from scrimmage set how many chances exist for the better team to express itself. A fast pairing widens the distribution of margins, which changes how often a spread is covered. |
| `injury_out_diff` | 2026-08-28 | Players listed Out do not play. Declared non-availability only — no judgement about how badly hurt anyone is, because a one-word status cannot support one and guessing at severity is how a model starts inventing information. |
| `qb_out_diff` | 2026-08-28 | Quarterback is the one position where the backup is usually a large step down and the offence is built around the starter. A positional fact, not a severity judgement. |
| `divisional` | 2026-08-28 | Division opponents play twice a year with continuous film and shared personnel knowledge, which compresses margins relative to what ratings alone suggest. |
| `wind` | 2026-08-28 | The weather variable that actually changes football: it moves the deep ball and the field goal, pushes teams to the run, lowers scoring. Above ~15mph the passing game measurably degrades. |
| `cold` | 2026-08-28 | Cold stiffens the ball and the hands and favours the run. Centred on 55°F, scaled per 20°F. |
| `precipitation` | 2026-08-28 | Rain and snow reduce grip and increase fumbles, compressing scoring. Probability of precipitation at kickoff. |
| `public_bet_pct` **(inactive)** | 2026-08-28 | A hypothesis, not an assumption: that heavy public agreement marks spots where the line moved on sentiment rather than information. Declared and scored like anything else — the only way to find out whether it is true. |

**`public_bet_pct` ships inactive.** Checked 2026-08-28: no free source publishes
ticket-count betting percentages with an API and a licence to depend on. The
options were to leave it off or to build a proxy from something correlated, and
a proxy would make it a factor about the proxy while still wearing the label
"public". It stays declared, dated and switched off, with the reason on the row,
so the hypothesis remains visible and can be turned on the day a real source
exists.

Indoors, the three weather factors read **0, not null** — a dome is a known
absence of wind, not missing data.

### Prop factors

| Factor | Added | Why it should matter |
|---|---|---|
| `prop_volume` | 2026-08-28 | Recent per-game attempts, carries or targets. Opportunity precedes production, and usage is stickier than efficiency. |
| `prop_efficiency` | 2026-08-28 | Yards per opportunity separates 12 targets for 60 yards from 6 for the same; the two have different distributions around one mean. |
| `prop_mean_vs_line` | 2026-08-28 | The rolling mean of the stat, relative to the line asked. The centre of the distribution the question is about. |
| `prop_volatility` | 2026-08-28 | Two players with the same average are not the same question: a high-variance player clears a high line more often and a low line less often. Without a spread estimate a mean cannot become a probability. |
| `opponent_allowance` | 2026-08-28 | Defences differ in what they surrender by position. Yards allowed per game to the position, relative to league average, carried with its own sample size. |
| `prop_player_status` | 2026-08-28 | A Questionable tag means fewer snaps on average even when active. Participation status only: 1 Out, 0.5 Doubtful, 0.25 Questionable. |
| `prop_volume_share` | 2026-08-29 | A player's share of his own offence's volume. Eight targets on a team that throws forty times is a different role from eight on a team that throws twenty, and the share is what survives when the offence changes pace. |
| `prop_snap_share` | 2026-08-29 | Offensive snap share: the most direct measure of opportunity there is, and it moves before production does when a role changes. The source keys on player NAME, so roughly one in twenty cannot be matched (measured join rate 95.1%); those games record the factor as absent, never as a zero, which would read as a healthy scratch. |
| `prop_game_script` | 2026-08-29 | Projected game script from the same opponent-adjusted ratings the spread question uses, signed for the player's own team. A team expected to lead runs to hold the lead; a team expected to trail throws to catch up. The same player has a different job in the two games. Derived from our ratings, never from a market number. |

`travel_kmiles`, `pace_sum` and the three weather factors also apply to props.

### Missing is an explicit state (v2)

A factor that cannot be measured for a game is **excluded from that game's
vector**. It does not receive a default, and it is never silently
indistinguishable from a real measurement that happened to be zero. Every
prediction records `present`, `absent`, `absent_detail`, `sources` and
`coverage`, permanently.

Before v2, an unmeasurable factor was substituted with a declared default —
usually `0.0` — and merely noted. That is how `precipitation`, unmeasurable in
66% of games, came to be fitted as if two thirds of the league's history had
been played in confirmed dry weather.

**An honest limit on that change, because it would be easy to oversell.** For a
linear model, excluding a term and imputing zero produce *identical*
coefficients: a row with `x = 0` already contributes nothing to that
coefficient's normal equations. This was verified on the real 2,639-game
training set — largest coefficient difference `0.00e+00` — and
`tests/test_missingness.py` pins the equivalence so nobody later believes the
change improved the fit.

What exclusion actually buys is downstream, and it is not small:

* The record distinguishes *"measured, and it was dry"* from *"we could not
  look"*. Those were previously identical, forever.
* `Fit.presence` reports how many training rows actually carried each factor:
  `srs_diff` 2,603 of 2,639, `wind` 2,468, `precipitation` 761. Under
  zero-imputation the last of those reported 2,639.
* A factor is scored only over the predictions where it was measured.
* A factor that never *varies* where it is measurable is dropped from the fit
  and named, instead of being fitted to 0.0 and read as "no effect".
  `precipitation` is exactly this: measurable only indoors, where it is always
  zero.

The substantive repair for `precipitation` is not the arithmetic. It is
fetching the forecast so the factor has a value at all — which forward
predictions now do, from Open-Meteo, cached and tagged with its source on the
prediction row.

### The two repaired instruments

Neither was a refuted hypothesis. Both were instruments that never measured
anything, and the registry says so on the row, because a reader who mistakes a
repair for a discovery will draw the wrong conclusion from both.

**`short_week_diff` → deactivated, replaced by `short_week_either`.** The
differential was non-zero in **1 game of 544**. The reason is the schedule, not
the idea: the NFL puts *both* clubs on a short week for a Thursday game, so the
difference cancels to zero exactly when the effect is largest. The level does
vary — non-zero in 38 of the same 544 games — and fits a real coefficient where
the differential fitted 0.000. The old factor's history stays; its v1 score
stands as recorded.

**`rest_diff` was kept, not duplicated.** A replacement "signed difference in
actual rest days" was proposed. That factor already existed under this name and
is a working instrument: non-zero in 206 of 544 games (37.9%), spanning −8 to
+8 days. A second one would have been perfectly collinear with the first, and a
test now fails if a duplicate rest factor ever appears.

### Factor set versions

A factor set is a different forecaster. Its record **begins at N = 0 on its
activation date**, and nothing earlier is backfitted onto it. Versions are
reported side by side and are **never summed**: a closed record and an
accumulating one describe different models, and their total describes neither.

* **fs1** — activated 2026-08-28. Closed. 48 forward predictions written, 0
  resolved.
* **fs2** — activated 2026-08-29. Current. 56 forward predictions written, 0
  resolved.

The interface shows both, with no total row, and says in words that a version
starting at zero is the expected state rather than a rendering fault.

---

## 4. The models

### Statistical baseline

Logistic regression, fitted by Newton–Raphson IRLS with ridge, in **pure Python**
— about 150 lines, no numpy, no sklearn (`gridiron/model/logistic.py`).

That is a deliberate cost. A probability you cannot interrogate cannot be
debugged when it is wrong, and the coefficients are meant to be read by a human.
Every prediction stores its factor values *and* the full decomposition of its
log-odds, so any forecast can be read back as "this factor pushed it this far,
in this direction", and the contributions plus the intercept sum exactly to the
log-odds. A test generates data from known coefficients and requires the fitter
to recover them.

Ridge is on by default and the intercept is never penalised: with twenty-odd
correlated football factors and a few thousand games, an unregularised fit will
happily hand a large coefficient to whatever one strange season suggested.

### LLM reasoning pass

Given the factor values and their rationales, nothing else. It writes a
narrative and states its own probability, recorded as a **separate prediction**
so the two forecasters can be scored against each other.

It never sees a line, and structurally cannot: `gridiron/model/llm.py` sits
inside the prediction import closure, which has no path to the market package.
The prompt explicitly tells it no market price is available and instructs it not
to reason about what "the market" thinks.

Spend is governed by a ledger: a daily USD cap checked **before** the call is
made, per-call cost written to `llm_calls`, and model routing that sends JSON
repair to the cheap model rather than paying reasoning rates twice. If the key
is missing, the budget is gone, or the API errors, the pass raises, the run tags
itself `llm_unavailable:<reason>`, and the statistical prediction stands alone.
**No probability is ever invented.** A fabricated forecast in a calibration
record is worse than a missing one, because later it is indistinguishable from a
real one.

---

## 5. What the numbers mean

### Calibration

Resolved predictions are bucketed by *stated confidence*: 50–60, 60–70, 70–80,
80+. Confidence is always ≥ 0.5 by construction — the model states a side and its
confidence in that side — so these are buckets of belief in a claim, not of
P(home).

A well-calibrated forecaster's 70% claims come true about 70% of the time. The
chart plots claimed against actual with the diagonal as reference, prints **N on
every point**, and draws a 95% interval on the observed rate so a thin bucket
looks as uncertain as it is.

The headline sentence always names the **largest gap** — the worst thing the
record says — never the most flattering bucket. A bucket below 20 resolved
predictions cannot be the headline and is drawn as provisional.

### Brier score and log loss

Both are proper scoring rules: lower is better, and both are minimised by
stating your true belief rather than by hedging or by exaggerating.

- **Brier** is the mean squared error of the probability. A forecaster who says
  50% to everything scores 0.25.
- **Log loss** punishes confident errors far harder. Always-50% scores 0.693.

Beating always-50% is a low bar and clears it merely by knowing which team is
better. The number that matters is the market comparison.

### The two baselines

- **Always 50%** — the floor.
- **The market** — the closing spread converted to a probability under a normal
  margin with SD 13.2 points, scored on exactly the same questions. This is a
  stated modelling assumption, written down in `gridiron/market/lines.py` rather
  than buried in an expression.

The model's own score is also reported restricted to the subset the market
priced, so the comparison is like for like rather than across different question
sets.

### The edge question

For predictions where the model was **more confident in its stated side than the
market was**, by more than 5 points, what fraction resolved in the model's
favour? The reverse subset — where the market was more confident — is reported
beside it, because showing only the flattering half of a comparison is how a
record lies while remaining technically accurate.

**Nothing renders below 100 resolved disagreements in that category.** Below the
threshold the interface states the shortfall and how many more are needed, and
the figure is not merely hidden by the front end — it is absent from the payload
the server sends.

The standing note stays regardless of what the numbers say:

> Beating the market on a small sample is the expected behaviour of luck, not
> evidence of an edge. A run of correct disagreements is what chance looks like
> at this scale.

### Curves are never merged

Spread and prop are different questions with different difficulty. Statistical
and LLM are different forecasters. Each factor-set version is a different model.
Averaging across any of these produces a curve describing nobody, and reliably
flatters, because the easy category dilutes the hard one.

### Factor scoring

Each factor is scored by removing its contribution from the log-odds of the
predictions it took part in and comparing the Brier score with and without it.
This is computed from stored contributions — nothing is refitted, and only
predictions made from the factor's activation date forward are counted.

It is an **attribution within the fitted model**, not an independent test of the
idea. And the report distinguishes three different kinds of nothing, because
conflating them retires good ideas for bad reasons:

- **no data** — the factor was defaulted in most predictions, so it has never
  actually been tested (`precipitation`: historical games carry no precipitation
  reading at all).
- **the input almost never varies** — untested rather than disproved
  (`short_week_diff` was non-zero in 1 game out of 544, because the NFL schedules
  Thursday games so *both* clubs are on a short week; the differential is
  structurally almost always zero).
- **no measurable effect** — the only one of the three that is a verdict on the
  hypothesis.

---

## 6. What the record currently says

Two records, kept apart on purpose.

### The forward record: N = 0 resolved

**104 predictions have been written before kickoff and none has resolved.**
56 under fs2 and 48 under fs1, written on 2026-08-29, with the first kickoff of
the 2026 season on 2026-09-10. Nothing can resolve until the games are played,
and the scorecard says zero rather than borrowing a number from below.

This is the only record that could ever become evidence.

### The backtest: pipeline sanity, not evidence

Walk-forward over 2024–2025, each season fitted only on seasons before it,
1,892 resolved predictions under the fs2 factor set.

| Market | N | Void | Brier | Log loss | Hit rate |
|---|---:|---:|---:|---:|---:|
| spread | 544 | 0 | 0.2141 | 0.6153 | 64.9% |
| passing yards | 261 | 27 | 0.1684 | 0.5164 | 77.0% |
| receiving yards | 275 | 13 | 0.2137 | 0.6166 | 65.1% |
| rushing yards | 273 | 15 | 0.2091 | 0.6071 | 64.8% |
| receptions | 275 | 13 | 0.2074 | 0.6039 | 66.9% |
| passing TDs | 264 | 21 | 0.2318 | 0.6584 | 59.1% |

Always-50% scores 0.2500 Brier and 0.6931 log loss. On the same 544 spread
questions, **the closing line scores 0.2011** against the model's 0.2141.

There is no combined row and there will not be one.

**On comparing this to fs1.** A Brier from a refit is not a result. Any change
in it, in either direction, is what refitting on the same seasons produces, and
it means nothing until fs2 has a forward record of its own. The numbers above
are stated, not offered as an improvement on anything.

### The worst thing the record says

Two findings, both unflattering, both reported because that is the point.

**Where the model disagrees with the market, it does worse.** Over the 544
spread questions:

| | N | Model said | Market said | Resolved model's way |
|---|---:|---:|---:|---:|
| model more confident by >5 pts | 207 | 65.4% | 52.5% | **55.1%** |
| market more confident by >5 pts | 148 | — | — | **70.3%** |

Where it deferred, it did better. That is the opposite of an edge, it survived
the move from fs1 to fs2 essentially unchanged, and
[docs/DIAGNOSIS.md](DIAGNOSIS.md) is a pre-registered attempt to find out why
that failed: none of the four hypotheses is supported, and the honest conclusion
recorded there is *the disagreements lose and we do not know why yet.*

**Passing touchdowns are badly calibrated.** The model claimed 54.3% in the
50–60% bucket and was right 41.8% across 98 resolved — overconfident by 12.4
points — and it is over-confident in every bucket of that market. Passing TDs
are a small-count Poisson-ish quantity being forecast by a model whose other
markets are continuous yardage; that is a plausible reason, and it is a
hypothesis for a later phase, not a finding from this one.

---

## 7. What would have to be true before trusting any of this

Nothing above is evidence of an edge. Specifically:

**The backtest is not evidence, and cannot be made into evidence.** Each test
season is fitted only on prior seasons, so it is out-of-sample in the narrow
technical sense. But the factor set, the question rules, the scaling constants,
the model form and the choice of what to measure were all made in 2026 by
someone who already knew how those seasons went in aggregate. No walk-forward
split removes that. This is why backtests live in a separate database marked
`kind=backtest`, why the interface shows a banner when pointed at one, and why
the verification run reports the retrospective and forward records separately
and never adds them together.

**The live forward record is currently N = 0 resolved.** 104 predictions for
2026 week 1 were written on 2026-08-29 (56 under fs2, 48 under the now-closed
fs1), twelve days before the first kickoff on 2026-09-10, with lines
snapshotted afterwards. None can resolve until the games are played. The
scorecard says zero, and it should.

Before any claim here deserves weight, all of the following would have to hold:

1. **Volume.** At least 100 resolved forward predictions in the specific
   category being claimed about — and there are now eleven such categories, one
   per market per forecaster, each gated separately — and 100 is a floor for showing a number at
   all, not a threshold for believing it. Several hundred, across more than one
   season, is where the discussion starts.
2. **A season it was not built in.** fs2 was declared with knowledge of
   2016–2025. Its first honest test is 2026 and beyond. A factor set that keeps
   changing never accumulates one — which is the cost of the v2 repairs, paid
   knowingly: fs1's forward record is closed at zero resolved and fs2 starts
   again from nothing.
3. **Calibration that holds in the tails.** Being right about 55% claims is
   easy. The 80%+ bucket is where a model's self-knowledge is actually tested,
   and it fills slowest.
4. **Beating the market on its own questions, not on different ones.** The
   comparison must be over the same question set, and it must survive the
   split — not just win in aggregate because props (where no market comparison
   exists) dilute the spread record.
5. **Surviving the disagreement test.** The edge figure must hold up over
   several hundred resolved disagreements. At n=207 the current answer is that
   the model's disagreements are worse than its agreements, which is the most
   common true answer and should be the prior.
6. **Stability under a factor change.** If adding or removing one factor swings
   the record materially, the record was noise.
7. **A reason for the disagreement failure.** The single clearest signal in the
   record is that the model's disagreements with the market resolve worse than
   its agreements. A pre-registered diagnosis could not explain it. Until it
   can, any claim of edge is contradicted by the project's own scorecard.

Until then the correct reading of every number in this project is: *the pipeline
works, and we do not yet know whether the model does.*

---

## 8. What this is not

Not a betting tool. There is no stake sizing, no bankroll, no Kelly criterion,
no bet recommendation, and no sportsbook or exchange integration — and there
will not be, because that is Law 5 and a guard scans the package's identifiers
for it on every run.

The output is a probability, the reasoning behind it, and a track record of how
often probabilities like it came true.

---

## 9. Reproducing all of this

```bash
python tools/verify.py
```

Runs the full test suite, plants every violation and requires every guard to
fire, runs one complete week end to end through resolution, and reports the
state of the live forward week — separately, and without borrowing one's numbers
for the other.
