# Close-out — rulings on the Session E result

Brief: `docs/briefs/2026-09-04-rulings-on-session-e.md`.

Three rulings. One moved a finding to where readers are, two turned an absence
into a decision.

---

## 1. Against the brief

| # | ruling | verdict | evidence |
|---|---|---|---|
| **1** | the NO stands; add the finding to METHODOLOGY §6 in plain words | **DONE** | `DISTRIBUTIONAL.md` untouched; §6 now holds three findings, with the 55–59% table and no jargon. A test asserts both |
| **2** | CFB's slope recorded and NOT adopted; the market shown, not hidden | **DONE** | `questions.CFB_TOTAL_FIT_MEASURED` with `adopted: False`; `audit.check_no_market_is_hidden`; 1 planting |
| **3** | no confidence floor on rung game markets | **DONE** | `config.GAME_MARKET_MIN_CLAIM = None`, dated; an AST guard on `predict.py`; 2 plantings |

**Nothing SKIPPED, nothing DECLINED.**

## 2. Ruling 1 — the finding left the close-out

`docs/DISTRIBUTIONAL.md` is byte-for-byte as it was. §9 is the result and
nothing above it moved, which is what makes it a record of what was predicted
rather than of what happened.

**What changed is where the finding lives.** A close-out is a document about a
session; `METHODOLOGY.md` is the document about the project, and its §6
already keeps a section headed *"the worst thing the record says"*. It held
two findings. It now holds three.

The new one is written for a reader who has never seen a calibration table:

| | our number was off by | the market's was off by | the market was closer on |
|---|---:|---:|---:|
| NFL totals | 11.2 points | **10.1** | **57%** of games |
| NFL spreads | 10.4 points | **9.7** | **59%** of games |
| NBA totals | 15.3 points | **14.6** | **55%** of games |
| NBA spreads | 11.8 points | **10.9** | **57%** of games |

followed by what the model claimed against what happened — 74% claimed against
38% actual, 86% against 43% — and then the sentence the ruling asked for, in
the plainest form I could find it:

> **Being able to say something is not the same as being right about it.** The
> method that could reach 80% was wrong there; the method that can only reach
> 54% is accurate to within a third of a percentage point. A question with
> almost nothing in it beats a question with the wrong thing in it.

**No jargon crossed over.** The section says "how far our number sat from
theirs" and "how often it was right"; it does not say calibration gap, PIT,
read-out or Brier. A test asserts that, because the plain-words rule is easy
to honour on the day and easy to lose on the next edit.

## 3. Ruling 2 — recorded, not adopted, and not hidden

`questions.CFB_TOTAL_FIT_MEASURED` holds the fit with `adopted: False`:

```
actual_total = 47.3123 + 0.1087 x expectation
n = 1,639     R^2 = 0.0093     residual sd 16.31 (from 20.85)
```

**It is in `questions.py` rather than only in a close-out** because the next
person to wonder whether CFB's totals expectation should be fitted will open
that file, and the answer is that it was, and this is what happened.

**Why adopting it would have been worse than leaving it alone**, stated where
the constant lives: a slope of 0.109 is not a calibration, it is a dismissal.
The fitted line is 47.31 plus a whisker, so it asks about the league average on
every game in the country — and it would *look* more accurate for doing so,
because the residual drops from 20.85 to 16.31. **That is not a better
forecast. It is a forecast that has stopped trying**, and its confidence would
be borrowed from college totals clustering rather than from anything known
about the game.

**"Shown as such, not hidden" is now a guard**, not a promise.
`audit.check_no_market_is_hidden` fails if a market with a recorded verdict —
or a market carrying a method flag — stops being declared by its sport.

**The failure it guards against is a kind one.** Nobody withdraws a market out
of malice; they withdraw it because a question that measures almost nothing
looks bad on the page. A slate that quietly loses its weakest question looks
sharper and is less honest, and a reader has no way to tell the two apart.

### A bug in my first version of that guard, worth recording

The first draft asked whether every market with a **DO NOT SHIP** verdict
carried a caveat. It fired on the NFL and NBA **spreads** — and it was wrong to.

