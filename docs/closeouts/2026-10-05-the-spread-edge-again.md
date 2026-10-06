# Close-out -- THE SPREAD EDGE AGAIN (operator ruling A.5, 2026-10-05)

Against ruling A.5 of 5 October (`docs/briefs/2026-10-05-rulings.md`):
"After the void, re-run the 26 September edge comparison for spread markets
only (NFL, NCAAF, MLB spread), read-only, same method, reported beside the
old figures." The brief's reading: "the 26 September edge read's own method
... on the record as it stands after the void and the exclusion, spread
markets only, read-only, beside the old figures. It is a measurement asked
for by name, not the edge question re-opened."

**This is a measurement. It claims no edge and recommends no market.** No
figure below is an edge estimate under LAW 4 (none is past 100 resolved
disagreements but one, named in section 2, and that one points the other
way), and nothing here changes what the app does.

**A read, and it wrote nothing** to the record, to git or to the worktree
except this file.

## 1. How it was read

* **The record read** is ONE verified copy of the live record, made by
  `rebuild.verified_backup` into the scratchpad (`scratchpad\a5\record.db`):
  begun 2026-10-06T00:22:05Z, finished 00:22:57Z; integrity ok; every
  sqlite_master row byte for byte and every one of the 64 tables' row count
  and column checksums equal to the record at the instant copied. Every read
  of it went through `db.read_only(path, why)` (mode=ro, query_only); SQLite's
  quick check on it: ok. It held 4,442 forecasts, 127 recommendations, 2,829
  at-the-line claims, 53,684 venue quotes, 5,246 media-line snapshots and
  14,131 task runs; its newest task run started 00:21:01Z.
