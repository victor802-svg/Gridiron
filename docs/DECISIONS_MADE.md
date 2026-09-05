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

---

## 2026-09-02 — PrizePicks is UNAVAILABLE BY EVIDENCE

**Ruling (operator):** the LAW 5 amendment stands. The source is unavailable by
evidence. **No proxies, no bypass.**

**The evidence**, measured 2026-09-02 and recorded in
`docs/PRIZEPICKS_FEASIBILITY.md`: `GET https://api.prizepicks.com/projections`
answers **HTTP 403 with a DataDome CAPTCHA challenge** on the first request
from a clean client with an honest User-Agent. `api.prizepicks.com/robots.txt`
returns the same challenge — the host will not serve its own robots file.

**Unavailable by evidence, not by policy, and the distinction is the point.**
Nothing about PrizePicks was judged; a measurement was taken and it came back
403. If an official or documented feed appears, this becomes ordinary work and
the law already permits it — the amendment names the source, and the
one-module quarantine (`audit.market_source_faults`, planted and caught) is a
real guard that will hold when a lawful source arrives.

**What "no proxies, no bypass" forecloses**, written down so a later session
does not rediscover it as a clever idea: no rotating identities, no browser-
shaped User-Agent, no headless browser driven at the endpoint, no third-party
scraping service, no residential proxy. Each of those defeats the challenge
rather than satisfying it, and "unauthenticated, read-only, public" means
nothing if the first two words are engineered.

**The roster is rebuilt on a different axis.** The brief's ranking was volume ×
data availability, and volume was the half only PrizePicks could supply.
`docs/MARKET_ROSTER.md` is now built from **what our own loaders can already
resolve**, ranked by resolution data × per-slate count — both halves measured
here, neither guessed. Markets are built one per session from it.

---

## 2026-09-02 — NCAAF's 88% STRONG band: no change

**Ruling (operator):** no change. The extended ladder and the asked-line
redeclaration (GRIDIRON_18, 18B) are the fixes; **the record judges them.**

College football puts 15 of 17 picks in STRONG — 88% of a slate in the most
confident band, which distinguishes almost nothing. The measured cause is
recorded in `docs/closeouts/2026-09-02-cfb-ladder.md`: the college spread base
rate is **0.371, not 0.5**, so `cfb_expected_margin` runs high and the
probabilities it feeds run confident.

**Nothing is tuned to make the band look better.** A tier distribution adjusted
until it reads well is a distribution that describes the adjustment. The ladder
extension (2026-09-02, top rung 27.1% → 3.5%) and 18B's asked-line
redeclaration are changes with reasons; whether they worked is a question for
settled rows, and college football has **0 settled** so far.

Under ruling R2 this over-confidence is the first thing a reader sees, because
Picks opens on STRONG. That is the ruling working — the weakest band is in
front of the operator rather than buried three taps down.

---

## 2026-09-02 — the 119/119 correction stands; pushed history is never rewritten

**Ruling (operator):** the correction stands as recorded. **Never rewrite
pushed history.**

Commit `3fe3179` claims "120/120 plantings (three new)". The true figures were
**119/119, two new**. The error was mine, in a commit message, on a commit that
had already been pushed.

It was corrected **in the close-out**, in prose, rather than by amending or
force-pushing the commit. That is now the standing rule for this repository: a
wrong commit message is corrected forward, in a document that says what was
wrong and what is true. Rewriting the commit would make the record of the
mistake disappear along with the mistake, and a project whose whole claim is
"it keeps score of itself honestly" cannot edit its own history to look better
at it.

The same rule covers the amended-then-superseded, the miscounted, and the
mistaken: **append the correction, never revise the original.** It is LAW 3
applied to the repository rather than to the predictions.

---

## 2026-09-04 — ruling 1: totals and spreads become DISTRIBUTIONAL (Session E)

**Ruling (operator):**

