# Brief — ruling on player_numbers, 29 September

Saved before execution, as the standing contract requires. The operator's text
is unedited. Given during the board merge, after its merge commit (3148f39) and
before its gate.

---

player_numbers: a loaded roster table, refreshed each load, not append-only; say so in its description. Plain UPDATE then INSERT is fine. It is display only: nothing that forecasts, grades, fits or measures may read it, and a scan refuses any such read.

---

## How this brief is read

- **The description** is the table's comment in `gridiron/schema.sql` (outside
  any declaration's words), CLAUDE.md where the board's rows name it, and the
  loader's docstring: a roster loaded from nflverse, refreshed at each load,
  not append-only, display only.
- **The write** stays as the merge wrote it: an UPDATE, then a plain INSERT
  when no row changed (the Q15 register is not touched).
- **The scan** is an allow-list, the stricter default: the table may be named
  only by its loader (the write), the schema, the database door's own
  migration or init code if it must, and the display code that draws the
  jersey; any other module naming it -- anything in the prediction closure,
  the resolver, the calibration, correction, recount, horizon, drift, priced,
  at-the-line, recommendation, shortlist, bet or model code -- fails by name,
  in gate step 2, with a planting that puts a read of it in a measuring
  module. A name the scan cannot place counts as a read.
