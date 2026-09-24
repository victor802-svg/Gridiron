# Brief — the gate reads the live record, never writes it (2026-09-24)

Saved before execution, as the standing contract requires. The operator's text
is unedited.

---

Gate step 2 opens the live record read-only (SQLite mode=ro or the query-only handle). Any check that needs the new schema runs against a scratch copy migrated from it. A gate that changes the live record's schema or rows fails by name; planting. Record in the close-out the two occasions on 24 September when unmerged schema reached the live record.

---

## How this brief is read

**The gate that was running when this arrived was stopped** before its step 2,
so it never wrote the voids schema. Checked read-only afterwards: no
`recommendation_voids` on the live record.

**Order.** The voids are committed on `repair` (d93c466) but not gated. This
ruling's change is the next commit. The two are gated together, then released,
then the voids are written.

**The two occasions** go into the close-out with the evidence for each:

1. Item 1's draft schema reached the live record through the scheduler,
   between about 22:20Z and 22:47Z on 23 September UTC. The operator's
   "24 September" is read as the working day it belonged to.
   It created four objects and no rows.
2. `recommendation_close_cites_its_own_priced_read` was created on the live
   record by a worktree gate's step 2 before item 1 merged at 06:57Z on 24
   September.