> The blind object stops being a yes/no at a self-chosen rung and becomes the
> model's **forecast distribution** of the total or margin (mean + measured
> spread), written before any line exists. Once the market line is
> snapshotted, P(over the market's line) is **read off** that stored
> distribution — a deterministic read-out, not a new forecast, so **LAW 1
> holds exactly.**

**Its own session (GRIDIRON_18 Session E), probe-and-design first. The design
doc comes before any code**, and must cover: the blind object, storage,
resolution at the market line, calibration of a distribution, and what the
card shows when no line exists.

**Why it is right, in the record's own words.** Four sports declare a total and
all four ask it at the ladder rung nearest their own expectation. That makes
P(over) one half *by construction*, which two walk-forwards then measured:

| market | edge over always-the-base-rate |
|---|---|
| NBA total | **+0.0010** |
| NFL total | **+0.0016** |

The NBA's first version asked at the expectation itself and measured **+0.0006
with every one of 2,460 test rows in the 50–60% bucket** — a question with no
content. Quantising the ladder was the right local fix and did not touch the
cause: we choose the rung, so we choose the answer.

**What it ends.** "Asked at your own rung", and the `asked_line` dependency
entirely — including `nfl_total_asked_distance`, `nba_asked_line`,
`cfb_asked_line` and the 2026-09-03 asked-line redeclaration, all of which
exist to measure *the rounding residual of our own choice*.

**What it likely explains.** The spread-pair suppression. `srs_diff` and
`recent_form_diff` mutually suppress on the NFL and CFB **spreads** and behave
normally on both **moneylines** — a difference that has been demonstrated
twice and explained never. A margin distribution graded at the market's number
is the test.

**Not built in this session.** The ruling names its own session and its first
deliverable is a document. What this session owed it is this entry, so Session
E starts from the ruling rather than from memory.

---

## 2026-09-04 — ruling 2: a flagged method says so on the card, and never leads

**Ruling (operator):** until Session E lands, totals cards carry one line in
words —

> "totals asked this way have been a coin flip so far (NBA +0.001, NFL +0.002
> in walk-forward) — shown for the record."

— and **the hero never selects a market whose method is flagged this way.**

**Built 2026-09-04.** `config.FLAGGED_METHODS` declares which (sport, market)
pairs carry a finding; `language.METHOD_NOTES` holds the words. Split for the
reason every plain-words split exists: nothing a reader sees is composed
outside `language.py`.

**Derived, never a written row.** The map is built from `SPORT_MARKETS`, so a
sixth sport declaring a total is flagged the day it is declared. STEP 4 found a
declaration disagreeing with a hardcoded copy of itself **four times in one
session**, every one silent; a fifth copy is not written.

**UFC `rounds` is a total and is NOT flagged.** Its rung is fixed by the bout's
scheduled length — 2.5 for a three-rounder, 4.5 for a five — so it is not
chosen from the model's expectation and the construction argument does not
reach it. `questions.ufc_rounds_rung` is named `_rung` and every self-chosen
one is named `_asked`; the scan reads that distinction rather than a list.

**Rulings taken in the operator's absence, both recorded at the point of
decision:**

1. **The note is on the collapsed card face, not one tap in.** A caveat behind
   a tap is a caveat most readers never reach, and the reader taking the
   percentage at face value is exactly the one it is written for. It does not
   break the cards brief's R2 — "one number and the word for what it is a
   number of" is a rule about *numbers*, and this is a sentence.
2. **Every card flagged means NO HERO**, rather than a hero with a caveat
   attached. "Never" is the ruling's word. On the totals tab every card is
   flagged; the hero hides and the grid opens at rank 1.

---

## 2026-09-04 — ruling 3: the suppressed spread pairs stay one version

**Ruling (operator):** they stay, as previously ruled. **Session E is their
test.**

No code change. `config.JOINTLY_READ_FACTORS` continues to name the two
spreads and only the two spreads, and the scope is now demonstrated in two
sports rather than assumed from one.

---

## 2026-09-04 — ruling 4: the OFL font files are vendored

**Ruling (operator):**

> vendor the OFL woff2 files into the repo with the licence beside them — that
> is not the kind of binary the no-committing instinct protects against.

**The instinct was right and its scope was wrong.** "A binary nobody can diff
is a thing nobody can check" is why the app icon is drawn in code. A licensed
font carries glyph outlines, not behaviour, and the ruling draws the line
where it belongs.

