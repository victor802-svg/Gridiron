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

---

## R4 — the spread rung is chosen against the expected margin

**Decided 2026-09-01. Measured first, then ruled on.**

**What was measured.** The college slate of 2026-09-05, 177 picks:

| band | moneyline | spread | total |
|---|---|---|---|
| 50-59% | 4 | 5 | 16 |
| 60-69% | 1 | 6 | 10 |
| 70-79% | 5 | 8 | 12 |
| 80-89% | 17 | 12 | 7 |
| 90-99% | 33 | 29 | 12 |

135 of 177 (76%) claimed 70% or better. Split by division, the spread
confidence was not spread evenly at all: **77% of cross-division games claimed
90%+, against 20% of FBS-against-FBS ones.** The ten most confident spreads
were ten FCS visitors, at rating gaps of 12 to 54 points, asked at rungs of
-0.5 to -24.5.

**It was not a scale bug, and that had to be ruled out first.** The probability
path is `logistic.Fit.predict` — a sigmoid over fitted contributions. **No
standard deviation appears in it anywhere.** The measured `MARGIN_SD_BY_SPORT
["cfb"] = 22.46` reaches only `lines.implied_cover_probability`, the market
comparison, where it produces a mean implied cover probability of **0.739**
across the same sixty games: applied sanely, not too small.

So the second explanation holds: **fixed rungs far from the expected margin.**
Asking whether a team favoured by sixty covers -0.5 is not a question, and a
record full of non-questions measures the schedule rather than the model.

**The ruling.** Spread rung selection is now the declared rung NEAREST the
expected margin, per sport, from the same declared ladder. The expected margin
is built from stored ratings plus a measured home-field constant
(`CFB_HOME_MARGIN = 9.79`) — blind by construction, and it has to be, because
the rung is one of the model's own inputs and must exist before the model runs.
Activated `CFB_RUNG_RULE_ACTIVATED = "2026-09-01T00:00:00Z"`.

**The fit was retrained, and that is part of shipping the rule rather than a
separate act.** `training_set` builds each row by asking a completed game the
same question a live slate would be asked. Change how the question is formed
and the two halves stop matching: the stored fit had learned a coefficient for
`cfb_asked_line` when the line was a rotation independent of team strength, and
the live path now asks at a line that is a step function of the rating
difference. Refitting re-estimates the same declared factors over the same
games under the question the system now asks -- nothing is added, removed or
re-dated, so LAW 2 is untouched.

| | rotated rungs | margin rungs |
|---|---|---|
| rows | 1,761 | 1,769 |
| intercept | +0.3068 | +0.0867 |
| `cfb_srs_diff` | +0.0851 | +0.0655 |
| `cfb_asked_line` | +0.1003 | +0.0802 |
| `cfb_rest_diff` | -0.0069 | -0.0085 |
| `cfb_travel_kmiles` | +0.1310 | +0.1556 |
| `cfb_non_fbs_visitor` | +2.1012 | +1.9122 |

The eight extra rows are games that finished between the two fits -- 1,769 is
every completed college game in the record, checked -- not a change in what
qualifies. The intercept moving toward zero is the rule working: a slate of
near coin flips has no reason to lean.

**LAW 3: the sixty spreads of 2026-09-05 stand as written.** They were asked at
rotated rungs and they are a record of what was claimed, not a draft. A
synthetic re-ask was run for this note only and stored nowhere. Three columns,
because the rung change and the refit are separable and it is worth seeing
which did the work:

| | as written | margin rungs, old fit | margin rungs, refit |
|---|---|---|---|
| >= 70% | 49 | 36 | 37 |
| >= 90% | 29 | 12 | 6 |
| mean claim | 0.846 | 0.759 | 0.740 |

The rung change halves the 90%+ claims; the refit halves them again. STRONG is
now rare on a slate where it used to be the default.

**Two things that re-ask also showed, recorded rather than fixed here:**

1. **The ladder is too short for this sport.** 45 of the 60 games landed on
   -24.5, the end of the ladder, because cross-division expected margins run to
   sixty and the ladder stops at 24.5. The rule is doing the best the ladder
   allows. Widening a declared ladder is its own dated act, not a side effect
   of this one — see FOLLOWUPS.
