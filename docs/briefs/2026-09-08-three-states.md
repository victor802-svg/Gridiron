# Brief — GRIDIRON_THREE_STATES (drafted 2026-09-08)

Saved before execution, per the standing agreement. The operator's text is
unedited. How it was read is recorded beneath it.

---

A pick is one card with three states. It is born on **Upcoming**, moves to
**Live** when its game starts, and ends on **Results** when the game is
final. The operator ruled this on 2026-09-08 and it replaces the current
Picks page, on which the new Today section sits 900 pixels beneath the old
hero, sorters, carousel and market chips — two designs stacked, which is why
the page reads as unfinished.

The nav stays at four pages; a guard rules that and a layout does not get
to break a law. Picks gains two tabs, **Upcoming** and **Live**. Results is
already the fourth page and becomes the card's terminal state.

Phases S1–S4 touch the screen and the poller's existing data only. **Phase
S5, live win probability, is a new declared model with its own record** and
is scoped separately so nobody mistakes it for a card tweak.

---

## PHASE S1 — Picks becomes two tabs, and the old page goes

**Upcoming** is the Today layout: the day strip, Clears the bar, Watching,
Taken today in the rail, the learning panel beneath. **Live** is new (S3).

**What is removed from Picks, by name:** the notices bar, the "By
disagreement / By confidence" sorters, the tier buttons, the "View" menu,
the hero carousel with its dots, and the "Most confident, no line to compare
against" panel. The market chips survive as a filter row on Upcoming. The
close-out records each removal and where its information now lives (the
tier is a group heading; confidence is the Watching order; the hero's
reasoning is the card's own Why).

**A card moves on its own.** The poller already marks a game in progress
and final; the tab a card sits on is derived from that state, never from a
click. A test proves a game that goes live leaves Upcoming and appears on
Live within one poll, and reaches Results within one resolve.

## PHASE S2 — The richer card

Same card in all three states; what changes is the state band.

**Team identity.** Each side's **primary colour** is declared in a data file
per sport, dated, with its source. It is used as a 4px accent and a tinted
matchup header on the side the question favours. **No logos, no wordmarks,
no crests** — those are the clubs' trademarks and the plain-words scan's
cousin, `audit.check_no_marks`, refuses an image asset in the team data
directory. Colour is enough to make a Cubs card look like a Cubs card.

**The matchup header, made stronger:** away at home, both in team colour,
start time in the operator's zone, sport tag. In Live state this line
becomes the score (S3).

**The price row, per the operator's ruling of 2026-09-08:** the **payout
is the big chip** — "pays 1.65x" with the price beneath it. The Model chip
stays. **The edge shrinks to one quiet line** under the price row: "+3.2¢
after fees". The group heading is what says a card clears the bar; the edge
line is what ranks it. `audit` still refuses any card on Watching that
carries a size.

**What the card gains, from data the record already holds:**
- **the starter** for baseball (the probable pitcher the factors already
  read, absent-not-zero when unannounced, and the card says "starter not
  named" in those words);
- **form**, last five for each side, from `recent_form`;
- **weather** for outdoor football, from the forecast the factors already
  use;
- **the first sentence of the reasoning**, visible without a click; the
  rest and the factor bars behind Why, as now.
Nothing new is fetched. A card may only show what a factor already read.

**Colour, per the operator's ruling of 2026-09-08 ("add more colour").**
The card carries the clubs' colours structurally, not decoratively:
- the matchup header is a **two-tone band** — the away club's primary
  colour tinting the left, the home club's the right — and each club's
  name sits in a **solid pill of its own colour** with white text;
- the **payout chip is filled in the favoured side's colour**, so the
  biggest number on the card is also the most coloured;
- the card's top edge and hover glow take the favoured side's colour;
- the sport tag is a solid pill in a fixed per-sport colour;
- group headings carry a coloured rule — green for Clears the bar, grey
  for Watching, amber for Yours, blue for In progress — and the day
  strip's counts are coloured pills in the same scheme;
- on Live, the score sits in the two club colours and "Yours" is an amber
  badge.
Every new colour-on-ground pair goes into the contrast tool's pair list,
and white-on-club-colour must clear 4.5:1 or the club's darker secondary
is used instead, declared in the same data file. Colour never changes on a
price move and never encodes edge, which stays green/red on its own line.

**Polish, specifically:** one type scale declared in the stylesheet and
used everywhere on the card (header / question / chip / meta, four sizes,
no others); consistent 12px rhythm between rows; a hover state that lifts
the card one step, no transition on any price; focus rings on every
control. The contrast tool's pair list gains every new foreground/ground
pair this card introduces — the last redesign found a 3.39:1 label the tool
passed because the pair was not in its list.

## PHASE S3 — Live

A game in progress moves to the Live tab. Its card's header becomes the
score: "HOU 3 – PHI 2 · top 6th", from the poller's `live_` columns, at the
poller's cadence, with the time of the last poll printed on the card so a
stale score is visible as stale.

**What a Live card does NOT carry, and the guards that keep it that way:**
no size, no edge, no "I took this", no payout chip. The in-game rule is
already ruled and planted (THE_PRICED P2: a 90-second-stale score against
a live market is adversely selected by construction). `audit` extends the
existing check: a Live-state card that renders a size, an edge, a payout or
the taken control fails by name; `tools/guards/plant.py` plants each.

The Live tab shows the operator's **taken** picks first, so the game he
has money on is at the top — but shows only that it is his, never whether
it is winning. The operator declined "is my pick winning" on 2026-09-08;
the reasoning stands: it is the feature that makes a person watch the app
instead of the game.

**Results** already exists. Its card is the settled state: final score,
the question, the model's number, the venue's price at the time, the edge
at the time, and the outcome in plain words — "the model had this at 66%
and it happened." Closing the loop on the same card that opened it.

## PHASE S4 — Upcoming's empty and quiet states

A day with nothing live shows the Live tab with one sentence and the time
of the first pitch. A day where nothing clears the bar shows the top group
empty, as now. The day strip counts all three states: "4 clear the bar ·
11 watched · 2 live · 9 settled".

## PHASE S5 — Live win probability: a declared model, not a card feature

The operator asked for the model's chance as the game moves. **That model
does not exist.** The blind forecaster answers pregame questions; nothing in
the record conditions on score and time remaining.

This phase declares one, dated, with rationale, per LAW 2:

- **Baseball:** a win-probability table by inning, half, base-out state
  and run differential, fitted on the record's own completed games
  (thousands of them, from the league-history loader). A table, not a
  learned model, so a human can read it.
- **Football:** a logistic on lead, time remaining, possession and field
  position, fitted on the completed games the record holds.
- **Both are a separate forecaster identity, `live`, with their own
  curves and gate, never merged with the blind record.** They read the
  score; the blind path never may; the closure scan is untouched.
- **Displayed continuously, recorded at declared checkpoints only** — end
  of the 3rd, 6th and 8th in baseball; end of each quarter in football.
  Twenty rows from one game are twenty correlated looks at one outcome
  (METHODOLOGY's own argument against asking every rung); the checkpoint
  rows are what calibrate, and nothing between them counts toward any N.
- Rendered on the Live card as a line, in the tinted colour of the side
  it favours, with the last checkpoint's number in plain words. Never
  sized, never a recommendation, never green or red.

If S1–S4 ship and S5 does not, the Live tab is still complete: a score, a
card, and no claim. S5 is the one to run second, and to run on its own.

## Close-out

Standard table: one row per phase, four verdicts, evidence nameable.
Screenshots of all three states at both widths. A named list of what was
removed from Picks and where each piece now lives.

---

## How this brief is read

**S1 to S4 in this pass; S5 in its own.** The brief says so in as many
words -- "S5 is the one to run second, and to run on its own" -- and the
reason is its own: a win-probability model is a new forecaster with a new
record and a new gate, and shipping it beside a layout change would put a
model behind a card tweak's close-out. S5 is recorded SKIPPED with that
reason, not overlooked.

**The colours are taken from the source the team names already come from.**
Every team row in this record carries a `source_url` into ESPN's core API,
and that payload carries `color` and `alternateColor`. Reading them there
makes the palette measured with provenance rather than typed from memory,
which is the difference between a declared datum and a guess. The same
payload carries `logos`, and those are not taken: the brief bans marks and
`audit.check_no_marks` refuses an image in the team data directory.

**Contrast is measured per club, not assumed.** White on a club's primary
is a different pair for every club, and some of them fail. The generator
measures each one and records which clubs use their darker alternate, so
the fallback is a recorded fact rather than a runtime guess.

**"The tab a card sits on is derived, never clicked" is the load-bearing
sentence of S1.** A state a person can set is a state that can disagree
with the game.
