# Brief — rulings on the three open decisions (2026-09-24)

Saved before execution, as the standing contract requires. The operator's text
is unedited.

---

Fresh session. Start from docs/REPAIR_STATE.md on the repair branch. One operation at a time; no work against the worktree while a gate runs; no concurrent gates.

Rulings on the three open decisions, 2026-09-24:
1. Recommendation 65 stands. The void covers only rows written from fits 91–94; my "62–66" was imprecise. Voids are irreversible and apply only to rows actually tainted.
2. The 31 reasoning-forecaster rows: read the prompt the reasoning pass actually sent for each. If it carried any fs5 output (a probability, a rating, a line derived from fits 91–94), void that row under ruling 1. If not, it stands. Report the count each way with one example prompt.
3. Holdout rule: ties go to the incumbent. A new fit is activated only if it beats the incumbent on the holdout with the bootstrap interval of the difference in log loss excluding zero; otherwise the incumbent stays. Under this rule all four fs5 markets revert, including NFL moneyline. Record the rule in CLAUDE.md as part of the activation gate from ruling 2 of this morning.

Then, in order, each its own commit, gate and release: rulings 1–4 of this morning (voids, inactive-until-activated fits, revert, weather), then repair items 3–8. The hold is lifted per market only when that market's active fit is the incumbent and its forecasts are from it. Close-outs report spend.

---

## How this brief is read

**The order of commits** is voids, then inactive-until-activated fits with the
activation gate, then the revert of all four fs5 markets, then weather, then
repair items 3–8. Each commit is gated and released on its own, and nothing
touches the worktree while a gate runs.

**"The hold is lifted per market only when that market's active fit is the
incumbent and its forecasts are from it"** is read as two conditions, both
checked by code: the market's activated fit is the incumbent the revert named,
and the page shows forecasts only from that active fit. Lifting the hold is
what lets the incumbent forecast again. No fs5 row can reach the page after
that, because the page filters on the active fit and the fs5 rows are voided.
