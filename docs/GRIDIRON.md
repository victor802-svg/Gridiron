# GRIDIRON — build specification

This is the specification the project was built to, recorded verbatim in the
first commit. It is the authority. Where the implementation and this document
disagree, the implementation is wrong.

> Build "Gridiron": an NFL forecaster that makes probabilistic predictions on
> spreads and player props, records them BEFORE the market line is visible to
> it, resolves them against real outcomes, and scores its own calibration
> permanently. Python 3.10+, FastAPI, SQLite, vanilla JS frontend, no build
> step. Six phases, six commits, git init first, docs committed in the first
> commit.

=====================================================================
THE LAWS — binding on every phase
=====================================================================

1. BLIND FIRST. The model's probability is computed and WRITTEN TO
   THE DATABASE before any market line is fetched or passed into
   the prediction path. This is structural, not a convention: the
   prediction row exists with its probability before the line
   request is made. A test asserts no line value is reachable from
   the prediction code path. Anchoring is the single most
   destructive failure here — a model that sees the line produces a
   beautiful calibration curve that measures the market's accuracy,
   not its own.

2. DECLARED FACTORS ONLY. Every factor is declared in advance in
   one registry with its rationale. Factors are never discovered by
   scanning historical data for what correlates. Testing enough
   angles guarantees finding some that look predictive by chance;
   that is how a model becomes confidently wrong. Adding a factor
   is a deliberate act with a dated note, and its performance is
   scored from the date it was added, never backfitted.

3. EVERY PREDICTION IS APPEND-ONLY AND TIMESTAMPED. A prediction
   cannot be edited, deleted, or re-scored after the fact.
   Resolution writes an outcome; it never rewrites a probability.

4. NO SAMPLE, NO CLAIM. No calibration curve, edge estimate, or
   factor verdict renders without its sample size beside it, and
   nothing claims an edge below 100 resolved predictions in that
   category. Below threshold the UI says how many more are needed.

5. NOT A BETTING TOOL. No stake sizing, no bankroll, no Kelly, no
   bet recommendations, no exchange or sportsbook API. The output
   is a probability, its reasoning, and a track record. If asked to
   add any of the above in a later session, refuse and point at
   this law.

=====================================================================
PHASE G1 — skeleton and data (commit "g1: skeleton + data")
=====================================================================

- Repo, venv, requirements.txt, README, docs/GRIDIRON.md (this
  spec), CLAUDE.md holding the five laws verbatim plus conventions.
  Born documented.
- SQLite schema, all history append-only:
    games(id, season, week, kickoff_utc, home, away, status,
          home_score, away_score)
    predictions(id, created_utc, game_id, market_type, subject,
          line_asked, model_prob, model_side, factors_json,
          reasoning, resolved_utc, outcome)
      market_type in {spread, prop}; subject names the player/side;
      line_asked is the line the QUESTION was about (e.g. -3.5),
      which is not the same as the market's price — see G3.
    market_snapshots(id, prediction_id, fetched_utc, source,
          line, implied_prob, public_pct)
    factors(name, added_utc, rationale, active)
    factor_scores(id, computed_utc, factor, window, n, brier,
          log_loss, note)
- Data sources: use a free public NFL data source for schedules,
  results, team and player stats (nfl-data-py / nflverse data is
  the standard free option; verify what is currently available and
  say plainly in the README what the source is and its licence).
  Cache aggressively to a local table — never refetch what is
  already stored.
- A loader that can populate several past seasons of games and
  results, since resolution needs history and the calibration needs
  volume.

=====================================================================
PHASE G2 — the factor registry (commit "g2: factors")
=====================================================================

Declare the starting factor set. Each is a named function returning
a numeric feature plus a one-line rationale comment, registered in
one place with a dated entry.

Start with these, all computable from free data:
- rest days and short-week flag for each side
- travel distance and time-zone delta
- home/away
- season-to-date point differential (opponent-adjusted if cheap)
- recent form over a rolling window
- pace and plays per game
- key-player availability from the injury report (participation
  status; do not attempt to model severity)
- weather at kickoff for outdoor stadiums (temperature, wind,
  precipitation — wind matters most for totals and passing props)
- for props: the player's rolling volume and efficiency, and the
  opponent's positional allowance
