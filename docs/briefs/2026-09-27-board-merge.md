# Brief — the board merge checklist (2026-09-27)

Saved before execution, as the standing contract requires. The operator's text
is unedited. Its place in the order is set by
`2026-09-27-rulings-second-set.md`: after the flaky tests, before Q5.

---

Merge GRIDIRON_BOARD. Branch "board" at a63463a or later. Target branch is master.
1. Run the failing order (whole smoke suite, then whole cards suite) three times on this machine. All green, or stop and report — the race was timing-dependent and the cloud's 10/10 was on different hardware.
2. Merge board into the worktree branch. Every conflict resolves in favour of repair behaviour: the regrade line, the closing-line window (no mean or verdict before 15 October), per-forecaster per-distinct-bet counts (item 6, Q12, Q14), one recommendation per game and market. The board may restyle those, never remove or recount them. No new fixed wait enters the browser tests. List each conflict and how it resolved. Run the full gate read-only against the live record; every planting caught.
3. Capture Games, Props, My day, one game expanded, the Record page, the updating state, the first-load placeholder and the empty states from the live record at 1300px and 390px. List every difference from the fixture captures.
4. Release: merge to master, push, restart, confirm /api/health. The old Picks, Live and Today routes are removed in this release and not before.

---

## Additions, 27 Sep (third set: `2026-09-27-rulings-third-set.md`)

The order now places the merge after Q15 (+ scan), Q20, Q17 and Q16.

- Step 2: counts use Q17's key; arrival motion on any panel holding tap targets is opacity only; headings in plain words.
- Step 3: every tap target, links included, is 44px or more at 390px at rest; an open card stays open across a redraw it didn't cause and one the operator started. Each gets a test.

And from the same set, carried by the merge:

- Q18: fixed in the board, not the old UI: an open card stays open across any redraw. A test proves it.
- Q19: fixed in the board: headings in plain words; internal version names only in a tooltip.
- Q20's side question: the old Why panel's "How the model works" link is not in Q20's scope; it leaves with the board, and the merge checks every tap target, links included.
