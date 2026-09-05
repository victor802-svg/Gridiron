# Close-out — rulings on the audit's §6

Brief: `docs/briefs/2026-09-05-rulings-on-the-audit.md`. Six rulings; six
outcomes; five commits of code and data, one of documentation.

---

## 1. Against the brief

| ruling | verdict | evidence |
|---|---|---|
| 1 NFL `league_date`: refresh repairs, re-run the leak invariant and the walk-forward, old vs new for every NFL figure, METHODOLOGY §6 if moved | **DONE** | Repaired: 0 of 3,033 NFL games off the Eastern day (562 before). Invariant: 6,066 team-game windows, **0 inside their own game**. Walk-forward, diagnosis and distributional read-out each run on a pre-repair copy and on the repaired record: **every NFL figure identical** — Brier 0.2436 / market 0.2295 (n=570), confident-disagreement 243 → 46.1%, market-more-confident 152 → 65.8%, market closer on 59.9% of spreads and 59.4% of totals. Football windows are cut on `week`, never on the date. §6 rewritten anyway: its table was the 2026-08-29 reading of a different question set; the new figures sit beside the old with the reason. |
| 2 tasks run hidden; re-register | **DONE** | `e69dee0`: the installer executes `pythonw.exe`; re-run on this machine — the OS holds all 15 tasks under pythonw, five of them for the first time. |
| 3 league-day convention, declared, dated, one function | **DONE** | `bdfaddc`: `reference.league_day`, `LEAGUE_DAY_DECLARED = 2026-09-05`; CFB Eastern, UFC the venue's zone from a declared table covering every venue in the record (267 of 268 events; the 268th has no address). Slate keys follow the day. Repaired from cache: CFB 394 → 5 games off the Eastern day (the 5 predate the reloaded seasons); UFC 1,068 bouts moved to their local day, 0 guessed. `tzdata` declared. |
| 4 fingerprint mechanism | **DONE** | `2031689`: `gridiron/fingerprint.py`; every row hashed on write, resolution recorded once; `config.RECORD_BASELINE` holds the audit's `b15a9f6f…` beside the substance hash `0fcb277b…` the gate recomputes; drift fails by prediction id; planted by dropping the trigger. 765 rows backfilled; `tools/fingerprint.py` reports no drift. |
| 5 CatchUp on the Health panel | **DONE** | `912c041`: `catch-up` is a `TaskSpec` with a ledger row of its own wrapping the rows of what it ran. |
| 6 the 42 UFC reasoning rows stand | **DONE (nothing changed)** | LAW 3; render-time humanising covers them. |
| commit each, push, close-out | **DONE** | six commits pushed as they landed; this file; gate in §3. |

## 2. Rulings taken in your absence

1. **Ruling 1's "if they moved" was read as "if the repair moved them".** It
   did not, and the report says so with the measurement. §6 was still
   rewritten, because its backtest table was a reading of the four-rung,
   pre-floor question set of 2026-08-29 and no longer reproduces under the
   shipped code; the old numbers stand beside the new with the reason. Reversal:
   restore the table from `3910435`'s parent.
2. **`docs/DIAGNOSIS.md` was not regenerated.** It is a pre-registered
   analysis dated 2026-08-29; the re-run diagnosis (243 → 46.1%) is in §6 and
   in the scratch output. Regenerating a pre-registered document is a ruling.
3. **The NFL and CFB histories were reloaded from the cache** (2016–2025 and
   2024–2025) so the convention applies to the whole record, not only to the
   season the refresh touches. Games rows only; no prediction touched.
4. **UFC's undeclared venue falls back to the UTC day and is counted**
   (`undated_cards` on the refresh payload) rather than left NULL. One event.
5. **Final-UFC's and Recalibrate's times stand** as registered by the audit's
   installer commit; ruling 2 asked for hidden, not for new times.
6. **The fingerprint covers three fields the trigger does not** (`sport`,
   `prop_type`, `pass_kind`). A wider net that names the same row.
7. **`tzdata` is a new dependency.** Windows ships no zone database and the
   existing Eastern helper's hand-rolled DST rule cannot say what time it is
   in Perth. The PyInstaller spec will need it as a hidden import before the
   next bundle (FOLLOWUPS).

## 3. The gate

`tools/verify.py` under `.venv` after the six rulings (`scratchpad/rulings_verify2.txt`,
exit 0): all four steps PASS; **51 checks PASS, 0 FAIL** (the fingerprint check is
the 51st); **195/195 planted violations caught** (the dropped-trigger planting is
the 195th); suite **1103 passed, 0 skipped, 0 failed**. The first run of the gate
failed one test: §6's new paragraph used the word "read-out", which the plain-words
rule on METHODOLOGY forbids; reworded, re-run, green.

## 4. What the refresh warned about

The repair refresh reported five warnings, all pre-existing and none about
dates: nflverse has no 2026 player-week or injury file yet (the season has
not started), the NBA 2026-27 logs are empty (the season has not started),
and `ufc team names: no league path for 'ufc'` — the team-name loader has no
UFC entry, which is correct for a sport with no teams and reads as a warning.
Worth a line in `teams.LEAGUE_PATH` saying so (FOLLOWUPS).
