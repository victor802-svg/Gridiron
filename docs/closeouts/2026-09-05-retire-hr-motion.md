# Close-out — retire home runs, the view menu, the hero floor, motion

Brief: `docs/briefs/2026-09-05-retire-hr-motion.md`.

## 0. Deviations from the brief, up front

- **D1–D3 were not pasted.** The brief says "Then D1–D3, then R1–R4" and gives
  detail only for R1–R4. Nothing in the paste says what D1–D3 are; inventing
  three design phases is the failure the contract forbids. **BLOCKED**, not
  skipped: sending them is one paste, and R1–R4 were built from their own
  paragraphs.
- **One extra commit, outside the brief:** a run line of 0.0 is not a line
  (`3cd6d0d`). The gate found it on the live record this afternoon — ESPN posts
  `spread: 0` before a baseball run line exists, ten reached the record as
  lines, and the sign check called four of them contradictions. It blocked
  "verify.py green" and it was a clear defect, so it was fixed alone and first.

---

## 1. Against the brief

| phase | verdict | evidence |
|---|---|---|
| FIRST ACT — save the brief, read CLAUDE.md and MENTOR.md | **DONE** | `8049a77` |
| D1 | **BLOCKED** | not pasted |
| D2 | **BLOCKED** | not pasted |
| D3 | **BLOCKED** | not pasted |
| R1 retire home runs: registry entry, questions skip, Record row greyed with its final count, no Picks tab, cap loop excludes, checklist doc | **DONE** | `c2de0b1`. `config.RETIRED_MARKETS` = {retired 2026-09-05, from 2026-09-05T20:53:01Z, reason "operator ruling"}; `questions.assert_market_active` refuses at the write door and `predict_slate` skips on the way in; the MLB candidate loop and `select_day_props` fill across `active_prop_markets`; `already_answered` no longer counts it as a gap; `views._market_tabs` reads the active roster; Record's category reads "home runs · retired, statistical", greyed, N final; the outlook says the count is final; `docs/MLB_PROPS.md` records 51 written / 40 settled / 6 voided. Plantings: a row at the moment the door closed named, the second before not (`1ca861d`); the market put back on the strip fires. Both in the gate. |
| R2 the view menu: 44px, click/outside/Escape/keyboard, two labelled toggles, one-word tag, per-sport session memory; planting: a third control row | **DONE** | `9cfb3cc`. Button 44px, `aria-expanded`, panel closes on Escape (focus returns) and outside click, Tab lands inside; toggles "Forecaster" and "Forecast", the tag "statistical · final"; `viewChoice` Map per sport, memory only. `audit.picks_control_row_faults` declares the two rows (a nav counts by nature, a collapsed details does not); planted; in the gate. |
| R3 HERO_MIN_CLAIM = 0.55 dated; selection takes the tab's cards and the sort, filters, returns first or None; "no lead" in language.py; planting | **DONE** | `b1f3c53`. `heroCandidates`/`selectHero`; the grid drops exactly the lead; `language.no_lead_line`; a fully flagged tab still shows no hero (ruling 2 stands). Tested AT the boundary (0.55 leads, 0.5499 does not). `hero_flag_faults` reads the floor off the renderer; planted by removing it. |
| R4 transitions in the one motion block; carousel keeps dots and arrows, adds swipe; renders before commit at 1440/390 mid-transition; reduced motion identical; plantings: transform outside 2%, duration over 200ms | **DONE** | `bcf173e`. Two lines in the motion block; `.arriving` snaps with `transition: none` and comes off a frame later; swipe of 40px steps the hero; `audit.transform_faults` holds the bound AT 2% and refuses pixels and sideways; two plantings. Rendered before commit: 11 mid-transition frames at 1440 and 390 (opacity 0 → 0.13 → 0.26 → … → 1 over 200ms), reduced motion identical boxes and `0s`. |
| QA — full suite no skips under .venv; all plantings; verify.py green | **DONE** | `scratchpad/qa_verify2.txt`, run on the committed tree at `b5c5253` under `.venv`: step 1 the full suite, 1144 tests, no skips, no failures (one test reaches the network by design and is named); step 2 201/201 planted violations were caught; steps 3–4 and every check green, 54 PASS and 0 FAIL; exit 0. An earlier run on the same afternoon failed twice — the midnight-bound retirement check on five real rows and the card-expand test mid-arrival (§2.2, §2.3) — both fixed before this run. |
| QA — renders: Picks on MLB with the new control row; the view menu open; the hero on a tab with no ≥55% pick; Record with the retired category | **DONE, one of them synthesised** | `scratchpad/shots_qa/`, 1440 and 390, on a byte copy of the record. Picks on MLB: the controls line (sort, tier, View) and the market tabs, eight tabs and no home runs, tag "statistical · final". The menu open: 155×44 button, `aria-expanded`, "FORECASTER statistical / FORECAST final · early view". Record: "home runs · retired, statistical — 34 of 100 · retired Saturday 5 September; nothing more will be written, so 34 settled is the final count", greyed, beside N 29 / voided 6. **No tab in the record is under the floor everywhere** (every tab on every sport has a pick at or above 55%), so the no-lead hero was rendered by handing the shipped renderer a synthetic tab through its exported door: the hero's place shows the sentence, no pick, no `data-id`, at both widths. Plain-words scan on every capture: clean. |
| QA — read-cold pass on five cards | **DONE** | Five cards, four sports, at 1440 and 390, each face read against the stored row: Matt Olson — NO home run 83% (stored under 0.5); Temple covers −24.5, 76%, market 33% (stored TEM cover −24.5); the NFL hero "49ers at LA — San Francisco covers +5.5" with the market at 56% (stored LA `not_cover` −5.5 — the other-side rule, and a stranger reads the right side); Montenegro vs Benouaich over 2.5 rounds 72%, settled LOSS (stored over 2.5); Miguel Vargas under 1.5 hits 77% (stored under 1.5). All five match at both widths; nothing needed decoding. |
| /closeout; push | **DONE** | this file; pushed |

