# Close-out — GRIDIRON_THE_RECOMMENDATION (2026-09-07)

Against the brief saved at `docs/briefs/2026-09-07-the-recommendation.md`. One
row per phase. The brief carried no operator decisions; it carried a ruling.

| # | phase | verdict | evidence |
|---|---|---|---|
| FIRST ACT | Save the brief before executing it | **DONE** | `docs/briefs/2026-09-07-the-recommendation.md`, committed before any code (23604df), with the one concern recorded at receipt. |
| R1 | Amend LAW 5 | **DONE** | `CLAUDE.md` now reads "THE APP RECOMMENDS, IT NEVER TRANSACTS", with the permitted list, the four permanent prohibitions, and the previous law quoted in full underneath with the date and the reason it changed. The enforcement table names the checks that exist rather than the ones that used to. |
| R1 | The four prohibitions, scanned | **DONE** | `audit.check_no_venue_credentials` reads the package, the environment and the record; `audit.check_no_order_path` refuses an order name or a write verb from the market module; `audit.check_no_wagering_ledger` refuses the operator's own stakes in the schema or the tree. Five plantings break them on purpose and all five are caught by name. |
| R1 | The retired scan | **DONE** | `check_not_a_betting_tool` is a documented no-op and `BETTING_IDENTIFIERS` keeps its words as `RETIRED_BETTING_IDENTIFIERS`, so a reader who greps for "kelly" finds the history rather than an absence. The two plantings that broke it now break what it stood for. |
| R2 | The recommendation, priced | **DONE** | `gridiron/market/recommend.py`: fair value as a price, the venue's price, the edge in cents after the venue's own fee formula, a side or no side, and a size. Eleven tests. |
| R2 | The sizing rule | **DONE** | Flat unit below the gate, and the same flat unit for a 92% claim as for a 62% one; a quarter of Kelly above it, capped at 2% of a declared denominator that is not a balance. Full Kelly is not reachable at any sample size. |
| R2 | Singles only, nothing in-game | **DONE** | `price_parlay` exists to refuse and says why in the same sentence; `refuse_in_game` is the one door and `for_predictions` is its only caller. Both planted, both caught. |
| R3 | The closing line | **DONE** | `recommendations` records the price each recommendation was made at; the near-start pass writes the closing price and the movement once. `calibration.clv_report` reports mean cents and the share beating the close per market, with its N, claiming nothing below fifty. |
| R4 | What the operator sees | **DONE** | A "Worth taking" section on Picks: one sentence per recommendation with the question, fair value, the price, the edge after fees and the size. Rendered at 1100 and 390 pixels. An empty list gets a sentence rather than a blank space. |
| Close-out | This table, the findings and the gate | **DONE** | Below. |

## Rulings taken in the operator's absence

1. **A measured sample is not a measured edge.** The brief's sizing rule keys
   on the n=100 gate. Read literally, that would have staked 2% of the
   bankroll on baseball moneyline, where 286 settled questions have measured
   the model as WORSE than the market's own prices. The fraction now requires
   the sample and a measured edge in the model's favour; the brief's own label
   -- "no measured edge — flat unit" -- is the authority for reading it that
   way. This is the most consequential decision in the phase and it should be
   reviewed.
2. **"Measured and not ahead" says so in its own words**, rather than reusing
   "no measured edge yet". A market with 109 settled questions is not waiting
   for data it already has, and a reader told otherwise would draw the wrong
   conclusion about what happens next.
3. **The declared denominator is 100 units**, pending the operator's own
   figure (THE_PRICED D3). It is a denominator and not an amount: no money
   figure exists in this repository and no balance is ever read.
4. **A recommendation is stored, the operator's stake is not.** The
   `recommendations` table records what the app said and at what price,
   because the closing line cannot be measured otherwise. It holds no stake,
   no return and no position, and `check_no_wagering_ledger` refuses a table
   that would.
5. **The fee comes from one implementation**, shared with the hypothetical
   ledger, so the record and a recommendation cannot disagree about the same
   wager.

## What the first runs caught

Four defects, none of which a test would have found unprompted:

1. **The credential scan flagged three innocent things** on its first run: the
   app's own sign-in cookie and the Anthropic key, twice. A fault now needs a
   venue word and a credential word in the same name, except inside the market
   module. A guard that cries wolf gets an allowlist, and an allowlist is a
   mute button.
2. **A bare "withdraw" in the order-path list** flagged the feature this
   project withdrew last week. The list names funds explicitly now.
3. **The in-game rule looked for a status this schema cannot hold.** It
   checked for "in_progress"; the record says "in". Every live game would have
   passed the guard. A test using a real status is what found it.
4. **The sizing rule keyed on the wrong thing**, as above. The live slate
   found it: the first real recommendation the engine produced was sized at
   the cap on the one market the record has already measured the model as
   losing.

And two the render caught: the same gate sentence printed under all twelve
recommendations, and a size reason that repeated the phrase it was explaining.

## The concern, recorded once

A recommendation surface reads as authority whatever the label says. Today
every recommendation on this record is a flat unit, and the two things
standing between an unmeasured model and a variable stake are the gate and the
sizing rule -- both of which are code, both of which are planted against, and
neither of which may be quietly loosened by a later session. The closing-line
measurement is the third, and it is the one that will say something first: it
needs about fifty recommendations rather than several hundred settled games.

The honest state of the evidence on the day this shipped: no market on this
record has a measured edge in the model's favour, and the one market with
enough settled questions to check has measured the model as behind the price.

## The gate

Two record-dependent checks were already failing before this work began, and
are unrelated to it: a scan renders each sport's current slate and reports "I
checked nothing" as a fault, and no slate has been predicted on 2026-09-07
because the daily task runs at 11:00 local. Verified red on HEAD with this
session's changes stashed, and recorded in `docs/FOLLOWUPS.md`. Everything
else passes, including the nine plantings this phase added.
