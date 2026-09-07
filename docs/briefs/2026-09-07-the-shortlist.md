# Brief — GRIDIRON_THE_SHORTLIST (drafted 2026-09-07, awaiting operator rulings)

Saved verbatim before any of it was executed, as every brief here is. The
operator's rulings on D1 and D2 had not arrived when the work started; how the
work proceeded without them is recorded at the end, under "How this brief is
read".

---

The slate is unreadable. Baseball asks roughly seventy questions a day — three
team markets on every game plus twenty-five props — and the operator's own
words are that it is "way too much." The convention this project already
holds says the same thing in the config's own comment: *a reviewable slate
beats a large one, and a forecast nobody reads is not a forecast anybody can
check.* Seventy a day is not reviewable. Twenty is.

**WHAT THIS BRIEF DOES NOT DO: it does not predict less.** Ruled by the
operator 2026-09-07: the model keeps asking every question it asks today.
Every market is still 100 resolutions from being allowed to claim anything
(LAW 4), MLB's regular season ends within weeks, and cutting the slate to
twenty would make the record grow three times slower in the one sport that
resolves daily. What changes is what the Picks page *puts in front of a
person*: a declared, dated, deterministic ranking that surfaces a shortlist
and files the rest behind it.

A rank is not a claim, not an edge figure, and not advice. It is an ordering,
and this brief's central requirement is that it be **recorded, so that it can
itself be scored**: does the shortlist actually calibrate better than the
questions it outranked? Nobody knows. Recording the rank is what makes that
answerable instead of a matter of taste.

---

## DECISIONS required from the operator

**D1 — the run line.** The operator asked to drop MLB's spread outright.
**This brief declines to do that as asked, and asks for a different ruling.**
The stated reason is that two run-line bets lost. Two. Retiring a market on a
P&L sample of two is precisely the pattern LAW 2 exists to forbid — a verdict
found by looking at outcomes rather than at the instrument — and the registry
would carry that reason forever. Three options, operator picks one:

  (a) **Leave it asked, let the shortlist bury it.** The market keeps
      accruing toward its own n=100; it simply stops appearing on the page
      unless it ranks. Recommended: costs nothing, decides nothing early.
  (b) **Retire it on a structural reason, stated honestly** — e.g. that a
      fixed ±1.5 rung against a measured MLB margin SD of 4.71 asks nearly
      the same question as the moneyline on most games, which is redundancy,
      not refutation. If the operator rules this way, the registry note says
      redundancy and does not mention any bet.
  (c) **Retire it by operator ruling, reason recorded as "operator ruling"**,
      the same shape as the batter-home-runs entry of 2026-09-05.

  For the record: **batter home runs is already retired** (RETIRED_MARKETS,
  2026-09-05). The operator's request for it is already satisfied; MLB asks
  seven markets, not eight.

**D2 — the caps.** Proposed, all declared and dated in config, all
overridable by environment variable as the existing caps are:

  | sport | slate | shortlist |
  |---|---|---|
  | MLB | day | 20 |
  | NBA | day | 20 |
  | NFL | week | 30 |
  | CFB | Saturday | 30 |
  | UFC | card | the full card (a card is already small) |

  The operator said football and college may run larger; these are the
  numbers unless he says otherwise.

---

## PHASE S1 — The rank, declared

A new module computes one number per written prediction, **after the blind
window has closed and market snapshots exist**. It reads the frozen
prediction row and its snapshot; it never touches the probability (LAW 3),
and it is not in the prediction import closure (LAW 1).

Three inputs, ruled by the operator, combined by a declared and dated formula
in config the way `RATING_DECAY` is declared — written from first principles,
**not tuned until the shortlist looks good**, which would be LAW 2's
discovery by another name:

1. **Confidence** — how far the model's probability sits from 50.
2. **Completeness** — whether the factor vector was whole. A game whose
   starting pitcher was unannounced is already ABSENT-not-zero in this
   codebase; that absence now costs rank rather than being invisible. This is
   the input most likely to raise real quality, because it is about the
   evidence rather than about the answer.
3. **Edge versus the venue's line** — *gated*. See below.

