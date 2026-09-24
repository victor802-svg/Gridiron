# GRIDIRON_REPAIR — state for the next session

## READ THIS BLOCK FIRST (updated 2026-09-24 ~11:35Z, overnight run)

- **Released and serving: ff7e5ab** (`/api/health` = ff7e5ab7546c), on main
  and pushed: **the activation gate** (repair 2c). Gate: 4/4, 275/275
  plantings, live record as found.
- **On the live record since the release:** 24 `incumbent` activations
  written by the bootstrap at 11:28:31Z, one per market in use, each naming
  the fit that market was already reading. **The four fs5 markets have
  none**: fits 91-94 post-date the rule, so NFL and NCAAF spread and
  moneyline are unforecast (and still held) until the revert.
- **Earlier today:** 55 restated closes (item 1); 31 forecast voids and
  recommendations 62, 63, 64 and 66 withdrawn (65 stands; the 31
  reasoning-forecaster rows stand).
- **The overnight queue** (docs/briefs/2026-09-24-overnight.md; the operator
  reordered it because the hold blocks football forecasts before Sunday):
  1. ~~Activation gate~~ -- released ff7e5ab.
  2. **Revert** all four fs5 markets to their incumbents (NFL spread fs3 fit
     88, NFL moneyline fs2 fit 71, NCAAF spread fs3 fit 44, NCAAF moneyline
     fs2 fit 35); lift the hold per market once its forecasts come from its
     active fit; confirm on the day strip.
  3. Weather: precipitation, wind and cold carry no value indoors; report
     coefficients before and after on the holdout.
  4. The reasoning-pass prompt record.
  5. Schema rulings (below, in the order the brief gives).
  6. Repair items 3-8.
- **The schema rulings, as queued before the overnight reorder** (their
  content stands; only their place moved):
  1. **Schema rulings** (docs/briefs/2026-09-24-schema-rulings.md):
     - (5) the auth backoff test takes an injectable clock, and no gated test
       may depend on real elapsed time
       (`test_auth::test_the_backoff_survives_a_restart` flaked once: its
       4-second penalty ran out under gate load);
     - (1) a gate diff of the live schema against a fresh build at the
       released commit, normalised for quoting, whitespace, comments and
       column order, failing on any difference in behaviour;
     - (3) schema.sql declares market_lines_raw.spread_sign_source;
     - (2) a dated, rehearsed, single-transaction migration of the 8
       behavioural tables, with row counts and per-column checksums verified,
       triggers and indexes recreated, a verified backup of the live record
       taken first, and a rollback if anything fails verification;
     - (4) the 8 missing market_snapshots ids: rolled-back insert or deletion,
       and a fix with a planting if any was deleted;
     - (6) a scan refusing a raw sqlite3.connect to the live path outside the
       approved handles, with a planting.

## Questions for the operator

Each blocks only its own step; the queue moves on where the next step does not
depend on the answer.

1. **A market with no incumbent (the activation gate, 2026-09-24).** Ties go
   to the incumbent, and a market that has never had an active fit has none.
   How may its first fit be activated on the live record? Until ruled there is
   no lawful path, and the schema refuses every one: a `measured` activation
   must name the market's active fit as its incumbent, an `incumbent`
   activation must name a fit fitted before 2026-09-24T05:16:00Z, and a
   `scratch` activation is refused on a live database. No rule was invented.
   Today every forecast market has an incumbent except the four fs5 markets,
   which the revert gives their pre-birthday fits; the case arrives with the
   next market declared. (The same gap covers a revert to a fit fitted after
   the birthday that was once activated by measurement: no kind admits it.)
2. **NBA spread and total forecast from fits trained through 2024 only.**
   Found by the bootstrap simulation: fits 80 (spread, fs4) and 79 (total,
   fs2), `season:2024`, written 23:52-23:54Z on 4 September by a walk-forward
   run on the live record, silently replaced fits 61 and 70 (every season)
   under the newest-fit rule -- the 91-94 failure, earlier. The bootstrap
   records 80 and 79 as the incumbents, because they are what those markets
   were forecasting from. Keep them, or revert to 61 and 70 (lawful as
   `incumbent` activations; both predate the birthday)? FOLLOWUPS has the
   numbers.

