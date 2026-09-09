# Close-out — GRIDIRON_NIGHT_AUDIT (2026-09-08, overnight)

Against `docs/briefs/2026-09-08-night-audit.md`. Every measurement below was
taken through `db.read_the_live_record(why)` — a query-only handle — or on a
scratch copy of the record made through the SQLite backup API. **Nothing in
this run wrote to `var/gridiron.db`.**

## Deviations from the brief, first

1. **"Turns red" was not built as red — and the operator ruled the same day
   that it stays that way.** Item 1 asked for red past a declared threshold.
   The colour law's guard (`audit.colour_law_faults`, ruled under CARD_FACE)
   admits `--loss` only under a selector naming an outcome — `.loss`, `.neg`,
   `.down` — and a job that stopped is not an outcome; the planting run went
   244 of 245 with red in place. The stale state ships **bold in the warning
   ink with the threshold in its own words** ("venue read 31h ago, past 30h";
   "reasoning pass has never run"). **RULED 2026-09-08: the colour law
   stands.** This is no longer a deviation awaiting a decision.
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
(c) — ALL SIX RULED 2026-09-08, the same morning:** the live poller
(registered, and it has fired on its own); red vs the colour law (the law
stands); per-card coverage (left, revisit after the 21st); the closer below
the early return (moved above it); `catch-up` calling a refusal a failure
(still open); the terminal retraction (still open). **After the 21st:** the tailnet leg; `LIVE_TTL`; the HTTP cache in
scratch copies; the slow prop fits; the 25 pre-fix MLB rows; the synthetic
package row; rare factors; the NFL team-name gaps; per-market factor-set
versions.

## Evidence of the run itself

`tests/test_night_audit.py`; the full planting set; the gate on the committed
tree. The bundle is rebuilt from this commit and its hashes are in the morning
message and the READINESS run log.

---

# Addendum — the operator's own screen, 2026-09-08 morning

He opened the app and found six things. **Every one was real, and the night
audit had passed the route they were on.**

## The finding about the audit itself, first

Item 7 recorded Live as "DONE (DOM), screenshots partial" because the pane was
minimised and captures timed out. **A DOM check sees what it asks for; a
screenshot sees what is there.** I asked for the ids I expected, found them
correct, and could not see that the old Picks grid was rendering fifteen cards
underneath the Live tab's own empty state.

**The rule from here, and it is in the audit's own terms:** a close-out with no
screenshot of a route is a close-out with that route UNVERIFIED, and it says so
in those words. `audit.live_tab_faults` now exists so the same blindness is at
least guarded on the payload, and `plant_the_old_card_on_the_live_tab` proves
it fires.

## The six

| # | what he saw | verdict | what it was |
|---|---|---|---|
| 1 | No Combos group | **NOT A DEFECT — confirmed rendering** | The group renders with zero packages at both widths (screenshots below). His screenshot predates the 03:14 rebuild that first carried it. C6 holds: the group is always present and says why it is empty. |
| 2 | "More picks" with fifteen pre-CARD_FACE cards under Live | **DEFECT, FIXED** | The old grid. See below — his premise about S1 is corrected. |
| 3 | A "SOLID" heading over an empty Live tab | **DEFECT, FIXED** | `applyStateTab` hid the heading SPANS and not the `<h3>` rows, so the clears group's rule and tier chip survived the tab switch. |
| 4 | Header 3:35 PM, Live 4:40 PM | **DEFECT, FIXED** | Two sources: the header took the minimum kickoff over every card; Live took the first card in CARD ORDER, which is by disagreement, not by clock. |
| 5 | "under 12.5 total points" on baseball | **DEFECT, FIXED** | `phrase` hardcoded "total points"; and the card did not carry its sport when the phrase was composed. |
| 6 | A Cubs card citing NBA and NFL walk-forward figures | **DEFECT, FIXED** | LAW 6 reaching a card. |

## Correcting the ruling's premise, because it matters for the record

The ruling calls the grid "the old Picks card renderer THREE_STATES S1 removed
by name". **S1 did not remove it.** Its brief names six removals: the notices
bar, the two sorters, the tier buttons, the View menu, the hero carousel with
its dots, and the "Most confident, no line to compare against" panel. The grid
is not among them; it survived by not being named, and the comment left on it
("THE GRID DROPS NOTHING NOW") records the hero's removal rather than its own.
So this is a removal ruled on 2026-09-08, not one S1 made and I missed.

