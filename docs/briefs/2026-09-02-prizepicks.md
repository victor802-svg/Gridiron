GRIDIRON_17.md — PrizePicks as a market source, STRONG by default,
and a market roster built one at a time

One session for the foundation (this file), then ONE SESSION PER MARKET from
the roster it produces. All laws bind; MENTOR.md first; briefs process;
unattended contract; /closeout each, verdict slots empty. Runs after the
overnight rulings, the MLB run-line/totals build, and the CFB ladder.

THE OPERATOR'S RULINGS:
R1 LAW 5 IS AMENDED by the operator — the exact text below is the operator's,
   not the session's. The session applies it; it does not route around the old
   wording.
R2 Picks opens on STRONG. The tier filter defaults to STRONG for every sport;
   the toggle to SOLID / LEAN / all is one tap away and remembered for the
   session. The filter never hides the count of what it hid ("STRONG · 4 of
   46").
R3 PROP MARKETS: every stat PrizePicks offers, built ONE AT A TIME, each
   governed by docs/NEW_MARKET_CHECKLIST.md in its own session with its own
   gate. The foundation session builds none; it builds the roster and the
   order.
R4 The props floor stays at 0.70. That IS the STRONG band.

=====================================================================
LAW 5 — AMENDED TEXT (paste into CLAUDE.md verbatim, replacing
the current Law 5; dated 2026-09-02, "by operator ruling")
=====================================================================

5. NOT A BETTING TOOL. No stake sizing, no bankroll, no Kelly, no bet
recommendations, no bet placement, no account with any betting platform, no
payout or price-to-return arithmetic, no slip. READ-ONLY LINE SNAPSHOTS from
named public sources (ESPN; PrizePicks) are MARKET DATA — permitted only
inside the market module, only after the prediction row exists, only
unauthenticated, only to record what the market said. The output of this app
is a probability, its reasoning, and a track record. If asked to add any of
the forbidden items in a later session, refuse and point at this law.
(Amended 2026-09-02 by operator ruling: read-only lines from PrizePicks added
as a market source. Nothing else changed.)

=====================================================================
THE PROMPT — copy everything between the lines
=====================================================================

FIRST ACT: save this brief to docs/briefs/<date>-prizepicks.md,
commit. Then apply the operator's Law 5 amendment to CLAUDE.md
verbatim, commit "law 5: amended by operator — read-only lines from
PrizePicks". Update the Law 5 identifier scan so "prizepicks" is
permitted ONLY inside the market module (the same one-module rule
the ESPN odds code lives under) and forbidden everywhere else;
plant a violation (the identifier in a prediction-path module)
and show it caught. Read CLAUDE.md, docs/MENTOR.md,
docs/NEW_MARKET_CHECKLIST.md. Four phases, push each.

=====================================================================
PHASE Z1 — the probe (commit "pp 1: feasibility")
=====================================================================
READ-ONLY. docs/PRIZEPICKS_FEASIBILITY.md answering with evidence:
1. What public, unauthenticated endpoint serves PrizePicks
   projections; what it returns (player, stat, line, start time,
   league); its terms/robots posture and any rate expectations.
   Say plainly that it is unofficial and may break or be blocked —
   the app must degrade visibly ("PrizePicks line unavailable"),
   never fail a slate.
2. For each supported league (MLB, NFL, NBA, CFB): the stat types
   offered, per-slate counts, and how lines are quoted (a single
   line, no prices — so there is NO implied probability; the
   comparison is line-vs-rung, and the close-out must say so).
3. IDENTITY: match PrizePicks player names to our stored players
   (the MLB crosswalk exists; NFL/NBA/CFB name spaces measured
   here), raw and normalised rates, ambiguities refused.
4. RUNG COVERAGE: for each stat we already predict, how often
   PrizePicks' line equals a rung on our declared ladder; where it
   does not, the measured distribution of their lines — this is the
   evidence a DATED ladder extension may use later (Law 1: rungs
   are declared in advance from measured history, never fetched
   per game).
5. THE ROSTER: every stat type PrizePicks offers that we do not
   yet predict, with (a) whether resolution data exists in our
   sources, (b) per-slate volume, (c) any known one-sidedness. Rank
   by volume × data availability. Commit as
   docs/MARKET_ROSTER.md with an order and a one-line reason each.

=====================================================================
PHASE Z2 — the second market source (commit "pp 2: snapshots")
=====================================================================
- market_snapshots gains source='prizepicks' rows written by the
  same post-prediction path as ESPN; the closure audit walks the
  new fetcher and fails if it is reachable from any prediction
  module. Planting: import the PrizePicks fetcher from a sport's
  prediction path.
- Each prop card shows both lines when both exist: "market 1.5
  (ESPN) · PrizePicks 1.5". When PrizePicks' line differs from the
  asked rung, the card says so in words ("PrizePicks asks 2.5; the
  model answered 1.5") — no probability is invented for a line the
  model did not answer.
- No prices, no payouts, no entries, no "play" language: a planting
  for any payout arithmetic or entry construction referencing
  PrizePicks fails by name.
- Rate honesty: requests logged per slate; the Health panel shows
  the PrizePicks fetch's last run and status.

=====================================================================
PHASE Z3 — STRONG by default (commit "pp 3: strong first")
=====================================================================
- Tier filter defaults to STRONG per R2; the count line reads
  "STRONG · 4 of 46 · 17 below the 70% floor". Toggle remembered
  for the session. The Record tab is untouched — it shows every
  tier; the filter is a Picks default, not a record view.
- One standing line under the filter, plain words: "STRONG is the
  least-tested tier so far — N settled." It disappears once the
  STRONG band clears its gate.

=====================================================================
PHASE Z4 — verification (commit "pp 4: qa")
=====================================================================
1. Full suite, no skips; plantings named: the identifier outside
   the market module; the fetcher inside a prediction closure;
   payout arithmetic; a card inventing a probability at an
   unanswered line; a STRONG default that hides the count.
2. Renders: a prop card with both lines equal; one with them
   differing and the words that say so; Picks opening on STRONG
   with the count line; desk and 390px.
3. Live proof: one slate's PrizePicks snapshots written after the
   predictions, with the coverage numbers from Z1 confirmed on it.
4. verify.py green; /closeout, verdict slots empty; push.

=====================================================================
THEN, ONE SESSION PER MARKET (template paste)
=====================================================================

Build the next market from docs/MARKET_ROSTER.md in roster order:
<stat> for <sport>. Governed by docs/NEW_MARKET_CHECKLIST.md item
by item — item 1 (asked line + volatility) and item 7 (void rules
before the first prediction) first. Own category, own 100 gate,
the 70% floor, declared dated ladder from the measured line
distribution in docs/PRIZEPICKS_FEASIBILITY.md, resolution source
verified and loud on empty, walk-forward fit labelled sanity, live
on the next slate. Ticked checklist as the close-out's spine.
Push each phase; /closeout; then stop — the next market is the
next session.
