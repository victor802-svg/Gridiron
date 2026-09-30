# GRIDIRON_ENTRY_CHECK — brief, 30 September 2026
Why: the model has never shown an edge against a market price. Pick'em promos are the one place an edge can come from arithmetic alone. The entry check does that arithmetic, keeps the operator off legs the model leans against, and records every entry so the edge is measured, not assumed.
Scope (v1): NFL player props only. Apps: PrizePicks, Underdog, Chalkboard. Entry types: power and flex. Promos: payout boosts, discounted lines, deposit matches.
LAW 5 (forbidden half unchanged): the operator types every entry. Gridiron never logs in to, reads, scrapes or calls any pick'em app, holds no credential for one, never places or edits an entry. No payout table hard-coded as fact: the operator types the multiplier or flex table shown in the app; the last one typed per app and entry size is offered as a default and must be confirmed.
Step 1, the arithmetic (no model): "Check an entry" on the Props page: app, entry type, legs (player, stat, line, over/under, original line if discounted), payout (power multiplier or flex table), optional boost (boosted multiplier, or profit-boost percent and cap, converted and shown). Output: break-even per leg (power M^(−1/N); flex solved from the typed table); EV per unit at coin-flip legs; the boost's value (EV with minus without); a same-game flag on legs from one game ("these legs move together; the math assumes they don't"), no correlation estimate (LAW 2). Colour law: green outline clears, red outline costs.
Step 2, the model as a veto: each leg's model probability at the typed line if the model forecasts that player and stat; at a discounted line only if the model can state a probability at any line, otherwise "can't price this discount". Show model EV beside coin-flip EV and flag legs below their break-even, with the model's record for that stat in plain words. The model only flags; it never raises a verdict.
Step 3, the record: a checked entry can be marked "taken" and is stored append-only: app, entry type, legs, lines (original and discounted), typed payout, boost, coin-flip EV, model EV and per-leg probabilities at the time. Units only, no dollars. Legs graded from settled stats. Record page "Pick'em": legs hit vs 50% and vs break-even, by app and entry type; boosted vs unboosted; model-flagged vs not. No verdict below 100 graded legs; show the count.
Step 4, deposit match calculator: typed bonus, playthrough multiple, entry type and payout used for playthrough; output the bonus's expected value after playthrough at coin-flip legs, with the playthrough cost shown, and "read the offer's terms; this assumes the numbers you typed".
Out of v1 (FOLLOWUPS): sharp-book prop prices as a better prior than 0.5; other sports; free/no-sweat entries; screenshot input.
Done means: each step released with its gate. Plantings: a wrong break-even, a boost applied twice, an unflagged same-game pair, a model flag raising a verdict, a taken entry edited.

---

Saved verbatim at the operator's instruction (2026-09-30), with the order that
came with it: "Queue the pick'em entry check after Q35. Order: Q36.1 → step A →
item 1 → Q35 → entry check (steps 1–4, each its own gate and release; step 1
ships first) → Q33 + Q34 → Q25/Q26 → Q5 → Q10."
