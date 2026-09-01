FIRST ACT: save this brief to docs/briefs/<date>-desk-polish.md,
commit. Read CLAUDE.md, docs/MENTOR.md. Four phases, push each.

=====================================================================
PHASE E0 — two checks before any polish (commit only if fixing)
=====================================================================

1. If not already done: rebuild the desktop bundle from HEAD and
   stamp it (commit hash + date in the footer, in words; launcher
   compares bundled commit to repo HEAD and shows "this build is N
   commits behind — rebuild" when they differ; planted mismatch
   without the notice fails). The operator's exe was showing a
   three-week-old screen over a live record.
2. If not already done: every LLM pass has been returning
   llm_unavailable:api_error. Report the actual error, fix if it is
   configuration, confirm the LLM forecaster writes rows on the
   next slate, and make sure the reason renders in plain words
   ("the reasoning model was unavailable") — the raw code was on
   every card.

=====================================================================
PHASE E1 — the pick says the pick (commit "polish 1: the pick")
=====================================================================

The tile "Alabama −24.5 … 76% MISSES" names the favourite and the
question's line while the model's pick is ECU +24.5. Arithmetically
honest, humanly backwards. Fix at the source, not the renderer:
- tile_line for a NO-side spread names the OTHER side with the
  flipped line ("ECU +24.5"), through side_named — the same flip
  the moneyline already performs. The label then reads "covers",
  never "misses". Totals: "Under 51.5" / "Over 51.5" stay as they
  are. Moneyline: "ECU to win".
- The rail's pick sentence, the Why heading, and History rows use
  the same line, so a pick reads identically in all four places;
  a test asserts equality across them.
- Planting: a tile whose pick line names a side different from
  the label's side fails by name.
- Plain-words: rail probability labels are "model" / "market",
  never "MKT" (the D3 fix confirmed present). Prose uses the
  school form ("Temple"), not the mascot form ("Temple Owls");
  headings may use the full name.
- The slate key ("week 20260905") is replaced everywhere by date
  words; the plain-words scan gains a rule: an 8-digit date-like
  string in visible text fails.

=====================================================================
PHASE E2 — tabs, filter, countdown (commit "polish 2: controls")
=====================================================================

- R1 tab records: computed server-side from resolved, non-void
  model predictions per sport, all time; rendered "MLB 33–18";
  hover shows settled and void counts; "0 settled" below any
  result. Law 6 planting: a summed record anywhere fails.
- R2 tier filter as a fourth segmented control beside sort and
  market; remembered per sport in session storage (memory only,
  no browser storage APIs beyond the session); the count line
  updates ("STRONG · 4 of 177 picks").
- R3 countdown: "first kickoff in 3d 4h" from the slate's earliest
  start, ticking each minute, date words beneath; once games are
  underway it reads "in progress · 12 of 60 final"; when the slate
  is done, "complete · 60 of 60 final". The dropdown keeps slate
  choice, labelled by date words.
- The AT A GLANCE panel loses its explanatory sentences
  ("grouped on the league's clock, not yours…") — move them to a
  tooltip on the heading. Panels state facts; they do not narrate
  their own design.

=====================================================================
PHASE E3 — read cold, then verify (commit "polish 3: qa")
=====================================================================

1. Renders before commit at 1440 and 1280 (desk) and 390 (rows):
   a NO-side spread tile, a total, a moneyline, the rail with a
   NO-side pick selected, the tabs with a real record, the
   countdown in all three states (seed a slate in progress and a
   complete one).
2. A READ-COLD pass: for each of five random tiles, write out what
   a first-time reader would say the pick is, in one sentence,
   from the tile alone — and confirm it matches the stored side.
   Report the five in the close-out.
3. Full suite in one process, no skips; all plantings named.
4. verify.py green; /closeout, verdict slots empty; push.
