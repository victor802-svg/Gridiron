# Close-out — four fixes from the key-rotation findings

Brief: `docs/briefs/2026-09-05-four-fixes.md`.
Four commits, in the order given, each pushed on its own.

---

## 1. Against the brief

| # | asked for | verdict | commit |
|---|---|---|---|
| **1** | diagnose `ufc_scheduled_rounds = 0`; fix at the source; plant it; survey every factor | **DONE — and the answer was neither hypothesis** | `3bfe2e5` |
| **2** | reverse `send()`: record intent, post, mark | **DONE** | `390bf55` |
| **3** | move the existence check before `llm.reason` | **DONE** | `95094dd` |
| **4** | plain names in the prompt; scan the LLM view; humanise old rows at render | **DONE** | `94d4041` |

**Nothing SKIPPED, nothing DECLINED.**

## 2. Fix 1 — the zero was correct, and something else was wrong

**Neither hypothesis held.**

- **The prompt does not render absence as zero.** Unmeasurable factors go into
  a block headed *"NOT MEASURABLE for this game. No value exists. Do not
  assume one, and do not treat these as zero"*. Checklist item 5 was honoured.
- **The stored value is not wrong.** `ufc_scheduled_rounds` is a declared
  **indicator** — 1.0 for five rounds, 0.0 for three — and its own rationale
  says *"scaled so five reads as 1 and three as 0"*. The zero meant three
  rounds, correctly.

**The third possibility is the real one**, and the survey the brief asked for
sizes it: **27 of 103 declared factors hand the model an encoded number** — an
indicator, a scaled value, a difference — **under its code name**. The model
quotes both, and a reader sees `(ufc_scheduled_rounds = 0)` on a card. That is
fix 4, and the survey found the thing that made fix 4 possible: **103 of 103
factors already have a plain-words phrase**, so the prompt can always use one.

**What is fixed at the source is that the property which DOES hold can no
longer stop holding quietly.** `compute.assert_missing_is_explicit` refuses a
defaulted absence at runtime; `check_no_silent_defaults` scans the factor code
for a reintroduced fallback. **Neither looks at what the model is told.** One
edit to the loop in `build_prompt` would hand every unmeasurable factor over as
a zero and nothing would look different — the model would reason from those
zeroes as facts and write confident prose about them.

The guard is **behavioural**: it builds a prompt from one present factor and
one absent one and reads what came out, so a rewrite that does the wrong thing
in a new shape cannot pass. **Two plantings, in both directions** — absence
handed over as zero, and a *measured* zero dropped out of caution about the
first. A guard that watches one direction teaches the next person to
over-correct.

## 3. Fix 2 — the record precedes the push

`send()` posted to both channels and **then** inserted its row. Every
validation the table performs was happening **after** the irreversible part.

**Now: record intent, post, mark.** The exact case that lost a push — a `kind`
the CHECK refuses — raises at the INSERT with the channels untouched, pinned by
a test that asserts nothing was posted.

**`sending` is its own state and not `queued`.** Queued means held for quiet
hours and never sent; sending means handed to the network and unaccounted for.
One is routine and one wants looking at, so they are not the same word.

That needed the state CHECK widened, which SQLite applies at CREATE and never
revisits. `db.widen_notification_states` rebuilds the table on an older
database — a plain copy with **the row count verified before the original is
dropped**, because the last rebuild this project did left 311,655 rows in a
table called `games_narrow` when a foreign key tripped after the copy. **Ran
clean on the live record: 13 rows in, 13 out, no stray table.**

## 4. Fix 3 — ask the record before the model

`predict_slate` called `llm.reason` and only then `write_prediction`, which
returns None for a row that already exists. **The answer was bought and thrown
away.**

**Measured yesterday:** an interrupted UFC pass was resumed and made **76
reasoning calls to write 8 rows**. Thirty-four questions were answered a second
time at full price — about **$0.23** against a $2.00 daily cap, on a slate of
forty-two.

The predicate is lifted into `predict.already_written` and asked before the
expensive call. **One door**: `write_prediction` still asks it too, because a
check a caller may forget is not a check, and a second predicate that drifted
from the unique index is how the final pass failed the first time it ran. A
test asserts `write_prediction` has not grown its own copy back.

`llm_skipped` is **counted, not silent** — a run reporting `llm_skipped: 34,
written: 8` is a resume that worked, and silence would look identical to a run
that had nothing to do.

**The guard reads the syntax tree.** `predict_slate` is a long loop and the
check inside `write_prediction` much further down would satisfy a text match —
and that check is exactly the one that was too late. **The behavioural planting
runs on the real slate with `llm.reason` stubbed by a counter**, so it spends
nothing and asserts zero calls over a written slate.

## 5. Fix 4 — no code name reaches a reader

**27 of 65 stored rows** carried a snake_case identifier onto a card.

