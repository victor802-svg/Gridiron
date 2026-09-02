# Overnight session close-out

Brief: `docs/briefs/2026-09-02-overnight.md` (saved verbatim before execution;
paste verified complete). Unattended contract in force throughout.

Ran from roughly 02:00 to **07:49 local on 2026-09-02**, stopping past the
7:00 bound: the clock was checked at the STEP 3/STEP 4 boundary, and STEP 4
was not started rather than started and abandoned.

---

## 1. Every item, as required

| step | item | verdict | evidence |
|---|---|---|---|
| **0** | Stop BRIEF A (calls) | **DONE** | `6dc5252`. O5 not run. The committed-ready work was the three reported picks defects. Tree clean, pushed. |
| **1** | GRIDIRON_16 — withdraw calls, palette v2, picks as ruled | **DONE** | `c31c9fd` W1 · `948e094` W2 · `bd7ac2f` W3 · `67b4d37` W4 · `356c85c` close-out. |
| **2** | GRIDIRON_13 — P1–P7 | **DONE** | `9fb9a9c` · `f4640b7` · `4812532` · `91b5ade` · `529fff4` · `4e35f75` · `bbbf56d` · `313490d` close-out. |
| **3** | MLB run line and totals | **PARTIAL** | `d501e9d`. The probe is complete and committed as `docs/MLB_RUNLINE_FEASIBILITY.md`. **The build was not started** — see below. |
| **4** | Model repairs (CFB-1 ladder, CFB-2 document) | **NOT REACHED** | The 7:00 bound arrived first. |
| **5** | FOLLOWUPS items | **NOT REACHED** | Same. |

**3 complete · 1 partial · 2 not reached · gate green.** That is the count sent
to the phone, and it is the count here.

## 2. Why STEP 3 stopped at the probe

The probe **passed** — both markets are supported, and the evidence argues for
shrinking nothing. ESPN carries a run line fixed at ±1.5 (71 of 71 priced
games), a total (71 of 71), prices for both, and **explicit side labels**, so
the side needs no deriving at all.

The brief says the markets go live tonight if the probe passes. **Tonight had
already gone**: the probe ran at about 05:30, and today's MLB slate was
forecast at 11:00 yesterday with the markets that exist. Two new question
shapes need void rules written first, declared factors with dated rationales,
a fit, the variance bookkeeping, and `NEW_MARKET_CHECKLIST.md` ticked item by
item — the checklist the brief itself requires. Half of that, committed
against a deadline, is what the laws exist to prevent.

**The probe is the thing that had to come first, and it stands alone.** The
build can now start from measured evidence instead of repeating the
measurement.

## 3. Rulings taken in your absence

Recorded in full in the two phase close-outs. The ones that would change
something if you disagree:

| ruling | where | one-line reversal |
|---|---|---|
| The wordmark loses its green (R2 over GRIDIRON_13 R8) | W2 | one declaration in `style.css` |
| The calibration chart drops green/red for emphasis | W2 | one line in `app.js` |
| A losing calendar day may wear the loss colour | P2 | remove `.down` from `_LOSS_SELECTOR` |
| `/api/health` carries a build stamp | P6 | remove the key; the launcher then always attaches |
| Picks is the landing page | P6 | one default in `route()` |
| A withdrawal may only drop what `schema.sql` no longer defines | W1 | — (this one should stand) |

## 4. What I would put in front of you first

1. **Two disagreements between the app and the OS scheduler are now visible on
   Settings.** `predict:nfl` is recorded as 09:00 and Windows holds 11:00; no
   `predict:cfb` task is installed on this machine at all. Both are stated in
   words. Which is right is yours.
2. **`market_lines_raw.spread_line`'s sign is wrong on a quarter of MLB rows** —
   found by the probe, reported not fixed. It affects the market comparison on
   any run-line build.
3. **The brief's margin SD of 4.71 does not reproduce.** Measured on 9,373
   games it is 4.534. A build must re-derive it.
4. **NFL week 1 holds two prediction sets** — 104 written, 78 standing, 26
   counted twice in calibration. Carried from the first close-out; still needs
   a ruling.
5. **I locked you out of your own app at the start of the session** by dropping
   `GRIDIRON_ACCESS_TOKEN` from `.env` while writing the ntfy topic. Fixed,
   with two tests (`775d9f7`).

## 5. The numbers

- **Commits:** 17, each pushed at its phase boundary.
- **Plantings:** 103 at the start of the session, **117** now.
- **Suite:** green in one process, no skips, at every phase boundary.
- **`verify.py`:** 4/4 PASS, EXIT=0, last run 07:5x local.
- **Bugs I introduced and caught:** 20 across the session; 15 by tests or the
  gate, 5 by looking. Three were caught by `check_js_composes_no_prose`, which
  does not run in pytest — the gate saw what the suite could not, three phases
  running.

## 6. Operator's verdicts

**Strongest thing:**

**Weakest thing:**

**What to do next:**
