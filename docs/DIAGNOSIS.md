# D1 - diagnosis: why the disagreements lose

**Read-only analysis. No model and no factor was changed to produce it.**

---

## The finding under investigation

Across 544 resolved spread predictions carrying a market comparison:

| | N | Hit rate | 95% interval |
|---|---:|---:|---|
| Model more confident than the market (>5 pts) | 207 | 55.6% | 48.7-62.2% |
| Market more confident | 146 | 71.2% | 63.4-78.0% |

The model is at its worst exactly where it would be acted on. That is what this document sets out to explain, and mostly fails to.

---

## Pre-registration

The hypotheses, every slice, and the significance threshold were written into `tools/diagnose.py` **before any outcome was examined**, and are frozen at the top of that file. This matters more than usual here: an analysis that slices until something appears is the failure LAW 2 exists to prevent, performed on the record instead of on the training data.

- **29 pre-registered comparisons.** Bonferroni-adjusted threshold: **p < 0.00172** (0.05 / 29). At an unadjusted p<0.05, about 1.5 of these would clear on noise alone.
- **Slices under n=30 render as INSUFFICIENT SAMPLE**, never as findings, however extreme they look.
- Intervals are Wilson score intervals. p-values are exact two-sided binomial tests against the 55.6% baseline.

**H1a.** The model disagrees most when it is MISSING information the market has — late injury news, lineup changes — which reaches the line before kickoff but never reaches us.

> *Test:* Correlate disagreement size against the CLOSING line with line movement between the opening and closing number. If our disagreements were smaller against the opener, we are fighting information that arrived after it.

**H1b.** SUBSTITUTE FOR H1a, declared at the data-availability check below and before any outcome was examined. The same underlying claim, tested on the missingness we can actually observe: disagreements lose more often when more of the model's own factors were unavailable for that game.

> *Test:* Split the disagreements by how many factors were defaulted (the `missing` list stored on each prediction) and compare hit rates. Also split by whether an injury report existed for the game at all.

**H2.** The losses concentrate in a slice rather than being spread evenly: home dogs, big favourites, divisional games, or early season when the season-to-date factors are thin.

> *Test:* Hit rate within each pre-registered slice below, with N, a Wilson interval, and a Bonferroni-adjusted binomial test against the overall disagreement hit rate.

**H3.** One factor is dragging: it pushes the model away from the market and is wrong when it does.

> *Test:* For each factor, the mean stored log-odds contribution among LOST disagreements versus WON ones, with N and the same adjusted threshold.

**H4.** The LLM and statistical paths disagree with the market differently, and the aggregate hides one of them.

> *Test:* Split the disagreements by `predictor` and compare.

---

## Verdicts

| Hypothesis | Verdict |
|---|---|
| H1a | **NOT TESTABLE** |
| H1b | **NOT SUPPORTED** |
| H2 | **NOT SUPPORTED** |
| H3 | **NOT SUPPORTED** |
| H4 | **INSUFFICIENT SAMPLE** |

---

## H1a - missing information the market has

### Verdict: NOT TESTABLE

No free source publishes opening lines for the seasons in this record (2024-2025). Every market number Gridiron holds is a closing number, so line movement cannot be computed at all - not poorly, not approximately, not at all.

Sources checked for an opening line covering these seasons:

| Source | What it actually has |
|---|---|
| `nflverse-data schedules/games.csv` | carries spread_line and total_line only. Those are CLOSING numbers; there is no opening column. |
| `nfldata/data/initial_lines.csv` | 1,088 rows, season 2021 only. Does not cover 2024 or 2025. |
| `nfldata/data/sc_lines.csv` | 4,092 rows, seasons 2013-2020. Does not cover 2024 or 2025. |
| `nfldata/data/closing_lines.csv` | closing numbers broken out by book. Closing again, not opening. |