(Older detail follows; where it conflicts with the block above, the block wins.)


Read this first, then `docs/briefs/2026-09-23-repair.md`,
`docs/briefs/2026-09-24-fs5-before-it-publishes.md` and
`docs/briefs/2026-09-24-morning-rulings.md`. Working method (ruled 2026-09-24):
**one operation at a time**; no rehearsals, splits or scripts against the
worktree while a gate runs; no concurrent gates.

## Where the code is

- Main checkout `C:\Users\stace\.claude\sessions\gridiron` is on **4941fa1**,
  pushed, and serving (`/api/health` = 4941fa153c47). The scheduler runs it.
  It must stay clean: work reaches it only by `git merge --ff-only repair`
  after a green gate.
- Worktree `C:\Users\stace\.claude\sessions\gridiron-repair`, branch `repair`,
  one commit ahead (1743a15, the item 1 close-out, documents only). `var` in
  the worktree is a junction to the main `var` (the live record). Python:
  `../gridiron/.venv/Scripts/python.exe`. Gate from the worktree:
  `../gridiron/.venv/Scripts/python.exe tools/verify.py` (about 25 minutes).
- Landed today: 23cf89b repair 1 (the closing line), d782380 (the word-scan
  fix the gate needed), 4941fa1 (the hold). The live write for item 1 is done:
  55 restated rows in `recommendation_closes`.

## What is live and why

**The hold** (`config.HELD_MARKETS`): NFL and NCAAF spread and moneyline are
not forecast and not shown, and the day strip says so. It stays until rulings
1-4 land. The rows below are hidden by it, not voided.

**fs5 fits 91-94** were trained on the live record 05:16-05:17Z on 24 September
(NFL on 2016-2025; NCAAF "2023-2025", which is really 2024-2025, since there are
no 2023 college games). The logon catch-up at 05:32-05:36Z published from them
before the hold:

- 31 statistical-forecaster rows (NFL spread 13, NFL moneyline 16, NCAAF spread
  1, NCAAF moneyline 1), `created_utc >= 2026-09-24T05:16`,
  `factor_set_version = 'fs5'`, `predictor = 'statistical'`
- recommendations 62, 63, 64 and 66, all NFL spread fs5

## Rulings since this file was first written (all in docs/briefs/)

- **Three decisions (2026-09-24-three-decisions.md).** Rec 65 stands. Of the 31
  reasoning-forecaster rows, 0 carried fs5 output (prompts rebuilt; none was
  saved), so all 31 stand. **Holdout rule: ties go to the incumbent.** A new
  fit activates only if it beats the incumbent's holdout log loss with the
  bootstrap interval of the difference excluding zero. So **all four fs5
  markets revert, NFL moneyline included** (fs2, fit 71). Record the rule in
  CLAUDE.md as part of the activation gate. Lift the hold per market only when
  that market's active fit is the incumbent and its forecasts come from it.
- **Two additions (2026-09-24-two-additions.md).** The reasoning pass stores
  the exact prompt it sent, or its hash plus the full inputs, with every row,
  append-only. No reasoning row without one; planting. Queued after the
  revert and weather, before item 3.
- **Order now:** voids (this batch) -> inactive-until-activated fits with the
  activation gate -> revert of all four -> weather -> the prompt record ->
  repair items 3-8. Each is its own commit, gate and release.

## The gate reads only, and the schema diff (2026-09-24, late morning)

- **The gate reads only** (docs/briefs/2026-09-24-the-gate-reads-only.md):
  built and committed with the voids. Record checks run on a migrated scratch
  copy, and a schema change during the gate fails it. Open: the scheduler's
  `db.init` still applies whatever schema is in the main checkout, and a raw
  sqlite3 write inside a gate step is not refused (FOLLOWUPS).
