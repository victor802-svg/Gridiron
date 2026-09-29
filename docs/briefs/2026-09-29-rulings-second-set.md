# Brief — rulings, 29 September, second set

Saved before execution, as the standing contract requires. The operator's text
is unedited.

---

Rulings, 29 Sep (second set). Q32, first in the order, ahead of Q27.
Q32: corrections activate through the same gate as model fits. Every correction row is written inactive. Activation is its own dated append-only row, written only when the holdout bootstrap interval of the Brier improvement excludes zero, measured on distinct bets by the key, per forecaster; a tie goes to the uncorrected probability. The recalibration task never activates anything; fix its docstring to say what it does.
Fit 71: withdrawn now by a dated append-only row, reason "activated under the pre-Q32 rule: single holdout comparison, pooled rows". Then run the new gate on it read-only and report the interval. If it passes, activation is a new dated row; if not, it stays withdrawn.
First, before building: report read-only whether any forecast or recommendation already carries fit 71. Any that does stands as written and gets a label naming the correction it used; list them.
Speed: Q32 must be released before the next MLB pass that would apply fit 71, if you can do that without skipping a gate. If you can't, tell me the next pass's time and what it would change, and I'll rule.
Q32 must be released before the weekly recalibration on 5 October 13:00Z.
Order: Q32 → Q27 → board merge → re-read → Q25 + Q26 + Q29 → Q5 → Q10.

---

## The first step, done read-only (2026-09-29 05:46Z)

- **No forecast and no recommendation carries fit 71**, or any correction:
  `predictions` rows with a `correction_version` or `calibrated_prob`: 0;
  `recommendations` with a `correction_version` or `calibrated_fair_value`:
  0. Nothing to label.
- **No MLB pass can apply fit 71 before Q32 ships.** The MLB loader reads the
  regular season only (`gameType=R`); it ended on 27 September, and the
  record holds no MLB game that has not started. Every MLB pass since has
  been recorded "missed" and written nothing (predict:mlb 05:00Z and 18:00Z,
  final:mlb 21:30Z daily). The newest MLB forecast is 3088, 27 Sep 05:48Z.
- Q27's build, stopped part-way when this ruling put Q32 ahead of it, is kept
  on branch `q27-held` (80108c1; not proven, not gated); the worktree was
  returned to clean.

## How this brief is read (the conservative default; recorded in
## docs/REPAIR_STATE.md)

- **"Now"** for fit 71's withdrawal is the release: the withdrawal is a row of
  a table Q32 adds, so it is written by Q32's tool right after the release,
  through the read-only door's dry run first, and before anything else. Until
  then no pass can apply fit 71 (above).
- **The gate** is the model fits' shape (`fit_activations`, the activation
  door, the triggers holding the rule): a correction row is written with no
  activation; an activation row names the correction and carries its
  measurement -- the holdout (the category's latest settled questions, one
  per distinct bet on the key, time-ordered as the existing holdout is), n,
  the raw and corrected Brier on the same bets, the bootstrap 95% interval of
  the improvement -- and the rule refuses it unless the interval's lower bound
  is above zero; an interval touching zero is a tie and the uncorrected
  probability stands. A withdrawal is its own dated row with its reason. The
  correction in force for a category is read from these rows alone;
  `active_from` stays on the stored rows as history.
- **Fit 71's activation**, if the new gate passes it, is written by the same
  door as a new dated row, as the ruling directs; the report of the interval
  is written whichever way it goes.
- A fit labelled "fitted below its gate" (Q16/Q31) can never be activated:
  the new door and its rule refuse it.