**The instinct is answered rather than waived.** `web/fonts/SOURCE.md` records
each file's origin URL, size and SHA-256; `audit.check_vendored_fonts`
re-hashes the files against that table in the gate, and also fails on a binary
sitting in `web/fonts` that the table does not name — which is the quiet one.
A provenance table nobody re-derives is decoration.

**Two files, not six.** Latin and latin-ext, 40KB together. Everything this
interface renders is English composed in `language.py`; team and fighter names
are stored transliterated. A glyph outside the ranges falls through the stack.

**The variable font, not static instances.** The stylesheet asks for weight
**640** in two places, which no static instance can answer — it would round to
600 or 700 in silence.

**`.gitattributes` now exists and declares `*.woff2 binary`.** `core.autocrlf`
is true here and Git's heuristic would almost certainly spare a font; "almost
certainly" is the wrong standard for a file whose hash the gate enforces.

**The `--faint` deviation is accepted:** an unreadable N violates LAW 4.
`#5F6975` measured 3.17:1 on a card and is now `--faintest`; `--faint` is a
lighter tone and the worst pair is 5.54:1.

---

## 2026-09-04 — the superseded count was reporting less than it was hiding

Found while executing the rulings above, on the live NFL slate. Not an
operator ruling — a defect, and the fix is recorded here because the figure is
one the operator reads.

`views.week` held **two different definitions of "the same question"**. The
fetch drops a row a later row of the **same factor set** replaced — the door
`_superseded_ids` and `calibration` both use. The Python dedup then drops what
is left over a **broader** key, which is what catches the 2026-08-29 double
run *across* factor set versions. Both kinds of hiding are real; the reported
count was the difference between the two definitions and so only ever counted
the second.

**On the live NFL slate it reported 29 while hiding 45.** The close-out calls
this figure "how the operator finds out a prediction task ran twice", so a
count that is quietly short is the one thing it must not be.

**Counted, not subtracted.** One query over the slate, minus what the page
shows. There is no second definition left to drift.

---

## 2026-09-04 — Session E Part 2: the walk-forward refused the redesign

**Ruling (operator), on the tie-break §7 left open:** if the walk-forward
splits by sport, **ship per sport** — LAW 6 makes each sport its own decision,
and sports are never averaged to reach a verdict.

**It did not split. It said no in all four arms**, on **3,947 out-of-sample
games**, so the ruling was not needed and the machinery that would have
applied it is built and unused.

| arm | n | rung gap | read-out gap | rung edge | read-out edge | PIT |
|---|---|---|---|---|---|---|
| NFL total | 768 | 0.35 | **13.24** | +0.0011 | **−0.0281** | flat |
| NFL spread | 813 | 1.93 | **11.91** | +0.0036 | **−0.0164** | flat |
| NBA total | 1,223 | 3.98 | **9.60** | −0.0030 | **−0.0147** | flat |
| NBA spread | 1,143 | 2.57 | **12.39** | +0.0085 | **−0.0197** | flat |

**Nothing ships.** Every totals and spreads market stays on the rung it was on.
`config.DISTRIBUTIONAL_VERDICTS` records each verdict with its evidence, and
`audit.check_distributional_verdicts` makes it binding **in both directions**:
a market cannot be marked shipped against its own numbers, a shipped market
cannot keep its ladder, and a market left on rungs cannot lose one.

**Why it failed, and it is not what the design expected.** Every PIT came back
flat, so the distributions were honest about their own width. What failed is
the step after. The market's number lands closer to the result on **55–59%**
of games in every arm, so the gap between our number and theirs is mostly
*our error*, not our edge — and a read-out converts that gap directly into
confidence. Above 70% the read-out is worse than a coin flip; above 80% it is
reversed, 86% claimed against 43% actual.

> **A distribution can be perfectly honest about its own error and still be
> badly calibrated at somebody else's number, because that number is not a
> random point. It is a better forecast.**

**What this settles about the confidence floor**, which was an open operator
question from the 2026-09-04 close-out: on NFL totals a 70% floor would have
admitted 95 of 768 read-out questions, and those 95 are **precisely the ones
the method gets wrong** (38.3% and 42.9% actual). A floor selects for
confidence, and confidence was the failure mode. The floor question is still
the operator's, and it now has evidence attached.

