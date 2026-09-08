# Close-out — GRIDIRON_NIGHT_AUDIT (2026-09-08, overnight)

Against `docs/briefs/2026-09-08-night-audit.md`. Every measurement below was
taken through `db.read_the_live_record(why)` — a query-only handle — or on a
scratch copy of the record made through the SQLite backup API. **Nothing in
this run wrote to `var/gridiron.db`.**

## Deviations from the brief, first

1. **"Turns red" was not built as red.** Item 1 asks that the day strip turn
   red past a declared threshold. The colour law's guard
   (`audit.colour_law_faults`, ruled under CARD_FACE) admits `--loss` only
   under a selector that names an outcome — `.loss`, `.neg`, `.down` — and a
   job that stopped is not an outcome. Widening a ruled guard is a ruling.
   The stale state ships **bold in the warning ink with the threshold in its
   own words** ("venue read 31h ago, past 30h"; "reasoning pass has never
   run"), the planting proves a stale job cannot be shown as fresh, and the
   choice is in the morning table. Found by the plantings: 244 of 245 caught
   until the colour was taken out.
2. **The live poller was not registered.** It has no scheduled task (item 1).
   Registering one is a machine change made while the operator sleeps and the
   remit does not cover it; two readings are given and none chosen.
3. **The LLM was not exercised on scratch.** A reasoning pass costs money;
   the ledger answers the question instead (item 3).

## Morning table

| item | verdict | evidence | what changed | what needs the operator |
|---|---|---|---|---|
| **First: tonight's open items** | DONE | Retraction as an append-only row (`picks_retracted`, `picks_taken_no_delete`, both planted); the scratch guard (`db.LiveRecordTouched`, `read_the_live_record`, three plantings, 26 call sites converted); the college-basketball package printed beside its tag — `cbb`, correct — and `SAME_GAME_SERIES` declared. Commit **`1af3f74`**, pushed; bundle rebuilt from it and stamped `1af3f74`, `Gridiron.exe` SHA-256 `c4eaa413003f7ca61c0c58f8f03262cc57136a76f36ebed32895809ea53c86cd`. | — | nothing |
| **1. Silent failure** | DONE, one defect fixed, one (c) | Last ran / last succeeded per job below. The notices bar THREE_STATES removed was the only route from `task_runs` to the first screen. The day strip now prints the age of the last successful daily run, venue read and reasoning pass; `config.FRESHNESS_HOURS` (36 / 30 / 36, dated) marks each stale; `audit.check_the_strip_shows_a_dead_job` + `plant_a_dead_job_the_strip_calls_fresh`. | `views.freshness`, `language.freshness_words`, strip markup/JS/CSS, scan, planting, tests | **(c) the live poller is unscheduled; (c) red vs the colour law** |
| **2. Sleep** | REPORTED | Balanced plan; **sleeps after 15 min idle on AC**; hibernate off; wake timers allowed; **no `Gridiron-*` task has WakeToRun**; all `StartWhenAvailable`; catch-up at logon only. | nothing, by ruling | **set the power plan — below** |
| **3. Pipeline on scratch** | DONE; one (c) | one row per step below; 966 MB copy, `quick_check` ok; the live file opened only by the backup read | nothing | (c) the closer sits below near-start's early return |
| **4. Guards** | DONE, three gaps closed | 243/243 before tonight's additions; every list read against the tree. Would have passed and no longer do: a `urllib` POST at the venue (no verb in it — `Request(url, data=…)`), the COMBOS identifiers on a label, four credential spellings, two ledger column shapes. Each grepped first: 0 hits. | `order_path_faults` reads the market module's syntax tree; `plant_a_urllib_post_at_the_venue`; list additions; tests | nothing |
| **5. Waste** | REPORTED; no class-(a) defect | Seven-day counts below. Poller: **0 requests, because it never runs.** One Picks render: **694 statements for 107 cards** — `priceable()` re-runs the coverage measurement (a full `venue_quotes` scan) and `clv_report` per card (120× / 60×); 0.3 s today. On scratch: `refresh` made 2 requests, repeated none; `near-start`, `capture` 0. | nothing | (c) per-card coverage: declare once-per-slate, or leave |
| **6. Dead weight** | DONE | `heroPool`, `HERO_STEPS`, `shortNotice`: zero callers, removed; `.notices*` (5 rules) and `.view-menu`: classes nothing builds, removed; the edge line repeated its label on both card kinds ("EDGE AFTER FEES +9.0¢ after fees") — a sibling of "Payspays" — fixed in `edge_line_words`. No migration splits on semicolons. `test_hero_floor.py` kept empty as the retirement marker. | removals + `test_night_audit.py` proving absence and clean scans | nothing |
| **7. Both widths** | DONE, DOM-verified; screenshots partial | below | nothing | nothing |
| **8. The record** | PRODUCED | below | nothing | read it on the 21st |
| **9. READINESS / FOLLOWUPS** | DONE | READINESS carries the three dates; FOLLOWUPS triaged by class, six rulings listed | docs | six rulings |
| defect: edge line repeats its label | FIXED | see 6 | `language.edge_line_words` | — |
| defect: dead job invisible on the first screen | FIXED | see 1 | strip | — |
| defect: a `urllib` POST would pass the order-path scan | FIXED | see 4 | scan + planting | — |
| defect: dead code and styles from removed pages | FIXED | see 6 | removals | — |

## Item 1 — last ran / last succeeded, per job (UTC, read at 09:00Z)

| job | last started | last ok/noop | last failed/missed | differ? | note |
|---|---|---|---|---|---|
| refresh | 09-08 09:00 | 09-08 09:00 | never | no | alive, 51 runs |
| resolve | 09-08 05:20 | 09-08 05:20 | 09-07 17:20 missed | no | alive, 66 runs |
| near-start | 09-08 09:05 | 09-08 09:05 | never | no | alive, 51 runs |
| capture | 09-08 07:15 | 09-08 07:15 | 09-03 22:42 | no | alive |
| predict:mlb | 09-07 20:48 | 09-07 09:06 | 09-07 20:48 | **yes** | the later runs are `SlateAlreadyAnswered` — correct refusals |
| predict:cfb | 09-07 17:12 | 09-07 16:00 | 09-07 17:12 | **yes** | same |
| predict:ufc | 09-07 18:00 | 09-06 18:00 | 09-07 18:00 | **yes** | same; the LLM half wrote 25 h after the statistical half (the dead key) |
| predict:nfl | 09-07 17:12 | 09-07 17:12 noop | never | no | weekly; the first real slate is 9 Sep |
| predict:nba | 09-07 18:00 | 09-07 18:00 noop | never | no | off-season |
| recalibrate | 09-07 13:00 | 09-07 13:00 | 08-31 | no | weekly |
| catch-up | 09-07 17:12 | **never** | 09-07 17:12 | **yes** | both runs "failed" because a member predict correctly refused an answered slate (c) |
| **live** | **09-02 03:02** | 09-02 03:02 | never | no | **no scheduled task exists**; 0 games marked `in` since 2 Sep |
| final:* | 09-07 | 09-07 | never | no | alive |

**The live poller (c).** No `Gridiron-Live` in Task Scheduler or in the
installer's `$TaskNames`; the installer's docstring never promised one.
THREE_STATES's close-out flagged "the poller has not run against a live
baseball slate since these cards existed" and nobody ruled. Reading (i):
register it on a short repetition — it makes zero requests when nothing is
on, by test. Reading (ii): declare Live a read of `refresh` and say so on the
tab. Not chosen.

## Item 2 — sleep

`powercfg`: plan **Balanced**; standby after **900 s on AC**; hibernate 0;
wake timers **Enabled**; chassis type 3, no battery. Every `Gridiron-*` task:
`WakeToRun False`, `StartWhenAvailable True`, 2 h limit. `Gridiron-Serve`
restarts at logon only.

**12–20 September asleep:** nothing fires while asleep. On wake each task runs
once, not the runs it missed: `refresh`/`resolve` catch up; `near-start` takes
one look; each daily `predict` runs once and records MISSED if its slate has
started (never forecast late, by design); `catch-up` only at logon; the phone
loses the app (the server is a task). The record is intact and every gap is a
MISSED row.

**What to set:** `powercfg /change standby-timeout-ac 0` — never sleep on
AC. Or, if it must sleep, give each `Gridiron-*` task `-WakeToRun`
(`Set-ScheduledTask … -Settings (New-ScheduledTaskSettingsSet -WakeToRun)`);
wake timers are already allowed. The first is what an appliance wants.

## Item 3 — the pipeline on scratch (02:40 PT)

| step | verdict | why |
|---|---|---|
| key from `.env`, not the environment | **pass** | `.env` holds it; the process environment does not; `setting()` resolves it — and gives the environment precedence if both exist (recorded in FOLLOWUPS) |
| ticker resolution, every sport with a game today | **pass / not exercisable** | MLB **15 of 15**; **no doubleheader today**, so the first-pitch stem is exercised only by its unit test; NFL/NBA/CFB have no game today; **UFC 0 of 5**, a declared absence — `SERIES` has no venue series for UFC (`sources.py` says so) |
| refresh | **pass** | `ok — refreshed 5 sports` |
| near-start window | **not exercisable at 02:40 PT** | `noop — no game starts within the next 2 hours`; 51 real firings on the live record, 32 on the 7th with 1,676 quote rows |
| claims pregame only | **pass** | 0 claims after kickoff since 8 Sep; the 17 that exist (19:41Z on the 7th) predate the `quote_after_first_pitch` guard by fifty minutes and stand under LAW 3 |
| the side map | **pass** | every claim is from the fixed proposition: `home/home_win` 86, `home/home_margin` 30, `over/total` 14 |
| closes recorded | **(c)** | 0 closed on scratch: the closer runs only when a game is within two hours; two finished games' recommendations stay open until then. The close *value* is the last pre-kickoff claim either way. Reading (i): call it before the early return; (ii): leave it |
| resolve | **pass** | `noop`; the 05:20Z run had already settled both finals |
| predict:mlb, statistical | **pass, as a refusal** | `SlateAlreadyAnswered: slate 165 already has 82 forecasts` |
| the LLM reaches game markets only | **pass** | 0 LLM prop rows since the roster guard (6 Sep); the 8 that exist are from 2 Sep |
| both forecasters on every run, View menu gone | **pass with a finding** | 7 Sep: cfb 1/1, mlb 58 LLM / 104 statistical. UFC's LLM half wrote 25 h after the statistical half, only because `final:ufc` fired twice — the dead-key day, which the strip now marks |

## Item 5 — waste, seven days (distinct URLs from `http_cache`)

| day | espn | weather | kalshi | mlb-statsapi |
|---|---|---|---|---|
| 09-01 | 8233 | 1978 | — | 2 |
| 09-02 | 122 | — | — | 5 |
| 09-03 | 1367 | 11 | — | 1 |
| 09-04 | 10749 | 14 | — | — |
| 09-05 | 2761 | 85 | — | 1 |
| 09-06 | 223 | 45 | 31 | 1 |
| 09-07 | 108 | 12 | 255 | — |
| 09-08 to 09Z | 4651 | 1 | 3 | 1036 |

LLM: 178 reasoning calls, one key probe. Repeats inside a run (scratch,
`urlopen` counted): `refresh` 2 requests, 0 repeated; `near-start` 0;
`capture` 0. Per-card queries: 694 statements per render at 107 cards, the
same `venue_quotes` scan 120×, `teams` 108×, `clv_report` 60×.

## Item 7 — both widths

The pane was minimized for most of the night, so most screenshot captures
timed out; every route was measured in the DOM instead, and the two captures
that succeeded are in the session transcript.

| route | 1100 | 390 |
|---|---|---|
| Upcoming | view visible, `scrollWidth ≤ viewport`; pulse line under the counts in one line; **screenshot captured** | no overflow; pulse wraps to two lines at x=14; **screenshot captured** (with Live selected) |
| Live | "Nothing is being played · first game starts …", no overflow | same |
| Results | `view-results` visible, no document overflow; a 948 px table scrolls inside its own container | same |
| Settings | `view-settings` visible, ten sections, no overflow | widest element 376 px; **0 tap targets under 44 px** |

Colour: the stale mark's computed colour is the warning ink and not `--loss`
(checked by adding the class to a fresh span on the scratch page and reading
`getComputedStyle`).

## Item 8 — the record, for the 21st

| sport | market | settled | with price | CLV pairs | settles/day | days to 100 | correction |
|---|---|---|---|---|---|---|---|
| mlb | moneyline | 155 | 97 | 0 | 18.6 | at gate | fitted, not applied (29 of 40 check rows) |
| mlb | spread | 97 | 76 | 0 | 13.9 | ~0 | fitted, not applied (17 of 40) |
| mlb | total | 97 | 76 | 0 | 13.9 | ~0 | fitted, not applied (17 of 40) |
| mlb | batter_home_runs | 36 | 28 | 0 | 4.3 | 15 | retired 5 Sep |
| mlb | batter_hits | 25 | 20 | 0 | 3.3 | 23 | fitted, not applied |
| mlb | batter_strikeouts | 8 | 8 | 0 | 1.1 | 80 | fitted, not applied |
| mlb | pitcher_strikeouts | 6 | 6 | 0 | 0.9 | 110 | fitted, not applied |
| cfb | moneyline | 137 | 99 | 0 | 19.6 | at gate | fitted, not applied (28 of 40) |
| cfb | spread | 134 | 133 | 0 | 19.1 | at gate | fitted, not applied (27 of 40) |
| cfb | total | 130 | 130 | 0 | 18.6 | at gate | fitted, not applied (26 of 40) |
| ufc | distance / moneyline / rounds | 20 each | 20 / 13 / 20 | 0 | 2.9 | 28 | begin at 50 |
| nfl | all | 0 | 0 | 0 | 0 | first slate 9 Sep | never fitted |
| nba | all | 0 | 0 | 0 | 0 | season 20 Oct | never fitted |

**CLV pairs are zero everywhere**: eight recommendations exist, all baseball
from the 7th; the first two games went final overnight; the closer runs inside
`near-start` and will write the first closes at the next window.

## Item 9 — triage

**Fix now (a), done tonight:** the four defects in the table. **Rule needed
(c):** the live poller; red vs the colour law; per-card coverage; the closer
below the early return; `catch-up` calling a refusal a failure; the terminal
retraction. **After the 21st:** the tailnet leg; `LIVE_TTL`; the HTTP cache in
scratch copies; the slow prop fits; the 25 pre-fix MLB rows; the synthetic
package row; rare factors; the NFL team-name gaps; per-market factor-set
versions.

## Evidence of the run itself

`tests/test_night_audit.py`; the full planting set; the gate on the committed
tree. The bundle is rebuilt from this commit and its hashes are in the morning
message and the READINESS run log.
