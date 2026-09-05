# Brief — rulings on the audit's §6

Received 2026-09-05. Saved before execution, per the unattended contract.

---

Rulings on the audit's §6:
1. NFL league_date: after the refresh repairs the dates, re-run the
   leak invariant on NFL (no game inside its own rolling window) and
   the NFL walk-forward on repaired dates. Report old vs new for
   every NFL figure on the record — Brier, market share of skill,
   confident-disagreement rate. If they moved, METHODOLOGY §6 gets
   the new numbers with the old beside them and the reason. NBA and
   MLB had this exact defect; assume NFL's numbers moved until shown
   otherwise.
2. Tasks run hidden (no console window) — yes; two control-C deaths
   is two too many. Re-register through the installer.
3. League-day convention: the league's own local date — CFB US
   Eastern, UFC the event's local date. Declared, dated, one
   function.
4. Fingerprint mechanism: build it — the baseline b15a9f6f… stored,
   recomputed in the gate, any protected-field drift fails by name.
5. CatchUp on the Health panel: yes.
6. The 42 pre-fix UFC reasoning rows stand (Law 3); render-time
   humanising covers them. No rewrite.
Commit each, push, /closeout.

---

## How this brief is read

- Six rulings, six commits (ruling 6 changes nothing and is recorded in the
  close-out). Each pushed as it lands.
- Ruling 2 authorises running the installer on this machine; nothing else in
  the contract's BLOCKED list is opened.
- Ruling 1 measures before it writes: METHODOLOGY changes only if the numbers
  moved, and then shows old beside new with the reason.
