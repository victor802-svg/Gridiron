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

| Law | Mechanism | Guard that has fired |
|-----|-----------|----------------------|
| 1 | Market columns live in `market_lines_raw` / `market_snapshots`; `games` has no spread, total or moneyline column at all | `test_schema.py::test_games_table_has_no_market_columns` |
| 1 | `gridiron.audit` walks the transitive import closure of `gridiron.model.predict` and rejects any module that imports `gridiron.market` **or names a market column in code** (docstrings exempt) | `test_guards.py::test_a_planted_market_import_is_caught_by_name`, `::test_a_planted_market_column_read_is_caught_by_name` |
| 1 | `blind.blind_window()` installs a `sys.meta_path` sentinel and refuses to open if `gridiron.market` is already in `sys.modules` | `test_guards.py::test_a_market_import_inside_the_blind_window_is_caught` |
| 1 | SQL triggers reject a `market_snapshots` row with no prediction, or timestamped before its prediction | `test_guards.py::test_a_reordered_snapshot_is_rejected` |
| 2 | `factors.rationale` NOT NULL + length CHECK; `added_utc` must parse as a date; factors cannot be deleted | `test_guards.py::test_a_factor_with_a_token_rationale_is_rejected`, `::test_a_factor_with_no_date_is_rejected` |
| 2 | `store.sync_registry` refuses to move a factor's activation date | `test_guards.py::test_backdating_a_factor_is_rejected_by_name` |
| 3 | Triggers `predictions_no_update` / `predictions_no_delete` ABORT on any edit to a prediction's substance and on every delete | `test_guards.py::test_every_substantive_field_is_frozen` |
| 3 | `resolve_all` updates `WHERE resolved_utc IS NULL`; trigger `predictions_resolve_once` is the backstop | `test_guards.py::test_resolving_twice_yields_one_outcome`, `::test_a_forced_re_resolution_is_rejected_by_name` |
| 4 | `calibration.assert_every_figure_has_n` walks the payload and raises naming the path; the API returns 500 rather than serving it; `Gridiron.requireN` throws in the browser | `test_guards.py::test_a_removed_sample_size_is_caught_by_name`, `test_smoke.py::test_the_renderer_refuses_a_figure_with_no_sample_size` |
| 4 | The edge figure is absent from the payload below `MIN_SAMPLE_FOR_EDGE_CLAIM`, replaced by the shortfall | `test_guards.py::test_an_edge_figure_below_threshold_is_not_present_to_render` |
| 5 | `audit.check_not_a_betting_tool` scans package **identifiers** for a staking surface — prose is exempt, so the disclaimer may keep saying "bankroll" | `test_guards.py::test_a_planted_stake_sizer_is_caught_by_name`, `::test_the_disclaimer_is_not_mistaken_for_a_feature` |
| 4 | Curves are never merged: `assert_no_merged_categories` rejects a category with no concrete market, an `all` prop_type, or a merged forecaster. Runs inside `scorecard()`, so a merge cannot reach the API | `test_guards.py::test_a_planted_merged_prop_curve_is_caught_by_name`, `::test_a_planted_merged_forecaster_curve_is_caught` |
| v2 | Missing stays missing: `compute.assert_missing_is_explicit` runs on every feature vector, and `audit.check_no_silent_defaults` scans the factor code for a reintroduced fallback. `Factor.default` was **removed**, not left unused | `test_guards.py::test_a_planted_zero_fallback_is_caught_by_name`, `::test_a_vector_that_defaults_an_absent_factor_is_caught_at_runtime` |
| 3 | A void is terminal: `prediction_voids` is append-only and a trigger refuses to resolve a voided prediction afterwards | `test_props.py::test_a_void_is_terminal`, `::test_a_void_reason_cannot_be_rewritten` |

Run them all at once, each violation planted for real:

```bash
python tools/guards/plant.py --verbose
```

And the whole verification:

```bash
python tools/verify.py
```

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
- **A repair is not a discovery.** When a factor is retired because its input
  never varied, or a default is removed because it was never a measurement, the
  registry note says so in those words. A later reader who mistakes the one for
  the other will draw the wrong conclusion from both.
- **`gridiron.audit` stays outside the prediction closure.** It holds the list
  of forbidden market identifiers, so a prediction-path module that imported it
  would make the LAW 1 scan flag itself. The runtime missing-data check
  therefore lives in `factors.compute`, and `audit` re-exports it.
