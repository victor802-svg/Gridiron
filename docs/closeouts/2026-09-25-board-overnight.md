# GRIDIRON_BOARD — overnight build log, 2026-09-24/25

Brief: `docs/briefs/2026-09-24-board-overnight.md` (saved verbatim as the
first act of the session). Branch: `board`, from `origin/master` at `fe4dc58`;
the same commits are also pushed to `claude/jolly-tesla-7ue0v7`, the branch
the cloud harness designates. Never merged, never pushed to master, no PR.

This file is the running log the brief asks for. It is written as the work
goes and finished with the close-out table, in that order, so the table is
checked against the brief rather than written from memory.

## Deviations from the brief, stated first

1. **The mockup did not arrive.** The brief names an attached
   `gridiron-redesign.html`; no such file reached the session (not in the
   repository, the scratchpad or anywhere on disk). The brief says it wins over
   the mockup wherever they disagree, so the build follows the brief's text
   alone. Where the brief is silent on a detail the existing approved mockup
   (`docs/mockup/gridiron_dark.html`) and the current stylesheet decide it.
2. **The record holds no jersey numbers.** The brief says "jersey numbers come
   from the roster the record already loads". Measured before building: no
   table in `gridiron/schema.sql` has a jersey or uniform number column
   (`player_week_stats`, `nba_player_games`, `mlb_people`, `player_crosswalk`
   were read), and a case-insensitive search of the package, the fixtures and
   the docs for "jersey" finds nothing. No new data source tonight, so the
   jersey template renders the surname on its nameplate and carries a number
   only where the payload provides one — which is nowhere until a roster with
   numbers is loaded. The tooltip says "no number on record" in those words.
   Needs the operator: whether to add numbers to the roster load.
3. **No pick'em venue is read, so there are no line multipliers to rank by.**
   `docs/PRIZEPICKS_FEASIBILITY.md` (2026-09-02) records that the projections
   feed is behind bot detection and nothing was built; the market module
   names no pick'em source and the record holds no line with a multiplier or
   an alt-line flag. The cushion is therefore computed against a DECLARED,
   DATED constant — a two-pick standard entry paying 3x, per-leg break-even
   1/√3 — and every prop tile says "not read yet" for its venue line in those
   words. The "Alt lines" chip exists and shows the not-read-yet state until a
   venue is read. The high-end-calibration badge is composed and tested against
   a synthetic alt tile; no shipped tile carries it yet.
4. **"Worth it" is on the advice-word list.** `audit.ADVICE_WORDS` bans the
   phrase from every composed label (THE_SHORTLIST S2). The brief uses it as
   the name of the green-outline state; the page keeps saying "clears the bar",
   which is the phrase the record already uses, and the rule the brief states —
   that the signal never renders without its badge — is enforced on the state
   whatever it is called.
5. **Python.** `gridiron/model/llm.py` line 229 uses a multi-line f-string
   expression, which Python 3.12 accepts and 3.11 does not; the container's
   default `python` is 3.11, so the suite is run under a 3.12 venv. Nothing in
   the tree changed for this.

## Two readings, and the one taken

- **"Nothing else uses those colours."** Reading A: the amended colour law
  lists four pick signals and retires every other use — the W/L colours on a
  club's form streak (operator ruling 2026-09-09), the green on yesterday's
  "right" count and the greeting's "correct" count, the green/red edge text.
  Reading B: the amendment speaks of picks and leaves a club's game alone, as
  the 09-09 ruling did. The conservative reading is A (fewer places wear the
  colours), and that is what is built; the form streak keeps its W/L marks in
  weight rather than hue. If the operator meant B, the 09-09 ruling is
  restored by one stylesheet rule and the scanner's allowance for `.fmark`.
- **The nav ruling.** `audit.nav_faults` rules the nav at four pages
  (GRIDIRON_13 R4). The brief, an operator ruling of 2026-09-24, makes it two
  page tabs and a menu of three. The scanner is re-ruled to the brief's shape
  rather than deleted, so a sixth entry still fails by name.

## Running log

### Checkpoint 1 — `38df569` (layout, Games, expansion, Props, rail, signals, tooltips)

Built and pushed to `board` and `claude/jolly-tesla-7ue0v7`. Everything the
brief lists under LAYOUT, GAMES PAGE, PROPS PAGE and SIGNALS is on the page;
what follows is what was measured and what is still open.

**Verified so far**
- Every renderer scanner passes on the new `app.js`: duplicate definitions,
  dead selectors, composed prose, the render guard, the live update, the
  in-place toggle, countdown, resolved rows, nav, control rows, live poll.
