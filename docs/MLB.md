# Baseball

Written 2026-08-29, at the end of phase S2.

MLB went first among the new sports for one reason: it resolves daily. Football
gives you sixteen questions a week and a five-month wait for a hundred of them.
Baseball gives you fifteen a day, so the forward record — the only record that
means anything under LAW 4 — starts accumulating within a week instead of within
a season. Everything below about baseball being hard is a reason to want that
sample sooner, not a reason to have picked a different sport.

---

## What is predicted

**The moneyline, and nothing else.** One question per game: *does the home club
win?*

No spread, no total, no props. Three deliberate omissions:

- The **run line** is a fixed -1.5/+1.5 spread, which makes it a different
  question rather than a rung on a ladder, and it resolves on a margin that a
  single ninth-inning swing rewrites entirely.
- **Totals** would need a run-scoring model, which is a separate instrument from
  a win model and would arrive undeclared and unmeasured.
- **Props** would need per-batter matchup data at a granularity the free source
  does not publish, and there is no free line to score them against anyway.

One question per game also means the home club is always the subject. Asking
"does the away club win" as well would be the exact complement, so the model
would learn a mirror of itself and every game would enter the record twice.

That decision has a consequence, and it cost a factor — see `mlb_home_away`
below.

## The factors

Seven declared, six active. Lean and pitcher-centric on purpose. A single
baseball game is close to a coin flip — the best club in a season wins about 60%
of its games and the worst wins about 40% — so the signal available per game is
small, and a wide factor set would mostly be fitting noise with more parameters.

| Factor | Fitted weight | Present in | Backtest verdict |
|--------|--------------:|-----------:|------------------|
| `mlb_team_offense_rolling` | +0.260 | 4,781 / 4,859 | no measurable effect either way |
| `mlb_park_factor` | −0.386 | 2,425 / 4,859 | no measurable effect either way |
| `mlb_starter_rolling_perf` | +0.112 | 3,792 / 4,859 | no measurable effect either way |
| `mlb_bullpen_recent_load` | −0.028 | 4,830 / 4,859 | no measurable effect either way |
| `mlb_team_rest_travel` | −0.153 | 4,844 / 4,859 | no measurable effect either way |
| `mlb_starter_rest_days` | +0.006 | 4,605 / 4,859 | no measurable effect either way |
| `mlb_home_away` | — | constant | **deactivated — broken instrument** |

Every one of the six comes back "no measurable effect either way" on 2,430
resolved predictions. That is a real result and it is not a good one, but it is
also the expected one at this sample size for effects this small: the largest
delta-Brier among them is +0.0012, which is well inside what 2,430 coin-flip-ish
questions can distinguish from zero. It says these factors have not been shown
to help. It does not say they have been shown not to.

`mlb_park_factor` is present in only half the training rows, and that is correct
rather than broken: it is measured from PRIOR seasons at the venue, so 2023 — the
earliest season loaded — has no prior to measure from. It is absent for those
rows rather than defaulted.

### The factor that could never vary

`mlb_home_away` is **deactivated as a broken instrument, not as a refuted idea**,
and the distinction is the one this project keeps insisting on. The backtest
reported it constant across all 4,859 training rows, so there was nothing to fit.

The cause is the shape of the question. Every MLB question asks whether the
*home* club wins, so the home side is home in one hundred percent of rows and the
factor returns 1.0 every time. NFL's `home_away` varies because its subject
rotates between the two clubs across the spread ladder; a moneyline has no ladder
to rotate on.

This is the third time this failure has appeared — `short_week_diff` never varied
because the NFL schedules both clubs onto a Thursday, and `precipitation` never
varied because the source reported it as zero. The pattern is now clear enough to
name: **a differential is only an instrument if the two sides can actually
differ**, and whether they can is a fact about the sport's structure, not about
the hypothesis.

There is no repair to make here and none is offered. The quantity is still
measured — it just lives in the intercept, which fitted at 0.0913, putting a
league-average home club at **52.3%**. That is baseball's home-field advantage,
measured rather than assumed, and smaller than football's as expected.

### The factor that was asked for and is not here

`mlb_asked_line` was in the brief by analogy with NFL's `asked_line`. It is not
declared, for the same reason `mlb_home_away` is now inactive: a moneyline has no
rungs, so `line_asked` is NULL on every MLB prediction and the factor could not
vary. The reasoning is written out at the foot of
[`factors/mlb.py`](../gridiron/factors/mlb.py) so a later reader finds it where
they would look for the factor.

## The unannounced starter

This is the missing-data case that matters in baseball. A club names its starting
pitcher anywhere from a week ahead to ninety minutes before first pitch, so a
slate written in the morning routinely has games where nobody knows who is
pitching.

