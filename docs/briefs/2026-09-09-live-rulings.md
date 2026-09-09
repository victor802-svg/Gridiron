# Brief — the Live rulings (2026-09-09, afternoon)

Saved before execution, as the standing contract requires. The operator's text
is unedited.

---

Rulings, 2026-09-09, afternoon.

1. Guard amended, law unchanged: audit.live_card_faults narrows from "probability at all" to "probability with a price, edge, size, tier chip, or taken control". A Live card shows the corrected probability the claim was written with, labelled "pregame" in that word on the card, because no live model exists (S5 unbuilt) and the figure must not read as current. Nothing else returns to the card. Planting: a live card carrying "74%" without "pregame" fails by name; a live card carrying a price fails by name.

2. Reconcile the payload with the screen: the server held six live cards while the operator's screen said nothing was being played. Prove which: does a page opened before first pitch ever start polling? If startLivePolling decides once at load, that is the defect — the page re-checks any_live at the poller's cadence whether or not anything was on at load, and starts when the first game does. Planting: a page loaded with any_live false and a game that goes live must fetch /api/live within one cadence.

3. Poller window closes on a final, not a clock, as already agreed; extra innings and delays keep polling. Per-sport word for "first kickoff".

Then gate, commit, push, restart, confirm, and one screenshot of the Live tab during a game showing a score, the last-poll time, and "pregame NN%" on one card.

---

## Carried in from the rulings of this morning, item 4, not yet built

> Live cadence from the server as planned; the price-endpoint planting as
> planned.

Both belong to this work and are built with it: the browser takes its interval
from `/api/live` rather than declaring its own, and a Live-state fetch that
touches a price endpoint fails by name.
