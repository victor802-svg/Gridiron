# Close-out — GRIDIRON_COMBOS, corrected (2026-09-09)

Against the brief in `docs/briefs/2026-09-09-combos-correction.md`.

| item | verdict | evidence |
|---|---|---|
| 1. the heading sentence | **DONE** | `language.COMBO_RFQ_SENTENCE`, drawn above the cards; the old "no package open" composer is deleted and a test asserts it cannot return |
| 2. C1 reverts to proposal | **DONE** | `combos.propose()`; five plantings feed it adversarial input and prove none of them comes out |
| 3. C2 becomes a ceiling | **DONE** | `combos.price_ceiling()`; the card carries the fair value and "worth taking only below 33¢", no venue price, no edge, no payout chip |
| 4. C3 sizing stands | **DONE** | untouched: `size_for` still returns a flat 0.5u on two legs, 0.25u on three |
| 5. C4 withdrawn | **DONE** | the two markets, the CLV threshold and the kill verdict are removed, not left unused; READINESS says unmeasurable by construction and why |
| 6. the grader stays, renamed | **DONE** | `_prepackaged_card`, and the payload key is `graded` — it is no longer what the group is for |
| 7. per sport, per LAW 6 | **DONE** | "MLB combos" / "NFL combos"; empty state "no two MLB picks clear the bar today" |
| gate, commit, push, restart, confirm | **DONE** | PASS ×4, 256/256 plantings |
| screenshot | **DONE (empty state)** | nothing clears the bar on any slate today, so the corrected empty state is what there is to photograph |

---

## LAW 5 was amended, and this says so first

The ruling could not be built under the law as it stood. **"PACKAGES ARE
GRADED, NEVER BUILT"** — written the previous day — said the engine "does not
choose legs, does not combine them, and does not compute a package price the
venue has not published." Item 2 reverses every one of those clauses.

So the law is rewritten rather than read around, with **both** superseded texts
kept beneath it, and the operator is the one who made the amendment. The
measurement that forced it is the ruling's own first sentence: the venue's
combos are user-built and quoted to an account holder on request, so "grade
what the venue published" describes a thing that does not exist for combos.

**The four structural prohibitions are untouched, and this ruling leans on
them.** The app cannot ask for a quote precisely because asking needs an
account. That is why the card has no price, no edge and no payout chip: it
would be comparing a real number against an invented one.

## What the group is now

Above the cards: *"The venue quotes combos to your account on request. This
app cannot ask, so it shows what a combo is worth and you compare."*

A proposal carries two numbers. **WORTH** is the product of the legs'
corrected probabilities. **PAY BELOW** is the ceiling: the highest price at
which

    fair − price − fee(price) ≥ MIN_RETURN_ON_STAKE × price

still holds — the same test a single faces, at the same threshold, so "worth
taking" means one thing in this app. The search is cent by cent because the
fee rounds up to the cent and is a step function; a closed form would give a
smooth answer to a stepped question. A 36¢ combo reads *"worth taking only
below 32¢"*.

## Two legs, not three, and that is a decision

The ruling permits two or three. The app proposes **two**, and the reason is
the number already printed on every card: the fee per dollar staked is 1.67
times the singles' rate on two 60c legs and **2.8 times on three**, measured
2026-09-08. Nothing in the record argues for the more expensive shape, and
choosing it would be the app taking a view it cannot support. `PROPOSAL_LEGS`
is declared and says this, so the absence is a decision rather than an
oversight. **Say the word and it becomes three.**

## The plantings, inverted

The old plantings proved the grader refused a bad package the venue had
published. A proposer cannot be handed a bad package — it builds its own — so
the planting runs the other way: adversarial input, and the proof is that
nothing comes out.

| planted | caught by |
|---|---|
| two clearing legs from the same game | no proposal made |
| a leg from another sport | no proposal made |
| a leg that does not clear the bar alone | no proposal made |
| four legs, best-first, checking for reuse | no leg appears twice |
| a card carrying a price, edge or payout | none of those fields exists |

## C4's withdrawal, and why it is a deletion

`COMBO_MARKETS`, `combo_market()`, `is_combo_market()`, `COMBO_KILL_AFTER`,
`MIN_PACKAGES_FOR_CLV` and `combo_kill_verdict` are **gone**, with a dated
comment in each place saying what stood there.

The kill counted SETTLED packages. **Nothing can ever settle**: no price paid,
no closing line, no CLV, no verdict. A criterion that cannot fire is worse
than none — it reads as a safety net while being a sign saying one is there.
Five tests that asserted its behaviour went with it; every one of them was
true, and every one described a product this app cannot have.

`views._settled()` now returns `0` as the constant it always was, instead of
asking a table that would always answer the same thing.

## Two composers the orphan scan caught

`combo_empty_words` (which wrote the forbidden sentence) and
`combo_kill_words` (which read out a verdict that can never be reached) had no
callers after the rewrite. `audit.check_no_orphan_functions` failed the gate
on both — the scan doing exactly its job, because a composer nobody calls is a
sentence a reader will eventually find on a screen. Removed, with their
reasons in place.

## What the screenshot shows

Nothing clears the bar on any slate today — the NFL strip says so on its own
first line — so there is no proposal to photograph and the empty state is the
honest picture: **"NFL combos"**, the request-for-quote sentence, and **"no two
NFL picks clear the bar today"**. The proposal path is proved by the plantings
and by `price_ceiling`'s own arithmetic rather than by a card that does not
exist today.
