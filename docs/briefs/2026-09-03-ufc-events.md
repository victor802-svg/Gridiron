ITEM 4 — UFC, ALL SANCTIONED EVENTS + THE MARKET COMPARISON
Save as docs/briefs/<date>-ufc-events.md. Unattended contract.

RULINGS (operator + mentor):
R1 Every UFC-sanctioned event feeds the record — numbered cards,
   Fight Nights, and Dana White's Contender Series — because more
   bouts make the fighter rating better and surface prospects early.
R2 LAW 6 inside the sport: ONE rating pool, SEPARATE calibration
   categories by event tier (numbered / Fight Night / Contender
   Series), each with its own 100 gate. Never a combined UFC record
   across tiers. An event-tier factor is declared so the model knows
   which kind of card it is asking about (Contender Series is
   finish-heavy by design — measure the goes-the-distance base rate
   per tier and report it).
R3 Other promotions (PFL, Bellator, ONE) are different sports under
   LAW 6 — different rulesets. Not in this session; probe later,
   each as its own sport.

E1 PROBE (read-only, appended to docs/UFC_FEASIBILITY.md): does
   ESPN carry Contender Series and Fight Night events, results with
   method/round, and odds? Coverage per tier over the last two
   seasons; fights per week in the Contender Series season
   (Aug–Oct); how the tier is identified in the payload (measured,
   not assumed from the name).
E2 LOADER: all tiers ingested with event_tier stamped; the rating
   recomputed walk-forward over the whole pool; report K refit and
   how many fighters gained a first data point.
E3 CATEGORIES: scoring, tiers and gates split by event_tier;
   Picks/Results show the tier on the card ("Contender Series ·
   Tue 8:00 PM"); the tier table per tier, never summed. Planting:
   a UFC category merged across tiers.
E4 THE MARKET COMPARISON — the PARTIAL from ufc 4: a UFC fetcher in
   the market module (two providers, explicit favourite flag, open
   and close per the probe), snapshots after prediction rows exist,
   the closure audit walking it; cards stop reading "no line".
E5 QA: plantings (merged tiers; a bout from an unsupported
   promotion entering the UFC pool; the fetcher in a prediction
   closure); renders; verify.py; /closeout; push.
