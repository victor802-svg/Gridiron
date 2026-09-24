# Close-out — the gate reads the live record, never writes it (2026-09-24)

Against `docs/briefs/2026-09-24-the-gate-reads-only.md`. The ruling, as the
operator wrote it: gate step 2 opens the live record read-only; any check that
needs the new schema runs against a scratch copy migrated from it; a gate that
changes the live record's schema or rows fails by name, with a planting; and
this close-out records the two occasions on 24 September when unmerged schema
reached the live record.

Built on `repair` in the worktree, on top of the voids (d93c466). The two are
gated together.

| part of the ruling | verdict | evidence |
|---|---|---|
| gate step 2 opens the live record read-only | **DONE** | Every step-2 record check reads the gate's own copy. The only handles on the record itself (the backup's source, the two schema readings, step 4) come from `db.read_the_live_record`, which now opens the file `mode=ro` as well as `query_only`. `verify.main` sets `GRIDIRON_VERIFYING` for the whole run, so `db.connect` refuses a writable open by name. `plant_a_gate_step_that_opens_the_live_record_writable` escaped on the unfixed code (exit 0, and 199 objects created on the stand-in) and is caught on the fix |
| checks that need the new schema run on a migrated scratch copy | **DONE** | One backup per run through the read door, migrated with `open_db` in the temp directory: 1.02 GB in 3 s, measured 2026-09-24. All step-2 record checks and step 3's facts read it. The voids checks pass on it while the record holds no `recommendation_voids` |
| a gate that changes the schema fails by name | **DONE** | The record's schema is read when the gate starts and again when it ends, and each object created, dropped or redefined is named. `plant_a_schema_change_during_the_gate` escaped on the unfixed code (exit 0) and is caught: `FAIL the live record changed during the gate: table recommendation_voids was created` |
| a gate that changes rows fails by name | **PARTIAL** | Rows are not compared, because the scheduler writes to the record for the whole of every gate. They are protected by construction instead. A writable open through `db` is refused by name (first planting). The read door cannot be switched back to writing: `plant_a_write_through_the_read_handle_switched_back` escaped on the unfixed code and is caught. Step 3's ATTACH of the record is refused. **Not covered:** a raw `sqlite3.connect` in a gate step would not be refused, and a row it wrote would not be seen. See FOLLOWUPS |
| record the two occasions | **DONE** | Below, with what the record and the logs can prove and what they cannot |

## What changed

- **`tools/verify.py`.** Five things. The whole run is verification. Step
  2's record checks and step 3's facts read one scratch copy: backed up once
  through the read door, migrated to this tree's schema, and deleted at the
  end. Step 4 reads the record through the read door, as it already did. A
  step that reaches for the record fails by name, and the gate still reaches
  its summary. And a new summary row, "the live record, as the gate found it",
  compares the record's schema at the start and at the end.
- **Every live access in the gate, before and after:**

  | where | before | now |
  |---|---|---|
  | step 2, "every foreign key points at a real table" | `db.open_db(config.DB_PATH)` (migrated the record) | the migrated copy |
  | step 2, fifteen checks through `_record_conn()` (the slate and at-the-line payloads among them) | `db.connect()`, writable, a new handle per call, never closed | the copy, handles closed at the end of the step |
  | step 2, "forecasters are never merged" | `db.connect()` inline, writable | the copy |
  | step 2, "a claim is priced at the line", "no withdrawn recommendation is counted" | the read door, on the record, which holds no `recommendation_voids` | the copy |
  | step 3, `copy_facts` | ATTACHed the record, writable | ATTACHes the copy; `copy_facts` refuses the record under verification |
  | step 4 | the read door | the read door, now `mode=ro` |
  | start and end of the gate | nothing | the read door reads the record's schema |

- **`gridiron/db.py`.** `refuse_the_live_record` is the one rule, asked by
  `connect` and by `copy_facts`. `read_the_live_record` opens the file
  `mode=ro`, so a missing record is now an error rather than an empty file
  created where the operator's database belongs.
- **`tools/dbcopy.py`.** `copy_facts` refuses to ATTACH the record under
  verification. A backtest run by hand is not verification and is not refused.
- **Three plantings** (`tools/guards/plant.py`). Each runs the real
  `verify.main`, or the real door, in a child process whose settings name a
  STAND-IN as the live record. The child stops before anything else if its
  record is not the stand-in. The harness now catches 270 of 270.

## The two occasions

The record keeps no time for a schema object. `sqlite_master` gives every new
object the next row id, so the ids give the ORDER things were created in, and
nothing more. Every time below comes from somewhere else, and says where.

### 1. Item 1's draft, through the scheduler — 23 September, about 22:20Z to 22:47Z

What happened: item 1's first draft sat uncommitted in the main checkout.
`Gridiron-Live` opens the database every 90 seconds, and `db.init` ran the
draft `schema.sql` against the live record. It created `recommendation_closes`
and four triggers. No rows were written.

What can be shown today, read-only:

- The live record holds those five objects at `sqlite_master` row ids 338 to
  342, in one contiguous run: the table, then `recommendation_closes_no_update`,
  `recommendation_closes_no_delete`, `recommendation_closes_only_when_closed`
  and `recommendation_close_is_a_later_read_of_its_own_contract`.
