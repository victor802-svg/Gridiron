# Close-out — PrizePicks as a market source, STRONG by default

Brief: `docs/briefs/2026-09-02-prizepicks.md` (GRIDIRON_17).

---

## 1. Close-out table

| phase | verdict | evidence |
|---|---|---|
| **First act** save the brief | **DONE** | `d498607`. |
| **First act** apply the operator's LAW 5 amendment verbatim | **DONE** | `2b704c4`. The operator's text, unedited, replacing the old law. |
| **First act** quarantine the identifier to the market module + planting | **DONE** | `audit.market_source_faults`; `plant_a_market_source_outside_the_market_module` writes the name into a real prediction-path module and runs the scan against the tree holding it. |
| **Z1** the feasibility probe | **DONE — negative result** | `36d7536`, `docs/PRIZEPICKS_FEASIBILITY.md`. Q1 answered; Q2–Q5 recorded as unanswerable. |
| **Z1.5** `docs/MARKET_ROSTER.md` | **DECLINED** | The brief ranks by *volume × data availability*, and volume is the half only PrizePicks can supply. Publishing the other half under that name would present half a ranking as a whole one. Reasoning in the probe, §5. |
| **Z2** the second market source | **BLOCKED** | There is no accessible source to snapshot. Nothing was built on a guess. |
| **Z3** STRONG by default | **DONE** | `fe117eb`. Live on all four sports at 1400px and 390px. |
| **Z4** verification, scoped to what exists | **PARTIAL** | `7071de5`. Suite, plantings, renders and gate all done; the live PrizePicks proof has nothing to prove against. Itemised in §4. |

## 2. Z1 — the probe, in one line

`GET https://api.prizepicks.com/projections` answers **HTTP 403 with a
DataDome CAPTCHA challenge** on the first request from a clean client with an
honest User-Agent. `api.prizepicks.com/robots.txt` returns the same challenge —
the host will not serve its own robots file.

**The block was not worked around, and the shape of it was not explored.** One
request was made. Probing how hard a block is to pass is the beginning of
passing it.

Where the marketing site's empty `Disallow` and a deployed bot-detection
service disagree, the probe reads the control as the clearer statement of
intent.

## 3. Z3 — STRONG by default, as it now opens

| sport | opens on | count line | caveat |
|---|---|---|---|
| NFL | STRONG | `STRONG · 24 of 78 picks` | 0 settled of 20 |
| MLB | STRONG | `tonight · STRONG · 13 of 45 picks · 15 below the 70% floor` | 19 settled of 20 |
| NCAAF | STRONG | `STRONG · 15 of 17 picks` | 0 settled of 20 |
| NBA | **all tiers** | `0 picks` | none shown |

Three things are load-bearing and all three are asserted, not eyeballed:

1. **The filter never hides what it hid.** `audit.tier_count_faults` fails on a
   tier-keyed count line naming no denominator, and `/api/week` returns 500
   rather than serving one. Four picks on a 46-pick night reads as a quiet
   Tuesday, and **the reader did not choose this filter.**
2. **The default yields on a slate without the band.** NBA is the live proof:
   no picks, so no STRONG, so it opens on every tier rather than on an empty
   list under a filter nobody asked for. A reader's *own* choice is honoured
   either way, empty result included — that is a question they asked.
3. **The caveat says what the default costs.** Opening on the most confident
   band also opens on the least-tested one. Composed server-side from the
   record rather than the slate, and it stops being sent once the band clears
   its gate — a caveat that outlives its reason is furniture.

The Record tab is untouched.

## 4. Z4 — what was verified, and what could not be

| the brief asked for | status |
|---|---|
| full suite, no skips | **DONE** — 926 tests, **0 skips**, 0 failures |
| planting: the identifier outside the market module | **DONE** |
| planting: payout arithmetic | **DONE — and it found a real gap** (§5) |
| planting: a STRONG default that hides the count | **DONE** |
| planting: the fetcher inside a prediction closure | **BLOCKED** — there is no fetcher |
| planting: a card inventing a probability at an unanswered line | **BLOCKED** — there are no PrizePicks lines to differ from a rung |
| render: Picks opening on STRONG with its count line, desk and 390px | **DONE** |
| render: a prop card with both lines equal / differing | **BLOCKED** |
| live proof: one slate's PrizePicks snapshots | **BLOCKED** |
| `verify.py` green | **DONE** — 4/4, EXIT=0 |

## 5. What I would put in front of you

1. **LAW 5's text and LAW 5's mechanism did not agree, and the brief's own
   planting is what found it.** The amended law forbids "payout or
   price-to-return arithmetic ... no slip". `BETTING_IDENTIFIERS` contained
   **none of those words**. A `prizepicks_payout` function written into the
   market module was scanned and passed. Eight words added, each checked
   against every identifier in the package first. `vig` and `odds` were
   deliberately left out: `devig_pair` recovers a fair probability and a stored
   price is what the market *said* — both are reading, which the law permits.
   The forbidden act is turning either into money.

2. **A defect found while rendering Z3, unrelated to it, and fixed.**
   `applyLive` fetched the desk tile's corner by `.tile-mkt`, a class renamed
   to `.tile-score` in `bd7ac2f`. **Every live tick threw**, and because the
   throw escaped the `forEach` around it, one tile stopped the score update for
   **every pick after it on the slate**.

   Nothing caught it, and the reason is worth more than the bug:
   `querySelector` answers `null` rather than raising, so the mistake surfaced
   as silence. The suite was green. The page rendered. The scores simply
   stopped moving. **Every existing desk test asserted on the first render;
   none drove a tick** — and a complete slate never polls at all, so the code
   path had no coverage in either direction.

   Two mechanisms, not one fix: `audit.dead_selector_faults` fails on any class
   the JS asks for that nothing in the app builds (proven against the real bug,
   not a lookalike), and a browser test drives one real poll and asserts the
   score reached the tile. **That test was verified to fail with the old
   selector restored** — a test that passes on a known bug proves nothing.

3. **NCAAF opens with 15 of 17 picks in STRONG, and NFL 24 of 78.** The college
   figure is 88%. A confidence band that holds seven eighths of a slate is not
   distinguishing much, and it points at the same defect STEP 4 recorded: the
   college spread base rate is 0.371, not 0.5, so `cfb_expected_margin` runs
   high and the probabilities it feeds run confident. **Under R2 that defect is
   now the first thing a reader sees.** It is in FOLLOWUPS and unchanged here.

4. **`docs/MARKET_ROSTER.md` was declined, not skipped.** If a roster of what
   our own loaders can already resolve is wanted — ranked by data availability
   alone, with no claim about how often anyone offers each stat — that is a
   different and smaller document, and about an hour. It is not the one the
   brief named.

## 6. What is measurably true now

- Suite **926 tests, 0 skips, 0 failures**; `verify.py` **4/4 EXIT=0**;
  **128/128** plantings (four new this session).
- Picks opens on STRONG for all four sports, rendered at 1400px and 390px.
- The PrizePicks endpoint is blocked by DataDome; one request was made.
- LAW 5 now forbids in code what it already forbade in words.

## 7. Operator's verdicts

**Strongest thing:**

**Weakest thing:**

**What to do next:**
