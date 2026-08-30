# MLB player props

Four markets, declared 2026-08-30: **batter hits, batter total bases, batter
home runs, pitcher strikeouts.** Each is its own scoring category with its own
100-resolution gate, and none of them is ever merged with another or with the
moneyline.

This document records what was measured before anything was built, because
several of the measurements contradicted what the project believed at the start
of the session and one of them contradicted a claim already written into the
code.

---

## What the sources actually carry

### statsapi.mlb.com — the stats

Everything the factor set assumes is present. Measured 2026-08-29 against a real
boxscore and game log:

| field | where | note |
|---|---|---|
| `hits`, `totalBases`, `homeRuns`, `atBats`, `plateAppearances` | hitting game log | one request per player per season |
| `strikeOuts`, `inningsPitched`, `battersFaced`, `homeRuns` | pitching game log | a pitcher's `homeRuns` is home runs **allowed** |
| `batSide`, `pitchHand` | `/people?personIds=...` | 300 ids per request; 1,581 players in 5 requests, 100% coverage |
| batting order | schedule `hydrate=lineups` | **see below** |

**The boxscore path was rejected on cost.** One boxscore is 178 KB and a season
has 2,430 games: a third of a gigabyte of cache per season, for numbers the game
log already carries. The loader's original docstring warned about exactly this
and the warning was right.

**`homeRunsAllowed` never needed deriving.** The feasibility probe saw `None`
for it, which is true of the *boxscore* path. The game log carries it: measured
across 24,433 re-parsed starts, 24,433 have it. The derivation the brief asked
for was for a problem the chosen path does not have, and inventing one would
have meant attributing the bullpen's home runs to the starter.

### The lineup finding, which changed a factor

The hydrated `homePlayers` / `awayPlayers` arrays **are** in batting order —
checked against the boxscore's own `battingOrder` field on 12 team-games, 12
agree, 0 disagree. One request per date range covers every game on it.

But: **a scheduled game carries no lineup at all.** Measured 2026-08-30, across
three future dates, **0 of 41 games** had one; they are all `Preview` until
roughly two hours before first pitch.

So tonight's batting slot is not knowable when a forecast is written, and a
factor reading it would be reading the future. This corrects the feasibility
report, which said lineup slot was available — true of a game already played,
which is not the case a forecast is in.

What the factor set does instead:

* `mlb_batter_expected_pa` — plate appearances per game over the window. A fact
  about games already played, carrying the same information the slot was a proxy
  for: a leadoff hitter gets more trips than a nine-hole hitter.
* `mlb_batter_lineup_slot` — the batter's **recent** average slot over his last
  five starts. Also a fact about the past, and a different one: it is the
  manager's judgement about the player, where expected PA is the traffic in
  front of him.

### ESPN — the lines, and a claim that was wrong

`market/sources.py` said, as a checked fact: *"ESPN's odds documents carry a
`propBets` link that returns nothing usable."* Re-checked 2026-08-30, **that is
false for MLB.** One 14-game slate carried **1,306 prop rows, 1,084 naming an
athlete**, covering all four markets.

The original reading was of one NFL document. The mistake was not the reading;
it was generalising one sport's reading to three, by a comprehension over
`SPORT_PROP_MARKETS`, and writing the generalisation down as measured. The list
is now stated per market, and NBA's entry says plainly that it has **not** been
re-checked — an untested market and a market with no source must not read the
same.

Where the lines sit, measured on that slate:

| market | ESPN rows | lines |
|---|---|---|
| batter hits | 216 | 0.5 (96%), 1.5 (4%) |
| batter total bases | 81 | 1.5 (100%) |
| batter home runs | 108 | "1+" (100%) — the over at 0.5 |
| pitcher strikeouts | 24 | 5.5, 4.5, 6.5, 3.5 |

---

## The asked line: a declared ladder

**Ruling R1.** The rungs are fixed in `config.MLB_PROP_LADDER`, declared
2026-08-30, and the rung a question is asked at is **the one nearest the
subject's own rolling mean**. Ties go to the lower rung, stated rather than left
to whichever way `min` breaks them.

    batter_hits          0.5, 1.5
    batter_total_bases   1.5
    batter_home_runs     0.5
    pitcher_strikeouts   3.5, 4.5, 5.5, 6.5

This replaces the NFL offset mechanism **for MLB only**. NFL's stands exactly as
recorded: its props were asked at the player's own average shifted by a declared
offset, and every NFL prop snapshot reads
`unavailable:no-free-prop-line-source` — 72 rows of "we looked, and there was
nothing".