**THE EDGE INPUT IS GATED, AND THIS IS THE MOST IMPORTANT LINE IN THE BRIEF.**
Ranking by disagreement with the market sounds like the sharpest possible
filter and is, today, the most dangerous one: with six resolved predictions in
the whole project, the questions where this model most disagrees with a
liquid market are overwhelmingly the questions where **this model is most
wrong**, and a shortlist built on them would systematically surface its own
worst errors and label them the best of the day. So: **edge contributes to
rank only for a market that has passed its own n=100 gate.** Below the gate
the edge number is still computed, still displayed beside the pick, and
carries zero weight in the ordering. The gate opening is what turns it on,
per market, automatically. `assert_edge_weight_gated` refuses a rank that
weighted an ungated market's edge, and `tools/guards/plant.py` plants one.

## PHASE S2 — The shortlist, and the rest

- The rank and its three component scores are **written to the database, in
  their own append-only table, keyed to the prediction id**, with the
  factor-set version and a `ranker_version` string. A rank is a measurement
  and gets the same treatment as every other measurement here.
- The Picks page shows the shortlist for the day (or week, per D2) and puts
  everything else behind one plainly-worded control — *"the other 48"*, not a
  "show more" that reads as decoration. **Nothing is hidden.** A prediction
  that was made and is not on the shortlist is one click away, and the count
  is on the face of the control, because a page that quietly dropped fifty
  questions would be lying about the record.
- **The shortlist is never called a bet, a play, a lock, or value.** The
  plain-words scan gains "best bets", "top plays", "lock" and "value" and a
  planting proves the scan fires. It is "Today's twenty", or "the twenty
  clearest questions", and the page says in one line what put them there.
- Cap fill respects the existing per-game ceiling logic so one marquee game
  cannot eat the shortlist, and round-robins across markets so the list is
  never twenty of the same question type.

## PHASE S3 — Score the ranker itself

The payoff, and the reason the rank is stored rather than computed on the fly.
Add to the Record page, per sport and market, gated behind the same n=100 rule
as every other figure:

- The calibration curve and Brier score of **shortlisted** predictions versus
  **not-shortlisted** ones, each with its N.
- If the shortlist does not separate — if the twenty score no better than the
  fifty they outranked — that is a real finding about the ranker, and it is
  written into FOLLOWUPS in those words rather than quietly retuned. A ranker
  that does not rank is worth knowing about early.

## PHASE S4 — Backfill the rank for standing predictions

Existing resolved and standing predictions get a rank computed from their
frozen rows, marked `backfilled=1` and dated. They are **excluded from S3's
comparison** — a rank computed after the fact by a formula written today is
not the same object as one computed before the games were played, and mixing
them would flatter the ranker. Backfill exists so the page is not empty on
day one, not to pad the evidence.

## Close-out

Standard table: one row per phase plus one per DECISION, four verdicts,
evidence nameable. SKIPPED and DECLINED remain ordinary outcomes.

---

## How this brief is read (written at receipt, before any work)

The standing contract is that work does not stop to ask. D1 and D2 are marked
as the operator's, and no ruling had arrived, so each was resolved by law,
then precedent, then the conservative default, and every choice is recorded
here and in the close-out under "Rulings taken in the operator's absence".

- **D1 defaults to (a) — leave the run line asked, let the shortlist bury
  it.** It is the brief's own recommendation, it is the only option that
  decides nothing that a later ruling could not still decide, and (b) and (c)
  both write a permanent line into the registry retiring a market. Retiring
  is not reversible in this codebase by design: a factor or market is
  deactivated with a dated note and its history stands. An irreversible
  decision on a market's life is the operator's, so it is BLOCKED, not
  guessed. If the operator later rules (b) or (c), nothing built here has to
  be undone — the market simply stops being asked as well as stops being
  shown.
- **D2 defaults to the proposed table**, which the brief itself states are
  "the numbers unless he says otherwise". Declared and dated in config,
  overridable by environment variable like every other cap, so a ruling
  changes one constant and nothing else.
- **"Ruled by the operator 2026-09-07"** appears twice in the brief — that the
  model keeps asking every question, and that the rank has three inputs. Both
  are read as settled instructions rather than open questions, because the
  brief states them as decisions already taken.
- **The edge gate is read as a law of this phase, not a preference.** Every
  place the ordering could touch an ungated market's edge is written so that
  it cannot, and the planting proves it fires rather than the code asserting
  it works.
- **The shortlist changes what is shown and never what is written.** No
  prediction is skipped, no question is dropped, and the count of everything
  else is on the face of the control that reveals it.
