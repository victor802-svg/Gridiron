FIRST ACT: save this brief to docs/briefs/<date>-asked-line.md.

THE RULING (operator, via mentor): under nearest-margin rungs,
cfb_asked_line became a coarsened copy of cfb_srs_diff (measured
2026-09-01). Redeclare the asked-line instrument for EVERY spread
market as the SIGNED DISTANCE between the asked rung and the
model's own expected margin — "how far the question sits from what
the model expects." This is exactly what mean_vs_line already is
for props, and it is orthogonal to the rating by construction.
Same repair shape as the batter-rate window fix.

B1 — Redeclare per sport (nfl_asked_line, nba_asked_line,
     cfb_asked_line) with the new rationale; date it; bump the
     factor-set version for spread markets only (records for those
     markets are at zero or tiny — state the counts; existing rows
     stand under their old version).
B2 — Prove the dependency is broken the way the batter-rate fix
     was proven: correlation between the new asked_line and the
     rating factor on the real training set, before and after
     (expect ~1.0 → well under 0.5). Refit; report standardised
     coefficients; nothing constant, nothing dropped.
B3 — The synthetic re-ask of the last slate for the close-out only;
     the "why" templates for asked_line reworded to the new meaning
     ("the question sits 6 points above what the model expects").
B4 — Plantings: an asked_line computed from anything but rung minus
     expected margin; a market value in its path. Full suite,
     verify.py, /closeout, push.

---

## AMENDMENT — operator ruling, 2026-09-03, mid-session

Received after B1 measurement began and before any factor was changed.
Recorded verbatim:

> Ruling: apply R4 (nearest-expected-margin rungs) to NFL and NBA
> spreads in this session, dated today. NFL week 1 rows stand (Law 3);
> week 2 onward uses the rule. NBA has no standing rows — free. Then
> redeclare asked_line for all three sports as rung minus the model's
> expected margin per 18B, and prove the dependency break on CFB
> (before/after correlation) and the *independence* on NFL/NBA (the
> new factor should correlate with the rating far less than the old
> rotation-based one did with nothing — report both). Refit all three,
> standardised coefficients, nothing constant or dropped, synthetic
> re-ask for the close-out only. Version the spread factor sets;
> existing rows keep their version.

**Why the amendment was needed, measured before it arrived:** NFL and NBA
choose their spread rung by `stable_index(game_id, ...)` — a hash of the game
id over `SPREAD_LADDER`. Their asked line is therefore independent of the
rating *by construction*, so the dependency B2 sets out to break does not
exist there. The ruling extends R4 to those sports so all three share one rule,
and asks for the independence to be reported rather than assumed.
