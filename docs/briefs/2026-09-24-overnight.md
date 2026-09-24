# Brief — overnight, local (2026-09-24)

Saved before execution, as the standing contract requires. The operator's text
is unedited.

---

Overnight, local. Start from docs/REPAIR_STATE.md on the repair branch. One operation at a time, no concurrent gates. Every release: gate, commit, merge to main, push, restart, confirm /api/health.

Queue order, changed by the operator 2026-09-24 because the hold blocks football forecasts before Sunday's slate:
1. Activation gate (fits are written inactive; activation is explicit, dated, with holdout scores; ties go to the incumbent).
2. Revert: all four fs5 markets to their incumbents; lift the hold per market once its forecasts come from its active fit. Confirm on the day strip.
3. Weather: precipitation, wind, cold carry no value for indoor games; report coefficients before and after on the holdout.
4. Reasoning-pass prompt record.
5. Schema rulings: normalised diff check, the ensure-only column in schema.sql, the 8 missing market_snapshots ids classified, the auth test's injectable clock, the raw-connect scan, then the rehearsed single-transaction migration for the 8 behavioural differences, after a verified backup.
6. Repair items 3–8.

Stop and write down the question instead of guessing if any step needs a ruling. Do not touch the "board" branch; a cloud session owns it. Keep REPAIR_STATE.md current after every release and end with a close-out listing what shipped, what's next, and the machine's awake time overnight.

---

## How this brief is read

**A question that needs a ruling blocks only its own step.** It is written
under "Questions for the operator" in REPAIR_STATE.md, and the queue moves on
where the next step does not depend on the answer.

**Known in advance:** activating a fit for a market that has no incumbent has
no rule yet ("ties go to the incumbent" presumes one). Every market forecast
today has an incumbent, so nothing tonight needs that case on the live record.
It is refused there until ruled, and the question is written down.
