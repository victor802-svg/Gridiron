# Brief — GRIDIRON_READINESS (drafted 2026-09-07)

Saved verbatim before any of it was executed.

---

BUILD NOTHING NEW. This session closes outstanding items, then writes a
readiness document that answers one question with numbers rather than
feeling: is this engine's output fit to act on? Re-runnable weekly; each run
appends a dated row rather than overwriting, so the trend is visible.

## PHASE V1 — Close what is open

1. **Name the escaping planting.** 218 of 219 are caught. Identify the 219th
   BY NAME and say whether it is genuinely the pre-existing empty-slate case
   or something else. An uncaught planting is a guard that is not guarding,
   and inheriting the explanation is not the same as confirming it.
2. **Turn the gate green.** Run `tools/verify.py` after the predict task has
   written a slate. Record all four steps. If steps 1 and 2 still fail for
   any reason other than an unpredicted slate, that is a finding.
3. **Verify the MLB moneyline verdict's provenance.** The 286 settled
   questions measuring the model behind the price: confirm the rows come
   from the LIVE forward database and not a backtest one, by reading the
   database `kind`. Record which. A verdict this consequential is worth one
   query.
4. **Re-measure coverage on real volume.** The current list was measured on
   five NFL games. Re-measure the structural criterion across at least two
   hundred games before the list is treated as settled, and record both
   measurements with their N so the change is visible.

## PHASE V2 — The readiness document

Create `docs/READINESS.md`. Six declared criteria, each with its current
value and a PASS/FAIL, dated. No prose verdict without the numbers beside it.

| # | criterion | threshold |
|---|---|---|
| 1 | Gate fully green | all 4 steps pass; every planting caught |
| 2 | Recommendations produced | ≥ 50 in one coverage entry |
| 3 | Closing line value | mean CLV positive at that N |
| 4 | Outcome evidence | that market at or above its n=100 gate |
| 5 | Open BROKEN findings | zero |
| 6 | Coverage provenance | measured on ≥ 200 games, dated |

**THE STANDING ANSWER UNTIL ALL SIX PASS:** the engine's output is a
forecast to read, not a recommendation to follow. Below the bar the app
already restricts itself to a flat unit and says "no measured edge" — that
restriction stands, and READINESS.md states in one plain sentence that the
operator is acting on an unproven signal with entertainment money.

**Criterion 3 is the one that decides it.** CLV is the fastest honest read
available and it is currently at n=0. Nothing about the other five makes a
difference if the engine is buying rich.

**A FAILING ROW IS A NORMAL OUTPUT.** This document exists to be red for a
long time. A run that reports six FAILs and the reasons is a successful run.
Do not soften a threshold to produce a PASS; changing a threshold requires a
dated operator ruling recorded in the file, and the old threshold stays
visible beneath it.

## PHASE V3 — Then stop

No new features this session, and none next session either unless something
in V1 turns up broken. The engine needs slates run through it, not more
surface area. Record in FOLLOWUPS that a two-week observation period began
on this date and what will be read at the end of it.

## Close-out

Standard table: one row per phase, four verdicts, evidence nameable.

---

## How this brief is read (written at receipt, before any work)

**"Build nothing new" is read as binding, including on me.** The temptation in
V1 is to fix whatever the investigation turns up. Anything found is recorded as
a finding with its evidence; a repair happens only where the brief already
asks for one, and anything else goes to `docs/FOLLOWUPS.md` for the operator to
schedule.

**Every V1 answer is a measurement, not an inheritance.** The escaping planting
is named by running the harness and reading the name, not by repeating what a
previous session said about it. The provenance question is answered by querying
the database rather than by reasoning about which file was used.

**A threshold is never moved to produce a PASS.** The brief says so and this is
the reading: if a criterion is close, the row says FAIL and the number. The
only path to a changed threshold is a dated operator ruling written into
`READINESS.md` with the old threshold still visible beneath it.

**Criterion 6 may be unreachable today, and that is an outcome rather than a
problem.** Two hundred games of venue ladders is more than the record can
supply in one sitting, and the venue publishes no rate limit for
unauthenticated reads. The measurement is taken as far as the data and a
prudent request rate allow, both numbers are recorded with their N, and the
criterion reports FAIL with the distance to the threshold.
