# Calibration corrections — five phases

Pasted verbatim, 2026-08-31.

> Given mid-turn, while the CFB probe (B1) was running. See the note at
> the foot of this file for how the two briefs were ordered.

---

FIRST ACT: save this brief to docs/briefs/<date>-calibration.md and
commit. Read CLAUDE.md, docs/MENTOR.md. Five phases, push each.

=====================================================================
PHASE C1 — the correction engine (commit "cal 1: engine")
=====================================================================

- METHOD: Platt scaling (two-parameter logistic on the claim's
  log-odds) per category. Chosen over isotonic because categories
  activate at N=50 where isotonic overfits steps; state this in a
  comment. Implementation transparent and inspectable like the
  base model — coefficients stored, no black box.
- CATEGORY = (sport, market_type, forecaster). Never merged (Law
  6 applies within the correction). The statistical and LLM
  forecasters each earn their own correction.
- TRAINING SET: settled, non-void predictions in the category,
  strictly resolved BEFORE the fit timestamp. A planted test: a
  correction whose training query can reach an unresolved row, a
  void, or any game/market table fails by name — the engine may
  touch predictions' claims and outcomes and NOTHING else.
- calibration_corrections table: category, version, fitted_utc,
  n_train, coefficients, train_brier_raw, train_brier_corrected
  (labelled in-sample), active_from. Append-only like everything.
- REFIT weekly by the scheduler once active; each refit is a new
  version. Corrections apply at WRITE TIME to new predictions
  only; nothing already written changes (Law 3).

=====================================================================
PHASE C2 — activation, honestly (commit "cal 2: gates")
=====================================================================

- A category's correction ACTIVATES only when: n_train >= 50, AND
  a time-ordered holdout check passes — fit on the earliest 80% of
  settled rows, verify Brier improves on the latest 20% (labelled
  what it is: a thin forward-shaped check, not proof). Below
  either bar the category stays raw and the record says why:
  "corrections begin at 50 settled — 31 so far."
- Once active, calibrated_prob feeds EVERYTHING downstream that
  consumes a claim: tier assignment, the props 70% floor, sort by
  confidence, the pick sentence's percentage. That is the point —
  the floor and the tiers should run on earned numbers. State the
  consequence in the close-out: corrected claims are mostly lower,
  so prop slates may shrink; that is honesty arriving, not a
  defect.
- THE CORRECTION IS GRADED: forward predictions written under
  version v track their own calibration curve, so "did v1 help"
  is answerable with N. Surface per-version forward Brier beside
  the in-sample figure, clearly labelled.
- Plantings: an active correction with n_train < 50; a correction
  applied retroactively to an existing row; calibrated_prob shown
  anywhere without model_prob stored beside it in the row; merged
  categories.

=====================================================================
PHASE C3 — line drift (commit "cal 3: drift")
=====================================================================

The question D1 could not test: when the model disagrees, does the
market later move toward it (model sees signal early, loses to
late news) or away (market's information beats the factors)?

- A second snapshot near start time: the existing refresh task
  fetches closing-adjacent lines for games starting within ~2h;
  market_snapshots gains a kind field (open_at_predict / near
  start). No schema break to the first snapshot's meaning.
- Both snapshots happen after the prediction row exists — the
  blind structure is untouched; assert it in the closure audit.
- THE DRIFT REPORT, gated at 50 drift-pairs per category: among
  disagreements >= 5 points, the fraction where the line moved
  toward the model, the mean signed movement, and the plain
  sentence: "When the model disagreed, the market moved toward it
  X% of the time over N games." Below the gate: the count and
  nothing else. No conclusions in code comments — the number
  decides later.

=====================================================================
PHASE C4 — the record speaks earned numbers (commit "cal 4: ui")
=====================================================================

- The pick card's percentage becomes calibrated_prob once a
  category is active, with the raw claim one tap away in the
  expanded row: "model's raw claim: 74% · shown as 66% — what
  claims like this have been worth over 120 settled." Plain-words
  scan over the sentence.
- The tier table gains one line per tier once corrections are
  active: "shown numbers are earned: claims are adjusted by the
  record (v2, fitted Sep 21, 143 settled)."
- History rows show the number that was displayed at write time
  (calibrated if active) with raw available in the expansion —
  the record shows what the operator actually saw.
- Before any category activates, nothing changes visually; the
  Record tab notes "corrections begin at 50 settled per category"
  in the same voice as the gate language.

=====================================================================
PHASE C5 — verification (commit "cal 5: qa")
=====================================================================

1. Full suite, no skips; all plantings named and caught, including
   C1's training-isolation planting and C2's four.
2. A walk-forward rehearsal on the ONE category with real volume
   (MLB moneyline, 31 settled): show the engine refusing to
   activate at n=31 with the correct message. Then a synthetic
   category at n=60 proving the 80/20 holdout gate both passes a
   genuine improvement and rejects a planted non-improvement.
3. Renders: a card in a raw category (unchanged), a synthetic
   active-category card showing earned-number language, the tier
   table line, desktop and 390px.
4. verify.py green; the drift snapshot task registered and its
   first real pairs visible; /closeout with verdict slots empty;
   FOLLOWUPS: the third-forecaster item dated "after gates fill",
   and the drift question's read-date.

---

## How this was ordered against the CFB brief

This arrived mid-turn, during CFB phase B1 (the read-only probe).
"Do This next" is taken at its word: the calibration build runs now,
and CFB resumes after it.

B1's measurements so far are written up in `docs/CFB_FEASIBILITY.md`
and that file is marked **INCOMPLETE**, with the questions still
unmeasured listed by number. Nothing was built on them, no CFB code
exists, and the probe was read-only throughout — so the pause costs
nothing but the fetches already cached.
