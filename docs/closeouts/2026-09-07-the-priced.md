# Close-out — GRIDIRON_THE_PRICED (2026-09-07)

Against the brief saved at `docs/briefs/2026-09-07-the-priced.md`. One row per
phase plus one per decision.

| # | phase or decision | verdict | evidence |
|---|---|---|---|
| FIRST ACT | Save the brief on receipt, queued behind the one in flight | **DONE** | Saved verbatim (8f6efd7) with nothing executed, and the reading written before the first line of code (661a01d). |
| D1 | The coverage list, and how it is chosen | **DONE** by measurement, option (a) | Five NFL games' ladders captured read-only from the venue; `gridiron/priced/coverage.py` measures the quote width and the volume per market and selects on them. Moneyline: not enough measured. Spread: the busiest half. Total: covered, two cents wide at the middle and 910 contracts at the median. A planting hands the selection a market with four winning tickets and a six-cent quote; it changes nothing. |
| D1 | The FCS hypothesis | **RECORDED, NOT ACTED ON** | In `docs/FOLLOWUPS.md` as a hypothesis with n=4, in those words. Nothing in the coverage rule reads it. |
| D2 | The kill criterion's numbers | **DONE** as the brief's declared defaults | `coverage.KILL_AFTER = 50` and a negative mean closing line stops the market, with the sentence written now rather than on the day. The operator's own numbers replace two constants. |
| D3 | The declared bankroll | **BLOCKED** | A hundred units stands as a denominator so sizes can be expressed. No money figure exists in the repository and no balance is read from anywhere. One constant changes when the operator writes his number. |
| P1 | The priced forecaster | **DONE** | `gridiron/priced/`, outside the blind closure, writing to `priced_forecasts` with the blind row's id, the snapshot it read, its blend version, and a trigger refusing any row stamped at or before the blind row. Its outcome is copied from the blind row rather than judged again. |
| P1 | The closure exemption, guarded both ways | **DONE** | `audit.CLOSURE_EXEMPT_PACKAGE` names one package. `plant.py` imports the priced package from a blind module (caught) and re-runs the original market-import violation (still caught), which is the planting that would have gone quiet if the exemption had loosened the scan generally. |
| P2 | Coverage: bet few things | **DONE** | One market covered of three measured, with the reason for every exclusion in the payload and on the page. Reviewed every 28 days by declaration, not continuously. |
| P3 | Fees and expected value | **DONE** | One fee implementation shared with the hypothetical ledger and the recommendation engine, so no two figures can disagree about the same wager. An edge that does not clear it is reported as no edge. |
| P4 | Closing-line value | **DONE** | Recorded per recommendation at the near-start pass and reported per market with its N, claiming nothing below fifty. The sentence for a negative result is written in advance. |
| P5 | The kill criterion | **DONE** | Asked before the coverage list, because a market stopped by its own closing line deserves the more specific sentence. Tested at exactly fifty. |
| P6 | What the operator sees | **DONE** | "Worth taking" on Picks, one line each, and an empty list that says which of the three reasons it is empty for. A Record section with the coverage, the closing line and the two forecasters' scores side by side. Rendered at both widths. |
| Close-out | This table and the number below | **DONE** | Below. |

## Rulings taken in the operator's absence

1. **The empty list distinguishes three reasons.** Nothing covered, nothing
   clearing the fee, and no price at all are different facts, and one sentence
   for all three would hide the one that needs fixing.
2. **The kill criterion is asked before coverage.** A market stopped by its own
   closing line is stopped whatever the coverage measurement now says.
3. **Repricing frequency is not measured** and is recorded as a hole rather
   than approximated. It needs two looks at one ladder separated in time, and
   the near-start pass has only just begun collecting them. The coverage rule
   therefore stands on two legs of the three the brief describes, and says so.
4. **The blend leans toward the market at 0.35**, declared and dated, because
   the record says the market's prices score better than the model's. A weight
   that leaned toward the model would assert the opposite of the measurement.

## The number this close-out is required to state

At twenty ten-dollar wagers a week, a genuine and professional-grade five per
cent return is about ten dollars a week. The ceiling here is set by stake size
and by the thinness of the very markets where an edge could exist, not by model
quality. Nothing in this project changes that arithmetic, and no later session
should mistake this for a business.

Two facts alongside it, so the ceiling is not read as pessimism about the code:
no market on this record has a measured edge in the model's favour, and the one
market with enough settled questions to check has measured the model as behind
the price. The engine's current output is one flat unit on the questions that
clear a fee, in one covered market, and an empty list on most days.

## The gate

The same two record-dependent checks that were already failing before either of
today's briefs began: a scan renders each sport's current slate and reports "I
checked nothing" as a fault, and no slate has been predicted on 2026-09-07
because the daily task runs at 11:00 local. Verified red on the commit before
this work started. Everything else passes, including the four plantings this
brief added and the two that guard its closure exemption.
