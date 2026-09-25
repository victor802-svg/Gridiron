# Brief — GRIDIRON_BOARD, visual and feature pass (saved verbatim, 2026-09-25)

Two messages from the operator, in the order they arrived. The first named an
attached mockup that had not arrived; the mockup itself was pasted next and is
saved at `docs/design/gridiron-redesign.html`; the second message, below the
rule, widened the pass and is the one the close-out is written against.

---

GRIDIRON_BOARD, visual pass, ruled by the operator 2026-09-25. Continue on branch "board" (currently e4e29ee). Same constraints as the overnight brief: no merge, no PR, no live record, no venue calls, no credentials, fixture world only. Spend cap $40, reported in the close-out.

THE PROBLEM: the build is less detailed and less colourful than the attached mockup. The brief described the design in words and too much was lost in translation. This pass matches the mockup.

1. PORT, DON'T REINTERPRET. Copy the mockup's CSS for these into the app's stylesheet, adapted only where a law requires it: the team band gradient on scoreboard rows (club block, tinted band, fade), the pick chip size and type, the glow box-shadows (outline strength and blur), the tile surfaces and radii, the probability bar and tick, the badge and checkmark styles, the header and page-tab styles, the type scale (Barlow Condensed weights 700/800 at the mockup's sizes). Port the jersey SVG template from the mockup verbatim: collar, sleeve bands, shoulder numbers, seams, mesh pattern, sheen gradient, arched nameplate scaled to fit.

2. CONTRAST WITHOUT MUTING. Where white on a club colour fails 4.5:1, use that club's darker declared shade for the text background only, and add the pair to the contrast list. Every club that passes renders at full strength. No global desaturation, no reduced opacity on club colour.

3. SIDE-BY-SIDE CHECK. Build a fixture slate that reproduces the mockup's content shape (a live game, a clear-the-bar game, a costs-after-fees game, a won final, a lost final; six prop tiles including alt lines). Capture the app and the mockup at 1300x1100 and 390 wide, and put the pairs in the close-out. Iterate until the differences are only the ones a law requires, and list each remaining difference with the law that causes it.

RULINGS ON LAST NIGHT'S QUESTIONS:
a. Jersey numbers: load roster jersey numbers from nflverse (the provider already used, same licence), as a declared, dated data addition read at the existing roster refresh; no other source. In the fixture world, fixture rosters carry numbers. A player with no number shows an empty slot, never a guess.
b. Pick'em venue read: stays suspended until GRIDIRON_REPAIR and the re-read are done.
c. Prop tile outline: neutral until a real multiplier exists for that line (read or typed). The cushion shows; the green or red outline does not. The entry rail's verdict, from the operator's typed multiplier, is where a prop earns a colour. Plant it: a props tile with an assumed multiplier and a coloured outline fails by name.
d. Form streak: the 2026-09-08 ruling stands. W and L in the form row keep green and red. The colour-law text in CLAUDE.md lists the form row as a permitted use beside the outline and fill rules. Update the scan and plant it.

Close-out: the side-by-side pairs, the list of law-caused differences, the four rulings as built, spend.

---

GRIDIRON_BOARD, visual and feature pass, ruled by the operator 2026-09-25.

BEFORE ANYTHING ELSE
- Work on branch "board". Never merge, never push to master, never open a PR.
- Read docs/closeouts/2026-09-25-board-overnight.md (what was built and why).
- Open docs/design/gridiron-redesign.html in a browser, screenshot both pages at 1300px and 390px, and read its CSS and SVG. That file is the design. The last build never saw it and came out flatter and less colourful. This pass matches it and then goes further.
- Constraints: no live record (fixture world and conftest only), no calls to any venue, pick'em app or data provider except the one nflverse roster addition below, no credentials. Spend cap $50, reported at the end.

1. MATCH THE MOCKUP FIRST
Port, don't reinterpret. Copy the mockup's CSS into the app's stylesheet for the team bands on scoreboard rows, the pick chip, the glow outlines, the tiles, the probability bar and tick, the badges, the checkmark, the header and page tabs, and the type scale (Barlow Condensed 700/800 with fallbacks). Port the jersey SVG template verbatim.
Contrast: where white text on a club colour fails 4.5:1, use that club's darker declared shade behind the text only, and add the pair to the contrast list. Every other club renders at full strength. No global desaturation or opacity on club colours.
Build a fixture slate with the mockup's content shape (live game, clears-the-bar game, costs-after-fees game, won final, lost final, six prop tiles including alt lines). Capture app and mockup side by side at both widths. Iterate until the only differences are ones a law requires, and list each with its law.

