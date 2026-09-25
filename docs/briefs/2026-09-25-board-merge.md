# Brief — Merge GRIDIRON_BOARD (saved verbatim, 2026-09-25)

Received in the cloud session that built the board. Steps 3 to 5 need the
operator's machine and the live record, which this session does not have;
the close-out (`docs/closeouts/2026-09-25-board-visual.md`, "The merge
brief") says what was done here and what waits for that machine.

---

Merge GRIDIRON_BOARD, after the repair queue closes. Branch "board" at fa0b28c or later.
1. Fix the order-dependent expand-in-place failure first: find the cause (arrival stagger or a second render during the wait), fix it in the page, not the test, and prove it by running the suite in the failing order ten times.
2. Operator ruling: the sort and filter bar stays above the rows, as built.
3. Merge board into the worktree branch, run the full gate on this machine against the live record (read-only), and confirm the plantings count went up by the board's additions.
4. Before restart, capture Games, Props, My day, a game expanded, the Record page, and the empty states from the live record at 1300px and 390px, and put them in the close-out. List anything that looks different from the fixture captures.
5. Then release: merge to main, push, restart, confirm /api/health. Remove the old Picks/Live/Today routes only in this release, never before.
