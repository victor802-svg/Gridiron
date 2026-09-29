# Close-out — THE RE-READ (2026-09-29)

Against the operator's ruling on the close-out of 27 September
(`docs/briefs/2026-09-27-close-out-rulings.md`): "The re-read: local,
read-only against a verified copy of the record, not before the weekly reset
(28 Sep 15:00Z). Scope: confirm on the record that each of repair items 1–8
took effect; restate every gate distance per forecaster and distinct bet.
Three measurers, not seven. The edge question is already answered and is not
re-measured."

**A read, and it wrote nothing.** Nothing was written to the record, to git,
or to the worktree except this file.

* **The record read** is one verified copy of the live record,
  `scratchpad\reread\record.db`, made at about 19:10Z on 29 September by
  `rebuild.verified_backup`: integrity ok, and every table's count and column
  checksums equal to the record at that instant. That verification was the
  orchestrator's, when it made the copy; this re-read never opened the live
  record, so it could not check it again. Every read of the copy went through
  `gridiron.db.read_only` (mode=ro, query_only). SQLite's own quick check on
  the copy: ok. The copy's newest task row started 19:10:31Z, so it is the
  record "at about 19:10Z". It holds 3,152 forecasts, 111 recommendations
  (106 closed), 1,728 at-the-line claims, 34,164 venue quotes and 7,482 task
  runs.
* **After the reset.** The copy was made 28 hours after 28 Sep 15:00Z.
* **The code** is the released tree, master `cb8c7da` (serving from 19:09Z on
  29 September), read from the worktree at `3856a6e`, which is `cb8c7da` plus
  one commit of documents. Python from the gridiron venv.
* **The clock** was held at 2026-09-29T19:10:00Z: through each function's own
  `now` where it takes one, and in the process for everything else. So every
  figure below is the record as of the copy.
* **Three measurers.** One read repair items 1-4, one items 5-8, and one every
  gate distance on the Record page. This report is the compiler's: it checked
  the three against each other, spot-checked 16, 16 and 59 of their figures on
  the copy with its own scripts, and re-measured each point where they
  disagreed or a verdict did not follow from its evidence (section 4).
* **Not done:** no pytest, `tools/verify.py` or `plant.py`; no network; no
  language-model call; `.env` not read; the main checkout, the live record and
  the app on 8848 not touched. Two things outside the record were read, both
  read-only: the Windows System log (`tools/awake.py`) and the scheduled
  tasks' settings (`Get-ScheduledTask`).