When the name is not published, `mlb_starter_rolling_perf` and
`mlb_starter_rest_days` are **absent from the feature vector** — excluded from
that row's normal equations entirely — never zero. This is the explicit-absent
rule from D2, and baseball is where it earns its keep: a defaulted starter would
mean silently predicting every unannounced game as though both arms were league
average, which is a strong claim disguised as a missing value.

The card says so on its face. On the first forward slate, five of fourteen games
were in that state.

---

## Backtest — pipeline sanity, not evidence

2025, walk-forward, fitted on 2023–2024 only. 2,430 predictions, 2,430 resolved,
0 void.

```
Brier    0.2468   vs always-50%: 0.2500
log loss 0.6867   vs always-50%: 0.6931
hit rate 0.5514
```

Calibration is good, which is the one genuinely positive thing here:

| bucket | n | claimed | actual | gap |
|--------|--:|--------:|-------:|----:|
| 50–60% | 2,232 | 0.540 | 0.545 | +0.005 |
| 60–70% | 195 | 0.623 | 0.626 | +0.002 |
| 70–80% | 0 | — | — | — |
| 80%+ | 3 | 0.949 | 0.667 | −0.283 *(provisional, n=3)* |

The model says 54% and is right 54.5% of the time. It is honest about how little
it knows, which is the property this project cares about most. Note also that 92%
of its predictions land in one bucket — baseball moneylines simply do not spread
out the way a spread ladder does.

### The market wins, and by more than in football

The brief said to expect this and to say so plainly if it happened. It happened.

Read as raw Brier the baseball gap looks *smaller* than football's:

| | n with a line | model | market | market ahead by |
|-|--:|--:|--:|--:|
| NFL spread | 544 | 0.2141 | 0.2011 | 0.0130 |
| MLB moneyline | 2,092 | 0.2470 | 0.2417 | **0.0053** |

That reading is wrong, and the reason is worth being explicit about. Brier scores
compress toward 0.25 when the questions are near coin flips, so baseball's whole
scale is smaller and every gap on it shrinks with it. Normalising each score
against how much there was to know — skill relative to a forecaster who says 50%
to everything — reverses the ordering:

| | model skill | market skill | **model as a share of market skill** |
|-|--:|--:|--:|
| NFL spread | 14.36% | 19.56% | **73.4%** |
| MLB moneyline | 1.20% | 3.32% | **36.1%** |

In football the model captures about three quarters of the skill the market
demonstrates. In baseball it captures about a third. **The market beats this
model by more in baseball than in football, exactly as expected**, and the small
absolute gap is an artefact of the sport, not a sign of a close contest.

The disagreement split says the same thing more bluntly:

| | model more confident | market more confident |
|-|--:|--:|
| NFL | n=207, right **55.1%** | n=148, model right 70.3% |
| MLB | n=618, right **48.9%** | n=508, model right 64.2% |

When this model confidently disagrees with a baseball line, it is right slightly
**less** than half the time. That is worse than a coin flip on the exact
questions where it is most sure. Football's equivalent number was at least above
50%, and D1 already concluded that even that was not evidence of anything.

The standing note applies unchanged: this was produced over seasons already
played, by a factor set chosen with knowledge of how those seasons went. It shows
the pipeline runs. It shows nothing about whether the model has an edge, and
under LAW 4 nothing in this file is a claim — the forward MLB sample stood at 25
when this was written, and the threshold is 100.

### Coverage

86.1% of backtest questions (2,092 of 2,430) had an ESPN line to compare against.
The other 338 are scored against the outcome as normal and are simply absent from
every market comparison, counted rather than filled in.

---

## Data

- **Games and probables**: `statsapi.mlb.com`. No licence granted; MLBAM
  copyright; personal non-commercial use only. Chosen over `pybaseball`, whose
  terms are less permissive and which drags in a pandas/lxml stack this project
  does not have.
- **Lines**: ESPN's public core API, licence **NONE STATED**. Where it publishes
  nothing, cards say "no line available" and the edge figure states it cannot be
  computed. Nothing is proxied.
- Loaded: 7,289 games across 2023–2025, plus the running 2026 season.

Full terms, rate-limit handling and the club-abbreviation aliases are in the
[README](../README.md#data-sources-and-licences).

---

## The forward record

Started 2026-08-29. **25 predictions standing**, every one written before its own
first pitch, every market snapshot timestamped after its prediction.

Six further predictions from the first run were **voided**, and the reason is
recorded on each of them: they were written at 19:17 UTC for games that had
started at 17:05. No line was seen — LAW 1 held — but a forecast written after
first pitch is not a forecast, and scoring it as one would have flattered the
record with six games whose state was already partly known.

The prediction loop now refuses to write into a live database for a game already
under way, and says which game and why. A backtest database is exempt, because
retrospection is its entire purpose and it is bannered as such.

At roughly fifteen questions a day, the 100-prediction threshold for MLB
moneylines arrives in early September 2026. That is the first date on which
anything in this file can begin to become a claim.
