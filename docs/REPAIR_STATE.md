# GRIDIRON_REPAIR — state for the next session

## READ THIS BLOCK FIRST (updated 2026-09-25 ~03:50Z, overnight run)

- **Revert confirmed on the day strip.** The 15:00Z passes on 24 September
  (final:nfl, final:cfb, both ok) wrote NFL spread 13 rows (fs3), NFL
  moneyline 16 (fs2), NCAAF spread 1 (fs3) and NCAAF moneyline 1 (fs2); the
  strip shows no held line; the gate's page check, run read-only on the live
  record at 03:20Z on 25 September, passes: every statistical forecast on
  the page is reproduced by its market's active fit, and every active fit is
  its declared set.
- **The machine was off 23:13:50Z (24 Sep) - 03:17:12Z (25 Sep)**: a power
  off initiated by winlogon for SYSTEM (event 1074; no title), not a sleep.
  Thursday's NFL game kicked off at 00:15Z inside that gap, so no near-start
  read was taken for it. The logon catch-up ran at 03:17Z.
- **Item 4, the prompt record, is RELEASED: f6e57f3** (`/api/health` =
  f6e57f3d27d7, 22:36:19Z on 25 September; gate 4/4, 295/295 plantings;
  released in a quiet window, no pass running). The release instant on the
  record is **2026-09-25T22:36:19Z**. `tools/reconstruct_prompts.py --live`
  then wrote **538 reconstructed records, 538 of 538 reasoning forecasts**
  (14 commits; 7.2 s; exit 0; none committed after the instant), and the
  gate's audit passes on the live record read-only. The first `sent`
  records come from the next reasoning pass (Predict-MLB, 05:00Z).
- **The machine was off again 08:35:30Z - 19:18:03Z on 25 September.** Both
  overnight gaps (and nine more since 21 September) are event 1074 from
  winlogon for SYSTEM with reason 0x500ff, "power off" -- the signature of a
  power-button or sign-in-screen shutdown, not an update restart (those say
  "Operating System: Upgrade (Planned)").
- **5a' RELEASED: f4c4db2** (02:12Z on 26 September; gate 4/4, 299/299):
  the eight review findings fixed, plus five more holes the rehearsal of the
  fixes found (NTFS streams and sidecar names as report/backup targets,
  UPDATE OR REPLACE on snapshots, the driver read off another module, a
  false note).
- **THE LIVE MIGRATION RAN** at 02:12:57Z on 26 September from f4c4db2: a
  final rehearsal on a fresh copy first (clean), then the verified backup
  `var/gridiron.db.pre-behaviour-migration-2026-09-26.bak` (60 tables,
  1,191,063 rows, every count, checksum and schema object equal), then one
  transaction: all eight tables rebuilt and verified, every column's exact
  checksum equal before and after, sequences 94 / 2558 / 5116 carried,
  foreign_key_check 0 rows, lock 3.52 s. COMMITTED.
- **5b RELEASED: 9d7af57** (`/api/health` = 9d7af570e047; gate 4/4,
  299/299): the register is empty; the live record matches the release
  with 0 registered differences, and from now on any difference fails the
  gate. **The schema rulings are complete.**
- **Item 2's remainder RELEASED: d7b4dfa** (`/api/health` = d7b4dfa40ecb,
  04:49Z on 26 September; gate 4/4, 302/302): a run writes what has a model,
  then fails by name for any active market without one, and the day strip
  says so; no scheduled pass turns red (measured read-only first).
- **Order now:** ~~5a~~ -> ~~item 4~~ -> ~~5a'~~ -> ~~migration~~ -> ~~5b~~
  -> ~~item 2's remainder~~ -> **item 3** (in progress) -> items 4-8 of the
  repair. (Was: item 2's remainder ("run.py:99 may never skip an untrained market
  silently -- a predict run with a skipped market fails by name, and the day
  strip shows it"; never applied: the activation gate made fits explicit
  but `run.already_answered` still drops a market with no model in silence)
  -> repair items 3-8.
