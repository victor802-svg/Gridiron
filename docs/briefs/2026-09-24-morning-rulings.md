# Brief — rulings on the morning report (2026-09-24)

Saved before execution, as the standing contract requires. The operator's text
is unedited.

---

Rulings, 2026-09-24, on the morning report.

1. Recommendations 62–66 and every NFL/NCAAF spread and moneyline forecast written from fits 91–94 since 05:16Z are VOIDED: one append-only void row each, dated, reason "published from an unvalidated fit before the hold; fit subsequently failed holdout" (or "not yet validated" for NFL moneyline). Voided rows never count in CLV, calibration, correction, readiness, or any gate; the page shows them as withdrawn in those words, never deleted. If any is in picks_taken, the tap stays (it is the operator's choice) and is excluded from the model's curves. Planting: a voided recommendation counted anywhere fails by name.

2. Root cause, class (a), fixed with the hold: training a fit must not make it live. Fits are written inactive. A fit becomes the active model for a market only by an explicit, dated activation that records its holdout scores against the incumbent. The predict path reads only activated fits. A logon catch-up or scheduled run after a training step publishes from the incumbent. Plantings: a freshly trained fit with no activation is never used, and an activation without holdout scores is refused.

3. fs5 disposition as measured: NFL moneyline activated on fs5 (holdout not worse); NFL spread, NCAAF spread and NCAAF moneyline revert to their last trained sets, dated. The retired rating factors reactivate for those markets by dated entry. The page shows forecasts only from each market's active fit.

4. Weather: precipitation, wind and cold all follow the same rule. An indoor game carries no value; the fit reports each factor's rows used. Report each factor's coefficient before and after on the holdout.

5. Working method for the rest of the repair: one operation at a time. No rehearsals, splits or scripts against the worktree while a gate runs, and no concurrent gates. After this commit batch lands and /api/health confirms it, end this session and start a fresh one from the state file. Items 3–8 continue there, in order.

---

## How this brief is read

**"This commit batch"** is everything now in flight: item 1 (the closing line),
the word-scan fix the gate needed, the hold, and rulings 1–4 above, which
together are GRIDIRON_REPAIR item 2. Ruling 2 says the root cause is fixed
*with* the hold, so they land together. Items 3–8 wait for the fresh session.

**Recommendation 65 is read narrowly.** "62–66" names a range, and 65 inside it
is an NFL total from the reasoning forecaster on fs2. It was not written from
fits 91–94, and the stated reason does not describe it. A void is permanent and
not voiding is reversible, so 65 is left standing and put back to the
operator. 62, 63, 64 and 66 are voided.

**"Forecast written from fits 91–94"** is read as the statistical forecaster's
rows (31). The reasoning forecaster's rows written in the same runs (31) do not
come from a fit. They stay standing and are reported, for the same reason.
