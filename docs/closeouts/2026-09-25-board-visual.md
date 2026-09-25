# GRIDIRON_BOARD — visual and feature pass, 2026-09-25

Brief: `docs/briefs/2026-09-25-board-visual.md` (verbatim, both messages).
Branch `board`, from `e4e29ee`. No live record, no venue, no credentials.

## Running log

### Before anything: the mockup

The morning brief said "the attached mockup"; nothing was attached and the
four files in `docs/mockup/` are the 2026-09-06 designs (no jersey, no glow,
no badge, no prop tile). The operator then pasted the redesign in full; it is
saved verbatim at `docs/design/gridiron-redesign.html`, the path the second
brief names.

### Ruling d, built first (form row keeps green and red)

- `CLAUDE.md` colour law lists the form row's W and L as a permitted use:
  the LETTER'S INK only, never a fill or an outline.
- `audit.colour_law_faults` allows `color` on `.fmark.win`/`.fmark.loss` and
  refuses any other declaration on a form mark by name ("a club's game is not
  a pick").
- `plant_a_value_colour_on_a_form_streak` reversed: it now plants a form mark
  FILLED green and a form mark ringed red, and fails the right way if the
  scan refuses the ink the ruling allows.
- `tests/test_guards.py::test_the_form_row_keeps_its_ink_and_nothing_more`.
- The form row itself is rendered under 3a (game detail stats); the
  overnight board had no form row at all, which the log of 2026-09-25 said.

### Step 1 — match the mockup

**Ported, from `docs/design/gridiron-redesign.html`, under the app's class
names:** the tokens (its `--bg/--panel/--tile/--tile2/--line/--ink/--mute`,
`--win #22e07a`, `--loss #ff4d4f`, `--you #ffb020`, `--live #3d8bff`); the
header (logo, sport tabs, ☰, page pills, pulse); the day heading and legend;
the glow system (`.g-bet/.g-risk` → `.sig-clears/.sig-costs`, `.f-won/.f-lost`
→ `.sig-won/.sig-lost`); the game row (`.row/.status/.teams/.team/.blk/.nm/.sc/
.pick/.pk/.pp/.meta/.badge/.chk/.car/.yours`); the expansion (`.exp/.mkts/.mkt/
.lab/.pk/.probar/.mini/.pay`); the props page (`.pchips/.tiles/.ptile/.ptop/
.jsvg/.pwho/.pbody/.pline/.cush/.pfoot/.tag/.rail/.leg/.fld/.verdict/.ev`);
both breakpoints (1000 and 560); Inter vendored as the sans (`web/fonts/
SOURCE.md`); the jersey SVG verbatim (`jerseySVG`), with the mockup's two
neutrals as the page's tokens and the number drawn only from the record.

**Contrast without muting.** The club block and the tinted band are text
backgrounds, so they take `--club-on-white` -- the primary itself for every
club that passes 4.5:1 with white, the club's darker declared shade for one
that does not -- and the fade's tail, which carries no text, is the primary
at full strength. `tools/contrast.py` measures every club (see below). No
opacity, no desaturation.

**Two defects found by looking, both older than today:**
- **A comment ate a rule.** The board's banner comment of 2026-09-24 opened a
  second comment inside itself, so its second half stood outside any comment
  and the browser read it as the prelude of the next rule -- `.bar { height:
  auto }` -- and dropped it. Both builds shipped with the bar at 52px and the
  second row overlapping the page. Caught by measuring the bar (52px) after
  the capture looked wrong. `audit.stray_comment_marker_faults` now refuses a
  `*/` left standing once comments are blanked, inside the parse check;
  `plant_a_comment_that_eats_a_rule` proves it.
- **A priced row said "venue has not listed this yet".** The Today card
  carried the price's words and the payout but not the price, so the board's
  block read `None`. Unseen because the fixture world never had a price until
  the shaped slate below. `views._today_card` carries `price` now, stripped on
  a live card with `payout`, both added to `LIVE_FORBIDDEN`;
  `test_a_priced_question_carries_its_price_in_words_and_as_a_number`.

**The shaped slate** (`board_shots._mockup_copy`): the fixture week holds four
games and the mockup five, so a fifth is seeded as a copy of the priced game's
total with the sides swapped; a live game, a pick that clears (claim 64% at
54¢, taken), a pick that costs after fees (59% at 60¢, neither side cheap), a
won final and a lost final (scores tried until every pick on one game won and
every pick on the other lost). Coverage is satisfied by sixty invented narrow
quotes, and the copy is thrown away. Props: the three tiles the week poses;
**no alt tile can exist** without a venue read (ruling b), so "six including
alt lines" is three without -- listed under the differences.

**Tests re-pointed, none loosened:** `.pick .badge` → `.meta .badge`;
`.jersey` → `.jsvg`; `aria-expanded` read off the caret and the head (both
carry it); the Manrope-loads test now asserts the vendored body face (Inter)
loads, same assertion; the font-axis test learns Inter's variable axis.
`scrollbar-gutter: stable` on `html` because a row opening on a short page
summoned a scrollbar and moved the page 8.5px (the in-place test caught it).

**Law-caused differences from the mockup**, each with what causes it. The
pairs are `mockup-*` beside `shaped-*` in `docs/closeouts/shots/2026-09-25-visual/`.

| in the mockup | in the app | why |
|---|---|---|
| the active sport tab underlines green; the pulse dots are green | chrome | the colour law: green is the outline of a pick that clears the bar and nothing else |
| the pressed props chip is green | chrome | the colour law |
| the cushion's sign is green or red | ink | the colour law; a cushion is arithmetic against a declared multiple, not a signal (ruling c) |
| prop tiles wear the green or red outline; a props legend explains it | no outline on a tile, no props legend; the verdict in the entry rail wears the colour | ruling c, 2026-09-25 |
| a badge turns green at "proven" | the badge stays n/100 in the record's ink | the colour law; LAW 4 says the count, not a verdict on it |
| "Worth it at 4.8x" | "Clears the bar at 4.8x" / "Falls short at" | plain words: "worth it" is an advice word the scan refuses |
| the live row carries a checkmark | the live row carries YOURS and no control | LAW 5: nothing is sized, priced or taken in-game |
| a 30px checkmark and caret | the same 30px square drawn inside a 44px target | the tap-size rule (`test_every_tap_target_on_the_phone_is_big_enough`) |
| rows are two bands tall | rows carry the flagged-method note on the pick's face | operator ruling 2, 2026-09-04: the caveat stays on the face |
| "best: Underdog 1.2x", ALT/BASE/DEMON/GOBLIN tags, alt-line tiles | "best line not read yet", an ALT tag only when the record holds an alt line (never yet) | ruling b: the pick'em read stays suspended |
| every club carries a typed second colour | the second colour only where the measured file records the club's alternate, white otherwise | no hand-typed club hex, and no network to re-measure |
| the caret rotates | the caret's glyph flips | the motion vocabulary: rotate is a gesture |
| the menu opens on hover | on a press, with `aria-expanded` | not a law: a hover menu has no keyboard or touch path; stated as a choice |
| glow halos as rgba literals | `color-mix` on the token | the colour scan reads `var(--win)`; the hue is written once |
| the pulse hides under 1000px | it wraps under the pills | FIRST SCREEN: a dead job is visible on the first screen the operator opens |
| "Q3 8:14 · polled 0:40 ago" | "3rd Quarter · 8:41 · read just now" | the server composes every word |
| six prop tiles, four alt | the three the fixture week poses, none alt | the fixture, and ruling b |
| the day strip's sentences are absent | "the model has 1 pick that clears the bar…" and the fee line sit under the heading | FIRST SCREEN and LAW 4: the counts and the fee are said in words |

### Step 2 — the PrizePicks polish, and ruling c's verdict

- The tile is the hero: the jersey at 108px, the club gradient behind it at
  55% strength, 16px corners, 18px between cards, the name at 24px and the
  line and chance at 28 and 34px.
- A hue per stat family (`--family-passing/-receiving/-rushing/-scoring/
  -other`, blue/violet/teal/amber/slate, never the two value colours), on
  the chip's dot, the pressed chip and the tile's family tag; each measured
  with white on it in `tools/contrast.py`. A sport pill in the sport's
  declared colour beside both headings.
- **Ruling c's colour, where it is earned:** the entry rail's verdict --
  "Clears the bar at 4.8x" / "Falls short at" from the typed multiple, the
  outline on the verdict block, the thinnest leg's record badge beside it,
  the words the server's. `test_the_rail_verdict_wears_the_colour_a_prop_earns_from_the_typed_multiple`
  takes a prop, types 9 and 1.1, and reads the class and the badge.

### Steps 3, 4 and 5 — My day, sort and filter, game detail, motion, Record

Built together and committed together, because the three features and the
motion all touch the same three files and no half-way state passed the
scans; each is listed here on its own. **Deviation from "commit after each
step"**, stated.

**3b, My day** (`board._my_day`, `renderMyDay`): the taken picks on the
slate as chips under the header on every page -- the club block in the
club's reading shade, the pick, the state in a word (upcoming / live with
the score / won / lost / withdrawn), the record badge. A won or lost chip is
filled like any settled verdict, so `audit.board_signal_faults` walks the
chips too. Counts of picks only; the payload's keys and words are scanned
for stake, payout and total (`test_my_day_holds_the_taken_picks_and_never_money`).
A tap scrolls to the game (`test_a_my_day_chip_scrolls_to_its_game`).

