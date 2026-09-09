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

**PACKAGES ARE GRADED, NEVER BUILT.** (Amended 2026-09-08 by operator ruling,
replacing "SINGLES ONLY". The text it replaced is kept beneath.)

The venue assembles multi-leg packages and sells them. The engine MAY price one
it reads, and may never assemble one: it does not choose legs, does not combine
them, and does not compute a package price the venue has not published.

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
