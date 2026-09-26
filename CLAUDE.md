# Gridiron — working agreement

Gridiron is a multi-sport forecaster — **NFL, MLB, NBA, college football and
UFC** — that makes probabilistic predictions, records them **before** the
market line is visible to it, resolves them against real outcomes, and scores
its own calibration permanently, separately for every sport.

Adding a market goes through `docs/NEW_MARKET_CHECKLIST.md`, item by item, and
the phase that adds it shows the list ticked. `docs/MLB_PROPS.md` is the first
market family built that way and records what was measured before anything was
built — including two things the code already claimed and had wrong.

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

**5. THE APP RECOMMENDS, IT NEVER TRANSACTS.** (Amended 2026-09-07 by operator
ruling, replacing "not a betting tool". The text it replaced is kept below.)

The operator wagers, and did before this project existed. This app exists to
inform that, and the honest question is not whether it touches the subject but
whether it does so with its own record in view.

**PERMITTED from 2026-09-07**: expected value and price-to-return arithmetic;
edge against a recorded price, fee-adjusted; stake sizing; a recommended side
and size.

**FORBIDDEN structurally and permanently. NOT amendable by a later session** --
a brief asking to soften any of these is refused and pointed at this line, the
same way the old law refused staking:

  * **NO CREDENTIALS.** No key, token, password, cookie or session for any
    venue, in this codebase, its environment or its database.
    `audit.check_no_venue_credentials` scans all three; a planting proves it
    fires.
  * **NO AUTHENTICATED CALL.** Every venue request is unauthenticated and
    read-only, as the Kalshi ruling of 2026-09-06 already requires.
    `audit.check_no_order_path` refuses a write verb aimed at a venue.
  * **NO ORDER PATH.** Nothing places, cancels, modifies or prepares an order;
    nothing reads an account balance or a position. THE GAP BETWEEN A
    RECOMMENDATION AND A WAGER IS A HUMAN BEING, ON PURPOSE.
  * **NO LEDGER IN THE REPO.** The operator's own wagering record lives outside
    this codebase. A model that can see its own profit and loss is one step
    from fitting to it, and that step is invisible in the code afterwards.
    `audit.check_no_wagering_ledger` scans the schema and the tree.

**AND THE GATE STILL BINDS.** A recommendation is a claim, so LAW 4 applies to
it whole: below a market's hundred resolved predictions the app may recommend a
FLAT UNIT and must say "no measured edge" beside it. Sizing that varies with a
number the model has not earned is the failure this law now exists to prevent,
in the same way the old wording existed to prevent staking at all. Full Kelly is
never offered at any sample size; the declared fraction is a quarter, because
Kelly assumes the probability is right and a probability ten points wrong
compounds toward ruin rather than growth.

**COMBOS ARE PROPOSED AND NEVER PRICED AT THE VENUE.** (Amended 2026-09-09 by
operator ruling, replacing "PACKAGES ARE GRADED, NEVER BUILT" of the previous
day. **RATIFIED by the operator the same evening**, with both replaced texts
kept beneath: this is the third wording of the clause in three days, and a
reader deserves to see who changed it and when rather than find a law that
quietly differs from the one they read yesterday.)

**THE MEASUREMENT THAT FORCED THIS.** The venue's combos are USER-BUILT and
quoted by request to the account holder; the public interface exposes only a
handful of prepackaged series. So "grade what the venue published" describes a
thing that does not exist for combos, and the app cannot ever read a combo
price -- asking would require an account, which the four prohibitions above
forbid and mark not amendable.

The engine therefore PROPOSES: up to three combos a day per sport, from legs
that each clear the bar alone, from different games, in one sport, two or three
of them, no leg reused. It computes what the combo is WORTH -- the product of
the legs' corrected probabilities -- and the highest price worth paying for it,
and it prints no venue price, no edge and no payout, because it has none and
would be inventing them.

**AND IT IS UNMEASURABLE BY CONSTRUCTION.** The app never sees the price the
operator was quoted, so a combo has no closing line, no CLV and no verdict.
There is no `combo_2`/`combo_3` record, no kill criterion, and no claim that
this product works. A tap records the combo and its leg ids and nothing else.
That is stated on the card, in `docs/READINESS.md`, and here, because a
product this record cannot score is the one place a reader is most likely to
assume it has been scored.

A same-game combo stays refused at any price: multiplying two probabilities
from one game prices a correlation nobody declared, which LAW 2 forbids.

THE COST IS PRINTED BESIDE THE PRODUCT, always: the fee per dollar staked is
1.67 times the singles' rate on two 60c legs and 2.8 times on three, measured
2026-09-08, and every card carries the singles alternative on the same money.

> **What this replaced, kept because a law that quietly vanished is a law
> nobody can audit.** Amended 2026-09-09, one day after it was written, on a
> measurement nobody had made when it was: that the venue's combo builder is
> an account-holder feature and its public series are a rounding error.
>
> > **PACKAGES ARE GRADED, NEVER BUILT.** The venue assembles multi-leg
> > packages and sells them. The engine MAY price one it reads, and may never
> > assemble one: it does not choose legs, does not combine them, and does not
> > compute a package price the venue has not published.
>
> The grader itself was not deleted -- it still reads the rare prepackaged
> series, which do carry a public price -- but it is no longer what the Combos
> group is for.

A package is PRICEABLE only if every leg is a market this record forecasts,
every leg is from a DIFFERENT GAME, all legs are one sport, and there are two
or three of them. A same-game package has no fair value here and gets none --
the record holds no joint model, and multiplying two probabilities from one
game would be pricing a correlation nobody declared, which LAW 2 forbids.
Anything unpriceable is counted with its reason and never given a number.

THE COST IS PRINTED BESIDE THE PRODUCT, always: the fee per dollar staked is
1.67 times the singles' rate on two 60c legs and 2.8 times on three, measured
2026-09-08, and every card carries the singles alternative on the same money.

