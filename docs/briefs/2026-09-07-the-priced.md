# Brief — GRIDIRON_THE_PRICED (drafted 2026-09-07, awaiting operator rulings)

Saved verbatim on receipt. It arrived while GRIDIRON_THE_RECOMMENDATION was
being built, with the instruction to work on it after that one, so it is
QUEUED: nothing in it has been executed at the time of saving. How it is read,
and how its three decisions are handled in the operator's absence, will be
written at the head of the work when it starts.

---

Reshape this project toward profit without destroying the instrument that
makes it trustworthy.

The operator has ruled that Gridiron exists to inform his own wagering
(LAW 5, amended 2026-09-07). This brief follows that ruling to its
consequence: **a forecaster built to be well-calibrated across every game is
not the same object as one built to make money**, and the second is a harder
problem, because it competes not against reality but against a market's
estimate of reality.

**WHAT DOES NOT CHANGE, AND THIS IS THE SPINE OF THE BRIEF: LAW 1 IS NOT
AMENDED.** The blind forecaster keeps writing its probability before any line
is fetched, keeps its import closure, keeps its guard tests and its
plantings. It remains the only honest measurement of whether this project can
forecast at all. What this brief adds is a **second, separately identified
forecaster that runs AFTER the snapshot exists and says so on its face** —
market-aware by design, scored on money rather than on calibration, and never
merged with the blind record in any curve, figure or N.

The reason for two rather than one, stated plainly so a later session does
not "simplify" it away: a forecaster that sees the price will beat a blind
one at predicting outcomes, and will teach you nothing about your own skill,
because most of what it knows it read off the market. Keeping both means the
project can answer "are we making money?" and "are we any good?" separately.
Collapsing them answers neither.

---

## DECISIONS required from the operator

**D1 — the coverage list, and how it is chosen.** The profit engine must
specialize; nobody beats five sports and twenty-nine markets. **It must NOT
be specialised by picking the markets the operator's own bets have won in.**
Four winning college-football tickets is a sample of four, and selecting on
them is exactly the discovery LAW 2 forbids, with money attached. Options:

  (a) **Select by a measured structural proxy for inattention** — venue
      bid/ask spread, contract volume, and how often the price updates,
      measured across a declared window and dated. Thin, rarely-repriced
      markets are where a retail edge can exist at all. Recommended: it is
      a measurement, not a result.
  (b) Operator names the coverage list outright, recorded as a ruling.
  (c) No specialisation: bet everything the engine prices. Not recommended,
      and the brief says why in P2.

  **RECORD, DO NOT ACT ON:** the operator's observation that his winners were
  FCS-versus-FBS mismatches in small-conference football goes into
  FOLLOWUPS as a **hypothesis with n=4**, in those words, to be tested by
  the criterion above rather than assumed by it.

**D2 — the kill criterion's numbers.** Proposed: **if mean CLV is negative
after 50 recommendations in a market family, the engine stops recommending
that family** and says so on the page. Blind forecasting continues; only the
money stops. Operator sets the number and the horizon, and rules now rather
than later, because nobody has ever wanted to write this rule on the day it
fired.

**D3 — the declared bankroll constant.** Sizing is meaningless without it.
The number written into config is the ring-fenced wagering money and nothing
else. It is a config constant, never a balance read from any venue (LAW 5's
forbidden half).

---

## PHASE P1 — The priced forecaster

A second forecaster identity — `priced` — living in its own package
(`gridiron/priced/`), **outside** `gridiron.model.predict`'s import closure.

- It runs **after** the blind rows and the market snapshot exist. Its rows
  carry the id of the blind prediction they correspond to, the snapshot they
  read, and a timestamp necessarily later than both. The schema must make it
  impossible to mistake a priced row for a blind one.
- It may read what the blind path may not: the venue's price, the opening
  price where recorded, and the movement between them. The `audit` closure
  scan is extended to permit `gridiron.priced` to import `gridiron.market`
  **while still refusing the blind path by name** — and a planting proves the
  blind refusal still fires after the change, because a loosened scan that
  loosened too far would be the most expensive silent failure available here.
- **Its own curves, its own gate, its own everything.** No figure ever mixes
  `priced` with the blind forecaster, per the no-merged-forecaster rule
  already enforced in `calibration.assert_no_merged_categories`.
- Its objective is **not** Brier score. It is scored on expected value and on
  CLV (P4). A priced forecaster with a worse Brier score and better CLV is
  succeeding, and the Record page must be able to say so without the reader
  thinking something has gone wrong.

## PHASE P2 — Coverage: bet few things, on purpose

Per D1, a declared, dated coverage list of (sport, market) pairs the engine
is allowed to price. Everything else is forecast and never recommended.

The argument for the list, recorded in `docs/` rather than assumed: NFL sides
and totals are among the most efficiently priced markets in existence, and
are priced by people with better data, better models and lower latency than
this project will ever have. An edge, if one exists here, exists where nobody
is looking. The engine should be embarrassed by how few markets it covers.

Coverage is **reviewed on a declared cadence, not continuously** — a list
that can be edited the moment a market loses is a list that chases results.

## PHASE P3 — Fees and expected value

Kalshi's published fee formula (roughly 7% of p×(1−p) per contract, largest
near 50¢) is implemented from the venue's own fee schedule, dated and cited,
and applied to every EV figure.

- An edge that does not survive fees is **displayed as no edge**, never as a
  small one.
- Because the fee is largest at coin-flip prices, the engine should expect to
  find fewer opportunities near 50¢ than the raw model disagreement suggests.
  That is a real property of the venue, not a bug in the ranking.
- EV, size and price all render with their N and their gate status, per
  LAW 4 and the amended LAW 5.

## PHASE P4 — CLV: the verdict that arrives first

For every recommendation, snapshot the price again at close and record the
movement. Per sport, market and coverage entry:

- mean CLV in cents, share of recommendations beating the close, each with N.
- **This is the fastest honest read available**: CLV says something at
  roughly 50 observations where a win-rate verdict needs several hundred, and
  it is what would tell the operator he is buying cheap long before his
  bankroll would.
- A negative mean CLV at meaningful N is written into FOLLOWUPS as "the
  priced forecaster is buying rich", in those words. Not retuned quietly.

## PHASE P5 — The kill criterion, written before it is needed

Per D2, implemented as code rather than as intention: when a coverage entry's
CLV verdict trips, the engine stops recommending it, the page says which
entry stopped and on what number, and re-entry requires a dated operator
ruling. Blind forecasting on that market continues untouched.

## PHASE P6 — What the operator sees

One line per recommendation: the question in plain words, fair value, the
venue's price, edge after fees, size, gate status, and the coverage entry it
came from. Most days the list should be short or empty. **An empty list is a
correct output and the page says so plainly** — "nothing priced wrong enough
today" — rather than reaching for something to say.

## A number the close-out should state honestly

At the operator's stake size, a genuine and professional-grade 5% ROI across
twenty bets a week of ten dollars is about ten dollars a week. The ceiling on
this project's profit is set by stake size and by the thinness of the very
markets where its edge could exist — not by model quality. The close-out
records that, once, so that no later session mistakes this for a business.

## Close-out

Standard table: one row per phase plus one per DECISION, four verdicts,
evidence nameable. SKIPPED and DECLINED remain ordinary outcomes.
