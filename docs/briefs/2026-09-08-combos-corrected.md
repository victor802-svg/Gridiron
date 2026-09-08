# Brief — GRIDIRON_COMBOS, corrected (2026-09-08)

Saved before execution. Supersedes the declined draft of the same date, which
stays at `2026-09-08-combos.md` with the close-out that declined it. The
operator's text is unedited; how it was read is beneath it.

---

Amendment to LAW 5, ruled by the operator 2026-09-08. The paragraph that forbids recommending or pricing a multi-leg combo is amended: the engine MAY price a combo the venue offers as a package, under GRIDIRON_COMBOS. Keep the old paragraph's text beneath the amendment, dated, with this reason: the operator takes the venue's combos regardless, and a computed edge beside a package is better than a guess. The four bulleted prohibitions are untouched and remain non-amendable. Retire the multi-leg raise and its planting by name; replace them with the C1 checks and plantings below.

GRIDIRON_COMBOS, corrected 2026-09-08 against the venue's measured product. Supersedes the declined draft. Arithmetic and screen only.

C1 — THE APP GRADES PACKAGES, IT DOES NOT BUILD THEM. The venue assembles combos; the app evaluates each package it reads. A package is PRICEABLE only if: every leg is a market the record forecasts; every leg is from a different game (a same-game package has no fair value — the record holds no joint model, LAW 2); all legs are one sport (LAW 6); two or three legs. Anything else is UNPRICEABLE: counted in the group heading with its reason, never given a number, never shown as a card. audit.check_combo_package fails by name on a priced same-game package, a priced cross-sport package, a priced package with an unforecast leg, or a priced four-leg package; plant.py plants all four.

C2 — ARITHMETIC. Fair value = product of the legs' published (corrected) probabilities. Venue price = the package price as read. Beside it, print the product of the legs' single prices so the venue's combo margin or discount is one visible number. Fee = the declared formula at the combo price. Edge = fair − price − fee; return on stake = edge ÷ price. A package clears the bar under the same two conditions as a single. Every card prints the singles alternative on the same money, with both fee rates: measured at 1.67x the singles' per dollar on two 60¢ legs and 2.8x on three. At most three packages shown per day, ranked by return on stake; shown packages may not share a leg. Payout is the big chip, coloured by the leg with the largest edge. The payout floor applies.

C3 — SIZE. Below the gate, flat: 0.5u on two legs, 0.25u on three, u = $15. Not adjusted by odds or by the model's own probability. Above the gate, quarter-Kelly capped at the flat fraction, as singles.

C4 — RECORD, GATE, KILL. Settled package = one row in combo_2 or combo_3 per sport; never counts toward any leg's N. Combo CLV on the package price against its close, own N, n=100 gate. Kill, dated in config: at fifty settled per sport, if combo return-on-stake CLV is negative while single-leg CLV is positive, that sport's combo markets enter RETIRED_MARKETS. Taken table records a package tap as one row with the package id; taken/not-taken curves gain a combo line, never merged.

C5 — WORDS. Scan amended, dated: "combo" permitted in the Combos group and on combo cards only. "parlay", "same game", "boost", "builder", "add leg", "slip" stay banned; a planting puts "same game" in a combo label. Nothing on a combo card animates, counts down, or invites another leg.

C6 — WHERE. Third group on Upcoming, Combos, beneath Watching. Heading: "1 priced · 2 same-game, not priceable · none for baseball". When the venue offers no package in any sport the record prices, the group says exactly that in one sentence, with the sport list. Live and Results as before.

Close-out: standard table. State in READINESS the date the combo record opened and which sports had priceable packages on that date.

---

## How this brief is read

**The amendment is properly formed and is executed.** It names the law, gives
the reason, keeps the old text, dates it, and leaves the four bulleted
prohibitions alone. That is the procedure this project used on 2026-09-07 and
the reason the declined draft was declined.

**C1 IS THE WHOLE DESIGN.** The app grades what it is offered. It never picks
legs, never combines them, and never computes a package price -- which is what
made the first draft unbuildable against this venue, and what makes this one
buildable.

**MEASURED BEFORE BUILDING, on 2026-09-08:** the only package markets the
venue exposes today are `KXNCAAMBSGP`, college-basketball SAME-GAME parlays,
which C1 rules unpriceable by name. The cross-game prepacks
(`KXNBAPREPACK2ML`, `KXNBAPREPACK3ML`, `KXNFLCOMBO`, `KXNCAAMB2ML`) list
historical events and expose no markets in any status. No baseball game
package exists at all.

**So the group ships empty, truthfully, and says why.** That is C6's own
requirement rather than a shortfall, and the close-out states which sports had
priceable packages on the day the record opened: none.
