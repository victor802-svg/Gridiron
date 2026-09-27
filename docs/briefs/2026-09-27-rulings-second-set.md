# Brief — rulings, 27 September, second set

Saved before execution, as the standing contract requires. The operator's text
is unedited. The board-merge checklist that came with it is saved on its own,
in `2026-09-27-board-merge.md`.

---

Rulings, 27 Sep (second set).
Q12: placed as you proposed: after the Q9 labels, before the flaky tests.
Q14: (B). Every count on the Record page that states a gate distance is rebuilt per forecaster (per tier for UFC) and per distinct bet, through its record's standing rule. Three commits, each with a planting that passes on the unfixed code: priced_scorecard, drift.report, horizon.market_outlook. They land before the re-read.
Q5: (A), scheduled after the board merge. Until then ELAPSED_TIME_HELD stays as is and may only shrink; the merge adds no fixed wait. After the merge: the app emits a render-finished signal, every fixed wait is rebuilt on it, on a held-and-released response or on page.clock; upper-limit timeouts stay. Its own step, with renders.
Order: Q13 → Q9 labels → Q12 → Q14 (three commits) → flaky tests → board merge → Q5 → Q10 → re-read (not before 28 Sep 15:00Z).

---

## How this brief is read

**"A planting that passes on the unfixed code"** means what every planting in
this repository has meant: the planted violation gets through on the unfixed
code (it ESCAPES there) and is caught by name on the fix. A planting that
passed its check on the unfixed code would prove nothing about the fix.

**Q14's three counts** are those of question 14:

- `calibration.priced_scorecard`: the priced forecaster's "settled
  comparisons";
- `drift.report`: the learning panel's media-line drift;
- `horizon.market_outlook`: the blind record's outlook beside each curve.

Each is rebuilt through its own record's standing rule, per forecaster, per
tier for UFC, and per distinct bet.