## What was removed, and what deliberately was not

**Removed:** `pickCard` and the three helpers only it called (`cardTail`,
`chanceBlock`, `marketHint`); `applyCardState`; `slateCards`; the grid heading,
the shortlist note and the show-all control; the grid's loading skeleton;
`state.showAllCards`; `CARDS_BEFORE_SHOW_ALL`.

**Rewired, not deleted:** `applyLive` reached for `.card[data-id=…]` — the OLD
card's class. The Live tab's cards are `.face`, so **the poll has never updated
them in place**: a score there moved only when something else re-rendered the
page. The tick now re-renders the day. Re-rendering is safe where re-sorting
was not: the Live group is ordered taken-first then by question, which does not
move as scores change.

**Kept:** `#week-cards`, now holding only the slate's own sentences — "no
forecasts on this slate yet", "every pick has been settled", the quiet-market
lines. Those were never part of the old card, and a slate that says nothing is
a slate a reader cannot read.

**NOT removed, and this is a judgement I am flagging rather than burying:** 83
CSS class rules style nothing the app builds, by a crude detector I wrote
tonight. **That detector has false positives** — it misses classes built by
concatenation (`'day-job' + ' day-job-stale'` is one of its own false hits) —
so it is not the proof the audit's item 6 requires before a deletion. Deleting
a rule whose class is built by concatenation breaks a page silently, and I will
not do that at four in the morning with no screenshot of every route. Recorded
in FOLLOWUPS as a measured backlog with the caveat attached.

## A defect I introduced and how it was caught

Cutting `applyCardState` out by scanning for the next top-level function
boundary **took six neighbours with it** — `arrive`, `renderMarketTabs`,
`renderYesterday`, `placeGreeting`, `probBlock`, `clamp01`. The page threw
`placeGreeting is not defined` on boot. Caught **by loading the page**, not by
a test: the suite does not execute `app.js`. All six restored verbatim with the
accident recorded where it happened. Then a second one — the grid's loading
skeleton still referenced `CARDS_BEFORE_SHOW_ALL` — caught the same way, by the
app's own error banner.

That is twice in one hour that a text-boundary cut in `app.js` took more than
it was aimed at. It is the same failure recorded in this project's memory for
heredocs, in a different disguise.

## Item 5's fix reached three call sites, not one

`language.phrase` is called from `week` (the cards), `history` (the Results
table) and `digest`. The first was fixed by moving `cards[-1]["sport"] = sport`
above the phrase composition — it sat **seventeen lines below it**, so every
composer above saw a card with no sport. The other two build their own `item`
dict and neither carried `sport`; both now do. Verified on all three paths:
`under 12.5 total runs` on Picks, `under 9.5 total runs` on Results and in the
digest.

## Evidence: all four routes, both widths, with screenshots

Captured against a scratch copy of the record, on the code in this commit. The
Claude window was restored from minimised first, which is what made the
captures possible at all.

| route | 1400px | 390px |
|---|---|---|
| Upcoming | Combos group beneath Watching with its heading, counts and empty sentence; no "More picks"; pulse line on the strip | same, no overflow; Combos wraps cleanly |
| Live | "Nothing is being played. The first game starts Tue, Sep 8, 3:35 PM" — **matching the header exactly** — no tier heading, no cards | same |
| Results | table renders; MLB totals read "total runs" | table scrolls in its own container; no document overflow |
| Settings | ten sections | widest element 376px, **0 tap targets under 44px** |

## What I observed and did not change

