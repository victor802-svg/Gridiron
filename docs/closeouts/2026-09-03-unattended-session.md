# Final close-out — the three-item unattended session

One line per item, and the per-item close-outs carry the detail.

---

## 1. The three items

| item | verdict | close-out |
|---|---|---|
| **ITEM 1 — UFC, declared** | **DONE** (one PARTIAL inside) | `docs/closeouts/2026-09-03-ufc.md` |
| **ITEM 2 — count markets** | **DONE** (one PENDING inside) | `docs/closeouts/2026-09-03-count-markets.md` |
| **ITEM 3 — adjusted form** | **DONE** | `docs/closeouts/2026-09-03-adjusted-form.md` |

Nothing was BLOCKED. Nothing was NOT REACHED.

## 2. What each one actually did

**ITEM 1** declared UFC as the fifth sport — six SQL CHECKs widened through the
verified rebuild path, all 21,527 games and 519 predictions restored, the
predictions fingerprint byte-identical before and after. Seven factors, three
markets, void rules written before the first prediction, 41 forecasts written
blind on the 2026-09-05 card, five plantings. **PARTIAL:** no UFC fetcher
exists in the market module, so no UFC card shows a market comparison.

**ITEM 2** moved five count markets from a logistic to a Poisson or negative
binomial rate — and found that the wiring which was supposed to deliver that
had never worked at all. The walk-forward that decides it: passing TDs 7.79 →
2.39 points of weighted gap, receptions 5.50 → 3.89, so it ships. **PENDING:**
two of five markets are fitted, one landed during ITEM 3, two remain (~50
minutes each through a pure-Python IRLS on 139,000 rows).

**ITEM 3** gave the NBA an opponent-adjusted rating, found that the NFL already
had one, and then found — in the bookkeeping the brief asked for — that the
adjusted and raw form factors mutually suppress. The card was about to tell
readers those two factors disagreed. They do not; the model uses their
difference. Repaired at the one door.

## 3. The three things worth your attention

**One. Two silent failures, both mine, both caught by writing the guard rather
than by the guard.** The count-market wiring never forwarded `with_counts`, so
every "rate" market was still a logistic. My first fix quietly fell back to the
logistic when an adapter could not supply counts — which would have shipped a
market claiming a form it did not have, with nothing anywhere saying so. It is
now a build error. **A silent fallback is worse than the crash it replaces.**

**Two. A sentence can be arithmetically derived and still false.** The NBA card
would have read "Pulling the other way, and not by a little: how the two clubs
have been playing lately." Every guard passed it — direction off the
contributions, ordering off the magnitudes, phrase off the declaration — and it
was false, because the model was using a difference and that factor was
carrying half of it. This is the failure mode this project's guards are least
equipped to see, and it is worth more than the features around it.

**Three. `language.rate_line` was composed and thrown away for an hour.** It
sat on the payload with no renderer. The orphan scan was satisfied, because
something called it. **A payload field with no renderer is a guard that passes
and a feature that does not exist** — and only rendering the card and looking
found it.

## 4. Where the record stands

- **Five sports declared.** 974 tests, 0 skips, 0 failures. **152/152**
  plantings — eight new across the three items.
- `verify.py`: **34 rows PASS, none FAIL**, steps 2–4 PASS.
- Nine commits, every one pushed and verified against the remote.
- No prediction row rewritten, re-dated or deleted.

## 5. Carried forward

| what | where |
|---|---|
| The UFC market comparison (ITEM 1's PARTIAL) | now ITEM 4's E4 |
| Two MLB count fits still running | ITEM 2 §10.1 |
| Compact rows truncate their titles at 390px | `docs/FOLLOWUPS.md` |
| `verify.py` no longer completes inside one ten-minute invocation | ITEM 2 §8 |
| Rotate the ntfy topic and the Anthropic API key | earlier close-outs |
| `predict:ufc`, `final:ufc` and capture not in the OS scheduler | ITEM 1 §5.2 |

**The reasoning pass stayed dark for the whole session**, as instructed. `.env`
was not read and not touched; the render servers were given their own token.

## 6. The push

One notification, through the failure channel, counts only — no probability, no
line, no pick. Both channels delivered (`HTTP 200`).

> 3 items run. UFC declared and forecasting. Count markets on the rate form:
> 2 of 5 fitted, 3 still fitting. NBA opponent adjustment declared. 974 tests,
> 152 plantings, 0 failures. 3 close-outs await your verdicts.

## 7. Operator's verdicts

**Strongest thing:**

**Weakest thing:**

**What to do next:**
