# GRIDIRON_REPAIR — state for the next session (written 2026-09-24 ~07:10Z)

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
