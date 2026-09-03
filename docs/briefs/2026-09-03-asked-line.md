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
