# Final close-out — the overnight session

One row per step. The per-step close-outs carry the detail.

---

## 1. The steps

| step | verdict | close-out |
|---|---|---|
| **STEP 0** — finish UFC ITEM 4 (E3–E5) | **DONE**, with E4's second half **DECLINED on evidence** | `2026-09-03-ufc-events.md` |
| **STEP 1** — the cards UI | **DONE**, two recorded deviations | `2026-09-04-cards-ui.md` |
| **STEP 2** — NBA moneyline | **DONE** | `2026-09-04-nba-moneyline.md` |
| **STEP 3** — NBA total | **DONE**, and it measures almost nothing | `2026-09-04-nba-total.md` |
| **STEP 4** — down the roster | **DONE** — 3 markets + 2 roster corrections | `2026-09-04-roster-step4.md` |
| Last act — ntfy push, counts only | **DONE** | §7 |

**Nothing was BLOCKED. Nothing was NOT REACHED.** One thing was DECLINED, on
measured evidence: §2.

## 2. The one DECLINED

**"Cards stop reading 'no line'" (UFC, E4).** The fetcher is built, correct,
cached and wired into the market quarantine — on a 14-bout November 2025 card
it prices 14 of 14, every one with an opening price. **And every bout Gridiron
currently forecasts is unpriced:**

| season | sampled | priced |
|---|---|---|
| 2022–2025 | 72 | **72** |
| 2026 | 18 | **0** |

One priced bout in forty-five sampled from January 2026 onward. The endpoint
answers `200` with `count: 0`. **The source stopped carrying UFC prices.** This
is the PrizePicks precedent: unavailable by evidence, no proxies, no bypass.

**I also corrected my own earlier finding.** ITEM 1's probe reported "19 of 20
sampled bouts carried an odds reference" and its close-out said "the probe
proved it is there". The count was right; the conclusion was not. **The sample
did not span the boundary.**

## 3. What is new in the record

**Five new markets**, taking the project from 24 declared markets to **29
across five sports**:

| market | edge (walk-forward, sanity only) |
|---|---|
| NBA moneyline | **+0.0415** |
| NFL moneyline | **+0.0215** |
| MLB batter strikeouts | rate form, fitted; walk-forward pending — §6 |
| NBA total | **+0.0010** |
| NFL total | **+0.0016** |

**One layout** where there were two. The desk and the compact rows are deleted
— markup, CSS, breakpoint machinery and 36 tests — with **zero allowlist
additions**. Measured identical at 1440, 900 and 390.

**UFC's record splits three ways.** Contender Series bouts go the distance
43.6% of the time against 58.0% on a numbered card, so 6 categories became 18,
each with its own hundred.

## 4. The five findings worth your time

**One. 68 of 321 live cards named opposite sides.** A card read *"Miami covers
+7.5"* beside *"chance Miami does not cover"* — the percentage attached to the
wrong claim. Two fixes, each right alone, arrived sessions apart and combined
into a double flip. **Every guard passed it**: "one door for the side" because
both functions asked the same door and got the same *name*; "the side in prose"
because both sentences were grammatical. The new guard checks that the two
**agree**, which is the only thing neither could be asked alone. Found by
rendering a layout that puts them four lines apart.

**Two. Twelve tables and 311,655 rows had foreign keys pointing at a table that
did not exist.** Residue from widening the sport CHECK on `games`: SQLite
repointed every referencing FK to follow the rename and never pointed them
back. **Every read worked. The suite was green. Five sports rendered.**
`PRAGMA foreign_key_check` was reporting violations the whole time and nothing
was asking it. It surfaced only when the UFC fetcher became the first thing in
hours to INSERT. Repaired with the predictions fingerprint byte-identical, and
now in the gate.

**Three. A total asked at your own rung is a coin flip by construction.**
Measured in two sports: NBA +0.0010, NFL +0.0016. Books set totals to be coin
flips; we set ours the same way because LAW 1 forbids us seeing theirs, and the
value in a totals market is disagreeing with somebody else's number. **This is
a property of the construction, not of either model.**

**Four. The roster's volume column is unreachable as written.** It counts
qualifying subjects, not questions this project asks: a 25-a-day cap and a 70%
floor sit between. Measured on the record — **10 MLB prop predictions a day,
two of four declared markets writing nothing at all.** "0.4 slates to gate"
means *270 subjects would qualify*, not *a hundred settled within a day*.

**Five. A declaration disagreed with a hardcoded list four times in one
session** — the prop-market tuple, the MLB batting loop, four test counts, and
the market tabs. Each was silent: a market with a category, a gate, a ladder
and a fitted model that **never gets a question** looks exactly like a market
nobody has settled yet.

## 5. Where the gate stands

- **966 tests, 0 skips, 0 failures.**
- **168/168 plantings** — nineteen new across the session.
- `verify.py`: **35 rows PASS, none FAIL.**
- **54 commits, every one pushed and verified against the remote.**
- No prediction row rewritten, re-dated or deleted.

## 6. What is PARTIAL, and what needs you

**The batter-strikeouts walk-forward was still running when this was written.**
The market is declared, laddered, fitted (`RateFit`, n=118,451, Poisson,
converged, nothing dropped or constant) and proved end to end. Its
out-of-sample number is the one thing missing, and it is a measurement rather
than a build step — 118,000 rows through a pure-Python IRLS takes about an
hour. **Nothing claims an edge for it in the meantime.**

**Two deviations from the cards brief**, both recorded where they were made:

- **`--faint: #5F6975` fails WCAG AA at 3.17:1 on a card**, measured by this
  project's own tool. That token draws every sample size and there is a dated
  ruling that an unreadable N violates LAW 4. It is used as `--faintest`, and
  `--faint` is a lighter tone. Worst pair now 5.54:1.
- **Manrope is not self-hosted and cannot be** — no font binary in the repo,
  and a CDN link would put a network dependency in a local-first app a test
  already forbids.

**Two decisions that are yours:**

1. **Game markets carry no confidence floor**, which is right for a moneyline
   and produces ~15 near-coin-flip total cards a night. Whether a floor should
   exist for a market that *structurally* cannot clear it is a ruling, not a
   defect.
2. **The suppressed spread pairs.** They stay for one version by the brief's
   own instruction. The moneylines now show the same two factors behaving
   normally in two sports, which is evidence the suppression is the spread's
   own problem.

**Carried forward:** the 390px compact-row truncation is FIXED; the UFC market
comparison is DECLINED on evidence; `predict:ufc`, `final:ufc` and capture are
still not in the OS scheduler; the ntfy topic and Anthropic key still want
rotating; `verify.py` no longer completes inside one ten-minute invocation; and
one flaky test is named in STEP 4's close-out §8.

**The reasoning pass stayed dark throughout, as instructed. `.env` was neither
read nor written.**

## 7. The push

One notification, failure channel, counts only — no probability, no line, no
pick. Both channels delivered (`HTTP 200`).

> Overnight run complete. 5 steps: UFC events, the cards UI, and 5 new markets
> across NBA, NFL and MLB. 29 markets declared in 5 sports. 966 tests, 168
> plantings, 0 failures. 6 close-outs await your verdicts, and 2 corrections to
> MARKET_ROSTER need reading.

## 8. Operator's verdicts

**Strongest thing:**

**Weakest thing:**

**What to do next:**