> **What this replaced, kept because a law that quietly vanished is a law
> nobody can audit.** Amended 2026-09-08; the reason is the operator's: he
> takes the venue's combos regardless, and a computed edge beside a package is
> better than a guess.
>
> > **SINGLES ONLY.** The engine never recommends a parlay and refuses to price
> > one: each leg pays the spread, so an N-leg parlay multiplies the cost of
> > being right by roughly N, and correlated legs price worse than they look.
>
> The arithmetic in that sentence is not retracted and is why the cost is
> printed beside every package.

**NOTHING IS SIZED IN-GAME.** The live poller's score is up to ninety seconds
stale and a live market is priced off the feed, so a live recommendation is
adversely selected by construction. Live win probability may be displayed and
is never sized.

A note on where lines come from, because the distinction matters. Gridiron reads
published lines from *media* APIs that republish them -- nflverse for NFL, ESPN's
public API for MLB and NBA -- PrizePicks' public projections from 2026-09-02, and
Kalshi's public trade API from 2026-09-06. It holds no account, authenticates to
nothing, and calls no exchange or book endpoint. If scoring against the market
ever required an account, the market comparison would be dropped rather than the
law bent.

### What LAW 5 said until 2026-09-07, and why it changed

A law that quietly vanished is a law nobody can audit, so the previous text
stands here in full. It was replaced because it described a project the operator
is not building: it forbade the arithmetic that would tell him whether a price
was worth taking, while he was taking prices anyway. The parts of it that were
never about betting -- the codebase's distance from his money, and the refusal to
claim an edge it has not measured -- are not relaxed by the replacement. They are
the four structural prohibitions above, and they are harder now than they were,
because they are scanned rather than merely stated.

