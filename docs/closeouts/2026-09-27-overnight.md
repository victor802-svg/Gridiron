# Close-out — the overnight queue (2026-09-24 to 2026-09-27)

Brief: `docs/briefs/2026-09-24-overnight.md`, with the rulings that arrived
during it (`2026-09-25-question-4.md`, `2026-09-26-edge-read.md`). Serving at
the end: **f02e913** (`/api/health` = f02e9134d984, 02:36Z on 27 September).
Every release went gate, commit, fast-forward main, push, restart, confirm.

## Against the brief

| # | item | verdict | evidence |
|---|---|---|---|
| 1 | Activation gate | **DONE** | ff7e5ab. Fits written inactive; dated activations carry their holdout; ties go to the incumbent (the trigger refuses an interval that does not lie below zero). Bootstrap on the record: 24 incumbents, none for fits 91-94. |
| 2 | Revert all four fs5 markets; lift the hold per market; confirm on the day strip | **DONE** | 4c3bda4. Fits 88, 71, 44, 35 activated with their set's holdout and the tie in the reason; `srs_diff`/`cfb_srs_diff` reactivated (dated). The 15:00Z passes on 24 Sep wrote NFL spread 13 (fs3), moneyline 16 (fs2), NCAAF 1+1; strip shows no held line; the gate's page check passed on the record read-only. |
| 3 | Weather: no value indoors; coefficients before and after | **DONE** | fddd61b. Every coefficient, probability, log loss and Brier identical before and after in all 8 weather-bearing markets; only rows used changed (NFL spread wind/cold 2,195 → 1,527). |
| 4 | Reasoning-pass prompt record | **DONE** | f6e57f3, after the question-4 ruling. Release instant 2026-09-25T22:36:19Z; 538 of 538 earlier rows carry a `reconstructed` record (14 commits' own code); every later row a `sent` one (first pass: 26 of 26). |
| 5 | Schema rulings | **DONE, one clause HELD** | 3603300 (5a), f4c4db2 (5a': eight adversarial-review findings and five more), the migration of the eight tables on the record at 02:12:57Z on 26 Sep after a verified backup (every checksum equal, lock 3.52 s), 9d7af57 (5b: register empty). The 8 missing snapshot ids were **deletions by hand** on 1 Sep (LAW 3), now refused. Ruling 5's second sentence: the browser tier's 44 fixed waits are held pending question 5. |
| 6.2 | Item 2's remainder: no market skipped in silence | **DONE** | d7b4dfa. A run writes what has a model, then fails by name; the strip says so. |
| 6.3 | Corrections reach recommendations | **DONE** | 36e863f. Inert today: no correction has ever been activated (63 fits, 0 active). |
| 6.4 | Return-on-stake denominator; re-grade | **PARTIAL** | 3c43509: the no-side cost is the divisor. The labels are **not written**: the old divisor let **four** through (3, 10, 26 and 56), not three; the tool refuses until question 9. |
| 6.5 | One recommendation per game and market, never both sides | **DONE** | 9014add. New rows only; the 18 existing pairs untouched (questions 11, 12). |
| 6.6 | At-the-line scorecard per forecaster, per distinct bet | **DONE** | 6cb20eb. "MLB moneyline 283, past the 100" is 92 of 100 per forecaster; nothing at the line is past its 100. |
| 6.7 | Jobs | **DONE** | 0c6da10, after a verified backup. 7 hung rows marked abandoned; refusals are noops; WakeToRun on all 18 registered tasks (wake timers enabled). |
| 6.8 | READINESS | **DONE** | f02e913. Two BROKEN findings recorded, dated, REPAIRED; window from 24 Sep; no closing-line verdict before 15 Oct. |
| — | REPAIR_STATE current after every release | **DONE** | one state commit per release. |
| — | "Do not touch the board branch" | **DONE** | never checked out or read. |
| — | One operation at a time | **BROKEN ONCE** | 25 Sep: an adversarial review launched as "remote" ran on this machine while the 5a gate ran; the gate failed on a browser race and was rerun alone. Recorded in memory so it is not repeated. |

Beyond the brief, by the operator's request: **the edge read** (26 Sep), recorded
in READINESS: the model shows no edge; MLB moneyline market better beyond
noise for both forecasters; nowhere does the model beat the market.

## The machine's awake time

`tools/awake.py` (built by item 7; reads the System log only):

- **From the start of the run (10:04Z, 24 Sep) to 02:36Z, 27 Sep: awake 49.8
  of 64.6 hours, 77.1%.** Asleep 0.0 h. Switched off 14.8 h, twice:
  - 23:13Z 24 Sep → 03:17Z 25 Sep, 4.1 h
  - 08:35Z → 19:18Z 25 Sep, 10.7 h

  Both were powered off from the power button or the sign-in screen (event
  1074, winlogon for SYSTEM, 0x500ff), not updates. Thursday's NFL game
  kicked off inside the first; no near-start read was taken for it.
- **Since item 7's fix (00:06Z, 27 Sep): awake 2.5 of 2.5 hours, 100%.** No
  timer has ever woken the machine. WakeToRun wakes a sleeping machine; it
  cannot help one that is switched off.

## Spend

Pro plan: weekly all-models allowance 71% used at 02:37Z on 27 Sep (resets
2026-09-28T15:00Z); extra usage off, $0.00. Subagents and workflows since the
run began: about 14.1 million tokens across 16 workflows and agents. None of
it ran in the cloud (see "one operation at a time").

## What is next

**Waiting for the operator** (docs/REPAIR_STATE.md, "Questions for the
operator"), the ones that block something first:

- **Q9, blocks item 4's labels:** label three recommendations or all four?
- **Q5, blocks the rest of ruling 5:** how far "no test in the gate may depend
  on elapsed real time" reaches.
- **Q13:** fix the INSERT OR REPLACE hole on `recommendations` (LAW 3, outside
  items 1-8)?
- **Q14:** three more pooled counts on the Record page, outside item 6's words.
- Also open: Q1-Q3, Q6-Q8, Q10-Q12.

**Queued by the operator for after this close-out**, in order: (1) the Record
page states "market ahead" per sport and market with its interval; (2) model
plan M3, the market blend, to the front of M1-M6 (no M1-M6 document is in this
repository).

**Owed by the repair brief:** "the read again, on the repaired record, with the
same seven measurers and verifiers, before any of jobs 2-5 are reconsidered."
The cloud split puts multi-agent verification in the cloud, and the only
"remote" agent tried here ran locally. How it runs is the operator's call.

**Dates:** first clean closing-line read **15 October**; MLB's regular season
ends 27 September.

**Housekeeping:**

- The gate's two browser flakes should be fixed so a sub-pixel height or a
  canvas race cannot fail a release:
  - `test_every_tap_target_on_the_slate_is_big_enough`: a button at
    43.9995px failed item 8's first gate.
  - `test_the_weekly_strip_renders_with_hit_targets`: a canvas read before
    its paint failed 5a's first gate.
- About 32 GB of scratch copies sit in the session scratchpad.
- Two verified backups sit in `var/`:
  - `gridiron.db.pre-behaviour-migration-2026-09-26.bak`
  - `gridiron.db.pre-task-runs-widening-2026-09-26.bak`