## 2. Bugs I introduced, and how they were caught

1. **The closed view panel was painted.** `.view-panel { display: grid }` beat
   the hidden attribute and the panel sat open under an unexpanded button on
   every Picks render; my test checked the attribute. **Caught by looking** at
   the 390 render. Fixed `2066b7f`; the test now asserts the paint.
2. **The retirement bound from midnight and named five real rows** written
   at 18:00Z by the scheduled pass, hours before the 20:53Z ruling — a
   retroactive rule (MENTOR 4). **Caught by the gate** on the live record.
   Fixed `1ca861d`: the registry carries the moment the door closed and the
   check binds from it; the five rows stand.
3. **The card-expand test read the grid's arrival as the card moving** (7px,
   1% of the grid). **Caught by the gate.** Fixed `b5c5253`: the card suite's
   slate helper waits for the arrival to settle.

4. **The fade never ran.** R4's first `.arriving` rule lacked `transition:
   none`, so adding the class animated *towards* zero and the removal a frame
   later reversed it: the class toggled, nothing faded. **Caught by looking** —
   the pre-commit render's sampler read opacity 1 on every frame — after the
   browser test had passed, because that test checked only that the class
   toggled. The test now requires a sampled frame strictly between 0 and 1.
   FOLLOWUPS carries the lesson.
5. **The reduced-motion comparison measured mid-arrival** (a 3px lie: 1% of the
   hero's height). Caught by the test failing; it now waits for the arrival.
6. **The retired label read "home runs, statistical · retired"**; the brief's
   wording puts the word beside the market. Caught by my test.
7. **`select_day_props` raised KeyError on a candidate in a retired market**
   (a defence the real candidate loop never needed, but the cap loop should
   not trust its caller). Caught by my test.
8. **The rerun-refusal test and its planting went vacuous this afternoon** —
   pre-existing, not mine, but found here: both read the live record's biggest
   LLM slate, and that slate's card started at 20:00Z, so every question was
   skipped as under way and zero calls proved nothing. Caught by the gate
   failing on the test. Both now build their own world.
9. **The tab-derivation planting compared the strip to the declared roster**
   and escaped once R1 made the strip the active roster. Caught by the harness.
10. **The run-line placeholder** (above) — caught by the gate's live-record
   check, pre-existing data behaviour.

## 3. Vacuous passes found

- `test_a_tab_switch_arrives_through_the_motion_block` (mine, first version) —
  see 2.4. Fixed.
- `test_a_rerun_over_a_written_slate_makes_no_model_calls` and its planting —
  see 2.8. Fixed.
- `test_the_carousel_keeps_its_dots_and_arrows_and_steps_on_a_swipe` carries a
  `pytest.skip` when a slate has fewer than two picks; conftest turns an
  unexplained browser skip into a failure, so it cannot read green silently.
  Left as is.

## 4. What I could not verify

- The view menu, the hero floor and the motion were rendered and driven in a
  headless Chromium at 1440 and 390 — not on a phone, and not by a touch of a
  finger. The swipe is a synthesised TouchEvent.
- Whether "statistical · final" reads as a one-word tag to a reader: the
  forecaster label is the payload's ("statistical", "LLM"), so the reasoning
  pass reads "LLM · final". The brief's example was followed; the other label
  is the existing declared one.

## 5. Rulings taken in your absence

1. **D1–D3 BLOCKED rather than inferred** (§0).
2. **The run-line placeholder fixed alone, first** (§0). Reversal: revert
   `3cd6d0d`; the gate then fails on the four stored placeholders until the
   next refresh replaces them.
3. **The retired market keeps its fitted model and its training loop**; only
   the asking stops. Retraining a market nobody asks costs a few seconds a week
   and deleting a fit is not retirement. Reversal: skip retired markets in
   `baseline.train_all`.
4. **A fully flagged tab still shows no hero** (ruling 2 of 2026-09-04) and only
   a tab with candidates under the floor shows the no-lead sentence. Reversal:
   one branch in `renderHero`.
5. **The pass toggle stays visible with "early view" disabled** on a slate that
   has no early forecast, rather than hiding half the menu. Reversal: hide the
   toggle when `has_early_view` is false.
6. **A `<nav>` counts as a control row by nature** in the two-rows guard, since
   the market tabs are filled at render and their markup holds no button.
7. **The movement bound refuses pixels, not only large values**: a bound in
   pixels is a bound at one width. Reversal: accept `px` under a pixel ceiling.
8. **The rerun planting's world is a backtest**, because the harness league's
   last slate kicked off in December 2025 and a live world skips it.
9. **The retired label's word order**: "home runs · retired, statistical".

## 6. The operator's attention list

1. **D1–D3** — paste them; nothing was built for them.
2. The MLB record now has **four prop markets on Picks and five on Record**; the
   retired row reads "home runs · retired" with 34 settled by the model and 6 by
   the reasoning pass. **Today's slate still carries five home-run picks** —
   written at 18:00Z by the scheduled pass, before the ruling — and they lead
   the MLB hero this evening; they resolve tonight and there will be no more.
3. The gate has **five new checks** (retired-written, retired-on-Picks, two
   control rows, plus the earlier fingerprint and run-record) — all green in the fresh gate (201/201 planted violations were caught, exit 0).
