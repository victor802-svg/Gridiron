# Close-out: the October queue (2026-10-06 to 2026-10-12)

Against the orders of 5 October (`docs/briefs/2026-10-05-rulings.md`), 6 October
(`2026-10-06-rulings.md`) and 6 October, second (`2026-10-06-rulings-second.md`):
C -> Q38 -> recs 114/115 voids -> B -> the entry check, steps 1-4 -> Q33 + Q34 ->
Q25/Q26 -> Q5 -> Q10, with the queue rule (a finding joins only if it breaks LAW
1 or LAW 3, makes a gate count false, or could show a wrong number on a pick --
the last joins first). Every release went gate (`tools/verify.py`, detached), push,
fast-forward of master, restart, `/api/health`. Each item's full account is in
`docs/REPAIR_STATE.md` (START HERE) and FOLLOWUPS.

| item | verdict | evidence |
|---|---|---|
| C, the Props board (ruling C) | DONE | 6c54ed1 (with the orphan scan read once, so the planting harness fits its 600 s -- ruled in absence by "never widen a tolerance"), 2026-10-06 18:40Z; no venue rung is a pick'em pick; break-evens only from typed payouts; "Nothing worth taking today"; the Kalshi ladder view |
| Recs 114 and 115 voided (6 Oct) | DONE | the constant rode C's gate (6c54ed1); dry run, then `--write --live`: 2 voids at 2026-10-06T18:41:19Z |
| Q38 (A), a game's start (6 Oct, second) | DONE | 1b5e7f6, 2026-10-06 23:20Z (gate green on its one as-is rerun; the first run's one failure was the Results race held for Q5); `live_first_under_way` on the record |
| B, picks ranked by edge | DONE | 5383e63, 2026-10-07 02:22Z; no game-market row is a pick until its gate (only MLB moneyline past it, season over); questions 41 and 42 put with defaults as built |
| Entry check, step 1 (arithmetic) | DONE | d8a49bf, 2026-10-07 21:38Z (resumed from a builder stopped mid-build at ~03:03Z); `pickem_payouts_typed` on the record |
| Entry check, step 2 (the model as a veto, M4) | DONE | baf6797, 2026-10-08 01:07Z; M4's first fits written inactive (fits 1-2, dry run first); questions 43 and 44 put with defaults |
| Entry check, step 3 (the record) | SKIPPED -- a decision | BLOCKED on question 45: storing taken entries with their payout against LAW 5's NO LEDGER (not amendable) -- allowed under one reading, forbidden under another ("Who reads a law"); nothing built |
| Entry check, step 4 (deposit match) | DONE | 372eeab, 2026-10-08 03:47Z; stores nothing, units only |
| Q33 + Q34 | DONE | 2ffa0b3, 2026-10-08 07:33Z; outlooks count only slates still to come; five UFC counts per card |
| Q46, the pooled band line (joined the queue) | DONE | e09447f, 2026-10-08 12:48Z; settled by LAW 4 and question 14's precedent |
| Q25 with Q29, and Q26 | DONE | d264f1f + cfcf273, 2026-10-08 17:19Z, ported from `q25-held`/`q26-held` (left as they were) and re-proved; green on the one as-is rerun (the Results race again) |
| Q5, the render signal | DONE | 451ab3d, 2026-10-08 23:54Z; ELAPSED_TIME_HELD emptied and pinned; the Results race fixed (10 of 10; the browser tier 70 runs) |
| Q47, the latest answer (joined the queue first) | DONE | 628880c, released with Q10 at af469aa, 2026-10-12 19:51Z; seven parts drew a superseded answer, now none |
| Q10, a no-side size on its own side | DONE | af469aa, 2026-10-12 19:51Z (resumed after the weekly limit); no stored row changed (all 149 a flat unit) |

Also, on the operator's word (2026-10-10, after an API key was updated): the
college final pass that hung at 16:19Z was rerun by hand -- ok at 16:46:55Z,
105 questions re-forecast; its 9 recommendations are not picks under B.5.

OPEN FOR THE OPERATOR (each with a default in force; `docs/REPAIR_STATE.md`):
39 (read the venue's player-prop series?), 40 (a band around 50c for the main
line), 41 (the writer under B), 42 (the colour law's fills under B), 43 (may M4
imply a yardage projection?), 44 (M4's refits after the first), 45 (entry check
step 3 against NO LEDGER -- blocks step 3).

WATCH: `tools/guards/plant.py` whole runs about 455 s of the harness test's 600
(it was 577-610 s before the orphan scan was read once). The rule kept since 6
October: past 480 s, make the slow plantings cheaper with identical results; the
limit is never widened.
