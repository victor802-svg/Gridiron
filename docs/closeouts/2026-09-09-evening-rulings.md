# Close-out — the rulings of 2026-09-09 (evening)

Against the brief in `docs/briefs/2026-09-09-evening-rulings.md`.

| ruling | verdict | evidence |
|---|---|---|
| 1. no imminence rule; record the question and the answer | **DONE** | dated in `shortlist.select`'s docstring and in FOLLOWUPS under "ASKED AND ANSWERED", with the numbers that prompted it |
| 2. any venue quote counts as listed; ratified, dated | **DONE** | dated in `shortlist.rank_rows` beside the query and in `config.PRICEABLE_FIRST_FROM`; FOLLOWUPS records why the strict reading was wrong |
| 3. the order of the next two jobs | **DONE as a record; neither started** | both briefs saved verbatim; FOLLOWUPS carries the order and the conditions each opens on |
| 4. post-window capture at 3:20 PM Pacific | **OWED** | the window opens 2026-09-09T22:20Z; it is 00:21 Pacific as this is written |

**No behaviour changed today.** r3 already ranked the week's slate with no
imminence term, and `rank_rows` already counted any venue quote as listed.
What changed is that both are decisions with dates on them rather than a
session's reading waiting for an answer — which is the point of CLAUDE.md's
"Who reads a law", applied to the answer as well as to the question.

---

## Ruling 1 — the question, and why it is written down

`New England covers +3.5` ranked **23rd of the 48 NFL spreads** and the round
robin takes fifteen; the fifteenth scored 0.3366. The same game's moneyline
made place 17. So the slate showed one of the two priceable questions on the
game kicking off in twenty hours while carrying questions on games six days
out.

That looks like a defect and is not one. **The shortlist is the week's**, and
a question that misses the cap has been out-scored — which is what the cap is
for. The operator refused an imminence term.

**It is recorded as a question with an answer, not as a fact**, because the
evidence that prompts it will still be sitting there next week: a reader
comparing the slate against tonight's fixture list will ask again. FOLLOWUPS
says what was asked, what was answered, on what date, and what the answer does
NOT touch — the two priceable groups, which are about whether a question can
become a recommendation at all rather than about when it settles.

## Ruling 2 — the reading, and the trap in the other one

"An open read at the venue" admitted two readings and the wider one is
ratified: **any venue quote for the game and market**.

The strict reading (`read_kind = 'open'`) fails in the case that matters most.
A game inside the two-hour near-start window has had its near-start read and
may have no opening one — so the questions CLOSEST to kickoff would have
ranked as unpriceable and sunk below questions on games a week away. The rule
meant to put actionable questions first would have buried the most actionable
ones.

**The absence of a `read_kind` filter in `rank_rows` is now load-bearing**, and
the comment beside the query says so, because an absence that looks like an
oversight gets "fixed" by the next reader.

## Ruling 3 — recorded, not started

Neither job is begun and neither condition is met: the crosswalk opens after
tonight's game settles, and the total opens after the crosswalk. Both briefs
are saved verbatim so the next session starts from the operator's words rather
than from a summary of them, and FOLLOWUPS carries the order.

The older NFL-totals entry stops asking an open question and points at the
scheduled job. What it keeps is the check that would have found it: nothing
refuses a market declared in `SPORT_MARKETS` that has produced no prediction —
`venue_series_faults` pointed the other way. GRIDIRON_NFL_TOTAL fixes this one
instance; that check would find the next one.

## Ruling 4 — still owed, and why it cannot be taken yet

`2026_01_NE_SEA` kicks off 2026-09-10T00:20:00Z. `NEAR_START_HOURS` is 2.0, so
the window opens **2026-09-09T22:20Z — 03:20 PM Pacific**. This close-out is
written at 00:21 Pacific. The capture is fifteen hours out and is not claimed
as done.
