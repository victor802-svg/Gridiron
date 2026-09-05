# Brief — GRIDIRON_18 Session E, Part 2: the build

Received 2026-09-04. Saved before execution, per the unattended contract.
**First act: read `docs/DISTRIBUTIONAL.md` in full; it governs.**

---

GRIDIRON_18 SESSION E, PART 2 — THE BUILD. Unattended contract. Save
as docs/briefs/2026-09-04-distributional-build.md. First act: read
docs/DISTRIBUTIONAL.md in full; it governs.

RULING on §7's tie-break: if the walk-forward splits by sport, ship
PER SPORT — Law 6 makes each sport its own decision. Never average
sports to reach a verdict.

Build in the doc's order:
 1. The blind object on the predictions row (mean, spread,
    family; the measured per-sport SDs already dated), for NFL and
    NBA totals and spreads. CFB totals WAIT for a fitted slope
    (fit it first, dated, then include CFB); MLB totals go to the
    count machinery, not Gaussian.
 2. Resolution: graded at the snapshotted line as a read-out; when
    no line exists, graded continuous (CRPS, dated) — and the doc's
    answer on which line (snapshot vs close) applied exactly.
 3. Calibration: PIT / interval coverage as the distribution's
    honesty check, plus binary calibration at the line for the
    tier table. Law 4 gates unchanged.
 4. THE WALK-FORWARD, BEFORE SHIPPING: read-out at the line vs the
    rung method on identical games, per sport, labelled sanity.
    Ship a sport only if the read-out is better calibrated; report
    the ones that are not and leave them on rungs, dated.
 5. Migration for shipped sports: ladders and asked_line for those
    markets deleted with a dated note; existing rows stand under
    their version; the stale "recorded and not yet used" comment
    fixed.
 6. Cards: the pick at the market's line with its probability once a
    line exists; before that, the expectation in words; the hero
    rule and plain-words scan as the doc specifies. The confidence
    floor question for game markets is now meaningful — report the
    distribution of P(over line) on the first live slate and STOP
    there; the floor is the operator's ruling.
 7. Plantings: a distribution row written after its snapshot; a
    read-out computed from anything but the stored row; a rung
    ladder surviving on a shipped market; a sport shipped without
    its walk-forward verdict recorded.
Renders, full suite no skips, verify.py, /closeout, push. If the
walk-forward says no for every sport, the close-out says so and
nothing ships — the design doc stays as the record of a hypothesis
that failed its test.

---

## How this brief is read

- **The doc's §7 order overrides the numbered list's order.** The list is the
  doc's section order — what to build — and item 4 says "BEFORE SHIPPING" in
  capitals. The doc is explicit: *"Before: the measurement harness only… The
  order matters and is the whole reason for two sessions. Building the schema
  first would make the test a formality that nobody wants to fail."* So the
  harness and the walk-forward run first, and only the sports that pass get
  items 1, 2, 3, 5, 6.
- **The tie-break is now ruled: PER SPORT.** A sport that passes ships; a
  sport that fails stays on rungs with its verdict dated. Sports are never
  averaged to reach one verdict — LAW 6.
- **A sport whose arm cannot run is NOT RUN, not dropped**, per the doc's own
  instruction about NBA line coverage.
- **Item 6 stops at reporting.** The confidence floor is the operator's
  ruling; this session measures the distribution and does not set a floor.