- **The schema diff** (docs/briefs/2026-09-24-schema-diff.md; measured
  read-only, report in the 24 September session's scratchpad/schema/
  diff_live_vs_fresh.txt):
  - Live against a fresh build at release 4941fa1: 0 objects on live that the
    release does not create, 0 missing.
  - 19 objects with different SQL: 17 tables and 2 triggers.
  - BEHAVIOURAL, 8: CHECKs missing on live for factors.sport,
    factor_scores.sport, model_fits.sport (9c0bc64), market_snapshots.kind
    (2d0e98f; the migration code must live in gridiron.market),
    mlb_lineups.source (8002a38), prediction_ranks.on_shortlist (63d998c) and
    ufc_events.event_tier (c78af51, bdfaddc). nba_injuries.player_name has an
    extra DEFAULT ''. Every live row already satisfies the released
    constraints. Rebuild each by renaming aside with legacy_alter_table=ON,
    creating the table with the released text, copying by column name with
    count and hash verified, then restoring sqlite_sequence, triggers and
    indexes and running foreign_key_check. ufc_events must be renamed aside in
    legacy mode, or ufc_bouts gets repointed.
  - COSMETIC, 11: teams, sessions, mlb_pitcher_starts, notifications,
    task_runs, at_the_line_claims, venue_quotes, recommendations (a comment),
    prediction_voids, market_snapshots (the quoted "predictions"), plus the
    triggers snapshot_requires_prediction and snapshot_not_before_prediction.
  - **Two readings for the operator, not yet ruled:** (A) exact byte match:
    rebuild all 17 tables, including the dense-trigger claim and quote tables,
    and re-create the 2 triggers; (B) rebuild the 8 behavioural tables and
    re-create the 2 triggers, and have the gate's diff compare after
    normalising quoting, comments, whitespace and column order. Default until
    ruled: (B), which puts less risk on the live record.
  - Also found: schema.sql does not declare
    market_lines_raw.spread_sign_source (only lines.ensure_raw_columns adds
    it), and market_snapshots holds 2,187 rows with a highest id of 2195, so
    8 ids are missing from an append-only table. Investigate both.
- **Order now:** voids + gate-reads-only (this batch) -> the schema diff check
  and its dated migration -> inactive-until-activated fits -> revert -> weather
  -> prompt record -> repair items 3-8.

## Next: rulings 2-4 of 2026-09-24 (the voids are in this batch), BEFORE items 3-8

1. **Voids.** Write one `prediction_voids` row for each of the 31 statistical
   rows. Reason: "published from an unvalidated fit before the hold; fit
   subsequently failed holdout", or for NFL moneyline "... fit not yet
   validated". Add an append-only `recommendation_voids` table and void 62, 63,
   64 and 66. Voided rows are excluded from CLV, calibration, correction,
   readiness and every gate. The page shows them as withdrawn, in those words.
   picks_taken has no single-pick tap. Planting: a voided recommendation
   counted anywhere fails by name.
   - **Readings taken, put back to the operator:** rec 65 (an NFL total from the
     reasoning forecaster on fs2, inside the "62-66" range) is NOT voided. The
     31 reasoning-forecaster rows written in the same runs are NOT voided,
     because they were not written from a fit.
2. **Activation.** A fit is written inactive and becomes live only by an
   explicit, dated activation row that records its holdout scores against the
   incumbent. The predict path reads only activated fits. Plantings: a fresh
   fit with no activation is never used, and an activation without holdout
   scores is refused.
   - **Design notes:** an append-only `fit_activations` table.
     `baseline.load_fit` reads the latest activation for the market. Existing
     incumbents trained before 2026-09-24T05:16Z get grandfathered activations
     (the rule binds from its birthday). An audit check: the active fit's
     factor set equals `config.FACTOR_SET_VERSIONS`.
   - **Expect a large fixture ripple.** Every test, planting and the gate's
     step 3 trains and then predicts, so each needs a lawful activation path
     (a real holdout helper).