**The prompt now uses plain names.** `compute.describe` carries each factor's
declared phrase alongside its code name; `build_prompt` renders the phrase.
There is no code name for the model to quote.

**Old rows are humanised at render time, never rewritten.** LAW 3 is
append-only: the reasoning is what the forecaster said. **27 rows carrying a
code name, 0 rendering one.**

### The model shortens names, and the alias rule refuses to guess

It wrote `scheduled_rounds` for `ufc_scheduled_rounds` and `mean_vs_line` for
`mlb_prop_mean_vs_line`. `with_prefix_aliases` derives those forms from the
declared names and adds one only when **all three** hold:

- it is not itself a declared factor — `nba_asked_line` yields `asked_line`,
  which is a factor of its own, so **no alias**, because a reader must never be
  shown basketball's phrase over football's factor;
- it still looks like a code name — `mean_vs_line` does, `line` does not, and
  mapping a bare English word would rewrite ordinary prose;
- **every declared name producing it agrees on the phrase.** Three sports
  declare a `prop_mean_vs_line` variant and all three read the same, so
  substituting is safe whichever was meant. Where they disagree, no alias is
  made and the code name survives — **the honest outcome**, because guessing
  which sport was meant is exactly the quiet wrongness this project spends its
  time preventing.

### Why nobody had seen it

**Two reasons, and the second is worse.** Picks opens on the statistical
forecaster and no test ever moved the selector — so the view went unread. And
**the browser fixture seeded its league with `use_llm=False`**, so the second
forecaster's view was *empty in every test*: the scan could not have caught
this even if somebody had pointed it at the view.

So the fixture now seeds **one LLM row whose reasoning quotes code names on
purpose** — a render-time repair can only be tested against a row that needs
one — and the render test clicks the control a reader clicks, opens every card,
scans, **and asserts the replacing phrase is actually on the page**, so it
cannot pass by scanning an empty one.

## 6. One guard caught another, which is the system working

**The first gate run after fix 4 failed**, and on a row none of the four
fixes touched: *"the side, in prose, anywhere"*.

`llm_prose_faults` — the guard fix 4 added — built its fault message as
`f"{sport} {card.get('subject')}: ..."`. **A raw subject going into a
sentence is exactly what `check_side_named_everywhere` refuses**, for a reason
this project learned the hard way: on a moneyline the subject is the HOME club,
so a message built from it names the side the model forecast *against* on every
pick against the home team. That shipped four times before the scan existed.

**It was a developer-facing string in a guard, not a card** — so the sanctioned
route was a dated `SIDE_ALLOWLIST` entry. It got the better fix instead: the
message now identifies the row by its **prediction id**, which is unambiguous,
points at one row, and needs no exemption.

**Worth saying plainly: a new guard tripped an old one, and the old one was
right.** The plantings were 188/188 in that same run — nothing escaped. What
failed was a scan doing its job on code written minutes earlier.

## 7. The gate

- Suite **1,055 tests, 0 skipped, 0 failures** under `.venv` — 26 new.
- Plantings **188/188** — eight new, two per fix.
- `verify.py`: **all four steps PASS**, 43 scan rows, four new.
- **No prediction row written, rewritten, re-dated or deleted.** Fix 4
  deliberately does not touch stored reasoning.
- **`.env` was neither read nor written** in this session.

## 8. Rulings taken in your absence

1. **Fix 1's source fix is a guard, not a change**, because the diagnosis found
   nothing broken there. The behaviour was right; what was missing was any way
   to know it stays right.
2. **Both directions of the absence rule are planted.** Dropping a *measured*
   zero is the over-correction the first planting invites, and it is just as
   silent.
3. **`sending` got a schema rebuild** rather than being folded into `queued`.
   Conflating "held until morning" with "unaccounted for" would hide the exact
   failure the fix is about.
4. **The alias rule refuses ambiguity rather than resolving it by sport.** It
   could have preferred the card's own sport; it does not, because every case
   in the record turned out to agree anyway and a preference rule would be
   machinery earning nothing.
5. **The browser fixture now contains the defect on purpose.** A clean fixture
   is why this was invisible; a test that cannot see a broken row cannot prove
   a repair.

## 9. What this does not settle

**The 27 encoded factors are still encoded.** The prompt now names them
plainly, and the *rationale* beside each already explains the encoding — so the
model is told. But `how many rounds the bout is scheduled for = 0` still reads
oddly to a human who sees the prompt. Giving each encoded factor a declared way
to read its value is a larger piece of work and was not in the brief.

**Two MLB rows needed the widest alias rule to come clean.** They are fine now,
but they are the reason the rule looks at agreement rather than uniqueness, and
a future factor whose sports disagree will leave a code name on a card. The
guard will catch it; the fix will be a declaration, not code.

## 10. Operator's verdicts

**Strongest thing:**

**Weakest thing:**

**What to do next:**