2. **`cfb_asked_line` is now a coarsened copy of `cfb_srs_diff`.** The rung is a
   step function of the rating difference by construction, so the two factors
   carry the same information. Ridge will absorb it, but the "why"
   decomposition will now split one signal across two names. Retiring or
   reworking a declared factor is a LAW 2 act with its own dated note — see
   FOLLOWUPS.

**Guarded** by `audit.rung_selection_faults` / `check_the_rung_is_chosen_by_
margin`, an AST read of every `*_spread_rung`. A rotation (`stable_index`) is
permitted **only** inside an `if <parameter> is None` branch — the declared
absence, for a team with no rating yet. Two plantings fire by name:
`plant_a_rung_chosen_by_rotation` and `plant_a_rung_chosen_by_the_market`. The
scanner checks its own known-positive and known-negative at import.

---

## E2/R1 — the tab records replaced the header's season-record strip

**Decided 2026-09-01, forced by a measurement rather than chosen.**

The brief asked for per-sport records on the tabs ("MLB 33-18"). Adding them
saturates the header exactly: the separate `.season-record` strip, which showed
the ACTIVE sport's current-season record, was left with **4px of width for 67px
of content at every width** — present in the layout, invisible to a reader, and
still asserted by two browser tests.

Two figures about MLB sitting adjacent with different scopes and no labels
distinguishing them would have been confusing even with room for both.

**So the strip is gone from the header.** The tabs say strictly more: every
sport's record rather than only the active one's, all time, with settled,
written and void counts on the hover. `views.season_record` and
`/api/record-line` remain — the season figure is still available and is shown
on the Record page — so this removes a surface, not a fact.

A previous session fought to keep that strip (it cut the words "this season"
to make it fit), so this is recorded rather than left in a diff. **Reversible:**
restore `#record-line` in `index.html` and `renderRecordLine` in `app.js`, and
the tab records would have to give back about 150px to make room.

The old test's real finding is preserved: it caught that a record with no sport
label makes two empty sports look identical, so switching between them changes
nothing on screen. The replacement test asserts every tab is distinct.

---

## Operator calls withdrawn 2026-09-02 by ruling; notifications retained

`operator_calls` — the operator's own side-and-tier calls on questions the
model had already answered — was built on 2026-09-02 (GRIDIRON_12,
`docs/briefs/2026-09-02-calls.md`) and withdrawn the same day by operator
ruling (GRIDIRON_16 R1). It stood for four phases: schema and rules, entry on
the desk and the phone, a third forecaster on the Record tab, and the notifier.

**Removed by surgery, not by revert**, because the notifier shipped in the same
brief and had to survive: the table and its three append-only triggers, both
`/api/calls` routes, the rail block, the row-expansion block, the tile marks,
the "you (informed)" forecaster and its tier table, the model-versus-operator
comparison line, and the digest's calls line.

**Kept, because each earned its place independently of the feature that
prompted it:**

- The **notifier** (`gridiron/notify.py`, the `notifications` table, both
  channels, quiet hours). It answers a question the calls feature did not
  raise: the appliance once sat stalled for two days with every screen green.
  Its results message lost the operator clause — `", you 2 of 3"` — and
  nothing else.
- **`subjects.py`'s canonical side map**, including the `not_cover` /
  `"fail to cover"` unification. A call's side validation is what first forced
  the two spellings into one place; the record still holds both, and the door
  that names a side is still `side_named`.
- The **forecaster selector mechanism**, which now carries Picks as well as
  Record (GRIDIRON_16 R5).

**Two guards were withdrawn with it**, and the reasoning is worth keeping
because it will come up again. `audit.call_stake_faults` scanned
`operator_calls` for a column expressing an amount — the LAW 5 tripwire on the
closest thing this project ever built to a stake. `merged_forecaster_faults`
carried a rule that an informed forecaster's label must say "informed". Both
now guard something that does not exist, so both could only ever pass. **A
guard that cannot fail is a guard on faith**, and leaving them would have
reported a clean scan forever while proving nothing. LAW 5's general identifier
scan is untouched, and `STAKE_COLUMNS` survives because that scan reads it.

**Reversible**, but not cheaply: the brief at `docs/briefs/2026-09-02-calls.md`
stays as the record of what was built, and `db.WITHDRAWN` drops the table
forward, so a live database that held calls no longer holds them. Restoring the
feature means restoring the rows too, and there are none.

**The one row that existed was a test's.** Nothing a person recorded was lost.
