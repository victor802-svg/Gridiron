# Brief — the live schema matches the release (2026-09-24)

Saved before execution, as the standing contract requires. The operator's text
is unedited.

---

Schema diff: build a fresh database by migrating from nothing at the released commit, and compare its schema object by object (tables, columns, triggers with their full SQL, indexes) against the live record's. Report every difference. An object on the live record that the released code does not create, or creates with different SQL, is listed with where it came from; a dated migration makes the live record match the release, and the close-out names each change. From then on, the gate runs this diff read-only and fails on any difference.

---

## How this brief is read

**"The released commit"** is the main checkout's HEAD, the code the scheduler
runs. When the gate runs from the worktree before a merge, the live record must
match the RELEASED code, not the worktree's. Unmerged schema on the live record
is exactly the difference the diff exists to catch. After a merge, the
released code's own first open applies its schema, and the live record matches
the new release.

**Order.** The measurement ran read-only against the main checkout and the live
record while the gate-read-only change was being built, since it touches
neither the worktree nor a gate. The diff check and the dated migration are the
next commit after the gate-read-only change. The migration is a live write,
done after the merge, from the main checkout.