H1b was declared as the substitute at this point, before any outcome was examined. It tests the same underlying claim - that the model disagrees hardest where it knows least - using the missingness the record does contain.

Recording this as untestable rather than substituting a proxy is the same rule the registry applies to `public_bet_pct`. A movement measure built from something that is not movement would be a finding about that something else, wearing H1a's label.

## H1b - does the model lose where its own inputs were missing?

### Verdict: NOT SUPPORTED

Hit rates across missingness slices span 4.9 points and no slice differs from the 55.6% baseline at the adjusted threshold. Missing factors do not explain the losses.

| Slice | N | Won | Hit rate | 95% interval | p vs baseline |
|---|---:|---:|---:|---|---:|
| 0 factors defaulted | 69 | 35 | 50.7% | 39.2-62.2% | 0.4678 |
| 1-2 factors defaulted | 124 | 69 | 55.6% | 46.9-64.1% | 1.0000 |
| 3+ factors defaulted | 14 | 11 | - | - | *insufficient (<30)* |
| injury report present | 207 | 115 | 55.6% | 48.7-62.2% | 1.0000 |
| injury report absent | 0 | 0 | - | - | *insufficient (<30)* |

Read this against what the factor report already showed: `precipitation` was defaulted in 66% of predictions, and `short_week_diff`'s input is structurally zero. Those are real instrument faults - but if missingness explained the disagreement losses, the slices above would separate, and they do not.

## H2 - do the losses concentrate in a slice?

### Verdict: NOT SUPPORTED

23 slices reached n=30 and none differs from the 55.6% baseline at the Bonferroni-adjusted threshold of p<0.00172. The losses are spread across the record, not concentrated anywhere the pre-registered list looked.

**rung asked**

| Slice | N | Won | Hit rate | 95% interval | p vs baseline |
|---|---:|---:|---:|---|---:|
| home -7.5 | 64 | 39 | 60.9% | 48.7-71.9% | 0.4508 |
| home -3.5 | 54 | 33 | 61.1% | 47.8-73.0% | 0.4939 |
| home +0.5 | 35 | 15 | 42.9% | 28.0-59.1% | 0.1727 |
| home +3.5 | 54 | 28 | 51.9% | 38.9-64.6% | 0.5871 |

**market view of the home side**

| Slice | N | Won | Hit rate | 95% interval | p vs baseline |
|---|---:|---:|---:|---|---:|
| home favourite | 140 | 81 | 57.9% | 49.6-65.7% | 0.6106 |
| home underdog | 67 | 34 | 50.7% | 39.1-62.3% | 0.4617 |
| near pick'em (|line| <= 2.5) | 62 | 37 | 59.7% | 47.3-71.0% | 0.5264 |
| big favourite (|line| >= 7) | 32 | 16 | 50.0% | 33.6-66.4% | 0.5949 |

**game type**

| Slice | N | Won | Hit rate | 95% interval | p vs baseline |
|---|---:|---:|---:|---|---:|
| divisional | 64 | 36 | 56.2% | 44.1-67.7% | 1.0000 |
| non-divisional | 143 | 79 | 55.2% | 47.1-63.2% | 1.0000 |

**season stage**

| Slice | N | Won | Hit rate | 95% interval | p vs baseline |
|---|---:|---:|---:|---|---:|
| weeks 1-4 | 60 | 34 | 56.7% | 44.1-68.4% | 0.8973 |
| weeks 5-13 | 97 | 55 | 56.7% | 46.8-66.1% | 0.8389 |
| weeks 14-18 | 50 | 26 | 52.0% | 38.5-65.2% | 0.6702 |

**which side the model took**

| Slice | N | Won | Hit rate | 95% interval | p vs baseline |
|---|---:|---:|---:|---|---:|
| model says cover | 80 | 43 | 53.8% | 42.9-64.3% | 0.8221 |
| model says not_cover | 127 | 72 | 56.7% | 48.0-65.0% | 0.8584 |

**rating basis**

