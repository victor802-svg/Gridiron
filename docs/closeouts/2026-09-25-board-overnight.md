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