The quiet-market sentences ("total bases: 0 asked — model never reached 70% at
the market's line") render inside `#week-cards`, which sits below the Today
panel, so they appear beneath the Live tab as well as beneath Upcoming. They
are slate-level sentences rather than cards, and the ruling was about the card
renderer. Left, and named here so it is a decision rather than an oversight.

---

# Addendum 2 — the browser suite, and a caveat I got wrong

## The claim I made and had to correct

The first addendum said the two defects I introduced were "caught by loading
the page, not by a test: the suite does not execute `app.js`."

**That is wrong.** There is a Playwright harness — `test_smoke.py`,
`test_cards.py`, `test_empty.py`, `test_tabs.py`, `test_hidden.py`,
`test_rapid.py` — that drives a real browser through a real login. It would
have caught `placeGreeting is not defined` in seconds. I had not run it when I
wrote that sentence, and wrote a claim about the harness from memory rather
than from running it. That is the failure this project's rubric calls a
vacuous pass, committed against my own work.

## What removing the grid did to those tests, and what was done about it

Twelve went red immediately and more surfaced behind them: 65 references
across eight files, all anchored on `#week-cards .card` — the grid's own
cards — or on the old card's anatomy (`.card-head`, `.card-body`,
`.card-numbers`, `.card-bucket`, `.tier`, `#week-showall`,
`#week-grid-heading`).

**They were re-pointed, not dropped**, on the precedent this project already
set for its guards:

    #week-cards .card   ->  #today .face
    .card-head          ->  .expand    (the Why control)
    .card-body          ->  .face-why  (the body it reveals)
    .card .tier         ->  .face-meta .chip
    card.classList('open')  ->  !faceWhy.hidden

Assertions about elements that no longer exist — the "More picks" heading, the
show-all button — were removed with a dated note where they stood, keeping the
assertion in each test that actually carries its promise.
`test_the_show_all_button_is_not_painted_once_it_has_shown_all` became
`test_a_hidden_control_is_hidden_to_the_accessibility_tree_too`, stating the
same rule against a control that survives.

## A real regression the suite caught, which is the point of it

`test_the_flagged_note_is_readable_without_a_tap` kept failing after the
selector was re-pointed, and it was right to.

**Operator ruling 2 of 2026-09-04 puts a flagged market's method note ON THE
FACE, not one tap in.** The OLD grid card rendered it. The CARD_FACE card
never has — and `_today_card` never carried `method_note` onto a Today card at
all, so the note lived only on `cards[]`, which only the grid read. Removing
the grid therefore removed the caveat from the product entirely: the payload
carried it and nothing on the page drew it.

Fixed in both halves: `_today_card` passes `method_note` through, and the card
renders it as `.face-method` above the lede — quiet, italic, and not behind a
tap. The test now passes for the right reason.

**This is the strongest argument in tonight's work for the screenshot rule.**
The note's disappearance was invisible to every scan: the payload was correct,
the guard on flagged methods checks the payload and stayed green, and no DOM
check asked for an element it did not know to expect.

## Two guards re-pointed for the same reason

The planting run fell to 245/247 after the removal. Both misses were guards
anchored on code the grid took with it, and both were re-pointed rather than
retired, as their own comments instruct:

* **`_JS_CARD_TOGGLE`** read `pickCard`'s `const toggle = () => {...}`. It now
  accepts that shape OR the CARD_FACE card's `more.onclick`, and the in-place
  check accepts `hidden` as well as `classList` — the new card reveals a body
  already in the tree by clearing `hidden`, which the stylesheet's own reset
  draws.
* **The dead-selector planting** anchored on `applyCardState`'s `.card-when`.
  It now anchors on `saveSetting`'s `.set-said`, where a renamed class would
  make every settings change report nothing, silently — the original bug's
  exact shape.

## And a guard I broke and had to satisfy rather than argue with

Rewriting `applyLive` to call `renderWeek()` tripped `live_update_faults`,
which refuses a re-render or re-sort on a live tick because "the reader is
part way down a slate and the thing they were looking at must not move." I had
reasoned that a rebuild was safe now that the Live group does not re-sort —
which is reasoning past a ruled guard, the thing I had refused to do for the
colour law an hour earlier.

The tick now patches in place, as the guard requires: the compact live payload
already carries `score_line` and `clock_line` composed by the server, the card
carries a `data-id`, and `applyLive` sets those two spans and nothing else. It
changes scores, never states — which group a card belongs to stays the
server's decision on the next render.

**247/247 planted violations caught.**

## What the grid's removal cost elsewhere, and what carried the promise instead

Four more things were anchored on the grid and went quiet with it. None was
dropped; each follows the mechanism that replaced it.

