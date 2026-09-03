# Close-out — moving the graded forecast close to start

Brief: `docs/briefs/2026-09-02-model-timing.md`.

---

## 1. Close-out table

| phase | verdict | evidence |
|---|---|---|
| **First act** save the brief, commit | **DONE** | `7c32cbd`. |
| **First act** read CLAUDE.md, MENTOR.md, DIAGNOSIS.md | **DONE** | All three; MENTOR §4's "verify the brief's factual claims" is why §3 below exists. |
| **A1** probe first (`docs/TIMING_FEASIBILITY.md`) | **DONE — mostly negative** | `8429d8e`. Three sports out of four cannot be measured at all. |
| **A1** final pass per sport, dated constants | **DONE** | `config.FINAL_PASS`, one per sport, derived from `config.SPORTS`. |
| **A1** the final pass writes NEW rows, early rows stand | **DONE** | `pass_kind` joined the uniqueness key; 495 existing rows migrated to `early`, none rewritten. |
| **A1** standing = latest row BEFORE START | **DONE** | `calibration.resolved`; planted and proven to fail when removed. |
| **A1** blind structure unchanged | **DONE** | Same path, same blind window; planting: the market module imported from the late pass. |
| **A1** MISSED rule unchanged | **DONE** | `_run_final_pass` returns `missed` and writes nothing; the early row stands and says so. |
| **A1** times in Settings > When it runs | **DONE, as fenced** | Read-only with provenance, not editable — §5.2. |
| **A1** the passes actually fire on a clock | **PARTIAL — needs you** | Installable, not installed. §4. |
| **A2** early-vs-final record, gated at 50 pairs | **DONE** | `calibration.early_vs_final`; n=0 today, so it reports the count and no verdict. |
| **A3** Picks shows the standing row + early-view toggle | **DONE** | Rendered at 1400px and 390px; 0 questions appear twice. |
| **A3** Results carry a "final" / "early only" mark | **DONE** | `language.pass_mark`; all 148 settled rows read "early only", which is true. |
| **A3** Health lists the final-pass tasks | **DONE** | They appear automatically and currently read "has never run", which is also true. |
| **A4** four plantings | **DONE** | 132/132; the after-start guard proven to fail when its rule is disabled. |
| **A4** full suite, renders, verify.py | **DONE** | 939 tests, 0 skips; `verify.py` 4/4 EXIT=0. |
| **A2/A4** does forecasting later actually help? | **UNVERIFIABLE TODAY** | Needs 50 paired games. Nothing in the build assumes an answer. |

## 2. Deviations from the brief, stated first

1. **MLB's final pass is T-1h30m, not T-2h30m.** The brief said to choose the
   time from the measured lineup distribution, and the measurement disagrees
   with the brief's own number: of 39 real pre-game lineup captures, T-2h30m
   would have found a lineup on **18 (46%)** and T-1h30m on **33 (85%)**.
2. **The final pass fetches before predicting.** Not in the brief, and the rest
   of it is inert without this — §5.1.
3. **The times are fenced, not editable.** The brief put them in Settings; they
   are there, read-only, because three of the four are judgements and one is a
   measurement and a text box would erase that difference.
4. **`pass_kind` is a new column in the uniqueness key.** The brief did not
   specify a mechanism; the schema made "two passes" impossible without one.

## 3. The brief's factual claims, checked before building (MENTOR §4)

| claim | verdict |
|---|---|
| "NFL week 1 was written 12 days before kickoff" | **CONFIRMED, understated** — 11.7 to 16.8 days |
| "MLB predicts before lineups post" | **CONFIRMED** — 100% of moneyline and prop rows |
| "the lineup-slot factor came back absent on every game" | **NOT TRUE** |

**`mlb_batter_lineup_slot` is present on 44 of 44 and absent on none.** It was
never going to be absent: its registry rationale says it reads *"the batter's
average batting-order slot across his most recent five STARTS"* — a role
measure computed from history, deliberately independent of whether tonight's
card has posted.

**The premise survives; the example does not.** Asking early does cost the model
information, and the cost lands on the *starter* factors:
`mlb_starter_rolling_perf` absent on 23 of 88 (26.1%), `mlb_starter_rest_days`
on 12 of 88 (13.6%).

**And the brief understates its own case by omitting NBA**, whose median lead is
**1,325 hours — 55 days**. Those 47 forecasts were written nearly two months
before tip-off, before rosters settle and before any injury is known. NBA, not
NFL, is the worst offender the brief set out to fix.

## 4. What needs you