2. THEN MAKE IT FEEL LIKE PRIZEPICKS
The operator wants PrizePicks-level polish on top of the dark sportsbook base:
- Player cards are the hero: bigger jerseys, richer club-colour gradients behind them, rounded corners, bold condensed names, the stat and line large enough to read at arm's length.
- Playful but clean. Coloured chips for stat families, a coloured pill for the sport, generous spacing between cards, nothing cramped.
- Every surface uses the club's colours, not grey, wherever it's about a team or player.

3. NEW FEATURES
a. Game detail stats, inside an expanded game row: last-five form strip for each team (W/L marks keep green and red per the 2026-09-08 ruling), key injuries and weather as small icons with tooltips, and the factors the model read, as a short bar list. Only data the record already reads; nothing new is fetched. Anything absent says so in words.
b. "My day" strip under the header: today's taken bets as small chips (team colour, pick, status: upcoming / live with score / won / lost), plus counts. Tapping a chip scrolls to that game. Taken bets only, never money. No stake, payout or total anywhere.
c. Sort and filter bar on Games and Props: sort by start time, by the model's probability, by cushion (Props); filter by "clears the bar only", by market, and by stat family on Props. The choice persists per page in localStorage (wrapped in try/catch).

4. MOTION: a bit more than subtle
Allowed: smooth expand and collapse of game rows (200–250ms), hover lift with a slightly stronger glow, staggered fade-in of rows and cards on page load, probability bars filling once on first load, a small pop when a bet is checked as taken, and a slow pulse on the LIVE dot.
Never: any animation or transition triggered by a price, probability, edge or score changing. When data updates, the new value appears instantly. The existing planting that catches a transition on a price element must cover the new classes; add plantings for the bar fill (load-only, never on update) and the score.
Respect prefers-reduced-motion: all motion off.

5. RECORD PAGE (in the ☰ menu)
- Closing-line chart per sport and market: CLV over time as a line, N in the title, drawn only past its gate. Below the gate, the chart area says "NN of 100" in words and draws nothing.
- Taken vs not taken vs all: three curves per sport, never merged, same gate, same rule.
- Tables beneath, as now. Voided and withdrawn rows are never counted.

6. RULINGS CARRIED FROM THIS MORNING
a. Jersey numbers come from nflverse roster data (the provider already used, same licence), as a declared, dated addition read at the existing roster refresh. Fixture rosters carry numbers. A player with no number shows an empty slot, never a guess.
b. Pick'em app reads stay suspended; tiles say "not read yet" where a line would need them.
c. Prop tile outlines stay neutral until a real multiplier exists for that line (read, or typed in the entry rail). The cushion shows; the coloured outline doesn't. Planting.
d. The colour law in CLAUDE.md lists its permitted uses: green/red outline (clears / costs after fees), solid green/red fill (won / lost), and the form row's W and L. Update the scan and plant each case.

7. UNCHANGED LAWS
Live carries no size, price or taken control. Sports are listed side by side, never summed. The footer and Settings law text render from CLAUDE.md. Record badges on every tile; a green glow or "worth it" never renders without the badge.

HOW YOU WORK
- Order: mockup match, PrizePicks polish, My day strip, sort/filter, game detail stats, motion, Record page.
- After each step: run the affected tests, capture screenshots at 1300px and 390px, commit, push. Fix a broken test before the next step. Never loosen a test to make it pass; plantings must fail on the old code first.
- Keep the running log in docs/closeouts/2026-09-25-board-visual.md.
- If a law's reading is unclear, write both readings in the log and take the conservative one.

CLOSE-OUT: side-by-side mockup pairs; final screenshots of every page, the empty states ("nothing clears the bar", "no games today", "props not read yet") and the My day strip, all at both widths; the list of law-caused differences; the four rulings as built; plantings added; spend; and everything that needs the live record or an operator ruling before merge.
