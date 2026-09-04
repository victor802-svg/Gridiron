# Brief — GRIDIRON_18 Session E: distributional totals and spreads

Received 2026-09-04. Saved before execution, per the unattended contract.
**Design first, build second, two separate sessions.**

---

GRIDIRON_18 SESSION E — DISTRIBUTIONAL TOTALS AND SPREADS. Design
first, build second, two separate sessions. Unattended contract.
Save as docs/briefs/2026-09-04-distributional.md.

PART 1 — THE DESIGN DOC (this session): docs/DISTRIBUTIONAL.md.
The causal claim, stated first: a binary asked at the model's own
expected value is a coin flip by construction (NBA total +0.0010, NFL
total +0.0016 walk-forward), and the same rung mechanism is the
likely cause of the spread-pair suppression that vanishes on the
moneylines. The blind object should be the model's forecast
DISTRIBUTION of the total or margin — mean plus a measured spread —
written before any line exists. P(over the market's line) is then a
deterministic READ-OUT of the stored distribution once the line is
snapshotted: not a new forecast, so Law 1 holds exactly. Cover, with
evidence from the record where it exists:
 1. The blind object: what is stored per prediction (mean, spread,
    distribution family), how the spread is measured per sport and
    market (the SDs already dated), whether it is constant or
    conditional (say which and why).
 2. Resolution: the graded question becomes "over the market's
    line?" read from the distribution at snapshot; when no line
    exists, what is graded (the mean vs the actual, scored as a
    continuous forecast — CRPS or absolute error, dated).
 3. Calibration of a distribution: PIT histograms / coverage of
    central intervals as the honesty check, plus the binary
    calibration at the market line for the tier table. How the tier
    chip maps from P(over line). Law 4 gates unchanged.
 4. What the card shows: the pick at the market line with its
    probability once a line exists; before that, the expectation in
    words ("the model expects about 47 points"). What the hero
    shows. What plain-words looks like.
 5. Migration: the rung ladders and asked_line for totals and
    spreads are DELETED (dated), existing rows stand under their
    version (Law 3), the market comparison becomes like-for-like at
    last. What the moneylines do: nothing — they have no line.
 6. What could go wrong: a spread that is not Gaussian (fat tails in
    CFB margins — measure), lines that move between snapshot and
    close (the drift pass already stores both — say which is graded),
    a market line that never posts (graded as continuous).
 7. A walk-forward plan for Part 2 that tests the claim before it
    ships: the distributional read-out at the closing line vs the
    current rung method on identical games, both sports, labelled
    sanity; the change ships only if the read-out is better
    calibrated. State that clause.
Commit the doc, then STOP. Part 2 (the build) is a separate session
that begins by reading it. /closeout, push.

---

## How this brief is read

- **This session writes ONE document and no code.** "Commit the doc, then
  STOP" is the instruction, and a design session that ships a helper
  function has stopped being a design session.
- **Measurement is not building.** §1, §3 and §6 ask for evidence from the
  record. Scratchpad scripts that measure the record are how the doc earns
  its numbers; nothing they produce enters `gridiron/`.
- **§7's clause is binding on Part 2**, and the doc must state it in those
  terms: the change ships only if the read-out is better calibrated.
