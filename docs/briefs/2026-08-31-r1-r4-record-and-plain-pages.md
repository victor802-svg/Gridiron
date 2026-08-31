# Brief — R1–R4: the record, plain reasons, plain pages

*Pasted 2026-08-31. Saved verbatim as the first act of the session, per the
process rule added to MENTOR.md §3 on the same day: a brief that exists only in
a transcript cannot be checked against what was built from it.*

---

Read CLAUDE.md, docs/MENTOR.md, docs/mockup/gridiron_compact.html
and FOLLOWUPS.md (the deferred K3 entry). Four phases, four
commits, push after each, /closeout at the end.

=====================================================================
PHASE R1 — the tier table IS the record (commit "r1: tier table")
=====================================================================

The calibration buckets and the tier chips are the same partition
(LEAN 50-60, SOLID 60-70, STRONG 70%+). Stop drawing them as a chart
and show them as the table the operator already reads on every card.

The Record tab, per sport, leads with THE TIER TABLE:

  Tier    Settled   Right   Claimed   Actual   Verdict
  LEAN       24      12      55%       50%     "a coin flip so far"
  SOLID       0       —       —         —      "unproven — 0 of 20"
  STRONG      7       6      83%       86%     "about as good as it claims"

Rules, all as dated constants in one place:
- Below 20 settled, the row shows "unproven — N of 20" and NO
  percentages (Law 4). No exceptions, no italics hinting at a
  number.
- Verdict words from a fixed rule on (actual − claimed):
  within ±3 → "about as good as it claims";
  actual lower by 3-8 → "overconfident by N points";
  lower by >8 → "much more confident than it should be";
  higher by >3 → "better than it claims".
  Plain-words scan runs over the verdict text.
- One sentence above the table, the largest-gap sentence in this
  vocabulary: "STRONG picks have been right 86% of the time over 7
  — about as good as they claim." Never the flattering row.
- Per sport, never merged (Law 6). Per market type available as a
  filter; default is the sport's headline market.
- Sourced from the SAME bucket math the tier chips use — one
  implementation; a test asserts the table's numbers equal the
  chips' to the decimal.

Below the tier table, in this order, each a small plain table:
- MARKET: "So far the market has been better than the model — its
  guesses have been closer by X points on N picks." When the edge
  figure is gated: "Model vs market on big disagreements: 6 of 100
  settled. 94 more before this can be shown." Words, then the two
  Brier numbers small beneath for anyone who wants them.
- RECORD: wins / losses / voids by market type, with N.
- The permanent line under RECORD stays: win rate alone cannot tell
  you whether the probabilities are honest.

THE CHART MOVES, not deleted: the calibration chart, the over-time
strip, and the Brier/log-loss detail go to the "How the model
works" page (Factors) for anyone auditing. The Record tab links to
it once.

=====================================================================
PHASE R2 — reasons in three sentences (commit "r2: plain why")
=====================================================================

K3, sized to the ruling: AT MOST THREE SENTENCES per pick.

- Sentence 1: the biggest reason, with its size in words.
- Sentence 2: the second reason (or the strongest thing pulling the
  other way, if it is larger than the second supporter).
- Sentence 3 (optional): the market clause where a line exists —
  "The market has Tampa at 48%; the model leans harder on the
  pitching." Where no line: omit; do not pad.
- A factor excluded as unmeasurable is a clause, not a sentence:
  "…(travel couldn't be measured for this game)."
- WHY-TEMPLATES live in the registry beside each factor's rationale
  — a plain sentence with slots. A factor without a template fails
  a test. The template names the THING in plain words, never the
  factor: "{team} has been the clearly better team lately", not
  "net rating".
- Generated server-side in language.py (one implementation);
  ordering and directions derived from the same contributions the
  K1 arithmetic guard verifies — plant a mismatch between words and
  numbers and show it caught.
- Contribution bars, the decomposition sentence, raw values and
  rationales move to the Factors page under "How the model works".
  The expanded row shows: rail, gap, the three sentences, the tier
  line, and one link. Nothing else.
- Plain-words scan over every generated WHY.

=====================================================================
PHASE R3 — the rest of the pages (commit "r3: everywhere plain")
=====================================================================

Sweep every remaining page against the same standard — a first-time
reader understands it without decoding:
- Factors page ("How the model works"): each factor shown as its
  plain-words name first, the code name small beneath, its one-line
  rationale, and its earned score with N in words ("helps a little
  · 412 picks"). This is the one page allowed to be dense.
- Versions: sets named by when they began (already), plus one line
  per set on what changed, in words.
- History: verdict chips and sentence rows (already); confirm the
  tier chip appears on each row.
- Schedule: task names in words ("Fetch results", "Settle picks",
  "Predict MLB"), never task ids; "!! has never run" stays blunt.
- Digest: same three-sentence reasons on the resolved rows.
- Every table: sample size in words or numerals on every row that
  makes a claim; no bare dashes.

=====================================================================
PHASE R4 — look, then verify (commit "r4: qa")
=====================================================================

RENDER FIRST, then tests — the last three sessions each found faults
only a screenshot showed:
1. Headless renders: Record tab with the tier table (a sport with
   real settled rows — MLB — and one at zero), one expanded pick
   with three sentences, the Factors page, at 1100px and 390px.
   Compare against the mockup's language; anything a stranger
   would have to decode gets fixed before commit.
2. Full suite, no skips; plantings: a tier row below gate showing a
   percentage; verdict words disagreeing with the gap rule; a
   factor without a why-template; WHY text disagreeing with
   contributions; table numbers disagreeing with chip numbers.
3. Plain-words scan clean over all routes including generated WHYs
   and verdict sentences.
4. verify.py green; FOLLOWUPS: K3 entry closed with this commit;
   anything deferred dated. /closeout with the verdict slots empty.

---

## Ruling on R2, given after R1 shipped

> Ruling on R2: delta only, K3 stands. Keep the phrase templates.
> Two changes:
> 1. Sentence budget of three: biggest reason; second reason or the
>    strongest opposer if larger; market clause as sentence 3 only
>    where a line exists, otherwise omit.
> 2. Readability without direction in templates: each phrase template
>    gets two renderings chosen by the SIGN at compose time ("SF has
>    been the better team even against tougher schedules" vs "the
>    weaker team"). The template asserts nothing; the composer picks
>    the verb from the number. If you judge even that risks the
>    sign-flip failure, improve the composer's grammar alone instead.
>    Read-aloud is the bar: if it sounds like a spreadsheet talking,
>    it fails.
> Process, from now on: first act of every session is to save the
> pasted brief to docs/briefs/<date>-<name>.md and commit it. Add a
> line to MENTOR.md §3: any rule with a numeric boundary is tested AT
> the boundary (the 3.0000000000000027 case).
> Then R3 and R4 as briefed. Render before committing. Push each
> phase. /closeout.

## What was corrected in R1, and why

R1's opening premise — that the buckets and the tiers are the same partition —
is false. There are four buckets and three tiers, because STRONG spans 70-80%
AND 80%+. A single STRONG row is the merge LAW 4 forbids and it flatters in a
knowable direction. The table was built with STRONG appearing twice, labelled
with its band, and a planted violation keeps it that way. See `54dbfd4`.