* **THE VOIDS ARE ON IT (the ruling's "after the void"; checked before
  anything was measured).** 51 `recommendation_voids` rows carry the reason
  "priced across two contracts, Q36", all stamped 2026-10-06T00:19:25Z: MLB
  run lines 6, 8, 11, 14, 16, 20, 25, 30, 32, 34, 38, 39, 40, 41, 42, 44, 48,
  50, 51, 53, 54, 55, 57, 59, 60, 79, 84, 85, 86, 87, 93, 94, 95, 96, 97, 98,
  100, 106, 107, 108, 109 (41); NFL spreads 68, 69, 70, 73, 75, 77, 78 (7);
  NCAAF spreads 88, 90, 91 (3). The other three of the 54, NFL 62, 63 and
  66, were withdrawn under ruling 1 on 24 September and left as they were;
  recs 114 and 115 are not voided (they wait for the operator's word).
* **The clock** was held at the copy's instant, 2026-10-06T00:22:05Z, in the
  process (`datetime.now`, `utcnow` and `date.today` answer it;
  `db.utcnow()` was checked to return it), so every figure is the record as
  of the copy.
* **The code** is the released tree: the worktree at `ec745dc`, which is
  master `e9d4cf5` (A.2 and Q37, serving) plus one commit of documents. The
  "before A.2" figures in section 4 ran `c829daa`, written out by
  `git archive` into the scratchpad (a read of the repository; its code is
  identical to `3508c7f`, the release before A.2). Python from the gridiron
  venv.
* **The 26 September figures** are those of `scratchpad\edge_read.py`, run
  2026-09-26 at about 06:53Z (its output, `edge_read.txt`, was written at
  06:53:15Z) through `db.read_the_live_record`, as recorded in
  `docs/READINESS.md`, "2026-09-26 -- the edge read".
* **Scripts and outputs**, all in `scratchpad\a5\`: `copy_record.py`
  (`copy.txt`), `edge_spreads.py` (the method; `edge_spreads.txt`, `.json`,
  and `edge_spreads_pre_a2.*` for the same on `c829daa`), `rule_check.py`
  (the old standing rule against today's), `venue_spreads.py` (section 4;
  `venue_now.*`, `venue_pre_a2.*`) and `venue_diff.py` (`venue_diff.*`).
* **Not done:** no pytest, `tools/verify.py` or `plant.py`; no git write; no
  network; no language-model call; `.env` not read (config looks for one in
  the tree it runs from, and neither tree holds one); the main checkout and
  the app on 8848 not touched. The live record was read once, by the backup
  door, to make the copy.
* **The copy was deleted** at 2026-10-06T00:29:56Z, with its -shm and -wal;
  no database file is left under `scratchpad\a5\`.

## 2. The 26 September comparison, re-run for spreads, beside the old figures

**The method, unchanged** (`edge_read.py`): per sport, market and forecaster,
never pooled, the graded rows `calibration.resolved` returns -- one standing
row per question, withdrawn forecasts left out -- that carry a market price
for the model's own side (`r.implied_prob`: the media line's first snapshot
of that forecast; nflverse's schedule line for the NFL, ESPN's DraftKings line
for NCAAF). On those rows, the Brier score of the model's probability for its
side and of the market's implied probability for the same side, and their
paired difference with a bootstrap 95% interval: 4,000 resamples of the rows,
the seed 20260926 set once before the loop, an interval drawn only for ten
rows or more, categories in the script's order (NFL statistical, NFL
reasoning pass, MLB statistical, NCAAF statistical, NCAAF reasoning pass).
Lower Brier is better; a positive difference is the market's score better.
Categories under 30 priced rows are not called findings. The one change: the
loop runs over the spread market of NFL, MLB and NCAAF only.

| spread market, forecaster | 26 Sep: graded / priced | 26 Sep: model / market | 26 Sep: model - market (95% interval) | now: graded / priced | now: model / market | now: model - market (95% interval) | read now |
|---|---|---|---|---|---|---|---|
| NCAAF, statistical | 132 / **131** | 0.1919 / 0.1731 | +0.0188 (-0.0093, +0.0470) | 239 / **237** | 0.2184 / 0.1883 | **+0.0301 (+0.0117, +0.0485)** | market's score better, and the interval is clear of zero: market ahead, beyond noise |
| NCAAF, reasoning pass | 5 / **5** | 0.2843 / 0.1738 | +0.1105 (no interval: under 10) | 112 / **111** | 0.2267 / 0.2055 | +0.0212 (-0.0061, +0.0490) | market's score better, within noise (the interval holds zero) |
| NFL, statistical | 30 / **30** | 0.2411 / 0.2393 | +0.0018 (-0.0363, +0.0357) | 57 / **57** | 0.2359 / 0.2419 | -0.0060 (-0.0383, +0.0242) | the model's score lower by 0.0060, within noise: the two cannot be told apart on 57 rows |
| NFL, reasoning pass | 1 / **1** | 0.3364 / 0.0465 | +0.2899 (no interval) | 28 / **28** | 0.2494 / 0.2376 | +0.0118 (-0.0748, +0.0847) | under 30 priced rows: not a finding |
| MLB run line, statistical | 175 / **0** | no price | no measurement | 202 / **0** | no price | no measurement | graded, with no price beside it |
| MLB run line, reasoning pass | none | | | none | | | the reasoning pass forecasts no run line |

**No category has the model's score better beyond noise**, on 26 September
or now.

**The MLB run line still has no price beside it.** 276 of its 308 forecasts
carry one media snapshot each, and all 276 are recorded with the source
"unavailable:no-free-line-source" and neither a line nor a price; the other
32 carry none. There is nothing to compare, and the regular season ended on
27 September.

**The interval is the 26 September bootstrap.** On the rows settled by the 26
September read, NFL statistical gives (-0.0363, +0.0357) again from a stream
seeded 20260926 -- exactly the old interval, because it was the first
category drawn on 26 September. Drawn again from a stream seeded for each
category alone, the intervals above move by at most 0.0055 (NFL reasoning
pass, 28 rows) and by 0.0009 or less elsewhere; NCAAF statistical's lower
bound is +0.0121 that way.

**The app's own LAW 4 edge count**, which `edge_read.py` printed beside the
table (`calibration.edge`: questions where the model was more confident in
its side than the market by more than 5 points, against the 100 needed): NFL
statistical 19 (13 on 26 September), NFL reasoning pass 12 (1), NCAAF
reasoning pass 69 (3) -- each short of 100, so no figure is drawn -- and
NCAAF statistical **119 (69)**, past the 100, so the app's figure renders
there. It reads against the model: in those 119 questions the model's side
came in 44.5% of the time, where the model had said 69.6% on average and the
market 52.0%; in the other direction (the market more confident by more than
5 points, 50 questions) the model's side came in 74.0%, where the model had
said 61.2% and the market 74.4%.

### The closing line (`calibration.clv_report`), the spread lines

| spread market, forecaster | 26 Sep (the report as it then was) | now |
|---|---|---|
| NFL, statistical | 0 measured; 1 closed with no later read | **6 of 50** priced against a close since 24 September; 1 more closed with no later read |
| NFL, reasoning pass | (one line for both forecasters) | **1 of 50** |
| NCAAF, statistical | 4 measured, mean +0.62c (both forecasters) | **11 of 50** |
| NCAAF, reasoning pass | (one line for both forecasters) | **2 of 50** |
| MLB run line, statistical | 9 measured, mean -0.17c, 3 of 9 beat the close; 28 with no later read; 23 restated | **3 of 50**; 12 more with no later read; 8 older closes restated; 5 repeats counted once, as the earlier one |

**No mean and no share can be set beside the old ones.** By ruling 8 (built
27 September) the closing line counts from 24 September and gives no mean
before 15 October; the report on the copy gives counts only, and that is
what it was asked. The 26 September means were read before that window
existed, from closes counted since 7 September, both forecasters on one line
(split by question 22 on 28 September) -- diagnostics far below the fifty,
as READINESS already says.

**What stands beside the lines now**, per forecaster for each sport (the
withdrawn and "priced across two contracts" lines are each one forecaster's
for the whole sport; every recommendation in them is a spread): NFL
statistical "11 withdrawn" (62, 63, 64, 66 under ruling 1; 68, 69, 70, 73,
75, 77, 78 by Q36) and "2 priced across two contracts" (114, 115); MLB
statistical "41 withdrawn" (Q36); NCAAF statistical "3 withdrawn" (Q36).

## 3. What moved, and why

**More settled games since 26 September, and nothing else.** Every movement
in the table above is new rows; no rule since the 26 September read moved a
row that was in it, and none moves a row since.

* **The rows settled since the read** (each forecast's own `resolved_utc`
  after 2026-09-26T06:53:15Z), by the day they settled:
  NCAAF 107 graded and 106 priced for each forecaster (26 Sep 10, 27 Sep 43,
  2 Oct 2, 3 Oct 18, 4 Oct 34 with 33 priced); NFL 27 for each forecaster
  (27 Sep 7, 28 Sep 4, 29 Sep 1, 2 Oct 1, 4 Oct 9, 5 Oct 5); MLB run line 27
  (26 Sep 5, 27 Sep 22), unpriced.
* **The old rows are as they were.** Today's code on the rows settled by the
  read gives NCAAF statistical 132 graded and 131 priced at 0.1919 / 0.1731,
  +0.0188; NFL statistical 30 / 30 at 0.2411 / 0.2393, +0.0018; NCAAF
  reasoning pass 5 / 5 and NFL reasoning pass 1 / 1 at the old figures; MLB
  175 / 0 -- every count and every Brier figure the 26 September read gave,
  to the fourth place.
* **The new rows, alone** (a split for this report, not the method; each
  interval drawn from a stream of its own, seeded 20260926): NCAAF
  statistical 106 priced, model 0.2512 against market 0.2070, +0.0441
  (+0.0218, +0.0681); NCAAF reasoning pass 106, 0.2240 against 0.2070, +0.0170
  (-0.0117, +0.0451); NFL statistical 27, 0.2302 against 0.2448, -0.0146
  (-0.0713, +0.0327); NFL reasoning pass 27, 0.2462 against 0.2447, +0.0015
  (-0.0831, +0.0731). So NCAAF statistical moves from "within noise" to
  "beyond noise" because the 106 college spreads settled since 26 September
  scored the market's line well ahead of the model, on top of 131 rows that
  had it ahead by less; and the reasoning pass's NCAAF category grows from 5
  rows to 111 because it answered 107 of the college spread questions settled
  since (the statistical model's count on each of the same days, and the same
  market score on them, 0.2070).
* **The standing rule (question 27, ruled 28 September, built 29
  September)** -- the final pass stands over an early pass written after it
  -- **moved no row here.** The 26 September rule, worked out again in Python
  (the latest row written at or before the start, compared as text, withdrawn
  rows left out), picks exactly the forecasts today's `calibration.resolved`
  picks, over every settled spread row on the copy: 57, 28, 202, 239 and 112
  rows, 0 different, and 0 different on the rows settled by the old read. So
  no settled spread question in these categories has an early pass written
  after its final pass. The same check covers question 35's instants
  (julianday and `<` against text and `<=`): no settled spread question's
  standing row depends on them.
* **The one key (question 17, ruled 27-28 September)** wrote once the key
  the standing clause already used for spreads -- forecaster, game, market,
  subject and rung -- and moved no spread row (the same check).
* **Voids.** Every spread forecast void written before the read was in
  force on 26 September (ruling 1's of 24 September: NFL spread 13, NCAAF
  spread 1; and one MLB run line of 23 September, a game recorded level). One
  spread forecast has been voided since: MLB game 823490's run line
  (statistical), on 27 September, a game recorded level; it was voided
  rather than settled, so it is graded in neither count.
* **THE Q36 RECOMMENDATION VOIDS DO NOT TOUCH THIS COMPARISON.** It reads
  forecasts, their games, the media line's snapshots and the forecast voids:
  `calibration.resolved` reads no recommendation, no recommendation void and
  no venue claim, so neither the 51 voids written at 00:19:25Z nor A.2's
  exclusion of the 275 two-contract claims can move it. Shown on the copy:
  the same script on `c829daa`, the code before A.2, gives every figure of
  the table in section 2 identically. Of the closing line, A.2 moved only NFL
  spread statistical, 8 to 6 (recs 114 and 115, priced across two contracts
  and not voided, which the measurement door now leaves out); the voided 51
  give the same counts on both trees, because a void already withdraws a
  recommendation from every count -- "nothing counted moves when the voids
  are written", as A.2's build said.

## 4. A SECOND, DIFFERENT COMPARISON: at the venue's line (not the 26 September method)

**What it is.** The same Brier comparison, but against the venue's price on
the venue's own contract: the at-the-line record's standing claims
(`at_the_line.standing_claims`, the record's one door -- one claim per
distinct bet per forecaster, the last before the start, a final pass's claim
first), settled; the model's number is its own distribution read at the
venue's line (the home side covering it), the market's is the venue's price
for that contract (Kalshi; the midpoint of bid and ask, or the last trade with
no two-sided quote), and the outcome is settled at that line. The same
bootstrap: 4,000 resamples, the seed 20260926 set once, the same order, an
interval for ten claims or more. It differs from section 2 in the price (the
venue's, not the media line), the line (the venue's rung nearest an even
chance, not always the question's), the instant (the last claim before the
start, not the first snapshot) and the questions (only those the venue was
read for). Run twice on the same copy and clock: by the released code, whose
door since A.2 leaves out every claim priced across two contracts, and by
`c829daa`, the code before A.2, which counts them. The page's own curve
(`calibration.at_the_line_curve`) gives the same n and both Brier figures on
each tree.

| spread market, forecaster | before A.2: settled claims | before A.2: model / venue | before A.2: model - venue (95%) | released: settled claims | released: model / venue | released: model - venue (95%) |
|---|---|---|---|---|---|---|
| NCAAF, statistical | **91** (of 92 standing) | 0.2443 / 0.2508 | -0.0065 (-0.0396, +0.0277) | **71** (of 72 standing) | 0.2669 / 0.2505 | +0.0164 (-0.0210, +0.0569) |
| NCAAF, reasoning pass | **7** | 0.2003 / 0.2538 | -0.0536 (no interval: under 10) | **7** | 0.2003 / 0.2538 | -0.0536 (no interval) |
| NFL, statistical | **29** (of 30 standing) | 0.2346 / 0.2490 | -0.0144 (-0.0784, +0.0565) | **23** (of 24 standing) | 0.2547 / 0.2477 | +0.0070 (-0.0602, +0.0841) |
| NFL, reasoning pass | **2** | 0.2834 / 0.2260 | +0.0574 (no interval) | **2** | 0.2834 / 0.2260 | +0.0574 (no interval) |
| MLB run line, statistical | **102** | 0.2085 / 0.2611 | **-0.0527 (-0.0813, -0.0227)** | **64** | 0.2232 / 0.2301 | -0.0069 (-0.0233, +0.0097) |
| MLB run line, reasoning pass | none | | | none | | |

Read by the same convention (under 30 is not a finding): on the released
code, NCAAF statistical (71) has the venue's score better and MLB statistical
(64) the model's, each within noise; NFL (23) and both reasoning-pass rows
are under 30. **Every one is short of the 100 an edge figure needs at the
venue's line.** The one standing claim not yet settled in each of NFL and
NCAAF is on a game not finished at the copy's instant (NFL: ATL at NO, which
started at 00:15Z).

### What the exclusion changed

| spread market, statistical | claims left out | all priced across two contracts? | written | bets gone | a bet standing on another claim | the left-out claims alone: model / venue |
|---|---|---|---|---|---|---|
| NCAAF | 20 | 20 of 20 | 25 Sep 19:35Z to 27 Sep 00:35Z | 20 | none | 0.1640 / 0.2517 |
| NFL | 6 | 6 of 6 | 27 Sep 16:35Z to 29 Sep 00:05Z | 6 | none | 0.1576 / 0.2540 |
| MLB run line | 39 | 39 of 39 | 7 Sep 21:30Z to 27 Sep 18:35Z | 38 | 1: forecast 1326 (MIA -1.5, game 823821) stands on its earlier claim 178, priced off one contract | 0.1826 / 0.3088 |

No reasoning-pass claim was priced across two contracts (all 275 are the
statistical model's), so the reasoning pass's rows are unchanged. Of the 275
stored spread claims priced across two contracts (NFL 96, MLB 139, NCAAF 40,
of 290, 293 and 413 stored spread claims), these 65 were the claim their bet
stood on before A.2; the others were not, then or now. The released door
holds none (checked through `at_the_line.across_two_contracts_among`).

**Why the before-A.2 MLB figure is not a measurement.** On each left-out
claim the model's number and the outcome are about the home side at -s, and
the price is about the away contract's line, +s: a price set beside a
question it did not price. Scored that way the "market" looks bad (0.3088 on
the 39 MLB claims), and that alone is what gave the before-A.2 MLB run line
the model's score lower by 0.0527 with an interval clear of zero. With the
39 left out it is -0.0069, within noise, on 64 claims (on the 63 kept claims
alone, 0.2245 against 0.2317). The same holds for NCAAF and NFL, whose signs
turn from the model's score lower to the venue's once their 20 and 6 are
left out. These are the figures A.2's build listed as moving at its release
(MLB 102 to 64, market and model 0.2611 / 0.2085 to 0.2301 / 0.2232; NFL 29
to 23; NCAAF 91 to 71), measured again here on a copy made after the voids,
unchanged.

## 5. Close-out

| part of the ruling | verdict | evidence |
|---|---|---|
| "After the void" -- the Q36 voids on the record | **DONE** (checked first) | 51 rows with the reason "priced across two contracts, Q36", stamped 2026-10-06T00:19:25Z; 62, 63, 66 withdrawn under ruling 1; 114, 115 waiting (section 1) |
| Re-run the 26 September comparison, spreads only, same method | **DONE** | `edge_spreads.py`: `edge_read.py`'s loop, bootstrap, seed and order on NFL, MLB and NCAAF spreads, both forecasters, on one verified copy, clock held (section 2) |
| Read-only | **DONE** | one verified copy through the backup door, read through `db.read_only`, deleted at 00:29:56Z; nothing written but this file |
| Reported beside the old figures | **DONE** | section 2's table, the closing line beside it |
| What moved and why | **DONE** | section 3: new settled games only; the standing rule, the key and the voids moved no row; the Q36 recommendation voids and A.2's exclusion cannot touch it, shown on both trees |
| The second comparison at the venue's line, released and before A.2, with the claims each rests on | **DONE** | section 4: 71 / 91, 23 / 29, 64 / 102 (statistical), 7 and 2 (reasoning pass), and every claim the exclusion took out |