| what | was anchored on | now |
|---|---|---|
| the arrival fade | `#week-cards` carried the `transition` and `arrive()` was called on it | `#today` carries the transition and the panel is what arrives; a market chip switching the slate fades as it always did |
| `arrive()` itself | called once, in the grid block | called on the panel in `renderToday`; it had no caller at all for an hour |
| the method-flag tests | asserted the shared note verbatim, NBA and NFL figures included | assert the per-sport rule: a note names its own sport and no other |
| `test_the_note_carries_its_numbers` | asserted `+0.001` and `+0.002` were present | **that test encoded the defect the operator ruled against** — it held the cross-sport citation in place. Rewritten to assert each sport cites only its own recorded verdict, or says its own has not been measured. |

The last of those is worth naming plainly: a test can hold a defect in place,
and this one did. It was green for four days while a Cubs card argued from
basketball.

## Three promises that lived only on the old card

The grid's removal turned up a pattern worth naming on its own, because it is
the same failure three times and the browser suite found all three.

`pickCard` and its expanded body (`buildCardBody`) rendered things the
CARD_FACE card had never adopted. While both cards were on the page, each
promise was still kept — by the OLD card. Removing the grid took them off the
product, with the payload still carrying them and nothing drawing them:

| promise | ruled | where it was | now |
|---|---|---|---|
| a flagged market's method note, ON THE FACE and not one tap in | operator ruling 2, 2026-09-04 | old card's face; `_today_card` never carried `method_note` at all | `.face-method`, above the lede, and the field travels with the card |
| model, market and gap AS TEXT, not a graphic | GRIDIRON_16 R3, 2026-09-02 | old card's body (`.card-numbers`) | `.face-numbers`, first in the Why body |
| a route from a card's reasons to the page holding the coefficients | R1 | old card's body (`.card-more`) | `.face-more`, after the factor chips |

**None of these was noticed when CARD_FACE replaced the card design.** The
cards coexisted, so every scan and every test still found the promise being
kept somewhere on the page. That is the shape to watch for whenever two
designs overlap: a redesign can quietly stop keeping a promise and the
evidence stays green until the older design is removed.

`buildCardBody` itself now has no caller. It is left in place rather than cut,
because two text-boundary cuts in `app.js` tonight each took more than they
were aimed at, and a third at this hour is not worth the risk. It is listed in
FOLLOWUPS for removal with a test proving nothing reaches it.

---

# Addendum 3 — a third `app.js` accident, and the NFL screenshots

## The one that stopped the whole file parsing

Restoring the Factors link (the third promise above) I wrote:

```js
const more = el('a', 'face-more', ...);   // the link
```

twenty-five lines below

```js
const more = el('button', 'expand');      // the Why button
```

**in the same block.** `const` twice in one scope is a SyntaxError, so `app.js`
did not parse, `boot()` never ran, and every route rendered nothing. The same
edit also hung the expander's `onclick` on the anchor and appended the anchor
to the actions row in the button's place — three faults from one careless
name. The link is `moreLink` now and sits at the foot of the Why body, which
is where the old card put it.

**Every text scan in the gate stayed green**, because they read `app.js` as
text and a text scan does not care whether the text is a program. The browser
suite did catch it — but as five `ERROR`s reading `Timeout 15000ms exceeded`
waiting for `document.body.dataset.ready`, with no cause named.

**So the fixture now says what the browser already knew.** `page.page_errors`
had held `Identifier 'more' has already been declared` from the first
millisecond; the fixture collected it two lines above and threw it away when
it raised. It now prints the page errors, the console errors and the ready
flag. The rewritten wait turned an hour of guessing into one run:

```
E  AssertionError: the page never finished booting.
E    page errors:    ["Identifier 'more' has already been declared"]
E    console errors: none
E    ready flag:     None
```

That is the same lesson as the Live tab's, one layer down: **a check that
cannot see the failure reports a timeout.** The gate still never parses the
browser files, which is recorded in FOLLOWUPS with the one-line fix
(`node --check`) and the reason it is not being added at the end of this
session.

**Third text-boundary or naming accident in `app.js` in one night**, and the
third found by loading the page rather than by reading the diff.

## NFL Upcoming, both widths, on this commit

The operator's ruling stands: a close-out with no screenshot of a route is a
close-out with that route unverified. Captured against the live record through
a local render server, signed in as a reader, NFL chosen by clicking its tab.