- Every stylesheet scanner passes: motion vocabulary, price animation, frame
  truncation, hidden rule, live mark, transforms, and the AMENDED colour law
  with zero faults after the sweep (23 before it).
- The board's own guards pass on the fixture world: no signal without a
  badge, no typed club hex, no live row with a price, no internal word or
  pressure word on a row, a tile or a tooltip.
- Nine new plantings caught, plus every existing web planting re-run
  individually and caught (the two that anchored on the old markup were
  re-pointed). `tools/guards/plant.py` as a whole cannot run here: several
  plantings read the operator's live record and the harness stops at the
  first `unable to open database file`. Same for `tools/verify.py` steps 2-4.
- `tools/contrast.py`: every pair meets AA, including ink on the two solid
  fills (9.60:1 and 6.81:1).
- Server-side test files touched by the board pass (`test_card_face`,
  `test_three_states`, `test_night_audit`, `test_today`, `test_laws`,
  `test_audit_surfaces`, `test_voids`, `test_health_words`, `test_yesterday`,
  `test_combos`, `test_recommend`, `test_guards` except the rows below).

**Failing here and not the board's** (they fail on `origin/master` in this
container the same way): every test that opens the live record
(`test_the_package_holds_no_venue_credential`,
`test_every_verified_run_line_in_the_record_agrees_with_its_price`,
`test_superseded_forecasts_are_not_in_the_arithmetic`,
`test_a_factor_set_query_still_returns_its_own_rows`,
`test_the_planted_violation_harness_catches_everything`), and
`test_the_csrf_token_is_bound_to_the_session`, which passes only when an
earlier browser fixture has exported the token variable — an ordering
dependence that predates tonight and is listed for the morning.

**Where the old Picks page's pieces went** (the brief's list):

