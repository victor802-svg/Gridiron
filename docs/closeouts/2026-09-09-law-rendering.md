# Close-out — the law is rendered, not retyped (2026-09-09)

Against the rulings of 2026-09-09 (evening), items 1–3, plus one change the
operator asked for while it was in flight.

| ruling | verdict | evidence |
|---|---|---|
| 1. LAW 5 rewrite ratified, dated, both superseded texts kept | **DONE** | the clause records the amendment, the ratification and the date in the law itself |
| 2. `PROPOSAL_LEGS = 2` ratified with the fee reason; three available by config, not enabled | **DONE** | `config.PROPOSAL_LEGS`, `GRIDIRON_PROPOSAL_LEGS=3` turns it on, and anything outside two or three refuses at import |
| 3. footer and Settings law list rendered from `CLAUDE.md`, with a test | **DONE** | `gridiron/laws.py`, `tests/test_laws.py`; a **third** stale copy was found doing it |
| MLB forecast the night before | **DONE** | two triggers, 22:00 and 11:00, and today's slate written by hand because the change could not help today |
| 4. live cadence, price-endpoint planting | **NOT STARTED** | next |

---

## Ruling 3 — and the third copy nobody knew about

The ruling named two surfaces. There were three.

| surface | what it said | true since |
|---|---|---|
| the page footer | "Not a betting tool. No stake sizing, no bankroll, no recommendations, and no sportsbook or exchange connection." | never, after 2026-09-07 |
| the Settings list of the laws | "Not a betting tool: no stake sizing, no bankroll, no bet recommendations." | never, after 2026-09-07 |
| **`meta.not_a_betting_tool`** | "It does not size stakes, manage a bankroll, or recommend a bet, and it connects to no sportsbook or exchange." | never, after 2026-09-07 |

LAW 5 became "THE APP RECOMMENDS, IT NEVER TRANSACTS" on 2026-09-07. For two
days the app sized every pick, led with a group called "clears the bar", and
read a venue for the price on every card, while three surfaces told the reader
it did none of those things.

**A disclaimer that understates what an app does is not a safe error.** It is
the page telling a reader not to check the thing it is doing. The Settings
entry is worse than the footer: that page exists to answer "can I turn this
off", and it was answering about a law that no longer existed.

### The mechanism

`gridiron/laws.py` parses `CLAUDE.md`: the six `**N. TITLE.**` headings, the
first paragraph of each law's own prose, and the four prohibitions LAW 5 marks
not amendable. It skips amendment notes — which record that a law changed and
are not what it says — and skips blockquotes, which are **replaced** laws kept
for audit. Without that second rule the footer would eventually quote the law
it replaced.

* the footer renders `laws.footer_note()` into `#law-note`, placed by the
  renderer and composed by the server, like every other visible string;
* the Settings list renders `laws.read_laws()`;
* `meta.law_note` replaced `meta.not_a_betting_tool`.

**Only capitalisation is normalised.** The law shouts its titles and a footer
that shouts back is a footer nobody reads, so the test compares
case-insensitively and every other character is the law's own.

### The test is a comparison, not a convention

`tests/test_laws.py` asserts each rendered title and sentence appears in
`CLAUDE.md` verbatim; that the footer names LAW 5 and **all four**
prohibitions; that a missing working agreement degrades to empty rather than
raising; and that the five withdrawn phrases — "not a betting tool", "no stake
sizing", "no bankroll", "no bet recommendations", "no recommendations" —
**cannot come back** on either surface. That last one is not a style rule:
those sentences were on the page while the opposite was true, and the only
reason they survived is that nothing compared them against anything.

`tests/test_api.py::test_the_meta_states_it_is_not_a_betting_tool` asserted
the stale key contained "does not". Rewritten and renamed: it now asserts the
payload equals `laws.footer_note()`, because a test spelling out the law would
be a fourth copy of it.

## MLB is forecast the night before

Not in the rulings — the operator asked at 05:00 while looking for picks that
were not there.

**Measured:** `Gridiron-Predict-MLB` ran once daily at 11:00 local. Today's
first pitch was 10:10. The picks were written **fifty minutes after the day
had started, every day** — yesterday's slate got its 162 predictions at 14:33.
Nobody had noticed because the run reported `ok`.

Now two triggers: **22:00 for the next day's card**, and **11:00 kept as a
backstop**. The backstop is not a hedge. `predict` targets the next UNPLAYED
slate; at ten at night a late West Coast game can still be running, in which
case the next unplayed slate is still today's — already answered — and the run
refuses. Alone, that refusal would silently cost the following day its picks.
A second firing on an answered slate costs nothing: `SlateAlreadyAnswered` is
the append-only guard doing its job and it writes a row saying so.

**Today's slate was written by hand**, because a change that fires at ten
tonight cannot help a slate starting this morning: 78 predictions for
Wednesday 9 September — 30 moneyline, 30 total, 15 spread, 3 props — with 22
prop questions below the 70% confidence floor and not asked.

## What is not done, and is not being decided by me

The operator asked for the tier chips to be coloured — STRONG green, SOLID
yellow, LEAN orange. **Reported and stopped**, under the ruling of this same
day that a law's reading is the operator's to make.

The colour law's own last line is *"Confidence still escalates by WEIGHT, not
hue — see .tier"*, and `audit.colour_law_faults` refuses the change by name
today: `'.tier.strong' uses --win but says nothing about a pick that won.`
There is also a collision on the card itself — the edge line is green for
value, and a green tier chip inches above it would mean confidence. That is
the misuse the `--green` → `--win` rename was made to end, returning.

Both readings are with the operator, along with the one question that decides
the shape: whether the edge line keeps green.
