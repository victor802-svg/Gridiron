# Brief — rulings, 28 September, second set

Saved before execution, as the standing contract requires. The operator's text
is unedited.

---

Rulings, 28 Sep (second set).
First: confirm Q20 (with Q28) is released. If it isn't, it goes before anything else.
Q27: the standing pass is chosen by pass, not by write time: the final pass stands whenever one exists before the start; otherwise the latest early pass. A read rule — no row changes. The 16 NFL totals are re-scored under it and every moved number listed. Separately, a catch-up may not run an early pass for a question whose final pass exists; it is a SlateAlreadyAnswered noop. Own commit, planting.
Q29: folded into Q25's scan: refuse any code that writes sqlite_sequence, and any multi-row INSERT OR FAIL / OR IGNORE / OR ROLLBACK on an append-only table. No separate item.
Order (budget-first): Q17 → Q16 → Q27 → board merge → re-read → Q25 + Q26 + Q29 → Q5 → Q10.
If the weekly limit stops work again, record where it stopped in REPAIR_STATE.md and resume from there at the reset. Don't restart any finished step.

---

## Confirmed

**Q20 with Q28 is released:** 724a72d reached master and was serving at
2026-09-28T04:51:18Z (`/api/health` = 724a72d5fe3e); master has since moved to
f0a4418 (Q24), which contains it (`git merge-base --is-ancestor 724a72d
master`, checked 21:11Z).

## How this brief is read (the conservative default; recorded in
## docs/REPAIR_STATE.md)

**Q27's rule** is the one standing rule, `calibration.standing_row_clause`:
among a question's rows written before its start (a withdrawn row never), a
final pass stands if one exists; otherwise the latest early pass. Its fallback
for a question with nothing written before the start (a backtest) is kept as
it is. Every record that reads the standing rule (the blind curves, the
priced record, drift, the outlook, the at-the-line claims through it, and Q17's
key) reads the new rule; no row changes. "Every moved number" is listed the way
Q17's were: the released code against the new, on one verified copy.

**Q27's catch-up rule** applies to every run that writes an early pass (the
catch-up and the scheduled predict alike, since both write early passes and
the ruling's reason -- a final pass already stands -- holds for both): an
early pass for a question whose final pass exists is not written, and a run
with nothing else to write is a `SlateAlreadyAnswered` noop, as item 7 records
one.

**Q29 inside Q25:** the scan refuses any shipped code that writes
`sqlite_sequence` -- except `gridiron.rebuild`, which carries the mark exactly
and is the verified rebuild door (named in the register with its reason, if
the scan's register admits it; otherwise the operator is asked) -- and any
insert of more than one row under OR FAIL, OR IGNORE or OR ROLLBACK aimed at an
append-only table.
