# Follow-ups

Work deferred with a date, and lessons that need acting on rather than
remembering. Consolidated here 2026-09-01; earlier entries were scattered
through close-outs and are gathered below with their original dates.

---

## Open

### 2026-09-01 — THE SUITE IS TOO SLOW TO RUN WHOLE, AND THAT HID A FAILURE

The full suite takes about fifteen minutes. To fit inside a command timeout it
was being split — browser tests in one run, everything else in another — and
**both halves passed while the whole suite failed.**

The failure was real: `test_side_arithmetic` reads the live record, and the
halves happened to run before the college slate was written into it. A guard
that only fails when the pieces are run together is a guard that a person
under time pressure will not see.

**The gate needs to run whole, so the suite needs to get faster.** Two obvious
routes, neither yet measured:

- **parallelise** — `pytest-xdist` across processes. The browser tests hold a
  server and a Chromium each, so this needs the fixtures checked for shared
  state before it can be trusted;
- **tier it** — a fast tier that runs on every change and a full tier that runs
  before a commit, with the split declared rather than improvised. The risk is
  that the tiering itself becomes the place a failure hides, which is exactly
  what just happened, so whichever tier is skipped must be named in the output.

Until then: **run the whole suite in one process before claiming it is green.**

### 2026-09-01 — `docs/mockup/gridiron_desk.html` is not in the repository

The desk brief (D1–D5) requires it and stops at its first act without it. A
rendered image was supplied in chat, which shows the layout but not the
measurements the brief cites.

### 2026-12-01 — the bowls decision

Whether to forecast college bowl games, and if so whether they are their own
calibration category. Neutral sites break the home-field assumption the margin
model rests on, rosters change between the regular season and a bowl so the
ratings describe teams that no longer exist, and about 40 games bolted onto 890
is a small, systematically different sample. Decide in December with the
regular season's forward record in hand.

### 2026-09-14 — read the rung distribution

Two weeks of `prop_rung_claims`. If below-floor claims cluster at 60–69 near
the mean rung, the floor is working as designed rather than the ladder being
mis-set. `gridiron rungs --sport mlb` refuses to read a verdict before then.

### after the gates fill — the third forecaster

The correction machinery is per (sport, market, forecaster) and the LLM
forecaster has no settled rows at all, so its correction cannot be fitted, let
alone graded. Revisit when any category reaches 200 settled.

### the drift question's read-date

Fifty drift pairs in one category. MLB moneyline is the only candidate and it
stops accumulating on 2026-09-27, so this may not be readable this year. The
report gives the count and nothing else until the gate clears.

### 2026-08-31 — the dead-but-named sweep (ruling 2, its own session)

Run the shadowed-definition guard's question backwards: what other shapes are
dead but read as live? Include an `app.js` orphan scan — nothing automated
looks at that file, which is how `pickSentence` sat there for two sessions
carrying the K1 verb table.

---

## Lessons that need a mechanism, not a memory

### 2026-09-01 — six of nine bugs in the CFB build were found by LOOKING

Renders and printed numbers are outperforming the test suite on interface and
data-shape work. Not a defect to fix — an argument for rendering earlier and
more often, and for treating "the number disagrees with the other number" as a
first-class check.

### 2026-08-31 — a `\b` in a generated regex has corrupted five guards

Fixed by the scanner-fixture ruling: every compiled pattern declares a
known-positive and a known-negative, checked at import. The fifth instance was
`SNAKE_CASE` itself, which had been matching nothing, so the plain-words law's
shape-detecting half was dead while its explicit name list kept working.

### 2026-08-31 — verify a new measurement against a source that CAN change

The drift pass measured the HTTP cache for its first eight rows. Any future
"second reading" of anything needs the same question asked of it: is the second
read capable of differing from the first?

### 2026-08-31 — a run that writes nothing commits nothing

The only commit in the prediction loop is inside `write_prediction`. Any
side-record written during a run must commit its own rows or be lost, as the
first fifteen rung-log measurements were.

### 2026-08-31 — an inert CSS property is invisible

`grid-column` on a flex child; `flex: none` on an item expected to shrink,
twice. Nothing fails; the layout is simply not what the rule says. Worth a scan
for properties inert against their parent's display mode.

### 2026-08-31 — hardcoded lists of sports go stale silently

Four tests hardcoded three sports and broke when a fourth arrived; the schedule
panel's test hardcoded four tasks and broke when a fifth did. All now derive
from `config.SPORTS` and `tasks.TASKS`.

---

## Measured and carried

- **NFL team names cover 30 of 34 tricodes.** LA, OAK, SD and WAS are
  pre-relocation codes with no row in ESPN's current feed.
- **Thirty-two NFL prop rows carry `prop_type = NULL`** (fs1, before 07:34 on
  2026-08-29). Permanent under LAW 3, handled at the reading end. Any new
  consumer must decide explicitly whether it is reading or querying.
- **One college venue could not be geocoded** — Sacred Heart, Fairfield CT.
  237 of 238. Its games have no travel figure, recorded absent.
- **The FCS scoring bias is unquantified.** A lower-division team enters the
  record only through its games against FBS opposition, so its scoring form is
  understated. Worth measuring once a college season has settled.
