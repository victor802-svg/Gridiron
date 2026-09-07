# Close-out — GRIDIRON_THE_SHORTLIST (2026-09-07)

Against the brief saved at `docs/briefs/2026-09-07-the-shortlist.md`. One row
per phase, one per decision. D1 and D2 were the operator's and no ruling had
arrived, so each was handled as the standing contract says: by law, then
precedent, then the conservative default, recorded here.

| # | phase or decision | verdict | evidence |
|---|---|---|---|
| FIRST ACT | Save the brief before executing it | **DONE** | `docs/briefs/2026-09-07-the-shortlist.md`, committed before any code (98044e7), with a section on how each undecided question was read. |
| D1 | The run line | **BLOCKED** | Not decided here. Retiring a market writes a permanent dated line into the registry and this codebase does not un-retire; the brief's own recommendation, option (a), is the only one that decides nothing a later ruling could not still decide. The run line is still asked, still accrues toward its own hundred, and now simply competes for a place on the page like every other question. Nothing built here has to be undone if the operator later rules (b) or (c). |
| D2 | The caps | **DONE** under the brief's own proposal | `config.SHORTLIST_CAPS` dated 2026-09-07: baseball and basketball 20 a day, football and college 30 a week, the fight card whole. Environment-overridable like every other cap, so a ruling changes one constant. The brief states these are the numbers unless the operator says otherwise. |
| S1 | The rank, declared | **DONE** | `gridiron/shortlist.py` with three inputs declared and dated in config: confidence, completeness read off the frozen payload's own coverage figure, and the edge. Stored in `prediction_ranks`, append-only, with the factor set and ranker version on every row and a trigger refusing a rank stamped at or before its own prediction. Eleven tests. |
| S1 (the gate) | The edge weighs nothing until its market has earned a verdict | **DONE** | `config.RANK_EDGE_GATE`, and `audit.edge_weight_faults` does not take the ranker's word for it: it recomputes every stored score from the components stored beside it and refuses a row whose number cannot be reproduced. A planted rank that weighted an ungated edge is caught by name. |
| S2 | The shortlist, and the rest | **DONE** | The page leads with the shortlist and puts everything else behind the control it already had, carrying the count in the server's own words ("the other 40"). Nothing is dropped: every card stays on the payload, marked, and each carries a sentence saying what put it there. Rendered at 1100 and 390 pixels: 20 in front, 40 behind, 60 after the control is opened. |
| S2 (the words) | Never a bet, a play, a lock or value | **DONE** | `audit.ADVICE_WORDS` gains "best bets", "top plays" and their neighbours; `audit.slate_advice_faults` scans the shortlist's own strings and every ordering line on every card; a planted "today's top plays" is caught. |
| S3 | Score the ranker itself | **DONE** | `calibration.ranker_comparison`: two curves per market, what led each slate against what it outranked, each with its own N and the same hundred-resolution gate. The sentence for a ranker that does not separate is written out in advance, in full, so a disappointing result has words waiting for it rather than a decision to make in the moment. Rendered as its own Record section. |
| S4 | Backfill the standing predictions | **DONE** | `tools/backfill_ranks.py` ranked all 1,142 rows on the record, every one marked `backfilled = 1` and excluded from the comparison in S3. The page has an ordering on day one; the evidence is not padded by it. |
| Close-out | This table, the follow-ups and the gate | **DONE** | Below, with one gate step that cannot pass today and the reason it is not this work's. |

## Rulings taken in the operator's absence

1. **D1 is left undecided rather than guessed.** See the table. The market is
   buried by the ordering, which is reversible; retiring it is not.
2. **The weights are 0.5 confidence, 0.3 completeness, 0.2 edge**, written from
   first principles and not tuned. Confidence weighs most because it is the
   only input that is entirely the model's own answer; completeness next
   because it is about the evidence rather than the answer; the edge least, and
   only once its market has earned a verdict.
3. **An input out of play is renormalised away, never scored as a zero.** An
   ungated or unquoted edge is an absence; scoring it zero would say the model
   agrees with a price nobody published, and it would also mean the shortlist
   silently reordered itself the day a market's gate opened.
4. **The selection is decided when the rank is written and stored on the row.**
   Recomputing it at read time would let a later change to a cap rewrite what a
   reader was shown last week, and the comparison that scores the ranker would
   then be scoring a shortlist nobody ever saw.
5. **Only a standing row can lead a slate**, through
   `calibration.standing_row_clause` -- the same door every count on the Record
   page uses. This was a defect the backfill exposed rather than a design
   decision made in advance; see below.
6. **A shortlist may come in under its cap.** The per-game ceiling and the
   round robin across kinds of question can both bind before the cap is
   reached, and the page then says "the 18 clearest questions" rather than
   padding the list to twenty. Reported rather than corrected: the ceiling
   exists to spread the list across games, and relaxing it to hit a round
   number would defeat the point of having it.
7. **The ranker's version was bumped rather than any row rewritten.** r1 is
   still on the record. A rank is append-only, and a version that was wrong is
   part of the history of getting it right.

## What the backfill caught

Ranking the record's own past found a real defect within a minute of the first
run: the selection was made over every stored row, superseded ones included.
The early forecast of a question the final pass later answered again was taking
places on shortlists the page never shows it on. One baseball day of fifteen
games, with a cap of twenty, led with **eleven** -- nine of the twenty being
rows the record does not grade. The selection now runs through the record's own
standing-row clause and the same slate leads with eighteen.

That is the argument for S4 in one paragraph. A formula that had only ever seen
tomorrow's slate would have looked correct for weeks.

## The gate, today

`tools/verify.py` cannot pass today, and the reason is not this work.
`audit.llm_prose_faults` renders each sport's current slate and scans the
reasoning on any LLM card it finds; **it reports "I checked nothing" as a fault
rather than a pass**, deliberately, because the hole it exists for was
invisible for weeks. No slate has been predicted on 2026-09-07 -- the daily
predict task runs at 11:00 local -- so there is no card to scan, and both the
scan and its planting are red.

Verified red on `HEAD` with every change of this session stashed. Nothing was
run early to turn it green: writing predictions outside their schedule to
satisfy a guard is manufacturing evidence, which is the failure this project's
whole apparatus exists to prevent. The gate should be re-run after the day's
first predict task, and the standing hole -- that a record-dependent scan is
red every morning until then -- is recorded in `docs/FOLLOWUPS.md`.

The gate's own summary, run at the end of this session:

| step | verdict |
|---|---|
| 1. test suite | FAIL — two tests, both the empty-slate scan |
| 2. planted violations | FAIL — 208 of 209 caught, the escape being the same scan |
| 3. one week end to end | PASS |
| 4. live forward week | PASS |

The two failing tests are `test_distributional.py::test_the_llm_view_shows_no_code_name`
and the planting harness that runs the same scan. Everything else passes,
including both checks this phase added and the 208 other plantings.
