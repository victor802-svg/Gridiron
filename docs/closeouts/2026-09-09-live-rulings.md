# Close-out — the Live rulings (2026-09-09, afternoon)

Against the brief in `docs/briefs/2026-09-09-live-rulings.md`.

| ruling | verdict | evidence |
|---|---|---|
| 1. guard narrows; live card shows the pregame probability, in that word | **DONE** | `model_words` out of `LIVE_FORBIDDEN`, `pregame_words` in; two plantings |
| 2. the page keeps asking at the poller's cadence | **DONE** | one line was the whole defect; `audit.live_poll_faults` in the gate, two plantings |
| 3. window closes on a final; per-sport first-start word | **DONE** | measured before and after; one planting, two tests rewritten |
| carried in: cadence from the server, price-endpoint planting | **DONE** | `/api/live` carries `poll_seconds`; the poll may touch no priced endpoint |

---

## Ruling 1 — the law never moved

LAW 5 has always said *"Live win probability may be displayed and is never
sized."* The guard written on 2026-09-08 — after the old Picks grid was found
leaking fifteen cards under Live's empty state — put `model_words` in
`LIVE_FORBIDDEN`, which forbade the probability itself. It overshot the ruling
that produced it: what was being prevented there was a recommendation surface,
not a number.

**What a live card carries now:** the corrected probability the claim was
written with, as `pregame 33%`. Nothing else came back — no price, no edge, no
size, and the tier chip is now explicitly stripped as well, since a confidence
band on a game being played is exactly the kind of thing the in-game rule is
about.

**The word is not decoration.** No live model exists here — THREE_STATES S5 is
unbuilt — so a bare `74%` beside a live score claims something this app does
not have. `live_card_faults` fails by name on a `pregame_words` value that
does not contain the word.

### Two things found while wiring it

**`recommend` refuses a game in progress**, by design — `refuse_in_game` skips
the row before an entry exists — so a live card has no priced entry to take a
number from, and the first render produced `None` on every live card. The
figure is read from the **claim** instead, which is the right source anyway:
it carries the model's probability for the venue's own proposition, frozen
before first pitch, and the claim guard already refuses one written after it.

**It is flipped with the question**, like every other number on the card. A
claim is stored from a fixed proposition and the question names the side the
model took; on the first card that ever cleared the bar those were opposites,
and the price row read "Toronto covers +1.5" over three numbers about the
Athletics. An unflipped pregame figure would be that defect again, on a number
with no price beside it to make the mismatch visible.

## Ruling 2 — one line, and the screen disagreeing with the server

```js
if (!live.any_live) stopLivePolling();
```

A page opened before first pitch polled **once**, saw nothing live, and killed
its own timer for the day. Every game could start and the screen would never
learn — which is precisely the state the operator described: the server held
six live cards with scores while his page said nothing was being played, and
only a reload fixed it.

The page now stops when **`slate_complete`** — nothing left to play, which is
the poller's own rule — rather than when nothing happens to be on in the
second it asked.

**And the cadence comes from the server.** `LIVE_POLL_MS` was 60000 while the
poller writes every 90 seconds: two numbers in two files for one fact, with
the browser asking half again as often as the data could change. `/api/live`
carries `poll_seconds` and the page adopts it on the first tick that has it.

`audit.live_poll_faults` reads the shipped renderer and fails on: stopping at
`any_live`, never reading `slate_complete`, or fetching any priced endpoint —
the last being the price-endpoint planting carried in from this morning.

## Ruling 3 — measured before and after

| | before | after |
|---|---|---|
| 1h past first pitch | polled | polled |
| 4h | polled | polled |
| **5h** | **dropped** | **polled** |
| 8h | dropped | polled |
| 13h | dropped | dropped (stale backstop) |

The window closed on `GAME_HOURS`, so extra innings or a rain delay ended the
poll while the game was still being played and the score froze on screen with
nothing saying so. It closes on `status = 'final'` now.

**The cap moved rather than vanished.** Without one, a row whose status never
arrives would keep the poller requesting all night — the zero-request contract
undone from the other end. `STALE_AFTER = 12 hours` is far beyond any real
game in any sport here.

**Two tests held the old rule** and were rewritten rather than weakened: each
keeps the edge it was testing, the far boundary moves from the expected length
of a game to the backstop, and a new test asserts the real closing condition —
a game seen final closes its window at once, whatever the clock says.

### The per-sport word

`SLATE_STATES["upcoming"]` was `"first kickoff"` for all five sports, so
baseball, basketball and the fights all said kickoff. `FIRST_START_WORDS`:
first kickoff, **first pitch**, first tip-off, first bell.

## What is not fixed, and is not in these rulings

**A card does not move between groups on a tick.** `applyLive` patches score
and clock in place, and `live_update_faults` fails by name on it calling
`renderWeek` — the guard from 2026-09-08 that I once reasoned past and was
corrected for. So a page held open across first pitch now keeps its scores
current, but the card stays in the group it was rendered into until the next
full render.

That is a real remaining gap and it is deliberately left: moving cards between
groups on a state change is a change to the rule about what a tick may do, and
that is the operator's to make.