* **Scripts and outputs:** `scratchpad\reread\measurer_items_1_4\`,
  `measurer_items_5_8\`, `gates\` and `compiler\`.

"Since the fix" means each item's fast-forward onto master, read from master's
reflog: item 1 at 2026-09-24T06:49:12Z, item 2 at 2026-09-26T04:48:16Z, item 3
at 06:34:00Z, item 4 at 08:23:44Z, item 5 at 10:48:05Z and item 6 at 21:33:40Z
that day, item 7 at 2026-09-27T00:05:55Z and item 8 at 02:36:33Z. The
scheduler runs the main checkout, so that is when each item's code began to
run.

| part of the ruling | verdict | evidence (the copy, clock held; each N and how it was got is in section 1) |
|---|---|---|
| **Item 1. The close** | **PARTLY** | The close rule holds on every close: 106 of 106 closes have one account, and `recommend.close_of` gives each again; the repaired closer wrote 51 (39 measured on a later read of the recommendation's own contract, 12 unmeasured and empty, never 0.00c); 0 of 106 cite the read they were priced from; the 55 old closes are restated beside the count and are in no N. But "every run inside its window until the game starts" did not hold for baseball: 14 of the 19 measured MLB closes are the read 35 minutes out, because the firing 5 minutes before each game's listed start left it out |
| **Item 2. fs5, and no silent skip** | **TOOK EFFECT** for the revert; the failure by name **CANNOT BE SEEN YET** | The four reverted fits (88, 71, 44, 35) are the active ones, and 155 of 155 statistical NFL and NCAAF spread and moneyline forecasts written since 24 Sep 13:00:01Z came from their market's active fit. No run since the fix has met an untrained market: no activation has changed since that instant, the door names no market in any sport, and 0 runs have ever failed `MarketNotTrained` |
| **Item 3. Corrections reach recommendations** | **CANNOT BE SEEN YET** | No correction was in force at any recommendation's stamp: 111 of 111 carry the empty pair. The one correction ever in force (fit 71, MLB moneyline, statistical, 28 Sep 13:00:01Z to its withdrawal at 29 Sep 09:12:46Z) is in a market never priced, and no recommendation was written after 27 Sep 16:00:46Z |
| **Item 4. The cost of the side** | **TOOK EFFECT** | 10 of 10 recommendations since the fix clear the 5% bar on their own side's cost (the lowest 8.38%, rec 102). Over all 111, exactly recs 3, 10, 26 and 56 pass on the yes price and fail on their own cost, and each carries a true "would not have cleared" label. The other half, a real no-side edge above a 50c yes price now clearing, has not happened yet |
| **Item 5. One per game and market** | **TOOK EFFECT** | 0 of the 10 recommendations since the fix met a standing one on its game and market; 0 games with both sides since; 2 repeats refused by name in the runs' payloads; the 18 older pairs (36 rows) untouched |
| **Item 6. At the line, one bet per forecaster** | **TOOK EFFECT** | 30 of 30 at-the-line curves count one claim per distinct bet of one forecaster, equal to `gridiron.recount` and to two recounts made without any door; 12 cells recounted again by the compiler, 12 of 12 equal |
| **Item 7. The jobs** | **TOOK EFFECT** for the refusal, the sweep and the setting; the guarded closing write and a timer wake **CANNOT BE SEEN YET** | Since the fix: 2,878 runs, 0 failed (the record holds 90 `SlateAlreadyAnswered` failures before it), and 8 refused reruns recorded as a noop; 9 hung rows marked abandoned, run 4821 among them at 36.0 hours; WakeToRun on 18 of 18 tasks. 0 rows have ever needed the closing-write guard, and no timer has woken the machine. **Awake 66.46 of 67.07 hours since the fix, 99.1%** |
| **Item 8. The closing line's window** | **TOOK EFFECT** | From 24 September, 5 of 21 days, first clean read 15 October; in all five sports no closing-line entry has a mean, a share or a finding, and the kill criterion stops nothing; both BROKEN findings are in READINESS, dated |
| Every gate distance, per forecaster and distinct bet | **DONE** | 354 figures across 19 records in five sports; the 343 that are counts each equal a recount made without any door (0 differ); READINESS criterion 2 added per forecaster (section 2) |
| Three measurers, not seven | **DONE** | items 1-4, items 5-8, the gates; checked by the compiler (section 4) |
| The edge question is not re-measured | **DONE** | no curve's score, mean, share, direction or edge figure was read or stated. A gate past says only that enough questions have settled |
| Local, read-only, a verified copy, after the reset | **DONE** | the copy of about 19:10Z on 29 September, through `db.read_only`; `git status` shows only this new file, and no bytecode was written in the worktree |

---

## 1. The eight items on the record

### Item 1 — the close: PARTLY

Built as 23cf89b, on master at 2026-09-24T06:49:12Z.

* **Every close has its account.** 111 recommendations: 106 closed, each with
  exactly one row in `recommendation_closes`; 5 open, none with one (62, 63,
  64 and 66, withdrawn and never followed to a close; 111, whose game starts
  2026-10-02T01:00Z). SQL on the copy.
* **The repaired closer wrote 51 closes** (`restated` = 0), from 24 Sep
  16:35:02Z to 29 Sep 00:35:01Z. **39 are measured** on a later near-start read
  of the recommendation's own contract. **12 are unmeasured**, their close and
  value both empty, never 0.00c: recs 56-61, 67 and 79-83. By market and
  forecaster, measured / unmeasured: MLB spread, statistical 18 / 10; NFL
  spread, statistical 11 / 1; NCAAF spread, statistical 8 / 0; MLB total,
  reasoning pass 1 / 0; NFL total, reasoning pass 1 / 0; MLB total,
  statistical 0 / 1.
* **Never the price against itself.** 0 of 106 closes cite the read they were
  priced from (quote ids). `recommend.close_of`, run again on the copy for all
  106, gives the same pricing read, closing read, price and value as every
  written row (the items 1-4 measurer; not run again here). 11 of the 39
  measured closes show the price paid (71, 75, 88, 90, 92, 93, 94, 95, 99, 102,
  105): each is a later, different read of its own contract that did not move,
  not the old defect.
* **The 55 old closes are restated beside the count** (`restated` = 1, recs
  1-55, written 24 Sep 06:49:48Z). Each recommendation's own columns still read
  close = price at 0.00c, as the old closer wrote them (LAW 3). 31 had a later
  read of their own contract and 24 had none; per forecaster, with / without:
  MLB spread, statistical 23 / 18; MLB total, reasoning pass 8 / 5; MLB total,
  statistical 0 / 1 (rec 45). None is in any N.
* **Where "every run until the game starts" held, and where it did not.**
  Read from each measured close's read against the near-start firings between
  it and the listed start (`task_runs` payloads,
  `compiler\c02_item1_lastfiring.py`):
  * **NFL: 12 of 12** measured closes are the last firing before the start.
  * **NCAAF: 7 of 8.** For rec 103 the firing 25 minutes out asked for its
    contract and the venue returned no quote of it.
  * **MLB: 5 of 19.** Nine firings between 25 and 27 September asked for fewer
    recommendations than were open in their window (runs 3504, 3525, 3568,
    3633, 4431, 4561, 4625, 4669, 5405). The 14 left out were all baseball
    games within 5 minutes of their listed start, and each closed on the read
    about 35 minutes out instead (13 at 35 minutes, 1 at 34).
  * **Why.** The pass keeps a recommendation only while it is open, not
    withdrawn, its kickoff inside the next two hours and its game's status
    'scheduled' or 'pre' (`tasks._near_start_snapshots`). Each of the 14 was
    open, not withdrawn and, by its kickoff as stored now, inside the window,
    so the likeliest cause is the status: the game marked under way before its
    listed start. The record keeps no history of a game's status or kickoff,
    so this is inferred, not seen: the live poller maps MLB's "Live" state to
    under way (`live.MLB_STATES`), and the inference is that MLB's feed calls a
    game in its warm-up "Live".
* **The first day read nothing.** On 24 September, 17 of 17 near-start firings
  that asked the venue (14:35Z to 23:05Z) got 0 prices back, each recorded
  'ok'. Those are 10 of the 12 unmeasured closes (56-61, 79-82); 67 and 83
  started while the machine was switched off. The first firing with prices
  back was run 3374, 25 Sep 19:35:01Z.
* **The closing line, per forecaster:** section 2, tables O and P.

### Item 2 — fs5, and no silent skip: TOOK EFFECT for the revert; the failure by name CANNOT BE SEEN YET

The ruling has two halves. The items 1-4 measurer read the second; the
compiler measured the first (`compiler\c08_item2_revert.py`).

* **The revert (4c3bda4).** Activation rows 25-28, all at 2026-09-24T13:00:01Z,
  kind 'incumbent': fit 88 (NFL spread, fs3), 71 (NFL moneyline, fs2), 44
  (NCAAF spread, fs3), 35 (NCAAF moneyline, fs2). `activation.active_fit` gives
  the same four on the copy, and `audit.hold_lift_faults` finds none.
* **Those markets are forecast again.** Before the revert the last NFL spread
  and moneyline forecasts were written 2026-09-04T18:40:24Z and the last NCAAF
  ones 2026-09-05T15:00:57Z. Since the activations (the first at 24 Sep
  15:00:02Z): NFL spread 13 and moneyline 16 from the model, 12 and 15 from
  the reasoning pass; NCAAF spread 62 and moneyline 64 from the model, 61 and
  63 from the reasoning pass. **155 of 155** of the model's were written by
  their market's active fit (`baseline.is_its_forecast`: the fit, applied to
  the row's own stored factors and rung, gives back its probability). The 31
  statistical forecasts fits 91-94 published at 05:32-05:37Z on 24 September
  are all withdrawn.
* **No silent skip (d7b4dfa).** 0 task rows have ever failed with
  `MarketNotTrained`. `baseline.untrained_markets` names no market in any of
  the five sports; the day strip's untrained list is empty and
  `tasks.failed_for_want_of_a_model` is false for all five (the measurer). No
  activation has changed since 24 Sep 13:00:01Z, and nothing between d7b4dfa
  and cb8c7da changed a held, active, retired or factor-set declaration (the
  measurer, `git diff`). So no run since the fix could have failed by name:
  the path has never been triggered on the record. Every 'ok' predict and
  final run since wrote every game market its sport asks (the measurer), and
  0 forecasts since the fix were written at or after their game's start, with
  every stamp read to the second (`compiler\c04_starts.py`).

### Item 3 — corrections reach recommendations: CANNOT BE SEEN YET

Built as 36e863f (26 Sep 06:34:00Z); from Q32 (c5dbd3b, 29 Sep 09:12:23Z) a
correction is in force only by its own activation row.

* 111 of 111 recommendations carry `correction_version` and
  `calibrated_fair_value` both empty; 0 have one without the other.
* 10 were written after the fix (102-111). For each, nothing was in force at
  its own stamp, by the released door and by the old `active_from` rule (the
  measurer; the compiler checked the old rule's one row: fit 71 from 28 Sep
  13:00:01Z, and the newest recommendation is 27 Sep 16:00:46Z).
* `correction_activations` holds one row: fit 71 withdrawn at 29 Sep 09:12:46Z,
  reason "activated under the pre-Q32 rule: single holdout comparison, pooled
  rows". The door serves nothing in any of the 26 fitted categories (the
  measurer).
* Nothing was re-derived: on 111 of 111 the stored number is the raw claim's
  (the measurer).
* **Not seen:** a correction reaching a pick. It needs a correction to pass the
  Q32 gate in a market that is priced, and a pick written while it stands.

### Item 4 — the cost of the side: TOOK EFFECT

Built as 3c43509 (26 Sep 08:23:44Z); the labels written after Q9 (27 Sep
07:04:41Z) and Q13.

* **10 of 10** recommendations since the fix (102-111) clear the 5% bar on what
  their side cost, re-worked from each frozen row with
  `recommend.clears_the_bar(side=...)`; the lowest is 8.38%, rec 102.
* **Exactly four let through by the old divisor.**
  `recommend.let_through_by_the_yes_price` selects recs 3, 10, 26 and 56 on the
  copy, and each is already labelled. The labels (27 Sep 07:04:51Z, verdict
  "would not have cleared", bar 0.05) match the arithmetic of their frozen
  rows: the no side cost 62.5c, 62.5c, 60.5c and 61c; returns on that cost
  3.34%, 3.68%, 4.69% and 4.97%; on the yes price 5.57%, 6.13%, 7.19% and
  7.77%.
* **Counted once.** The Record page counts 3 and 56 ("Would not have cleared,
  statistical: 2"): 10 and 26 are the later rows of the pairs 3/10 and 21/26
  (the measurer).
* **Not seen:** a real no-side edge above a 50c yes price reaching a pick. 5
  claims since the fix cleared only on their own cost; none was recommended (3
  NCAAF moneyline claims refused by coverage, 2 off the shortlist; the
  measurer).

### Item 5 — one per game and market: TOOK EFFECT

Built as 9014add (26 Sep 10:48:05Z).

* 10 recommendations since the fix (102-111). At its own write time, 0 found a
  standing recommendation on its game and market; 0 games hold both sides
  since. The 18 game-markets written before the rule still hold two standing
  rows each (36 rows, the newest 25 Sep 21:33:01Z), and 45/46 is the only
  both-sides pair on the record. SQL on the copy.
* 17 predict and final runs since the fix carry the payload's recommendation
  block. Summed: 10 recommended (the 10 rows), 0 already, 2 refused as a second
  on its game and market, 0 both sides, 119 with no side, 0 in the game. The two
  refusals, each named in the ruling's words: forecast 2977 (run 4492, final
  MLB) behind rec 98, and forecast 3147 (run 6261, final NCAAF) behind rec 111,
  each a final pass repeating the morning's pick.
* **Not seen:** a both-sides refusal live (0); it is proved only by the gate's
  planting.

### Item 6 — at the line, one bet per forecaster: TOOK EFFECT

Built as 6cb20eb (26 Sep 21:33:40Z); the key widened to the rung by Q17, the
pass order set by Q27.

* `calibration.at_the_line_scorecard` built for all five sports: 30 curves
  (market, card and forecaster), its guards run without refusing. In every one
  the curve's n equals its distinct bets and `gridiron.recount`, and both the
  items 5-8 and the gate measurers recounted all 30 without any door: 30 of 30
  equal. No curve holds two forecasters. The 63 count sentences beside pick
  cards each equal their own forecaster's curve (the measurer).
* The compiler recounted six cells again from the claims table, with the same
  standing rule written out by hand: MLB spread statistical 102, MLB moneyline
  statistical 107 and reasoning pass 108, NCAAF spread statistical 45, NFL
  spread statistical 14, NCAAF moneyline reasoning pass 46, and their ledgers
  67, 56, 75, 38, 13 and 33. 12 of 12 equal.
* Three curves are now past their 100: MLB spread statistical 102, MLB
  moneyline statistical 107 and reasoning pass 108. On 26 September none was.
* **Not seen:** two settled rungs of one game (every at-the-line market holds
  one settled bet per game so far).

### Item 7 — the jobs: TOOK EFFECT for the refusal, the sweep and the setting; the guarded closing write and a timer wake CANNOT BE SEEN YET

Built as 0c6da10 (27 Sep 00:05:55Z). SQL on `task_runs` unless named.

* **A refused rerun is a noop.** Since the fix: 2,878 runs, ok 778, noop
  2,093, missed 6, abandoned 1, **failed 0**. In the 26 September window before
  it: 1,041 runs, ok 897, noop 141, missed 1, failed 2. The record holds 90
  `SlateAlreadyAnswered` failures, the last run 4341 at 26 Sep 18:00:01Z. 8
  refused reruns since are recorded noop in the new words (runs 4826 to 7429:
  NCAAF 3, UFC 3, NFL 1, MLB 1). The catch-up has succeeded once ever, run 4812
  at 27 Sep 05:35:23Z (18 failed, 4 still running).
* **The closing write inside the try: CANNOT BE SEEN YET.** 0 of 7,482 rows
  carry a `closing_write` entry: the guard has never had to act.
* **A hung run is marked abandoned.** 9 rows: 7 at 27 Sep 00:06:03Z (final NCAAF
  969, 1742, 1847, 2057; refresh 1983, 1986, 1989), 3358 at 27 Sep 07:25:31Z, and
  **4821** (predict MLB, begun 27 Sep 05:44:37Z) at 28 Sep 17:45:01Z, 36.0 hours
  on, its task's own silence. Each keeps an empty ending. 5 rows still run, none
  past its own silence (catch-up 1978, 1982, 1985 and 1988; predict NFL 1981).
* **WakeToRun: set; a wake CANNOT BE SEEN YET.** `Get-ScheduledTask
  'Gridiron-*'`, read again by the compiler: 18 of 18 tasks have WakeToRun and
  StartWhenAvailable. Wake timers are enabled (the measurer, `powercfg /q`).
  Since the fix the machine has not slept, so no timer has woken it.
* **The awake fraction since the fix** (`tools/awake.py --since
  2026-09-27T00:05:55Z --until 2026-09-29T19:10:00Z`, the System log only, run
  again by the compiler): **awake 66.46 of 67.07 hours, 99.1%.** One stretch
  not awake: 27 Sep 04:58Z to 05:34Z, 0.61 hours, powered off from the power
  button or the sign-in screen. Asleep 0.00 hours; woken by a timer 0 times.

### Item 8 — the closing line's window: TOOK EFFECT

Built as f02e913 (27 Sep 02:36:33Z).

* `calibration.closing_line_window` at the copy's instant: from 2026-09-24, 5 of
  21 days, not open, first clean read 2026-10-15 (16 days).
* `calibration.clv_report` for all five sports, clock held: every market line is
  unrenderable, its mean and its share that beat the close empty, with no
  finding; every forecaster block counts 0 closes before the window.
  `priced.coverage.stopped` is empty in all five sports. The 26 page payloads,
  built with the clock held, carry no closing-line value anywhere (the
  measurer).
* `docs/READINESS.md` records both BROKEN findings, dated and repaired
  (section 5, "Open BROKEN findings", from line 564), and the window table
  (from line 494). A document check; nothing on the record to measure it by.

---

## 2. Every gate distance, per forecaster and distinct bet

**How every figure below was got.** The gate measurer built the two payloads
the Record page reads, `views.scorecard(conn, sport)` and
`views.learning(conn, sport)`, for all five sports on the copy with the clock
held (`gates\payloads\`), and recounted every count itself
(`gates\recount_mine.py`): every table read whole with plain SELECTs, no door,
no standing clause, no window, and each rule written again in Python. A
distinct bet is `bet.KEY` (the forecaster, the game, the market, the subject,
the rung asked). The blind standing row follows Q27: among a bet's rows
written before the start and withdrawn by no void, a final pass written before
the start stands first, then the latest written. The at-the-line standing
claim is chosen the same way among claims written before the start.

**Result: 354 rows; 343 are counts, and the page's figure and the recount
agree on all 343 (0 differ).** The other 11 (five "closest to a verdict"
lines, five combos lines, one dated window) are not counts of bets. The
compiler then re-measured 59 of the rows on the copy with its own scripts
(`compiler\c05_ufc.py`, `c06_gates.py`, `c09_item8.py`): 23 by a recount of
its own without any door (11 blind curves, 6 at-the-line curves, 6 ledgers)
and 36 through the released functions (3 media drift counts, 3 correction
counts, 2 ranker rows, 1 edge count, 2 priced counts, 4 UFC tier bands, 16
closing-line lines, 5 window lines). 59 of 59 equal. N in every table is
the count of distinct bets, one forecaster's. "UFC ... every card together"
marks a count the code makes across the three cards (finding G2). Where a
cell says "mine", it is the gate measurer's own recount; "page ~N" is the
outlook's own extrapolation, not a count.

**Gates now past. A gate past says only that enough questions have settled.
It says nothing about edge, which is not re-measured.**

* Blind curves, 100: MLB moneyline 260 (statistical) and 148 (reasoning pass),
  MLB spread 202, MLB total 213 and 141, NCAAF spread 185, moneyline 142 and
  total 144 (statistical).
* Tier table: the edge figure's 100 in MLB moneyline 50-60% (237); a verdict's
  20 in NFL spread 50-60% (29), MLB moneyline 60-70% (23), all four NCAAF spread
  bands (65, 32, 43, 45), and UFC moneyline 50-60% (28, the three cards
  together; Fight Night alone 22).
* At the venue's line, 100: MLB spread statistical 102, MLB moneyline 107
  (statistical) and 108 (reasoning pass).
* The priced forecaster, 100: MLB moneyline statistical 105.
* Where the line went, 50: the media line in MLB moneyline 52, NCAAF spread 78
  and NCAAF total 54; the venue's own pair (not painted) in MLB moneyline
  reasoning pass 57 and MLB spread statistical 56.
* Correction gates, 50: 13 categories, none in force.
* MLB's dated rung-distribution window: 14 of 14 days.
* **Not past:** every closing line (the nearest, MLB spread statistical, 15 of
  50) and the kill criterion; every edge-figure count (the nearest, NCAAF
  spread, 98 of 100); every hypothetical ledger (the nearest, MLB moneyline
  reasoning pass, 75 of 100); no ranker comparison on both sides; no taken
  comparison (taken is 0 everywhere).

#### A. The blind record: each curve and its outlook (LAW 4's 100 settled)

How got: `views.scorecard` (the curves and `horizon.market_outlook`). N is the forecaster's settled standing questions, one per distinct bet, Q27's standing rule. The reasoning pass's curve in a market it is still asked carries its N and no outlook, by design. 70 rows.

| sport | market | forecaster | N | gate | distance | what the page says | notes | flag |
|---|---|---|---|---|---|---|---|---|
| NFL | spread | statistical | 42 | 100 | 58 more | 42 of 100 · ~357 expected · season ends 01-10 | page ~357 (315 more, 15 slates to come) |  |
| NFL | spread | reasoning pass | 13 | 100 | 87 more | 13 resolved; no outlook line (the reasoning pass is still asked) |  |  |
| NFL | moneyline | statistical | 32 | 100 | 68 more | 32 of 100 · ~272 expected · season ends 01-10 | page ~272 (240 more, 15 slates to come) |  |
| NFL | moneyline | reasoning pass | 16 | 100 | 84 more | 16 resolved; no outlook line (the reasoning pass is still asked) |  |  |
| NFL | total | statistical | 18 | 100 | 82 more | 18 of 100 · ~153 expected · season ends 01-10 | page ~153 (135 more, 15 slates to come) |  |
| NFL | total | reasoning pass | 17 | 100 | 83 more | 17 resolved; no outlook line (the reasoning pass is still asked) |  |  |
| NFL | prop: passing_yards | statistical | 10 | 100 | 90 more | 10 of 100 · ~85 expected · season ends 01-10 · THIS GATE CANNOT CLEAR THIS SEASON | page ~85 (75 more, 15 slates to come) |  |
| NFL | prop: passing_yards | reasoning pass | 0 | 100 | 100 more | 0 of 100 · reasoning pass stopped asking 6 Sep; 0 settled is the final count |  |  |
| NFL | prop: receiving_yards | statistical | 10 | 100 | 90 more | 10 of 100 · ~85 expected · season ends 01-10 · THIS GATE CANNOT CLEAR THIS SEASON | page ~85 (75 more, 15 slates to come) |  |
| NFL | prop: receiving_yards | reasoning pass | 0 | 100 | 100 more | 0 of 100 · reasoning pass stopped asking 6 Sep; 0 settled is the final count |  |  |
| NFL | prop: rushing_yards | statistical | 9 | 100 | 91 more | 9 of 100 · ~76 expected · season ends 01-10 · THIS GATE CANNOT CLEAR THIS SEASON | page ~76 (67 more, 15 slates to come) |  |
| NFL | prop: rushing_yards | reasoning pass | 0 | 100 | 100 more | 0 of 100 · reasoning pass stopped asking 6 Sep; 0 settled is the final count |  |  |
| NFL | prop: receptions | statistical | 9 | 100 | 91 more | 9 of 100 · ~76 expected · season ends 01-10 · THIS GATE CANNOT CLEAR THIS SEASON | page ~76 (67 more, 15 slates to come) |  |
| NFL | prop: receptions | reasoning pass | 0 | 100 | 100 more | 0 of 100 · reasoning pass stopped asking 6 Sep; 0 settled is the final count |  |  |
| NFL | prop: passing_tds | statistical | 8 | 100 | 92 more | 8 of 100 · ~68 expected · season ends 01-10 · THIS GATE CANNOT CLEAR THIS SEASON | page ~68 (60 more, 15 slates to come) |  |
| NFL | prop: passing_tds | reasoning pass | 0 | 100 | 100 more | 0 of 100 · reasoning pass stopped asking 6 Sep; 0 settled is the final count |  |  |
| MLB | moneyline | statistical | 260 | 100 | PAST IT | 260 of 100 · ~272 expected · season ends 09-27 | page ~272 (past already); season over save one stale game: ~260 |  |
| MLB | moneyline | reasoning pass | 148 | 100 | PAST IT | 148 resolved; no outlook line (the reasoning pass is still asked) |  |  |
| MLB | spread | statistical | 202 | 100 | PAST IT | 202 of 100 · ~214 expected · season ends 09-27 | page ~214 (past already); season over save one stale game: ~202 |  |
| MLB | spread | reasoning pass | 0 | 100 | 100 more | 0 resolved; no outlook line (the reasoning pass is still asked) |  |  |
| MLB | total | statistical | 213 | 100 | PAST IT | 213 of 100 · ~226 expected · season ends 09-27 | page ~226 (past already); season over save one stale game: ~213 |  |
| MLB | total | reasoning pass | 141 | 100 | PAST IT | 141 resolved; no outlook line (the reasoning pass is still asked) |  |  |
| MLB | prop: batter_hits | statistical | 31 | 100 | 69 more | 31 of 100 · ~33 expected · season ends 09-27 · THIS GATE CANNOT CLEAR THIS SEASON | page ~33 (2 more, 1 slates to come); on slates still ahead only (0): ~31 |  |
| MLB | prop: batter_hits | reasoning pass | 2 | 100 | 98 more | 2 of 100 · reasoning pass stopped asking 6 Sep; 2 settled is the final count |  |  |
| MLB | prop: batter_total_bases | statistical | 0 | 100 | 100 more | 0 of 100 · nothing written yet; no rate |  |  |
| MLB | prop: batter_total_bases | reasoning pass | 0 | 100 | 100 more | 0 of 100 · reasoning pass stopped asking 6 Sep; 0 settled is the final count |  |  |
| MLB | prop: batter_home_runs | statistical | 31 | 100 | 69 more | 31 of 100 · retired Saturday 5 September; nothing more will be written, so 31 settled is the final count |  |  |
| MLB | prop: batter_home_runs | reasoning pass | 6 | 100 | 94 more | 6 of 100 · reasoning pass stopped asking 6 Sep; 6 settled is the final count |  |  |
| MLB | prop: batter_strikeouts | statistical | 10 | 100 | 90 more | 10 of 100 · ~11 expected · season ends 09-27 · THIS GATE CANNOT CLEAR THIS SEASON | page ~11 (1 more, 1 slates to come); on slates still ahead only (0): ~10 |  |
| MLB | prop: batter_strikeouts | reasoning pass | 0 | 100 | 100 more | 0 of 100 · reasoning pass stopped asking 6 Sep; 0 settled is the final count |  |  |
| MLB | prop: pitcher_strikeouts | statistical | 8 | 100 | 92 more | 8 of 100 · ~10 expected · season ends 09-27 · THIS GATE CANNOT CLEAR THIS SEASON | page ~10 (2 more, 1 slates to come); on slates still ahead only (0): ~8 |  |
| MLB | prop: pitcher_strikeouts | reasoning pass | 0 | 100 | 100 more | 0 of 100 · reasoning pass stopped asking 6 Sep; 0 settled is the final count |  |  |
| NBA | moneyline | statistical | 0 | 100 | 100 more | 0 of 100 · nothing written yet; no rate |  |  |
| NBA | moneyline | reasoning pass | 0 | 100 | 100 more | 0 resolved; no outlook line (the reasoning pass is still asked) |  |  |
| NBA | spread | statistical | 0 | 100 | 100 more | 0 of 100 · nothing written yet; no rate |  |  |
| NBA | spread | reasoning pass | 0 | 100 | 100 more | 0 resolved; no outlook line (the reasoning pass is still asked) |  |  |
| NBA | total | statistical | 0 | 100 | 100 more | 0 of 100 · nothing written yet; no rate |  |  |
| NBA | total | reasoning pass | 0 | 100 | 100 more | 0 resolved; no outlook line (the reasoning pass is still asked) |  |  |
| NBA | prop: points | statistical | 0 | 100 | 100 more | 0 of 100 · nothing written yet; no rate |  |  |
| NBA | prop: points | reasoning pass | 0 | 100 | 100 more | 0 of 100 · reasoning pass stopped asking 6 Sep; 0 settled is the final count |  |  |
| NBA | prop: rebounds | statistical | 0 | 100 | 100 more | 0 of 100 · nothing written yet; no rate |  |  |
| NBA | prop: rebounds | reasoning pass | 0 | 100 | 100 more | 0 of 100 · reasoning pass stopped asking 6 Sep; 0 settled is the final count |  |  |
| NBA | prop: assists | statistical | 0 | 100 | 100 more | 0 of 100 · nothing written yet; no rate |  |  |
| NBA | prop: assists | reasoning pass | 0 | 100 | 100 more | 0 of 100 · reasoning pass stopped asking 6 Sep; 0 settled is the final count |  |  |
| NBA | prop: threes | statistical | 0 | 100 | 100 more | 0 of 100 · nothing written yet; no rate |  |  |
| NBA | prop: threes | reasoning pass | 0 | 100 | 100 more | 0 of 100 · reasoning pass stopped asking 6 Sep; 0 settled is the final count |  |  |
| NCAAF | spread | statistical | 185 | 100 | PAST IT | 185 of 100 · ~1334 expected · season ends 12-12 | page ~1334 (past already) |  |
| NCAAF | spread | reasoning pass | 58 | 100 | 42 more | 58 resolved; no outlook line (the reasoning pass is still asked) |  |  |
| NCAAF | moneyline | statistical | 142 | 100 | PAST IT | 142 of 100 · ~1027 expected · season ends 12-12 | page ~1027 (past already) |  |
| NCAAF | moneyline | reasoning pass | 60 | 100 | 40 more | 60 resolved; no outlook line (the reasoning pass is still asked) |  |  |
| NCAAF | total | statistical | 144 | 100 | PAST IT | 144 of 100 · ~715 expected · season ends 12-12 | page ~715 (past already) |  |
| NCAAF | total | reasoning pass | 67 | 100 | 33 more | 67 resolved; no outlook line (the reasoning pass is still asked) |  |  |
| UFC | moneyline, card: Numbered card | statistical | 0 | 100 | 100 more | 0 of 100 · nothing written yet; no rate |  |  |
| UFC | moneyline, card: Numbered card | reasoning pass | 0 | 100 | 100 more | 0 resolved; no outlook line (the reasoning pass is still asked) |  |  |
| UFC | moneyline, card: Fight Night | statistical | 39 | 100 | 61 more | 39 of 100 · ~121 expected · season ends 12-12 | page ~121 (82 more, 6 slates to come); on slates still ahead only (4): ~94 | **G1** |
| UFC | moneyline, card: Fight Night | reasoning pass | 39 | 100 | 61 more | 39 resolved; no outlook line (the reasoning pass is still asked) |  |  |
| UFC | moneyline, card: Contender Series | statistical | 10 | 100 | 90 more | 10 of 100 · ~25 expected · season ends 12-12 · THIS GATE CANNOT CLEAR THIS SEASON | page ~25 (15 more, 3 slates to come) |  |
| UFC | moneyline, card: Contender Series | reasoning pass | 10 | 100 | 90 more | 10 resolved; no outlook line (the reasoning pass is still asked) |  |  |
| UFC | rounds, card: Numbered card | statistical | 0 | 100 | 100 more | 0 of 100 · nothing written yet; no rate |  |  |
| UFC | rounds, card: Numbered card | reasoning pass | 0 | 100 | 100 more | 0 of 100 · reasoning pass stopped asking 6 Sep; 0 settled is the final count |  |  |
| UFC | rounds, card: Fight Night | statistical | 39 | 100 | 61 more | 39 of 100 · ~121 expected · season ends 12-12 | page ~121 (82 more, 6 slates to come); on slates still ahead only (4): ~94 | **G1** |
| UFC | rounds, card: Fight Night | reasoning pass | 14 | 100 | 86 more | 14 of 100 · reasoning pass stopped asking 6 Sep; 14 settled is the final count |  |  |
| UFC | rounds, card: Contender Series | statistical | 10 | 100 | 90 more | 10 of 100 · ~25 expected · season ends 12-12 · THIS GATE CANNOT CLEAR THIS SEASON | page ~25 (15 more, 3 slates to come) |  |
| UFC | rounds, card: Contender Series | reasoning pass | 0 | 100 | 100 more | 0 of 100 · reasoning pass stopped asking 6 Sep; 0 settled is the final count |  |  |
| UFC | distance, card: Numbered card | statistical | 0 | 100 | 100 more | 0 of 100 · nothing written yet; no rate |  |  |
| UFC | distance, card: Numbered card | reasoning pass | 0 | 100 | 100 more | 0 of 100 · reasoning pass stopped asking 6 Sep; 0 settled is the final count |  |  |
| UFC | distance, card: Fight Night | statistical | 39 | 100 | 61 more | 39 of 100 · ~121 expected · season ends 12-12 | page ~121 (82 more, 6 slates to come); on slates still ahead only (4): ~94 | **G1** |
| UFC | distance, card: Fight Night | reasoning pass | 14 | 100 | 86 more | 14 of 100 · reasoning pass stopped asking 6 Sep; 14 settled is the final count |  |  |
| UFC | distance, card: Contender Series | statistical | 10 | 100 | 90 more | 10 of 100 · ~25 expected · season ends 12-12 · THIS GATE CANNOT CLEAR THIS SEASON | page ~25 (15 more, 3 slates to come) |  |
| UFC | distance, card: Contender Series | reasoning pass | 0 | 100 | 100 more | 0 of 100 · reasoning pass stopped asking 6 Sep; 0 settled is the final count |  |  |

#### B. The tier table: each band of the headline market, the statistical model (a verdict at 20 settled, then the edge figure's 100)

How got: `calibration.tier_table` through `bucket_record`. 20 rows.

| sport | market | forecaster | N | gate | distance | what the page says | notes | flag |
|---|---|---|---|---|---|---|---|---|
| NFL | spread 50-60% | statistical | 29 | 100 | verdict gate (20) PAST; 71 more to the edge figure's 100 | 29 of 100 settled / verdict earned - 29 of 100 toward the edge figure |  |  |
| NFL | spread 60-70% | statistical | 11 | 20 | 9 more to a verdict (20) | 11 of 20 settled / 9 more settled |  |  |
| NFL | spread 70-80% | statistical | 2 | 20 | 18 more to a verdict (20) | 2 of 20 settled / 18 more settled |  |  |
| NFL | spread 80%+ | statistical | 0 | 20 | 20 more to a verdict (20) | 0 of 20 settled / 20 more settled |  |  |
| MLB | moneyline 50-60% | statistical | 237 | 100 | PAST IT (the verdict's 20 and the edge figure's 100) | 237 settled / past the edge figure |  |  |
| MLB | moneyline 60-70% | statistical | 23 | 100 | verdict gate (20) PAST; 77 more to the edge figure's 100 | 23 of 100 settled / verdict earned - 23 of 100 toward the edge figure |  |  |
| MLB | moneyline 70-80% | statistical | 0 | 20 | 20 more to a verdict (20) | 0 of 20 settled / 20 more settled |  |  |
| MLB | moneyline 80%+ | statistical | 0 | 20 | 20 more to a verdict (20) | 0 of 20 settled / 20 more settled |  |  |
| NBA | moneyline 50-60% | statistical | 0 | 20 | 20 more to a verdict (20) | 0 of 20 settled / 20 more settled |  |  |
| NBA | moneyline 60-70% | statistical | 0 | 20 | 20 more to a verdict (20) | 0 of 20 settled / 20 more settled |  |  |
| NBA | moneyline 70-80% | statistical | 0 | 20 | 20 more to a verdict (20) | 0 of 20 settled / 20 more settled |  |  |
| NBA | moneyline 80%+ | statistical | 0 | 20 | 20 more to a verdict (20) | 0 of 20 settled / 20 more settled |  |  |
| NCAAF | spread 50-60% | statistical | 65 | 100 | verdict gate (20) PAST; 35 more to the edge figure's 100 | 65 of 100 settled / verdict earned - 65 of 100 toward the edge figure |  |  |
| NCAAF | spread 60-70% | statistical | 32 | 100 | verdict gate (20) PAST; 68 more to the edge figure's 100 | 32 of 100 settled / verdict earned - 32 of 100 toward the edge figure |  |  |
| NCAAF | spread 70-80% | statistical | 43 | 100 | verdict gate (20) PAST; 57 more to the edge figure's 100 | 43 of 100 settled / verdict earned - 43 of 100 toward the edge figure |  |  |
| NCAAF | spread 80%+ | statistical | 45 | 100 | verdict gate (20) PAST; 55 more to the edge figure's 100 | 45 of 100 settled / verdict earned - 45 of 100 toward the edge figure |  |  |
| UFC | moneyline 50-60%, every card together | statistical | 28 | 100 | verdict gate (20) PAST; 72 more to the edge figure's 100 | 28 of 100 settled / verdict earned - 28 of 100 toward the edge figure | per card: Numbered card 0, Fight Night 22, Contender Series 6 | **G2** |
| UFC | moneyline 60-70%, every card together | statistical | 15 | 20 | 5 more to a verdict (20) | 15 of 20 settled / 5 more settled | per card: Numbered card 0, Fight Night 14, Contender Series 1 | **G2** |
| UFC | moneyline 70-80%, every card together | statistical | 4 | 20 | 16 more to a verdict (20) | 4 of 20 settled / 16 more settled | per card: Numbered card 0, Fight Night 2, Contender Series 2 | **G2** |
| UFC | moneyline 80%+, every card together | statistical | 2 | 20 | 18 more to a verdict (20) | 2 of 20 settled / 18 more settled | per card: Numbered card 0, Fight Night 1, Contender Series 1 | **G2** |

#### C. The tier table's "closest to a verdict" line (a share, not a count of bets; not recounted)

How got: `calibration._closest_verdict`. No sport has seven days of settlements, so every line says "pace unknown". 5 rows.

| sport | market | forecaster | N | gate | distance | what the page says | notes | flag |
|---|---|---|---|---|---|---|---|---|
| NFL | spread | statistical | 11 (not recounted) |  | no gate (a share) | Closest to a verdict: SOLID -- 9 more settled, pace unknown | no pace stated; it would pool every market and both forecasters (190 settled over 6 days) |  |
| MLB | moneyline | statistical | 0 (not recounted) |  | no gate (a share) | Closest to a verdict: STRONG -- 20 more settled, pace unknown | no pace stated; it would pool every market and both forecasters (512 settled over 6 days) |  |
| NBA | moneyline | statistical | 0 (not recounted) |  | no gate (a share) | Closest to a verdict: LEAN -- 20 more settled, pace unknown | no pace stated; it would pool every market and both forecasters (0 settled over 0 days) |  |
| NCAAF | spread | statistical | 185 (not recounted) |  | no gate (a share) | Every tier has settled enough for a verdict. |  |  |
| UFC | moneyline, every card together | statistical | 15 (not recounted) |  | no gate (a share) | Closest to a verdict: SOLID -- 5 more settled, pace unknown | no pace stated; it would pool every market and both forecasters (120 settled over 3 days) | **G2** |

#### D. The blind edge figure's gate (100 resolved disagreements; the count only)

How got: `calibration.edge`: settled standing questions where the model's probability exceeds the market's by more than 0.05. What the figure would say is not read. 5 rows.

| sport | market | forecaster | N | gate | distance | what the page says | notes | flag |
|---|---|---|---|---|---|---|---|---|
| NFL | spread | statistical | 14 | 100 | 86 more | 14 of the 100 disagreements required; 86 more |  |  |
| MLB | moneyline | statistical | 46 | 100 | 54 more | 46 of the 100 disagreements required; 54 more |  |  |
| NBA | moneyline | statistical | 0 | 100 | 100 more | 0 of the 100 disagreements required; 100 more |  |  |
| NCAAF | spread | statistical | 98 | 100 | 2 more | 98 of the 100 disagreements required; 2 more |  |  |
| UFC | moneyline, every card together | statistical | 0 | 100 | 100 more | 0 of the 100 disagreements required; 100 more | per card: Numbered card 0, Fight Night 0, Contender Series 0 | **G2** |

#### E. The ranker: questions that led the slate against those they outranked (100 on each side)

How got: `calibration.ranker_comparison`, from `prediction_ranks` (not backfilled) on the standing settled rows. N below is "led the slate"; the other side is in the distance and the words. 29 rows.

| sport | market | forecaster | N | gate | distance | what the page says | notes | flag |
|---|---|---|---|---|---|---|---|---|
| NFL | spread | statistical | 28 | 100 | led the slate: 72 more; outranked: 86 more | 28 settled on the shortlist and 14 off it; both sides need 100 (outranked: page 14 / mine 14) |  |  |
| NFL | moneyline | statistical | 31 | 100 | led the slate: 69 more; outranked: 99 more | 31 settled on the shortlist and 1 off it; both sides need 100 (outranked: page 1 / mine 1) |  |  |
| NFL | total | statistical | 17 | 100 | led the slate: 83 more; outranked: 99 more | 17 settled on the shortlist and 1 off it; both sides need 100 (outranked: page 1 / mine 1) |  |  |
| NFL | prop: passing_yards | statistical | 0 | 100 | led the slate: 100 more; outranked: 90 more | 0 settled on the shortlist and 10 off it; both sides need 100 (outranked: page 10 / mine 10) |  |  |
| NFL | prop: receiving_yards | statistical | 0 | 100 | led the slate: 100 more; outranked: 90 more | 0 settled on the shortlist and 10 off it; both sides need 100 (outranked: page 10 / mine 10) |  |  |
| NFL | prop: rushing_yards | statistical | 0 | 100 | led the slate: 100 more; outranked: 91 more | 0 settled on the shortlist and 9 off it; both sides need 100 (outranked: page 9 / mine 9) |  |  |
| NFL | prop: receptions | statistical | 0 | 100 | led the slate: 100 more; outranked: 91 more | 0 settled on the shortlist and 9 off it; both sides need 100 (outranked: page 9 / mine 9) |  |  |
| NFL | prop: passing_tds | statistical | 1 | 100 | led the slate: 99 more; outranked: 93 more | 1 settled on the shortlist and 7 off it; both sides need 100 (outranked: page 7 / mine 7) |  |  |
| MLB | moneyline | statistical | 98 | 100 | led the slate: 2 more; outranked: PAST IT | 98 settled on the shortlist and 151 off it; both sides need 100 (outranked: page 151 / mine 151) |  |  |
| MLB | spread | statistical | 105 | 100 | led the slate: PAST IT; outranked: 13 more | 105 settled on the shortlist and 87 off it; both sides need 100 (outranked: page 87 / mine 87) |  |  |
| MLB | total | statistical | 78 | 100 | led the slate: 22 more; outranked: PAST IT | 78 settled on the shortlist and 125 off it; both sides need 100 (outranked: page 125 / mine 125) |  |  |
| MLB | prop: batter_hits | statistical | 20 | 100 | led the slate: 80 more; outranked: 89 more | 20 settled on the shortlist and 11 off it; both sides need 100 (outranked: page 11 / mine 11) |  |  |
| MLB | prop: batter_total_bases | statistical | 0 | 100 | led the slate: 100 more; outranked: 100 more | 0 settled on the shortlist and 0 off it; both sides need 100 (outranked: page 0 / mine 0) |  |  |
| MLB | prop: batter_home_runs | statistical | 25 | 100 | led the slate: 75 more; outranked: 94 more | 25 settled on the shortlist and 6 off it; both sides need 100 (outranked: page 6 / mine 6) |  |  |
| MLB | prop: batter_strikeouts | statistical | 4 | 100 | led the slate: 96 more; outranked: 94 more | 4 settled on the shortlist and 6 off it; both sides need 100 (outranked: page 6 / mine 6) |  |  |
| MLB | prop: pitcher_strikeouts | statistical | 3 | 100 | led the slate: 97 more; outranked: 95 more | 3 settled on the shortlist and 5 off it; both sides need 100 (outranked: page 5 / mine 5) |  |  |
| NBA | moneyline | statistical | 0 | 100 | led the slate: 100 more; outranked: 100 more | 0 settled on the shortlist and 0 off it; both sides need 100 (outranked: page 0 / mine 0) |  |  |
| NBA | spread | statistical | 0 | 100 | led the slate: 100 more; outranked: 100 more | 0 settled on the shortlist and 0 off it; both sides need 100 (outranked: page 0 / mine 0) |  |  |
| NBA | total | statistical | 0 | 100 | led the slate: 100 more; outranked: 100 more | 0 settled on the shortlist and 0 off it; both sides need 100 (outranked: page 0 / mine 0) |  |  |
| NBA | prop: points | statistical | 0 | 100 | led the slate: 100 more; outranked: 100 more | 0 settled on the shortlist and 0 off it; both sides need 100 (outranked: page 0 / mine 0) |  |  |
| NBA | prop: rebounds | statistical | 0 | 100 | led the slate: 100 more; outranked: 100 more | 0 settled on the shortlist and 0 off it; both sides need 100 (outranked: page 0 / mine 0) |  |  |
| NBA | prop: assists | statistical | 0 | 100 | led the slate: 100 more; outranked: 100 more | 0 settled on the shortlist and 0 off it; both sides need 100 (outranked: page 0 / mine 0) |  |  |
| NBA | prop: threes | statistical | 0 | 100 | led the slate: 100 more; outranked: 100 more | 0 settled on the shortlist and 0 off it; both sides need 100 (outranked: page 0 / mine 0) |  |  |
| NCAAF | spread | statistical | 34 | 100 | led the slate: 66 more; outranked: PAST IT | 34 settled on the shortlist and 151 off it; both sides need 100 (outranked: page 151 / mine 151) |  |  |
| NCAAF | moneyline | statistical | 38 | 100 | led the slate: 62 more; outranked: PAST IT | 38 settled on the shortlist and 104 off it; both sides need 100 (outranked: page 104 / mine 104) |  |  |
| NCAAF | total | statistical | 46 | 100 | led the slate: 54 more; outranked: 2 more | 46 settled on the shortlist and 98 off it; both sides need 100 (outranked: page 98 / mine 98) |  |  |
| UFC | moneyline, every card together | statistical | 49 | 100 | led the slate: 51 more; outranked: 100 more | 49 settled on the shortlist and 0 off it; both sides need 100 (outranked: page 0 / mine 0) | per card: Numbered card 0/0, Fight Night 39/0, Contender Series 10/0; with the card's start read to the second: 43/6 | **G2, G3** |
| UFC | rounds, every card together | statistical | 49 | 100 | led the slate: 51 more; outranked: 100 more | 49 settled on the shortlist and 0 off it; both sides need 100 (outranked: page 0 / mine 0) | per card: Numbered card 0/0, Fight Night 39/0, Contender Series 10/0; with the card's start read to the second: 43/6 | **G2, G3** |
| UFC | distance, every card together | statistical | 49 | 100 | led the slate: 51 more; outranked: 100 more | 49 settled on the shortlist and 0 off it; both sides need 100 (outranked: page 0 / mine 0) | per card: Numbered card 0/0, Fight Night 39/0, Contender Series 10/0; with the card's start read to the second: 43/6 | **G2, G3** |

#### F. Taken, passed over, every forecast (100 each; the comparison needs both)

How got: `calibration.taken_comparison`. N is "taken": the operator has recorded no tap, so it is 0 everywhere. 21 rows.

| sport | market | forecaster | N | gate | distance | what the page says | notes | flag |
|---|---|---|---|---|---|---|---|---|
| NFL | spread | statistical | 0 | 100 | taken: 100 more; passed over: 58 more (the comparison needs both) | taken 0 of 100; passed over 42 of 100; every forecast 42 of 100 (mine: 0, 42, 42) |  |  |
| NFL | moneyline | statistical | 0 | 100 | taken: 100 more; passed over: 68 more (the comparison needs both) | taken 0 of 100; passed over 32 of 100; every forecast 32 of 100 (mine: 0, 32, 32) |  |  |
| NFL | total | statistical | 0 | 100 | taken: 100 more; passed over: 82 more (the comparison needs both) | taken 0 of 100; passed over 18 of 100; every forecast 18 of 100 (mine: 0, 18, 18) |  |  |
| NFL | prop: passing_yards | statistical | 0 | 100 | taken: 100 more; passed over: 90 more (the comparison needs both) | taken 0 of 100; passed over 10 of 100; every forecast 10 of 100 (mine: 0, 10, 10) |  |  |
| NFL | prop: receiving_yards | statistical | 0 | 100 | taken: 100 more; passed over: 90 more (the comparison needs both) | taken 0 of 100; passed over 10 of 100; every forecast 10 of 100 (mine: 0, 10, 10) |  |  |
| NFL | prop: rushing_yards | statistical | 0 | 100 | taken: 100 more; passed over: 91 more (the comparison needs both) | taken 0 of 100; passed over 9 of 100; every forecast 9 of 100 (mine: 0, 9, 9) |  |  |
| NFL | prop: receptions | statistical | 0 | 100 | taken: 100 more; passed over: 91 more (the comparison needs both) | taken 0 of 100; passed over 9 of 100; every forecast 9 of 100 (mine: 0, 9, 9) |  |  |
| NFL | prop: passing_tds | statistical | 0 | 100 | taken: 100 more; passed over: 92 more (the comparison needs both) | taken 0 of 100; passed over 8 of 100; every forecast 8 of 100 (mine: 0, 8, 8) |  |  |
| MLB | moneyline | statistical | 0 | 100 | taken: 100 more; passed over: PAST IT (the comparison needs both) | taken 0 of 100; passed over 260 of 100; every forecast 260 of 100 (mine: 0, 260, 260) |  |  |
| MLB | spread | statistical | 0 | 100 | taken: 100 more; passed over: PAST IT (the comparison needs both) | taken 0 of 100; passed over 202 of 100; every forecast 202 of 100 (mine: 0, 202, 202) |  |  |
| MLB | total | statistical | 0 | 100 | taken: 100 more; passed over: PAST IT (the comparison needs both) | taken 0 of 100; passed over 213 of 100; every forecast 213 of 100 (mine: 0, 213, 213) |  |  |
| MLB | prop: batter_hits | statistical | 0 | 100 | taken: 100 more; passed over: 69 more (the comparison needs both) | taken 0 of 100; passed over 31 of 100; every forecast 31 of 100 (mine: 0, 31, 31) |  |  |
| MLB | prop: batter_home_runs | statistical | 0 | 100 | taken: 100 more; passed over: 69 more (the comparison needs both) | taken 0 of 100; passed over 31 of 100; every forecast 31 of 100 (mine: 0, 31, 31) |  |  |
| MLB | prop: batter_strikeouts | statistical | 0 | 100 | taken: 100 more; passed over: 90 more (the comparison needs both) | taken 0 of 100; passed over 10 of 100; every forecast 10 of 100 (mine: 0, 10, 10) |  |  |
| MLB | prop: pitcher_strikeouts | statistical | 0 | 100 | taken: 100 more; passed over: 92 more (the comparison needs both) | taken 0 of 100; passed over 8 of 100; every forecast 8 of 100 (mine: 0, 8, 8) |  |  |
| NCAAF | spread | statistical | 0 | 100 | taken: 100 more; passed over: PAST IT (the comparison needs both) | taken 0 of 100; passed over 185 of 100; every forecast 185 of 100 (mine: 0, 185, 185) |  |  |
| NCAAF | moneyline | statistical | 0 | 100 | taken: 100 more; passed over: PAST IT (the comparison needs both) | taken 0 of 100; passed over 142 of 100; every forecast 142 of 100 (mine: 0, 142, 142) |  |  |
| NCAAF | total | statistical | 0 | 100 | taken: 100 more; passed over: PAST IT (the comparison needs both) | taken 0 of 100; passed over 144 of 100; every forecast 144 of 100 (mine: 0, 144, 144) |  |  |
| UFC | moneyline, every card together | statistical | 0 | 100 | taken: 100 more; passed over: 51 more (the comparison needs both) | taken 0 of 100; passed over 49 of 100; every forecast 49 of 100 (mine: 0, 49, 49) | per card: Numbered card 0, Fight Night 39, Contender Series 10 | **G2** |
| UFC | rounds, every card together | statistical | 0 | 100 | taken: 100 more; passed over: 51 more (the comparison needs both) | taken 0 of 100; passed over 49 of 100; every forecast 49 of 100 (mine: 0, 49, 49) | per card: Numbered card 0, Fight Night 39, Contender Series 10 | **G2** |
| UFC | distance, every card together | statistical | 0 | 100 | taken: 100 more; passed over: 51 more (the comparison needs both) | taken 0 of 100; passed over 49 of 100; every forecast 49 of 100 (mine: 0, 49, 49) | per card: Numbered card 0, Fight Night 39, Contender Series 10 | **G2** |

#### G. At the venue's line: each curve and its outlook (100 settled comparisons)

How got: `calibration.at_the_line_curve` through `at_the_line.standing_claims`: one claim per distinct bet per forecaster (repair item 6). 30 rows.

| sport | market | forecaster | N | gate | distance | what the page says | notes | flag |
|---|---|---|---|---|---|---|---|---|
| NFL | spread | statistical | 14 | 100 | 86 more | 14 of 100 settled comparisons · 86 more // 14 of 100 · ~119 expected · season ends Sunday 10 January | page ~119 (105 more) [6 of 14 settled claims under 50% (in no bucket)] |  |
| NFL | spread | reasoning pass | 0 | 100 | 100 more | 0 of 100 settled comparisons · 100 more // 0 of 100 · no claim written yet; no rate |  |  |
| NFL | total | statistical | 1 | 100 | 99 more | 1 of 100 settled comparisons · 99 more // 1 of 100 · ~16 expected · season ends Sunday 10 January · THIS GATE CANNOT CLEAR THIS SEASON | page ~16 (15 more) [1 of 1 settled claims under 50% (in no bucket)] |  |
| NFL | total | reasoning pass | 1 | 100 | 99 more | 1 of 100 settled comparisons · 99 more // 1 of 100 · ~16 expected · season ends Sunday 10 January · THIS GATE CANNOT CLEAR THIS SEASON | page ~16 (15 more) |  |
| NFL | moneyline | statistical | 16 | 100 | 84 more | 16 of 100 settled comparisons · 84 more // 16 of 100 · ~256 expected · season ends Sunday 10 January | page ~256 (240 more) [7 of 16 settled claims under 50% (in no bucket)] |  |
| NFL | moneyline | reasoning pass | 16 | 100 | 84 more | 16 of 100 settled comparisons · 84 more // 16 of 100 · ~256 expected · season ends Sunday 10 January | page ~256 (240 more) [7 of 16 settled claims under 50% (in no bucket)] |  |
| MLB | spread | statistical | 102 | 100 | PAST IT | 102 settled comparisons, past the 100 this record needs // 102 of 100 · ~111 expected · season ends Sunday 27 September | page ~111 (past already); on slates still ahead only: ~102 [102 of 102 settled claims under 50% (in no bucket)] |  |
| MLB | spread | reasoning pass | 0 | 100 | 100 more | 0 of 100 settled comparisons · 100 more // 0 of 100 · no claim written yet; no rate |  |  |
| MLB | total | statistical | 25 | 100 | 75 more | 25 of 100 settled comparisons · 75 more // 25 of 100 · ~28 expected · season ends Sunday 27 September · THIS GATE CANNOT CLEAR THIS SEASON | page ~28 (3 more); on slates still ahead only: ~25 [17 of 25 settled claims under 50% (in no bucket)] |  |
| MLB | total | reasoning pass | 25 | 100 | 75 more | 25 of 100 settled comparisons · 75 more // 25 of 100 · ~28 expected · season ends Sunday 27 September · THIS GATE CANNOT CLEAR THIS SEASON | page ~28 (3 more); on slates still ahead only: ~25 [22 of 25 settled claims under 50% (in no bucket)] |  |
| MLB | moneyline | statistical | 107 | 100 | PAST IT | 107 settled comparisons, past the 100 this record needs // 107 of 100 · ~117 expected · season ends Sunday 27 September | page ~117 (past already); on slates still ahead only: ~107 [20 of 107 settled claims under 50% (in no bucket)] |  |
| MLB | moneyline | reasoning pass | 108 | 100 | PAST IT | 108 settled comparisons, past the 100 this record needs // 108 of 100 · ~118 expected · season ends Sunday 27 September | page ~118 (past already); on slates still ahead only: ~108 [47 of 108 settled claims under 50% (in no bucket)] |  |
| NBA | spread | statistical | 0 | 100 | 100 more | 0 of 100 settled comparisons · 100 more // 0 of 100 · no claim written yet; no rate |  |  |
| NBA | spread | reasoning pass | 0 | 100 | 100 more | 0 of 100 settled comparisons · 100 more // 0 of 100 · no claim written yet; no rate |  |  |
| NBA | total | statistical | 0 | 100 | 100 more | 0 of 100 settled comparisons · 100 more // 0 of 100 · no claim written yet; no rate |  |  |
| NBA | total | reasoning pass | 0 | 100 | 100 more | 0 of 100 settled comparisons · 100 more // 0 of 100 · no claim written yet; no rate |  |  |
| NBA | moneyline | statistical | 0 | 100 | 100 more | 0 of 100 settled comparisons · 100 more // 0 of 100 · no claim written yet; no rate |  |  |
| NBA | moneyline | reasoning pass | 0 | 100 | 100 more | 0 of 100 settled comparisons · 100 more // 0 of 100 · no claim written yet; no rate |  |  |
| NCAAF | spread | statistical | 45 | 100 | 55 more | 45 of 100 settled comparisons · 55 more // 45 of 100 · ~704 expected · season ends Saturday 12 December | page ~704 (659 more) [35 of 45 settled claims under 50% (in no bucket)] |  |
| NCAAF | spread | reasoning pass | 0 | 100 | 100 more | 0 of 100 settled comparisons · 100 more // 0 of 100 · no claim written yet; no rate |  |  |
| NCAAF | total | statistical | 2 | 100 | 98 more | 2 of 100 settled comparisons · 98 more // 2 of 100 · ~88 expected · season ends Saturday 12 December · THIS GATE CANNOT CLEAR THIS SEASON | page ~88 (86 more) [2 of 2 settled claims under 50% (in no bucket)] |  |
| NCAAF | total | reasoning pass | 2 | 100 | 98 more | 2 of 100 settled comparisons · 98 more // 2 of 100 · ~88 expected · season ends Saturday 12 December · THIS GATE CANNOT CLEAR THIS SEASON | page ~88 (86 more) [2 of 2 settled claims under 50% (in no bucket)] |  |
| NCAAF | moneyline | statistical | 46 | 100 | 54 more | 46 of 100 settled comparisons · 54 more // 46 of 100 · ~734 expected · season ends Saturday 12 December | page ~734 (688 more) [21 of 46 settled claims under 50% (in no bucket)] |  |
| NCAAF | moneyline | reasoning pass | 46 | 100 | 54 more | 46 of 100 settled comparisons · 54 more // 46 of 100 · ~734 expected · season ends Saturday 12 December | page ~734 (688 more) [25 of 46 settled claims under 50% (in no bucket)] |  |
| UFC | moneyline, card: Numbered card | statistical | 0 | 100 | 100 more | 0 of 100 settled comparisons · 100 more // 0 of 100 · no claim written yet; no rate |  |  |
| UFC | moneyline, card: Numbered card | reasoning pass | 0 | 100 | 100 more | 0 of 100 settled comparisons · 100 more // 0 of 100 · no claim written yet; no rate |  |  |
| UFC | moneyline, card: Fight Night | statistical | 0 | 100 | 100 more | 0 of 100 settled comparisons · 100 more // 0 of 100 · no claim written yet; no rate |  |  |
| UFC | moneyline, card: Fight Night | reasoning pass | 0 | 100 | 100 more | 0 of 100 settled comparisons · 100 more // 0 of 100 · no claim written yet; no rate |  |  |
| UFC | moneyline, card: Contender Series | statistical | 0 | 100 | 100 more | 0 of 100 settled comparisons · 100 more // 0 of 100 · no claim written yet; no rate |  |  |
| UFC | moneyline, card: Contender Series | reasoning pass | 0 | 100 | 100 more | 0 of 100 settled comparisons · 100 more // 0 of 100 · no claim written yet; no rate |  |  |

#### H. At the venue's line: the hypothetical ledgers (100 disagreements; none shown)

How got: `paper.ledger`: settled standing claims where the model and the venue differ by more than 0.05 either way. 30 rows.

| sport | market | forecaster | N | gate | distance | what the page says | notes | flag |
|---|---|---|---|---|---|---|---|---|
| NFL | spread | statistical | 13 | 100 | 87 more | hypothetical, not shown yet: 13 of 100 disagreements · 87 more |  |  |
| NFL | spread | reasoning pass | 0 | 100 | 100 more | hypothetical, not shown yet: 0 of 100 disagreements · 100 more |  |  |
| NFL | total | statistical | 0 | 100 | 100 more | hypothetical, not shown yet: 0 of 100 disagreements · 100 more |  |  |
| NFL | total | reasoning pass | 0 | 100 | 100 more | hypothetical, not shown yet: 0 of 100 disagreements · 100 more |  |  |
| NFL | moneyline | statistical | 11 | 100 | 89 more | hypothetical, not shown yet: 11 of 100 disagreements · 89 more |  |  |
| NFL | moneyline | reasoning pass | 9 | 100 | 91 more | hypothetical, not shown yet: 9 of 100 disagreements · 91 more |  |  |
| MLB | spread | statistical | 67 | 100 | 33 more | hypothetical, not shown yet: 67 of 100 disagreements · 33 more |  |  |
| MLB | spread | reasoning pass | 0 | 100 | 100 more | hypothetical, not shown yet: 0 of 100 disagreements · 100 more |  |  |
| MLB | total | statistical | 10 | 100 | 90 more | hypothetical, not shown yet: 10 of 100 disagreements · 90 more |  |  |
| MLB | total | reasoning pass | 17 | 100 | 83 more | hypothetical, not shown yet: 17 of 100 disagreements · 83 more |  |  |
| MLB | moneyline | statistical | 56 | 100 | 44 more | hypothetical, not shown yet: 56 of 100 disagreements · 44 more |  |  |
| MLB | moneyline | reasoning pass | 75 | 100 | 25 more | hypothetical, not shown yet: 75 of 100 disagreements · 25 more |  |  |
| NBA | spread | statistical | 0 | 100 | 100 more | hypothetical, not shown yet: 0 of 100 disagreements · 100 more |  |  |
| NBA | spread | reasoning pass | 0 | 100 | 100 more | hypothetical, not shown yet: 0 of 100 disagreements · 100 more |  |  |
| NBA | total | statistical | 0 | 100 | 100 more | hypothetical, not shown yet: 0 of 100 disagreements · 100 more |  |  |
| NBA | total | reasoning pass | 0 | 100 | 100 more | hypothetical, not shown yet: 0 of 100 disagreements · 100 more |  |  |
| NBA | moneyline | statistical | 0 | 100 | 100 more | hypothetical, not shown yet: 0 of 100 disagreements · 100 more |  |  |
| NBA | moneyline | reasoning pass | 0 | 100 | 100 more | hypothetical, not shown yet: 0 of 100 disagreements · 100 more |  |  |
| NCAAF | spread | statistical | 38 | 100 | 62 more | hypothetical, not shown yet: 38 of 100 disagreements · 62 more |  |  |
| NCAAF | spread | reasoning pass | 0 | 100 | 100 more | hypothetical, not shown yet: 0 of 100 disagreements · 100 more |  |  |
| NCAAF | total | statistical | 1 | 100 | 99 more | hypothetical, not shown yet: 1 of 100 disagreements · 99 more |  |  |
| NCAAF | total | reasoning pass | 1 | 100 | 99 more | hypothetical, not shown yet: 1 of 100 disagreements · 99 more |  |  |
| NCAAF | moneyline | statistical | 29 | 100 | 71 more | hypothetical, not shown yet: 29 of 100 disagreements · 71 more |  |  |
| NCAAF | moneyline | reasoning pass | 33 | 100 | 67 more | hypothetical, not shown yet: 33 of 100 disagreements · 67 more |  |  |
| UFC | moneyline, card: Numbered card | statistical | 0 | 100 | 100 more | hypothetical, not shown yet: 0 of 100 disagreements · 100 more |  |  |
| UFC | moneyline, card: Numbered card | reasoning pass | 0 | 100 | 100 more | hypothetical, not shown yet: 0 of 100 disagreements · 100 more |  |  |
| UFC | moneyline, card: Fight Night | statistical | 0 | 100 | 100 more | hypothetical, not shown yet: 0 of 100 disagreements · 100 more |  |  |
| UFC | moneyline, card: Fight Night | reasoning pass | 0 | 100 | 100 more | hypothetical, not shown yet: 0 of 100 disagreements · 100 more |  |  |
| UFC | moneyline, card: Contender Series | statistical | 0 | 100 | 100 more | hypothetical, not shown yet: 0 of 100 disagreements · 100 more |  |  |
| UFC | moneyline, card: Contender Series | reasoning pass | 0 | 100 | 100 more | hypothetical, not shown yet: 0 of 100 disagreements · 100 more |  |  |

#### I. At the venue's line: the edge figure's gate (in the payload only; the page does not draw it)

How got: `calibration.at_the_line_edge`. Its count takes only claims where the model is higher than the venue on the home side or the over (finding F1). 5 rows.

| sport | market | forecaster | N | gate | distance | what the page says | notes | flag |
|---|---|---|---|---|---|---|---|---|
| NFL | spread | statistical | 8 | 100 | 92 more | 8 of 100 settled comparisons · 92 more | counts only model higher on home/over; the other way 5; disagreements either way (the ledger's rule) 13; bolder on the model's own side 13 |  |
| MLB | spread | statistical | 1 | 100 | 99 more | 1 of 100 settled comparisons · 99 more | counts only model higher on home/over; the other way 66; disagreements either way (the ledger's rule) 67; bolder on the model's own side 66 |  |
| NBA | spread | statistical | 0 | 100 | 100 more | 0 of 100 settled comparisons · 100 more | counts only model higher on home/over; the other way 0; disagreements either way (the ledger's rule) 0; bolder on the model's own side 0 |  |
| NCAAF | spread | statistical | 8 | 100 | 92 more | 8 of 100 settled comparisons · 92 more | counts only model higher on home/over; the other way 30; disagreements either way (the ledger's rule) 38; bolder on the model's own side 38 |  |
| UFC | moneyline, card: Numbered card | statistical | 0 | 100 | 100 more | 0 of 100 settled comparisons · 100 more | counts only model higher on home/over; the other way 0; disagreements either way (the ledger's rule) 0; bolder on the model's own side 0 |  |

#### J. At the venue's line: coverage (a share, no gate)

How got: `at_the_line.coverage`: the questions answered, and how many of them hold a standing claim. 21 rows.

| sport | market | forecaster | N | gate | distance | what the page says | notes | flag |
|---|---|---|---|---|---|---|---|---|
| NFL | spread | statistical | 14 |  | no gate (a share) | point spread, statistical: read for 14 of 42 questions answered (33%) (mine: 14 of 42) |  |  |
| NFL | spread | reasoning pass | 0 |  | no gate (a share) | point spread, reasoning pass: read for 0 of 13 questions answered (0%) (mine: 0 of 13) |  |  |
| NFL | total | statistical | 1 |  | no gate (a share) | total, statistical: read for 1 of 18 questions answered (6%) (mine: 1 of 18) |  |  |
| NFL | total | reasoning pass | 1 |  | no gate (a share) | total, reasoning pass: read for 1 of 17 questions answered (6%) (mine: 1 of 17) |  |  |
| NFL | moneyline | statistical | 16 |  | no gate (a share) | moneyline, statistical: read for 16 of 32 questions answered (50%) (mine: 16 of 32) |  |  |
| NFL | moneyline | reasoning pass | 16 |  | no gate (a share) | moneyline, reasoning pass: read for 16 of 16 questions answered (100%) (mine: 16 of 16) |  |  |
| MLB | spread | statistical | 102 |  | no gate (a share) | point spread, statistical: read for 102 of 202 questions answered (50%) (mine: 102 of 202) |  |  |
| MLB | total | statistical | 25 |  | no gate (a share) | total, statistical: read for 25 of 213 questions answered (12%) (mine: 25 of 213) |  |  |
| MLB | total | reasoning pass | 25 |  | no gate (a share) | total, reasoning pass: read for 25 of 141 questions answered (18%) (mine: 25 of 141) |  |  |
| MLB | moneyline | statistical | 107 |  | no gate (a share) | moneyline, statistical: read for 107 of 260 questions answered (41%) (mine: 107 of 260) |  |  |
| MLB | moneyline | reasoning pass | 108 |  | no gate (a share) | moneyline, reasoning pass: read for 108 of 148 questions answered (73%) (mine: 108 of 148) |  |  |
| NCAAF | spread | statistical | 46 |  | no gate (a share) | point spread, statistical: read for 46 of 187 questions answered (25%) (mine: 46 of 187) |  |  |
| NCAAF | spread | reasoning pass | 0 |  | no gate (a share) | point spread, reasoning pass: read for 0 of 60 questions answered (0%) (mine: 0 of 60) |  |  |
| NCAAF | total | statistical | 2 |  | no gate (a share) | total, statistical: read for 2 of 146 questions answered (1%) (mine: 2 of 146) |  |  |
| NCAAF | total | reasoning pass | 2 |  | no gate (a share) | total, reasoning pass: read for 2 of 69 questions answered (3%) (mine: 2 of 69) |  |  |
| NCAAF | moneyline | statistical | 48 |  | no gate (a share) | moneyline, statistical: read for 48 of 144 questions answered (33%) (mine: 48 of 144) |  |  |
| NCAAF | moneyline | reasoning pass | 48 |  | no gate (a share) | moneyline, reasoning pass: read for 48 of 62 questions answered (77%) (mine: 48 of 62) |  |  |
| UFC | moneyline, card: Fight Night | statistical | 0 |  | no gate (a share) | moneyline, Fight Night, statistical: read for 0 of 41 questions answered (0%) (mine: 0 of 41) |  |  |
| UFC | moneyline, card: Fight Night | reasoning pass | 0 |  | no gate (a share) | moneyline, Fight Night, reasoning pass: read for 0 of 41 questions answered (0%) (mine: 0 of 41) |  |  |
| UFC | moneyline, card: Contender Series | statistical | 0 |  | no gate (a share) | moneyline, Contender Series, statistical: read for 0 of 15 questions answered (0%) (mine: 0 of 15) |  |  |
| UFC | moneyline, card: Contender Series | reasoning pass | 0 |  | no gate (a share) | moneyline, Contender Series, reasoning pass: read for 0 of 15 questions answered (0%) (mine: 0 of 15) |  |  |

#### K. The priced forecaster (100 settled comparisons; Q14, 1 of 3)

How got: `priced.forecast.standing_forecasts`. 10 rows.

| sport | market | forecaster | N | gate | distance | what the page says | notes | flag |
|---|---|---|---|---|---|---|---|---|
| NFL | spread | statistical | 13 | 100 | 87 more | 13 of 100 settled comparisons · 87 more |  |  |
| NFL | spread | reasoning pass | 13 | 100 | 87 more | 13 of 100 settled comparisons · 87 more |  |  |
| MLB | moneyline | statistical | 105 | 100 | PAST IT | 105 settled comparisons, past the 100 this record needs |  |  |
| MLB | moneyline | reasoning pass | 94 | 100 | 6 more | 94 of 100 settled comparisons · 6 more |  |  |
| NCAAF | moneyline | statistical | 54 | 100 | 46 more | 54 of 100 settled comparisons · 46 more |  |  |
| NCAAF | moneyline | reasoning pass | 54 | 100 | 46 more | 54 of 100 settled comparisons · 46 more |  |  |
| NCAAF | spread | statistical | 58 | 100 | 42 more | 58 of 100 settled comparisons · 42 more |  |  |
| NCAAF | spread | reasoning pass | 58 | 100 | 42 more | 58 of 100 settled comparisons · 42 more |  |  |
| NCAAF | total | statistical | 67 | 100 | 33 more | 67 of 100 settled comparisons · 33 more |  |  |
| NCAAF | total | reasoning pass | 67 | 100 | 33 more | 67 of 100 settled comparisons · 33 more |  |  |

#### L. Where the line went, on the media line (50 pairs; Q14, 2 of 3)

How got: `drift.report` (the statistical model's, as the page paints it). 28 rows.

| sport | market | forecaster | N | gate | distance | what the page says | notes | flag |
|---|---|---|---|---|---|---|---|---|
| NFL | spread | statistical | 11 | 50 | 39 more | 11 of 50 pairs |  |  |
| NFL | moneyline | statistical | 0 | 50 | 50 more | 0 of 50 pairs |  |  |
| NFL | total | statistical | 0 | 50 | 50 more | 0 of 50 pairs |  |  |
| NFL | prop: passing_yards | statistical | 0 | 50 | 50 more | 0 of 50 pairs |  |  |
| NFL | prop: receiving_yards | statistical | 0 | 50 | 50 more | 0 of 50 pairs |  |  |
| NFL | prop: rushing_yards | statistical | 0 | 50 | 50 more | 0 of 50 pairs |  |  |
| NFL | prop: receptions | statistical | 0 | 50 | 50 more | 0 of 50 pairs |  |  |
| NFL | prop: passing_tds | statistical | 0 | 50 | 50 more | 0 of 50 pairs |  |  |
| MLB | moneyline | statistical | 52 | 50 | PAST IT | 52 pairs -- the page reports a direction (not restated: the edge question is not re-measured) |  |  |
| MLB | spread | statistical | 0 | 50 | 50 more | 0 of 50 pairs |  |  |
| MLB | total | statistical | 0 | 50 | 50 more | 0 of 50 pairs |  |  |
| MLB | prop: batter_hits | statistical | 0 | 50 | 50 more | 0 of 50 pairs |  |  |
| MLB | prop: batter_home_runs | statistical | 0 | 50 | 50 more | 0 of 50 pairs |  |  |
| MLB | prop: batter_strikeouts | statistical | 0 | 50 | 50 more | 0 of 50 pairs |  |  |
| MLB | prop: pitcher_strikeouts | statistical | 0 | 50 | 50 more | 0 of 50 pairs |  |  |
| NBA | spread | statistical | 0 | 50 | 50 more | 0 of 50 pairs |  |  |
| NCAAF | spread | statistical | 78 | 50 | PAST IT | 78 pairs -- the page reports a direction (not restated: the edge question is not re-measured) |  |  |
| NCAAF | moneyline | statistical | 49 | 50 | 1 more | 49 of 50 pairs |  |  |
| NCAAF | total | statistical | 54 | 50 | PAST IT | 54 pairs -- the page reports a direction (not restated: the edge question is not re-measured) |  |  |
| UFC | moneyline, card: Numbered card | statistical | 0 | 50 | 50 more | 0 of 50 pairs |  |  |
| UFC | moneyline, card: Fight Night | statistical | 0 | 50 | 50 more | 0 of 50 pairs |  |  |
| UFC | moneyline, card: Contender Series | statistical | 0 | 50 | 50 more | 0 of 50 pairs |  |  |
| UFC | rounds, card: Numbered card | statistical | 0 | 50 | 50 more | 0 of 50 pairs |  |  |
| UFC | rounds, card: Fight Night | statistical | 0 | 50 | 50 more | 0 of 50 pairs |  |  |
| UFC | rounds, card: Contender Series | statistical | 0 | 50 | 50 more | 0 of 50 pairs |  |  |
| UFC | distance, card: Numbered card | statistical | 0 | 50 | 50 more | 0 of 50 pairs |  |  |
| UFC | distance, card: Fight Night | statistical | 0 | 50 | 50 more | 0 of 50 pairs |  |  |
| UFC | distance, card: Contender Series | statistical | 0 | 50 | 50 more | 0 of 50 pairs |  |  |

#### M. Where the line went, on the venue's own pair (50 pairs; in the payload only)

How got: `drift.venue_report`. 26 rows.

| sport | market | forecaster | N | gate | distance | what the page says | notes | flag |
|---|---|---|---|---|---|---|---|---|
| NFL | moneyline | statistical | 11 | 50 | 39 more | 11 of 50 pairs |  |  |
| NFL | moneyline | reasoning pass | 8 | 50 | 42 more | 8 of 50 pairs |  |  |
| NFL | spread | statistical | 11 | 50 | 39 more | 11 of 50 pairs |  |  |
| NFL | spread | reasoning pass | 0 | 50 | 50 more | 0 of 50 pairs |  |  |
| NFL | total | statistical | 0 | 50 | 50 more | 0 of 50 pairs |  |  |
| NFL | total | reasoning pass | 0 | 50 | 50 more | 0 of 50 pairs |  |  |
| MLB | moneyline | statistical | 41 | 50 | 9 more | 41 of 50 pairs |  |  |
| MLB | moneyline | reasoning pass | 57 | 50 | PAST IT | 57 pairs -- a direction in the payload |  |  |
| MLB | spread | statistical | 56 | 50 | PAST IT | 56 pairs -- a direction in the payload |  |  |
| MLB | spread | reasoning pass | 0 | 50 | 50 more | 0 of 50 pairs |  |  |
| MLB | total | statistical | 6 | 50 | 44 more | 6 of 50 pairs |  |  |
| MLB | total | reasoning pass | 10 | 50 | 40 more | 10 of 50 pairs |  |  |
| NBA | spread | statistical | 0 | 50 | 50 more | 0 of 50 pairs |  |  |
| NBA | spread | reasoning pass | 0 | 50 | 50 more | 0 of 50 pairs |  |  |
| NCAAF | moneyline | statistical | 22 | 50 | 28 more | 22 of 50 pairs |  |  |
| NCAAF | moneyline | reasoning pass | 26 | 50 | 24 more | 26 of 50 pairs |  |  |
| NCAAF | spread | statistical | 26 | 50 | 24 more | 26 of 50 pairs |  |  |
| NCAAF | spread | reasoning pass | 0 | 50 | 50 more | 0 of 50 pairs |  |  |
| NCAAF | total | statistical | 1 | 50 | 49 more | 1 of 50 pairs |  |  |
| NCAAF | total | reasoning pass | 1 | 50 | 49 more | 1 of 50 pairs |  |  |
| UFC | moneyline, card: Numbered card | statistical | 0 | 50 | 50 more | 0 of 50 pairs |  |  |
| UFC | moneyline, card: Numbered card | reasoning pass | 0 | 50 | 50 more | 0 of 50 pairs |  |  |
| UFC | moneyline, card: Fight Night | statistical | 0 | 50 | 50 more | 0 of 50 pairs |  |  |
| UFC | moneyline, card: Fight Night | reasoning pass | 0 | 50 | 50 more | 0 of 50 pairs |  |  |
| UFC | moneyline, card: Contender Series | statistical | 0 | 50 | 50 more | 0 of 50 pairs |  |  |
| UFC | moneyline, card: Contender Series | reasoning pass | 0 | 50 | 50 more | 0 of 50 pairs |  |  |

#### N. Each correction's gate (50 settled questions on the key; Q16, Q23, Q31, Q32)

How got: `views._correction_count` and `correction.settled_rows`. A category past its 50 is fitted, and nothing is in force in any category (Q32). 27 rows.

| sport | market | forecaster | N | gate | distance | what the page says | notes | flag |
|---|---|---|---|---|---|---|---|---|
| NFL | moneyline, reasoning pass | reasoning pass | 16 | 50 | 34 more | 16 of 50 settled questions -- not in force |  |  |
| NFL | moneyline, statistical | statistical | 32 | 50 | 18 more | 32 of 50 settled questions -- not in force |  |  |
| NFL | player props, every prop type together, statistical | statistical | 65 | 50 | PAST IT | 65 settled questions -- fitted, NOT IN FORCE (no measured activation row) |  |  |
| NFL | point spread, reasoning pass | reasoning pass | 13 | 50 | 37 more | 13 of 50 settled questions -- not in force |  |  |
| NFL | point spread, statistical | statistical | 42 | 50 | 8 more | 42 of 50 settled questions -- not in force -- LABEL: fit of Monday 28 September fitted below its gate: 60 forecasts = 41 questions, can never be in force |  |  |
| NFL | total, reasoning pass | reasoning pass | 17 | 50 | 33 more | 17 of 50 settled questions -- not in force |  |  |
| NFL | total, statistical | statistical | 18 | 50 | 32 more | 18 of 50 settled questions -- not in force |  |  |
| MLB | moneyline, reasoning pass | reasoning pass | 148 | 50 | PAST IT | 148 settled questions -- fitted, NOT IN FORCE (no measured activation row) |  |  |
| MLB | moneyline, statistical | statistical | 260 | 50 | PAST IT | 260 settled questions -- withdrawn since Tuesday 29 September; nothing in force |  |  |
| MLB | player props, every prop type together, reasoning pass | reasoning pass | 8 | 50 | 42 more | 8 of 50 settled questions -- not in force |  |  |
| MLB | player props, every prop type together, statistical | statistical | 80 | 50 | PAST IT | 80 settled questions -- fitted, NOT IN FORCE (no measured activation row) |  |  |
| MLB | point spread, statistical | statistical | 202 | 50 | PAST IT | 202 settled questions -- fitted, NOT IN FORCE (no measured activation row) |  |  |
| MLB | total, reasoning pass | reasoning pass | 141 | 50 | PAST IT | 141 settled questions -- fitted, NOT IN FORCE (no measured activation row) -- LABEL: fit of Monday 21 September fitted below its gate: 76 forecasts = 48 questions, can never be in force |  |  |
| MLB | total, statistical | statistical | 213 | 50 | PAST IT | 213 settled questions -- fitted, NOT IN FORCE (no measured activation row) |  |  |
| NBA | point spread, statistical | statistical | 0 | 50 | 50 more | 0 of 50 settled questions -- not in force |  |  |
| NCAAF | moneyline, reasoning pass | reasoning pass | 60 | 50 | PAST IT | 60 settled questions -- fitted, NOT IN FORCE (no measured activation row) |  |  |
| NCAAF | moneyline, statistical | statistical | 142 | 50 | PAST IT | 142 settled questions -- fitted, NOT IN FORCE (no measured activation row) |  |  |
| NCAAF | point spread, reasoning pass | reasoning pass | 58 | 50 | PAST IT | 58 settled questions -- fitted, NOT IN FORCE (no measured activation row) |  |  |
| NCAAF | point spread, statistical | statistical | 185 | 50 | PAST IT | 185 settled questions -- fitted, NOT IN FORCE (no measured activation row) |  |  |
| NCAAF | total, reasoning pass | reasoning pass | 67 | 50 | PAST IT | 67 settled questions -- fitted, NOT IN FORCE (no measured activation row) |  |  |
| NCAAF | total, statistical | statistical | 144 | 50 | PAST IT | 144 settled questions -- fitted, NOT IN FORCE (no measured activation row) |  |  |
| UFC | distance, every card together, reasoning pass | reasoning pass | 14 | 50 | 36 more | 14 of 50 settled questions -- not in force |  |  |
| UFC | distance, every card together, statistical | statistical | 49 | 50 | 1 more | 49 of 50 settled questions -- not in force -- LABEL: fit of Monday 21 September fitted below its gate: 56 forecasts = 32 questions, can never be in force -- LABEL: fit of Monday 28 September fitted below its gate: 85 forecasts = 49 questions, can never be in force |  |  |
| UFC | moneyline, every card together, reasoning pass | reasoning pass | 49 | 50 | 1 more | 49 of 50 settled questions -- not in force -- LABEL: fit of Monday 28 September fitted below its gate: 63 forecasts = 49 questions, can never be in force |  |  |
| UFC | moneyline, every card together, statistical | statistical | 49 | 50 | 1 more | 49 of 50 settled questions -- not in force -- LABEL: fit of Monday 21 September fitted below its gate: 56 forecasts = 32 questions, can never be in force -- LABEL: fit of Monday 28 September fitted below its gate: 85 forecasts = 49 questions, can never be in force |  |  |
| UFC | rounds, every card together, reasoning pass | reasoning pass | 14 | 50 | 36 more | 14 of 50 settled questions -- not in force |  |  |
| UFC | rounds, every card together, statistical | statistical | 49 | 50 | 1 more | 49 of 50 settled questions -- not in force -- LABEL: fit of Monday 21 September fitted below its gate: 56 forecasts = 32 questions, can never be in force -- LABEL: fit of Monday 28 September fitted below its gate: 85 forecasts = 49 questions, can never be in force |  |  |

#### O. The closing line since the repair, each forecaster's window line (50 closes; Q22)

How got: `calibration.clv_report`, each forecaster's block. 10 rows.

| sport | market | forecaster | N | gate | distance | what the page says | notes | flag |
|---|---|---|---|---|---|---|---|---|
| NFL | every market | statistical | 11 | 50 | 39 more | 11 priced against a close since 24 Sep; first clean read 15 Oct, nothing claimed before | awaiting a close 0; withdrawn 4; would not have cleared 0; repeats 0 |  |
| NFL | every market | reasoning pass | 1 | 50 | 49 more | 1 priced against a close since 24 Sep; first clean read 15 Oct, nothing claimed before | awaiting a close 0; withdrawn 0; would not have cleared 0; repeats 0 |  |
| MLB | every market | statistical | 15 | 50 | 35 more | 15 priced against a close since 24 Sep; first clean read 15 Oct, nothing claimed before | awaiting a close 0; withdrawn 0; would not have cleared 2; repeats 14 |  |
| MLB | every market | reasoning pass | 1 | 50 | 49 more | 1 priced against a close since 24 Sep; first clean read 15 Oct, nothing claimed before | awaiting a close 0; withdrawn 0; would not have cleared 0; repeats 3 |  |
| NBA | every market | statistical | 0 | 50 | 50 more | 0 priced against a close since 24 Sep; first clean read 15 Oct, nothing claimed before | awaiting a close 0; withdrawn 0; would not have cleared 0; repeats 0 |  |
| NBA | every market | reasoning pass | 0 | 50 | 50 more | 0 priced against a close since 24 Sep; first clean read 15 Oct, nothing claimed before | awaiting a close 0; withdrawn 0; would not have cleared 0; repeats 0 |  |
| NCAAF | every market | statistical | 8 | 50 | 42 more | 8 priced against a close since 24 Sep; first clean read 15 Oct, nothing claimed before | awaiting a close 1; withdrawn 0; would not have cleared 0; repeats 0 |  |
| NCAAF | every market | reasoning pass | 0 | 50 | 50 more | 0 priced against a close since 24 Sep; first clean read 15 Oct, nothing claimed before | awaiting a close 0; withdrawn 0; would not have cleared 0; repeats 0 |  |
| UFC | every market | statistical | 0 | 50 | 50 more | 0 priced against a close since 24 Sep; first clean read 15 Oct, nothing claimed before | awaiting a close 0; withdrawn 0; would not have cleared 0; repeats 0 |  |
| UFC | every market | reasoning pass | 0 | 50 | 50 more | 0 priced against a close since 24 Sep; first clean read 15 Oct, nothing claimed before | awaiting a close 0; withdrawn 0; would not have cleared 0; repeats 0 |  |

#### P. The closing line, each market and forecaster (50 closes; the kill criterion reads the same count and stops nothing before 15 October)

How got: `calibration.clv_report`, each market line; `priced.coverage.stopped` is empty in all five sports. 6 rows.

| sport | market | forecaster | N | gate | distance | what the page says | notes | flag |
|---|---|---|---|---|---|---|---|---|
| NFL | spread | statistical | 11 | 50 | 39 more | 11 of 50 since 24 Sep · first clean read 15 Oct · 1 closed with no later read (not counted) | kill criterion: stopped 0 (it reads nothing before Thursday 15 October) |  |
| NFL | total | reasoning pass | 1 | 50 | 49 more | 1 of 50 since 24 Sep · first clean read 15 Oct | kill criterion: stopped 0 (it reads nothing before Thursday 15 October) |  |
| MLB | spread | statistical | 15 | 50 | 35 more | 15 of 50 since 24 Sep · first clean read 15 Oct · 23 closed with no later read (not counted) · 17 restated (not counted) · 14 repeats (counted once) | kill criterion: stopped 0 (it reads nothing before Thursday 15 October) |  |
| MLB | total | statistical | 0 | 50 | 50 more | 0 of 50 since 24 Sep · first clean read 15 Oct · 2 closed with no later read (not counted) | kill criterion: stopped 0 (it reads nothing before Thursday 15 October) |  |
| MLB | total | reasoning pass | 1 | 50 | 49 more | 1 of 50 since 24 Sep · first clean read 15 Oct · 4 closed with no later read (not counted) · 6 restated (not counted) · 3 repeats (counted once) | kill criterion: stopped 0 (it reads nothing before Thursday 15 October) |  |
| NCAAF | spread | statistical | 8 | 50 | 42 more | 8 of 50 since 24 Sep · first clean read 15 Oct | kill criterion: stopped 0 (it reads nothing before Thursday 15 October) |  |

#### Q. The closing line's window (21 days from 24 September to the first clean read)

How got: `calibration.closing_line_window(now)`. 5 rows.

| sport | market | forecaster | N | gate | distance | what the page says | notes | flag |
|---|---|---|---|---|---|---|---|---|
| NFL | every market | both, each apart | 5 | 21 | 16 more | 5 of 21 days / read on 15 Oct, 16 days |  |  |
| MLB | every market | both, each apart | 5 | 21 | 16 more | 5 of 21 days / read on 15 Oct, 16 days |  |  |
| NBA | every market | both, each apart | 5 | 21 | 16 more | 5 of 21 days / read on 15 Oct, 16 days |  |  |
| NCAAF | every market | both, each apart | 5 | 21 | 16 more | 5 of 21 days / read on 15 Oct, 16 days |  |  |
| UFC | every market | both, each apart | 5 | 21 | 16 more | 5 of 21 days / read on 15 Oct, 16 days |  |  |

#### R. Other dated windows

How got: the page's own window line. 1 row.

| sport | market | forecaster | N | gate | distance | what the page says | notes | flag |
|---|---|---|---|---|---|---|---|---|
| MLB | the rung distribution | -- | 14 (not recounted) | 14 | PAST IT | 14 of 14 days / the window is open - read it |  |  |

#### S. Combos (a gate of 100 printed; nothing priced)

How got: the page's combos line. 5 rows.

| sport | market | forecaster | N | gate | distance | what the page says | notes | flag |
|---|---|---|---|---|---|---|---|---|
| NFL | packages | -- | 0 (not recounted) | 100 | 100 more | no package priced yet |  |  |
| MLB | packages | -- | 0 (not recounted) | 100 | 100 more | no package priced yet |  |  |
| NBA | packages | -- | 0 (not recounted) | 100 | 100 more | no package priced yet |  |  |
| NCAAF | packages | -- | 0 (not recounted) | 100 | 100 more | no package priced yet |  |  |
| UFC | packages | -- | 0 (not recounted) | 100 | 100 more | no package priced yet |  |  |

#### T. READINESS criterion 2: recommendations in one coverage entry (50), per forecaster, counted once

How got: `recommend.counted_once` on the copy (withdrawn by neither void; a
same-side pair of one forecaster's distinct bet counted once, as its earlier
row, Q12 and Q22), and again by the compiler's own pairing in Python, 12 of 12
equal (`compiler\c10_criterion2.py`). The 17 repeats left out are recs 9, 10,
12, 13, 14, 25, 26, 28, 34, 44, 48, 49, 79, 80, 93, 94 and 95; the 4 withdrawn
are 62, 63, 64 and 66.

READINESS left it to the re-read whether this count runs from 7 or 24
September (its section of 27 September). **The re-read reads it from 24
September**, the day ruling 8 restarts the observation window: the
conservative default, because it is the stricter count and claims no pass.
The count from 7 September is beside it, and the operator may rule the other
way. The criterion's verdict is not re-read here.

| sport | market | forecaster | N from 24 Sep (the re-read's reading) | distance to 50 | N from 7 Sep (beside it) |
|---|---|---|---|---|---|
| MLB | spread | statistical | 23 | 27 more | 55 (past 50) |
| MLB | total | statistical | 1 | 49 more | 2 |
| MLB | total | reasoning pass | 1 | 49 more | 11 |
| NFL | spread | statistical | 12 | 38 more | 12 |
| NFL | total | reasoning pass | 1 | 49 more | 1 |
| NCAAF | spread | statistical | 9 (8 closed, 1 awaiting its close: rec 111) | 41 more | 9 |
| every other sport, market and forecaster | -- | -- | 0 | 50 more | 0 |

---

## 3. Findings

**The queue rule:** a new finding becomes a question only if it breaks LAW 1
or LAW 3 or makes a gate count false. **None breaks LAW 1 or LAW 3.** Three
make a gate count false, all in UFC; they come first and are marked. Everything
else is for FOLLOWUPS.

* **LAW 1, not broken.** 0 forecasts since item 2's release were written at or
  after their game's start, every stamp read to the second (3,152 forecasts
  read). Run 4821's 56 forecasts have no market read at all (0 snapshots, 0
  claims). Every close is a read taken before the start and after its forecast
  (the items 1-4 measurer).
* **LAW 3, not broken.** The 55 restated recommendations still carry the old
  closer's close = price at 0.00c, the account beside them. The four re-grades
  and the nine correction labels are companion rows whose arithmetic holds (the
  compiler for the re-grades, the gate measurer for the labels). Each
  abandoned row was ended by the one write the ledger allows and keeps an empty
  ending. On 111 of 111 recommendations the stored number is the raw claim's
  (the measurer). No row was found changed.

### Questions under the queue rule (each makes a gate count false)

**G1 — QUESTION. The UFC Fight Night outlook counts two fought cards as still
to come, and says a gate can clear that cannot.**

* **Rows:** UFC moneyline, rounds and distance, Fight Night, statistical (table
  A). Each reads "39 of 100 · ~121 expected · season ends 12-12", reachable.
* **The count is true:** 39 settled standing questions, the door and two
  recounts equal. **The count of cards still to come is not.**
  `horizon.slates_remaining` counts every week that holds a bout still marked
  'scheduled', whatever its date, and gives 6 Fight Night slates. Two were
  fought: Noche UFC on 12 September (13 of 14 bouts final; bout 401913546
  still 'scheduled') and UFC Fight Night on 26 September (12 of 13 final; bout
  401923433). Four cards remain: 10, 17 and 31 October and 7 November.
* **The arithmetic:** this season's pace is 41 questions over 3 cards, 13.67 a
  card (`horizon.market_outlook` on the copy). 39 + 13.67 × 6 = ~121, as the
  page says; on the four cards still to come, 39 + 13.67 × 4 = ~94, under the
  100, so by the page's own rule the line should read "THIS GATE CANNOT CLEAR
  THIS SEASON".
* **Why it is first:** the outlook is one of question 14's three counts that
  state a gate distance, and the number of cards it multiplies by is false.
  The Numbered card has a stale bout too (401905377, UFC 331, 19 September), but
  no forecast on it and so no outlook. The same cause in MLB (FOLLOWUPS F8)
  changes no verdict.
* How got: `compiler\c05_ufc.py` (the scheduled bouts by card and week, and
  their slates' statuses).

**G2 — QUESTION. UFC's tier table, ranker, taken record and blind edge figure
count the three cards as one.**

* **The rule:** question 14, "Every count on the Record page that states a gate
  distance is rebuilt per forecaster (per tier for UFC)"; its three commits did
  not reach these four. `calibration.tier_table` (through `bucket_record`),
  `ranker_comparison`, `taken_comparison` and `edge` call `calibration.resolved`
  with no card. R2 of 2026-09-03 splits UFC by card because one curve over the
  cards "would average those and describe neither".
* **Tier table**, UFC moneyline, statistical, bands 50-60 / 60-70 / 70-80 /
  80+: the page shows 28 / 15 / 4 / 2. By card (`calibration.resolved` with the
  card, on the copy): Fight Night 22 / 14 / 2 / 1, Contender Series 6 / 1 / 2 /
  1, Numbered card 0 / 0 / 0 / 0. The page's "Closest to a verdict: SOLID -- 5
  more settled" is 6 more on Fight Night and 19 more on Contender Series.
* **Ranker:** "49 settled on the shortlist and 0 off it" in each of moneyline,
  rounds and distance; by card 39 / 0, 10 / 0, 0 / 0.
* **Taken record:** "passed over 49 of 100" in each market; by card 39, 10, 0.
* **Edge figure:** "0 of the 100 disagreements"; 0 on each card, so the number
  holds, but it is one count over three.
* **The board:** `shortlist.settled_for_gate(ufc, moneyline, statistical)`
  gives 49 on the copy, the badge and the sizing words ("49 of 100 settled in
  this market").
* **Precedent for asking:** FOLLOWUPS ("Where the line went, one bet per
  forecaster", question 14's second step, OPEN) put the correction gates'
  pooled count to the operator as "a count on the Record page stating a gate
  distance, outside the three commits the ruling names", and he ruled it
  (question 16). No card reaches 100 either way, so the size stays a flat
  unit; the counts themselves are what is false.

**G3 — QUESTION, under one of two readings. Eighteen UFC final passes written
2-3 seconds after their card's start stand as written before it.**

* **The rows:** predictions 1014-1031, six Fight Night bouts on 5 September,
  each in moneyline, rounds and distance; the model's final passes, all
  settled, none withdrawn, written 19:00:02Z-19:00:03Z on a card whose start is
  stored as `2026-09-05T19:00Z`.
* **Why:** UFC stores its starts to the minute (the 398 UFC forecasts' games,
  17 characters each) and every other sport to the second. The standing rule
  compares the stored text, and ':' sorts before 'Z', so 19:00:03Z reads as
  before 19:00Z.
* **Reading A** (the stored minute is the start): the page is right.
  **Reading B** (the start is 19:00:00Z, as written): the 18 were written after
  it and their early passes (520-537, written 4 September) stand. No blind,
  priced, drift or correction count moves (Fight Night moneyline statistical is
  39 either way, the compiler's own recount), but the ranker's split does: each
  of the 18 led the slate and none of its early passes did
  (`prediction_ranks`), so UFC moneyline, rounds and distance go from "49 on
  the shortlist and 0 off it" to 43 and 6 each.
* It is the operator's reading ("Who reads a law"). Since item 2's release no
  forecast has been written after its start, read either way. Not LAW 1 (no
  line is involved) and not LAW 3 (no row changes).
* How got: `compiler\c04_starts.py`, `c07_g3_ranker.py`.

### For FOLLOWUPS

* **F1. The at-the-line edge figure's gate counts one direction.**
  `calibration.at_the_line_edge` counts only claims where the model is more
  than 0.05 higher than the venue on the home side or the over, although its
  own words say "Both directions, always". MLB spread, statistical: "1 of 100",
  against 66 the other way and the ledger's 67 either way; NFL spread 8 against
  the ledger's 13; NCAAF spread 8 against 38 (table I). It is in the payload
  only; the page does not draw it, so no painted count is false today. It
  would be the day it is painted. (The gate measurer.)
* **F2. The at-the-line curve has no bucket for a claim under 50%.** Claims are
  stated for the home side or the over and the buckets start at 50%, so MLB
  spread statistical's 102 settled claims are all in no bucket, and the curve
  would say "Nothing has resolved yet" beside its "past the 100". Also NFL
  spread 6 of 14, MLB moneyline 20 of 107 and 47 of 108, NCAAF spread 35 of 45,
  among others (notes in table G). The curve is not painted; its gate line and
  outlook are. (The gate measurer; not recounted here.)
* **F3. Baseball's last near-start firing left the game out** (item 1, above):
  14 of the 19 measured MLB closes are the read 35 minutes out. The close is
  still the last read taken, so no count is false; the price it closes on is
  earlier than the ruling means. Baseball's season is over; the same shape
  would bind any sport whose feed marks a game under way before it starts.
* **F4. The venue's silence of 24 September was recorded 'ok'.** 17 of 17
  firings that asked got 0 prices; 10 of the 12 unmeasured closes. The payload
  keeps only the count of quotes, so "the venue did not answer" and "the venue
  had nothing" look the same on the record.
* **F5. A predict or final run keeps no list of the questions it skipped.** Run
  4252 (predict NCAAF, 26 Sep 16:00:01Z, 'ok', 320 forecasts) did not forecast
  11 of the slate's 65 games, all starting at 16:00:00Z, one second before it
  (a correct refusal, said nowhere); two more games got a moneyline and total
  but no spread, with no reason recorded. Its sibling row 4251, the same
  second, says "missed ... NOT being forecast now" of the same slate.
* **F6. Run 4821 stopped mid-slate and nothing priced what it wrote.** It wrote
  56 of the 27 September MLB slate's 81 forecasts (3008-3063, 05:44:39Z to
  05:46:34Z; run 4827 wrote the other 25, and no question was written twice,
  the measurer), and those 56 have 0
  market snapshots, 0 claims and 0 recommendations. Why it stopped is not on
  the record, and the Task Scheduler's history log is switched off (the
  measurer). A forecast carries no run id, so this is attributed by time.
* **F7. MLB's scheduled tasks record slate 179 'missed' twice a day** since the
  season ended: 6 rows since 27 Sep 21:30Z (5510, 5831, 6395, 6547, 6869, 7430).
  Noise in the ledger, not a failure.
* **F8. Games left 'scheduled' after they were played.** `mlb_823490` (NYY-BAL,
  27 Sep 17:05Z) adds one slate to every MLB outlook ("260 of 100 · ~272
  expected"; at the line ~111, ~117, ~118) and turns none between reachable and
  cannot clear. 12 UFC forecasts (8 on bout 401913546, 4 on 401923433) cannot
  settle while their bouts stay 'scheduled'; none is withdrawn. (`mlb_746577`,
  a 2024 game, is 'scheduled' too and counts in no 2026 outlook.) G1 has the
  same cause.
* **F9. Two documents say what the record no longer counts.**
  `docs/READINESS.md`'s last section (question 12, 27 September) still says
  recs 45 and 46 count zero in every measurement, with no dated note that
  question 22 reversed it on 28 September; the page follows question 22 (45 in
  the model's MLB total line, 46 in the reasoning pass's). And item 1's
  close-out and READINESS state MLB total's restated closes over both
  forecasters ("MLB total 8 ... and 6 unmeasured"): per forecaster they are the
  reasoning pass's 8 with a later read and 5 without, and the model's 0 and 1
  (rec 45). Neither is in any count.
* **F10. The corrections payload still carries each fit's stored status words
  from before the key,** counting forecasts: NFL moneyline reasoning pass
  "29 so far" where the key count is 16; NFL spread reasoning pass 23 against
  13. Not painted; the page reads the key. (The gate measurer.)
* **F11. The tier table's pace would pool the whole sport.**
  `calibration._closest_verdict` takes its pace from every market and both
  forecasters (NFL 190 settled over 6 days, MLB 512, UFC 120 over 3). Latent:
  every sport has under seven days of settlements, so every table says "pace
  unknown". (The gate measurer.)
* **F12. The venue's own drift pair is never painted,** and two are past their
  50 (MLB moneyline reasoning pass 57, MLB spread statistical 56). Its
  `recounted` field counts the claims read, not the pairs; the gate measurer's
  own recount of the pairs matches on 26 of 26.
* **F13. Four catch-up rows from 23 September (1978, 1982, 1985, 1988) stay
  'running' for a year** under their task's literal silence of 8,760 hours
  (already in FOLLOWUPS). Predict NFL run 1981 falls due to be marked abandoned
  on 2 Oct 06:36Z.
* **F14. WakeToRun has never been exercised:** 0 timer wakes and 0.00 hours
  asleep since item 7. The one stretch not awake was a power-off, which
  WakeToRun cannot help.
* **F15. "A UFC closing line would pool cards"** (FOLLOWUPS, open, "For the
  re-read"): no UFC recommendation has been written, so both forecasters' UFC
  lines are 0 and nothing is pooled yet. It stays open.

### Notes, not defects

* Item 3 has had nothing to act on: the only correction ever in force was in a
  market coverage never prices, and no recommendation was written while it
  stood.
* Item 4's fixed bar has not yet had to refuse anything the old bar passed: 0
  of the 143 claims priced by the 9 predict and final runs since the fix (the
  measurer).
* The 11 measured closes at the price paid are later reads of their own
  contract that did not move. Rec 108's closing read is identical to a read
  30 minutes before it (not its pricing read): a quiet market and a replayed
  answer cannot be told apart on the record, and the rule accepts it.
* Recs 56-66 were written on 24 September before item 1 reached master; recs
  97-101 on 26 September before items 3 and 4 (the measurer). READINESS says
  so for the first group.
* The NCAAF wrong-side display of rec 111 is already before the operator
  (REPAIR_STATE, 29 Sep 16:10Z). Its stored row is consistent with its side
  (the items 1-4 measurer); the display was not measured again here.
* The copy is the record "at about 19:10Z": its newest task row started
  19:10:31Z, 31 seconds after the clock was held.

---

## 4. How the three measurers were checked

**Where two said the same thing differently, or a verdict did not follow from
its evidence, the compiler measured that point on the copy:**

1. **Item 1's verdict.** The items 1-4 measurer wrote TOOK EFFECT with its own
   finding beside it that baseball's last firing left games out. The ruling's
   first words are "reads every open recommendation on every run inside its
   window until the game starts". Re-measured: nine firings asked for fewer
   recommendations than were open, the 14 left out all baseball games within 5
   minutes of their listed start, each closed on the read 35 minutes out; NFL
   12 of 12 and NCAAF 7 of 8 closed on the last firing. The verdict is
   **PARTLY**.
2. **Item 2's verdict** rested on the ruling's second half only. Re-measured the
   first: the four reverted fits are active and wrote 155 of 155 statistical
   forecasts since. The revert **TOOK EFFECT**; the failure by name still
   **CANNOT BE SEEN YET**.
3. **Stale 'scheduled' games, read two ways.** The items 5-8 measurer called
   the MLB game's phantom slate "an extrapolation line, not a gate count"; the
   gate measurer called the UFC case "THE GATE COUNT IS FALSE". Re-measured:
   both come from `slates_remaining` counting any week with a 'scheduled'
   game. In MLB it adds one slate and changes no verdict; in UFC Fight Night it
   counts 6 cards for 4 and turns "cannot clear" into "reachable". The settled
   count, 39, is true in both measurers' words; the count of cards to come is
   false. G1 is a question; the MLB case is FOLLOWUPS (F8).
4. **"0 forecasts written at or after their start"** (items 1-4) was compared as
   text. Re-measured with every stamp read to the second: still 0 since item
   2's release; across the whole record 24 (6 MLB early passes, all withdrawn,
   and G3's 18) where the text comparison finds 6.
5. **G2's "not in FOLLOWUPS".** Searched again: FOLLOWUPS holds the precedent
   that counts outside question 14's three commits are the operator's, and an
   open item, "A UFC closing line would pool cards ... For the re-read" (F15).
   G2 stands, and the precedent is why it is a question.
6. **The same figure stated two ways:** the model's MLB closing line has "25
   unmeasured" (items 5-8) and "23 closed with no later read" (items 1-4, the
   gates). Both are right: 25 is the forecaster's block, 23 its point-spread
   line, and the other 2 are its MLB total line (recs 45 and 81)
   (`calibration.clv_report`, re-run).
7. **Run 4821's window:** the items 5-8 measurer gave 05:44:37Z-05:47:48Z, the
   run's own window; the 56 rows themselves are stamped 05:44:39Z-05:46:34Z.
   The count, 56 of 81, agrees.

Everywhere else two measurers stated one figure, they agreed: the closing line
per forecaster (all three), and every at-the-line curve, ledger, coverage
line, venue pair and edge count (items 5-8 and the gates).

**Spot-checks, each on the copy with the compiler's own scripts
(`compiler\c01` to `c11`):**

| measurer | figure | as stated | on the copy | how |
|---|---|---|---|---|
| items 1-4 | recommendations, closed, open | 111, 106, 5 (62, 63, 64, 66, 111) | same | SQL |
| items 1-4 | the repaired closer's closes | 51: 39 measured, 12 unmeasured (56-61, 67, 79-83) | same | `recommendation_closes`, restated = 0 |
| items 1-4 | the 51 by market and forecaster | 18/10, 11/1, 8/0, 1/0, 1/0, 0/1 | same | joined to each forecast |
| items 1-4 | restated closes | 55 (recs 1-55): 23/18, 8/5, 0/1 | same | restated = 1 |
| items 1-4 | closes citing their own pricing read | 0 | 0 | quote ids |
| items 1-4 | measured closes at the price paid | 11 (71 ... 105) | same 11 | the account's value |
| items 1-4 | MLB measured closes about 35 minutes out | 14 of 19 | 14 of 19 (13 at 35, 1 at 34) | `minutes_before_start` |
| items 1-4 | 24 Sep firings that asked the venue | 17, 0 prices | same; first prices 25 Sep 19:35:01Z | `task_runs` payloads |
| items 1-4 | the correction pair on every recommendation | empty on 111 of 111; 102-111 after the fix | same | SQL |
| items 1-4 | fit 71 | in force 28 Sep 13:00:01Z; withdrawn 29 Sep 09:12:46Z | same | `calibration_corrections`, `correction_activations` |
| items 1-4 | the four labels | 3, 10, 26, 56; 3.34% ... 7.77% | same; selection [3, 10, 26, 56] | `recommend.let_through_by_the_yes_price` |
| items 1-4 | recommendations since item 4 clearing on cost | 10 of 10, lowest 8.38% | same | `recommend.clears_the_bar(side=)` |
| items 1-4 | `MarketNotTrained` rows | 0 | 0 | SQL |
| items 1-4 | the newest activation | 24 Sep 13:00:01Z, fits 88, 71, 44, 35 | same | `fit_activations` |
| items 1-4 | run 4252 | 54 of 65 games; 11 at 16:00:00Z; 2 without a spread; 320 written | same | SQL |
| items 1-4 | the closing line per forecaster | NFL 11 and 1; MLB 15 and 1; NCAAF 8; NBA, UFC 0 | same | `calibration.clv_report` |
| items 5-8 | recommendations since item 5 on a held game and market | 0 of 10 | 0 of 10 | SQL, at each write time |
| items 5-8 | older pairs | 18 game-markets, 36 rows, newest 25 Sep 21:33:01Z | same | SQL |
| items 5-8 | the payloads' recommendation blocks | 17 runs: 10, 0, 2, 0, 119, 0 | same | `task_runs` payloads |
| items 5-8 | the two refusals | 2977 (run 4492), 3147 (run 6261) | same | payloads |
| items 5-8 | runs since item 7 | 2,878: 778 / 2,093 / 6 / 1 / 0 failed | same | SQL |
| items 5-8 | runs on 26 Sep before it | 1,041: 897 / 141 / 1 / 2 failed | same | SQL |
| items 5-8 | abandoned rows | 9; run 4821 at 28 Sep 17:45:01Z | same | SQL |
| items 5-8 | rows still running | 5 | 5 (1978, 1981, 1982, 1985, 1988) | SQL |
| items 5-8 | rows carrying a closing-write entry | 0 of 7,482 | 0 of 7,482 | SQL |
| items 5-8 | refused reruns recorded noop | 8 (4826-7429) | same | SQL |
| items 5-8 | catch-up | 1 ok ever (4812) | same; 18 failed, 4 running | SQL |
| items 5-8 | run 4821 | 56 of 81; 0 snapshots, claims, recommendations | same | SQL |
| items 5-8 | repeats left out of the closing line | 17 ids | the same 17 | the compiler's own pairing |
| items 5-8 | the window and the kill criterion | 5 of 21 days; stopped nothing | same | `closing_line_window`, `coverage.stopped` |
| items 5-8 | awake since item 7 | 66.46 of 67.07 h, 99.1% | same | `tools/awake.py`, run again |
| items 5-8 | WakeToRun | 18 of 18 | 18 of 18 | `Get-ScheduledTask`, read again |
| gates | 11 blind curves | MLB moneyline 260 and 148, spread 202, total 213; NCAAF spread 185 and 58; NFL spread 42, moneyline reasoning 16; UFC Fight Night 39, Contender 10, Fight Night rounds reasoning 14 | 11 of 11 equal | the compiler's own recount, no door |
| gates | 6 at-the-line curves and their 6 ledgers | 102/67, 107/56, 108/75, 45/38, 14/13, 46/33 | 12 of 12 equal | the compiler's own recount, no door |
| gates | media drift | MLB moneyline 52, NCAAF spread 78, NCAAF moneyline 49 | same | `drift.report` |
| gates | correction counts | MLB moneyline 260, UFC moneyline 49, NFL spread 42 | same | `correction.settled_rows`, `bet.count` |
| gates | ranker | MLB moneyline 98 / 151; UFC moneyline 49 / 0 | same | `ranker_comparison` |
| gates | edge figure | NCAAF spread 98 of 100 | same | `calibration.edge` |
| gates | priced | MLB moneyline 105 and 94 | same | `priced.forecast.standing_forecasts` |
| gates | UFC tier bands | 28 / 15 / 4 / 2; by card 22/14/2/1, 6/1/2/1, 0 | same | `tier_table`, `resolved` by card |
| gates | closing-line lines and the window | 16 lines, 5 windows | same | `clv_report`, `closing_line_window` |
| gates | G1's calendar | 6 Fight Night slates, 2 fought; 41 over 3 cards; ~121 | same | `slates_remaining`, `market_outlook` |
| gates | G3's rows and split | 18 rows; 49/0 to 43/6 | same | stamps parsed; `prediction_ranks` |

---

## What the re-read did not do

* **The edge question, by ruling.** No curve's score, mean closing line, share
  that beat the close, drift direction, ledger return or edge figure was read
  or stated. Whether the model has an edge was answered on 26 September
  (`docs/READINESS.md`) and is not re-measured. There is no paragraph here on
  which market is worth money.
* **READINESS's verdicts.** No criterion's verdict was re-read. Criterion 2's
  count is restated per forecaster (table T); criterion 3's count is the
  closing line (tables O and P) and criterion 4's the blind curves (table A);
  criteria 1, 5 and 6 were not measured.
* **What the record cannot show:**
  * why the venue returned nothing on 24 September;
  * a game's status at a past firing (the cause behind F3 is inferred);
  * why run 4821 stopped (the Task Scheduler's history log is off);
  * a correction reaching a pick, a run failing by name for want of a model, the
    closing-write guard acting, a timer waking the machine, a both-sides
    refusal, and a real no-side edge above 50c now clearing: none has happened
    on the record, so each is proved only by the gate's plantings, which were
    not run here.
* **The live record.** Only the copy was read; its verification against the
  record at 19:10Z is the orchestrator's.
* **The page itself.** The page's payloads were built on the copy and read
  (the gate measurer and the items 5-8 measurer); nothing was drawn in a
  browser, and the live app was not touched.
* **Fixed nothing, and did not commit.** Every finding above is recorded for
  the operator; the three questions wait for his ruling.
