# Brief — GRIDIRON_BOARD, overnight build (saved verbatim, 2026-09-24)

Saved as the first act of the session, per MENTOR.md 4a. The brief refers to
an attached `gridiron-redesign.html`; no such file arrived with the session
(not in the repository, the scratchpad, or anywhere on disk). The brief says
it wins over the mockup where they disagree, so the build follows the brief's
text alone. Recorded in the close-out.

---

GRIDIRON_BOARD, overnight build, ruled by the operator 2026-09-24. You are a cloud session. You have about 9 hours and a spend cap of $60; report spend in the close-out and stop at the cap.

WHERE YOU WORK: a new branch "board" from origin/master. Push it often. Never merge, never push to master, never open a PR. You have no live record and must not ask for one: build and test against the repository's own test fixtures and planting harness world (conftest). No network calls to any venue, pick'em app, or data provider. No credentials of any kind. If something requires the live record or the operator's machine, write it down in the close-out and move on.

THE SPEC: the attached gridiron-redesign.html is the design. Where this brief and the mockup disagree, this brief wins. Mockup names, lines and numbers are placeholders; the build shows what the record holds.

LAYOUT
- Dark sportsbook look. Condensed bold type (Barlow Condensed, with fallbacks) for team names, scores, picks and big numbers; clean sans for everything else.
- Top bar: sport tabs (NFL MLB NBA NCAAF UFC); under them two page tabs, Games and Props; a menu (☰) holding Record, Results, Settings. The old Picks/Live/Today routes are removed by name; the close-out lists where each of their elements now lives.
- The pulse line (daily run / prices / boards ages) stays in the header, stale in bold warning ink past its threshold.

GAMES PAGE (the first screen)
- ESPN-style scoreboard rows, one per game on the slate. Each team line is loud: full club-colour block with tricode, name on a club-tinted band, score when live or final.
- The model's pick is the most pronounced element on the row: large condensed text, probability, market price and payout beneath.
- Clicking a row expands it in place to show every bet the record holds for that game (every market, both forecasters where present), as tiles.
- Live rows: LIVE marker, period and clock, last-poll time; the pick shows "pregame NN%", no glow, no price, no size.

PROPS PAGE
- Tiles, three across on desktop. Each tile has a jersey: one generic SVG template for every club (V-neck in the secondary colour, two sleeve bands, shoulder numbers, stitched seams, mesh and sheen, surname on an arched nameplate scaled to fit, number outlined in the secondary colour). Jersey numbers come from the roster the record already loads. Colours come only from the club colour data file; a hand-typed club hex anywhere fails the gate by name (plant it). No club's real stripe pattern, sleeve design, crest, wordmark or likeness.
- Best line only on the tile; other lines in the tooltip. Where a line comes from a venue the app does not read yet, the tile says "not read yet" in those words. No new data sources tonight.
- Rank by cushion: the model's probability minus the per-leg break-even for that line's multiplier in a 2-pick standard entry. The model itself is never biased toward any line type; alt lines rank high only when their cushion is real. Filter chips: All, Alt lines, and one per stat family.
- The break-even is the white tick on the probability bar.
- Entry rail on the right: legs, a "venue pays" field the operator types, three EV lines (model, "if half as good", Kalshi where listed), floor.

SIGNALS
- Colour law amended by the operator 2026-09-24, recorded in CLAUDE.md with the old text beneath: a green OUTLINE glow means a pick clears the bar; a red OUTLINE glow means it costs the operator after fees; a SOLID green fill means a pick won, a SOLID red fill means it lost. Nothing else uses those colours. Update audit.colour_law_faults and plant each case.
- Every tile and row carries its record badge ("12/100"); alt-line tiles carry the separate high-end-calibration badge. "Worth it" or a green glow never renders without the badge beside it; plant it.
- Taking a bet: tap the tile and it gets an amber checkmark; the game row shows YOURS. It writes to picks_taken exactly as today.
- Explanations live in tooltips on the numbers, not in sentences on the card. The plain-words scan still applies to every tooltip.

UNCHANGED LAWS: nothing animates on a price change; no countdowns; no banned words (parlay, boost, promo, lock, popular, trending, hot, and the rest of the list); Live carries no size, price or taken control; LAW 6 side-by-side never summed. The footer and Settings law text render from CLAUDE.md.

HOW YOU WORK
- Order: layout and navigation, Games page, row expansion, Props page and jerseys, entry rail, signals and badges, tooltips, empty states (nothing clears the bar; no games today; props not read yet), then polish.
- After each step: run the affected tests, capture screenshots at 1100px and 390px, commit, push. A step that breaks a test gets fixed before the next step starts. Never loosen a test to make it pass; plantings must fail on the old code first.
- Keep a running log in docs/closeouts/2026-09-25-board-overnight.md: what was done, what's left, what needs the operator.
- If you are unsure how to read a law, write both readings in the log and take the conservative one.

CLOSE-OUT: the log, final screenshots of every page and the empty states at both widths, the list of removed routes and where their pieces went, spend, and a list of everything that needs the live record or an operator ruling before merge.