**3c, sort and filter** (`prefGet/prefSet`, one row on Games, one on Props):
start time or the model's chance on Games; cushion or the model's chance on
Props; the market select moved up from the week picker; "clears the bar
only" on Games. Kept per page in the browser, wrapped in try/catch, and the
page renders the same when storage refuses. **Two readings:** the 2026-09-24
brief put no control row above the rows and `audit.PICKS_CONTROL_ROWS` was
empty; the 2026-09-25 brief asks for this bar by name. The later brief is
the operator's later word, so the row is DECLARED in the scanner with its
date rather than slipped past it; a second row is still a fault and the
planting still plants an undeclared one. No "clears the bar only" on Props:
under ruling c nothing on a tile clears, so the filter would match nothing.

**3a, game detail** (`board._detail`, `detailPanel`): inside the expanded
row, above the tiles -- last five for each club from the record's own
finished games (W and L in the ruled colours, the letter's ink), the injury
report as an icon with the names in its tooltip (the report the model
already reads; NFL only, the other sports' loaders carry none), the weather
as an icon with the forecast the weather pass already fetched, and the
factors the pick read as a bar list from the same decomposition the Factors
page shows. Every absence is the server's sentence. The factor phrases are
the registry's own and are read for internal vocabulary and pressure, not
for advice ("how many plays both offences run" is a noun about the game).

**4, motion**, inside the vocabulary the scans enforce (opacity and
transform only, one curve, 200ms, nothing on a number): rows and tiles
arrive with a 30ms stagger; an expansion arrives once when opened; a row
lifts one per cent on hover; the bar fills once on first load by a
transform (`.filling` cleared a frame later) and never on an update
(`audit.bar_fill_faults`, `LIVE_PATCH_FORBIDDEN` in the live-patch scan);
the checkmark pops two per cent when a pick is marked taken (`pop`, the one
one-shot keyframe, which may not loop); the LIVE dot pulses at 1.6s; all of
it off under prefers-reduced-motion. `PRICE_SELECTORS` now names every board
class a price, chance, payout or score is drawn in. Plantings:
`plant_a_bar_that_fills_on_an_update` (a width transition, and a live patch
that re-arms the fill), `plant_a_score_that_animates`.
**Law-caused differences from the brief's list:** no height animation on
expand/collapse (a layout property may not be animated: the expansion
arrives by opacity and a one per cent rise instead), no stronger glow on
hover (an interactive selector may not wear a value colour), 200ms not
250ms (the ceiling).

**5, Record**: two panels. The closing line over time -- `clv_report`
entries carry their measured closes in order as `series` only past the
market's floor, and `gate_words` ("12 of 50") beneath it; `drawSeries` draws
the line with the N in the title and refuses an entry without its N. Taken,
passed over, every forecast -- `calibration.taken_comparison` per market
of the sport, wired into `views.scorecard` as `taken_record`, three curves
each behind the hundred, drawn with the same calibration drawer, words
below the gate; markets with nothing settled are one sentence rather than
three empty cards. Voided and withdrawn rows never enter either (both read
through `resolved` and the door). `tests/test_record_charts.py`.
**Unverified here:** the closing-line chart's drawing on real closes -- the
fixture holds no closed recommendation, so the drawer is tested on a
synthetic series and the payload's shape on an empty report.

## Close-out

### The four rulings, as built

| ruling | built | evidence |
|---|---|---|
| a. jersey numbers from nflverse rosters | `sources.ROSTERS_URL` (`rosters/roster_{season}.csv`, same provider and licence), `loader.load_rosters` at the NFL refresh in `load_all`, table `player_numbers` (declared, dated, `config.ROSTER_NUMBERS_DECLARED`), `board._player_number` by player id and club, never by name alone; fixture rosters carry numbers with one receiver left without; an absent number is an empty slot and its tooltip says so | `test_the_roster_file_fills_player_numbers_and_never_guesses`, `test_the_jersey_is_drawn_from_the_payload_and_no_hex_is_typed` (numbers drawn only where the payload holds one) |
| b. pick'em reads stay suspended | nothing read; every tile says "not read yet"; the Alt lines chip stays empty; `multiple_source` is "declared" on every tile | `test_props_rank_by_cushion_against_the_declared_multiple` |
| c. prop outlines neutral until a multiplier is read or typed | `audit.board_signal_faults` refuses `clears`/`costs` on a tile whose multiple was not read; the entry rail's verdict wears the colour from the typed multiple with a leg's badge beside it | `plant_an_outline_on_a_prop_against_an_assumed_multiple`, `test_the_rail_verdict_wears_the_colour_a_prop_earns_from_the_typed_multiple` |
| d. the form row keeps green and red | CLAUDE.md lists the form row's letters as a permitted use; the scan allows `color` on `.fmark.win`/`.fmark.loss` and refuses a fill or ring on a form mark; the form strip renders in the expanded row | `plant_a_value_colour_on_a_form_streak` (reversed: plants the fill), `test_the_form_row_keeps_its_ink_and_nothing_more`, `test_the_form_streak_wears_its_ink_and_nothing_more` |

### Plantings added today

`plant_an_outline_on_a_prop_against_an_assumed_multiple`,
`plant_a_comment_that_eats_a_rule`, `plant_a_bar_that_fills_on_an_update`,
`plant_a_score_that_animates`; `plant_a_value_colour_on_a_form_streak`
reversed. Each run in-process and CAUGHT; the harness as a whole still
needs the live record to run end to end.

### The brief's phase list

| phase | verdict | evidence |
|---|---|---|
| Before anything: branch `board`, the overnight log read, the mockup opened and captured at both widths | **DONE** | commits from `9341a7f`; `mockup-games/props-{1300,390}.jpg` |
| 1. Match the mockup: port the CSS, the jersey verbatim | **DONE** | the board block and tokens are the mockup's; `jerseySVG` is the mockup's template with the page's two neutrals; `shaped-*` beside `mockup-*` |
| 1. Contrast without muting; every club measured | **DONE** | `--club-on-white` behind text only, the primary in the fade; `tools/contrast.py` measures 562 club pairs, worst 4.51:1 (CFB TOW), all pass |
| 1. The fixture slate in the mockup's shape; side-by-side pairs; the law-caused list | **PARTIAL** | five game states built and captured; **props are three tiles and no alt line** (ruling b, no venue read); the difference list is in the Step 1 section with a law on each row |
| 2. PrizePicks polish: hero tiles, family chips, sport pill, club colours everywhere | **DONE** | `shaped-props-*`; a hue per family measured; the tile's gradient is the club's |
| 3a. Game detail: form, injuries, weather, factors | **DONE** | `board._detail`, `detailPanel`; NFL injuries only (the other loaders carry no report); `test_the_detail_panel_says_every_absence_in_words` |
| 3b. My day strip | **DONE** | `board._my_day`, `renderMyDay`; two tests; the won/lost fill at two classes -- a defect caught by looking, see below |
| 3c. Sort and filter, persisted | **PARTIAL** | Games: time / chance, market, clears only; Props: cushion / chance, family chips. **No "clears the bar only" on Props** (ruling c: nothing on a tile clears). The control row is declared with its date (two readings in the Step 3 section) |
| 4. Motion | **PARTIAL** | stagger, arrival, hover lift, one-shot fill, pop, live pulse, reduced-motion; **no height animation and no stronger hover glow** (the vocabulary and the colour law); two plantings, the price planting covers the new classes |
| 5. Record: closing-line chart per market, three curves per sport, tables as now | **DONE** | `taken_record`, `series`, `drawSeries`; below the gate the words "NN of 100"; `tests/test_record_charts.py`; the drawer on real closes is unverified here |
| 6a. jersey numbers from nflverse | **DONE** | see the rulings table |
| 6b. pick'em reads suspended | **DONE** | nothing read |
| 6c. prop outlines neutral; planting | **DONE** | `plant_an_outline_on_a_prop_against_an_assumed_multiple` |
| 6d. the colour law lists its uses; scan and plantings | **DONE** | CLAUDE.md, `colour_law_faults`, the form-mark planting reversed |
| 7. Unchanged laws | **DONE** | every existing scanner and planting re-run; Live rows carry no control; sports side by side; the footer and Settings text from CLAUDE.md untouched |
| After each step: tests, captures, commit, push | **PARTIAL** | five commits, not eight: steps 3, 4 and 5 share one (stated above); captures at 1300 and 390 after each |
| Running log | **DONE** | this file |

### Bugs I introduced, and how they were caught

- **A comment ate a rule** (2026-09-24, mine): the bar's `height: auto` never
  applied on either build. Caught by measuring, not by a test; the scanner
  `stray_comment_marker_faults` and its planting close the class.
- **"Venue has not listed this yet" beside a payout** (2026-09-24, mine): the
  Today card never carried the price as a number. Caught by looking at the
  first priced slate; `test_a_priced_question_carries_its_price_in_words_and_as_a_number`.
- **The name column wrapped one letter per line** in the detail panel
  (today): a grid column sized `auto` beside long words. Caught by looking;
  no test reads layout at that grain.
- **A won chip in My day lost its fill** to the chip's own ground (today,
  the same class of defect the tile's fill had on 2026-09-24). Caught by
  looking at `shaped-props-390.jpg`; fixed at two classes; **no test asserts
  the chip's painted colour** -- a FOLLOWUPS line, because the shared world
  has no taken settled pick on the current slate to paint.
- **A stray block pasted into `language.py`** by a script that reused a
  variable name; caught at once by `py_compile` before anything ran.
- **The page scrolled 8.5px on opening a row** (a scrollbar appearing);
  caught by the existing in-place test, fixed with `scrollbar-gutter`.

### Vacuous passes named

- `test_a_my_day_chip_scrolls_to_its_game` takes a pick if none is taken and
  asserts the page scrolled; it does not assert the chip's colour.
- The closing-line chart is exercised on a synthetic series only.

### What could not be verified here

- `python tools/verify.py` and `plant.py` end to end (the live record).
  Every web planting and every new one ran in-process and was caught; every
  gate check that reads the tree passes on the final commit.
- The board against the live record: real club names on the bands, a real
  jersey with a real number, the closing-line chart on fifty real closes, a
  live game's pulse and score patching under the new classes.
- The roster file's columns (`gsis_id`, `jersey_number`, `team`) are as
  nflverse documents them; no fetch was made, so the first refresh on the
  operator's machine is the first read.
- **An order-dependent failure I could not root-cause inside the cap:**
  `test_a_card_expands_in_place_and_shows_the_why` fails when `test_smoke.py`
  runs before `test_cards.py` (`pytest tests/test_smoke.py tests/test_cards.py`,
  reproduced twice) and passes alone, with its neighbours, and with
  `test_cards.py` first. The measured movement equals the card's own top, so
  the node the test holds is detached after the click -- a re-render landed
  during the 250ms wait. Not reproduced by hand on a world with taken picks
  and chips. It began with this pass; the candidates are the arrival stagger
  (`--i`, a transition-delay on `.game`) and a second `renderGames` after the
  one the opener awaits. Left open, named in FOLLOWUPS, not loosened.

### Spend

Not measurable in dollars from inside the session. This pass ran in one
context window from the morning brief to the close-out with no sub-agents;
the window's own usage is not reported to it. Measured against the previous
night (2.34M sub-agent tokens for the map alone, "well inside $60"), this
pass is smaller and inside the $50 cap; stated as an estimate, not a reading.

### For the operator, in order

1. **Look at the pairs** in `docs/closeouts/shots/2026-09-25-visual/`
   (`mockup-*` beside `shaped-*`) and rule on the differences table: each row
   names its law, and two are choices rather than laws (the hover menu; the
   400 to 700 Inter axis).
2. **Rule on the control row**: the sort-and-filter bar is declared in
   `audit.PICKS_CONTROL_ROWS` on the strength of this brief against the
   2026-09-24 one; if that reading is wrong the bar moves under the rows.
3. **Run the gate** on the machine with the record: `python tools/verify.py`
   (step 2 gains "the bar fills once, on load"). The harness registers 283
   plantings.
4. **Run a refresh** so `player_numbers` fills from the roster file, then
   open Props and look at a real jersey.
5. **Open Record** with the live record: the closing-line chart draws only
   where a market has fifty measured closes.

Three verdicts (yours, not mine): strongest thing ___ ; weakest thing ___ ;
what to do next ___ .