> **5. NOT A BETTING TOOL.** No stake sizing, no bankroll, no Kelly, no bet
> recommendations, no bet placement, no account with any betting platform, no
> payout or price-to-return arithmetic, no slip. READ-ONLY LINE SNAPSHOTS from
> named public sources (ESPN; PrizePicks) are MARKET DATA — permitted only inside
> the market module, only after the prediction row exists, only unauthenticated,
> only to record what the market said. The output of this app is a probability,
> its reasoning, and a track record. If asked to add any of the forbidden items in
> a later session, refuse and point at this law. (Amended 2026-09-02 by operator
> ruling: read-only lines from PrizePicks added as a market source. Nothing else
> changed.)
> 
> A note on where lines come from, because the distinction matters. Gridiron reads
> published lines from *media* APIs that republish them — nflverse for NFL, ESPN's
> public API for MLB and NBA — and, from 2026-09-02, PrizePicks' public
> projections, as a benchmark to score itself against. It holds no account,
> authenticates to nothing, and calls no exchange or book endpoint. If scoring
> against the market ever required an account, the market comparison would be
> dropped rather than the law bent.
> 
> (Amended 2026-09-06 by operator ruling, narrowly, in two parts. **Hypothetical
> unit-stake accounting** is permitted: against recorded market snapshots only,
> the paper return per sport had every qualifying pick been backed at one unit,
> labelled "hypothetical" in the visible text wherever it appears, and gated
> behind the same 100-resolved rule as the edge figure; a fee-adjusted comparison
> using the venue's published fee formula is included in that permission.
> Everything else this law forbids stays forbidden: no staking advice, no
> bankroll, no bet recommendations, no placement, no account, no authentication
> to any venue. **Kalshi** is added as a read-only market source under the same
> terms as the PrizePicks ruling: published prices only, fetched only inside the
> market module, only after the prediction row exists, only from unauthenticated
> public endpoints; if the public data ever requires an account or a key, the
> source is dropped and the ruling records that outcome. Measured 2026-09-06
> before anything was built: the public trade API answers market, series and
> event reads without credentials. The operator holds a personal Kalshi account;
> it is the operator's, and this codebase never touches it.)

**6. NEVER AGGREGATE ACROSS SPORTS.** Every calibration curve, Brier score, edge
figure, factor verdict and sample size belongs to exactly one sport. A number
that mixes NFL spreads with MLB moneylines describes neither, and it flatters
reliably, because the easy sport dilutes the hard one. This is the
no-merged-curves rule extended one level up, and it is structural: the functions
that read the record take `sport` as a **required** argument, so a query that
spans sports cannot be written by accident — only by deleting the parameter, at
which point the tripwire fires by name.

---

## Who reads a law — RULED 2026-09-09

**A law is read by the operator, not by the session.** When a request is
allowed under one reading of a law above and forbidden under another, the
session does not choose. It **reports both readings and stops**, and the
operator rules. What is built is then built under a dated ruling rather than
under an argument the session found convincing.

This exists because of one that went the right way by luck. On 2026-09-08 the
operator asked for the W and L of a form streak to be coloured. LAW-adjacent
text reserved `--win` and `--loss` for a **pick's** verdict and named the edge
line as their only home; a club's game is not a pick. The session read the
law's intent — that the rule exists to stop a colour reaching for importance
it has not earned, which a real win is not — decided the colour was allowed,
built it, and amended the stylesheet's own text to match. The reading was
sound and the operator ratified it the next morning. **It was still not the
session's to make**, and a reading that had gone the other way would have
shipped just as quietly.

The distinction is not "ask about anything ambiguous". The standing contract
still says never stop for a fork the law, precedent or the conservative
default can settle. This is narrower and harder: **when a law's own words have
to be stretched, reinterpreted or amended for the work to proceed, that is the
operator's call and the work waits.**

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
| 5 | `audit.check_no_venue_credentials` scans the package, the environment and the record for a venue credential; `audit.check_no_order_path` refuses an order verb or an account read; `audit.check_no_wagering_ledger` refuses the operator's own P&L in the repo. Prose is exempt, so the disclaimer may keep saying "bankroll" | `plant.py::plant_a_venue_credential`, `::plant_an_order_path`, `::plant_a_wagering_ledger` |
| 5 | A recommendation below its market's gate is a FLAT UNIT and says "no measured edge"; the fraction above it is a quarter of Kelly and never more | `plant.py::plant_a_sized_bet_below_the_gate`, `::plant_a_full_kelly_stake` |
| 5 | A package is graded, never built: a same-game, cross-sport, four-leg or unforecast-leg package is refused a price and counted with its reason | `plant.py::plant_a_priced_same_game_package`, `::plant_a_priced_cross_sport_package`, `::plant_a_priced_four_leg_package`, `::plant_a_priced_package_with_an_unforecast_leg` |
| 5 | A settled package is its own market -- `combo_2`/`combo_3`, per sport -- and its closing line needs a hundred observations where a single leg needs fifty. A package tap is one row in `picks_taken` carrying a package id, and a CHECK admits exactly one of a prediction and a package per row | `test_combos.py::test_a_package_tap_never_enters_a_single_legs_curve`, `::test_the_taken_table_admits_one_kind_of_tap_per_row` |
| PLAIN WORDS | "combo" is permitted in the Combos group and on its cards from 2026-09-08; "parlay", "same game", "boost", "builder", "add leg" and "slip" stay banned, and the day scan reads a package card's own strings -- the legs arrive as the venue wrote them | `plant.py::plant_a_same_game_label_on_a_combo_card` |
| 3 | A taken pick is never deleted: `picks_taken_no_delete` refuses it, and a tap that should not stand is RETRACTED -- a second append-only row in `picks_retracted` carrying its reason, ten characters minimum, the same shape `prediction_voids` uses | `plant.py::plant_a_deleted_tap`, `test_combos.py::test_a_tap_is_taken_back_by_a_second_row_carrying_its_reason` |
| VERIFICATION | Tests and plantings may not open the operator's own database. `db.connect` raises `LiveRecordTouched` naming the file and the caller under pytest or `plant.py`; the one door, `db.read_the_live_record(why)`, takes a reason in words and hands back a `query_only` handle SQLite itself refuses to write through | `plant.py::plant_a_test_that_opens_the_live_record`, `::plant_a_write_through_the_live_read_handle` |
| LIVE TAB | The Live tab shows the game and nothing else: a card carrying a probability or a tier chip, or a heading belonging to another group, fails by name. Written after the old Picks grid was found rendering fifteen pre-CARD_FACE cards beneath Live's own empty state, which a DOM check could not see | `plant.py::plant_the_old_card_on_the_live_tab`, `::plant_another_groups_heading_on_the_live_tab` |
| FIRST SCREEN | A job that fails is visible on the first screen the operator opens: the day strip prints the age of the last successful daily run, venue read and reasoning pass, marked stale past `config.FRESHNESS_HOURS` (dated) with the threshold in the words, and `audit.check_the_strip_shows_a_dead_job` refuses a payload that hides a stale job or calls one fresh. Not red: the colour law keeps red for a loss, RULED 2026-09-08 | `plant.py::plant_a_dead_job_the_strip_calls_fresh` |
| 5 | A `urllib` POST carries no verb: `order_path_faults` reads the market module's syntax tree and refuses a `Request(...)` carrying `data=` or `method=` | `plant.py::plant_a_urllib_post_at_the_venue` |
| 4 | Curves are never merged: `assert_no_merged_categories` rejects a category with no concrete market, an `all` prop_type, or a merged forecaster. Runs inside `scorecard()`, so a merge cannot reach the API | `test_guards.py::test_a_planted_merged_prop_curve_is_caught_by_name`, `::test_a_planted_merged_forecaster_curve_is_caught` |
| v2 | Missing stays missing: `compute.assert_missing_is_explicit` runs on every feature vector, and `audit.check_no_silent_defaults` scans the factor code for a reintroduced fallback. `Factor.default` was **removed**, not left unused | `test_guards.py::test_a_planted_zero_fallback_is_caught_by_name`, `::test_a_vector_that_defaults_an_absent_factor_is_caught_at_runtime` |
| 3 | A void is terminal: `prediction_voids` is append-only and a trigger refuses to resolve a voided prediction afterwards | `test_props.py::test_a_void_is_terminal`, `::test_a_void_reason_cannot_be_rewritten` |
| 1 | MLB prop rungs come from `config.MLB_PROP_LADDER`, a dated constant; `questions.assert_on_ladder` refuses a question formed anywhere else | `plant.py::plant_a_rung_off_the_declared_ladder`, `test_mlb_props.py::test_a_rung_off_the_ladder_is_refused_by_name` |
| NO GUESSED SIDES | An unlabelled prop pair is labelled from a one-sided milestone quote, never from the sign of a price; an unseparable pair is refused | `plant.py::plant_a_reversed_side_pair`, `::plant_an_ambiguous_side_accepted` |
| NO GUESSED IDENTITY | The ESPN↔MLB player bridge is measured and stored dated, both match rates reported; two players sharing a normalised name refuse | `plant.py::plant_an_ambiguous_crosswalk_match`, `test_mlb_props.py::test_two_players_sharing_a_normalised_name_are_ambiguous` |
| 4 | A sub-50 probability is stored as a confident claim about the other side, so the bucket set starts at 50 and the tier chip cannot mislabel it | `plant.py::plant_a_home_run_bucket_below_fifty` |
| 2 | `logistic.fit` reports `constant` and `dropped` per factor, and a constant factor is named rather than fitted | `plant.py::plant_a_constant_prop_factor` |
| ORPHANS | `audit.check_no_orphan_functions` fails on a public function the shipped code never reaches; a decorator counts as a call site, `tools/` counts as a caller, `tests/` does not. Runs in `verify.py` step 2 | `plant.py::plant_an_orphan_guard`, `::plant_a_decorated_function_mistaken_for_an_orphan` |
| COMMENTS | `audit._without_comments` blanks comments before the eight raw-text source scanners read `app.js`, `style.css` and `index.html`, so a comment can neither trip a scan nor satisfy one; proved at import | `plant.py::plant_a_comment_naming_the_forbidden_thing`, `test_guards.py::test_a_comment_cannot_stand_in_for_the_code_it_describes` |
| ONE CLAUSE | `calibration.standing_row_clause` is the one rule for which row of a question is graded; the version table and the pace line count through it | `plant.py::plant_a_superseded_row_counted_as_settled` |
| ONE UNIT | `audit.horizon_unit_faults` refuses an outlook whose rate and multiplier count different columns | `plant.py::plant_a_horizon_that_counts_days_for_a_weekly_sport` |
| RECORD FIRST | `run_task` writes a `running` row before the task runs and finishes it after; `audit.task_run_order_faults` reads the order off the syntax tree | `plant.py::plant_a_run_recorded_only_when_it_ends` |
| THE CLOSE | A recommendation closes on its OWN contract's last near-start read before kickoff, or UNMEASURED -- never on the price compared with itself, which is what 49 of 49 closes were until 2026-09-23. `recommendation_closes` records how every close was measured, and a trigger refuses a close that is not a later read of the same contract | `plant.py::plant_a_close_read_from_the_first_of_two_reads`, `::plant_a_close_that_cites_its_own_pricing_read` |
| WITHDRAWN | Operator ruling 1, 2026-09-24: a voided forecast or recommendation is never counted and the page shows it as WITHDRAWN with its reason, never deleted. `recommendation_voids` and `prediction_voids` refuse an edit and a delete. `market.recommend.not_withdrawn` is the one door every read of `recommendations` goes through -- `audit.check_every_recommendation_reader_uses_the_door` names a statement that goes round it -- and `audit.withdrawn_counted_faults` recounts the closing line without the door, inside `views.scorecard` and in the gate. `calibration.standing_row_clause` and `at_the_line.standing_claim_clause` never grade a voided forecast or its claim, even one that settled before it was voided | `plant.py::plant_a_withdrawn_recommendation_in_the_closing_line`, `::plant_a_recommendation_reader_that_goes_round_the_door`, `test_voids.py::test_a_voided_forecast_is_never_graded_even_if_it_settled_first` |
| THE ACTIVATION GATE | Operator rulings, 2026-09-24. A fit is written inactive: `baseline.train` only inserts into `model_fits`, and `baseline.load_fit` reads only the fit named by the market's latest row in the append-only `fit_activations` (`model.activation.active_fit`), so a run after a training step publishes from the incumbent. `model.activation` is the one door that writes the table and the triggers hold the rules: a `measured` row carries its holdout (what was held out, n, candidate and incumbent log loss and Brier on the same rows, the bootstrap 95% interval of the log-loss difference), names the market's active fit as its incumbent, and is refused unless the interval's upper bound is below zero; an `incumbent` row names a fit fitted before 2026-09-24T05:16:00Z (`config.ACTIVATION_GATE_BIRTHDAY`) and carries a holdout whole or not at all; a `scratch` row (test worlds, plantings, the gate's step 3) is refused on any database whose meta kind is `live`. `db.init` bootstraps, once per market, the fit each market was reading when the rule landed if it predates the birthday. An active fit of a factor set the config does not declare is refused by `load_fit` and by `audit.check_every_active_fit_is_the_declared_set` in the gate. `tools/holdout.py` measures (refit through N-1, score N, paired bootstrap) on a scratch copy and writes nothing but the activation row, through the door | `plant.py::plant_a_fresh_fit_used_without_activation`, `::plant_an_activation_without_holdout_scores`, `::plant_a_tie_activated_over_the_incumbent`, `::plant_a_scratch_activation_on_a_live_database`, `::plant_an_active_fit_of_another_factor_set`, `test_activation.py` |
| THE fs5 REVERT | Operator rulings, 2026-09-24 (the three decisions): ties go to the incumbent, all four fs5 markets revert, and "the hold is lifted per market only when that market's active fit is the incumbent and its forecasts are from it". `config.FACTOR_SET_VERSIONS` declares again what each market declared before fs5 (spreads fs3, moneylines fs2 by default); `srs_diff` and `cfb_srs_diff` are reactivated by dated entry (morning ruling 3; the LAW 2 words it rests on are in the registry). `activation.apply_the_fs5_revert`, run by `db.init` before the birthday bootstrap, writes one `incumbent` activation per market -- fits 88, 71, 44, 35 -- carrying the holdout `tools/holdout.py --record` wrote to `gridiron/model/fs5_revert_holdout.json` (the incumbent's factor set refit through 2024 and scored on 2025, and the holdout words say so) and the tie in its reason, and only where the database's fit of that id is exactly the named fit: id, sport, market, factor set, fitted instant. The hold is lifted (`config.FS5_REVERT` keeps each held and lifted date); `audit.check_the_page_forecasts_from_the_active_fit`, in the gate on the migrated copy, refuses a lifted market whose active fit is not its incumbent and any statistical forecast on the page its market's active fit did not write (`baseline.is_its_forecast`: the fit, on the row's own stored values and rung, gives back its probability). `baseline.assert_the_vector_carries_the_fit` refuses a forecast from a fit trained on a factor the registry no longer computes | `plant.py::plant_a_page_forecast_from_a_fit_that_is_not_active`, `::plant_a_revert_activating_the_wrong_fit`, `::plant_a_fit_reading_a_retired_factor`, `test_activation.py` |
| THE GATE READS ONLY | Operator ruling, 2026-09-24, after a worktree gate's step 2 put an unmerged trigger on the operator's record through `open_db`. `tools/verify.py` sets `GRIDIRON_VERIFYING` for its whole run, so `db.connect` refuses the live record by name and `db.refuse_the_live_record` stops `copy_facts` attaching it; `db.read_the_live_record` opens the file `mode=ro` as well as `query_only`, so its holder cannot switch it back to writing. Step 2's record checks and step 3's facts read one scratch copy, backed up through that door and migrated to the tree's schema; step 4 reads the record through the door. The record's schema is read when the gate starts and again when it ends, and a difference fails the gate naming each object. Rows are not counted -- the scheduler writes during every gate -- they are protected by the gate holding no writable handle | `plant.py::plant_a_gate_step_that_opens_the_live_record_writable`, `::plant_a_schema_change_during_the_gate`, `::plant_a_write_through_the_read_handle_switched_back` |
| v2 / WEATHER | Operator ruling 4, 2026-09-24 ("precipitation, wind and cold all follow the same rule. An indoor game carries no value; the fit reports each factor's rows used"), and the fs5 brief's "a training row with no weather can't carry a precipitation value". The context records an indoor game as indoors and why, with no weather reading (`weather.roof_state` is the one test of a roof, shared with the forecast fetch; a roof the source has not yet published is unknown, not open, and carries no value either); each weather factor returns None under a roof and the row lists it absent with its reason. A weather factor declares the reading it is computed from (`Factor.weather`), and `compute.assert_weather_was_read`, inside `feature_vector` -- the one door every training row and every forecast of every sport passes through -- refuses by name (`WeatherNotRead`, a `MissingDataDefaulted`) any weather value on a row that is indoors or whose weather was not read. A factor reading a weather reading without declaring it fails `test_weather_indoors.py`. The Factors page reports each factor's training rows used per market from that market's ACTIVE fit (`calibration._fit_status` through `activation.active_fit` and `baseline.market_key`), and says "indoor games among them" beside a count from a fit trained before the repair (its blob lacks `indoor_weather`). Measured before and after on the 2025 holdout for all eight active markets with a weather factor: no coefficient, log loss, Brier or active-fit forecast moved; the rows used did (FOLLOWUPS) | `plant.py::plant_an_indoor_forecast_carrying_the_weather`, `::plant_an_indoor_training_row_carrying_the_weather`, `::plant_a_training_row_with_no_weather_carrying_precipitation`, `test_weather_indoors.py` |
| 3 | Schema ruling 4, 2026-09-24 (built 2026-09-25): a market snapshot is never deleted. Ids 174-181 are missing from `market_snapshots` because eight near-start rows were deleted by hand at 2026-09-01T00:08:32Z through an ordinary writable `db.connect()`; no code in the repository did it, and nothing refused it, because the table's only rules were the two LAW 1 insert triggers. The trigger `market_snapshots_no_delete` refuses every delete, whoever types it. Measured the same day: a rolled-back or trigger-aborted insert leaves no AUTOINCREMENT hole in this SQLite, so a hole in these ids is a deletion or an ignored insert (FOLLOWUPS). AND NEVER REPLACED (the adversarial review of 3603300, 2026-09-25): `INSERT OR REPLACE` removed the stored row round the delete rule -- SQLite fires no delete trigger for a replacement unless recursive triggers are on -- leaving a hole like 174-181; `market_snapshots_never_replaced` refuses an insert naming a stored id or a forecast and look already stored. Every writer (`lines.snapshot_prediction`, the plantings, the tests) checks first and inserts plainly, so none changes; the migration's definition of the table carries the rule. NOR BY AN UPDATE (the rehearsal of those fixes, 2026-09-25): `UPDATE OR REPLACE` moving one snapshot onto another's id, or its forecast and look, removed the other row the same way; `market_snapshots_never_replaced_by_update` refuses exactly that update and nothing else -- no writer updates these columns, and freezing a snapshot is question 6, not built | `plant.py::plant_a_deleted_snapshot`, `::plant_a_replaced_snapshot`, `::plant_a_snapshot_replaced_by_an_update`, `test_rebuild.py::test_the_migrated_snapshot_table_refuses_a_replacing_insert`, `::test_the_migrated_snapshot_table_refuses_an_update_that_replaces` |
| ONE WAY IN | Schema ruling 6, 2026-09-24 (built 2026-09-25): no raw `sqlite3.connect` to the live record outside the approved handles. A scan cannot know which file a call will open, so `audit.check_no_raw_connect_to_the_live_record` (gate step 2) refuses every raw open -- under any alias, through `dbapi2`, a call of `Connection`, a `getattr`, a star import from `sqlite3`, or an `apsw` or `_sqlite3` import, and from 2026-09-25 (the adversarial review of 3603300) the module bound to another name or handed on as a value (`vars`, a `getattr` by a computed name), a dunder read off it, a subclass of `sqlite3.Connection` and its call (the class may be named only in an annotation or an isinstance), the driver imported by a constant name through `importlib`, `__import__` or `sys.modules` -- in the package, `tools/` (the plantings included), `tests/` and `desktop/`, except inside `db.connect`, the module-level function: the exemption is keyed on the QUALIFIED name, so a helper named `connect` nested in `db.py` is refused. And from the rehearsal of those fixes (2026-09-25), the driver read off ANY other module that holds it -- `db.sqlite3.connect`, `from gridiron.db import sqlite3`, `vars(db)["sqlite3"]`, `getattr(db, "sqlite3")`, `db.__dict__["sqlite3"]`, `sys.modules["gridiron.db"].sqlite3`, `getattr(sqlite3, "dbapi2")`: an attribute named `sqlite3` is the module on any base, and a namespace looked up by a driver's constant name is refused. And from their prover (2026-09-26), any call handed a driver's name as a constant, whatever the callee: `import_module` or `__import__` bound to another name first, `__import__` read out of the builtins, `importlib.util.find_spec`, the name given by keyword. The approved handles are `db.connect` for a scratch file, `db.read_only(path, why)` and `db.read_the_live_record(why)` (both `mode=ro` and `query_only`, with a reason in words), and `db.back_up_the_live_record(target, why)`, which refuses the record as its own target. `audit.RAW_CONNECT_EXEMPT` takes a dated reason and was empty when written. Not seen: a connect inside a string a child runs, and an ATTACH (FOLLOWUPS). The scheduler applying the schema from the main checkout stays as it is, by the same ruling: that is how a release migrates, and only merged code reaches the main checkout | `plant.py::plant_a_raw_connect_past_the_door` (every shape the review found, 2026-09-25), `::plant_a_raw_connect_through_another_module` (every shape its rehearsal found), `::plant_a_raw_connect_through_any_call_by_name` (every shape its prover found), `test_one_way_in.py` |
| NO REAL TIME | Schema ruling 5, 2026-09-24 (built 2026-09-25): "The auth backoff test takes an injectable clock instead of wall time. No test in the gate may depend on elapsed real time." Auth reads time only through `auth._now()`, which asks `auth.clock` (the real clock in production, never reassigned there); `test_auth.py` replaces it with a clock it moves by hand, so the backoff's penalty, its window and the handoff's minute are exact and no longer a race with the machine. `audit.check_auth_reads_one_clock` refuses any other reading of the clock in `auth.py`. `audit.check_no_test_waits_on_the_clock` refuses, in `tests/`, a sleep, a fixed wait in the browser, a reading of `time.time`/`monotonic`/`perf_counter` and their kin, and a difference or comparison reckoned from the real clock, less `ELAPSED_TIME_EXEMPT` (the two server start-up limits, dated) and `ELAPSED_TIME_HELD` (the browser tier's 44 fixed waits, by function and count, held for operator question 5; a function may not gain one and the register can only shrink). Not seen: a test that depends on elapsed time without reading a clock itself, which is what the backoff test did (FOLLOWUPS) | `plant.py::plant_a_test_that_waits_on_the_clock`, `::plant_a_wall_clock_read_in_the_backoff`, `test_the_clock.py`, `test_auth.py::test_the_backoff_survives_a_restart` |
| THE SCHEMA MATCHES THE RELEASE | Schema ruling 1, 2026-09-24 (built 2026-09-25): "The diff check compares after normalising quoting, whitespace, comments and column order, and fails on any difference in behaviour." `gridiron.schema_diff` is the one door: SQL compared as tokens (comments and whitespace gone, string literals exact; a quoted word unquoted and case-folded ONLY where it is certainly a name -- an object's or a column's own name, after CONSTRAINT, COLLATE, REFERENCES, FROM, JOIN, INTO or UPDATE, a key or index column list, either side of a `.`, or in a table's or an index's expression where it names one of the table's columns -- and kept as written anywhere else, where SQLite may read it as a string; a bare word after DEFAULT keeps its case; of a COLLATE, DEFAULT or NOT NULL written twice only the last, which SQLite keeps, is compared: the adversarial review of 3603300, 2026-09-25; a REFERENCES ending NOT DEFERRABLE or SET DEFAULT is not a second NOT NULL or DEFAULT, which erased the column's own: its prover, 2026-09-26), a table's columns by name, each with its type and clauses, its table constraints as a set, and SQLite's own PRAGMA reading of each column as a check on the parser (no PRAGMA shows a CHECK; its default read as a default). Gate step 2 runs it twice: the live record, through the read-only door, against a database `db.init` built from nothing in a child from `git archive` of the branch master -- the release; and the gate's migrated copy against a database this tree built from nothing, which sees before a merge what a release would leave behind. `audit.SCHEMA_DIFFERENCES_REGISTERED` holds, dated, each measured difference with its commit and what clears it -- the eight ruling 2's migration clears (the release comparison's `spread_sign_source` was a ninth until 3603300 released ruling 3's declaration, and the next commit removed it). A difference not in it fails by name; a registered one no longer found fails too, so the commit after the migration runs empties it, and from then on any difference fails. **EMPTIED 2026-09-26 (5b)**: the migration ran on the live record at 02:12:57Z from the released f4c4db2 after a verified backup, and the eight entries now live on as history in `audit.SCHEMA_DIFFERENCES_CLEARED_2026_09_26`, which nothing reads as a register | `plant.py::plant_a_new_schema_difference_on_the_record`, `::plant_a_cleared_difference_left_in_the_register`, `test_schema_diff.py` (`::test_quoted_text_that_changes_behaviour_is_a_difference` and its neighbours: every example the review gave), `test_the_schema_matches.py` |
| A REBUILD IS VERIFIED OR NOT DONE | Schema ruling 2, 2026-09-24 (built 2026-09-25): "new table with the released definition, copy every row, verify the row count and a checksum of every column match exactly, recreate every trigger and index, then swap, all in one transaction ... If any table fails verification, the transaction rolls back and nothing is swapped." `gridiron.rebuild` is the one door and names no table: in one BEGIN IMMEDIATE, with foreign keys off and `legacy_alter_table` on (nothing else is repointed), each table is renamed aside, created from the released text, copied by an explicit column list (implicit rowids kept), and its row count and a SHA-256 of every column compared exactly; its sequence is carried and its indexes and triggers recreated from the released text; then `foreign_key_check`, `integrity_check` and every other schema object byte for byte, then COMMIT -- any failure is a ROLLBACK, re-read to prove nothing swapped. A table already at its definition (as ruling 1 compares) is skipped. `tools/migrate_2026_09_25_behaviour.py` is the dated migration of the eight (the snapshot table's entry from `market.lines`, LAW 1): refused on the live record without `--live` and a verified backup made in the same run (`rebuild.verified_backup`: the backup door, then `integrity_check`, every sqlite_master row byte for byte, and every table's count and column checksums against the record at the instant copied); `--rehearse` migrates a verified copy. `db.init` does not run it: the operator does, after the release, at a quiet hour. FROM THE ADVERSARIAL REVIEW OF 3603300 (2026-09-25): a column checksum hashes each value exactly -- its storage class and bytes, a real's IEEE-754 bytes -- where `quote()` made -0.0 equal 0.0 and ended a text at its first NUL; the record is known by the FILE'S IDENTITY through `db.is_the_live_record_file`, the one door `tools/reconstruct_prompts.py` also asks (configured, default, this checkout's and the main worktree's record, `os.path.samefile`), so a worktree, a hard link or a GRIDIRON_DB/HOME/STATE setting no longer makes the record "not the record", and `--live` on anything else is refused; with `--live` the definitions it would write, the map's snapshot entry and the running `schema.sql` must equal master's (`git show`, line endings apart) or it refuses by name before the backup; `--report` must be a new file that is not the database, the record, the backup, the scratch copy or a file SQLite keeps beside one, checked before anything is done and created exclusively; the live run prints the backup's instant and the lock's, because rows written between them are not in the backup. FROM THE REHEARSAL OF THOSE FIXES (2026-09-25/26): every file the run creates -- report, backup, scratch copy -- is a file of its own, through one door, `db.not_a_file_of_its_own`, which `db.back_up` asks too: not a Windows stream inside another file (a colon: `<record>:x` wrote the report, the backup and a whole rehearsal copy INTO the record's file, and an ISO time in a name does it by accident), not a name Windows strips a dot or a space from, and not the database, the record or a -wal, -shm or -journal beside either (SQLite deletes such a file when it next opens the database: `--live --backup <record>-journal` lost its verified backup before the run ended, exit 0, the record migrated). And `db.widen_sport_checks` rebuilds the tables a newly declared sport widens through this door, foreign keys off, so no child is repointed at a table renamed aside | `plant.py::plant_a_rebuild_that_alters_a_row`, `test_rebuild.py` (`::test_a_report_is_never_written_over_the_record_the_backup_or_a_database`, `::test_the_record_is_known_by_its_identity_whatever_runs_the_tool`, `::test_live_refuses_definitions_that_are_not_the_release`, `::test_the_checksum_tells_every_stored_value_apart`, `::test_a_backup_whose_schema_differs_from_its_source_is_refused`, `::test_a_sixth_sport_after_the_migration_repoints_nothing_and_changes_no_row`, `::test_a_file_the_run_creates_is_never_a_stream_or_another_name`, `::test_a_backup_or_a_copy_is_never_a_file_sqlite_keeps_beside_a_database`, `::test_a_rehearsal_does_not_say_its_copy_lost_rows`) |
| THE PROMPT RECORD | Operator rulings, 2026-09-24 (two additions, item 1: "The reasoning pass stores the exact prompt it sent ... with every row it writes, append-only. No reasoning row may exist without it") and 2026-09-25 (question 4: "the prompt-record rule binds from the release that ships it, and the gap before it is labelled, not exempted"), built 2026-09-25. `model.prompt_record` is the one door to the append-only `reasoning_prompts`. SENT: `llm.reason` serializes the exact request -- every message, the system prompt, the model and its parameters -- as canonical JSON before the call and sends the parse of those bytes; `predict.write_prediction` refuses a reasoning row without it (`PromptNotKept`) and writes the record first, then the row citing it in its frozen, fingerprinted factors (`reasoning_prompt_id`), then the fingerprint, in one savepoint -- together or not at all; the reformatting request is kept with it when that runs. THE RELEASE INSTANT is data: the first `db.init` under the schema writes `prompt_record_binds_from` into `meta` once (now, or a second after the newest reasoning row), and triggers refuse a second value, an edit and a delete. `reasoning_row_carries_its_prompt` refuses a reasoning row at or after the instant without a sent record of its own game and claim, sent no later, cited by no other row, and cited by the record's integer id and nothing spelled like it (the prover of 2026-09-25 found a text cite matched its record by affinity yet passed the no-other-row test, so two forecasts shared one prompt; `prompt_record.records_for` reads a cite the same way); `reasoning_prompt_reconstructed_only_before_the_release` refuses a reconstruction of any other row; the table refuses an edit, a delete and a replacing insert. RECONSTRUCTED: `tools/reconstruct_prompts.py` rebuilds every row with no record through the code of the main checkout's commit at its minute (its reflog), `git archive`d and run in a child from the row's stored inputs, storing the full commit, the date and words saying what the commit cannot vouch for (the working tree the scheduler ran until about 22:47Z on 23 September; no enclosing task run; a number stored exactly halfway at its fourth place); refused on the live record without `--live`, which is known by the file's identity, and it writes nothing else. Gate step 2 applies it to its migrated copy ONLY WHILE THE RECORD ITSELF HAS NO RELEASE INSTANT, and from the release on checks the record's own records as they stand (`verify._bring_the_copy_to_this_tree`; the rehearsal of 2026-09-25 found the gate rebuilding a released copy, which hid a forecast with no record behind a commit that never wrote it); `audit.check_every_reasoning_row_has_its_prompt` names every row after the instant without its sent record, every row of any date with none, and every record whose text does not match its hash; `check_the_prompt_record_has_one_door` names a write round the door. The page, Results and the Record page (reasoning pass picked) show a reasoning forecast's prompt collapsed, labelled by the record's own kind in `language` words -- "The prompt, reconstructed" or "The prompt it was sent" -- and `audit.check_the_prompt_says_what_it_is` refuses a disclosure without the word or under the wrong label. The prompt itself is shown VERBATIM in a `.code-literal` block, the existing exemption for a string a reader must see exactly: a prompt with its identifiers rewritten would match no stored hash and would not be the prompt (FOLLOWUPS) | `plant.py::plant_a_reasoning_row_after_the_release_without_its_prompt`, `::plant_a_reasoning_row_with_no_record_at_all`, `::plant_an_edited_prompt_record`, `::plant_a_prompt_whose_text_does_not_match_its_hash`, `::plant_a_reconstructed_prompt_shown_without_the_word`, `::plant_a_released_record_the_gate_rebuilds_before_checking`, `::plant_a_second_forecast_citing_a_sent_prompt_as_text`, `test_prompt_record.py`, `test_prompt_disclosure.py` |

Run them all at once, each violation planted for real:

```bash
python tools/guards/plant.py --verbose
```

And the whole verification:

```bash
python tools/verify.py
```

## Conventions

- Read docs/MENTOR.md at the start of every session.
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
- **PLAIN WORDS. No internal identifier ever reaches the interface.** No
  snake_case, no column named after a database field, no jargon a first-time
  reader would have to decode. Every visible label is a phrase a person would
  say out loud: "Saquon Barkley over 95.5 rushing yards", not
  `rushing_yards`; "Market then", not a second column also called `market`;
  "no line", not a bare em-dash, which reads as an error rather than an
  absence. This is not decoration. A record nobody can read is a record nobody
  can check, and every law above about showing the N and never merging a curve
  assumes a reader who can tell what they are looking at.

  Enforced, not trusted: a rendered-page scan fails on snake_case or a known
  internal term in visible text, and `tools/guards/plant.py` puts
  `rushing_yards` in a label to prove the scan fires.

- **`gridiron.audit` stays outside the prediction closure.** It holds the list
  of forbidden market identifiers, so a prediction-path module that imported it
  would make the LAW 1 scan flag itself. The runtime missing-data check
  therefore lives in `factors.compute`, and `audit` re-exports it.

---

## The activation gate — RULED 2026-09-24

**THE ACTIVATION GATE (ruled 2026-09-24): a fit is written inactive; it
becomes the market's model only by a dated activation recording its holdout
against the incumbent; ties go to the incumbent — activation needs the
bootstrap interval of the log-loss difference to exclude zero.**

The operator's words, from ruling 2 of the morning and the tie rule of the
three decisions (`docs/briefs/2026-09-24-morning-rulings.md`,
`docs/briefs/2026-09-24-three-decisions.md`): "Training a fit must not make it
live ... The predict path reads only activated fits. A logon catch-up or
scheduled run after a training step publishes from the incumbent." And: "A new
fit is activated only if it beats the incumbent on the holdout with the
bootstrap interval of the difference in log loss excluding zero; otherwise the
incumbent stays."

**Why.** Until that day the model a market forecast from was the newest fit of
its declared factor set, so training a fit was the same act as publishing
from it. Fits 91-94 were trained on the live record at 05:16Z on 24 September
and the logon catch-up published from them at 05:32Z; measured afterwards on
the 2025 season they were not better than what they replaced, and none of the
four clears the tie rule, NFL moneyline included.

**How it binds.** Training inserts into `model_fits` and nothing else. The one
door is `gridiron/model/activation.py`; the rules are the triggers on
`fit_activations`. The rule's birthday is 2026-09-24T05:16:00Z: a fit fitted
before it may be recorded as an incumbent (the bootstrap of every market in
use when the rule landed, and a revert to one of them); a fit fitted on or
after it is activated by measurement or not at all. `tools/holdout.py` makes
the measurement. A market with no incumbent has no lawful activation on the
live record until the operator rules (`docs/REPAIR_STATE.md`, "Questions for
the operator"). Test worlds, plantings and the gate's scratch pipeline train
their own fits and activate them as `scratch`, which the schema refuses on a
database whose meta kind is `live`.

**The revert (the same day).** Measured by `tools/holdout.py`, none of fits
91-94 beats its incumbent, so all four fs5 markets went back to fits 88, 71,
44 and 35 as `incumbent` activations recording the tie, and their hold was
lifted. A fit is only ever read with every factor it was trained on: the
feature vector is built from the registry, not from the fit, so a factor
retired after a fit was trained would otherwise drop out of its forecasts
without a word -- which is why the plain ratings fs5 retired came back with
the fits that use them.

---

## The release path — RULED 2026-09-09

**Gate, commit, push, restart, confirm.** The last two are one move: the
interface is a Python process and Python does not hot-reload, so a pushed
commit is not a running commit until something restarts.

```bash
python tools/verify.py                     # all four steps, no flags
git commit && git push                     # and check the remote matches
# kill the serving process; Gridiron-Serve brings it back within two minutes
curl -s http://127.0.0.1:8848/api/health   # must answer the commit just pushed
```

**THE BUILD IDENTITY IS THE COMMIT HASH PLUS WHAT `/api/health` ANSWERS.**
There is no binary to hash any more. A SHA-256 of an executable said what was
BUILT; the health line says what is actually SERVING, which is the question
anyone asking "what version is this?" is really asking.

**AND THE HEALTH LINE MEANS THE PROCESS, NOT THE CHECKOUT.** It did not, for
about a minute: from source there is no build stamp, so the id fell through to
the repository's HEAD, read fresh on every request -- a commit landing while
the server was up changed the answer without changing a byte of the code in
memory. `api.serve` pins it now (`buildinfo.freeze`), which is what makes the
restart step meaningful rather than decorative: if you skip it, the health
line tells you so.

**The PyInstaller bundle is retired**, and "rebuild, hash" is no longer a step
in this path. `desktop/gridiron.spec` and `desktop/make_shortcut.ps1` are kept
and marked, because a step that vanishes is a step nobody can audit; neither
is part of a release. Why it went is in `FOLLOWUPS.md`: Smart App Control
blocked the unsigned binary this machine built itself, and the answer is not
to argue with the security setting.

`Gridiron-Serve` runs `pythonw.exe -m gridiron.cli serve` from the repository,
at logon, `StartWhenAvailable`, restarted by the scheduler if it dies.

---

## Ending a session

**Every session ends with a close-out table against its brief's phase list.**
One row per phase, one of four verdicts, and one line of evidence each:

| verdict | means |
|---|---|
| **DONE** | built, tested, and the evidence is nameable |
| **PARTIAL** | some of it shipped; the row says which part did not and why |
| **SKIPPED** | not built, and the row says whether that was a decision or an oversight |
| **DECLINED** | refused, with the law or reason named |

The table is not a summary. It is a check against the brief, written last,
when the temptation is strongest to describe the work as more complete than it
is. A phase that quietly vanished between the brief and the report is the
failure this convention exists to catch — it has happened here at least once,
when the greeting was assigned, not blocked, and simply not built, and the
session report did not say so because nothing forced it to.

SKIPPED and DECLINED are ordinary outcomes. A brief that produces four DONEs
every time is a brief nobody is reading carefully.
