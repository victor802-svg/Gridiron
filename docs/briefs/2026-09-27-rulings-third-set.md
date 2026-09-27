# Brief — rulings, 27 September, third set

Saved before execution, as the standing contract requires. The operator's text
is unedited. The board-merge additions it carries are also written into
`2026-09-27-board-merge.md`, marked as this set's.

---

Rulings, 27 Sep (third set).
Q15: first in the order. Fix predictions the same way as Q13, own commit, planting that gets through on the unfixed code. Then one gate scan that refuses INSERT OR REPLACE, REPLACE and ON CONFLICT DO UPDATE against every append-only table; any legitimate upsert (cache, derived table) is named in a register that may only shrink. Measure read-only whether any live prediction row shows evidence of having been replaced; report it, change nothing.
Q20: (A). The Today panel arrives by fade alone; per-frame whole-pixel check that fails today, plus a planting; the one test_motion assertion changes. Side question: not in scope; the old Why panel leaves with the board. The board merge checks every tap target, links included.
Q17: one function defines a distinct bet: forecaster + the venue's question (game, market, line). Morning and final pass of one question count once; which pass counts stays each record's standing rule; alt lines are separate questions. Q12's, Q14's and Q16's counts all use it. List every released number that moves.
Q16: (B), after Q17, on its key. Each correction gate's count per forecaster and distinct bet, planting each.
Q18: fixed in the board, not the old UI: an open card stays open across any redraw. A test proves it.
Q19: fixed in the board: headings in plain words; internal version names only in a tooltip.
Gate reruns: a failed gate may be rerun once as-is. A second failure of the same test gets a diagnosis before any third run.
Order: Q15 (+ scan) → Q20 → Q17 → Q16 → board merge → Q5 → Q10 → re-read (not before 28 Sep 15:00Z).
Board merge checklist additions (update docs/briefs/2026-09-27-board-merge.md):
- Step 2: counts use Q17's key; arrival motion on any panel holding tap targets is opacity only; headings in plain words.
- Step 3: every tap target, links included, is 44px or more at 390px at rest; an open card stays open across a redraw it didn't cause and one the operator started. Each gets a test.

---

## How this brief is read (rulings taken in the operator's absence, by the
## conservative default; each is recorded in docs/REPAIR_STATE.md)

**Q15, the predictions fix.** "The same way as Q13" means Q13's three rules,
applied to `predictions` under names of their own: an insert rule that refuses
a row naming a stored prediction's number or any other stored unique key of
the table, whatever its conflict clause; an update rule naming no columns that
refuses an update taking another stored prediction's place (by `id`, `rowid`,
`oid` or `_rowid_`); and an after-insert rule on the number written. The live
record gains them through `db.init` alone, no row touched, rehearsed on a
verified copy first. No writer changes. The other holes question 15 listed
(the snapshot update rule's column list, `recommendation_closes`,
`recommendation_voids`, a recommendation's number moved by a plain update,
SQLite's sequence) are not named by the ruling and stay in FOLLOWUPS.

**Q15, the scan.** Its own commit, after the predictions fix; one gate covers
both, and they release together (Q14's precedent). The scan reads every SQL
statement the shipped code can issue -- the package and `tools/`, and
`schema.sql` for a table-level `ON CONFLICT REPLACE` clause, which makes a
plain insert replace -- and refuses by name `INSERT OR REPLACE`, `REPLACE
INTO`, `INSERT ... ON CONFLICT ... DO UPDATE`, and (the stricter default,
since it is the same hole Q13 closed) `UPDATE OR REPLACE`, aimed at any
append-only table. An append-only table is one the schema gives a no-delete or
no-update rule, read from the schema, never from a list. Any other upsert
fails too unless the register names it (file, function, table, and a dated
reason); a registered upsert aimed at an append-only table still fails; a
registered entry no longer found fails, so the register only shrinks. A
statement whose target table cannot be read from the code is treated as aimed
at an append-only table. Tests and the plantings are outside the scan: they
write only scratch worlds, and they are how the rules are proved.

**Q15, the measurement.** Read-only, through `db.read_the_live_record` or a
verified copy; the report lands in docs/REPAIR_STATE.md and FOLLOWUPS; nothing
on the record changes.

**Gate reruns** bind from this set on: one as-is rerun after a failure; a
second failure of the same test is diagnosed before any third run.
