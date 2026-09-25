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