It is blind by construction. The set is declared in advance; only our own stats
choose the rung; nothing is fetched inside the blind window. And it buys the
thing this project has never once had on a prop: asking where the market
answers makes a real prop-vs-market comparison possible. A self-generated 1.2
hits would be a question no book prices, so the comparison would stay absent
even though lines now exist.

A rung off the ladder is **refused by name** (`questions.assert_on_ladder`). An
off-ladder question is incomparable twice over — no book quotes it, and no other
prediction in its category shares it — and both losses are silent.

---

## The side, which had to be derived

A prop row carries a line and a price and **no over/under label**. The union of
keys is `athlete, competition, current, lastUpdated, odds, open, provider,
type`. One pitcher's 5.5 appears twice, at −136 and +107, and nothing says which
is the over.

This is the ESPN spread-sign shape exactly: a number that looks right and is
right about half the time.

**Ruled out — "the shorter price is the over."** Forbidden as a method, and
measurably worse than it sounds: the first row in document order carries the
shorter price in 62.7% of pairs, close enough to noise to be indistinguishable
from it. The underlying claim is simply false for any subject whose line sits
above their mean.

**Ruled out — cross-rung monotonicity**, the originally specified derivation.
Correct reasoning, no data: measured on a full slate, **0 of 354 subjects were
quoted at more than one rung**. Every subject gets exactly one line. There is
nothing to compare.

**What works: the milestone anchor.** The slate carries two kinds of prop
market. *Totals* are two-sided and unlabelled. *Milestones* — "Hits Milestones",
"Total Bases Milestones", "Strikeouts Thrown Milestones", "Home Runs
Milestones" — are **one row per subject**, displayed "1+", "2+", "6+", and
one-sided by construction: "2+ total bases" has no other half.

And a milestone at K+ is the *same event* as the over at K−0.5. "6 or more
strikeouts" and "over 5.5 strikeouts" are one question with two names. So the
milestone's price states P(over) directly, and the member of the ambiguous pair
that matches it is the over. Measured:

| market | anchored pairs | resolved | mean gap: matching vs other |
|---|---|---|---|
| Total Hits | 112 | 112 | 0.001 vs 0.187 |
| Total Bases | 49 | 49 | 0.001 vs 0.178 |
| Total Strikeouts | 12 | 11 | 0.001 vs 0.097 |

Three orders of magnitude of separation. The one strikeout pair that did not
resolve had its two sides priced too alike for the anchor to tell them apart,
and it is **refused** — recorded with side `unknown` and no implied probability
— rather than assigned the likelier half.

Because the anchor is a third quote rather than a property of the pair,
**reversing the pair cannot change the answer**, which is the property a test
and a planted violation both assert.

Home runs need no derivation at all: they are published only as a milestone, so
the side is known by construction.

---

## The identity bridge

The two feeds share no player id. Goldschmidt is `502671` to MLB and `31027` to
ESPN; Ranger Suárez is `624133` and `39817`. ESPN offers `id`, `uid`, `guid` and
`slug`, none of which is an MLB number.

`market/crosswalk.py` measures the bridge rather than assuming it:

* **Both rates are reported** — `exact` where the raw names were already
  identical, `normalised` where it took accent-stripping and punctuation
  folding. The normaliser's contribution is a count, not a hope.
* **Ambiguity refuses.** Two players normalising to one string is recorded as
  `refused_ambiguous` with both candidates named, and the prop is skipped.
* **It persists, dated.** Every row carries `measured_utc`.
* **It re-runs per slate.** September roster expansion lands inside the window
  these markets are scored over, and a new unmatched name is logged rather than
  dropped.

The candidate set is drawn from **our own record** — players we hold game logs
for — not from a roster endpoint. A player we have no history for cannot be
forecast, so an unmatched September call-up is a correct refusal.

A crosswalk refusal produces **no line**, not a void. The brief asked for a
void; that would delete a legitimate blind forecast because a third party's feed
was unhelpful, and it contradicts the standing rule that a missing line source
degrades the comparison and never the record. The four absence reasons are kept
distinct — nobody published a price, we cannot tell whose price it is, there is
no price at the rung we asked, the side could not be derived — because
collapsing them would hide which part of the chain broke.

---

## The confidence floor

**Ruling R4.** `config.PROPS_MIN_CLAIM = 0.70`, declared 2026-08-30, applied to
every prop market in every sport from that date. Existing prop records stand
exactly as written (LAW 3).

A prop question whose answer the model is not at least 70% sure of is not asked.
Because `stated_side` reports confidence in the side claimed, this reads the
same on both halves of a market: **a 28% chance of a home run is a 72% claim
that there will not be one**, and it qualifies.

The gate reads the statistical probability and skips the question for *every*
predictor. Two predictors answering different sets of questions could not be
compared with each other — the LLM's record would be over the questions the LLM
found easy, which is the one thing a head-to-head must not be.