| element | now |
|---|---|
| `#/week` (Picks), `#/live`, `#/today`, `#/picks` | redirect to `#/games` |
| the Upcoming / Live state tabs | gone; a row's state is on the row (LIVE mark, FINAL mark) |
| the market tabs above the cards | gone (no control above the first game); the Market select beneath the rows narrows every row, and the Props chips carry the per-family counts |
| Clears the bar / Watching group headings and chips | gone; the green outline on a row's pick IS "clears the bar", the day strip counts them |
| the CARD_FACE card (`todayCard`) | the game row's pick block and the question tiles behind it |
| the price row (Model / Pays boxes), the edge line | probability, price and payout beneath the pick; the edge in the tile's `edge_words`; the signal's meaning in its tooltip |
| the tier chip | gone from the board; the record badge "12/100" is the count on every row and tile; `.tier` still renders on Results |
| "I took this" | the checkmark button on every upcoming tile (`picks_taken`, unchanged) |
| Yours badge | YOURS on the row |
| the Why body: numbers line, reasons, link to the workings | the numbers line is the probability's tooltip, the reasons are the pick's tooltip, the link sits at the foot of the expanded row |
| the flagged-method note | on the pick block's face and on the tile (operator ruling 2, 2026-09-04, kept) |
| the form line, starter, weather | not on the board (the brief's row has no context line); the data still travels on `cards[]` |
| the day strip (where / counts / note / fee) | top of Games, unchanged |
| the pulse (three ages, held markets) | the header, on every page |
| the Combos group | beneath the rows on Games, unchanged |
| Taken today rail | beneath the rows on Games, shown when it has entries |
| the yesterday strip, the week picker | beneath the rows on Games |
| the settled cards on Results | the same question tile, filled with its verdict |
| the greeting | above the day strip on Games |

**Tests retired rather than re-homed** (each with its reason, none loosened):
the STRONG-by-default block in `tests/test_cards.py` (eight tests reading
`#week-tier-seg` and `#week-counts`, controls THREE_STATES removed on
2026-09-08; they had passed by skipping since), and the three skipped
"RE-POINT NEEDED" tests in `test_smoke.py` stay skipped as they were.

**Open after this checkpoint**: the browser suites are being re-run against
the re-homed selectors; the jersey's nameplate needs polish; the empty states
and the live and final rows need their screenshots; the log's close-out
table.

### Checkpoint 2 — `81c9069` (tests re-homed, the board's own tests, captures)

- The eight browser suites the board touches — smoke, cards, tabs, empty,
  rapid, hidden, motion, settled line — re-run green after the re-homing
  (`EXIT 0`, one run, 2026-09-24 ~11:30Z).
- `tests/test_board.py` (13 tests) holds the board's own promises and passes.
- Two defects found by looking at the captures, both fixed: a live prop tile
  carried its venue line (the existing live guard named it by field — caught
  by a test, `test_board.py`), and the settled fill lost to the tile's own
  ground because both rules were one class deep (caught by looking; the
  computed-style probe in `zoom_settled.py` is what saw it, and
  `test_board.py::test_the_jersey...` does not cover it — see the vacuous-pass
  note below).
- `tools/board_shots.py` writes 22 captures to
  `docs/closeouts/shots/2026-09-25-board/`: every page at 1100 and 390, the
  expanded row, a settled slate, the live row with YOURS, the Props page with a
  taken leg in the entry rail, and the two empty states.

### Checkpoint 3 — `6738a84` (greeting off-home, the rail's Kalshi line, the painted fill)

- The greeting's countdown line no longer renders under the Props tabs
  (`applyRouteVisibility`); the entry rail's Kalshi line says "not listed"
  with the reason in its tooltip; `test_a_settled_pick_is_painted_solid_and_its_words_are_ink`
  reads the computed background and ink, closing the vacuous pass named below.

### The full suite, one run, after checkpoint 3

`pytest -q -m "not slow" --deselect tests/test_the_network_is_shut.py` on
`6738a84`, in this container, 2026-09-24:

| | count |
|---|---|
| passed | 1419 |
| failed | 17 |
| skipped | 5 |

**Every one of the 17 fails on the same line:** `db.read_the_live_record`
raising `unable to open database file`, because this container has no live
record (the brief: "you have no live record and must not ask for one"). They
are the record-reading tests in `test_cfb`, `test_distributional`,
`test_guards`, `test_method_flag`, `test_mlb_markets`, `test_plain_why`,
`test_side_arithmetic` and `test_tier_table`, and each is in the baseline
list taken on `origin/master` in this container before the board was built.
Nothing fails here that did not fail on `master` the same way; two baseline
failures now pass (`test_the_variable_axis_covers_every_weight_the_page_asks_for`,
re-homed for the static Barlow faces, and the network test, deselected
because it probes the block with a real socket). `test_the_csrf_token_is_bound_to_the_session`
passed in this run because the browser fixtures ran first; its order
dependence stands in FOLLOWUPS.

Every gate check that reads the tree rather than the record (34 of them, the
web scanners and the closure, orphan, docstring, order-path and door checks)
was run directly on this commit and passes.

---

## Close-out

### The brief's phase list

The brief's order was layout → Games → row expansion → Props and jerseys →
entry rail → signals and badges → tooltips → empty states → polish, with a
commit after each. **Deviation:** the steps were built together and committed
as three checkpoints rather than nine steps, because the old Picks markup and
the new rows could not both satisfy the control-row scanner for long enough
to test a half-way state; each checkpoint was tested and pushed.

| phase | verdict | evidence |
|---|---|---|
| Layout: dark look, condensed face for names/scores/picks/numbers, sans elsewhere | **DONE** | Barlow Condensed 700/800 vendored with provenance (`web/fonts/SOURCE.md`, `OFL-barlow-condensed.txt`), on `.tname .tri .tscore .pick-line .pick-prob .q-line .prop-player .prop-prob .jersey-*`; every pre-board rule that reached for `--cond` asks for the body face. `test_cards.py::test_the_condensed_face_is_where_the_brief_put_it` holds both directions |
| Top bar: sport tabs; Games/Props tabs; ☰ menu with Record, Results, Settings | **DONE** | `index.html` header; `audit.nav_faults` re-ruled to two tabs and a menu of three with three plantings; `test_smoke.py::test_the_nav_is_two_tabs_and_a_menu_of_three` opens the menu and follows a choice |
| Picks/Live/Today removed by name; where each piece went | **DONE** | `#/week #/picks #/live #/today` redirect to Games (`test_every_old_route_redirects`); `state-tabs`, the groups and `applyStateTab` are gone (`test_three_states.py`, `test_night_audit.py`); the table in Checkpoint 1 above lists every element's new home |
| Pulse line in the header, stale in bold warning ink | **DONE** | `#day-jobs` in `.bar-under` on every page via `/api/pulse` and every slate fetch; `.day-job-stale` bold warning ink, never red (`test_night_audit.py::test_the_strip_carries_the_pulse...`) |
| Games page: scoreboard rows, club-colour blocks, tinted name band, scores when live/final | **DONE** | `board.build` → `gameRow`; colours from `views.team_colours` off the measured file; `board-games-1100.jpg`, `live-games-1100.jpg`, `settled-games-1100.jpg` |
| The pick the most pronounced element, with probability, price and payout beneath | **DONE** | `.pick-line` 26px condensed; `.pick-under` carries `prob_words`, `price_words`, `pays_words`; an absence is said once |
| Row expands in place to every bet, every market, both forecasters | **DONE** | `game-more` already in the tree, revealed by `const toggle` (the in-place scanner reads it); `_other_forecaster_rows` adds the other forecaster's standing rows labelled and never ranked against the page's; `test_board.py::test_the_expanded_row_holds_both_forecasters_and_never_merges_them`, `::test_the_row_expands_in_place_to_every_question_on_the_game` |
| Live rows: LIVE, period and clock, last poll; pick shows "pregame NN%", no glow, no price, no size | **DONE** | `board._question_block` strips every actionable field on a live row; `LIVE_FORBIDDEN` extended with the board's field names; `plant_a_price_on_a_live_row`; `test_board.py::test_a_live_row_carries_the_game_and_the_pregame_figure_only`; `live-games-1100.jpg` |
| Props: tiles three across, the generic jersey from the colour file, numbers from the roster | **PARTIAL** | Tiles and the SVG jersey are built (`jerseySVG`): V-neck and two sleeve bands in the second colour, seams, mesh, sheen, arched nameplate scaled to the surname, number outlined in the second colour WHEN THE PAYLOAD CARRIES ONE. **The record holds no jersey numbers** (deviation 2), so no number renders and the tooltip says so; the second colour exists only where the colour file's reading shade is the club's alternate, white otherwise. `plant_a_hand_typed_club_hex`; `test_board.py::test_the_jersey_is_drawn_from_the_payload_and_no_hex_is_typed` |
| Best line on the tile, other lines in the tooltip; "not read yet" where a venue is not read | **DONE** | Every tile: the record's own line, `venue_words` "not read yet" in those words, the tooltip saying where other lines would sit. No new source |
| Rank by cushion against the per-leg break-even of a 2-pick standard entry; Alt lines chip; a chip per stat family | **PARTIAL** | Cushion = shown probability − 1/√3 against `config.PICKEM_TWO_PICK_MULTIPLE` (declared, dated) because **no line carries a multiplier** (deviation 3); ranking is monotone in probability until a venue is read; chips from `config.SPORT_PROP_MARKETS` with counts, Alt lines present and permanently empty with its own sentence. `test_board.py::test_props_rank_by_cushion_against_the_declared_multiple` |
| The break-even as the white tick on the probability bar | **DONE** | `.pbar-tick` at `breakeven`, with the words in its tooltip |
| Entry rail: legs, "venue pays" the operator types, three EV lines, floor | **DONE** | `renderEntryRail`/`entryLines`: legs are the taken props on the slate (`picks_taken`, unchanged); the multiple typed; model, "if half as good" (each leg's cushion halved against the typed multiple's break-even), Kalshi where listed ("not listed": Kalshi carries no prop), floor = 1/Π p. Labels the server's; `live-props-1100.jpg` shows a leg |
| Colour law amended, recorded in CLAUDE.md with the old text beneath; `colour_law_faults` updated; each case planted | **DONE** | CLAUDE.md "The colour law — AMENDED 2026-09-24"; `audit.colour_law_faults` reads state and form; five plantings (`plant_a_fill_on_a_pick_that_only_clears`, `plant_an_outline_on_a_pick_that_won`, `plant_a_red_fill_on_a_pick_that_only_costs`, `plant_a_value_colour_on_a_form_streak`, plus the two older ones); the stylesheet's 23 other uses swept |
| Record badge on every tile and row; the high-end badge on alt tiles; no signal without its badge (plant it) | **DONE** | `badge_words` "n/100" on every block; `high_end_badge_words` composed and demanded by `board_signal_faults` for an alt tile; `plant_a_glow_without_its_badge`. "Worth it" is not the label (deviation 4) |
| Taking a bet: tap → amber checkmark, row shows YOURS, writes to `picks_taken` as today | **DONE** | `takeButton` POSTs `/api/taken/{id}` with the form token, re-renders; `.q-taken` amber inset and `take-done`; YOURS on the row; `live-games-1100.jpg`, `live-props-1100.jpg` |
| Explanations in tooltips on the numbers; the plain-words scan applies to every tooltip | **DONE** | `tips` on every block, composed in `language.py`; the numbers line and the reasons moved into tooltips; `audit.board_words_faults` scans every text and every tooltip for internal words, pressure and advice; `plant_a_tooltip_with_internal_vocabulary`; `test_board.py::test_a_tooltip_shows_the_payloads_words_on_hover` |
| Unchanged laws: no price animation, no countdown, banned words, Live carries no size/price/tap, LAW 6 never summed, footer and Settings law text from CLAUDE.md | **DONE** | Every existing scanner and planting re-run and caught; the CLAUDE.md amendment parses (`laws.read_laws()` 6 laws, `prohibitions()` 4) and Settings' "Rulings in force" and the footer still render from it |
| Empty states: nothing clears the bar; no games today; props not read yet | **PARTIAL** | No games today and props not read yet: `empty-games-*.jpg`, `empty-props-*.jpg` (NBA in the fixture world). Nothing clears the bar: the day strip already says so in words and `nothing_clears_words` is composed for a PRICED slate where nothing clears — the fixture world has no venue prices, so that sentence has no capture; the day strip's "nothing that clears the bar" is what the captures show |
| After each step: tests, screenshots at 1100 and 390, commit, push | **PARTIAL** | Three checkpoints, not nine steps (deviation above); each tested and pushed to both branches; captures by `tools/board_shots.py` at both widths |
| Running log | **DONE** | This file |
| Close-out: log, screenshots, removed routes and their pieces, spend, operator list | **DONE** | This section, `docs/closeouts/shots/2026-09-25-board/`, the table in Checkpoint 1, the two lists below |

### Bugs I introduced, and how they were caught

- `viewChoice` was cut with the tier block and `renderGames` threw on boot —
  caught by looking at the first capture ("viewChoice is not defined" in
  `#error`), not by a test: the browser suite had not been re-homed yet. The
  page's own error box was read first this time (MENTOR §3).
- A pick with no price said "venue has not listed this yet" twice — caught by
  looking at the capture; the "Payspays" class of defect. Fixed in `board.py`;
  `test_the_card_says_nothing_the_server_did_not_write` does not cover it.
- The settled fill lost to the tile's own ground (equal specificity) — caught
  by a computed-style probe while looking; no test asserted the fill was
  painted. **Vacuous pass named and closed:** `test_board.py` checked the
  payload's signal and the badge, not the computed background;
  `test_a_settled_pick_is_painted_solid_and_its_words_are_ink` now reads the
  painted background and the ink on a settled slate.
- A live prop tile carried `venue_words` — caught by the existing
  `live_card_faults` guard through `test_board.py`.
- The greeting's countdown line rendered under the Props tabs — caught by
  looking at `live-props-1100.jpg`; fixed in `applyRouteVisibility`.

### What could not be verified here

- `python tools/verify.py` (all four steps) and `tools/guards/plant.py` as a
  whole: both read the operator's live record and stop without it. Every
  planting that does not was run one by one in-process and caught (44 web
  plantings plus the ten new ones); every audit check the gate runs on the
  web files was run directly and passes.
- The live record's own slate on the board: all captures are the fixture
  world (synthetic NFL 2025 with tricodes for names). Team names, real
  prices, the green and red outlines on a priced slate, the "nothing clears
  the bar" sentence, and a real club's jersey have not been seen.
- The service worker's new shell list against a real browser cache.

### Spend

Not measurable in dollars from inside the session. Measured in tokens: the
map workflow spent 2.34M sub-agent tokens (8 agents, 429 tool calls); the main
session's own context is not reported to it. At published per-token rates the
whole night is well inside the $60 cap, but the number is an estimate, not a
reading, and is stated as one.

### For the operator, in order

1. **Rule on the four open ends** in `docs/FOLLOWUPS.md` (2026-09-25): jersey
   numbers in the roster; a pick'em venue this app may read; whether a prop
   tile's cushion may wear the green outline; whether the form streak keeps
   its colours under the amended law.
2. **Look at the live record on the board** before merging: `python
   tools/board_shots.py` against the record is not what the tool does (it
   builds the fixture world on purpose), so open the page. What to look for:
   a priced slate's outlines, the day strip's "nothing clears" sentence, the
   club names on the tinted bands, and a real jersey.
3. **Run the gate on the machine that has the record:** `python
   tools/verify.py`. Step 2 now carries three more rows (a signal carries its
   badge; no club colour is typed; the board speaks plain, tooltips
   included). The harness registered 270 plantings on `master` and registers 279 here (nine added, none removed, counted off `main` by name).
4. **The csrf test's order dependence** (FOLLOWUPS) predates tonight and is
   one line to fix.

Three verdicts (yours, not mine): strongest thing ___ ; weakest thing ___ ;
what to do next ___ .
