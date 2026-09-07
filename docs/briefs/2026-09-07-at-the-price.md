# Brief — GRIDIRON_AT_THE_PRICE (drafted 2026-09-07)

Saved before execution, per the standing agreement. The operator's text is
unedited. How it was read is recorded beneath it.

Delivered in the same message: **one unit is fifty dollars.** Recorded through
the settings page rather than in code, as the field added by CARD_FACE asks,
so it carries a date and a previous value: `unit_dollars`, empty to `50`,
2026-09-07.

---

At-the-line claims require a frozen margin distribution for every question.
That is right for a spread or total whose venue line differs from the
model's rung, and wrong for everything else. It leaves baseball — the daily
sport — producing no claims, no recommendations and no CLV, by design.
Plumbing, not modelling: the blind forecaster is untouched.

## The four shapes a venue contract can take, and what each needs

| shape | example | what the claim needs |
|---|---|---|
| line-less | moneyline, UFC winner | nothing — the blind probability IS the value at the venue's price |
| rung-matched | an MLB prop asked on the declared ladder at the rung the venue quotes | nothing — same |
| rung-differs, counting stat | a prop where the venue's rung is off the model's | the count model's distribution (`model/counts.py`), already fitted |
| rung-differs, margin | spread, total | the frozen margin distribution (AT_THE_LINE E3), as built |

## PHASE Q1 — Classify every question, refuse the unclassifiable

`priced.claim_shape(question, venue_quote)` returns one of the four or
refuses by name. The claim writer dispatches on it. A question whose shape
cannot be determined writes no claim and is counted, not silent.

## PHASE Q2 — The direct path

For line-less and rung-matched shapes: the claim is the blind probability
against the venue's price, fee-adjusted, with the side named. The claim row
records `shape` so the Record page can curve the four shapes separately —
they are different kinds of comparison and never merge (LAW 6's logic).

## PHASE Q3 — The count path

For a counting-stat prop at a differing rung: evaluate the count model's
fitted distribution at the venue's rung. The distribution parameters must
have been written during the blind window (as E3 does for margins); if they
were not, the claim is refused, not computed after the fact.

## PHASE Q4 — Backfill nothing

Standing baseball predictions predate this and carry no shape. They get no
claim. The first baseball claims are tomorrow's slate. READINESS.md records
the date baseball first reached the priced pipeline.

## Close-out

Standard table. The close-out states how many of today's questions fell in
each shape, and how many were refused and why.

---

## How this brief is read

**The diagnosis is checked before it is built on.** The brief says the frozen
margin distribution is required for every question and that this is why
baseball produces nothing. That was measured yesterday from the other end --
zero predictions in the whole record carry the distribution -- and the trigger
that enforces it is `at_the_line_requires_a_frozen_distribution` in
`schema.sql`. The trigger is checked first, because a shape the writer allows
and the schema refuses is a claim that fails at the last step.

**"Nothing" is not the same as "the blind probability".** For a line-less
contract the model's probability answers the venue's question exactly, so the
claim needs no distribution. For a rung-matched prop it answers a question with
the same subject and the same number, which is the same thing said twice; the
check that the rungs really match is the load-bearing part of Q2 and is done
on the number, never on the label.

**Q3 refuses more than it computes, and that is the intended outcome.** The
count model's parameters must have been written blind. Anything else is
evaluating a distribution against a line that was visible when it was fitted,
which is LAW 1 with extra steps.

**LAW 6's logic, applied one level down.** Four shapes are four kinds of
comparison. A curve that mixed a moneyline claim with a rung-differing prop
claim would describe neither, and it would flatter, because the line-less
shape has no distribution error in it at all.
