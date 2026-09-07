# Close-out — GRIDIRON_READINESS (2026-09-07)

Against the brief saved at `docs/briefs/2026-09-07-readiness.md`. One row per
phase. Nothing new was built.

| # | phase | verdict | evidence |
|---|---|---|---|
| FIRST ACT | Save the brief before executing it | **DONE** | `docs/briefs/2026-09-07-readiness.md` (1552401), with how it is read: every answer measured rather than inherited, and no threshold moved to produce a pass. |
| V1.1 | Name the escaping planting | **DONE, and the inherited explanation was wrong** | `plant_a_code_name_in_rendered_llm_prose`, guard `audit.llm_prose_faults`. It never plants: its precondition finds the shipped view already faulty. The fault is real and is not the empty-slate case — see V1.3's neighbour below. |
| V1.2 | Turn the gate green | **PARTIAL** | Run and recorded: step 1 FAIL, step 2 FAIL (218 of 219 caught), step 3 PASS, step 4 PASS. It is not green, and the reason is NOT an unpredicted slate — which the brief says makes it a finding. It is the dead reasoning pass, recorded below and in `FOLLOWUPS.md`. |
| V1.3 | Verify the verdict's provenance | **DONE, with a correction** | `meta.kind` is `live`. All 139 settled baseball moneyline rows were written before kickoff, so none is a backtest row. The verdict stands and its number was wrong in my earlier report: the comparison is on **74** settled questions with a price, not 286 — the model's Brier 0.2527 against the market's 0.2412, lower being better. 286 was that sport's total settled count across all markets. |
| V1.4 | Re-measure coverage on real volume | **PARTIAL** | Re-measured on 22 games and 1,172 quoted strikes, against 5 games and 297 before. Both measurements agree: football totals covered, the spread excluded on volume, the winner market not measured enough. Two hundred games is not reachable from one sitting; the number and the distance are recorded. |
| V2 | The readiness document | **DONE** | `docs/READINESS.md`: six criteria, six failures, each with its measured value, a run log that appends, and the standing answer in plain words. |
| V3 | Then stop | **DONE** | No features built. The two-week observation period is recorded in `FOLLOWUPS.md` with the date it ends and the five things to be read then. |

## The finding this session exists for

**The reasoning pass has been returning HTTP 401 since 2026-09-05T15:00:03Z**,
with the venue's own words: `"API key is invalid."` The last successful call
was 2026-09-05T02:56:26Z. Ten consecutive failures follow, including both of
today's scheduled prediction runs. A key is configured — 108 characters — so it
is a rejected credential rather than a missing one, which is the shape of a key
rotated elsewhere and never updated here.

**A guard reported this correctly for two days and was explained away once.**
Earlier today the escaping planting was recorded as an artefact of the hours
before the daily predict task runs. That was wrong, and the brief's instruction
— name it by running the harness, because inheriting an explanation is not
confirming it — is what caught it. The current slates do carry forecasts: 27
cards on baseball's day, 107 on football's week. What is missing is the second
forecaster.

The fix is one line in `.env`, and it is the operator's: this session does not
edit that file.

## Two numbers corrected

1. **74, not 286.** The baseball moneyline verdict is measured on 74 settled
   questions that had a price beside them. 286 was the sport's settled count
   across every market, and I reported it as the comparison's N in two earlier
   documents. The direction of the verdict is unchanged.
2. **22 games, not 5.** Coverage now rests on four times the sample and reaches
   the same list, which is worth as much as the numbers themselves.

## What the readiness document says

Six criteria, six failures, and that is the expected state. The engine's output
is a forecast to read rather than a recommendation to follow; the app already
holds itself to a flat unit with "no measured edge" beside it, and that stays
until all six pass. The one that decides the rest is the closing line, which is
at zero observations and needs about fifty before it says anything.
