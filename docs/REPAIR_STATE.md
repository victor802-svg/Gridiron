# GRIDIRON_REPAIR — state for the next session

## START HERE (2026-09-27 ~02:40Z): the overnight queue is closed out

- **THE ORDER NOW (5 Oct, docs/briefs/2026-10-05-rulings.md; wins over
  every order below):** A -- the rest of Q36 (A.2: void the 54
  recommendations, "priced across two contracts, Q36"; recs 114 and 115
  listed for the operator's word; the stored two-contract claims left out
  of every price comparison by a dated rule; every moved number listed),
  then Q37 (headline the contract bought, the model's side beside it),
  then A.5 (the 26 Sep edge comparison re-run for spreads, read-only) ->
  C (the Props board) -> B (picks ranked by edge; a pick only at +3 points
  after fees; payout multiplier on every row; no filling; Kalshi game
  markets no badge or combo until their gate) -> the entry check steps 1-4
  (D's amendments) -> Q33 + Q34 -> Q25/Q26 -> Q5 -> Q10. DONE before this
  order: A.1 (4b1facb), A.3 and A.4 (48c4ddd), item 1 (e159be2), Q35
  (3508c7f). The queue rule: LAW 1, LAW 3, a false gate count, or a wrong
  number on a pick.
  **Q36 (ii) BUILT (2026-10-05, on c829daa; uncommitted for its prover;
  FOLLOWUPS "A claim priced across two contracts is in no price
  comparison; the 54 voided by rule"; CLAUDE.md row of that name):**
  MEASURED FIRST on one verified copy (made 15:25:58Z, deleted after): the
  rule (a claim's stored line is not the line its contract sells) selects
  275 claims -- MLB 139, NFL 96, NCAAF 40, all statistical, all settled,
  all written before Q36.1's release, none since -- and 56 recommendations
  priced from them, the 54 named and 114, 115. BUILT: a dated READ rule,
  nothing stored changed -- the at-the-line door (`at_the_line.
  on_one_contract`) and the measurement door (`recommend.
  priced_on_one_contract`, in `counted_once`) leave them out of the
  at-the-line record (curves, outlooks, edge, ledgers, coverage, the
  venue's drift pairs, the card's count), the closing line and all it
  feeds, the re-grade line and the empty bar; never one of a pair; the
  closing line names them in a row of its own; combos propose no such leg;
  the writer writes no recommendation from one; a guard inside each builder
  reads the stored claims its rows name (`calibration.
  ComparedAcrossTwoContracts`); the recounts work the rule out in Python;
  gate step 2's `audit.check_no_price_comparison_holds_a_claim_across_two_
  contracts`. THE READINGS (each the conservative default, FOLLOWUPS): the
  claims are left out, not the bets (ruling 1's void precedent; one MLB bet
  stands on an earlier claim); the rule is not bounded by the date; the
  closing line leaves out all 56 from the release, withdrawn or not. THE
  TOOL, `tools/void_two_contract_recommendations.py`, rehearsed on a
  scratch copy only: 51 written (the 54 less 62, 63 and 66, withdrawn under
  ruling 1, left and listed), 114 and 115 listed as waiting
  (`ON_THE_OPERATORS_WORD` empty), idempotent, `--live` refused on the
  copy. WHAT MOVES AT THE RELEASE (FOLLOWUPS has every figure): MLB spread
  at the venue's line 102 "past the 100" -> 64 of 100, NFL 29 -> 23, NCAAF
  91 -> 71; ledgers 67/25/70 -> 28/19/52; NCAAF's venue drift "47% over 59"
  -> 48 of 50, its direction withdrawn; the closing line's window line
  (statistical) MLB 15 -> 3, NFL 15 -> 6, NCAAF 14 -> 11; the empty bar
  NFL 7 of 10 -> 6 of 9, MLB +1 empty day. When the voids are written no
  count moves -- only which row names them. Four plantings escape on
  c829daa and are caught here; `plant.py` 413/413; 19 tests, each failing
  on c829daa; gate step 2's rows 112 of 114 on the copy (the two schema
  rows not run: no schema change); the suite 2,391 passed, 4 skipped. The
  copies deleted 16:32:55Z. **TO APPLY AFTER THE RELEASE:** the
  tool dry on the record (it must say "--write would void 51"), then
  `--write --live`. **Next: Q37, then A.5.**
  **Q36 (ii) PROVED (2026-10-05, its prover, alone in the worktree; one
  verified copy made 17:40:25Z, deleted after; FOLLOWUPS, "THE PROVER"; one
  local commit, "Q36 (ii): the 54 recommendations voided; ...", not
  pushed):** one defect found and fixed -- the
  rule's sentences (the coverage clause and hole, a withdrawal's reason, the
  closing line's row) said the claims were priced "before 30 September",
  false of run 8464's six written at 18:00-18:05Z that day and of recs 114
  and 115 priced from two of them, the very two the closing line's row
  names once the 54 are voided; they say "before the fix of 30 September"
  (`language.ACROSS_TWO_CONTRACTS_WHEN`), and `audit.two_contract_words_faults`
  (in the gate's A.2 check) holds each sentence's date to the record; a
  fifth planting, `plant_a_two_contract_sentence_dated_before_its_claims`,
  escapes on c829daa and on the change as first built and is caught here;
  one test more (20). Nothing else the ruling covers was found missed: the
  tool rehearsed on the copy wrote exactly 51 (the 54 less 62, 63, 66,
  listed), listed 114 and 115 as waiting, wrote nothing a second time and
  refused `--live` off the record; every NFL, NCAAF and MLB slate with a
  recommendation and every Record page built on the voided copy without a
  refusal. `plant.py` 414/414; step 2's rows 112 of 114 on the copy (the
  schema rows not run), the touched eight again on the voided copy; the
  suite 2,392 passed, 4 skipped on its one as-is rerun (the first run's one
  failure was the planting harness killed by its own 600-second limit, not
  a planting escaping). Found, not built (FOLLOWUPS; no queue): step A's
  own sentence "Priced across two contracts before 30 September" is false
  of the same six rows; MLB's run line labelled "point spread" on the
  Record page; and plant.py whole now runs at 527-600+ seconds against that
  600-second limit (the orphan scan's two plantings half of it) -- the
  release gate's step 1 can fail on the clock, which the one as-is rerun
  covers. **To apply after the release, unchanged:** the tool dry on the
  record ("--write would void 51"), then `--write --live`.

- **THE ORDER NOW (30 Sep, second, ~15:30Z; wins over every order below):**
  Q36.1 (the claim writer reads an away-side spread contract at +s, the
  sign the venue sells, from the release; a planting) -> step A (every
  number on a pick names the line it belongs to; rec 111 reads "North Texas
  +1.5") -> item 1 (the close window; its partial build kept on
  `item1-held`, 15:33Z) -> Q35 -> THE ENTRY CHECK
  (docs/briefs/2026-09-30-entry-check.md; steps 1-4, each its own gate and
  release; step 1 first) -> Q33 + Q34 -> Q25/Q26 (`q25-held`, `q26-held`)
  -> Q5 -> Q10.
  **Q36.1 released as 4b1facb (2026-09-30 18:44Z; gate 4/4, 397/397,
  first run; resumed after the session ended at ~15:59Z mid-build):**
  `at_the_line.home_view_line` is the one place a contract's line is read
  (a home contract at -s, an away one at +s, as the venue sells it);
  the claim writer, the near-start reader, the opening read and drift read
  through it; the gate checks it by fixtures of the venue's own contracts
  (`audit.check_every_venue_contract_is_read_at_the_line_it_sells`). All
  8,286 same-strike pair rows (6,177 distinct) now agree within the
  spread. From the release: no claim, recommendation, price, card or
  combo moves; MLB spread's venue drift 56 -> 36 pairs; 0 future MLB
  run-line claims refused (season over). Stored rows unchanged.
  **STEP A released as 48c4ddd (2026-09-30 22:43Z; gate 4/4, 401/401,
  first run):** every number on a pick names the contract it belongs to
  (`views._the_contract`, `views._as_the_page_draws`); rec 111 reads "North
  Texas +1.5 · 76% · 52¢ · 1.94x · $15" (the question's -6.5 and the
  model's 63% in the tooltip); rec 117 "Atlanta +2.5"; the opening read is
  the question's own rung or names the rung it is; a row priced across two
  contracts (the stored away-contract claims; Q36 (iii) not ruled -- the
  default) shows the model's own number and no price, payout, edge, size or
  outline, with "Priced across two contracts before 30 September; no single
  contract carries these numbers."; `audit.check_every_number_names_its_line`
  in step 2. NEW BEFORE Q36.1 SHIPPED: predict:nfl run 8464 (18:00-18:05Z)
  wrote six NFL week-4 claims off an away contract at -s (1749, 1752, 1755,
  1761, 1780, 1786); two became recommendations: rec 114 (PIT at CLE, 2 Oct
  00:15Z) and rec 115 (GB at TB) -- drawn unpriced; they join Q36 (ii)'s
  rows (now 275 claims, 56 recommendations). 69 of 117 past recommendations
  were drawn under another line's words while live (FOLLOWUPS, THE LIST).
  **Next: item 1's gate and release** (built fresh on the released code,
  `item1-held` read as a reference; proven and committed locally on
  2026-10-01 -- ITEM 1 below), then Q35.
  **ITEM 1 released as e159be2 (2026-10-01 01:37Z; gate 4/4, 405/405,
  first run; before 15 Oct):** every game with an open recommendation or a
  drift row is kept until its LISTED START INSTANT, whatever its status
  says; only MLB showed the 35-minute gap (14 of 19 measured closes,
  statsapi's warm-up 'Live'); NFL and NCAAF closes were already the last
  firing's read. The schedule is unchanged (the ruling names no lead): a
  :00/:30 start's last read is 25 minutes out; moving it is one installer
  line, the operator's call. Question 38 below.
  **Q35 released as 3508c7f (2026-10-01 07:01Z; gate 4/4, 409/409, first
  run; commits 3cb376e Q35, 3508c7f a UFC category counts its own card's
  voids -- the first of Q34's counts, done first because Q35's voids would
  otherwise have put false void counts on the Record page):** starts are
  stored to the second (`db.stored_start`) and compared as instants
  (`db.instant`; a gate scan names any text comparison of a start); every
  pass at or after its start is refused (`predict.PassAtOrAfterTheStart`).
  WHY THE UFC FINAL PASS RAN AT THE START: Gridiron-Final-UFC fired daily at
  12:00 local (19:00Z); the 5 Sep card's main bouts were listed '19:00Z' to
  the minute; ufc.next_slate and the question check compared starts as
  text (':' sorts below 'Z'), so the card read as still to come and 18 final
  passes were written at 19:00:02-03Z; 12:00 local was also never the
  declared three hours before the first bout. THE 18 VOIDED on the live
  record at 07:01:54Z by `tools/void_passes_written_at_the_start.py --write
  --live` (dry run first: exactly 1014-1031; MLB 105-110 already withdrawn,
  left); Q27's rule stands their early passes 520-537 (same
  probabilities); UFC ranker split 53/0 -> 47/6 per market; UFC settled
  378 -> 360 with '18 withdrawn'; Fight Night's void count 6, the other
  cards 0. THE SCHEDULE MOVED (07:02Z, the one task only, its action and
  settings unchanged): Gridiron-Final-UFC now a time trigger from 00:20 local
  every 30 minutes (as NearStart), writing only inside the 180 minutes
  before its card's first start still ahead (`tasks.final_pass_window`).
  **WEEKLY LIMIT, 2026-10-01 ~07:10Z:** the entry check's step-1 build
  (workflow wf_24b751de-849) stopped 37 seconds in on the weekly usage limit
  (reset 2026-10-05 15:00Z); it had changed nothing (the tree clean at
  65e0a32). Resumed at 2026-10-05 15:17Z from that run (no finished step
  existed to restart). Meanwhile the scheduled tasks ran on the released
  3508c7f; the weekly recalibration of 2026-10-05 13:00:01Z (run 13607)
  fitted 26 categories, 18 past 50 settled questions on the key, and wrote
  corrections 90-115, NONE in force and no activation row (Q32 as built;
  `correction_activations` still holds only fit 71's withdrawal).
  **Next: the entry check, step 1 (resumed).**
  **Q35 BUILT AND PROVEN (2026-10-01, on a9c5193; committed locally on
  `repair` by its prover, not pushed; next: its gate and release; FOLLOWUPS
  "A pass written at or after the start is not blind; a start is an
  instant"; CLAUDE.md, the LAW 1 row of that name and the ONE CLAUSE row):**
  MEASURED FIRST on one verified copy (made 01:40:24Z, deleted after): UFC's
  2,783 starts stored to the minute, the other sports' 21,527 to the second,
  every pass, read and run to the second; 67 text comparisons of a start in
  the shipped code and one schema rule; 24 forecasts written at or after
  their start by the instant -- the 18 (1014-1031, withdrawn by nothing) and
  MLB 105-110 (withdrawn 29 August) -- none at the start's own second. WHY
  THE FINAL PASS RAN AT THE START: `Gridiron-Final-UFC` (read read-only: a
  daily trigger from 2026-09-05 12:00 local, 19:00Z in summer, whatever card
  is next; its first firing was that day) began run 131 at 19:00:01Z, the
  minute the Paris card's main bouts were listed ("2026-09-05T19:00Z");
  `next_slate` and the question check compared that with the clock as text,
  so the card read as still to come, and the 18 were written 19:00:02-03Z.
  12:00 local was never the declared "three hours before the first bout":
  18 of 2025-2026's 103 cards start before it, 2 at it, and every other
  final pass of September landed 23 to 73 hours before its card. BUILT:
  every loader stores a start to the second (`db.stored_start`; the UFC
  mirror rewrites the record's 2,783 at the first UFC refresh after the
  release, the same instants -- rehearsed, only `kickoff_utc` moves); every
  comparison reads instants (`db.instant`; `julianday()` on both sides),
  the standing rule strictly before the start; a schema rule beside the
  close's text rule (through `db.init`, rehearsed: the one object, 0
  differences from a fresh build, no checksum moved); the writer refuses a
  pass at or after its start at its own stamp (`predict.PassAtOrAfterTheStart`);
  `final:ufc` fires by its declared 180-minute lead (`tasks.
  final_pass_window`); the gate's scan (`audit.check_every_start_is_compared_
  as_an_instant`, step 2) and the standing world to the minute; the void
  tool (`tools/void_passes_written_at_the_start.py`). NUMBERS (a9c5193
  against this tree on the copy): the UFC ranker split 53/0 -> 47/6 in each
  market (the re-read's 49/0 -> 43/6), nothing else counted moves -- the
  early passes carry the finals' probabilities exactly; after the voids, UFC
  378 -> 360 settled ("189-171, 18 withdrawn") and the figures beside it
  (FOLLOWUPS). Three plantings escape on a9c5193 and are caught here;
  `plant.py` 408/408; the suite 2,356 passed, 4 skipped; gate step 2's rows
  110 of 112 on the copy, the two schema rows 0 differences each (the copies
  deleted 03:33:11Z).
  **ITS PROVER (2026-10-01; one verified copy made 03:45:01Z, deleted
  04:21:46Z with its four scratch copies; FOLLOWUPS, THE PROVER):** the
  measurement and the report stand as built; no start is compared as text
  anywhere in the shipped code, and no path writes or stands a pass at or
  after its start. FIXED, each failing on the change as first built, with a
  test and a planting form: a start nobody can read (empty, or a feed's
  "TBD" kept as sent) put a final pass below an early one in the standing
  order (`julianday()` NULL), so the clause stood the early pass where the
  recount keeps the latest row -- the term is `IFNULL(..., 0)` (none on the
  record); and the gate's scan saw a start only bare and by its own name --
  it now follows one handed to a local or a loop, `str()` and string
  methods, a cut short of the day, a call that keeps it text (`COALESCE`,
  `IFNULL`, `datetime`, `substr`), brackets and a scalar subquery (nothing
  more on a9c5193 than the 67 and the rule; the tree clean). FOUND, NOT
  BUILT: the 5 September slate's payload labels the eighteen standing early
  passes "A later forecast stands in its place" (`views._superseded_ids`,
  question 30's FOLLOWUPS; drawn nowhere), voids or not. Rehearsed again on
  the copy: the void tool (24 listed, the 18 written once, `--live` refused
  on the copy), `db.init` (the one rule, appended, 0 differences both rows,
  no checksum moved), the mirror (2,783 UFC starts, the same instants);
  the numbers the same as the build's (11,041; 623; 0 for the voids alone on
  the released code). `plant.py` 408/408; step 2's rows 110 of 112 (the
  schema two in the rehearsal); the suite 2,358 passed, 4 skipped, none
  failed (04:23:27Z to 04:50:29Z).
  **TO APPLY AFTER THE RELEASE (the orchestrator):** (1) the 18 --
  `python tools/void_passes_written_at_the_start.py --database
  var/gridiron.db` (dry; it must list exactly 1014-1031), then the same with
  `--write --live`; (2) THE SCHEDULE -- re-register `Gridiron-Final-UFC` with
  the installer's Final-UFC trigger (every 30 minutes from 00:20 local;
  `tools/schedule_install.ps1`, dated 2026-10-01); until it is, the 12:00
  firing writes a final pass only for a card whose first start still ahead
  is within 180 minutes of it; (3) nothing else -- `db.init` adds the rule on
  the first open, and the first UFC refresh rewrites the starts. **FOR THE
  ORCHESTRATOR, FOUND:** the void count beside a UFC curve is the market's
  across every card (`calibration.curve` hands the card to `resolved`, not
  to `void_count`), so after (1) the Record page reads "6 withdrawn" beside
  the Contender Series and Numbered card curves of each UFC market --
  question 34's ground ("every UFC count is per card tier"); FOLLOWUPS has
  it and four more, none LAW 1, LAW 3 or a gate count.
  Q36 (ii) (the 269 stored claims and 54 recommendations:
  void, label or leave) and (iii) (what the page draws for a row priced off
  one) are not ruled: until they are, the stored rows stay as written and
  step A draws such a row WITHOUT a price and says why (the conservative
  default: no number is shown under a contract it does not belong to; the
  amended queue rule). Q37 not ruled.
  **ITEM 1, THE CLOSE WINDOW, BUILT (2026-09-30, fresh on 747a6c7) AND
  PROVEN (2026-10-01; committed locally on `repair` by its prover, not
  released; FOLLOWUPS "The close window" and its THE PROVER; CLAUDE.md THE
  CLOSE):** measured first on one verified copy (made 22:48:13Z, deleted
  23:28:18Z): NFL 12 of 12 and NCAAF 7 of 8 measured closes since item 1 are the
  last firing's read (10-30 minutes out, as the :05/:35 schedule gives;
  NCAAF 103's venue answer lacked its contract) -- NO 35-MINUTE GAP; MLB 5 of
  19, the 14 left out by nine firings, every one five minutes before its
  listed start (the selection kept 'scheduled'/'pre' only, and baseball's
  warm-up is statsapi 'Live' -> 'in'; inferred, the status history not
  kept). Built: `tasks._near_start_selection` reads every open
  recommendation and drift row until the listed START INSTANT (`db.instant`),
  whatever the status; the claim writer claims by the start instant alone;
  `close_of` and the closer compare instants (as text a start stored to the
  minute -- UFC's -- took a read 30 s after it as before it, and
  `_minutes_between` raised on it: latent, it would have stopped every
  near-start firing at the first UFC close); each firing's payload names
  every read while its game is marked under way. No close on the record
  moves (106 of 106 given again; the venue was not read at all for the 14 at
  the firing five minutes out). THE SCHEDULE IS NOT MOVED (the reading taken:
  the ruling names no lead, and the :05/:35 firings give a last read before
  every start -- 25 minutes before a :00/:30 start; one installer line if the
  operator wants it nearer, FOLLOWUPS). Three plantings escape on 747a6c7 and
  are caught here; `plant.py` 404/404; the suite 2326 passed, 4 skipped; gate
  step 2's rows 109/109 on the copy (the two schema rows not run).
  THE PROVER (its own verified copy, 23:59:56Z, deleted after): the gap
  table stands figure for figure (NFL and NCAAF: no 35-minute gap); 106 of
  106 closes given back. FOUND AND FIXED: one listed start `db.instant`
  cannot read (no zone, no time) on any game a drift row or open
  recommendation sits on stopped the whole pass on every firing (raised in
  the selection, before the closer; the claim writer, the closer and the
  noop count raised too, the count on an empty start as well) -- now not
  read, named on every firing (`near_start_unreadable_start`), held open by
  the closer, never claimed; a fourth planting
  (`plant_an_unreadable_start_that_stops_the_near_start_run`) escapes on
  747a6c7 and on the change as first built, caught here. Named, not built
  (FOLLOWUPS): college TBD placeholders (292 games still to start listed at
  midnight Eastern; Q35's ground), a UFC bout listed at its segment's start,
  the identical-read skip (latent since item 1), the media day cache; and,
  for the queue (with the orchestrator), a finished game's pick priced from
  an in-play claim if it really started before its listed start. SCHEDULE:
  none to apply. Four plantings escape on 747a6c7 and are caught here;
  `plant.py` 405/405; gate step 2's rows 109 of 111 on the copy (the two
  schema rows not run); the suite 2332 passed, 4 skipped.
  Releasable well before 15 October.
  **Q36.1 BUILT (2026-09-30, resumed 16:01Z after its first build agent was
  cut off; uncommitted for its prover; FOLLOWUPS "An away contract is read
  at the line it sells"):** `at_the_line.home_view_line` reads a venue
  contract's stored number as it is -- "<away> wins by over s" at the home
  side's +s -- and refuses a side it has no rule for; the claim writer (and
  the near-start reader through it), the opening read and drift's ladder
  matching read through it; a baseball run line off an away contract is the
  writer's `no_distribution` refusal (139 of 293 MLB run-line claims on the
  record; none from the release -- no MLB game is still to start). Nothing
  stored changes. The one page figure that moves: MLB spread's venue drift,
  56 pairs -> 36 ("36 of 50"). Gate by fixtures
  (`audit.check_every_venue_contract_is_read_at_the_line_it_sells`); two
  plantings, each escaping on 8662205 and caught here; the suite 2275
  passed, 4 skipped; `plant.py` 397/397. For the queue, not built: the
  Record page's MLB spread at-the-line comparison, past its gate, is
  flattered by the 39 away-contract claims (the market's Brier 0.2611 with
  them, 0.2317 without) -- Q36 (ii).
  **Q36.1 PROVED (2026-09-30, its prover, alone in the worktree; one local
  commit, "Q36.1: an away-side spread contract is read at the line the
  venue sells"; FOLLOWUPS, the same section, THE PROVER):** no reader on
  this tree turns an away contract at the wrong sign (every reader hunted:
  the storage, totals -- all "Over N ...", none shares the shape -- the
  closer, the packages, coverage, the board, the claim-line readers). On one
  verified copy (made 17:11:04Z, deleted 17:27:56Z): the 8,286 same-strike
  pair rows rise within the spread at the lines they sell (the builder's
  41.18 points and 32 on the released reading reproduced); the claim writer
  run dry in memory over every spread forecast and quote on the record
  writes no claim off an away contract at -s (the released writer: 363, and
  564 of the 567 stored spread claims given back exactly); gate step 2's
  rows 108 of 110 on the copy, none failing on the 269 (the two schema rows
  not run). Found and fixed: the gate blamed the one place for a storage
  flip (an away contract stored at -s), never naming `parse_markets`; it
  names the storage now -- a third planting form and two tests, each
  escaping or failing on the check as first built. Not built, for (ii):
  under this tree 31 of the 73 venue-drift pairs (MLB 15 of 36, NFL 5 of 11,
  NCAAF 11 of 26) set a stored away-contract claim's near price (+s) beside
  the home contract's open (-s) -- their movement spans two contracts (on
  8662205 those claims' disagreement did); no direction is shown under the
  50. `plant.py` 397/397; the suite 2277 passed, 4 skipped.
  **STEP A BUILT (2026-09-30, from 4422403; uncommitted for its prover;
  FOLLOWUPS "Every number on a pick names the line it belongs to"; CLAUDE.md
  row of the same name):** THE READING TAKEN (the conservative default, under
  the amended queue rule): a number on a pick is always shown under the words
  of the exact contract it belongs to -- its line and its side; where a
  recommendation was priced on the venue's contract at a line other than the
  question's, the pick names the VENUE's contract and says beside it, in
  plain words, what the model was asked and its own number for it; nothing
  pairs one line's words with another line's numbers; the side drawn is the
  one the page already drew (question 37 not touched). Built: one door for a
  pick's words (`views._the_contract`, with `language.at_the_contract`),
  read by the board's rows and tiles through the Today card, the Today card,
  the recommendation line, a combo's leg, the taken rail, the live figure and
  the opening read; the opening read asks the question's own contract and
  names the one it is where the ladder lists none; a row whose stored claim
  was priced across two contracts is drawn with none of its numbers and the
  sentence "Priced across two contracts before 30 September; no single
  contract carries these numbers." (the default of 15:30Z); the gate's
  `audit.check_every_number_names_its_line` (step 2, every sport's slate,
  both forecasters) reads the line off the record and off the drawn words.
  Rec 111 reads "North Texas +1.5 · 76% · 52c · 1.94x" (tooltip: "The model
  was asked about North Texas -6.5 and gives it 63%."). Measured on one
  verified copy (made 18:52:24Z): 69 of the 117 recommendations were drawn
  under another line's words while live (13 at the venue's rung, 56 across two
  contracts), 60 live pregame figures, 855 opening reads; 289 faults on
  4422403's 52 payloads, none here. Nothing stored changes; `record_for`
  writes what it wrote before. Three plantings, each escaping on 4422403 and
  caught here; `plant.py` 400/400; the suite 2292 passed, 4 skipped; gate
  step 2's rows 109/109 on the copy (the copy deleted 20:40:37Z).
  **FOUND BY STEP A'S MEASUREMENT, FOR THE OPERATOR (no question: the default
  of 15:30Z covers the page):** `predict:nfl` at 18:00-18:05Z (run 8464) ran
  the released code before Q36.1 was released at 18:44Z and wrote six NFL
  week-4 claims off an away contract at -s (claims 1749, 1752, 1755, 1761,
  1780, 1786), two of them recommended -- rec 114 (PIT at CLE, 2 October
  00:15Z) and rec 115 (GB at TB, 4 October), both drawn as clearing the bar
  on the release ("Pittsburgh -0.5 · 62% · 52c · $15") and unpriced with the
  sentence here. Question 36's "nothing upcoming carries one" no longer holds:
  (ii) now covers 275 claims and 56 recommendations. And question 37 has a
  game still to start: rec 117 (ATL at NO, 6 October) buys New Orleans -2.5
  while its row reads "Atlanta +2.5" with that contract's $15 and outline.
  **STEP A PROVED (2026-09-30, its prover, alone in the worktree; one local
  commit, "Every number on a pick names the line it belongs to"; FOLLOWUPS,
  the same section, THE PROVER):** on one verified copy of the record (made
  20:49:25-20:50:12Z, deleted after) every slate that carried a claim or an
  opening read and every sport's current slate, both forecasters, were drawn
  three ways -- as the record holds them, every game read as still to start
  (each priced row the record ever held, as before its start: 135 priced
  blocks, 47 recommendation lines, 32 combo legs, 158 opening reads, 111 rows
  across two contracts) and every finished game read as being played -- and
  the early passes; neither the gate's check nor one written apart from it,
  which holds each number's VALUE to the contract its words name, finds a
  number under another contract's words (on 4422403: 710 and 531). Found and
  fixed, each on the step as first built: (1) A FINISHED GAME'S CARD IS STILL
  PRICED, and its card in CLEARS named the claim's contract with the claim's
  chance but the QUESTION's figure and verdict -- "New York covers +6.5 · 30c
  · the model had this at 67% and it happened", New York not having covered
  +6.5 (12 cards, 3 with the other verdict; payload): now the chance the card
  shows and its claim's settled verdict; (2) THE FORECAST'S OWN SENTENCES
  beside words moved to the claim's line -- the Today card's numbers line and
  why heading (14 questions; payload) and a live row's reasons tooltip (12;
  drawn) -- now name the question they are about ("The model was asked about
  New York +15.5 and gives it 67%. ..."); (3) A ROW PRICED ACROSS TWO
  CONTRACTS left its payout slot empty, which a tile draws "not recorded"
  (recs 114 and 115): it says "not shown"; (4) THE CHECK demanded the
  sentence of a live tile drawing the question's own figure with no Today
  card (the other forecaster's, or off the shortlist) -- 196 on the finished
  slates read as live; the gate would have failed step 2 during PIT at CLE
  (2 October 00:15Z) and five more NFL week-4 games -- and read an opening
  read against the first of a ticker written twice in one look; both
  mended. THE READING, UNCHANGED: the sentence travels with the figure a
  claim priced across two contracts would have given (the Today card's), as
  step A drew it on an upcoming row; a tile that never drew the claim's
  numbers draws the question's own and needs none. One planting
  (`plant_the_questions_own_numbers_under_the_contracts_words`) and a form in
  the across planting, each escaping on 4422403 and on the step as first
  built; six tests, each failing on the step as first built. FOR THE
  OPERATOR, NO QUESTION (the words are true of their numbers): a pick drawn
  at the venue's contract before its start settles, on the board, at its
  question's -- rec 111 reads "North Texas +1.5 · 76% · $15" now and, once
  finished, "North Texas -6.5 · the model had this at 63% ..." (the finished
  row is the forecast graded on its question; the claim's own verdict is on
  the Today card, payload only; a taken pick's My day chip moves with it) --
  a companion to question 37; nothing on the record is taken. `plant.py`
  401/401; the suite 2298 passed, 4 skipped; gate step 2's rows 109/109 on
  the copy (the copy deleted 21:58:18Z). **Next: release step A (gate,
  merge, restart), then item 1.**

- **THE ORDER NOW (30 Sep, docs/briefs/2026-09-30-rulings.md; wins over
  every order below):** the NCAAF wrong-side fix (rec 111; own commit and
  gate; released before 2026-10-02T01:00Z) -> item 1, the close window (the
  near-start run keeps every game until its start; measure NFL/NCAAF
  first; released before 2026-10-15) -> Q35 (starts as instants; the 18
  voided; the final pass's schedule moved before the start) -> Q33 + Q34
  (UFC outlook on cards still to come; every UFC count per card) -> Q25/Q26
  released as planned (`q25-held` 3c36861, `q26-held` 72c90bd, set aside
  2026-09-30 03:33Z; `repair` returned to bd90dc3) -> Q5 -> Q10.
  **QUEUE RULE AMENDED:** anything that could show the operator a wrong
  number on a pick (side, price, probability, size) joins the queue first,
  display or not.
  **THE WRONG-SIDE FIX released as fa4c8eb (2026-09-30 07:55Z; gate 4/4,
  387/387, first run; before the 2 Oct 01:00Z deadline):** one place,
  `subjects.SIDES` / `side_taken()`, reads every stored side ('fail to
  cover' is the no side beside 'not_cover'); the words, the resolvers, the
  lines module and the page all ask it; the page and the gate
  (`audit.board_price_side_faults`, `audit.check_every_side_is_placed`)
  refuse a side they cannot place (`UnplaceableSide`, the API answers 500).
  THE LIST (FOLLOWUPS, "The side is placed in one place ... THE LIST"):
  recs 88, 90, 104, 111 were drawn with the other side's chance and price
  (88: 43% 48.5¢ for 57% 51.5¢, WON; 90: 20% for 80%, LOST; 104: 27% for 73%,
  LOST; 111: 24% 48.5¢ for 76% 51.5¢, not settled); and, found by the fix,
  THE LIVE ROWS' PREGAME FIGURE showed the proposition's chance on the
  other side from 2026-09-09 (fb6dcdf): 116 live cards on 13 slates, 57 of
  them recommendations (recs 25-31, 33-40, 44, 46-59, 67, 70-72, 74-80, 82,
  83, 88, 90, 92-97, 104, 106-110; e.g. rec 67 showed 80% for 20%); the
  opening read of forecasts 2503, 2917, 2923, 3148; three NCAAF combos (not
  repaired here: pick-number finding 1). None was taken.
  **PICK-NUMBER FINDINGS JOIN THE QUEUE FIRST (the amended rule; found by
  the fix's builder and prover, verified on the record):** (A) a priced
  spread row names the QUESTION's line but draws the VENUE contract's
  numbers at another line -- rec 111 was priced on claim line -1.5 ("Tulsa
  by more than 1.5"), so the pick is North Texas +1.5 at about 76% and
  50.5-51.5¢, yet the row reads "North Texas -6.5" (North Texas -6.5 is the
  UNT7 contract at about 29¢; the model's own number for it is 62.6%); 262
  of 274 NFL/NCAAF spread claims are rung-differs; the opening read is the
  venue's main rung, not the question's; (B) combos worth the product of
  each leg's yes-side number, legs named on the other side; (C) My day's
  chip, the payout and the recommendation line on the proposition's side.
  Built in that order, A first, released before 2 Oct 01:00Z; the reading
  (a number is always shown under the words of the contract it belongs to)
  is recorded in docs/briefs/2026-09-30-rulings.md's successor note here.
  **STEP A STOPPED for question 36** (the venue's away-side spread contracts
  read at the wrong sign: 269 claims, 54 recommendations priced across two
  contracts); nothing of A is built. **STEP C released as 8109f1f
  (2026-09-30 11:27Z; gate 4/4, 392/392, first run):** My day's chip wears
  the picked side's club; the Today card's payout and the payout floor are
  the side bought's; each recommendation line names the side it buys in its
  own words (no "the yes side / the other side"); the Results table said
  "<club> to win" beside a "lose" pick's number on 403 of 3,434 rows (every
  release so far) -- now "to lose", held by a gate row; the edge figure,
  the better side's, is labelled "on the other side" where it is (10 cards,
  NBA 3166 upcoming); `audit.check_every_pick_names_its_side` in step 2.
  Question 37 below.
  **STEP B released as 2330954 (2026-09-30 14:38Z; gate 4/4, 395/395,
  first run):** a proposed combo is worth the product of its legs'
  probabilities on their picked sides, its ceiling and singles line on
  those sides at their costs, each leg named on its picked side and with its
  game (`language.combo_leg_words`); `audit.check_every_combo_is_its_picked_
  sides` in step 2. 34 of 35 proposals on the record were drawn at the
  yes sides' product (e.g. NCAAF "Rutgers -24.5 + Navy -6.5" 2% -> "Howard
  +24.5 + Navy -6.5" 71.1%; NFL week 3 17.9% -> 66.3%; NBA today 32.2% ->
  37.9%); FOLLOWUPS has every one. LAW 5's combo clause unchanged. **Next:
  item 1 (the close window)**; step A when Q36 is ruled.
  **STEP A STOPPED on question 36** (the away contracts' sign). **STEP C
  BUILT (2026-09-30, uncommitted for its prover; FOLLOWUPS "Every pick
  names its own side"):** the Today card's payout and payout words are
  what the side its question names pays (finding 3); each recommendation
  line names the side it buys, in that side's words, with that side's
  number and cost -- never "the yes side / the other side" (finding 4);
  My day's chip wears the club its pick's words name (finding 6); and from
  the sweep, the payout floor folds by what the side bought pays, and a
  moneyline "lose" with no opponent is said "PHI to lose". Gate:
  `audit.check_every_pick_names_its_side` (step 2); three plantings. ITS
  SWEEP STOPPED ON ONE ITEM, **question 37** below: a recommendation that
  buys the OTHER side of its question's words (16 on the record) is drawn
  on the board and the Today card with its size, edge and outline under
  the model's own side's words; which contract such a row headlines is not
  settled by the rulings.
  **STEP C PROVED (2026-09-30, its prover, alone in the worktree; one local
  commit, "My day, the payout and the recommendation line name the picked
  side"; FOLLOWUPS "Every pick names its own side", THE PROVER):** the
  three findings and the sweep's two fixes hold on a verified copy of the
  record (0 faults on this tree's 50 payloads, 909 on 401d059's), and the
  prover found two more and fixed them: (1) THE RESULTS TABLE drew a
  moneyline "lose" as "KC to win" beside the lose pick's number, market
  figure and verdict -- 403 rows on the record, every sport, on every
  release (a history row carries no opponent); the sweep's "said as asked"
  fix mends it ("KC to lose"), which its builder had recorded as moving
  nothing drawn, and a check now holds it (gate step 2 reads each sport's
  latest 500 rows); (2) THE EDGE'S SIDE: a watched card whose edge figure is
  the other side's was labelled as the question's own when neither side
  clears the fee (10 cards on the record; NBA 3166 upcoming, "San Antonio
  to win" -1.5c where its own is -2.5c), and the board's tile drew the
  figure bare -- the engine names the figure's side (`edge_cents_side`),
  the card says "on the other side", and so does a moneyline or total tile;
  a spread tile keeps its bare figure for step A. Five plantings, each
  escaping on 401d059 and caught here. Question 37 stays open (its edge
  part is narrower now: see its prover's note).
  **STEP B BUILT (2026-09-30, uncommitted for its prover; FOLLOWUPS "A combo
  is worth the product of its picked sides"):** a proposed combo is worth
  the product of each leg's number on the side its recommendation buys
  (`combos.leg_on_its_side`: one minus the proposition's number, at the rest
  of the dollar, on the no side), its ceiling and singles line are those
  sides' at those costs, and each leg is named in the words of the side it
  buys (`views._the_side_bought`, the recommendation line's). On one
  verified copy (made 11:31Z, deleted 12:24Z): 34 of 35 proposals' worths,
  ceilings and singles lines moved -- "Rutgers covers -24.5 + Navy covers
  -6.5" 2% -> "Howard covers +24.5 + Navy covers -6.5" 71.1%; the model's
  MLB run-line combos 8.7-19.5% -> 34.5-49.5%; NBA's two on today's board
  32.2% -> 37.9% and 23.0% -> 27.0%; NFL week 3's three 12-18% -> 63-73% --
  and 8 proposals' words. Gate: `audit.check_every_combo_is_its_picked_sides`
  (step 2; 259 faults on 8318650's payloads, none here); two plantings,
  each escaping on 8318650 and caught here; `plant.py` 394/394; the suite
  2256 passed, 4 skipped. LAW 5's combo clause unchanged. NOT HERE: the line of a spread leg's
  numbers (12 legs in 7 proposals rung-differs, 37 in 22 off an away
  contract: finding 2 and question 36, step A).
  **STEP B PROVED (2026-09-30, its prover, alone in the worktree; one local
  commit, "A combo is worth the product of its picked sides, each leg named
  on its picked side"; FOLLOWUPS, the same section, THE PROVER):** the
  builder's figures hold on a fresh verified copy (made 12:53:33Z, deleted
  after): 259 faults on 8318650's 44 payloads, none on the build; every
  leg's worth less its cost and fee is its line's edge. The prover found one
  more and fixed it: A LEG NAMED NO GAME -- the card draws its legs and
  nothing around them, so three of the reasoning pass's baseball combos read
  "under 8.5 total runs + under 8.5 total runs" (MLB 165, 166 twice), ten
  total legs named no game and seven baseball legs a city two clubs share
  ("Chicago covers +1.5"); each leg is now its side's words and the game as
  the board heads its row, "under 8.5 total runs · Rays at Braves"
  (`language.combo_leg_words`), drawn one to a line with the plus in the
  muted ink; the check names a leg without its game (324 faults on
  8318650, 80 on the build as first written, none here); a third planting,
  `plant_a_combo_leg_that_names_no_game`; `plant.py` 395/395; the suite
  2258 passed, 4 skipped; gate step 2's touched rows 38/38 on the copy
  (the copy deleted 13:30:11Z). Read on the render and named for
  step A: every leg on NFL's current slate is a venue contract's number at
  another line than its words' ("Chicago covers -15.5" at 86% is Chicago
  -3.5's; its own is 42%). **Next: step A when Q36 is ruled.**

- **THE ORDER NOW (29 Sep, second set, ~05:40Z;
  docs/briefs/2026-09-29-rulings-second-set.md; wins over every order
  below):** **Q32** (corrections activate through the model fits' gate:
  written inactive; activation its own dated append-only row, only when the
  holdout bootstrap interval of the Brier improvement, on distinct bets by
  the key per forecaster, excludes zero; a tie to the uncorrected
  probability; the recalibration never activates; fit 71 withdrawn by a
  dated row, then the new gate run on it read-only and its interval
  reported -- activated by a new row if it passes) -> Q27 (its partial
  build kept on `q27-held`, 80108c1) -> board merge -> re-read -> Q25 + Q26
  + Q29 -> Q5 -> Q10. Q32 released before 5 Oct 13:00Z. First step done
  read-only: no forecast or recommendation carries fit 71 or any
  correction; no MLB pass can apply it (regular season over, loader reads
  `gameType=R` only, no unstarted MLB game on the record).
  **Q32 released as c5dbd3b (2026-09-29 09:12Z; gate 4/4, 360/360, first
  run):** every correction row is written inactive (a rule refuses
  `active_from` on a new row); the append-only `correction_activations`
  (measured / withdrawn / scratch, 15 rules) is the only way into force;
  a measured row carries the bootstrap interval of the Brier improvement on
  distinct bets (seed 20260923, 1000 resamples, pinned) and is refused
  unless its lower bound is above zero; the door reads these rows alone;
  the recalibration fits and never activates (its docstring says so);
  `tools/correction_holdout.py` measures and activates or withdraws.
  **FIT 71:** withdrawn at 2026-09-29T09:12:46Z by a dated row, reason as
  ruled ("activated under the pre-Q32 rule: single holdout comparison,
  pooled rows"); then measured read-only under the new gate on the live
  record: 260 distinct questions, refit on the earliest 208 and scored on
  the latest 52, Brier raw 0.247471 against corrected 0.247620 (improvement
  -0.000149), paired bootstrap 95% interval [-0.015132, +0.016931] --
  **DOES NOT PASS: a tie, the uncorrected probability stands; no activation
  written, fit 71 stays withdrawn.** The door serves nothing in any
  category.
  **Q27 released as 06145b1 (2026-09-29 11:55Z; gate 4/4, 362/362, first
  run; commits 2eda91a and 06145b1, FOLLOWUPS' moved-number list made
  complete):** `calibration.standing_pass_order` -- a final pass written
  before the start stands, else the latest written -- is the one order the
  standing clause, the at-the-line window, the card, the recounts and the
  correction measurement read (`audit.check_the_final_pass_stands` probes
  nine doors); no run writes an early pass for a question whose final pass
  exists (`predict.final_pass_written`, checked before the write and before
  a paid reasoning call; a run left with nothing is `SlateAlreadyAnswered`,
  a noop, and each skip is named). THE SIXTEEN RE-SCORED (all NFL week-3
  totals, reasoning pass, each stating the over, so no hit changed): the
  final pass now stands for all 16; better on 3, worse on 4, the same on 9;
  summed Brier 3.8652 -> 3.8840, log loss 10.8204 -> 10.8581; the NFL total
  reasoning-pass curve (n 17) Brier 0.2409 -> 0.2420, log loss 0.6750 ->
  0.6772. EVERY MOVED NUMBER (FOLLOWUPS, "The standing pass is chosen by
  pass", corrected by the numbers step; `scratchpad\q27\numbers\moves.md`):
  those, the week-3 over-time point, 8 standing claims at the venue's line
  (NFL total PHI-CHI; six MLB spreads, one price moves; MLB moneyline ATL),
  the at-the-line figures for NFL total reasoning pass (n 1) and MLB spread's
  market Brier 0.2613 -> 0.2611, slate forecaster counts (NFL week 3
  reasoning 72 -> 45, NFL week 1 statistical 128 -> 101, NCAAF 5 Sep 250 ->
  243: a question under two factor sets counted once per set), NYG-LA's band
  claimed 0.5118 -> 0.5106, the Today panel's "Settled"/"Watching" 38 -> 42.
  No gate count moved.
  **THE BOARD MERGED AND RELEASED as cb8c7da (2026-09-29 19:09Z; gate
  4/4, 384/384, first run; commits 3148f39 the merge, 4df9153 the
  player_numbers brief, cb8c7da the fixes before it shipped).** By the
  checklist (docs/briefs/2026-09-27-board-merge.md): STEP 1, the failing
  order (whole smoke, then whole cards) on board a63463a: 3 of 3 green;
  again on the merged tree 3 of 3, and after the fixes 3 of 3. STEP 2: 12
  conflict hunks, each resolved to repair's behaviour (listed in the merge
  commit's message and FOLLOWUPS) -- the closing line per forecaster from
  the window with nothing drawn before 15 Oct, counts on Q17's key, the
  prompt disclosure moved onto reasoning tiles, the board's panels
  arriving by opacity only; Q18 (an open row stays open across any
  redraw, tested both ways) and Q19 (plain headings, versions only in a
  tooltip) built; 17 board defects found and fixed on the way (pooled
  counts, a taken prop counted twice, a pre-window chart, moving arrivals,
  a write-time standing rule, an upsert); ELAPSED_TIME_HELD 28/44 -> 19/27.
  STEP 3: 63 captures at 1300 and 390 from a verified copy of the record
  (served by the test server, never the live app); 33 differences from the
  fixture captures, every one in FOLLOWUPS ("The board merge, step 3");
  three tap targets under the rule fixed before release (the first-load
  controls are not drawn until they can act; the calendar's days 44/50px
  whole; a live row's head whole), each with a test. THE player_numbers
  RULING (2026-09-29): described as a loaded roster, refreshed each load,
  not append-only, display only; `audit.check_the_roster_numbers_are_
  display_only` refuses its name anywhere but the loader, the schema and
  the jersey drawing (never the prediction closure or any measuring
  module), four plantings. STEP 4: master cb8c7da, pushed, restarted,
  `/api/health` = cb8c7da0be16; the record gained `player_numbers` (268
  objects); the old Picks, Live and Today routes are gone.
  **OPEN FOR THE OPERATOR (reported 2026-09-29 16:10Z, not built, the queue
  rule): the NCAAF wrong-side display** -- rec 111 (UNT at TLSA, kickoff
  2026-10-02T01:00Z, a sized flat unit, stored correctly: side 'no' on
  "TLSA covers +6.5") is shown as "North Texas -6.5 · 24% · 48¢", the
  other side's numbers (about 76% and 51.5¢ for North Texas -6.5); 93
  NCAAF spread forecasts store `model_side` 'fail to cover' where every
  other sport stores 'not_cover', `priced.shape.blind_probability` has no
  rule for it, and the page and `audit.board_price_side_faults` turn only
  on `is False`. The released Today card had the same display. A fix waits
  for "fix it". **THE RE-READ, done 2026-09-29 (19:10Z copy; report
  docs/closeouts/2026-09-29-the-re-read.md; three measurers and a compiler):**
  item 1 PARTLY (the close rule holds on every close -- 106 of 106
  accounted, 0 priced against their own read -- but 14 of 19 measured MLB
  closes are the read 35 minutes out, the firing 5 minutes before the start
  leaving the game out); item 2 TOOK EFFECT for the revert, its failure by
  name CANNOT BE SEEN YET (no run has met an untrained market); item 3
  CANNOT BE SEEN YET (no correction was ever in force at a recommendation's
  stamp); items 4, 5, 6, 8 TOOK EFFECT; item 7 TOOK EFFECT for the noop, the
  sweep (9 hung rows abandoned, 4821 among them) and WakeToRun (18 of 18),
  awake 66.46 of 67.07 hours since its fix (99.1%). Every gate distance
  restated: 354 figures, 19 records, five sports; 343 counts each equal a
  recount made without any door. Three findings make a gate count false:
  questions 33-35 (all UFC). The edge question was not re-measured.
  **Next: Q25 + Q26 + Q29** (then Q5, Q10; the Record page's "market
  ahead" and the pick'em decision, queued after the re-read on 27 Sep, are
  not placed in the later orders and wait at the end).

- **RULINGS OF 29 SEP (docs/briefs/2026-09-29-rulings.md):** Q31 (i)(B) and
  (ii)(B): label every fitted row written before Q16's release that is
  short on the key -- 33, 59, 61, 63, 81, 85, 86, 87, 89 -- and no
  placeholder. Q30 to FOLLOWUPS (queue rule). Q27's and Q29's readings
  confirmed. If Serve stops again unexplained, read the Windows event log
  around it before anything else. Order unchanged: Q16 -> Q27 -> board
  merge -> re-read -> Q25 + Q26 + Q29 -> Q5 -> Q10.
  **FIT 71: HOW IT CAME INTO FORCE (read-only report, 2026-09-29 ~02:30Z; the
  ruling of 29 Sep; nothing about fit 71 changed).**
  - **The process:** the weekly scheduled task `Gridiron-Recalibrate` (task run
    6173, `recalibrate`, started and finished 2026-09-28T13:00:01Z, result ok,
    "fitted 26 categories; 18 had at least 50 settled"; payload: 1 activated),
    running the released main checkout (724a72d at that instant; master's
    reflog: 724a72d from 04:51Z, f0a4418 from 20:42Z). `tasks._run_recalibrate`
    calls `correction.refit_all`, which calls `correction.record_fit`, the one
    writer of `calibration_corrections` (no other shipped caller; the
    plantings call it on scratch worlds).
  - **THE WEEKLY RECALIBRATION ACTIVATES A CORRECTION WITHOUT AN OPERATOR
    RULING.** `refit_all` fits every category past `MIN_TRAIN` (50 settled) and,
    when `holdout_check` passes, writes the row with `active_from` = the run's
    own instant. Nothing else is asked: no ruling, no separate activation row,
    no incumbent. `_run_recalibrate`'s own docstring says "Writes versions;
    activates nothing" -- it is wrong. The model fits' activation gate (ruled
    2026-09-24: `fit_activations`, a dated measured row, the bootstrap
    interval of the log-loss difference excluding zero) does NOT bind
    corrections; they are a separate table with their own rule.
  - **ITS HOLDOUT HAS NO INTERVAL.** `holdout_check`: fit on the earliest 80%
    of the category's settled rows (time-ordered), score on the latest 20%;
    pass when there are at least 40 held-out rows (`HOLDOUT_MIN`) and the
    corrected Brier beats the raw one by more than 0.005 (`HOLDOUT_MIN_GAIN`),
    a point comparison. Fit 71: 364 settled (`n_train`), 73 held out, Brier
    0.250413 raw to 0.245211 corrected, a gain of 0.005202 -- past the 0.005
    bar by 0.0002. No interval was computed or stored. (The constant's own
    comment measured 2 of 60 false activations at this margin on 200-row
    synthetic categories.)
  - **THE DATED ROW:** `calibration_corrections` id 71: MLB, moneyline,
    statistical, version 8, fitted 2026-09-28T13:00:01Z, slope 1.00658,
    intercept -0.23354, train Brier 0.250636 -> 0.247286, holdout 73 rows
    0.250413 -> 0.245211, `active_from` 2026-09-28T13:00:01Z, status "active -
    the correction scored better on the most recent rows, which it was not
    fitted on (73 rows held out)". It is the only row ever active (71 of 89).
    `active_from` is written once, at the insert; `calibration_corrections_no_
    update` refuses any edit.
  - **WHAT IT HAS TOUCHED:** nothing yet -- 0 forecasts and 0 recommendations
    carry a correction version. From its instant, `recommend.for_predictions`
    prices a new MLB moneyline statistical pick from the corrected probability
    (repair item 3), and the card's model chip shows it.
- **THE ORDER NOW (28 Sep, second set, ~21:10Z;
  docs/briefs/2026-09-28-rulings-second-set.md; wins over every order
  below):** Q17 (building) -> Q16 -> Q27 (the standing pass chosen by pass:
  a final pass before the start stands, else the latest early pass -- a read
  rule, no row changes, the 16 NFL totals re-scored and every moved number
  listed; and no early pass for a question whose final pass exists, a
  `SlateAlreadyAnswered` noop; own commit, planting) -> the board merge ->
  the re-read -> Q25 + Q26 + Q29 (Q29 folded into Q25's scan: code writing
  `sqlite_sequence`, and a multi-row insert under OR FAIL / OR IGNORE / OR
  ROLLBACK on an append-only table) -> Q5 -> Q10. Q20 with Q28 confirmed
  released (724a72d, 04:51Z; master f0a4418 contains it).
  **IF THE WEEKLY LIMIT STOPS WORK:** record here where it stopped, resume
  from there at the reset, and never restart a finished step (a workflow
  resumes from its run id; a finished agent replays from cache).
  **Observed 21:11:54Z:** `/api/health` did not answer; the Serve task's
  repeat trigger started it again at 21:12:01Z (f0a4418). Cause not found
  (no step of this session stopped it); watch for a repeat.
  **Q17 (with Q21, Q22) released as 00b66d3 (2026-09-29 01:32Z; gate 4/4,
  344/344, first run; commits c57354c the one key and the four gate
  records, 1949730 the recommendation counts per forecaster, 00b66d3 a fix
  before release).** `gridiron/bet.py` holds the key once: forecaster,
  game, market, subject (which names a prop's player and type), the rung
  asked; every count door and its recount read it. THE FIX: the key as
  first built also compared `prop_type`, so eight NFL week-one props
  written without one (fs1, 29 Aug 05:55Z) and their fs2 re-asks
  (9/68, 18/76, 23/91, 24/92, 27/95, 29/102, 33/66, 41/104) counted as two
  questions -- 193 NFL values moved that no ruling named (the factor table,
  "scored over 154" -> 162, the pick-card worst-band footnote, a pace
  figure); the numbers step caught it, the key dropped the column, and all
  193 are back at their released values. EVERY RELEASED NUMBER THAT MOVED
  (scratchpad `q17fix\numbers\moves.md`, and FOLLOWUPS): at the venue's
  line, coverage per question (NCAAF spread 46 of 142 games -> 46 of 187
  questions; NFL spread 14/29 -> 14/42; NFL total 1/17 -> 1/18; MLB total
  25/202 -> 25/213 and reasoning 25/133 -> 25/141; 16 lines' wording only);
  where the line went (NCAAF spread 22% over 65 -> 28% over 78 questions,
  gate row 65 -> 78 pairs; NFL spread 10 -> 11 of 50; venue pairs MLB
  spread 55 -> 56, NFL spread 12 -> 11 of 50); the closing line per
  forecaster (MLB "since the repair" 16 -> 15 and 1; "Both sides, no
  position" gone, 45 in the model's total line and 46 in the reasoning
  pass's; "Would not have cleared" 2 the model's; NFL 12 -> 11 and 1 at
  00:52Z; counted once MLB 66 -> 57 and 11); empty_bar per forecaster. The
  kill criterion stops nothing either way; no mean painted before 15
  October. Question 30 below.
  **Q16 (with Q23 and Q31) released as 428e1cb (2026-09-29 04:59Z; gate
  4/4, 350/350, first run; commits 108c431 Q16, 36d539e the 29 Sep brief,
  fit 71's report and CLAUDE.md's words on how a correction comes into
  force, 428e1cb the nine):** every correction gate counts distinct bets on
  the key per forecaster -- the page's line, the learning panel, the
  version report and the fit's own gate from the release (training rows
  unchanged); the append-only `correction_gate_labels` and its rules; the
  door passes over a labelled fit. THE LABELS, written 04:59:27Z by
  `tools/label_corrections_below_the_gate.py --write --live` in one
  transaction after a dry run through the read-only door selected exactly
  the ruled nine: 33 (MLB total, reasoning pass, v1: 76 forecasts, 48 on the
  key), 59, 61, 63 (UFC distance, moneyline, rounds, statistical, v3: 56,
  32), 81 (NFL spread, statistical, v3: 60, 41), 85, 87, 89 (UFC,
  statistical, v4: 85, 49), 86 (UFC moneyline, reasoning pass, v4: 63, 49);
  no placeholder; fit 71 still the one in force. Page before/after in
  FOLLOWUPS (e.g. NFL spread, statistical "60, cleared" -> 41 of 50; UFC
  statistical "85, cleared" -> 49 of 50). The next weekly refit (5 Oct
  13:00Z) gates on the key. **The queue rule now binds** (after Q16: a new
  finding joins the queue only if it breaks LAW 1 or LAW 3 or makes a gate
  count false). **Next: Q27.**

- **THE ORDER NOW (rulings of 28 Sep, docs/briefs/2026-09-28-rulings.md;
  wins over every order below):** Q20 with Q28 (A: one shared test helper
  waiting in the page for the test's own redraw) -> Q24 (recommendations'
  above-the-mark hole, Q15's basis, own commit + planting) -> Q27
  measurement (read-only; report first; a pass written after its start is
  voided under the existing rule) -> Q17 (key: forecaster + game, market,
  subject, the rung asked; Q22 A: recommendation counts per forecaster, the
  "Both sides" row goes; every released number that moves, listed) -> Q16
  (Q23 A: page count and the fit's own gate on the key for fits from the
  release; existing fits short of the gate labelled "fitted below its
  gate", never activated) -> Q25 (the scan refuses rules switched off by a
  connection setting and a function under a built-in's name) + Q26 (the
  five tables: rules or true words; mlb_people's words and the register;
  one commit) -> the board merge -> Q5 -> Q10 -> the re-read (not before
  2026-09-28T15:00Z). **Queue rule after Q16:** a new finding joins the
  queue only if it breaks LAW 1 or LAW 3 or makes a gate count false;
  everything else goes to FOLLOWUPS for the re-read.
  **Done 28 Sep:** the scratchpad's rehearsal and measurement copies of the
  record deleted (~00:40Z): 58 copies and 74 files SQLite kept beside them,
  132 files, 61.05 GB freed (C: 131.9 -> 193.0 GB free); the list is
  `deleted_2026-09-28.tsv` in the session's scratchpad; nothing in var\ and
  not the live record touched. **Q20 with Q28 released as 724a72d (04:51Z;
  gate 4/4, 338/338, first run):** the Today panel arrives by its fade
  alone; the per-frame check failed 10/10 on f66fefa and passes; one shared
  helper, `tests/conftest.py::wait_for_the_redraw_it_starts`, armed around
  each affected test's own redraw (nine tests in test_smoke.py,
  test_prompt_disclosure's Why test, and test_cards' card test, found by
  shape); the race copy lost 0/60 with it and 33/60 without;
  ELAPSED_TIME_HELD unchanged (28 functions / 44 waits). The helper's one
  precondition (a redraw asked for before arming) is Q5's to close.
  **Q24 released as f0a4418 (20:42Z; gate 4/4, 339/339, first run; its
  prover was cut off by the weekly usage limit at ~11:10Z and resumed at
  19:18Z):** `recommendations_never_moved_above_the_mark` refuses an update
  moving a recommendation above every number given out (by id, rowid, oid,
  _rowid_, every conflict clause); the live record gained it on its first
  open (242 objects; recommendations 1-111 unchanged). Question 29 below
  (ways round the number rules that need a statement no writer makes).
  **Q27, THE MEASUREMENT (read-only, 20:43Z; ruled: report before changing
  anything else):** all 16 are NFL week-3 reasoning-pass totals (fs2). For
  every one the EARLY pass stands (written 24 Sep 05:32-05:36Z by
  predict:nfl run 2336) over the FINAL pass (written 23 Sep 19:30-19:31Z by
  final:nfl run 2052), both at the same rung; **no pass of any of the 16 was
  written after its game's start** (kickoffs 25 Sep 00:15Z to 29 Sep
  00:15Z), so the void rule writes nothing. Early (standing) / final ids:
  2227/1999 ATL-GB, 2232/2009 CAR-CLE, 2237/2015 CIN-PIT, 2242/2021 HOU-IND,
  2247/2027 KC-MIA, 2250/2033 LAC-BUF, 2253/2039 NE-JAX, 2258/2045 NYJ-DET,
  2263/2051 SEA-WAS, 2268/2057 TEN-NYG, 2273/2063 ARI-SF, 2278/2068 MIN-TB,
  2283/2070 BAL-DAL, 2286/2072 LV-NO, 2291/2074 LA-DEN, 2296/2076 PHI-CHI
  (the last unsettled). Nothing changed; whether a final pass should stand
  over a later early one stays the operator's (question 27). Output:
  scratchpad `q27_measure.txt`. **Next: Q17.**

- **THE ORDER NOW (third set, 2026-09-27 ~15:50Z;
  docs/briefs/2026-09-27-rulings-third-set.md; wins over every order
  below):** Q15 (predictions never replaced, own commit + planting; then
  one gate scan refusing INSERT OR REPLACE / REPLACE / ON CONFLICT DO
  UPDATE against every append-only table, legitimate upserts in a register
  that only shrinks; a read-only measurement of whether any live
  prediction was replaced) -> Q20 (A: the Today panel arrives by fade
  alone; per-frame whole-pixel check + planting; test_motion's
  `transform` line changes) -> Q17 (one distinct-bet function: forecaster +
  the venue's question (game, market, line); every released number that
  moves, listed) -> Q16 (B, on Q17's key, planting each) -> the board merge
  (checklist with the third set's additions; Q18 and Q19 are fixed in the
  board) -> Q5 -> Q10 -> the re-read (not before 2026-09-28T15:00Z).
  **Serving 68b215e** (Q14). Gate reruns: one as-is; a second failure of
  the same test is diagnosed before any third run.
  **Done 27 Sep (third set):** Q15 released as 70ad888 (22:00Z; commits
  22e182d, the predictions rules, and 70ad888, the scan; gate 4/4, 337/337,
  on its one as-is rerun -- the first run failed only
  `test_nothing_moves_under_reduced_motion`, Q5's race). The live record
  gained the three rules on its first open (241 objects; predictions 3140,
  numbered 1-3140, sequence 3140). THE MEASUREMENT (read-only, a verified
  copy at ~20:40Z and the door at 20:54Z): **no live prediction shows
  evidence of having been replaced** -- no hole in the numbers, the sequence
  at the max, stamps rising with the numbers, every row equal to its
  fingerprint and to the 765-row baseline, every row unchanged across 12
  earlier copies back to 8 September, no child citing a missing forecast or
  stamped before one. What a replacement could have left no trace of: rows
  1-765 rewritten under their own number before the fingerprint backfill (5
  Sep 11:04Z), a rewrite to identical content, or a forecast and its
  fingerprint replaced together (`prediction_fingerprints` has no replace
  rule). Found alongside, none standing in a count: five at-the-line claims
  (7, 8, 13, 14, 26) store the complement of their forecast (the claim
  writer's first minute, 7 Sep, 25d83b8); run 4821 (predict:mlb, 27 Sep
  05:44Z) has no ending recorded, for item 7's sweep. New questions 21-27
  below.
  **THE QUEUE IS BLOCKED (2026-09-28 ~00:25Z).** Q20 is built and proved
  but not committed: question 28 (its fix uncovers the click-after-hash
  race in ~10 browser tests). The change is left uncommitted in this
  worktree AND kept on branch `q20-held` (e4b9792, pushed; not gated, not
  for master) -- if the worktree is ever reset, `git checkout q20-held --
  <its 9 files>` brings it back. Q17 waits for questions 21 and 22, Q16 for
  23 and Q17; the board merge, Q5, Q10 and the re-read are ordered after
  them. **Next: whichever of Q28, then Q21-Q23, the operator rules.**
- **Serving: f02e913** (`/api/health` = f02e9134d984). Repair items 1-8 and
  the schema rulings are released; close-out:
  `docs/closeouts/2026-09-27-overnight.md` (verdicts, awake time, spend).
- **THE ORDER, as ruled 2026-09-27 (second set,
  docs/briefs/2026-09-27-rulings-second-set.md; supersedes the list just
  below where they differ):** Q13 (committed 9db5582; its gate was cut off
  by a power-off at 04:58Z on 27 Sep and runs again) -> Q9 labels -> Q12 ->
  Q14 in three commits (priced_scorecard, drift.report,
  horizon.market_outlook; each with a planting that escapes on the unfixed
  code) -> the flaky tests -> the board merge
  **Done 27 Sep:** Q13 released as 8d0ed63 (06:07Z; the gate re-run after
  the operator's power-off); Q9 released as 99bff26 (07:05Z) and the four
  labels written to the live record (3, 10, 26, 56; one transaction; the
  rule's selection verified against the arithmetic). A third race failed a
  gate once and passed alone 3/3:
  `test_motion.py::test_a_tab_switch_arrives_through_the_motion_block`
  (a computed style read before it applied) -- Q5's business, with the
  weekly strip's canvas race.
  Q12 released as 5a93bb3 (09:08Z; gate 4/4, 318/318): every measurement
  counts a same-side pair once and 45/46 not at all ("Both sides, no
  position"); the rule leaves out exactly the 18 pairs' later rows and
  45/46 on the record. Q14 released as 68b215e (14:06Z; three commits
  29811e0 priced record, cdaf03c drift, 68b215e outlook; gate 4/4,
  324/324): MLB moneyline's priced "281" is 103 (statistical, genuinely
  past its 100) and 91 (reasoning); drift "over 79 games" is 50; the
  outlook's "350 of 100" is 246; NFL passing yards, rushing yards, passing
  touchdowns and UFC Contender Series now read "cannot clear". Its gate
  failed twice first on `test_nothing_moves_under_reduced_motion`: a
  diagnosis (scratchpad diag/) showed the test racing the redraw its own
  hash change starts -- reproduced on the code before Q14 with a planted
  25-30 ms delay; Q5's business -- and the third run was green.
  **Next: the flaky tests.**
  (The order continues:
  (docs/briefs/2026-09-27-board-merge.md) -> Q5 (A: a render-finished
  signal, every fixed wait rebuilt; ELAPSED_TIME_HELD may only shrink until
  then, and the merge adds no fixed wait) -> Q10 -> the re-read (not before
  2026-09-28T15:00Z).
- **RULED 2026-09-27 (docs/briefs/2026-09-27-close-out-rulings.md). The
  order:**
  1. **Q13** (in progress): no stored recommendation may be replaced by any
     statement; its own commit, planting proved on the unfixed code.
  2. **Q9 labels**: (B) all four -- 3, 10, 26, 56 -- written after Q13's
     release (set RULED, gate, release, `--write --live`).
  3. **Q12** (ruled, not placed in the order; default until placed: here):
     measurements count a same-side pair once (the earlier row); recs 45/46
     count zero everywhere and are labelled "both sides, no position"; the
     record shows rows as written.
  4. **The flaky tests**: the elements render at 44px or more in whole
     pixels; never widen a tolerance; its own commit.
  5. **The board merge**: checklist in docs/briefs (none there on 27 Sep) or
     pasted by the operator; `board` untouched until then.
  6. **Q10**: the size uses the taken side's cost; its own commit and
     planting.
  7. **The re-read**: local, read-only, against a verified copy, not before
     2026-09-28T15:00Z; three measurers; confirm repair items 1-8 took
     effect on the record and restate every gate distance per forecaster
     and distinct bet; the edge question is not re-measured.
  8. After it: the Record page's "market ahead" per sport and market with
     its interval; then the operator's decision on the pick'em entry check
     against M3 (the model plan: docs/briefs/2026-09-27-model-plan.md).
  - Q11: the default stands (record only). Q5 and Q14 were sent to the
    operator in full, as asked.
- **Dates:** first clean closing-line read 2026-10-15 (window from
  2026-09-24); MLB's regular season ends 2026-09-27.

## The overnight run, as it went (older; the block above wins)

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
  -> ~~item 2's remainder~~ -> ~~item 3~~ -> ~~item 4~~ -> ~~item 5~~ ->
  ~~item 6~~ -> ~~item 7~~ -> ~~item 8~~ -> ~~close-out~~.
- **Item 8 RELEASED: f02e913** (`/api/health` = f02e9134d984, 02:36Z on 27
  September; gate 4/4, 314/314; the first run failed only on the tap-target
  flake, 43.9995px, and the rerun was green): two BROKEN findings recorded
  in READINESS, the closing line counts from 2026-09-24, no verdict before
  2026-10-15.
- **Item 7 RELEASED: 0c6da10** (`/api/health` = 0c6da10ce66e, 00:06Z on 27
  September; gate 4/4, 312/312), after a verified backup
  (`var/gridiron.db.pre-task-runs-widening-2026-09-26.bak`, integrity ok,
  every table equal) because db.init rebuilds `task_runs` to admit
  'abandoned'. On the record: the 7 rows past their task's silence are
  'abandoned' (969, 1742, 1847, 2057 final:cfb; 1983, 1986, 1989 refresh);
  6 stay 'running' until theirs passes. **WakeToRun set on all 18 registered
  Gridiron-* tasks** (Set-ScheduledTask, settings only; nothing else
  changed); wake timers are enabled on AC and DC. WakeToRun wakes a
  SLEEPING machine; it does nothing for a machine switched off, which is
  what both overnight gaps were. `tools/awake.py` reports the awake
  fraction for the close-out.
- **Item 6 RELEASED: 6cb20eb** (`/api/health` = 6cb20eb21ec7, 21:35Z on 26
  September; gate 4/4, 308/308): every at-the-line count is one bet per
  forecaster (UFC per card). MLB moneyline's "283, past the 100" is 92 of
  100 for each forecaster, MLB spread's 130 is 88, the moneyline ledger's
  "176, past the 100" is 49 and 66: nothing at the line is past its 100.
  Question 14 (three more pooled counts outside the ruling's words)
  written.
- **Item 5 RELEASED: 9014add** (`/api/health` = 9014addcf403, 10:49Z on 26
  September; gate 4/4, 306/306): one recommendation per game and market,
  never both sides, in the door and a new trigger that binds new rows only.
  The 18 existing pairs are untouched (questions 11, 12); question 13 (a
  LAW 3 hole: INSERT OR REPLACE on recommendations) written.
- **Item 4 RELEASED: 3c43509** (`/api/health` = 3c43509a055c, 08:25Z on 26
  September; gate 4/4, 305/305): a no-side edge divides by the no-side
  cost. **The re-grade labels are NOT written**: the old divisor let four
  through (3, 10, 26 and 56), not three; `tools/regrade_return_on_stake.py`
  refuses the live record by naming 56 until question 9 is answered. Once
  ruled: set RULED / LEFT_BY_RULING, gate, release, then run it with
  `--write --live`.
- **Item 3 RELEASED: 36e863f** (`/api/health` = 36e863f09439, 06:35Z on 26
  September; gate 4/4, 303/303): a recommendation is priced from the
  correction in force (now before the start; the claim's own instant once
  the game is under way or over), stores raw, corrected and version, frozen.
  On the live record no correction has ever been activated (63 fits, 0
  active), so nothing changes until one is. The two columns and the trigger
  reached the record through db.init.
- **The first pass after items 4 and 2's remainder** (Predict-MLB, 05:00Z
  on 26 September): ok, 68 forecasts, 26 reasoning rows each with a `sent`
  prompt record; the audit passes on the record (538 reconstructed, 26
  sent). (Was: item 2's remainder ("run.py:99 may never skip an untrained market
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

## Queued for AFTER the repair's close-out (operator ruling of 2026-09-26)

The edge read (docs/briefs/2026-09-26-edge-read.md; recorded in
docs/READINESS.md as a dated finding: the model shows no edge; MLB moneyline
market better beyond noise for both forecasters; nowhere does the model beat
the market). **No feature work from it now.** After close-out, in this order:

1. The Record page states "market ahead" per sport and market, with its
   interval.
2. Model plan M3, the market blend, moves to the front of M1-M6. (No document
   naming M1-M6 is in this repository; the order is recorded as ruled for
   whoever holds the plan.)

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
9. **"The three recommendations it let through": the divisor let a fourth
   through after the ruling. (Repair item 4; asked 2026-09-26.)** The ruling:
   "Re-grade the three recommendations it let through as 'would not have
   cleared'." THE READ of 2026-09-23 counted three -- recs 3, 10 and 26.
   Measured again on 2026-09-26 through the read-only door, the rule
   (cleared 5% of the yes price, does not clear 5% of what its own side
   cost, written after the bar was declared, not withdrawn) selects FOUR:

   | rec | written | MLB spread, side | edge | yes price | on the yes price | on its own cost |
   |---|---|---|---|---|---|---|
   | 3 | 2026-09-07T20:52:31Z | no | +2.09c | 37.5c | 5.57% | 3.34% of 62.5c |
   | 10 | 2026-09-08T21:33:31Z | no | +2.30c | 37.5c | 6.13% | 3.68% of 62.5c |
   | 26 | 2026-09-09T21:32:20Z | no | +2.84c | 39.5c | 7.19% | 4.69% of 60.5c |
   | 56 | 2026-09-24T05:21:25Z | no | +3.03c | 39.0c | 7.77% | 4.97% of 61.0c |

   Rec 56 (PIT -1.5 not covered, game mlb_823326, prediction 2165, gate 144)
   was written by the logon catch-up's predict:mlb run (task run 2325) on 24
   September, after the ruling and before the fix; its close is unmeasured
   (no later read of its contract). Until the fix is released the scheduler
   can let more through the same way; the tool names any it finds.
   - **(A) The three named.** "The three" is the set the ruling answered;
     re-grade 3, 10 and 26 only. Rec 56 stands unlabelled -- or waits for a
     ruling of its own -- and the tool lists it as selected and left.
   - **(B) Every one it let through.** "The three" described the class as it
     was counted then; re-grade 3, 10, 26 and 56, and any more the old code
     writes before the release.
   Built meanwhile, the same under both: the fix, the table, the page's
   words, and `tools/regrade_return_on_stake.py`, which REFUSES on the live
   record today, naming rec 56 and its arithmetic, because its selection is
   not the ruled set. Your answer is one line in it: rec 56 into `RULED`
   (B) or into `LEFT_BY_RULING` (A). Rehearsed both ways on scratch copies.
   Taken as the conservative default, not asked: a re-grade is a LABEL, not
   a withdrawal -- the re-graded rows stay in every count they were in (the
   ruling says "re-grade", where ruling 1 said "void" for out of the
   counts); today none of the four is in any closing-line N (3, 10 and 26
   are restated closes, 56 unmeasured), so no figure moves either way.
10. **Does "a no-side edge divides by the no-side cost" reach the SIZE?
    (Repair item 4; asked 2026-09-26.)** Above a market's gate, with its
    edge measured ahead, `recommend.size_for` passes the claim's YES
    probability and the YES price to `kelly_fraction` whatever the side, so a
    no-side pick with a real edge is sized as the yes bet: 43% against 48.5c
    is +3.5c on the no side and a quarter of Kelly of 0.0 units, written as a
    `fraction` (item 3's prover found it). Measured 2026-09-26, read-only:
    every one of the 101 recommendations is a flat unit; six categories have
    their hundred settled (NCAAF spread statistical 132; MLB moneyline
    statistical 233 and reasoning 121; MLB spread statistical 175; MLB total
    statistical 182 and reasoning 110), and in none is the model measured
    ahead (three behind, three with nothing settled beside a price) -- so the
    defect has touched no recommendation, and is one measurement away in
    each of the six.
    - **(A) Yes: one ruling, one orientation.** The ruling names the rule
      that every quantity of a no-side pick is the no side's; the size is
      computed on the no side (the no side's probability and cost into
      `kelly_fraction`), with its own planting, in item 4.
    - **(B) No: the ruling names the return-on-stake denominator.** Kelly's
      arithmetic divides no edge by a cost the way the bar does (a no-side
      Kelly fraction is the edge over the YES price), the brief allows no
      fix beyond what is named, and item 3's prover already wrote "a fix is
      its own ruling". It waits for one.
    Default until ruled: (B); not built; FOLLOWUPS has it with two more of
    the same shape, also not named -- the payout floor and a proposed
    combo's no-side legs.
11. **Does "never both sides" bind the page, or the record? (Repair item 5;
    asked 2026-09-26.)** The ruling: "One recommendation per game and
    market, and never both sides." Built: the record -- `record_for` asks
    one door (`recommend.one_per_game_and_market`) before it writes, and a
    schema trigger refuses a second standing row however it is written. The
    page (Upcoming's "Clears the bar", the recommendation lines and the
    combos, all from `recommend.for_predictions`) shows one forecaster at a
    time, the latest forecast per question, and is unchanged.
    - **(A) The record.** A recommendation is a row in `recommendations` --
      recs 45 and 46 are rows -- and the rule binds what is written. The
      page can then show a pick the record refused: after the final pass, a
      game whose morning pick stands shows the final card's pick at its new
      price (17 of the 18 pairs on the record are this shape, same side);
      when the two forecasters split in one pass, each forecaster's page
      shows its own side while the record holds neither; and if a final
      pass ever turned the side of a standing morning pick (none has on the
      record), the page would show the other side of a recommendation that
      stands. A pick marked from such a card has no edge on record.
    - **(B) The page follows the record.** `for_predictions` asks the same
      door: a pick on a game and market with a standing recommendation from
      another forecast, or on which the pass took both sides, is shown with
      its edge but not as a pick, and says why. After a final pass the
      morning's pick then leaves "Clears the bar" (the recommendation that
      stands is the morning's, and the card on the page is the final's),
      so a card would need to say which recommendation stands and at what
      price -- new words on the card, the Watching heading and the empty
      sentence, and renders at both widths.
    Default until ruled: (A), built; (B) not built.
12. **The pairs written before the rule: counted as written, or once per
    game and market? (Repair item 5; asked 2026-09-26.)** Measured read-only
    at about 08:20Z on 2026-09-26: 18 game-markets hold two standing
    recommendations each, 36 rows -- 1/9, 3/10, 4/12, 5/13, 6/14, 20/25,
    21/26, 23/28, 32/34, 41/44, 42/48, 43/49, **45/46** (the only pair on
    opposite sides), 60/79, 61/80, 84/93, 86/94, 87/95 (THE READ counted
    13; the scheduler wrote five more since, and can until the release).
    The trigger reads none of them, and nothing was voided, re-graded or
    labelled: the ruling names none. They are counted as written today:
    MLB spread's closing line holds 9 measured closes, 3 of them (93, 94,
    95) the second row of their game and market; MLB total holds none (45
    and 46 are restated, unmeasured). The kill criterion
    (`coverage.stopped`, 50) and READINESS count the same rows.
    - **(A) As written.** The ruling says what may be written from now on;
      every existing row stays in every count it is in. Item 6 restates the
      at-the-line scorecard per distinct bet by its own words.
    - **(B) Once per game and market.** The closing line, and so the kill
      criterion, counts only the first standing row of each game and market
      -- a read-time clause beside `standing_row_clause`, nothing written --
      and names the later rows beside the count; for 45/46 that is 45 alone,
      or neither if "never both sides" is read back onto the pair.
    Default until ruled: (A); nothing built for (B).
13. **A LAW 3 hole outside the named items: fix it? (Found by item 5's
    prover, 2026-09-26.)** `INSERT OR REPLACE` naming a stored
    recommendation's id removes it and writes another in its place: SQLite
    fires no delete trigger for a replacement, so `recommendations_no_delete`
    never sees it. It is the shape `market_snapshots` had until
    `market_snapshots_never_replaced` (5a'), and it exists on every release
    so far. No code does it today (every writer inserts plainly). The fix is
    one trigger of a new name and a planting -- but the repair brief says
    "class (a) defects only ... in this order", and this is not among items
    1-8. Build it as its own commit now, or after close-out? Default until
    ruled: not built; FOLLOWUPS has it.
14. **Three counts on the Record page pool the way item 6's did, outside its
    words: fix them under item 6, or each by its own ruling? (Found by item
    6, 2026-09-26.)** Item 6 ("The at-the-line scorecard never pools
    forecasters or duplicates ... Re-state every gate distance on the
    corrected counts") is built for every count stated at the venue's line.
    Measured read-only on 2026-09-26, three more counts on the same page
    count a question's morning and final pass twice, or two forecasters as
    one:
    - **The priced forecaster** (`calibration.priced_scorecard`, worded by the
      at-the-line gate line): MLB moneyline "261 settled comparisons, past
      the 100 this record needs" is one priced row per blind forecast -- 139
      on the statistical model's (96 standing questions), 122 on the
      reasoning pass's (84). Neither is past the hundred.
    - **The learning panel's drift line** (`drift.report`, the media line,
      statistical, gate 50): MLB moneyline "over 75 games", past the fifty,
      is 58 questions, 48 of them standing rows.
    - **The blind record's outlooks** (`horizon.market_outlook`, the line
      beside each statistical curve) count every row, superseded passes
      included, and for UFC every tier: MLB moneyline "330 of 100" beside a
      curve of 233, spread and total "272 of 100" beside 175 and 182; UFC
      "62 of 100" beside a Numbered-card curve of 0.
    - **(A) Item 6's words name the at-the-line scorecard.** These stay as
      they are, recorded in FOLLOWUPS, each for a ruling of its own.
    - **(B) "Every gate distance" reaches every count on the Record page that
      pools.** Each is rebuilt through its record's standing rule, per
      forecaster (and per tier for UFC), with a planting, under item 6.
    Default until ruled: (A); nothing built for (B).
    **RULED 2026-09-27: (B)**, three commits before the re-read.
15. **The replacement hole beyond recommendations: fix it on the other
    tables, and where in the order? (Found by Q13's build and prover,
    2026-09-27; FOLLOWUPS, "No stored recommendation is replaced", OPEN.)**
    Q13 closed it for `recommendations` only, as ruled. Measured on scratch
    databases:
    - **Predictions (LAW 3's own table).** `INSERT OR REPLACE` naming a
      stored prediction's id rewrote its probability from 0.61 to 0.99
      under the same id, and `UPDATE OR REPLACE ... SET rowid` onto another
      prediction removed that one; `predictions_no_delete` never runs.
      Nothing refuses it, and only the record's fingerprint audit would
      catch it afterwards. 16 of the 20 tables with a delete rule have no
      replace rule.
    - **`market_snapshots_never_replaced_by_update`** (5a') is written
      `BEFORE UPDATE OF id, prediction_id, kind`, which SQLite does not run
      for `SET rowid` / `oid` / `_rowid_`: two snapshots became one.
    - **`recommendation_closes` and `recommendation_voids`** accept a
      replacing insert naming a stored recommendation: a close or a
      withdrawal can be rewritten.
    - **A recommendation's id** can still be changed by a plain `UPDATE ...
      SET id` (not a replacement, but a later insert could reuse the old
      number).
    - **SQLite's own sequence** can be rewritten by any statement, and no
      trigger can be put on it.

    No code does any of these today. The fix is the Q13 pattern, table by
    table (a replace rule with no column list, and an after-insert rule
    where the number can read twice), each with a planting. Default until
    ruled: not built.
    **RULED 2026-09-27 (third set): first in the order.** Predictions fixed
    as Q13 was, own commit and planting; then one gate scan refusing
    replacing writes against every append-only table, legitimate upserts
    named in a register that only shrinks; a read-only measurement of
    whether any live prediction was replaced. The other holes listed above
    are not named and stay in FOLLOWUPS.
16. **The correction gates on the Record page pool the same way, outside
    Q14's three: rebuild them too? (Found by Q14's drift step, 2026-09-27.)**
    `views.corrections_report` ("A correction for ..." under "What else is
    still counting") counts every settled row -- each pass of a question,
    every prop type under "prop", UFC's cards together. Measured read-only
    against the standing questions the correction's own learning-panel
    count uses: MLB moneyline 350 against 246; NFL point spread "49 of 50"
    against 30; UFC distance, moneyline and rounds "85 settled", past the
    fifty, against 49, under it. Q14's first sentence says "every count on
    the Record page that states a gate distance"; its three commits named
    three others. Default until ruled: not built.
    **RULED 2026-09-27 (third set): (B), after Q17, on its key;** each
    correction gate's count per forecaster and distinct bet, planting each.
17. **One key for "a distinct bet"? (Found by Q14, 2026-09-27.)** Q14's
    priced step keys a distinct bet as the blind question (game, market,
    subject, rung); its drift step keys it as game and market (plus the
    player for a prop), which is item 6's key. They count the same on the
    priced record today and differ on the drift record: NCAAF point spread
    has 78 standing questions on 66 games (twelve games asked at two
    rungs). Which key? Default until ruled: each as built.
    **RULED 2026-09-27 (third set):** one function defines a distinct bet:
    forecaster + the venue's question (game, market, line). A question's
    passes count once (each record's standing rule picks which); alt lines
    are separate questions. Q12's, Q14's and Q16's counts all use it; every
    released number that moves is listed.
18. **A card's Why panel snaps shut when a redraw lands. (Found by the
    diagnosis of 2026-09-27; not a test defect.)** `renderToday` rebuilds
    every card with its Why body hidden. On the live record `/api/week`
    takes about 7.6 s, so a person who opens Why after a market tab, the
    tier filter, the sort toggle or the took button -- before the redraw
    they started lands -- sees it close. A defect to fix (keep the open
    card open across a redraw), or as designed? Default until ruled: as is.
    **RULED 2026-09-27 (third set): fixed in the board, not the old UI;** an
    open card stays open across any redraw, and a test proves it.
19. **The priced panel's heading paints an internal identifier.** (Found by
    Q14's priced render.) The "Priced, and against the close" heading
    shows the blend version "b1" raw on every sport's Record page, since
    the priced record opened. PLAIN WORDS forbids an internal identifier in
    the interface. A class (a) fix of one line and a planting, or wait?
    Default until ruled: not changed.
    **RULED 2026-09-27 (third set): fixed in the board;** headings in plain
    words, internal version names only in a tooltip.
20. **The tap-target flake is not in the elements. It is the Today panel's
    arrival. (The flaky tests, ruled 2026-09-27; asked 2026-09-27.)** The
    ruling: "fix the elements so they render at 44px or more in whole
    pixels. Never widen a tolerance." Measured on this tree with a
    synthetic world (scratchpad `flaky/diag/`): every tap target the tests
    measure is already laid out at a whole number of pixels, 44 or more.
    `.expand` has `min-height: 44px` (style.css:2325), its `offsetHeight`
    is 44, and its box reads exactly 44.0 at rest on every view and width
    the tap-target tests use. That covers the week with every card closed
    and every card open, Record, Results and Settings, at 390 (3x) and
    375 (2x). The failing 43.99951171875 is 44 less 1/2048, which is one
    step of single precision at 4,096-8,192px down the page. It appears
    only while the Today panel arrives. Every render calls `arrive(panel)`
    (app.js:1473), which starts the panel one per cent below its place
    (`#today.arriving { transform: translateY(1%) }`, style.css:1765) and
    eases it up over 200ms (R4, 2026-09-05). While it moves, the panel
    sits a fraction of a pixel off whole (for example 34.0407px). The
    browser maps each button's box through that offset and rounds the
    box's top and bottom separately, so 44 reads 43.9995 or 44.0005 and
    the 54px "took" button reads 53.9995. The test sets the hash to the
    week, which redraws the page, and it measures inside those 200ms. We
    made twelve market switches and sampled every frame. As shipped, 9 of
    192 frames read a tap target off whole pixels, and 3 of those readings
    were under 44. With the panel's movement removed and the fade kept,
    193 of 193 frames were whole. No CSS on the target fixes this. With
    every target at 45px, 15 readings were still off whole (none under
    44), and the extra pixel would be a tolerance by another name. Run
    alone, the test passed 10 of 10 on this tree. It flakes only when the
    redraw lands inside the measurement.
    - **(A) The panel arrives by its fade alone.** `#today.arriving` loses
      its `translateY(1%)`, and `#today`'s transition names opacity only
      (200ms and ease-out, as now). Every tap target then renders at its
      own whole-pixel size on every frame. It would come with a check that
      samples every frame of an arrival at 390 (3x) and fails by name on
      a tap target under 44 or off whole pixels; that check fails on this
      tree. It would also come with a planting that puts the movement
      back. The cost: the "one per cent below" arrival goes. L3's
      vocabulary allows a translate within 2% but does not require one.
      Also, `test_motion.py::test_a_tab_switch_arrives_through_the_motion_block`
      checks that the panel's transition names `transform`, so that one
      line changes, in a test Q5 is about to rebuild.
    - **(B) The elements stay as they are, and the test measures the slate
      once it has arrived**, waiting on Q5's render-finished signal. No
      fixed wait is added and nothing is widened, and the movement stays.
      But the ruling said to fix the elements, not the test, and this
      step would then wait for Q5, which comes after the board merge.
    Also measured, and checked by no test: the "How the model works" link
    inside an open card's Why panel (`a.face-more`) is 17.4px tall at 390
    and 375. The smoke test measures only `nav a`, and `test_cards.py`
    measures `#view-week a` with every card closed. Is that link in this
    item's scope, or its own item? Default until ruled: nothing built, and
    the test flakes as before.
    **RULED 2026-09-27 (third set): (A)**, second in the order, after Q15:
    the Today panel arrives by fade alone, a per-frame whole-pixel check that
    fails today, a planting, and the one `test_motion` assertion changes.
    The side question: not in scope; the old Why panel leaves with the
    board, and the board merge checks every tap target, links included.

21. **Q17: which "line" is in the key? (Asked 2026-09-27, before Q17's
    build; a read-only map of every count's key, scratchpad.)** The ruling:
    "forecaster + the venue's question (game, market, line) ... alt lines
    are separate questions". Six keys exist today: `priced.bet_of` and
    `horizon.bet_of` (game, market, subject, the RUNG we asked:
    `predictions.line_asked`), `drift.bet_of` (game, market, the player for
    a prop; no line), `at_the_line.standing_claims` (game, market, side; no
    line), the coverage line (game only), and Q12's rule (game, market,
    across forecasters). The blind record has no venue line at all, and
    `calibration.assert_no_pooled_outlooks` holds each outlook's count to
    its curve's n, so the key's line decides whether the blind curves move.
    - **(i) The rung asked** (`line_asked`; NULL for a moneyline or UFC
      distance). Every forecast has it; the priced record, the outlook and
      the blind curves do not move; drift and the at-the-line record split
      each game asked at two rungs (twelve NCAAF spread games) into two bets.
      A prop's player is in the question (the subject), as it is in the
      blind record's own key.
    - **(ii) The venue's strike.** Only a forecast the venue quoted has one,
      so a blind curve's forecasts would mostly have no line; the outlook
      would then disagree with its curve, or the curves would be rebuilt on
      a key most of their rows lack.
    Recommended: (i). Default until ruled: Q17 not built.
    **RULED 2026-09-28: (i), the rung the forecaster was asked;** two
    rungs on one game are two questions.
22. **Q17: the recommendation counts, and recs 45/46.** Q12's counts (the
    closing line, the kill criterion, "Would not have cleared",
    tools/empty_bar.py) are the app's recommendations, both forecasters
    pooled per market (`clv_report` groups by market). Recs 45 (statistical,
    over 7.5) and 46 (reasoning pass, under 7.5), Toronto at Baltimore on 21
    September, are two forecasters: with the forecaster in the key they are
    two distinct bets, and Q12's "count zero ... both sides, no position"
    cannot come out of one function that includes the forecaster.
    - **(A) Those counts split per forecaster** on Q17's key. 45 and 46
      each count once, in their own forecaster's closing line; the "Both
      sides, no position" row goes (Q12's words for 45/46 are superseded);
      the kill criterion reads each forecaster's line.
    - **(B) Those counts stay the app's position, pooled.** Pairs are found
      on Q17's key; "both sides" is a second rule on the venue's question
      without the forecaster, so 45/46 still count zero -- two functions,
      against "one function".
    Recommended: (A), as Q17's words read; it reverses Q12 for 45/46, so it
    is yours. Default until ruled: Q17 not built.
    **RULED 2026-09-28: (A);** recommendation counts split per
    forecaster; 45 and 46 each count once in their own forecaster's line
    and the "Both sides, no position" row goes; same-side pairs count
    once only within one forecaster; every released number that moves,
    listed.
23. **Q16: the page's count, or the fit's gate too?** A correction's category
    is sport, market type and forecaster (`correction.py:107-120`: every
    prop type under "prop", UFC's cards together), and the fit is gated on
    every settled row of it (`correction.training_rows`, `refit_all`). The
    page's "A correction for ..." line counts the same rows. Rebuilt on
    Q17's key alone, the page would state a count the fit is not gated on.
    - **(A) The page and the fit's gate both count distinct bets** on Q17's
      key: the page states what actually gates the fit. When a correction
      can be fitted changes -- a model change.
    - **(B) Only the page's count changes**, and it states a number the fit
      does not use.
    Recommended: (A). Default until ruled: Q16 not built.
    **RULED 2026-09-28: (A);** the page's count and the fit's own gate
    both move to the key for fits from the release forward; the 63
    existing fits stay as written, and any short of its gate on the
    corrected count is labelled "fitted below its gate" and can never be
    activated.
24. **Q13's released rules have the hole Q15's prover closed on predictions.
    (Found by Q15's prover, 2026-09-27.)** A plain `UPDATE recommendations
    SET id = 10 WHERE id = 2` (over a mark of 3) is not refused -- it is not
    a replacement -- and afterwards a one-row `INSERT OR REPLACE` whose
    number reads as a free 99 to the rules and as 10 to the row writes
    another forecast's recommendation over it: the after-insert rule
    assumed every stored number is at or below SQLite's mark. Q15 fixed
    this for predictions (commit 22e182d); Q13 is released as it was. Fix
    it on recommendations the same way (own commit, planting)? Default
    until ruled: not built; no code does either statement.
    **RULED 2026-09-28: fix it after Q20,** on Q15's basis, own commit
    and planting.
25. **Connection settings that switch the rules off. (Found by Q15's
    prover.)** `Connection.setconfig(SQLITE_DBCONFIG_ENABLE_TRIGGER,
    False)` turns every rule in the schema off for that connection, the
    delete rules included, and `create_function` redefining a built-in the
    rules call (`json_valid`, `json_extract`) answers a rule one way and a
    key another. None is in shipped code. The scan the ruling asked for
    names three statements; add these two calls to it? Default until ruled:
    not built.
    **RULED 2026-09-28: yes;** the scan also refuses code that turns the
    rules off by a connection setting or registers a function under a
    built-in's name.
26. **Tables append-only in words, with no rule. (Found by Q15's scan.)**
    `factor_scores` and `llm_calls` (CLAUDE.md, "Append-only history"),
    `injury_reports`, `lineup_captures` and the observed-weather table
    ("append-only and stamped" in schema.sql) have no delete or update rule,
    so the scan treats them as ordinary (none takes a replacing write
    today). And `mlb_people`'s schema comment says a row is "written once",
    while `mlb_loader.load_people` upserts it on every load (registered as
    a cache). Give the five their rules, and which is meant for
    `mlb_people`? Default until ruled: not built.
    **RULED 2026-09-28:** each of the five gets the rules or words
    saying what the code does; mlb_people's words change and it joins
    the upsert register; one commit.
27. **Sixteen NFL week-3 reasoning totals stand on their early pass, written
    after their final pass. (Found by Q15's measurement.)** `final:nfl` run
    2052 wrote the finals on 23 September at 19:30Z; `predict:nfl` run 2336
    wrote the early rows on 24 September at 05:32-05:36Z, the first run
    after the spread and moneyline were trained. Both are lawful (the key
    includes the pass), and `calibration.standing_row_clause` takes the
    latest row before the start without reading the pass, so for these 16
    the later EARLY row stands over the final. Q17 says which pass counts
    "stays each record's standing rule": as designed, or should a final
    pass always stand over an early one? Default until ruled: as is.
    **RULED 2026-09-28: measure read-only first** (which pass stands for
    each of the 16; when each pass was written against the start); a
    pass written after the start is voided as an append-only row under
    the existing void rule; report before changing anything else.
28. **Q20's fix uncovers a race the movement was hiding. Tests that open a
    card right after setting the hash now lose the card to the redraw that
    same hash change starts. (Found by Q20's prover, 2026-09-27. Q20 is
    built and proved, but NOT COMMITTED. The change is in the worktree.)**
    Q20 itself holds. The per-frame check fails 10 runs of 10 on f66fefa and
    passes 10 of 10 on the fix. The planting escapes on f66fefa and is
    caught on the fix. The harness catches 338 of 338. A wider sampler
    covered every other redraw at 390 (3x) and at 375 (2x), 64 redraws
    each, and read nothing off whole or under 44.

    The race is in the tests. They set the hash, wait for a card that the
    previous render already drew, and tap its Why. The hash change's redraw
    rebuilds the panel, and an open card closes when that happens (Q18,
    fixed in the board). On f66fefa, the Why sat inside a moving panel.
    Playwright waits until a target stops moving before it taps, so every
    tap came after the redraw. We checked this in a scratch copy of the
    steps, 30 fresh sessions per tree: on f66fefa the redraw came first 30
    times and the card stayed open 30 times. With the fade alone the Why
    is still, so the tap lands first. On the fix the redraw came after the
    tap 11 times in 30, and each of those 11 times the card was closed.

    The test file whole (`test_smoke.py`), by tree:
    - f66fefa, 3 runs: 2 failed, both only on
      `test_nothing_moves_under_reduced_motion`. That test already raced
      this way, because nothing moves under reduced motion (Q5's
      diagnosis).
    - The fix, 6 runs: 4 failed on another test.
      `test_the_dumbbell_and_contribution_bars_fit` failed twice.
      `test_the_bucket_line_never_shows_an_accuracy_without_its_n` and
      `test_a_card_still_expands_on_a_phone` failed once each.
    - The full suite on the fix failed the dumbbell test and the
      reduced-motion test.

    Each of those tests passes alone (5 of 5). The tests with this shape
    are `_open_first_card`, which 4 tests use, and 5 other places in
    `test_smoke.py`, plus `test_prompt_disclosure.py::test_a_reasoning_card_shows_its_prompt_inside_why`.
    - **(A) Fix those tests in Q20's commit.** Before tapping, each would
      wait for the redraw its own hash change started to finish. The test
      would see that from inside the page, when the arrival class goes on
      and comes off, as the per-frame check already does. There would be no
      clock and no fixed wait, and `ELAPSED_TIME_HELD` would not change.
      This would be one test helper. The app would not change. It does part
      of Q5's work early, for these tests only. Q5's render-finished signal
      would later replace the helper.
    - **(B) Commit Q20 as built.** These tests would keep racing until Q18
      (an open card stays open across a redraw, in the board) or Q5 (after
      the board merge). With the one-rerun rule, the gate's step 1 would
      fail on one of them in most runs: 4 of 6 runs of the test file did.
    Recommended: (A). Default until ruled: Q20 is not committed. The change
    stays uncommitted in the worktree on `repair`, at f66fefa.
    **RULED 2026-09-28: (A),** in Q20's commit: one shared helper, no
    clock, no fixed wait; Q5's signal replaces it later.

29. **The number rules still have ways round them, each needing a statement
    no writer makes. (Found by Q24's prover, 2026-09-28; FOLLOWUPS, "No
    recommendation moved above every number given out", OPEN and NOT
    SEEN.)** On predictions (Q15) and recommendations (Q13, Q24), measured
    on scratch worlds and a verified copy (rolled back):
    - **A stopped multi-row insert.** `INSERT OR FAIL` of several rows whose
      later row fails a CHECK or NOT NULL keeps the rows before it, above
      SQLite's mark (a stopped statement never writes the mark back); a
      one-row insert whose number reads twice then writes over them. No
      writer uses OR FAIL or RAISE(FAIL). The hole closes at the next insert
      that finishes.
    - **The mark rewritten first** (four ways: its row deleted; set forward,
      a row moved beneath, set back; the same inside temporary rules; set
      back and the newer rows moved down beneath it). SQLite refuses a rule
      on its sequence store, so no rule can see it. `rebuild._rebuild_one`
      is the one shipped writer of the store: it carries the mark exactly.
    Both need a replacing insert whose number is worked out twice, which the
    scan (Q15) refuses in shipped code, and Q25 will refuse the connection
    settings and function names that make one. Close them in the schema (a
    rule refusing OR FAIL's partial rows; a scan naming any write to the
    sequence store other than the rebuild's), or leave them in FOLLOWUPS?
    Default until ruled: FOLLOWUPS. (Before Q16, so the new queue rule does
    not yet apply; by it, this touches LAW 3.)

30. **Counts that do not read Q17's key. (Found by Q17's numbers step,
    2026-09-28; none moved, none a gate count.)** The header record, the
    sport tabs and the sign-in page count every settled row -- both passes
    of a question, both forecasters together. A pick card's footnote, "the
    model's worst band" (`views._worst_band`), draws one curve over every
    market and both forecasters of the sport. `views._superseded_ids` (the
    "early view" label) keeps a key of its own (with the factor set, without
    the prop type); it labels rows and counts none. Put them on the key, or
    leave them (none states a gate distance)? Default until ruled: as they
    are, in FOLLOWUPS; by the queue rule after Q16 they would wait for the
    re-read.
    **RULED 2026-09-29: FOLLOWUPS, per the queue rule;** none states a
    gate distance.

31. **Q16/Q23: "the 63 existing fits" are 89 today, and one is in force.
    (Found by Q16's first step, 2026-09-28, read-only through
    `db.read_the_live_record`; nothing built, nothing committed, no copy of
    the record made.)** Q23: "The 63 existing fits stay as written; any that
    falls short of its gate on the corrected count is labelled 'fitted below
    its gate' and can never be activated." 63 was the record's count when
    that was ruled: fits 1-63, written 31 August to 21 September 22:11Z (the
    ruling was saved at 01:50Z on 28 September). At 13:00:01Z on 28
    September the weekly `recalibrate` (run 6173) wrote 26 more, 64-89, on
    the pooled gate. The next weekly run is due Monday 5 October, 13:00Z.
    THE MEASUREMENT (scratchpad `q16\measure.txt`, `q16\measure2.txt`).
    Every fit's gate is `MIN_TRAIN` = 50 (unchanged since 31 August) over
    every settled row of its category (sport, market type, forecaster)
    resolved before its fitted instant, voids left out. Recounted, that is
    exactly `n_train` for all 48 fitted rows (voids read as of now or as of
    the fit: the same). The corrected count is the distinct bets on Q17's
    key among those rows. It is the same for all 89 whether read as
    distinct keys or through the blind record's standing rule. Fitted, and
    short of 50 on the key:
    - of the 63: 33, MLB total, reasoning pass, v1 (76 rows, 48 bets); 59,
      61 and 63, UFC distance, moneyline and rounds, statistical, v3 (56
      rows, 32 bets each).
    - of 64-89: 81, NFL point spread, statistical, v3 (60, 41); 85, 87 and
      89, UFC distance, moneyline and rounds, statistical, v4 (85, 49
      each); 86, UFC moneyline, reasoning pass, v4 (63, 49).
    None of those nine is in force. **Fit 71 is: MLB moneyline,
    statistical, v8, in force from 13:00:01Z on 28 September**, the first
    correction ever in force (364 rows, 260 bets, clear of 50 under either
    reading; holdout 73 rows, Brier 0.2504 raw to 0.2452). No forecast or
    recommendation carries it yet (no MLB moneyline forecast written since).
    Nothing to rule on 71 unless you want otherwise.
    THE PLACEHOLDERS. 41 of the 89 rows (33 of the 63) hold no fit. The
    refit found fewer than 50 settled and wrote slope 1, intercept 0, no
    holdout, `n_train` 0, with the count only in its words ("corrections
    begin at 50 settled - 25 so far"; each equal to the recount). Each is
    short of its gate on any count.
    - **(i) Which fits?** (A) The 63 as ruled: 4 labelled (33, 59, 61, 63),
      and 64-89 stand unlabelled, so 81, 85, 86, 87 and 89 stay on the page
      as fits past a gate they are short of on the key. (B) Every fit
      written before Q16's release, by the same rule: 9 labelled today (the
      four, and 81, 85, 86, 87, 89), and more if the 5 October refit lands
      first. Recommended: (B). The ruling divides the fits at the release
      ("for fits from the release forward"), and 64-89 were gated on the
      pooled count exactly as 1-63 were.
    - **(ii) The placeholders?** (A) Labelled too, as "any that falls
      short" reads: 33 more labels (41 under (i)(B)), each saying "fitted
      below its gate" of a row whose own words say nothing was fitted. (B)
      Only a row that was fitted (past its gate on the count it used) and
      is short on the key. Recommended: (B). A placeholder was never
      fitted, so the words would be false of it. And like every stored row
      it can never be activated anyway: `active_from` is written once, at
      the insert, and `calibration_corrections_no_update` refuses any edit
      (the label's rule, once built, would refuse the one other way: a
      replacing insert in its place).
    - Not a question, for the build: the learning panel shows a correction
      row per prop type, while the category is every prop type together
      (and UFC every card together). Built, each such row would state the
      category's count and say it is every prop type together. Splitting
      the category would be a model change the ruling does not name.
    Default until ruled: Q16 not built.
    **DEFAULT TAKEN IN YOUR ABSENCE (2026-09-29 ~01:50Z; the conservative
    default and question 9's precedent):** Q16 is built now -- the count on
    the key, the fit's own gate on the key for fits from the release, the
    label table, its rules and its tool -- because none of that turns on
    (i) or (ii). The label is permanent, so the tool's ruled set is the
    four every reading covers: 33, 59, 61, 63 (among the 63 when ruled,
    fitted, short on the key). The tool selects by rule and refuses to
    write any other selection, as the re-grade tool refused its fourth row
    until question 9 was ruled; if you rule (i)(B) or (ii)(A), the extra
    labels are written by the same tool afterwards (labels only add).
    Fits 81, 85, 86, 87, 89 and the placeholders stay unlabelled until
    then.
    **RULED 2026-09-29: (i)(B) and (ii)(B)** -- the nine fitted rows short on
    the key (33, 59, 61, 63, 81, 85, 86, 87, 89), no placeholder. The default
    above (four) is superseded; the tool's ruled set becomes the nine before
    Q16's gate.

33. **G1: UFC Fight Night's outlook says a gate is reachable that is not.
    (Found by the re-read, 2026-09-29; docs/closeouts/2026-09-29-the-re-read.md
    section 2A; makes a gate count false, so it joins the queue.)** Fight
    Night moneyline, rounds and distance (statistical) each read "39 of 100
    · ~121 expected". The 39 is true. `horizon.slates_remaining` counts 6
    Fight Night cards to come, but 2 of them were fought (12 and 26
    September), each still holding one bout marked 'scheduled' (bouts
    401913546 and 401923433). On the 4 cards really ahead: 39 + 13.67 x 4 =
    ~94, so the page should say THIS GATE CANNOT CLEAR THIS SEASON. Fix the
    slate count (a card is to come only if its start is ahead, or every
    bout on it unsettled), with a planting? Default until ruled: not built.
34. **G2: UFC's tier table, ranker, taken record, blind edge figure and the
    board badge count the three cards as one. (The re-read, section 2B-F;
    under Q14's "per tier for UFC" a gate count is false.)** The tier bands
    read 28/15/4/2; by card they are Fight Night 22/14/2/1, Contender Series
    6/1/2/1, Numbered card 0. The ranker reads 49/0; by card 39/0, 10/0, 0/0.
    The taken record's "every forecast" 49; the board badge
    (`shortlist.settled_for_gate`) 49. Q14 rebuilt three counts per card;
    these were not named. Split each per card, a planting each? Default
    until ruled: not built.
35. **G3: a UFC start stored to the minute is compared as text with a pass
    written to the second. (The re-read, section 2E; a gate count moves
    under one reading.)** 18 final passes (1014-1031) were written at
    19:00:02-03Z for a 19:00Z start; `standing_pass_order` compares the
    stored strings, so "19:00:02Z" <= "19:00Z" reads as before the start and
    the final passes stand. Read to the second, they were written after the
    start, the early passes stand, and the UFC ranker split in each of three
    markets goes 49/0 -> 43/6. No other count moves. (A) As stored: a start
    to the minute covers that minute. (B) Read to the second: a pass
    written after hh:mm:00 is after the start (the stricter reading, LAW
    1's spirit). Default until ruled: (A), unchanged.
36. **The venue's away-side spread contracts are read at the wrong sign,
    so 269 claims and 54 recommendations put the model's number for one
    line beside the venue's price for another. (Found 2026-09-30 by the
    measurement that opens pick-number step A, "every number on a pick
    names the line it belongs to", on one verified copy of the record made
    at about 08:00Z and deleted after. The step STOPPED here: nothing is
    built, nothing committed.)**
    - **What the venue sells.** Every spread contract is "<team> wins by
      over <s> points" -- the venue's own words, in the record's cached
      payloads: "North Texas wins by over 1.5 points" and "Tulsa wins by
      over 1.5 points" (UNT at TLSA), "Toronto wins by over 1.5 runs" (TOR
      at BAL), "SEA Seahawks wins by over 7.5 points" (SEA at WAS).
      `kalshi.parse_markets` stores a home contract as -s and an away one as
      +s. For an away contract, +s is already the home side's line of the
      proposition its complemented price is about (the away side does not
      win by more than s = the home side covers +s). `at_the_line.
      home_view_line` negates it, so every claim priced off an away contract
      stores -s: its model number is the forecast read at -s, and its price
      is about +s. From the first claim writer (25d83b8, 2026-09-07);
      `test_at_the_price.py::test_the_venue_line_is_read_from_the_home_side`
      asserts the negation.
    - **Proved on the record.** The released reading prices "the home side
      covers -s" twice wherever the venue lists s from both sides (8,286
      pairs): the home contract's mid and one minus the away contract's mid
      differ by 41 points on average, the same way in 99.96% of pairs. One
      proposition read twice would agree within the spread. Read at +s, each
      ladder is one rising curve (UNT at TLSA: Tulsa -6.5 30.5¢, -1.5 48.5¢;
      Tulsa +1.5 54.5¢, +6.5 71.5¢).
    - **What it touched.** 269 of the 567 spread claims, all statistical, all
      settled, written 2026-09-07 to 2026-09-29: MLB 139 of 293 (the model's
      number at the question's own -1.5, the price about +1.5), NFL 90 of
      171 and NCAAF 40 of 103 (19 with the price at the question's line and
      the model's number at the other sign, 111 with neither at it). 54 of
      the 113 recommendations were priced from one, their side, edge and
      size worked out across two contracts: MLB run lines 6, 8, 11, 14, 16,
      20, 25, 30, 32, 34, 38-42, 44, 48, 50, 51, 53-55, 57, 59, 60, 79,
      84-87, 93-98, 100, 106-109; NFL 62, 63, 66, 68-70, 73, 75, 77, 78;
      NCAAF 88, 90, 91. Their mean edge is +23.2¢, against +10.8¢ on the 40
      spreads priced off a home contract. E.g. rec 44 (TOR at BAL) was drawn
      "Toronto +1.5 · 66% · 36.5¢": 66% is Toronto +1.5's chance, and 36.5¢
      is the price of the contract the recommendation buys, "Toronto wins by
      over 1.5 runs" (Toronto -1.5). Rec 90, "Navy -6.5 · 80% · 50.5¢": 80%
      is Navy +6.5's chance, 50.5¢ the price of "Navy wins by over 6.5". A
      baseball forecast carries no margin distribution, so a claim at the
      right sign (+1.5, another rung than the question's -1.5) would have
      been refused: none of the 41 MLB run-line recommendations would exist.
      On the page: 53 of the 68 priced rows (shortlisted forecasts' last
      claim before the start) whose numbers are not at their words' line,
      and 47 of 60 such live pregame figures. The at-the-line record's
      market figures for spreads score those 269 prices against the other
      line's outcome, and `drift.py` matches a claim's ladder by the same
      reading (a home contract at -s and an away one at +s taken as one).
      The list of 30 September (FOLLOWUPS, "THE LIST") carries it: rec 88's
      and 90's "should be" figures are two contracts' numbers, and so are 47
      cards of its list B. No game-market pick on the record is taken.
    - **Today:** nothing upcoming carries one (UNT at TLSA is priced off the
      home contract TLSA2; WKU at NMSU has moneylines only). The next
      near-start look at an NFL or NCAAF spread whose rung nearest 50¢ is an
      away contract writes another, and the page draws it.
    - **Step A's own measurement, for when it resumes** (same copy):
      recommendations shown under another line's words, 66 -- the 54 above
      and 12 priced off a home contract at another rung than the question's
      (NFL 64, 67, 71, 72, 74, 76; NCAAF 89, 102-105, 111: rec 111 drawn
      "North Texas -6.5 · 76% · 50.5-51.5¢", each number North Texas
      +1.5's);
      priced rows 68 (15 + 53), live pregame figures 60 (13 + 47); opening
      reads at another rung than the question's, 628 reads on 167
      shortlisted forecasts (the question's own rung listed in 337 of them,
      not in 291). Lists: scratchpad `picknum\A\measure.json`,
      `measure2.json`.
    - **What needs your ruling** (LAW 3 keeps the stored rows as written, and
      the rulings do not say what a pick priced across two contracts is):
      (i) the writer -- read an away contract at +s (the stored number as it
      is) from the release, with a planting that escapes on the released
      code; a baseball look at an away contract then becomes the writer's
      ordinary refusal. (ii) The 269 stored claims and 54 recommendations --
      (A) void the recommendations by append-only rows (ruling 1 of
      2026-09-24's rule) and leave the claims out of the at-the-line record
      by a dated rule that names them, (B) label them and keep them counted,
      or (C) leave them as they are. (iii) The page, for a row priced off one
      (past slates' payload today; new ones until (i) ships) -- (A) refuse it
      by name (the API answers 500 for that slate), (B) draw it unpriced: the
      model's own number at the question's line, no price, no size, a
      sentence saying why; or (C) each number under its own contract.
      (iv) Step A waits on (i)-(iii): its gate check must know which line a
      price belongs to, and on the released reading it would pass rec 44's
      row. Or build step A now on the home contracts, with (iii)(B) for an
      away one, so rec 111 reads "North Texas +1.5" before its kickoff
      (2026-10-02T01:00Z)?
    Default until ruled: nothing built; step A not started.
    - **RULED (i) 2026-09-30 (built, 4b1facb); (iii) by step A's default
      (48c4ddd); (ii) 2026-10-05, A.2: "Void the 54 recommendations by
      append-only rows (reason: 'priced across two contracts, Q36'). The
      269 claims stay in the blind record ... and are excluded by a dated
      rule from every price comparison".** Built 2026-10-05 (START HERE,
      "Q36 (ii) BUILT"): 275 claims and 56 recommendations by the rule; the
      54 voided by `tools/void_two_contract_recommendations.py` after the
      release; recs 114 and 115 listed for the operator's word.
37. **A recommendation that buys the OTHER side of its question's words is
    drawn under the model's own side's words: its size, its edge and the
    green outline beside the other side's chance, price and payout. (Found
    2026-09-30 by pick-number step C's sweep, on one verified copy of the
    record made at 08:18Z and deleted after. Step C built findings 3, 4 and
    6 and the sweep's other two fixes; it stopped on this item alone.)**
    - **What happens.** A question's words name the side the model took; a
      recommendation buys the side the price makes worth buying, and that
      can be the other one (the old Today card's edge label said "on the
      other side"). On the board (from 2026-09-29) the row's pick and the
      tile draw the words' side's chance, price and payout and, beside
      them, the recommendation's size ("$15 · one flat unit"), its edge
      ("+2.1¢") and the green outline "clears the bar" -- the three that
      belong to the other side -- and nothing says which side they are. The
      Today card's size words and the taken list's "edge when marked" do the
      same (payload). The recommendation line now names the side bought
      (step C, finding 4); the row and the card do not.
    - **On the record: 16 of the 113 recommendations.** MLB 47 and 82, read
      at the question's own rung: the model's "Washington covers +1.5" at
      58%, the recommendation Detroit -1.5 at 37.5¢ worth 41.6% (+2.1¢); "Tampa
      Bay covers +1.5", the recommendation New York -1.5 at 37.5¢ worth 42.5%
      (+3.0¢). NFL 67-69, 71-74, 76-78 and NCAAF 89, 91, 102, 103, every one a
      spread read at the venue's line where it is not the question's
      (finding 2, question 36: the side flips because the line does) -- e.g.
      rec 76, "Las Vegas covers +15.5", bought New Orleans at the venue's line
      at 46.5¢ worth 84%. None is upcoming, and no game pick on the record is
      taken. None yet in a moneyline or a total; it can happen in any market
      whenever the model's side is priced above its own number.
    - **What needs your ruling** (the reading taken covers a number's line;
      for its side it would choose what a row labelled "Model's pick"
      headlines): (A) the pick names the contract the recommendation buys
      -- its words, chance, price, payout, size and outline -- and says
      beside it, in plain words, the model's own side and number (the
      reading's "the pick names the venue's contract ... the one the operator
      would buy", applied to the side); the label then heads a side the
      model did not take and would say so; (B) the row keeps the model's own
      side and its numbers, and the size, the edge and the outline are drawn
      with the words of the contract they belong to ("$15 on Detroit -1.5 at
      38¢"); or (C) such a recommendation is refused by name on the page
      (the API answers 500 for its slate) until one of those is built. For
      a spread it lands with step A in any case (steps B and C may not
      change how a spread row draws a priced number). Recommended: (A), the
      reading already taken for the line.
    - **Its prover's note (2026-09-30).** The edge now says whose it is where
      the page could say it without choosing a headline: the Today card
      labels the figure "on the other side" in every market (the label the
      card already carried, which read no side when neither side cleared
      the fee), and a moneyline or total tile draws "+2.1¢ on
      the other side" (none of the 16 is a moneyline or a total). A spread
      tile keeps its bare figure: its line is step A's (question 36), so all
      16 still draw the edge bare, with the size and the green outline, under
      the words of the side they did not buy. And the payout floor folds a
      recommendation by what the side it BUYS pays (step C's sweep), while
      the row states the payout of its words' side: on these rows the fold
      and the drawn payout are two sides' numbers (all 16 final; before step
      C the fold read the proposition's, which on these rows is also not
      always the drawn one). Nothing else of this question is built.
    Default until ruled: nothing built; the list is in FOLLOWUPS ("Every pick
    names its own side", THE SWEEP).
    - **Step A's note (2026-09-30).** Step A moved a spread row's words to the
      line its numbers belong to and kept the side it drew, so on these rows
      the words, chance, price and payout are now one contract's -- the
      words' side at the venue's line -- and only the size, the green
      outline and the edge (labelled "on the other side") are the other
      contract's. One is on a game still to start: rec 117 (ATL at NO, 6
      October 00:15Z) reads "MODEL'S PICK · ATLANTA +2.5 · 32% · 48c · 2.06x
      · $15" with the outline, and buys New Orleans -2.5 (68%, 51.5c). Still
      nothing built for this question.

38. **A game that really starts before its listed start: its in-play reads
    can now be claimed, and a finished pick priced from one. (Found by item
    1's prover, 2026-10-01; a pick-number finding, so it joins the queue
    first by the amended rule -- but it needs a ruling.)** Item 1 (ruled 30
    Sep: "the near-start run keeps every game until its start") keeps a game
    and claims its reads until its LISTED start instant, whatever its status
    says -- the status refusal it removed is what cut MLB closes to 35
    minutes out (statsapi reports warm-up as 'Live', mapped to 'in'). If a
    game actually begins BEFORE its listed start (a stale listing), its
    in-play reads before the listed start can now be claimed, and
    `recommend.for_predictions` (which skips only 'in', so it still prices a
    FINISHED game's pick) could draw that pick's side, price and edge from an
    in-play read. The status refusal only ever protected the ten minutes the
    live poll sees before a listed start. Not seen on the record.
    - **(A)** A game's start is the EARLIER of its listed start and the first
      poll that sees it truly under way (a score or a period recorded; MLB's
      warm-up 'Live' before the listed start does not count); reads and
      claims after it are never a close or a claim. Recommended.
    - **(B)** The listed start only, as item 1 built it (the ruling's words
      read as "its listed start").
    Default until ruled: (B), as built; nothing more.

## Rulings taken in your absence (2026-09-27, third set)

- **Q15's scan: what "against every append-only table" reaches.** Read by
  the stricter default (docs/briefs/2026-09-27-rulings-third-set.md, "How
  this brief is read"): the scan sees every replacing write in the shipped
  code and `schema.sql`, `UPDATE OR REPLACE` and a table-level `ON CONFLICT
  REPLACE` included; an append-only table is one the schema gives a
  no-delete or no-update rule; any other upsert must be in the register; an
  unreadable target counts as append-only. Tests and plantings are outside
  it.
- **Q15's release:** two commits (the predictions rules, the scan), one gate,
  released together -- Q14's precedent.
- **Q15's scan, as built (2026-09-27; FOLLOWUPS "No write replaces a row of
  an append-only table", READINGS TAKEN):** `desktop/` is read as well as
  the package and `tools/` (shipped code; it issues no SQL); docstrings are
  not read; an append-only table is one a DELETE or UPDATE rule is on,
  whatever its timing (22 tables, all BEFORE rules, the same set as a fresh
  build's); a part worked out at run time where a conflict clause or the
  verb goes counts as a replacing write, a run-time table name in a plain
  update does not; a write under OR REPLACE is also aimed at what its
  table's rules write; every key declared to replace on conflict counts; a
  register entry names one statement and carries a dated reason. `meta` is
  append-only by the brief's reading, so `db.set_meta`'s upsert is now an
  UPDATE and a plain INSERT, the same effect -- no ruling needed. Not built,
  for the operator: a scan for connection settings that switch rules off
  (the predictions prover's suggestion; the ruling names three statements).
- **Q15's scan, its prover (2026-09-27; FOLLOWUPS "THE PROVER"):** each
  reversible in one line. "May only shrink" is read literally: the register
  is frozen at its 35 entries of this date
  (`audit.UPSERTS_REGISTERED_ON_2026_09_27`), and an entry not among them
  fails however it is dated -- until then a later upsert with an entry dated
  2026-09-27 passed. So a later upsert (the board merge's included, if it
  adds one) is written plainly, as `set_meta` was, or the operator rules.
  (Reversal: drop the frozen check, and the register grows by review
  alone, as `ELAPSED_TIME_HELD`'s does.) A foreign key's action counts as
  a write, the reading the first build gave a rule's writes: SQLite's
  CASCADE, SET NULL or SET DEFAULT rewrites an append-only child when a
  replacing write removes or changes its parent (measured), so the write is
  aimed at the child whatever its conflict clause; no key declares an
  action today. A template is read as one wherever it is filled in, and a
  statement in pieces by each piece: the stricter reading of "a formatted
  part is unknown". Nothing refused on the shipped code by any of it.

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
