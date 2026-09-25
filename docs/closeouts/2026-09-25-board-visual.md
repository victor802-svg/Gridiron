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