| width | what the screenshot shows |
|---|---|
| 1400px | `Tomorrow`, market tabs with their counts, Upcoming/Live, "Nothing clears the venue's fee today.", then Watching — 30 more, then the cards |
| 390px | the same, one card to a row, nothing overflowing; the two price chips stay side by side |

**What they prove, and what they do not.**

* FIXED, and visible: the empty payout chip is **grey**. Computed background
  `rgb(38, 43, 51)` at both widths, class `box box-payout box-payout-empty`.
  It carried the favoured club's colour before tonight, which is why the
  operator saw "no price yet" written on red.
* STILL PRESENT, deferred with reasons in `docs/briefs/2026-09-08-opening-read.md`:
  the Model chip reads `—` on a card with a STRONG claim; the heading says
  `Tomorrow` over Sunday games with no day on the card; and every card says
  "no price yet" because the venue has not been asked — the opening read is
  the item that fixes it, and it is not built.
* The day strip reads `daily run 6h ago · venue read 2h ago · reasoning pass
  2h ago` — one figure for all sports, which is exactly the per-sport age the
  brief asks for and this session did not build.


## The form streak, in colour (operator, 2026-09-08, mid-session)

> "Colorize the W L to green and red to"

Done, and it needed a reading of the colour law rather than a free choice, so
the reading is written down.

**What the law said.** `--win` and `--loss` "mean a pick won and a pick lost
and appear on the edge line alone". A club's last five results are not picks.

**How it was read.** The law's target, stated in its own comment, is a colour
reaching for importance it has not earned: green as the interactive accent,
red as every warning. A W in a form streak is not that. It is the most literal
possible use of the colour — a game won — and the operator, who owns the law,
asked for it directly. So the colours are used, and the LAW'S OWN TEXT IS
AMENDED to list where they live: the edge line, a settled verdict, and the
form streak. A doc that describes the old behaviour is a doc that will be
believed, which is the ruling he made about "red" six hours earlier.

**A draw takes neither**, because it is neither.

**Mechanism, not habit.** The classes are `win` and `loss` — the words
themselves — which is exactly what `audit.colour_law_faults` scans a selector
for, so the guard reads the new rules and passes on their merits rather than
because they slipped past it. `tools/contrast.py` gained both pairs by name
and measures them: **8.86:1** for a win on a card, **6.29:1** for a loss,
against a 4.5 floor. `test_the_form_streak_is_green_for_a_win_and_red_for_a_loss`
asserts three things — that a mark is not the context row's grey, that a win
and a loss differ, and that every mark the renderer actually built is one of
W, L, D wearing the right class — plus that nothing which is NOT a streak is
broken into marks, so "no finished games yet" stays a sentence.


## Ruling 1 broke the gate, six hours later

Registering `Gridiron-Live` at ninety seconds — the first ruling of the night —
made the poller write to the record continuously for the first time. The next
full gate run failed:

```
dbcopy.TransposedCopy: the copied tables do not match their source column for
column, which is what a POSITIONAL copy produces...
  games.live_period: copy has (19, 160),      source has (19, 163)
  http_cache.body:   copy has (35644, 798094494), source has (35644, 798094658)
```

**The message was wrong, and confidently.** Nothing was transposed. Step 3
copies the fact tables out of the live record, and `copy_facts` committed —
releasing its read lock — *before* `verify_copy` re-read the source. Between
those two instants the poller advanced `games.live_period` and the venue read
replaced a cached body. Both tables are written by jobs that now run on a
schedule; before tonight the poller ran only when somebody typed a command,
so the gate and the record were never in the same minute.

**Fixed as a snapshot, not a retry.** The record is in WAL, so a read
transaction sees one instant and blocks no writer. The copy and its
verification now happen inside one transaction, so both read the same instant.
A retry would have turned a race into "flakiness" and left the gate's own
sentence false.

**And a diagnosis I wrote and deleted.** My first fix also taught the error to
tell the two causes apart: counts moved means a shift, only sums moved means a
concurrent write. **The project's own planting disproves it** — swapping
`home` and `away` on one row leaves both counts at 1 and moves only the
lengths, because `KC` and `BUF` are different lengths. A transposition can
look exactly like the thing I was calling not-a-transposition. The heuristic
came out; what stands is the snapshot, which removes the second cause instead
of guessing at it, and a message that now says the other cause is gone and
when it went.

`plant.py` still catches the real thing: **247/247**.
