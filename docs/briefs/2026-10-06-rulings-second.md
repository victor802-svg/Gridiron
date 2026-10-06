# Brief — rulings, 6 October 2026 (second)

Saved before execution, as the standing contract requires. The operator's text
is unedited.

---

Ruling, 6 Oct (second): Q38 (A), plus:
1. A game's start is the earlier of its listed start and the first poll that sees it truly under way (a score or period recorded; MLB's warm-up "Live" before the listed start does not count). No read at or after that instant is a close or a claim.
2. recommend.for_predictions refuses any game that is not still upcoming: in progress, final, postponed, or past its start as defined in 1. Planting: a finished game's pick priced; an in-play read used as a close.
Order: C → Q38 → recs 114/115 voids (with C's or Q38's gate, whichever is next) → B → entry check steps 1–4 → Q33 + Q34 → Q25/Q26 → Q5 → Q10.

---

## How this brief is read

- **Q38 (A)** is built after C, as its own gate and release. Item 1's rule
  (the near-start run keeps a game until its start) now reads "its start" as
  ruling 1 defines it: the earlier of the listed start and the first poll that
  records a score or a period. MLB's warm-up "Live" before the listed start is
  not "truly under way". No read at or after that instant is a close or a
  claim.
- **Ruling 2's planting is two plantings:** a finished game's pick priced, and
  an in-play read used as a close. Both escape on the released code and are
  caught on the build.
- **Recs 114/115.** C's gate is the next gate, so the one-line change to the
  void tool's operator's-word constant (114, 115) goes into C's gate. The dry
  run and then the write (`--write --live`) follow that release, before Q38's
  build starts. The order lists the voids after Q38, but its parenthesis ties
  them to whichever gate comes next, and that gate is C's.
