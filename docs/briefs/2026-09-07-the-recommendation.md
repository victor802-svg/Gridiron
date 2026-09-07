# Brief — GRIDIRON_THE_RECOMMENDATION (drafted 2026-09-07)

Saved verbatim before any of it was executed. How it was read, and the one
concern recorded at receipt, are at the end.

---

The operator has ruled that this project exists to inform his own wagering,
that he is wagering either way, and that the app should give him the best
available chance. LAW 5 as written describes a project he is not building.
This brief amends it, builds the recommendation surface it was blocking, and
keeps the two things that were never about betting: the codebase's distance
from his money, and the gate that stops the app claiming an edge it has not
measured.

## PHASE R1 — Amend LAW 5

Replace LAW 5 in CLAUDE.md with the text below. The prior wording and the
reason it changed stay in the file; a law that quietly vanished is a law
nobody can audit.

**5. THE APP RECOMMENDS, IT NEVER TRANSACTS.** (Amended 2026-09-07 by
operator ruling, replacing "not a betting tool".)

PERMITTED from this date: expected value and price-to-return arithmetic;
edge versus a recorded price, fee-adjusted; stake sizing; a recommended
side and size.

FORBIDDEN structurally and permanently, NOT amendable by a later session:
  * NO CREDENTIALS — no key, token, password, cookie or session for any
    venue in this codebase, its environment or its database.
    `audit.check_no_venue_credentials` scans; a planting proves it fires.
  * NO AUTHENTICATED CALL — every venue request unauthenticated and
    read-only, as D3 already requires.
  * NO ORDER PATH — nothing places, cancels, modifies or prepares an order;
    nothing reads an account balance or position. The gap between a
    recommendation and a wager is a human being, on purpose.
  * NO LEDGER IN THE REPO — the operator's own wagering record lives
    outside this codebase. A model that can see its own P&L is one step
    from fitting to it.

## PHASE R2 — The recommendation, priced

For every shortlisted question carrying a recorded market price, compute and
show, in plain words:

- **Fair value** — the model's probability as a price.
- **The market's price**, and the **fee-adjusted edge** in cents. Kalshi's
  published fee formula is applied; an edge that does not clear fees is
  displayed as no edge, not as a small one.
- **A side**, or no side. Most questions get no side, and the page says so
  rather than manufacturing twenty opinions a day.
- **A size**, capped in code:
  - **Below the market's n=100 gate: a FLAT UNIT ONLY**, labelled "no
    measured edge — flat unit". The operator wagers regardless; flat
    sizing on an unproven signal is the harm the app can actually reduce.
  - **At or above the gate: quarter-Kelly** on a declared bankroll
    constant. Full Kelly is never offered: Kelly assumes the probability
    is right, and Kelly on a probability ten points wrong compounds toward
    ruin rather than growth. Declared, dated, rationale beside it.

**SINGLES ONLY. The engine never recommends a parlay** and refuses to price
one. Each leg pays the spread, so an N-leg parlay multiplies the cost of
being right by roughly N, and correlated legs price worse than they look.
A planting proves the refusal fires.

**NO IN-GAME RECOMMENDATION.** The poller's score is up to 90 seconds stale
and a live market is priced off the feed; a live recommendation is an
adversely-selected one by construction. Live win probability may be
DISPLAYED (S-brief), never sized. Recorded as a technical finding, dated,
in docs/DECISIONS_MADE.md.

## PHASE R3 — Closing line value, the fast verdict

The most decision-relevant measurement available, and far faster than
outcomes: for every recommendation, snapshot the price again at close and
record the movement.

- Per sport and market: mean CLV in cents, share of recommendations that
  beat the close, each with its N.
- CLV needs roughly 50 observations to say something, against several
  hundred for a win-rate verdict, so this is the number that will first
  tell the operator whether the model is buying cheap.
- **CLV is a claim like any other**: it renders with its N and makes no
  edge claim below the declared threshold.
- If mean CLV is negative once N is meaningful, the honest reading is that
  the model is buying rich, and it goes into FOLLOWUPS in those words.

## PHASE R4 — What the operator sees each morning

One line per recommended bet: the question in plain words, fair value, the
price, the edge after fees, the size, and the gate status. Nothing else.
No "lock", no "best bet", no confidence theatre — the words stay the plain
ones the scan already enforces.

## Close-out

Standard table, one row per phase, four verdicts, evidence nameable.

---

## How this brief is read (written at receipt, before any work)

**The ruling is the operator's to make and it is made.** The prior law said
the tool would refuse this and point at itself; the operator has replaced the
law rather than asked the tool to ignore it, which is the mechanism working
rather than being bent. The old text stays in `CLAUDE.md` above the new one,
with the date and the reason, so a later reader can see what changed and why.

**The four structural prohibitions are treated as harder than the law they
sit in.** The brief marks them "NOT amendable by a later session", and they
are enforced the way the other laws are: scans over the package, the
environment and the record, each proved by a planted violation. No credential,
no authenticated call, no order path, no ledger. A later brief asking to
soften one is refused and pointed here, which is exactly what the prior law's
own refusal clause did for staking.

**One concern, recorded once, and then the work proceeds.** No market in this
record has passed its hundred-resolution gate, so on the day this ships every
recommendation is a flat unit with "no measured edge" beside it. That is the
brief's own design and it is the right one: the sizing rule is what stops an
unmeasured model turning into a variable-stake one. The concern is worth
stating plainly all the same -- a recommendation surface reads as authority
whatever the label says, and the label is doing a great deal of work until a
gate opens. The gate, the flat unit and the closing-line measurement in R3 are
the three things that keep this honest, and none of them may be quietly
loosened later.

**"Recommends, never transacts" is read as a line about capability, not
intent.** It is not enough that the code does not place an order today; the
scans are written so that adding one would fail the gate rather than merely
being frowned upon.