| Slice | N | Won | Hit rate | 95% interval | p vs baseline |
|---|---:|---:|---:|---|---:|
| in-season ratings | 174 | 92 | 52.9% | 45.5-60.1% | 0.4929 |
| prior-season fallback | 33 | 23 | 69.7% | 52.7-82.6% | 0.1162 |

**model confidence**

| Slice | N | Won | Hit rate | 95% interval | p vs baseline |
|---|---:|---:|---:|---|---:|
| 50-60% | 73 | 32 | 43.8% | 33.0-55.2% | 0.0458 |
| 60-70% | 68 | 39 | 57.4% | 45.5-68.4% | 0.8080 |
| 70-80% | 51 | 31 | 60.8% | 47.1-73.0% | 0.4840 |
| 80%+ | 15 | 13 | - | - | *insufficient (<30)* |

**size of disagreement**

| Slice | N | Won | Hit rate | 95% interval | p vs baseline |
|---|---:|---:|---:|---|---:|
| 5-10 points | 86 | 55 | 64.0% | 53.4-73.3% | 0.1290 |
| 10-20 points | 91 | 51 | 56.0% | 45.8-65.8% | 1.0000 |
| 20+ points | 30 | 9 | 30.0% | 16.7-47.9% | 0.0055 |

**The closest thing to a signal, and why it is not one**

The lowest p-value among all 23 sufficient slices is **20+ points**: 30.0% on n=30 (p=0.0055, 95% interval 16.7-47.9%).

It does **not** clear the adjusted threshold of p<0.00172, and it is not treated as a finding. Three reasons, all of which would still apply if it looked twice as strong:

1. 23 slices were tested. The smallest of 23 p-values being around 0.006 is roughly what pure noise produces; that is what the adjustment is for.
2. n=30 is at or near the n=30 floor, where a swing of three games moves the rate by ten points.
3. Acting on it would mean changing the model on the strength of a slice found by looking at slices, which is the exact procedure LAW 2 forbids on training data and which is no safer here.

If it is real, a forward season will show it again, and then it will be a hypothesis worth pre-registering rather than a number worth explaining away.

## H3 - is one factor dragging?

### Verdict: NOT SUPPORTED

No factor separates won from lost disagreements. The largest separation is asked_line (|t|=1.45, mean contribution -0.3709 when won vs -0.2466 when lost, n=115/92), which is inside the range 16 simultaneous comparisons produce by chance.

Mean stored log-odds contribution among won versus lost disagreements. A factor that dragged would push consistently harder on the losses. `|t|` is Welch's t as a ranking aid only - with this many factors compared at once it is not a licence to claim.

| Factor | N won / lost | Mean when won | Mean when lost | Difference | \|t\| |
|---|---|---:|---:|---:|---:|
| `asked_line` | 115 / 92 | -0.3709 | -0.2466 | -0.1243 | 1.45 |
| `home_field` | 115 / 92 | +0.1999 | +0.1834 | +0.0165 | 1.28 |
| `neutral_site` | 115 / 92 | -0.0017 | -0.0071 | +0.0054 | 1.18 |
| `timezone_shift` | 115 / 92 | +0.0015 | -0.0022 | +0.0036 | 1.16 |
| `recent_form_diff` | 115 / 92 | +0.0005 | -0.0246 | +0.0251 | 0.98 |
| `cold` | 115 / 92 | -0.0295 | -0.0204 | -0.0092 | 0.78 |
| `srs_diff` | 115 / 92 | +0.0165 | -0.0214 | +0.0379 | 0.75 |
| `qb_out_diff` | 115 / 92 | -0.0103 | -0.0028 | -0.0075 | 0.56 |
| `travel_kmiles` | 115 / 92 | -0.0023 | -0.0031 | +0.0007 | 0.35 |
| `rest_diff` | 115 / 92 | -0.0016 | -0.0025 | +0.0008 | 0.24 |
| `wind` | 115 / 92 | +0.0015 | +0.0016 | -0.0001 | 0.15 |
| `divisional` | 115 / 92 | -0.0194 | -0.0190 | -0.0005 | 0.12 |
| `pace_sum` | 115 / 92 | -0.0602 | -0.0596 | -0.0006 | 0.10 |
| `injury_out_diff` | 115 / 92 | +0.0053 | +0.0058 | -0.0005 | 0.05 |
| `precipitation` | 115 / 92 | +0.0000 | +0.0000 | +0.0000 | - |
| `short_week_diff` | 115 / 92 | +0.0000 | +0.0000 | +0.0000 | - |

