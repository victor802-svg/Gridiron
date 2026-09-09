# Brief — GRIDIRON_COMBOS, corrected (ruled 2026-09-09)

Saved before execution, as the standing contract requires. The operator's text
is unedited.

---

Correction to GRIDIRON_COMBOS, ruled 2026-09-09. The venue's combos are user-built and priced by request-for-quote to the account holder; the public API exposes only prepackaged series. The app can never read a combo price (LAW 5, authenticated calls, not amendable). Rewrite:

1. The Combos heading sentence: "The venue quotes combos to your account on request. This app cannot ask, so it shows what a combo is worth and you compare." Never "no package open" when the builder exists.

2. C1 reverts to proposal: the app proposes up to three combos per day per sport from legs that each clear the bar alone, different games, same sport, two or three legs, no leg reused. Plantings as before. Same-game stays unpriceable.

3. C2 becomes a ceiling, not an edge: fair value = product of the legs' corrected probabilities; the card prints the fair value and the highest price worth paying = fair value minus the declared fee at that price minus MIN_RETURN_ON_STAKE times price, in cents, in words: "worth taking only below 33¢". No venue price, no edge, no payout chip; the singles alternative line stays.

4. C3 sizing stands: 0.5u two legs, 0.25u three, flat.

5. C4 is withdrawn: no combo_2/combo_3 record, no combo CLV, no kill criterion — the app never sees the price paid, so nothing is measurable. The taken tap records a combo as one row with its leg ids and nothing else. State in READINESS that the combo product is unmeasurable by construction and why.

6. The package grader from the current build stays, renamed as what it is, for the rare prepackaged series; it is not the Combos group's main content.

Gate, commit, push, restart, confirm. Screenshot of the Combos group with one proposed combo, both widths, or the empty state with the corrected sentence.

7. The Combos group is per sport, like every other group: "MLB combos" / "NFL combos" headings, each proposing only from that sport's legs, per LAW 6. The empty state reads "no two MLB picks clear the bar today" in those words, so it is clear a combo is two picks from one sport, never two sports.

---

## What this requires of LAW 5, flagged before anything is built

LAW 5 currently reads, as amended by the operator on 2026-09-08:

> **PACKAGES ARE GRADED, NEVER BUILT.** The venue assembles multi-leg packages
> and sells them. The engine MAY price one it reads, and may never assemble
> one: it does not choose legs, does not combine them, and does not compute a
> package price the venue has not published.

**Item 2 of this ruling reverses every clause of that sentence**: the app
chooses legs, combines them, and computes a value for a package the venue has
not published. It cannot be built under the law as written.

**This is an amendment and the operator is the one making it**, so the law is
rewritten here rather than read around — with the superseded text kept in
place, as this project does for every law it has replaced. The reason the
amendment is coherent is the ruling's own first sentence: the venue prices a
combo only to an account holder on request, so "grade what the venue
published" describes a thing that does not exist for combos.

**The four structural prohibitions are untouched and this ruling reinforces
them.** No credentials, no authenticated call, no order path, no ledger. The
app cannot ask for a quote precisely because asking would require an account,
and item 3 removes the venue price, the edge and the payout chip from the card
for the same reason.
