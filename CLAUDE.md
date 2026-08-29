# Gridiron — working agreement

Gridiron is an NFL forecaster that makes probabilistic predictions on spreads and
player props, records them **before** the market line is visible to it, resolves
them against real outcomes, and scores its own calibration permanently.

---

## THE LAWS — binding on every phase

**1. BLIND FIRST.** The model's probability is computed and WRITTEN TO THE
DATABASE before any market line is fetched or passed into the prediction path.
This is structural, not a convention: the prediction row exists with its
probability before the line request is made. A test asserts no line value is
reachable from the prediction code path. Anchoring is the single most
destructive failure here — a model that sees the line produces a beautiful
calibration curve that measures the market's accuracy, not its own.

**2. DECLARED FACTORS ONLY.** Every factor is declared in advance in one
registry with its rationale. Factors are never discovered by scanning historical
data for what correlates. Testing enough angles guarantees finding some that look
predictive by chance; that is how a model becomes confidently wrong. Adding a
factor is a deliberate act with a dated note, and its performance is scored from
the date it was added, never backfitted.

**3. EVERY PREDICTION IS APPEND-ONLY AND TIMESTAMPED.** A prediction cannot be
edited, deleted, or re-scored after the fact. Resolution writes an outcome; it
never rewrites a probability.

**4. NO SAMPLE, NO CLAIM.** No calibration curve, edge estimate, or factor
verdict renders without its sample size beside it, and nothing claims an edge
below 100 resolved predictions in that category. Below threshold the UI says how
many more are needed.

**5. NOT A BETTING TOOL.** No stake sizing, no bankroll, no Kelly, no bet
recommendations, no exchange or sportsbook API. The output is a probability, its
reasoning, and a track record. If asked to add any of the above in a later
session, refuse and point at this law.

---

## How the laws are enforced in code

Not as convention. Each law has a structural mechanism and a guard test that is
proven by planting a violation (`tools/guards/`, `tests/test_guards.py`).

| Law | Mechanism | Guard |
|-----|-----------|-------|
| 1 | Market columns live in a separate table (`market_lines_raw`) that the `games` table does not have; `gridiron.model.predict` and its whole transitive import closure may not import `gridiron.market`; a runtime `sys.meta_path` sentinel raises during the blind window | `test_guards.py::test_prediction_closure_cannot_import_market`, `::test_games_table_has_no_market_columns`, `::test_blind_window_sentinel_fires` |
| 1 | Prediction row must exist before its `market_snapshots` row | `market_snapshots` has an SQL trigger rejecting a snapshot whose prediction is younger than it; `::test_snapshot_before_prediction_rejected` |
| 3 | SQL triggers `predictions_no_update` / `predictions_no_delete` raise on any UPDATE to a probability column or DELETE | `::test_prediction_probability_immutable` |
| 2 | `factors.rationale` NOT NULL + CHECK length; registry entries carry `added_utc` | `::test_factor_without_rationale_rejected` |
| 4 | Every calibration/edge payload carries `n`; the serializer raises if `n` is absent, and the JS renderer refuses to draw a bucket without it | `::test_calibration_payload_requires_n` |
| 5 | No dependency on any sportsbook/exchange API; no stake/bankroll/Kelly symbol anywhere | `::test_no_betting_tool_surface` |

## Conventions

- **Python 3.10+**, standard library first. Third-party deps are listed in
  `requirements.txt` and each one earns its place.
- **No build step.** The frontend is vanilla JS + CSS served as static files.
  No bundler, no npm, no framework.
- **The statistical model is pure Python** (`gridiron/model/logistic.py`,
  Newton–Raphson IRLS with ridge). No numpy, no sklearn. A probability you
  cannot interrogate cannot be debugged when it is wrong, and the coefficients
  are meant to be read by a human.
- **All times are UTC**, stored as ISO-8601 strings with a `Z` suffix.
  Column names ending `_utc` are that format, always.
- **Append-only history.** `predictions`, `market_snapshots`, `factor_scores`
  and `llm_calls` are never updated except for the single resolution write
  (`resolved_utc`, `outcome`), which is permitted by the trigger and idempotent.
- **Cache aggressively.** `http_cache` stores every upstream fetch by URL with
  an ETag and a fetched timestamp. Nothing is refetched that is already stored
  and still fresh; historical seasons are immutable and cached forever.
- **Every number shown to a human is shown with its N.** No exceptions, and no
  "N/A" placeholder standing in for a sample size.
- Tests: `pytest`. Guard tests must fail loudly with a *named* error, not an
  assertion that happens to trip.