- **5a is RELEASED: 3603300** (`/api/health` = 3603300cbde0, 08:05Z on 25
  September; gate 4/4, 288/288 plantings, both schema comparisons pass with
  only registered differences; the first gate run failed on a browser race,
  `test_the_weekly_strip_renders_with_hit_targets`, a canvas read before its
  paint while a review agent loaded the machine -- it passes alone; the
  rerun alone was green). `market_snapshots_no_delete` is on the live
  record. The migration tool is NOT run.
- **Before the migration runs, the tool must be fixed** (an adversarial
  review of 3603300, meant for the cloud but run locally -- see the
  close-out): `--report` can overwrite the record or the backup; the `--live`
  guard is keyed on the running checkout's config path and can be bypassed;
  the released definitions are not checked against master; schema_diff
  lower-cases double-quoted text (a CHECK against "NFL" and "nfl" compare
  equal -- latent, no such literal today); `INSERT OR REPLACE` gets round
  the snapshot no-delete trigger; the raw-connect scan misses aliasing;
  checksums miss -0.0 and text after a NUL; after the migration,
  `widen_sport_checks` would rename `model_fits` with foreign keys on and
  leave `fit_activations` pointing at a dropped table. These go in 5a' after
  item 4 and before the migration.
- **Next commit must remove the register's ninth entry**
  (`market_lines_raw.spread_sign_source`): 5a's release cleared it, so every
  gate now reports it "CLEARED, STILL REGISTERED" until it goes.

- **Released and serving: fddd61b** (`/api/health` = fddd61b8d635), on main
  and pushed: **weather** (repair 2e), after 4c3bda4 **the fs5 revert**
  (repair 2d) and ff7e5ab **the activation gate** (repair 2c). Gates: 4/4
  each; 275, 278, then 281 plantings, all caught; live record as found each
  time. (The revert's first gate failed on the package side-in-prose scan --
  its new audit message quoted a raw subject -- fixed and rerun green.)
