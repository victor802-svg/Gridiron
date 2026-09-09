# Close-out — the shortlist ranks priceable questions first (2026-09-09)

Against the brief in `docs/briefs/2026-09-09-priceable-first.md`.

| item | verdict | evidence |
|---|---|---|
| priceable first, inside each sport's cap | **DONE** | `shortlist.select` fills the priceable group before the rest; three tests, the key one proved on the unfixed code |
| order inside each group unchanged | **DONE** | r2's score, weights and tie-breaks untouched; the round robin and the per-game ceiling are the same code, threaded across both groups |
| display ranking only | **DONE** | no forecaster, correction or claim touched; the only writes are 1,393 new `prediction_ranks` rows under a new version |
| dated in config | **DONE** | `config.PRICEABLE_FIRST_FROM = "2026-09-09"`, and `RANKER_VERSION` moved r2 → r3 |
| the 21st's empty-top-group count in two spans | **DONE** | `tools/empty_bar.py`, split at the constant; `docs/FOLLOWUPS.md`'s 21 September reading list points at it |
| effect today: three questions on `2026_01_NE_SEA` | **PARTIAL** | one of the three appears. The other two cannot, for two different reasons, both measured below |

---

## What changed on the slate

Tonight's NFL slate, before and after, same cap of thirty:

| | before (r2) | after (r3) |
|---|---|---|
| point spread | 4 | **15** |
| moneyline | 4 | **15** |
| player props | 22 | **0** |
| questions the venue lists | 8 of 30 | **30 of 30** |

That is the ruling's whole intent, and it is the largest single change to what
the first screen shows since the card was redesigned. Twenty-two of thirty
places were going to questions that cannot become a recommendation.

## The three questions on tonight's game

**`Seattle to win` is on the slate.** Shortlist place 17, carrying the opening
read — `PAYS 1.63x · read 8:27 PM · re-read near kickoff`. Screenshots at both
widths.

**`New England covers +3.5` is not, and the ruling is why.** The ruling keeps
the order inside each group exactly as SHORTLIST set it, and that question
ranks **23rd of the 48 NFL spreads** by score. The round robin across two
priceable kinds takes fifteen spreads; the fifteenth scores 0.3366 and this
one scores below it. Nothing about the game it belongs to enters the ranking,
because nothing in the ruling says it should.

**THE TWO READINGS, and this one is the operator's:**

* *As written.* Priceable first; inside each group, confidence and
  completeness. Then a low-scoring question on tonight's game loses to a
  higher-scoring question on next Sunday's, and the slate is a week's worth of
  questions ranked by score. **This is what is built.**
* *As the reason implies.* "The three priceable questions on tonight's only
  game" suggests IMMINENCE should count — that a game starting in twenty hours
  should outrank one starting in six days. That is a fifth rule and the ruling
  does not state it, so it is not invented here.

The slate is Week 1, which runs to 15 September; tonight's game is one of
sixteen on it. If the intent is that the game being played today leads the
list, that is a rule about kickoff proximity and it is the operator's to make.

**The total does not exist.** Not for this game and not for any: **the record
has never held a single NFL total**, against 133 for college football and 171
for baseball. `total` is declared in `config.SPORT_MARKETS["nfl"]`, the tab
renders and reads "Total points 0", `KXNFLTOTAL` resolves 40/40, and nineteen
contracts are open on tonight's game. The venue prices it, the ticker builder
reaches it, and nothing asks the question. Recorded in FOLLOWUPS with what
would settle it; forming the question is a forecaster change and this ruling
says none.

## How it is built

`select()` gained one line — two `_fill` passes instead of one — and lost
nothing. `_fill` is the previous body verbatim, with `chosen` and `per_game`
threaded through, **so the per-game ceiling spans both groups**: a fixture
cannot take three places for being priceable and three more for not being.
There is a test for exactly that.

**Which read counts as "an open read at the venue".** The ruling's words admit
two readings and the reason settles it:

* strictly `read_kind = 'open'` — but a game inside the two-hour near-start
  window has had its near-start read and may have no opening one, so the
  questions closest to kickoff would rank as UNPRICEABLE. That is backwards.
* any venue quote for the game and market — the venue lists this question.
  This is what "a question the venue does not list cannot become one" asks
  for, and it is what is built.

Stated here so it can be overruled in a line.

**Nothing is stored about priceability**, and it does not need to be: the
decision it produced is already in `prediction_ranks.shortlist_place` under
version **r3**, and r2's rows are untouched beside it. That is the two-span
mechanism the 21st needs, in the table, without a migration.

## The re-rank

`shortlist.rank_rows` wrote 1,393 r3 rows — every prediction in the record,
none rewritten, r2 left exactly where it was. 446 shortlisted across all
sports and slates. A rank is append-only and versioned precisely so that a
change to the ordering is a new measurement rather than an edit to an old one.

## Proved on the unfixed code

`test_a_question_the_venue_lists_outranks_a_better_one_it_does_not` builds two
unpriceable questions at 0.97 and two priceable ones at 0.55 against a cap of
two. With the two passes it picks the priceable pair. With the one-pass
selection planted back in it fails — `assert [1, 3] == [3, 4]` — which is the
loud unpriceable prop taking a place. Restored; all seventeen shortlist tests
pass.