- All five are byte-identical to the same objects built fresh from the schema
  this tree carries. It was checked again for this close-out. So what the
  draft left on the record is exactly what shipped.
- `recommendation_closes` holds 55 rows, and every one was written at
  2026-09-24T06:49:48Z, which is the restatement after the merge. Its
  no-delete trigger arrived with the draft, so no earlier row can have been
  written and removed since. No row from the window exists.
- The main checkout's reflog records `reset: moving to HEAD` at 22:40:46Z. The
  worktree's administrative directory was created one second later, at
  22:40:47Z. That is consistent with the draft leaving the main checkout then.

What cannot be shown: the window's start, 22:20Z, and its end, 22:47Z, are the
figures item 1's close-out and FOLLOWUPS gave that night. The record stores
neither.

### 2. The fifth trigger, through a worktree gate's step 2 — 24 September, before the merge at 06:49Z

What happened: `recommendation_close_cites_its_own_priced_read` was created on
the live record by `tools/verify.py` step 2, run from the worktree. Step 2's
foreign-key check called `db.open_db(config.DB_PATH)`, and `open_db` runs
`db.init`, which runs the worktree's own `schema.sql` against the file. The
worktree's `var` is a junction to the main checkout's record.

What can be shown, from the gate logs this session kept (the scratchpad's
`repair/verify_*.log`), the reflog and the record:

| when (UTC) | what | source |
|---|---|---|
| 23 Sep 23:05:12 | the trigger's text is written into the worktree's `schema.sql` | `repair/patch_item1_review2.py`, last modified then |
| 24 Sep 05:32:06 | a gate run from the worktree ends in step 2 with a traceback: `verify.py` `_live_db` → `db.open_db(config.DB_PATH)` → `init` → `conn.executescript(schema.sql)` → `sqlite3.OperationalError: database is locked` | `repair/verify_item1c.log`, last modified then; every frame is under `gridiron-repair\` |
| 24 Sep 05:53:42 | a gate run from the worktree passes "every foreign key points at a real table", so `open_db` and the schema script ran to completion against the record. Its step 4 names the record as `gridiron-repair\var\gridiron.db` | `repair/verify_item1d.log` |
| 24 Sep 06:21:04, 06:47:58 | two more worktree gate runs do the same | `repair/verify_e.log`, `repair/verify_h.log` |
| 24 Sep 06:48:39 | commit 23cf89b, carrying the trigger | `git log` |
| 24 Sep 06:49:12 | the main checkout fast-forwards to 4941fa1: item 1 merges | main checkout reflog, `merge repair: Fast-forward` |
| 24 Sep about 06:57 | the release goes live | item 1's close-out |

**Why the 05:32Z lock is evidence.** This rests on an inference, and the
inference was tested. `schema.sql` holds no INSERT, and a `CREATE ... IF NOT
EXISTS` for an object already present needs no write lock. A temp record
holding every object ran the schema script while another connection held the
write lock. With one trigger dropped, the same script failed with "database is
locked". So at 05:32Z the worktree's script was trying to create something the
live record did not hold. Item 1's schema adds six objects, and the draft had
already created five of them. The one left was this trigger.

**What is provable.** The mechanism, caught in the act from the worktree at
05:32Z. The trigger was on the live record by 05:53:42Z at the latest, 55
minutes before item 1 merged. And nothing on the main checkout could have
created it earlier, because its schema had no item 1 objects until the
fast-forward. The trigger sits at row id 343, the newest object on the record.

**What is not.** The exact minute the trigger was created. The gate runs
record no start time, and a log's modification time is when its run ended.
Nor is it provable that the 05:53Z run created it rather than another process
running the worktree's schema between 05:32Z and 05:53Z. Item 1's review found
that `tools/restate_closes.py`'s dry run also applied the schema, and the
record cannot tell the two apart. `init` also runs the fingerprint backfill and
seeds `meta`. Both are no-ops on a record the scheduler has already set up, but
the record cannot show whether those runs wrote anything there.

### A third, prevented

The voids gate started at about 08:27Z on 24 September. It was stopped before
step 2. Its log, `repair/verify_voids.log`, was last written at 08:30:13Z, and
it ends inside step 1's test run, past the 70% mark. The record was read
through a `mode=ro` handle at 08:33Z and again at 09:00Z. It holds 197 schema
objects, and the newest is still row id 343. None of the four objects the
voids add is there: `recommendation_voids`, `recommendation_voids_no_update`,
`recommendation_voids_no_delete` and `voids_no_delete`.

## Verified here, and what was not

- The three plantings escaped on the unfixed `verify.py` and `db.py`, run
  alone. They are caught on the fix.
- Step 2 was run alone under the gate's environment: 270 of 270 planted
  violations caught, and every record check PASS on the copy. The copy took
  3 s. The record's schema was unchanged: 197 objects before and after.
- Steps 3 and 4 were run alone the same way. Both PASS, and the record was
  unchanged.
- **The full gate was not run by this session.** It is run on the tree that
  carries this change and the voids together, before either is released.