## H4 - do the two forecasters disagree differently?

### Verdict: INSUFFICIENT SAMPLE

Only 1 of 2 forecasters reached n=30 (statistical: n=207, llm: n=0). The comparison cannot be made.

| Slice | N | Won | Hit rate | 95% interval | p vs baseline |
|---|---:|---:|---:|---|---:|
| statistical | 207 | 115 | 55.6% | 48.7-62.2% | 1.0000 |
| llm | 0 | 0 | - | - | *insufficient (<30)* |

The LLM path contributed **zero** predictions to this record. The backtest ran with the reasoning pass disabled, and the live runs degraded to statistical-only with the tag `llm_unavailable:no_api_key`. This hypothesis is not weakly supported and not weakly refuted - it is untested, and stays untested until the LLM path has a record of its own.

---

## Recommendations

**None of the pre-registered hypotheses is supported.**

The honest conclusion is the one the brief explicitly permitted: *the disagreements lose, and we do not know why yet.* The losses are not concentrated in any slice that was looked for; no factor separates the wins from the losses; the missingness we can measure does not track the failures; and the one hypothesis with a real mechanism behind it - that the market knows things we do not - cannot be tested without an opening-line source that does not exist for free.

Three things that do **not** follow:

1. **That the model should be tuned to disagree less.** Shrinking towards the market would improve every score on this page by making the model more market-like. That is the anchoring failure LAW 1 exists to prevent, reached by a different road, and it would destroy the only thing the project measures.
2. **That the factors are wrong.** 55.6% on n=207 has a 95% interval of 48.7-62.2%. That interval contains 'slightly worse than a coin' and 'roughly as good as the market'. The sample cannot separate those, and neither can this analysis.
3. **That nothing should be done.** Two instruments were found broken by the earlier factor report - not by this diagnosis - and repairing an instrument that never measured anything requires no hypothesis to justify it.

**The recommendations are therefore procedural, not corrective:**

1. **Repair the broken instruments and nothing else.** `short_week_diff` (input non-zero in 1 game of 544) and `precipitation` (no data in 66% of predictions) never measured anything. Fixing them is maintenance, not a response to a finding, and the registry rationales should say so plainly so a later reader does not mistake a repair for a discovery.
2. **Make missing data an explicit state.** A factor that could not be measured currently becomes its default and is merely *recorded* as missing. That is why 66% of `precipitation` values were indistinguishable from a real zero at fit time. Excluding an unmeasurable factor from that game's vector is a correctness fix independent of anything here.
3. **Do not re-ask this question until there is forward volume.** The subset is n=207 from a retrospective backtest whose factor set was chosen with knowledge of these seasons. Re-running this diagnosis on the same record after changing the model would be measuring the change against the data that motivated it.

---

## What this analysis cannot tell you

Every number here comes from a **retrospective backtest**, in a database marked `kind=backtest`. The predictions were made after the games were played, by a factor set chosen by someone who already knew how those seasons went in aggregate. The diagnosis inherits that limitation whole: it can say where the model failed in a record it was built alongside. It cannot say why the model will fail next season.

Generated by `tools/diagnose.py`. Seasons 2024-2025. 544 resolved spread predictions with a market comparison; 207 of them disagreements in the model's favour.