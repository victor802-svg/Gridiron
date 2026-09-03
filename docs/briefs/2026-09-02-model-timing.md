FIRST ACT: save this brief to docs/briefs/<date>-model-timing.md,
commit. Read CLAUDE.md, docs/MENTOR.md, docs/DIAGNOSIS.md.

THE CAUSAL CLAIM, stated before anything changes: the model's
confident disagreements lose (55% NFL, 53% NBA in backtest) and D1
could not test whether that is because the market knows late news.
The model guarantees the disadvantage by asking early — NFL week 1
was written 12 days before kickoff; MLB predicts before lineups
post (the lineup-slot factor came back absent on every game for
that reason). This session moves the GRADED forecast as close to
start as the lead rule allows. No factor changes. The early
forecast is kept as a planning view, never graded.

A1 — TWO PASSES, ONE STANDING ROW
- Every sport's predict task gains a FINAL pass, scheduled per sport
  (dated constants, in Settings > When it runs):
    MLB  — after lineups post: T-2h30m before first pitch, per game
           slate window (a second daily task at a fixed local time
           chosen from the measured lineup-post distribution; the
           probe below measures it)
    NFL  — Sunday 08:00 local for the Sunday slate; Thursday 14:00
           and Monday 14:00 for the standalone games
    CFB  — Saturday 08:00 local; Thursday/Friday 14:00 for weeknight
           games
    NBA  — 15:00 local after the 5:30 ET injury report window
- The final pass writes NEW rows (Law 3 — append-only; the early
  rows stand). The standing forecast for grading, calibration,
  Picks and Results is the LATEST ROW BEFORE START — the precedent
  already applied to the NFL double slate. Early rows are labelled
  "early view" everywhere they appear and never enter calibration.
- Blind structure unchanged: the final pass runs the same
  prediction path, no market data inside the window; snapshots
  after, as always. A second snapshot at the final pass is the
  drift pass's "near start" row — reuse it, don't duplicate.
- MISSED rule unchanged: a final pass after start writes nothing
  and records MISSED; the early row remains the standing forecast
  for that game, labelled as such.
- PROBE FIRST (docs/TIMING_FEASIBILITY.md): for each sport, from
  the data we hold, when do lineups / injury reports / probable
  starters actually post relative to start? Choose the final-pass
  times from that measurement, dated, and state the fraction of
  games the chosen time expects to catch.

A2 — THE EARLY-VS-FINAL RECORD
- A new comparison, gated at 50 game-pairs per sport: on games with
  both rows, how often did the final pass change the side, by how
  much did the claim move, and did the final pass score better
  (Brier) than the early one on resolved games. Plain words:
  "The final pass changed the pick on 9 of 62 games and scored
  better on 41." Below the gate, the count only.
- This is the information-vs-model question made measurable. No
  conclusion in code comments; the number decides on its date.

A3 — SURFACES
- Picks shows the standing row; an "early view" toggle shows the
  early row for the same game, labelled, never mixed in a ranking.
- Results rows carry a small "final" or "early only" mark.
- Health lists the final-pass tasks; MISSED applies.

A4 — VERIFICATION
- Plantings: a final pass inside the market closure; an early row
  entering calibration; a final pass writing after start; two
  standing rows for one question.
- Full suite, renders (a game with both rows, the toggle, a MISSED
  final pass), verify.py, /closeout, push.