A slate under its cap for this reason says so: the task detail carries
`N prop question(s) were below the 70% confidence floor and not asked`.

### On the sub-50 bucket set

The brief asked for the home-run market's bucket set to extend below 50.
**Building it would have been wrong, and this is the evidence.** Confidence is
`>= 0.5` by construction — `baseline.stated_side` converts every probability
into a side and a confidence in that side — so a bucket below 50 could never
receive a row. It would render as a row of empty bins beside a tier chip reading
LEAN on a claim that is not a lean.

What was needed was that sub-50 claims *map correctly*, and they do: 0.28 over
becomes `under` at 72%, bucket `70-80%`, tier `STRONG`. A planted violation
asserts exactly that chain, and the interface says
**"Kyle Schwarber — NO home run"** rather than "under 0.5 home runs".

---

## Void rules, written before the first prediction

Decided and recorded in code and here *before* any MLB prop existed. Deciding
after seeing results which non-answers count is choosing which losses to keep.

| case | outcome |
|---|---|
| batter has no line in the game (scratched, rested, late change) | **VOID** |
| announced starter did not start | **VOID** |
| game never finished, 4+ days after its date | **VOID** |
| line exists but the stat is missing from it | **VOID** |
| game simply has not been played yet | *unresolvable*, stays open |

The asymmetry that makes the first rule necessary: **a batter who played and
went 0-for-4 has a row full of zeros and settles normally.** The absence of a
row and a row of zeros mean opposite things, and collapsing them would score a
manager's decision as a correct under.

---

## Cadence and what cannot be reached

Props run on the daily `predict:mlb` task, capped at
`config.MLB_PROPS_PER_DAY = 25`, filled round-robin across the four markets in
measured liquidity order (hits, total bases, home runs, strikeouts). One
question per subject per day: asking the same batter about hits *and* total
bases is two correlated looks at one afternoon, and counting them as two would
inflate every N on the scorecard.

**No postseason (ruling R3).** `GAME_TYPES` stays `("R",)`. The MLB record ends
2026-09-27. October is a different question — different rest, different bullpen
usage — and pooling it into the same category would be the merge item 6 forbids,
in a new costume.

---

## The declared factors

Thirteen, dated 2026-08-30. The two question instruments come first because
checklist item 1 says they must exist from the first fit, and because NBA's props
shipped without them and nothing looked wrong.

The batter markets and the pitcher market get **disjoint** sets, enforced by the
`markets=` argument on the declaration rather than by a factor returning `None`
for questions it has nothing to say about. A batter's platoon split is not a weak
instrument for a strikeout prop; it is not an instrument at all, and letting it
be absent in every row of that fit would be item 2's constant-across-training
failure arriving as missing data.

| factor | markets | what it measures |
|---|---|---|
| `mlb_prop_mean_vs_line` | all four | which rung was asked, relative to the subject's own mean |
| `mlb_prop_volatility` | all four | dispersion over the window, scaled by the mean |
| `mlb_prop_park_factor` | all four | the venue's run environment in prior seasons, against the league |
| `mlb_batter_rate` | 3 batter | the stat per plate appearance |
| `mlb_batter_expected_pa` | 3 batter | plate appearances per game — the volume instrument |
| `mlb_batter_lineup_slot` | 3 batter | recent average batting-order slot, signed so higher is better |
| `mlb_batter_platoon` | 3 batter | +1 opposite hands, −1 same, 0 switch-hitter |
| `mlb_batter_opposing_k_rate` | hits, total bases | the opposing starter's strikeouts per batter faced, negated |
| `mlb_batter_opposing_hr_rate` | total bases, home runs | the opposing starter's home runs allowed per batter faced |
| `mlb_pitcher_k_rate` | strikeouts | his own strikeouts per batter faced |
| `mlb_pitcher_innings_form` | strikeouts | innings per start — the workload the strikeouts come out of |
| `mlb_pitcher_opponent_k_rate` | strikeouts | the opposing club's strikeouts per plate appearance, 30 games |
| `mlb_pitcher_prop_rest` | strikeouts | days since his last start, clipped to six either way |

**`mlb_batter_rate` carries a dated note recording a defect in its own
declaration**, found after the first fit: it and `mlb_batter_expected_pa`
multiply to exactly the rolling mean that `mlb_prop_mean_vs_line` is built from
(`corr(rate × pa, mean) = +1.000`), so their coefficients are corrections rather
than effects and must not be read as causes. It is not ordinary collinearity —
the pairwise correlations are −0.077 and +0.082, and the dependency runs through
the product, which no pairwise check sees. Left as declared rather than repaired
mid-session, because changing a declared factor set is a deliberate dated act.