**The four final passes are built and registered, and nothing fires them.**
`tools/schedule_install.ps1` now offers them; until it is run, the Settings page
says plainly *"The scheduler has no task called Gridiron-Final-MLB. It has not
been installed on this machine."*

Installing four scheduled tasks changes the machine, and the precedent from
2026-09-02 is that installing a task is an operator ruling made through the
installer. **This session prepared it and did not run it.**

```powershell
powershell -ExecutionPolicy Bypass -File tools\schedule_install.ps1
```

Proposed times, on this machine's clock (UTC-7):

| task | at | what it rests on |
|---|---|---|
| Final-MLB | **14:30** | measured; 16:00 local is the biggest first-pitch cluster (2,382 games) |
| Final-NFL | 08:00 | not measured |
| Final-NBA | 15:00 | not measured; the league's published 5:30 ET report window |
| Final-CFB | 08:00 | not measured |

## 5. What I would put in front of you

### 5.1 A later prediction alone would have changed nothing

`_run_predict` **reads stored rows and does not fetch.** A pass ninety minutes
before first pitch reads whatever the last `refresh` left behind; if that ran
six hours ago, the lineup is not there however long ago MLB posted it.

The 39-game sample is the illustration: those lineups entered our database at
17:00 and 21:00 UTC **because that is when we looked**. The brief does not ask
for a fetch, and without one the whole mechanism would have shipped, run on
schedule, reported success, and improved nothing — the exact shape of the
`refresh` failure recorded in `tasks.py` where every task was individually
correct and the record never moved.

The final pass now fetches its own sport first. A fetch failure does not cancel
the forecast; it is recorded on the run, so a pattern shows up as itself rather
than as a late pass that mysteriously never beats the early one.

### 5.2 Three of the four times are not measured, and the page says so

Only MLB's rests on data. For the others the data does not exist:

- **NFL** — the `injuries` table has **no timestamp column at all**. 55,554
  rows, not one of them dated.
- **CFB** — no college injury or depth-chart table exists.
- **NBA** — `nba_injuries` holds about 75 rows.

"(not measured)" appears **in the value** on the settings page, not in a
footnote, because a reader scanning a settings page reads values and skips
notes. One column on the NFL injuries table would make that sport measurable
within a week of games; it is in FOLLOWUPS.

### 5.3 A daily MLB pass cannot serve a 7.5-hour card

A baseball night spreads **7.47 hours** median from first pitch to last. At
14:30 local the afternoon games have been under way for four hours, so the final
pass correctly writes nothing for them and their early forecast stands, labelled
as the only one they got. Roughly the 10:00-local cluster — **1,101 games** in
the record — is outside its reach.

Fixing it properly means a per-game trigger rather than a daily one. That is a
bigger change than this brief asked for and is not smuggled in here.

### 5.4 Bugs I introduced, and how each was caught

| bug | caught by |
|---|---|
| The early-view note said *"a later forecast stands in its place"* on **every** early row, in a record containing no final rows at all | **by looking** — a harness gap, in FOLLOWUPS |
| My set of ids shadowed `superseded`, already an integer count in the same function | by looking |
| An installer comment claimed two MLB passes when I had registered one, at a time (17:30) that is *after* most first pitches | by looking |
| `early_view_note` written before its call site | **the orphan guard**, within a minute |
| Plantings deleted their own rows | **LAW 3's append-only trigger**, by name |
| A dedupe check that no longer matched the index it stood in for | **the UNIQUE constraint**, as an IntegrityError |

Three of six were caught by looking rather than by a test. That is the harness
gap worth naming: **every one of them was a claim in prose that no test
checked** — a sentence about supersession, a comment about two tasks, a note
about a time.

### 5.5 The question this cannot answer yet

**Whether forecasting later is better is unmeasured and unassumed.** A later
forecast could be a worse one: more news is not automatically more signal.
`early_vs_final` is gated at 50 paired games and today reports *"No game yet has
both an early and a later forecast."* Nothing in the code concludes anything,
and the number decides on its date.

## 6. What is measurably true now

- Suite **939 tests, 0 skips**, EXIT=0; `verify.py` **4/4**; **132/132**
  plantings (four new).
- A real early pass and a real final pass over one MLB slate, run on a **copy**
  of the record: 37 rows each, and Picks showed **37 cards with zero questions
  appearing twice**.
- Rendered at 1400px and 390px, both views, no page errors.
- 495 existing predictions migrated to `pass_kind='early'`; none rewritten.

## 7. Operator's verdicts

**Strongest thing:**

**Weakest thing:**

**What to do next:**
