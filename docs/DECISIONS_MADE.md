# Decisions made

Rulings that bind the build, each with the law or measurement behind it and
the date it was made. A decision recorded here is not re-litigated in a later
session; it is cited.

---

## 2026-09-01 — R-A: coverage is REPORTED, never used to choose

**Ruling:** questions are formed blind for every game on the slate. The share
of them that carry a published line is reported after the fact. Line coverage
never decides which questions get asked.

**The law that governs it:**

> **LAW 1. BLIND FIRST.** The model's probability is computed and WRITTEN TO
> THE DATABASE before any market line is fetched or passed into the prediction
> path. This is structural, not a convention.

The CFB brief asked for questions "only for lined games". Choosing *which*
questions to ask by what the market has priced makes the market an input to
the prediction path — not to the probability, but to the sample, which is
worse in a subtle way: the record would then consist only of the questions
bookmakers found worth pricing, and every calibration figure drawn from it
would describe that filtered slate while appearing to describe the sport.

The audit's import-closure scan enforces this independently: `gridiron.sports.
cfb` may not name a market table at all, so the filter could not be written
without failing the build.

**What happens instead.** After the snapshot step — which runs once the
prediction rows exist — the record reports how many of the slate's questions
carry a comparison. For Saturday 2026-09-05:

| market | coverage |
|---|---|
| spread | 60 of 60 (100%) |
| total | 57 of 57 (100%) |
| moneyline | 44 of 60 (73%) |

The practical gap is small because spread and total are near-complete, and the
missing moneylines are systematically the blowouts. A question with no line
renders as "no line" — an absent comparison, never a missing prediction.

**Operator's ruling, 2026-09-01:** "your reading is correct and LAW 1 governs.
Questions are formed blind for every game; coverage is reported, never used to
choose."

---

## 2026-08-31 — R-D: rankings are not a factor

Polls are votes. They lag the results they summarise, carry preseason
expectation for weeks after it is refuted, and are influenced by who plays on
television. A model reading one is partly modelling sportswriters, and when it
beats the market nobody could say which part did it.

Enforced structurally rather than remembered: the college context carries no
poll field, and `audit.check_no_rankings` fails by name on any context field or
factor body that names one. Planted and caught.

---

## 2026-08-31 — R-C: no college player props

Measured, not assumed. Zero prop rows on completed and upcoming games alike,
and a CFB event carries exactly one odds provider whose `propBets` endpoint
returns 404. Player game statistics exist and would resolve props; the gap is
the lines. The build shrank to the three team markets the evidence supports.

---

## 2026-08-31 — corrections: fitted at 50, applied from about 200

`MIN_TRAIN = 50` is the bar for FITTING a correction and looking at it.
Applying one additionally requires a 40-row holdout to beat the rows it was not
fitted on by a measured margin, which in practice means about 200 settled
predictions.

Both numbers are measurements, not choices. At fifty settled the holdout check
cannot tell a badly miscalibrated category from a well-calibrated one — 13 of
40 against 11 of 40 — and a bare "Brier improves" test passes a perfectly
calibrated category 38% of the time.