**A verdict in `DISTRIBUTIONAL_VERDICTS` records whether the READ-OUT beat the
rung. It is not a judgement on the market.** The NFL spread is refused there
and is the market this project was built on, with a walk-forward calibration
gap of 1.93 points. Reading "the read-out lost" as "this market is weak" would
have put a coin-flip caveat on one of the better questions on the page.

The guard now checks **presence** and leaves the caveat to
`flagged_method_faults`, which is the one door that decides it. A test pins the
distinction.

## 4. Ruling 3 — an absence becomes a decision

`config.GAME_MARKET_MIN_CLAIM = None`, dated 2026-09-04. Game markets had no
floor before by nobody having added one; they have none now by ruling. **The
difference is that adding one means overturning a dated decision rather than
filling a gap.**

**The argument is this session's own evidence.** A floor keeps the claims the
model is most sure of, so it is only as good as the relationship between
confidence and accuracy. Session E measured that relationship for the one
game-market method that could produce confident claims at all:

| of 768 NFL totals questions | n | right |
|---|---:|---:|
| cleared 70% | 95 | **38% and 43%** |
| did not | 673 | 49% |

**It runs backwards.** A floor would have kept precisely the wrong questions.

**And the rung method cannot reach 70% at all** — 45.8%–54.2% by construction —
so a floor above about 55% empties the slate and one below it is decoration.
There is no useful place to put it.

**What replaces it is already on the page.** The tier chip says LEAN, SOLID or
STRONG with its own settled record beside it, and the coin-flip line says what
the method is worth in words. **A reader is told what a claim is worth instead
of having weak claims hidden from them** — the same choice ruling 2 makes about
CFB, taken for the same reason.

**Props keep theirs, and the situation is genuinely different.** A prop is
asked at a rung a source actually posts, one subject at a time, against a daily
cap of 25 — so refusing the ones the model is unsure of **chooses between**
questions. A game market asks about every game on the slate; refusing there
**hides** them.

### The guard reads the syntax tree, and the first version could not

`predict.py` applies the floor inside `if q.market_type == "prop":`. My first
guard matched that phrase and the floor comparison with a regex — and
**`predict.py` has two prop branches.** Lifting the floor out of the second one
left the first still matching, the planting escaped, and the guard was
reporting on a branch that was not the one doing the work.

It now walks the AST from each comparison against a floor constant up through
its ancestors, asking whether **this** comparison sits inside a branch that has
established the question is a prop. That is the question that actually matters,
and a regex cannot ask it.

**The constant is not the floor**, either — `FLOOR_CONSTANTS` covers both
names, because a guard that only read `GAME_MARKET_MIN_CLAIM` would pass
happily while `PROPS_MIN_CLAIM` was applied to every question in the loop.

## 5. The gate

- Suite **1,029 tests, 0 skipped, 0 failures** under `.venv` — 10 new.
- Plantings **179/179** — three new.
- `verify.py`: **all four steps PASS**, 38 scan rows, two new.
- **No prediction row written, rewritten, re-dated or deleted.** No market
  changed what it asks.
- **`.env` was neither read nor written.**

## 6. Rulings taken in your absence

1. **The METHODOLOGY passage keeps "rung"**, which is jargon everywhere except
   in that document — §1 introduces it and it is used nine times before §6.
2. **The hidden-market guard checks presence, not wording.**
   `flagged_method_faults` already decides whether a market has words, and two
   guards deciding one thing is how they come to disagree.
3. **The floor guard covers `PROPS_MIN_CLAIM` as well**, because the ruling is
   about floors reaching game markets and a floor's name is not the thing that
   matters.
4. **`CFB_TOTAL_FIT_MEASURED` is a dict, not a live constant.** Nothing reads
   it at runtime by design — it is a record, and a test asserts
   `cfb_total_asked` has not quietly started applying the slope.

## 7. What is still yours

- **Whether CFB's totals question should exist at all.** This session keeps it,
  shown with its caveat, on your ruling. That an expectation explaining 0.93%
  of the variance should still be asked about is a defensible position and not
  an obvious one; it is worth revisiting once the market has a settled record.
- **Whether the tier chip is enough** in place of a floor. It is what ruling 3
  leans on, and it has never been measured against a slate a reader actually
  worked through.

## 8. Operator's verdicts

**Strongest thing:**

**Weakest thing:**

**What to do next:**