3. **Disposition (SUPERSEDED by the tie rule: all four revert).**
   - Revert NFL spread to fs3 (fit 88), NFL moneyline to fs2 (fit 71), NCAAF
     spread to fs3 (fit 44) and NCAAF moneyline to fs2 (fit 35), dated. Fit 92
     is NOT activated: it did not beat the incumbent with the interval
     excluding zero.
   - Registry: `srs_diff` active again for the NFL game markets it had
     (`NFL_GAME_MARKETS`); `nfl_rating_decayed_diff` retired, dated;
     `cfb_srs_diff` active; `cfb_rating_decayed_diff` retired, dated. Every
     note cites the holdout numbers and the tie rule.
   - The page shows only forecasts from each market's active fit.
   - Lift the hold per market once its active fit is the incumbent and its
     forecasts come from it.
4. **Weather.** Precipitation, wind and cold give no value for an indoor game.
   Today the weather lookup (`factors/context.py` `_weather`) and each factor's
   `if ctx.indoors` branch fill 0.0. The fit reports each factor's rows used.
   Report each factor's coefficient before and after on the holdout: expected
   identical, because a 0.0 contributes nothing to the fit. Retrain NFL spread
   (fs3) after the fix, and activate it with holdout scores. Guard
   `compute.assert_weather_was_read`, plus plantings.
5. Merge, push, restart, confirm. Close-out for item 2 with the tables below.
   Render the day strip and the Upcoming page at 1100px and 390px through the
   test harness's signed-in world: the live app needs a token, and entering
   one is not allowed.

## Holdout (train through 2024, score 2025; scratch copy of the record, no network)

| market | n | log loss new / old | Brier new / old | new − old [95% CI] |
|---|---|---|---|---|
| NFL spread fs5 v fs3 | 272 | .68904 / .68361 | .24786 / .24535 | +.0054 [−.0094, +.0205] |
| NFL moneyline fs5 v fs2 | 271 | .62773 / .63666 | .21889 / .22342 | −.0089 [−.0255, +.0077] |
| NCAAF spread fs5 v fs3 | 839 | .68377 / .68211 | .24571 / .24469 | +.0017 [−.0041, +.0084] |
| NCAAF moneyline fs5 v fs2 | 888 | .50714 / .50343 | .16984 / .16912 | +.0037 [−.0143, +.0215] |

None is measurably different. The reading taken is that **"worse" means the
point estimate** on the two numbers placed side by side, so three markets revert
and NFL moneyline ships. The other reading, measurably worse, would ship all
four. It is recorded for the operator. The coefficient and share tables are in
the holdout agent's report. Findings: NFL spread flips sign between the sets
(correlation .67); home_field and neutral_site mirror each other exactly.

## Precipitation, per training season (NFL spread, 2016-2025)

Read 0 / filled 760 / absent 1,872. Every filled value was a dome 0.0.
Wind and cold: read 1,703 / filled 760 / absent 169. Per season (read / filled
/ absent for precipitation): 2016 0/62/194, 2017 0/59/197, 2018 0/60/196, 2019
0/59/195, 2020 0/91/165, 2021 0/78/193, 2022 0/84/186, 2023 0/81/188, 2024
0/94/178, 2025 0/92/180.

## Also found today, for FOLLOWUPS if not already there

- The scheduled tasks never fetch weather forecasts: `weather_forecasts` holds
  9 rows, from 29 August.
- The Factors page reads the wrong fits: `calibration._fit_status` looks up
  'prop:total' and defaults to fs2.
- `INSERT OR REPLACE` bypasses the append-only triggers.
- Predict-time captures file cached bytes as near-start reads.
- One test reads the operator's `.env`.
- A comment containing the words that open a SQL declaration breaks
  `at_the_line._schema_statements`.

## Spend, 24 September session

Local agents: repair map 2,265,274 tokens; item 1 review 737,255; precipitation
investigation 209,164; holdout 145,803. Plan usage at 06:26Z: 20% of the 5-hour
window, 19% of the week. Extra usage: $0.00.
