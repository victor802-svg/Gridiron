# Brief — rulings on the overnight close-out

Received 2026-09-04. Saved before execution, per the unattended contract.

---

Rulings on the overnight close-out:

1. TOTALS AND SPREADS BECOME DISTRIBUTIONAL (GRIDIRON_18 Session E,
   its own session, probe-and-design first). The blind object stops
   being a yes/no at a self-chosen rung and becomes the model's
   FORECAST DISTRIBUTION of the total or margin (mean + measured
   spread), written before any line exists. Once the market line is
   snapshotted, P(over the market's line) is READ OFF that stored
   distribution — a deterministic read-out, not a new forecast, so
   Law 1 holds exactly. This ends "asked at your own rung", ends the
   asked_line dependency entirely, grades the model at the question
   the market actually asks, and likely explains the spread-pair
   suppression. Design doc first (blind object, storage, resolution
   at the market line, calibration of a distribution, what the card
   shows when no line exists); build only after the doc.
2. Until then, totals cards carry one line in words: "totals asked
   this way have been a coin flip so far (NBA +0.001, NFL +0.002 in
   walk-forward) — shown for the record." The hero never selects a
   market whose method is flagged this way.
3. Suppressed spread pairs stay one version, as ruled; Session E is
   their test.
4. --faint deviation accepted (an unreadable N violates Law 4).
   Manrope: vendor the OFL woff2 files into the repo with the
   licence beside them — that is not the kind of binary the
   no-committing instinct protects against.
5. UFC "cards stop reading no line" DECLINED — read the reason back
   to me in one line before ruling.

---

## How this brief is read

- **Ruling 1 is NOT built here.** It names its own session (Session E),
  and its first deliverable is a design doc, not code. What this session
  owes it is a dated, declared record of the ruling so Session E starts
  from it rather than from memory.
- **Ruling 2 is built here.** The words, the flag, and the hero refusal.
- **Ruling 3 is recorded here.** No code changes; the existing
  `JOINTLY_READ_FACTORS` scope stands one more version.
- **Ruling 4 is built here.** Vendor the woff2 files and the OFL text.
- **Ruling 5 is an operator-only decision.** One line back, then stop.
  Nothing about the UFC market comparison is touched until it rules.
