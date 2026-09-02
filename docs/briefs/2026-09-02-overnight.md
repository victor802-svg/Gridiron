OVERNIGHT SESSION — ~8 hours, unattended contract in force
throughout: never stop to ask; forks resolve by law, precedent,
then the conservative default, all recorded under "Rulings taken in
your absence"; operator-only decisions are BLOCKED and skipped;
commit + verified push at every phase boundary and a WIP push if any
phase passes 45 minutes; budget the window — a complete item beats a
half-built one; the gate, renders, and /closeout run for every item.
Verify this paste ends with "=== END OF PASTE ===" before starting.

ORDER OF WORK, priority first. Do not reorder. Save each brief to
docs/briefs/ before executing it.

STEP 0 — STOP BRIEF A (calls). Do not run O5. Commit anything
committed-ready, leave the tree clean, push.

STEP 1 — GRIDIRON_16 (below): withdraw calls, palette v2, picks as
ruled. /closeout, push.

STEP 2 — GRIDIRON_13, both parts, already saved at
docs/briefs/2026-09-01-progress.md (P1–P7; mockup
docs/mockup/gridiron_pages.html). Note: Results replaces History
per 16; the pages mockup's green interactive elements are
superseded by 16's tokens. /closeout, push.

STEP 3 — MLB RUN LINE AND TOTALS (below). Probe first; markets go
LIVE tonight if the probe passes — the operator ruled it. /closeout,
push.

STEP 4 — MODEL REPAIRS (below), CFB ladder only. /closeout, push.

STEP 5 — If the window remains: FOLLOWUPS items in the order they
appear, smallest first, each its own commit. Stop at 7:00 local
regardless; the last act is one ntfy push through the existing
notifier's failure channel — counts only: "overnight: N items
complete, M blocked, gate <green|red>" — and the final close-out
listing every item as DONE / PARTIAL / BLOCKED / NOT REACHED.

########################## GRIDIRON_16 ##########################
withdraw calls, darken the ground, green means won

RULINGS:
R1  CALLS WITHDRAWN. Remove the feature entirely by surgery, not
    revert: table (drop; the one row is a test), endpoints, rail
    block, row expansion block, tile marks, the "you (informed)"
    forecaster in Record and digest. KEEP the notifier minus its
    operator clause, KEEP subjects.py's canonical side map and the
    not_cover unification. Suite passes with zero allowlist
    additions afterwards. DECISIONS_MADE: "Operator calls withdrawn
    2026-09-02 by ruling; notifications retained." The calls brief
    stays in docs/briefs as the record.
R2  PALETTE v2: ink #050705, card #0B0F0B, raised #10150F, hairline
    #1A211A. Rename --green to --win and --red to --loss. GREEN
    MEANS A PICK WON; nothing else. Red only for a loss. Active tab,
    buttons, links, selection, focus, segmented controls: white.
    Tighten the token-misuse scan to match; two plantings (a green
    link, a red warning border). Re-run the contrast audit on the
    darker ground and fix anything under AA.
R3  PICKS shows tonight only. Each tile: game in condensed caps,
    pick line in plain words with time, then two mono numbers —
    model % and market % — with small labels ("no line" in words
    when absent), and the 3px tier edge. NO gap on the tile; NO
    graphs anywhere on Picks. The rail states model, market and gap
    as text, the three-sentence why, the tier line, one link.
R4  History is renamed RESULTS (nav + route; old route redirects);
    resolved rows live there only. Picks carries no resolved section.
R5  FORECASTER SELECTOR on Picks: Statistical (default) · Reasoning
    model. Never both in one ranking — planting.
R6  The MLB day slate uses the same desk as weekly sports; the
    breakpoint decides layout, never the sport (the empty-rail
    defect). Slate label in date words with the countdown; day/week
    keys never render (extend the scan).

Phases: W1 withdraw → W2 palette + colour law → W3 picks as ruled →
W4 qa: full suite no skips; plantings named (green link, red border,
two forecasters in one list, a resolved row on Picks, a day key in
visible text, any surviving calls symbol); renders at 1440/1280/390
(Picks both sorts and both forecasters, the rail, Results with the
calendar, login, nav reading Picks · Record · Results · Settings);
read-cold pass on five tiles; verify.py green; /closeout; push.

########################## MLB RUN LINE + TOTALS ##########################
Two new MLB question shapes, governed by docs/NEW_MARKET_CHECKLIST.md
item by item, ticked in the close-out. Operator ruling: LIVE tonight
if the probe passes.

M-PROBE (read-only, committed as docs/MLB_RUNLINE_FEASIBILITY.md):
 1. Does ESPN carry MLB run lines (±1.5) and totals per game, at
    what coverage across a real current slate? Side labels present
    or derived (the milestone-anchor / monotonicity precedent)?
 2. Measured MLB TOTAL-RUNS SD from the stored seasons, dated, N;
    the existing margin SD 4.71 covers the run line.
 3. Any market where lines are missing or one-sided: report it;
    the build shrinks to what the evidence supports.
M-BUILD (only what the probe supports):
 - RUN LINE: the market's rung is fixed at ±1.5 — ask exactly that
   rung, both sides declared, blind by construction (no fetch inside
   the window). Own category, own gate. Void rules written first
   (postponement; a game shortened before regulation resolves by
   the league's ruling, documented).
 - TOTALS: self-generated asked total from the model's own run
   expectation, rounded to .5, per the CFB mechanism; measured total
   SD for the market comparison; own category, own gate; totals
   factors: combined offence form, both starters' suppression,
   bullpen load both sides, park factor, wind at first pitch for
   outdoor parks via the existing Open-Meteo path.
 - Checklist items 1 (asked line / mean_vs_line + volatility) and 2
   (variance bookkeeping) satisfied from the first fit; walk-forward
   fits labelled pipeline-sanity; market comparison uses measured
   SDs under the undated-SD guard.
 - Picks market filter gains Run line and Total (already in the
   mockup). predict:mlb writes both markets on the next slate;
   snapshots after; coverage reported.
M-QA: plantings (a run-line rung other than ±1.5; a total merged
with the moneyline curve; an undated total SD; a total asked from a
market value); renders of a run-line tile and a total tile; the
ticked checklist; verify.py; /closeout; push.

########################## MODEL REPAIRS ##########################
CFB-1  LADDER EXTENSION (dated change to a declared thing): 45 of 60
       games landed on the last rung. Measure the 2024–25 expected-
       margin distribution, extend the declared spread ladder so the
       top rung is reached by <10% of games, record the old and new
       ladders with the date, RETRAIN the CFB spread fit against the
       new asked rungs (same factors, same games, nothing re-dated),
       re-run the synthetic re-ask of Saturday for the close-out
       only. Saturday's 177 stand (Law 3). Planting: a game whose
       nearest rung is beyond the ladder's top must fail loudly, not
       clamp silently.
CFB-2  ASKED-LINE DEPENDENCY — DOCUMENT, DO NOT CHANGE. Record in
       the factor's note and FOLLOWUPS that cfb_asked_line is now a
       coarsened function of cfb_srs_diff under nearest-margin
       rungs, that its coefficient cannot be read as an independent
       effect, and that what the factor is FOR under this rule is an
       operator ruling. BLOCKED, by design.

=== END OF PASTE ===
