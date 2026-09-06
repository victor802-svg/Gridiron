# Brief — GRIDIRON_AT_THE_LINE (received 2026-09-05 22:30 PDT, during the UI audit session; saved verbatim before any work on it)

Received mid-session while GRIDIRON_UI_AUDIT was in progress. Saved as the
first act, per the unattended contract; taken up after the UI audit closes
out, because a complete item beats a half-built one. D1–D3 are the
operator's rulings and nothing that depends on them is built without them.

---

# Brief — GRIDIRON_AT_THE_LINE (drafted 2026-09-06, supersedes GRIDIRON_EDGE_FIRST; awaiting operator rulings)

Same goal as the superseded brief — improve the picking system in the order
that serves a future edge claim — with one new fact that reshapes it: the
operator now trades NFL spread contracts on Kalshi, a CFTC-regulated event
exchange, with a personal account. Gridiron itself remains NOT A BETTING
TOOL (LAW 5, untouched): it holds no account, authenticates to nothing,
recommends nothing, sizes nothing. What changes is the benchmark. The most
relevant market comparison this project could make is against the venue the
operator can actually trade, and the most useful probability it could state
is one evaluated AT that venue's line rather than at its own rung. All laws
bind. MENTOR.md first. Backtest is sanity, never evidence. Every new
instrument gets a NEW NAME and a forward record.

Context: 6 resolved predictions exist, none NFL. Nothing has an edge and
nothing may claim one (LAW 4). The operator's personal trading records stay
OUT of this repository entirely — a personal ledger inside the codebase is
a staking surface waiting to be discovered by the Law 5 scan, and it is not
this project's data.

---

## DECISIONS required from the operator

**D1 — Law 5 and the paper ledger.** Unchanged from the superseded brief.
A hypothetical flat-stake ledger requires price-to-return arithmetic, which
Law 5 forbids. (a) leave it — the readout stays probability vs implied
probability; (b) amend by dated ruling, narrowly: hypothetical unit-stake
accounting against recorded snapshots only, labelled hypothetical on its
face, no staking advice, no bankroll, no placement. Fee-adjusted comparison
(the venue takes roughly 7% of p×(1−p) per contract) is also return
arithmetic and sits behind the same ruling. Do not build without it.

**D2 — sport order.** NFL moves to the front: it is the sport the operator
trades and the sport the at-the-line work below serves. MLB keeps its daily
cadence regardless (its regular season ends within the month and those
resolutions are the fastest n=100 available). Then CFB, NBA before opening
night, UFC last.

**D3 — Kalshi as a read-only market source.** Proposed amendment to Law 5,
same shape as the PrizePicks ruling of 2026-09-02: read-only snapshots of
Kalshi's published market prices for games Gridiron already predicts,
fetched only inside the market module, only after the prediction row
exists, only from unauthenticated public endpoints. If Kalshi's market data
turns out to require an account or a key, THE SOURCE IS DROPPED rather than
the law bent — the operator's personal account is the operator's, and this
codebase never touches it. If ratified, the amendment text goes into
CLAUDE.md dated, and MARKET_ROSTER.md gains the source with its licence and
terms described honestly, per the sources convention.

---

## PHASE E1 — Route the LLM spend (game markets only)

Unchanged from the superseded brief. LLM passes run on game markets only
(spread, moneyline, total, UFC winner) and are skipped for all prop
markets. Config-declared and dated; skips counted, never silent; a
routed-off prop is not `degraded` — the absence is a ruling, not a failure.
Existing LLM prop predictions stand (LAW 3) and their curves stop growing
without implying an error.

## PHASE E2 — Ratings core, NFL first

As before, with the order flipped to match D2. Declare the successor to
`nfl_srs_diff` under a new name (e.g. `nfl_rating_decayed_diff`):
opponent-adjusted, recency-decayed, margin-capped, home adjustment measured
not assumed. Full causal rationale and date (LAW 2); scored forward from
that date; the old factor retired with a dated REPLACED-not-refuted note,
the asked-line retirement as precedent. Decay half-life and margin cap are
declared choices from first principles with written rationale — NOT tuned
against the record; that is LAW 2's line and the temptation is real.
Backtest-as-sanity to prove machinery only. `asked_distance`'s rationale is
updated if the expected margin now flows from the new rating.

## PHASE E3 — The margin distribution is the product, not a nicety

The superseded brief treated the distributional model as a prop upgrade.
It is now load-bearing: evaluating a probability at an arbitrary line —
the venue's, not our rung — requires a distribution over the final margin,
not a logistic answer to one pre-chosen question.

- **During the blind window, for every game question, write the fitted
  margin distribution's parameters into the prediction row's payload**
  (expected margin, spread/SD, family — whatever the model form is). This
  is written blind, before any line exists in the process (LAW 1), and it
  is frozen by LAW 3 like everything else.
- The blind rung question and its curve continue exactly as today. Nothing
  about the existing record changes meaning.