**The suppression hypothesis is untouched and is no longer testable this way.**
The correlations stand — the two factors carry +0.26 and +0.24 against the
moneyline's label and −0.02 and +0.04 against the spread's, on the same games.
But removing the rung was the test, and removing the rung makes the model
worse, so whatever tests it next has to be something else.

**CFB's total never reached the walk-forward, and not for want of lines.** Its
expectation was fitted as the brief instructed: `actual = 47.31 + 0.109 ×
expectation`, n=1,639, **R² = 0.0093**. The sum of two points-per-game figures
explains under one per cent of a college total. There was nothing to
distribute. The slope is measured and deliberately **not** declared live:
adopting it would change which questions college football asks, which §8 says
is an operator ruling.

**What survives the NO:** the test itself, re-runnable; eight measured forecast
spreads with their N; and **NBA line coverage from 25 to 4,900 lined finals**,
which every future market comparison in that sport now rests on.

---

## 2026-09-04 — rulings on the Session E result

### Ruling 1: the NO stands, and the finding goes where readers are

**Ruling (operator):** *"The NO stands as recorded; §9 is the result; nothing
amends the sections above it. Add the 'reach is not calibration' finding and
the market-closer figure (55–59%) to METHODOLOGY §6 in plain words."*

`docs/DISTRIBUTIONAL.md` is unchanged and stays unchanged: §9 records what the
test said, and everything above it is exactly as written before the test ran.

**What moved is where the finding lives.** It was in a close-out, which is a
document about a session. `METHODOLOGY.md` §6 is the document about *the
project*, and it already keeps a section headed "the worst thing the record
says" — that section now holds three findings rather than two.

**In plain words, and the plainest sentence is the point:**

> **Being able to say something is not the same as being right about it.**

The method that could reach 80% was wrong there; the method that can only
reach 54% is accurate to within a third of a percentage point.

### Ruling 2: CFB's slope is recorded and not adopted

**Ruling (operator):** *"CFB totals: the measured slope (R² 0.0093) is recorded
and NOT adopted. CFB keeps asking totals at rungs, carrying the coin-flip line;
a market the model cannot inform is shown as such, not hidden."*

`questions.CFB_TOTAL_FIT_MEASURED` records the fit — intercept 47.31, slope
0.109, n 1,639, R² 0.0093 — with `adopted: False` and the reason.

**Adopting it would have made every college total the same number.** The
fitted line is 47.31 plus a whisker, so it would ask about the league average
on every game in the country and would *look* more accurate for doing so: the
residual drops from 20.85 to 16.31. That is not a better forecast, it is a
forecast that has stopped trying, and its apparent confidence would come from
college totals clustering rather than from anything known about the game.

**"Shown as such, not hidden" is now structural.**
`audit.check_no_market_is_hidden` fails if a market with a recorded verdict,
or a market carrying a method flag, stops being declared by its sport. The
temptation it guards against is a kind one: a slate that quietly loses its
weakest question looks sharper and is less honest, and a reader cannot tell
the two apart.

### Ruling 3: no confidence floor on rung game markets

**Ruling (operator):** *"No confidence floor on rung game markets — the floor
selects for confidence, and this session showed confidence was the failure
mode for the method that had any."*

`config.GAME_MARKET_MIN_CLAIM = None`, dated. **`None` is a decision, not an
omission**, and the difference is that adding a floor now means overturning
this entry rather than filling a gap.

**The evidence is this session's own.** Of 768 NFL totals questions under the
read-out, the 95 that cleared 70% were right **38% and 43%** of the time
against **49%** for the ones that did not. Confidence ran backwards; a floor
would have kept precisely the wrong questions.

**And the rung method cannot reach 70% at all** — an NFL total asked at its own
rung is confined to 45.8%–54.2% by construction — so a floor above about 55%
would empty the slate and one below it would be decoration.

**What replaces it is already on the page:** the tier chip with its own settled
record, and the coin-flip line in words. A reader is told what a claim is worth
instead of having weak claims hidden from them — **the same choice ruling 2
makes about CFB, for the same reason.**

**Props keep their floor**, and the situation is genuinely different: a prop is
asked at a rung a source actually posts, one subject at a time, against a daily
cap of 25, so refusing the ones the model is unsure of **chooses between
questions**. A game market asks about every game on the slate; refusing there
**hides** them.