- **Weather (2e):** an indoor game carries no wind, cold or rain value in
  any sport; the Factors page reads rows used from each market's active
  fit. The 2025 holdout refit moved no coefficient and no score in any of
  the 8 weather-bearing markets (FOLLOWUPS, "Weather: an indoor game
  carries no value"). Question 3 below.
- **On the live record since the releases:** 24 `incumbent` activations by
  the bootstrap at 11:28:31Z, one per market in use; then activations 25-28
  at 13:00:01Z, the revert: NFL spread fit 88 (fs3), NFL moneyline fit 71
  (fs2), NCAAF spread fit 44 (fs3), NCAAF moneyline fit 35 (fs2), each with
  its set's holdout scores. `srs_diff` and `cfb_srs_diff` are active again
  (dated). **The hold is lifted** (`HELD_MARKETS` empty; the strip shows no
  held line). No forecast for those markets yet: the first pass that writes
  them is Final-NFL / Final-CFB at 15:00Z (08:00 local), which answers the
  whole of NFL week 3 including Sunday. Confirm on the day strip after it.
- **Earlier today:** 55 restated closes (item 1); 31 forecast voids and
  recommendations 62, 63, 64 and 66 withdrawn (65 stands; the 31
  reasoning-forecaster rows stand).
- **The overnight queue** (docs/briefs/2026-09-24-overnight.md; the operator
  reordered it because the hold blocks football forecasts before Sunday):
  1. ~~Activation gate~~ -- released ff7e5ab.
  2. ~~Revert~~ -- released 4c3bda4; the day-strip confirmation waits for the
     15:00Z pass.
  3. ~~Weather~~ -- released fddd61b.
  4. The reasoning-pass prompt record -- BLOCKED on question 4.
  5. **Schema rulings** (in progress; below, in the order the brief gives).
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
3. **The active NFL fits count domes among their weather rows (ruling 4,
   2026-09-24).** Fits 88 (spread), 90 (total), 12, 13 and 14 (the yardage
   props), 56 (passing touchdowns) and 57 (receptions) were trained while an
   indoor game read wind, cold and rain 0.0, and each stores those domes
   among the rows that carried the weather: fit 88 counts wind and cold on
   2,463 of 2,632 rows, 760 of them domes, and precipitation on 760, every
   one a dome. Refit without the fill, every coefficient, 2025 probability,
   log loss and Brier is bit-for-bit the same (measured; FOLLOWUPS, "Weather:
   an indoor game carries no value"), so a refit ties its incumbent, the tie
   rule keeps the incumbent, and no activation kind admits it; none was
   trained or activated. The Factors page prints the stored counts with
   "indoor games among them". Is that enough, or should the counts be
   restated -- an identical refit activated under a ruling that says so, or
   a dated measured count shown beside the stored one? Default until ruled:
   the stored counts, with the words.
4. **RULED 2026-09-25 (docs/briefs/2026-09-25-question-4.md): the rule binds
   from the release that ships it, and the gap before it is labelled, not
   exempted** -- every earlier reasoning row gets a `reconstructed` record,
   every later one a `sent` record, and the gate fails on either missing.
   Item 4 goes next, after 5a, ahead of the live migration and 5b. The
   question as asked, kept: **From when does the prompt record bind? (Two
   additions, item 1; asked 2026-09-25.)** The ruling says "No reasoning row may exist without it", and
   the operator's message arrived at 2026-09-24T08:04:32Z. No code that keeps a
   prompt has been released, and the scheduler has kept running the reasoning
   pass without one. When the API came back, `predict:mlb` wrote 34 reasoning
   rows between 03:30:13Z and 03:33:07Z on 25 September: ids 2358-2441, 17 MLB
   moneyline and 17 MLB total, early pass, one successful call each (llm_calls
   502-535). None of their prompts was kept. A rebuild would not be the prompt
   that was sent, and LAW 3 forbids editing the rows. Every pass until the
   release adds more; a day's pass is 40 to 70 rows. The 433 rows written
   before the ruling are historic under either reading. (Read through the
   read-only door at 03:37Z on 25 September.)
   - **(A) The rule binds from the ruling, 2026-09-24T08:04:32Z.** This is how
     the activation gate binds: from its birthday, which came before its
     release. The 34 rows, and any written before the release, are then in
     breach. The gate fails and names each one. A future rebuild of
     `predictions` (for a new sport or market type) would refuse to copy them
     back. Both stay that way until you say what happens to the rows: void
     them, as with the earlier voids, or exempt them by a dated list of ids.
   - **(B) The rule binds from the release of the code that keeps the
     prompt.** Every reasoning row before that instant, the 34 included, is
     historic and exempt by date, and the close-out counts them. The instant
     is either a literal confirmed through the read-only door just before the
     fast-forward, or the moment `db.init` first opens the record under the
     new schema, which leaves no gap. The gate passes. But "no reasoning row
     may exist without it" then lets through rows written after the ruling by
     code that could not keep a prompt.

   From the release on, under either reading, the database refuses a
   reasoning row without its prompt. Nothing has been built; the prompt
   record waits for this answer. Until it is ruled, each scheduled pass adds
   to the count. Stopping the pass means unsetting the key in `.env`, which
   is an operator step.
5. **How far does "No test in the gate may depend on elapsed real time"
   reach? (Schema ruling 5, second sentence; asked 2026-09-25.)** The first
   sentence is built: auth reads one clock, the backoff and handoff tests move
   it by hand, and a scan refuses a sleep, a clock reading or a real-time
   comparison in `tests/`. The browser tier holds 44 fixed waits in 9 files:
   43 `page.wait_for_timeout(N)` after an action, before an assertion, and
   one `time.sleep(1.2)` inside a route handler that makes a response late
   (`test_rapid.py`). Each can pass without testing anything, or go red, on a
   slow machine. The app signals no "render finished" event the tests could
   wait for instead.
   - **(A) Literal: they depend on elapsed real time and must go.** Each is
     rebuilt on an event (a signal the app would add when a render lands, or
     a response the test holds and releases) or on Playwright's `page.clock`,
     and the held register empties. Upper-limit timeouts (server start 20 s,
     Playwright `timeout=`) stay: they turn a hang into a failure and change
     no result below the limit. Nine test files, and likely `app.js` for the
     render signal: its own step, with renders.
   - **(B) Narrow: the ruling means a test whose assertion compares a
     measured duration with a limit in the code under test** -- the two
     backoff tests and the handoff's minute, all now on the manual clock. The
     fixed waits stay, listed.
   Default until ruled: the 44 are held by function and count in
   `audit.ELAPSED_TIME_HELD`; none was changed, none may be added, and the
   register can only shrink. FOLLOWUPS, "HELD: the browser tier's fixed
   waits".
6. **A companion no-update trigger on `market_snapshots`? (Schema ruling 4;
   asked 2026-09-25.)** The 8 missing ids (174-181) were DELETED by hand at
   2026-09-01T00:08:32Z through a writable `db.connect()` -- a LAW 3
   violation, now refused by `market_snapshots_no_delete` with a planting.
   A snapshot row can still be rewritten in place with no trace (line,
   implied_prob, fetched_utc, source, kind). Freezing it goes beyond ruling
   4's words, so it was not built; FOLLOWUPS has it.

7. **"Written before the release": the row's own date, or when it was
   committed? (Question-4 ruling; asked 2026-09-25.)** The reconstruction
   tool and the trigger that admits a `reconstructed` record decide "before
   the release" from the row's own `created_utc`, which its writer chooses.
   A reasoning row inserted after the release with an earlier date would be
   rebuilt and labelled reconstructed. Refusing it would also refuse a
   lawful old-code row that took its date just before the first open under
   the new schema and committed just after, which could never carry a sent
   record and would fail every gate. Built meanwhile: the tool names such a
   row ("REBUILT, BUT COMMITTED AFTER THE RELEASE INSTANT", with its
   fingerprint time) and exits 1, so it cannot pass silently. FOLLOWUPS,
   OPEN.
8. **Which page is "the Record page"? (Question-4 ruling; asked
   2026-09-25.)** The Record tab shows aggregates only; the per-forecast
   record is Results. Built meanwhile, as the conservative default: both,
   with one component -- a panel on the Record tab (reasoning pass picked)
   listing the newest twenty with their prompts, and the prompt under each
   reasoning row in Results.

## Rulings taken in your absence (2026-09-25, schema rulings 5a)

- **Ruling 4, "find the code path that did it and fix it":** no repository
  code deleted the 8 snapshots; it was an ad hoc statement. Read as: the
  table itself refuses the delete (a BEFORE DELETE trigger), with a planting
  that runs the same statement. Conservative default: it would have stopped
  the 00:08:32Z statement.
- **Ruling 4, "a rolled-back insert (a normal AUTOINCREMENT gap)":**
  measured on SQLite 3.49.1 with the live triggers, a rolled-back or
  trigger-aborted insert leaves NO gap; only OR IGNORE, DO NOTHING,
  REPLACE, explicit ids or a DELETE do. Recorded in FOLLOWUPS; today's
  classification rests on direct evidence either way.
- **The register's ninth entry:** `market_lines_raw.spread_sign_source` is on
  the record and not in the released schema.sql until ruling 3's
  declaration ships; the release comparison registers it and it must be
  removed at the next commit after 5a merges ("CLEARED, STILL REGISTERED"
  fails the gate otherwise).
- **Ruling 5, second sentence:** question 5; both readings require the auth
  clock and its guard, which are built; the browser waits are held.

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