- Per prop market, the walk-forward promotion rule from the superseded
  brief stands: promote the distributional model only where it at least
  matches the logistic on log loss and calibration, new forecaster
  identity, own curves, own 100-gate.

## PHASE E4 — At-the-line evaluation (the new work)

After the blind window closes and market snapshots are taken, a market-side
step evaluates the FROZEN distribution at each snapshotted line and records
the result as a new kind of row — an at-the-line claim.

- **This is arithmetic on a blind artifact, not a second prediction.** The
  distribution parameters were written before any line was seen; evaluating
  them at the venue's number afterwards adds no market information to the
  model. The row records which prediction's frozen parameters it was
  computed from, the venue, the line, the price, and the timestamp — which
  is necessarily after the line fetch, and the schema should make that
  impossible to misread as a blind row.
- **Separate record, separate curves, separate gate.** At-the-line claims
  resolve like predictions and calibrate like predictions, but their curves
  never mix with the blind rung curves (the LAW 6 refusal extended one
  more level: a merged curve would describe neither). Their edge readout —
  model probability at the venue's line versus the venue's implied
  probability — is the single most decision-relevant number this project
  can produce, and it sits behind the same n=100 gate as every other edge
  figure.
- **The words on the card are a forecast, never advice.** No "value", no
  "play", no "bet", no "lock", no side recommendation — the plain-words
  scan gains these terms and `tools/guards/plant.py` plants one to prove
  the scan fires. The output is "the model gives the home side covering
  −6.5 a 58% chance; the market's price implies 52%, n so far: 14", and it
  stops there. What a reader does with that is outside this codebase.
- Coverage and pace reporting as in the superseded brief: per market, the
  share of predictions with a comparable snapshot, the named reason for
  every hole, and the projected date each n=100 gate opens.

## PHASE E5 — Wire the new source (only if D3 is ratified)

Kalshi snapshot fetcher in the market module: public endpoints,
unauthenticated, cached like every other source, crosswalked to games with
the same refuse-on-ambiguity discipline as the ESPN↔MLB bridge. Snapshots
land in the existing tables with the source named. If the public data
requires auth: DECLINED, with the law cited, and the ESPN-published lines
remain the NFL comparison.

## Close-out

Standard table: one row per phase plus one per DECISION, four verdicts,
evidence nameable. SKIPPED and DECLINED remain ordinary outcomes.

---

## How this brief is read (written at receipt, before any work)

- No "=== END OF PASTE ===" marker was requested for this brief; the paste
  ends at its close-out section.
- D1, D2 and D3 are the operator's rulings. Until they arrive: D1 defaults
  to (a) — no ledger, no return arithmetic, LAW 5 as written; D3 is not
  ratified, so E5 is not built and no Kalshi endpoint is touched; D2 is a
  proposal and the sport order it names is followed only for the work in
  this brief that does not otherwise depend on a ruling.
- "6 resolved predictions exist, none NFL" is a factual claim to VERIFY
  against the record before acting on it (MENTOR §4); the record on
  2026-09-05 held far more than six resolved rows.

---

## Operator rulings, received 2026-09-06 (saved verbatim at receipt)

# Operator rulings on GRIDIRON_AT_THE_LINE (2026-09-06)

Run the saved brief (docs/briefs/2026-09-06-at-the-line.md). Rulings on its
three decisions, so nothing falls to a conservative default:

**D1 — RULED: option (b).** Law 5 is amended by this dated operator ruling,
narrowly: hypothetical unit-stake accounting against recorded market
snapshots is permitted — "had every qualifying pick been backed at one
unit, the paper return per sport is X", labelled hypothetical in the
visible text, gated behind the same n=100 rule as the edge figure.
Fee-adjusted comparison using the venue's published fee formula is
included. Everything else Law 5 forbids stays forbidden: no staking
advice, no bankroll, no bet recommendations, no placement, no account,
no authentication to any venue. Write the amendment into CLAUDE.md the
way the PrizePicks ruling was written.

**D2 — RULED: NFL and CFB first** for the ratings-core work, in that
order. The daily MLB runs keep priority on the scheduler regardless —
those resolutions are the fastest n=100 available before spring.

**D3 — RULED: ratified.** Kalshi is added as a read-only market source
under the same terms as the PrizePicks ruling of 2026-09-02: published
prices only, fetched only inside the market module, only after the
prediction row exists, only from unauthenticated public endpoints. If
the public data requires an account or key, the source is DROPPED and
this ruling records that outcome. I hold a personal Kalshi account; it
is mine, not the project's, and this codebase never touches it.

All laws bind. Close-out table at the end, one row per phase plus one
per decision.

## How the rulings are read (written at receipt)

- The rulings supersede the "How this brief is read" defaults above for D1,
  D2 and D3. They are taken up after the UI audit's U4 closes out: a
  complete item beats a half-built one, and the audit's re-drive was in
  flight when they arrived.
- The operator's personal Kalshi account is never touched, read, or
  referenced by this codebase; only unauthenticated public endpoints, and
  if none serve the data, the source is dropped and the outcome recorded.