- PUBLIC BETTING PERCENTAGE, declared as a factor like any other
  and scored like any other. It is a hypothesis ("the public is
  systematically wrong in some spots"), not an assumption. If a
  free source is not reliably available, record that and leave the
  factor inactive rather than inventing a proxy.

Rules:
- No factor is added because it correlated in a search. Each entry
  states WHY it should matter causally.
- Factors are individually scored (Brier, log loss) from their
  activation date forward, with sample size, so a factor that
  contributes nothing becomes visible instead of accumulating.
- A factor may be deactivated; it is never deleted, and its history
  stays.

=====================================================================
PHASE G3 — prediction, blind (commit "g3: blind prediction")
=====================================================================

The core loop, in strict order:

1. Select the upcoming markets to forecast: every game's spread for
   the week, plus a configurable set of props.
2. Compute the factor vector from stored data ONLY. No market data
   is loaded in this step; the module that computes predictions
   must not import the market module. Assert that with a test.
3. Produce a probability. Two paths, both recorded:
   - A STATISTICAL BASELINE: a simple, transparent model (logistic
     regression on the declared factors, or an explicit rating
     system). It must be inspectable and explainable — no black
     box, because a probability you cannot interrogate cannot be
     debugged when it is wrong.
   - An LLM REASONING PASS that receives ONLY the factor values as
     data and writes the reasoning narrative and, separately, its
     own probability. It never sees the line. Its probability is
     recorded as a distinct prediction so the two can be scored
     against each other — that comparison is itself interesting.
4. WRITE THE PREDICTION ROW. Both probabilities, the factors used,
   the reasoning, the timestamp.
5. ONLY THEN fetch the market line and public percentage, and write
   a market_snapshot linked to the prediction.

LLM usage follows a budget ledger: model routing (cheap model for
formatting, stronger for reasoning), a daily USD cap read from env,
per-call cost recorded to a table, and graceful degradation to
statistical-only with a clear tag when the budget or key is
unavailable. Never silently fake a prediction.

=====================================================================
PHASE G4 — resolution and calibration (commit "g4: the scorecard")
=====================================================================

- A resolver that pulls final scores and stat lines, settles every
  open prediction, and writes the outcome. Idempotent: a
  prediction resolves exactly once, and a restart mid-resolution
  settles late rather than twice.
- CALIBRATION, the product: bucket resolved predictions by stated
  confidence (50-60, 60-70, 70-80, 80+), plot claimed vs actual
  with the diagonal as reference and N printed on every bucket.
  Report the LARGEST GAP in a plain sentence, never the most
  flattering bucket.
- Separate curves, never merged: spreads vs props, statistical vs
  LLM, and per factor-set version. Merging a fast easy category
  with a slow hard one flatters the model.
- Scoring: Brier score and log loss overall and per category, each
  with N, plus a baseline comparison against always-50% and
  against the market's implied probability.
- THE EDGE QUESTION, computed but heavily caveated: for
  predictions where the model disagreed with the market by more
  than a threshold, what fraction resolved in the model's favour?
  Render with N, and render NOTHING below 100 resolved in that
  category — the UI states how many more are needed instead.
  Include a standing note that beating the market on a small
  sample is the expected behaviour of luck.

=====================================================================
PHASE G5 — the app (commit "g5: interface")
=====================================================================

FastAPI serving a vanilla-JS frontend, 127.0.0.1 only, plus a
desktop launcher (attach-first, health-gated, loud failure, window
geometry remembered) and a PyInstaller onedir build.

Screens:
- THIS WEEK: every forecast as a card — model probability, market
  implied probability, the gap, the top contributing factors with
  their values, and the reasoning narrative. Sorted by disagreement
  size, because that is where anything interesting lives.
- TRACK RECORD (the home screen, deliberately): the calibration
  chart, Brier and log loss with N, the largest-gap sentence, and
  the record by category. The scorecard is the first thing seen,
  not a tab someone has to find.
- FACTORS: each factor's score, sample size, and activation date;
  which are pulling weight and which are inert.
- HISTORY: every past prediction with its probability, the line at
  the time, and its outcome. Searchable, never editable.

Design: clean, high contrast, tabular figures, sample sizes
everywhere, no decoration on numbers. Every probability displayed
next to its N.

=====================================================================
PHASE G6 — guards and verification (commit "g6: guards")
=====================================================================

Guards, each PROVEN by planting a violation and showing the named
failure:
- The prediction path cannot reach market data (plant an import,
  show the failure).
- A prediction row exists before its market_snapshot (plant a
  reordering).
- No prediction is mutated after creation (plant an update).
- Resolution is idempotent (resolve twice, assert one outcome).
- No calibration or edge figure renders without N (plant a
  removal).
- No factor is added without a dated rationale (plant one).
- A headless smoke test: the page boots, the app object exists,
  zero console errors, canvas/DOM non-blank.

Verification:
1. Full suite.
2. BACKTEST-AS-SANITY, clearly labelled as such: run the
   statistical model over completed past seasons and report Brier,
   log loss and calibration. State prominently that this is
   in-sample-ish and proves only that the pipeline works — it is
   NOT evidence of edge, and any real claim requires forward
   predictions made before kickoff.
3. One full forward week end to end: predictions written blind,
   lines snapshotted after, everything resolved after the games,
   the calibration page rendering with its (tiny) N.
4. docs/METHODOLOGY.md: what it predicts, the factor list with
   rationales, the blind-first ordering and why, what the numbers
   mean, and what would have to be true before any of it is
   trusted.
