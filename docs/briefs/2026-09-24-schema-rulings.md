# Brief — rulings on the schema diff (2026-09-24)

Saved before execution, as the standing contract requires. The operator's text
is unedited.

---

Rulings on the schema diff, 2026-09-24.

1. The diff check compares after normalising quoting, whitespace, comments and column order, and fails on any difference in behaviour. Byte-identical matching isn't required.

2. The 8 behavioural differences are fixed by a dated migration that rebuilds each affected table: new table with the released definition, copy every row, verify the row count and a checksum of every column match exactly, recreate every trigger and index, then swap, all in one transaction. Rehearse it on a scratch copy first and report counts and checksums before and after. Take a verified backup of the live record before running it. If any table fails verification, the transaction rolls back and nothing is swapped.

3. schema.sql declares the column that currently exists only through an ensure step. A fresh database built at the released commit must match the live record without relying on ensure code.

4. market_snapshots: for each of the 8 missing ids, determine from sqlite_sequence, the task log at that time, and the surrounding rows whether it was a rolled-back insert (a normal AUTOINCREMENT gap) or a deletion. Report each. If any was a deletion, it's a LAW 3 violation: find the code path that did it and fix it with a planting.

5. The auth backoff test takes an injectable clock instead of wall time. No test in the gate may depend on elapsed real time.

6. The two open gaps: add a scan that refuses a raw sqlite3.connect to the live record path outside the approved handles, with a planting. The scheduler applying the schema from the main checkout stays as-is, because that's how a release migrates, and only merged code reaches the main checkout.

---

## How this brief is read

These rulings arrived while the voids-and-gate-reads-only batch was gating.
They are queued **immediately after that batch**, as the schema-diff step the
state file already names, and ahead of inactive-until-activated fits. Item 5
also covers the failure that turned the batch's first gate red:
`test_auth::test_the_backoff_survives_a_restart` compares a 4-second penalty
with wall-clock time elapsed under load. If the batch's rerun goes red on it
again, the injectable clock is built first, as its own commit, and the batch
waits for it.
