# UI findings — 2026-09-05 (GRIDIRON_UI_AUDIT)

> **Verdict, in plain words.** A person can use this app today without
> hitting something broken. The evening's drive found seven things a person
> would call broken — the tabs that did not filter, a slower slate landing on
> the wrong sport, a lead left over from the sport before, a button that
> stayed after it had done its work, a menu the Escape key could not close, a
> switch that said one thing and showed another, and a select that did
> nothing — and every one is fixed, with a test that failed first and passed
> after, and the whole script driven again on the fixed code. The one thing
> to look at first: **the six decisions at the foot of this document**, and
> among them the sport in the address (reload and Back still forget which
> sport you were on). Everything else on that list is a judgement call, not a
> defect.

Brief: `docs/briefs/2026-09-05-ui-audit.md`. Found by driving, not by reading:
a real Chromium against a byte-consistent snapshot of the live record
(1,075 predictions, taken 22:05 PDT), at 1440 and 390, every route and every
control twice on every sport, then the rapid, mid-load, deep-link, reload,
history, offline and keyboard cases, with console errors, failed requests,
state diffs and box measurements recorded after every action. The drive
scripts live in the session scratchpad (`u1_picks.py`, `u1_routes.py`,
`u1_views.py`, `u1_probe*.py`, on `drive_common.py`); their JSON logs and
captures are the evidence behind every row below.

Severity: BROKEN > MISLEADING > AWKWARD > COSMETIC. Every finding carries the
route, the width(s), the exact steps, what happened, what should have, and
after U2–U4: why no test caught it, the fix commit, the test that now covers
it, and the class fix where one was made.

---

## BROKEN

### 1. A slower earlier slate lands after the current one and takes the page

- **Route / width:** Picks, 1440 and 390.
- **Steps:** On Picks, click NCAAF (243 cards, the slowest payload) and then
  UFC within about a second — or any sport whose answer arrives after the
  next click's. Deterministic reproduction: delay the NCAAF `/api/week`
  response by 2 s, click NCAAF, click UFC 150 ms later, wait 4 s.
- **What happened:** UFC is pressed, the tabs and counts are UFC's, and the
  hero and cards are another sport's. Seen three ways: UFC pressed with a
  baseball hero (`race_cfb_then_ufc_probe1440.png`); the NBA baseline capture
  showing 243 college football cards under "Today" (`picks_nba_1440.png`,
  24,116 px tall); the UFC LLM view showing "Rhode Island Rams at Temple Owls"
  (`u1_views`). `renderWeek` and `selectSport` have no in-flight guard: every
  response renders whenever it arrives.
- **What should happen:** the page shows the sport whose tab is pressed; a
  response that a later action has superseded is dropped.
- **Why no test caught it:** **drives differently than a person.** Every browser test clicks, waits for the response, then reads; no test clicks twice before the first answer lands, and no test slows a response. `page.route` is used in `test_cards.py` to reshape payloads, never to delay one. Class B.
- **Fix / test:** `7c7ef08` — `sportSeq`/`weekSeq`; every sport-scoped fetch checks its number after the answer, the live tick included, and a sport clicked during boot wins. Test: `tests/test_rapid.py::test_a_slower_earlier_slate_does_not_take_the_page` (a slow answer already in flight, for the week picker and for the slate; failed before the fix). Class fix B: `test_rapid.py` holds the interactions the tests never performed. Guard: `audit.render_guard_faults`, planted by `plant_a_late_answer_that_still_paints`, in the gate.

### 2. An empty slate leaves the previous sport's lead on the page

- **Route / width:** Picks, 1440 and 390.
- **Steps:** Open Picks on MLB, click NBA (no forecasts until October); or
  reach UFC after its whole card has settled.
- **What happened:** "this week · 0 picks", eight NBA tabs at 0, then a hero
  reading "Most confident today — Herrera · home runs — 88%" (a baseball
  pick), the "More picks" heading, a "show all 7 →" button, and only then "No
  forecasts recorded for this slate yet." (`nba_fresh_probe2_*.png`,
  `race_cfb_then_ufc_probe1440.png`). The empty branch of `renderWeek`
  returns before it touches the hero, the heading or the button.
- **What should happen:** no hero, no heading, no button; the message alone.
- **Why no test caught it:** **checks a proxy.** The empty-slate tests assert the message is present; none asserts that nothing else is. The fixture world has empty sports beside its full one, so the shape exists — the assertion stops early. Class D.
- **Fix / test:** `8d2647f` — the empty branch clears the hero, the heading, the show-all button and the carousel state. Test: `tests/test_empty.py::test_a_sport_with_no_forecasts_shows_nothing_of_the_last_one` (failed before), and `tests/test_tabs.py::test_a_tab_with_no_picks_shows_nothing_of_the_last_one`.

### 3. `[hidden]` loses to a class's `display` rule

- **Route / width:** Picks, both widths.
- **Steps:** MLB, tier STRONG, click "show all 7 →". Then look at NFL Picks
  below the grid.
- **What happened:** after the click the button carries `hidden` and is still
  painted (`display: block` from `.show-all`), 44 px tall, and clickable —
  a second click does nothing (`showall_after_click_probe1440.png`). On NFL
  and NBA the hidden yesterday strip is painted as a 17 px empty box with a
  1 px rule across the page (`.yesterday { display: flex }`). This is the
  same class as the view panel found on 2026-09-05 (`.view-panel { display:
  grid }`), fixed then for one element.
- **What should happen:** hidden means not painted, everywhere, by one rule.
- **Why no test caught it:** **checks a proxy.** The tests read the `hidden` attribute (and, since 2026-09-05, one element's computed display); no test asks of every `[hidden]` element on every route whether it is painted. The view-panel fix on 2026-09-05 fixed the instance, not the class. Class A.
- **Fix / test:** `9cfd137` — `[hidden] { display: none !important }`, the six copies deleted. Test: `tests/test_hidden.py` walks every `[hidden]` element on every route at 1440 and 390 and asserts its computed display; the show-all button is asserted unpainted after use. Class fix A: `audit.hidden_rule_faults`, planted by `plant_a_hidden_element_painted_by_its_class`, in the gate.

### 4. Escape does not close the View menu once a choice has been made

- **Route / width:** Picks, both widths (keyboard).
- **Steps:** UFC, click View, click "LLM", press Escape.
- **What happened:** the menu stays open; `document.activeElement` is the
  body. Choosing re-renders the toggles and drops focus, and the Escape
  handler listens on the menu, so a key pressed on the body never reaches it.
  (Escape straight after opening works, which is what the test checks.)
- **What should happen:** Escape closes the menu whenever it is open; focus
  stays on the chosen toggle after the re-render.
- **Why no test caught it:** **drives differently than a person.** `test_view_menu.py` presses Escape immediately after opening, with focus still on the button; a person chooses first. The re-render between open and Escape is the interaction the test never performs. Class B.
- **Fix / test:** `0eb3002` (and `291e89b` for the test) — Escape listens on the document; a choice remembers its toggle and the re-render hands focus to the new copy. Test: `tests/test_rapid.py::test_escape_closes_the_menu_after_a_choice_and_focus_stays_on_it` (failed before: focus on BODY). Class B.

### 5. A Settings switch ignores its own save

- **Route / width:** Settings, both widths.
- **Steps:** click "Tell me when results land" (reads "on").
- **What happened:** the line says "Tell me when results land changed from 1
  to 0." and the switch still reads "on" (`aria-pressed="true"`). A second
  click: "is already 0." Reload: "off". `saveSetting` writes the line and
  never the face.
- **What should happen:** the switch reads what was saved.
- **Why no test caught it:** **no assertion on the surface.** The settings tests exercise `/api/settings` and the fence; no browser test clicks a switch. The line under it (a proxy) is what the API tests read. Class D.
- **Fix / test:** `1b974b9` — `saveSetting` sets the face from the value the server recorded. Test: `tests/test_every_control.py::test_a_settings_switch_reads_what_it_saved` (click, read the face, reload, put the world back). Class fix D: `test_every_control.py`.

### 6. The Market select above the tier table does nothing

- **Route / width:** Record, both widths.
- **Steps:** Record, MLB, choose "hits" (or any market) in the select above
  "When it says STRONG, is it?".
- **What happened:** the table, its caption ("92 settled") and its headline
  ("LEAN picks in the 50-60% band … over 87") do not change; no request is
  made. The select is filled (`loadTierMarkets`) and never wired; the
  scorecard route takes no market.
- **What should happen:** the table shows the chosen market, with its N.
- **Why no test caught it:** **no assertion on the surface.** No test names `#tier-market`; the forecaster picker's tests assert its pressed state, a proxy, not the table. A control nobody acts on in a test cannot fail one. Class D.
- **Fix / test:** `737055a` — `/api/tier-table?sport&market&forecaster` through `views.tier_table_for` and the same `calibration.tier_table` the chips use; the select and the picker ask it; the caption names the market and the forecaster; an unknown market is a 404. Tests: `tests/test_every_control.py::test_the_market_select_fetches_the_tier_table_it_names`, `::test_the_forecaster_picker_fetches_the_tier_table_it_names`, `::test_every_record_control_asks_or_changes_something`. Class fix D.

### 24. The market tabs did not filter the slate (found during U3)

- **Route / width:** Picks, both widths.
- **Steps:** MLB, click "Moneyline 15", then "Total bases 0".
- **What happened:** the pressed tab changed and nothing else did: the same
  cards, the same hero, the same counts line, on every tab, the zero-count
  tab included. `renderWeek` filtered on the hidden Market select inside
  "This week"; the tab click set only `state.market`, which the pressed state
  read. The U1 drive log shows it plainly — eight MLB tab clicks, `cardCount`
  unchanged on all eight — and the digest's "[OK] tab 'total' with zero
  picks → shows: Sharpest disagreement 49ers at LA" was this defect wearing
  an OK label.
- **What should happen:** the tab is the filter.
- **Why no test caught it:** **no assertion on the surface.** `test_cards.py`
  asserts the tabs exist, carry their counts and come from the declared list;
  none clicks one and looks at the cards. Class D.
- **Fix / test:** `5cae0b5` — one source of truth, `state.market`, set by the
  tab or the select, mirrored by the select, reset on a sport switch, and
  falling back to All when the new sport does not ask that market. Tests:
  `tests/test_tabs.py` click every tab and check whose picks are on the page
  (failed before: "tab 'spread' shows picks from another market").
- **A correction to U1:** finding 1's "UFC pressed with a baseball hero" in
  `race_cfb_then_ufc_probe1440.png` was finding 2 (the residue on a settled
  slate), not a late paint; the race itself was seen in the NBA baseline and
  the UFC LLM view, and reproduced by the test with the slow answer in flight.

---

## MISLEADING

### 7. The yesterday strip is dated by the UTC resolution stamp

- **Route / width:** Picks, both widths.
- **Steps:** MLB Picks on the evening of 5 September (Pacific).
- **What happened:** "6 September: 10 right, 9 wrong". `_yesterday` groups
  settled picks by `substr(resolved_utc, 1, 10)`, so the games after 5 pm
  Pacific fall on tomorrow's date, the day's 106 earlier results sit under
  "5 September" and only the 19-pick fragment shows; `settled_day_label`
  compares that UTC date with the machine's local date, so "Today" never
  matches. UFC read "6 September: 7 right, 11 wrong" for an event fought that
  afternoon.
- **What should happen:** the league day of the games (the record's
  `games.league_date`, the convention ruled on 2026-09-05), labelled "Today"
  or "Yesterday" against that day.
- **Why no test caught it:** **the fixture world cannot contain the shape.** The seeded league resolves its games with stamps on the league day; no fixture game finishes after midnight UTC, so the UTC date and the league date never differ. Class C.
- **Fix / test:** `7af254e` — `_yesterday` groups on `games.league_date` (falling back to the resolver's UTC date where a game has none) and labels against that day. Test: `tests/test_yesterday.py` on a private copy of the browser world (`world_copy` fixture, new) whose 2025 games resolve today, so the two dates cannot agree (failed before: '6 September:' against '8 July:'). Class fix C.

### 8. Offline says "Failed to fetch", and keeps saying it

- **Route / width:** Picks, both widths.
- **Steps:** go offline; click a market tab; come back online; click a tab.
- **What happened:** the OFFLINE banner appears (correct). The error box says
  "Failed to fetch" — the browser's own string. Back online, the next tab
  click succeeds and the box still says "Failed to fetch"; only a route
  change clears it.
- **What should happen:** a sentence the server wrote, and the box clears
  when the next request succeeds.
- **Why no test caught it:** **interaction never performed.** The only offline test asserts the banner is hidden while online. Nothing goes offline. Class B.
- **Fix / test:** `61afe71` — `/api/meta` carries `unreachable_line` (language.py); `fetchJSON` throws it when the network fails, with the offline bar's text as the pre-boot fallback; a slate render that lands clears the box. Test: `tests/test_rapid.py::test_offline_says_so_in_words_and_a_later_success_clears_it`. Class B.

### 9. The counts line and the grid disagree on a finished slate

- **Route / width:** Picks, both widths.
- **Steps:** MLB after its card is complete: "All tiers", then STRONG.
- **What happened:** "tonight · 53 picks" with 40 on the page; "STRONG · 10 of
  53 picks" with 8. Once a slate is not live, settled picks are dropped from
  the grid (`open = cards.filter(!settled)`) and nothing says so.
- **What should happen:** the line says how many have settled, or the settled
  cards stay with their stamps.
- **Why no test caught it:** **checks a proxy.** Tests read the counts line and the grid separately; none compares them, and the fixture's open slate is never a finished one with settled picks still in `count_lines`. Class D.
- **Fix / test:** `b60ff0a` — the glance carries `settled_lines` beside `count_lines`, keyed the same way; the counts line appends them on a slate that is not live. Tests: `tests/test_settled_line.py` (payload and the rendered line). Class D.

### 10. Past the gate, the countdown counts to zero

- **Route / width:** Picks (the glance strip), both widths.
- **Steps:** MLB, read the line under the notices.
- **What happened:** "50-60% bucket: 158 of 100 · 0 more before calibration
  speaks". `max(0, gate - n)` keeps the sentence's shape after the gate is
  passed.
- **What should happen:** past the gate the line says the bucket is graded.
- **Why no test caught it:** **the state never occurs in the test record.** No fixture bucket reaches the gate (100), so the countdown is only ever tested on the way up — the boundary MENTOR §3 says to test AT. Class C.
- **Fix / test:** `9bfcabb` — `language.bucket_countdown_line`, tested AT the gate (99, 100, 158). Test: `tests/test_countdown.py`. Class C.

### 11. The Health panel prints a raw exception

- **Route / width:** Settings, both widths.
- **Steps:** Settings → Health, the CatchUp row.
- **What happened:** "SlateAlreadyAnswered: ufc 2026 slate 20260905 already
  has 84 forecasts in every market it asks (distance, moneyline, rounds),
  written 2026-09-04T02:04 under fac…" — a Python class name, a slate key and
  an ISO stamp, in visible text. `run_task` records `f"{type(exc).__name__}:
  {exc}"` and the panel places `last_detail` as is. The same row is counted as
  a failure; a slate already answered is not one (DECISION 3).
- **What should happen:** words: the sport, the day, what was already there.
- **Why no test caught it:** **the state never occurs in the test record.** The browser world has no failed task run, so the Settings plain-words scan (which does cover the route) has never seen a detail with a class name or a slate key in it. Class C.
- **Fix / test:** `96810c3` — `language.task_detail_words` strips the class prefix, turns a slate key into the day in words, a stamp into a day and a time, a factor set into a number; applied to `last_detail` and to missed runs. The browser world gains a failed run with the real detail (class fix C: the Settings plain-words scan now sees the shape). Tests: `tests/test_health_words.py` (the string, the payload, the page). Guard: `audit.health_detail_faults` on `tasks.status`, planted by `plant_a_raw_exception_on_the_health_panel`, in the gate on the record.

### 12. The login page and Picks count the same slate differently

- **Route / width:** login, both widths.
- **Steps:** sign out, read the login glance; sign in, read Picks.
- **What happened:** "NFL 152 picks this week" against "All 107"; "NCAAF …
  262 picks tonight" against 243. `login_glance` counts every unresolved row,
  early and final passes both; Picks counts standing questions.
- **What should happen:** one count, the standing one.
- **Why no test caught it:** **the fixture world cannot contain the shape.** The seeded league writes one pass per question; with no early/final pairs the row count and the standing count are equal, and no test compares the login glance to Picks. Class C.
- **Fix / test:** `e3dcea6` — the count goes through `calibration.standing_row_clause`. Test: `tests/test_login_count.py` writes two passes on one question and expects one (failed before: two). Class C.

### 13. NBA: the picker says 47, the page says 0, and the wrong reason shows

- **Route / width:** Picks, both widths.
- **Steps:** click NBA; open "This week".
- **What happened:** the picker reads "Week 1, 2026 (47)" — 47 voided rows —
  beside "this week · 0 picks". Because the picker pins `week=1`, the payload
  loses the season-start message ("The NBA season starts on 2026-10-20, 44
  days from now…") and the page says "No forecasts recorded for this slate
  yet." followed by four lines like "points: 0 asked — model never reached
  70% at the market's line", a reason that is not true of a season that has
  not begun.
- **What should happen:** the picker counts forecasts; the season-start
  message shows; no quiet-market reasons on an empty slate.
- **Why no test caught it:** **the state never occurs in the test record.** No fixture slate is both non-empty in rows and empty in forecasts (all voided). The season-start message test uses the default week, never a pinned one. Class C.
- **Fix / test:** `5639d26` — the picker counts forecasts and drops a slate with none; an empty payload always carries its message; quiet markets only on a slate that asked questions. Test: `tests/test_empty_slate.py` voids a whole slate on the world copy (failed before). Class C.

### 14. The View menu on an empty slate shows a "Forecaster" row with nothing in it

- **Route / width:** Picks, both widths.
- **Steps:** NBA, click View.
- **What happened:** "FORECASTER" with no choices, then "FORECAST final / early
  view (disabled)" (`viewmenu_nba_open_probe3.png`). `data.forecasters` is
  empty for an empty slate and the row renders anyway.
- **What should happen:** the row names the one forecaster or is not shown.
- **Why no test caught it:** **the state never occurs in the test record.** The view-menu tests run on a slate with forecasters; none opens the menu on an empty one. Class C.
- **Fix / test:** `e5d13c7` — the forecaster row hides when the payload offers no choice. Test: `tests/test_view_menu.py::test_a_forecaster_row_with_no_choices_is_not_shown`. Class C.

---

## AWKWARD

### 15. The glance abbreviates what the hero spells out

- Picks NFL: "sharpest disagreement +19.2 on SF @ LA" beside a hero reading
  "49ers at LA". The abbreviation form is the data's. "LA" is ambiguous with
  two Los Angeles teams in the league — the team-name map is DECISION 4.

### 16. Reload and Back forget the sport

- Choose NCAAF on Picks, reload: NFL. Picks (MLB) → Record → (UFC) → Results,
  Back, Back: Picks on UFC. The sport lives in memory only; the address
  carries the route alone. DECISION 2.

### 17. Tap targets at 390

- "This week" summary 19 px tall; "The measurements in full" 31 px; sport tabs
  NFL 40 px and NBA 43 px wide; hero dots 20 px wide; hero arrows 30 px wide.
  Everything else measured at or above 44 px. **Fixed `727e403`**: the summaries
  44 px tall, the sport tabs 44 wide (the strip's gaps give up the pixels), the
  arrows 44 wide; the dots 32 wide by 44 tall, because five dots and two
  arrows share a 312 px row and 44 each runs 83 px past the edge. The phone
  test measures width now.

### 18. `/login` while signed in shows the form again

- A signed-in reader opening `/login` gets the token form, not the app.
  **Fixed `ca44bf5`**: a valid session is sent to `/`, and the login page is
  `Cache-Control: no-store` — the browser had been serving the form from its
  own cache (a `FileResponse` carries validators), so the redirect never ran.
  Test: `tests/test_login_redirect.py`.

### 19. A tap on a card that lands before the new slate arrives is lost

- Tap a market tab and a card in quick succession: the tap hits the old
  card, the new grid replaces it. Recorded, not fixed: the fade is 200 ms and
  the old grid is gone on the response, so this is a race with the network
  rather than the motion. DECISION 5.

### 20. The sign-in POST is aborted by the page's own navigation

- Every successful sign-in logs `/auth/login net::ERR_ABORTED`: the page
  navigates before the fetch resolves. Harmless; noted.

---

## COSMETIC

### 21. LEAN chip contrast 4.36:1 (needs 4.5) — `rgb(136,146,160)` on `rgb(23,26,31)`.
**Fixed `d75088e`**, with a correction: the tokens themselves are 5.5:1; the
4.36 the browser measured included an ancestor's opacity on the chip. `--muted`
is the lighter token and clears the floor with that opacity applied; the test
asserts the improvement, not the false premise.
### 22. Disabled pager buttons 3.04:1 — disabled, so acceptable; noted.
### 23. Footer "LLM spend today $0.0000 of $2.00" — four decimals of nothing.
**Fixed `633f685`**: cents. Test: `tests/test_spend_line.py`.

---

## Cleared while driving (not bugs)

- "complete · 15 of 15 final" on MLB at 22:20 UTC — it was 05:25 UTC on the
  6th; the machine is Pacific. The slate was complete.
- The closed "This week" details' content measured with boxes under the
  headline — Chrome 131 keeps layout boxes under `content-visibility:
  hidden`; `checkVisibility()` is false and Tab skips it. Not painted.
- "See them in Results →" measured as covered — the arrival transform had
  moved the box by the time the point was tested; the click navigates.
- Next/Previous unclickable on NBA Results — disabled by design.
- Factor codes on Record read as snake_case — the one sanctioned identifier,
  exempt by ruling (`.factor-code`, `td.wide`).
- Every "the page scrolled" entry — Playwright scrolls a target into view
  before clicking; a person had already scrolled there.

## Harness lessons (for FOLLOWUPS)

- Two drivers on one snapshot server inflated latency enough to fake a dozen
  "the click did not take" findings; every one vanished when re-driven alone.
  One driver per server, and measure click-to-paint latency directly.
- Chrome's sequential-focus starting point follows the last click: a keyboard
  walk must focus the first link explicitly or it starts mid-page.
- Inline spans that wrap report overlapping rects; only block boxes count.

## DECISIONS for the operator

1. **Today's MLB hero is a retired market's pick.** Five home-run picks
   written at 18:00 UTC before the 20:53 UTC retirement led the MLB tab all
   evening with no "Home runs" tab to find them under. They stand (LAW 3) and
   resolve tonight; nothing to build unless a rule is wanted for the next
   retirement.
2. **Sport in the address.** Reload and Back forget the sport (16). A
   `?sport=` in the hash, or session memory, is a small change to how the app
   addresses itself; it is a change of behaviour, so it is yours.
3. **"SlateAlreadyAnswered" is recorded as `failed`.** A CatchUp run that finds
   the slate already answered is a refusal, not a failure, and it inflates the
   all-time failure count on Health. Wording is fixed in U3; the result word
   is the record's and needs a ruling.
4. **Team names.** "LA" for the Rams follows the data source's abbreviation.
   A name map (LA → Rams, LAC → Chargers) is a data change across sports.
5. **The lost tap during arrival (19).** Keeping the old grid interactive until
   the new one arrives is a design choice.
6. **Settled picks on a finished slate (9).** Say the count (done in U3) or
   keep the settled cards on the page with their stamps — which is the design
   the "green means a pick won" rule was written for.

## U2 — why no test caught it, and the classes fixed

The brief named five classes. Every finding above carries its class; the count:

| class | findings | what the tests were doing instead |
|---|---|---|
| **A — the assertion checks a proxy for painting** (attribute set, not element unpainted) | 3 | reading `hidden`, or one element's computed display |
| **B — the tests drive the app differently than a person** (no second click before the first answer, no slow response, no key after a re-render, never offline) | 1, 4, 8 | click, await, read |
| **C — the state never occurs in the test record / the fixture cannot contain the shape** | 7, 10, 11, 12, 13, 14 | one pass per question, no game past midnight UTC, no bucket at the gate, no failed task, no voided slate, no empty menu |
| **D — the assertion checks a proxy for behaviour, or there is no assertion on the control at all** | 2, 5, 6, 9 | the message is present; the line under the switch; the picker's pressed state; the counts line alone |
| **E — the surface is only reachable by hover** | none found | — |

The class fixes, each its own commit, each proven by a planting or a test that
failed before the fix:

- **A → one rule, every element, every route.** `[hidden] { display: none
  !important }` at the top of the stylesheet, the six per-element copies
  deleted, `audit.check_hidden_rule` in the gate, a planting that removes the
  rule, and a browser test that walks every `[hidden]` element on every route
  at both widths and asserts its computed display is `none`.
- **B → `tests/test_rapid.py`: the interactions a person performs and the
  tests never did.** A slower earlier slate delayed by `page.route`; two
  sport clicks 150 ms apart; a double-clicked tab; Escape after a menu choice;
  offline, a click, online, a click. Each asserts the thing (the ids on the
  page belong to the pressed sport; the menu is closed; the box is clear).
- **C → the fixture world gains the shapes.** The browser world's `task_runs`
  gets a failed run whose detail is the real `SlateAlreadyAnswered` text; a
  game that finishes after midnight UTC on its league day; a bucket at the
  gate; a slate of voided rows. Each shape has a test that read wrong before
  its fix.
- **D → `tests/test_controls.py`: every control does something.** For each
  control on Record and Picks: act, then assert a request was made or the
  region it governs changed — the dead Market select and the forecaster
  picker failed this before the fix, and the Settings switch's face is
  asserted rather than its line.


## U4 — proof

### U4.1 The full U1 script, driven again on the fixed code

Same snapshot, same scripts, same widths, one browser at a time this time
(`scratchpad/u4/`). What the second drive found, against the first:

| finding | first drive | second drive |
|---|---|---|
| 1 race | UFC pressed, football cards; NBA showing 243 football picks | UFC pressed, **0 foreign cards**; NBA shows its own message and nothing else |
| 2 residue | baseball hero on NBA and on settled UFC | hero hidden, no id, no heading, no button, on both |
| 3 hidden painted | show-all painted after use; yesterday strip painted on NFL | `hiddenPainted: []` on every route at both widths; show-all `display: none`, 0 px, not clickable |
| 4 Escape | menu open after a choice, focus on BODY | menu closed, focus on the chosen toggle, then the button |
| 5 switch | "changed from 1 to 0", face "on" | face follows the save; reload agrees |
| 6 tier select | same table for every market | caption and headline change per market and per forecaster |
| 7 yesterday | "6 September: 10 right, 9 wrong" | "Today: 10 right, 9 wrong" (MLB), "Today: 75 right, 20 wrong" (NCAAF) |
| 8 offline | "Failed to fetch", never cleared | the server's sentence; cleared by the next tap |
| 9 counts | "53 picks" over 40 | "53 picks · 13 settled"; STRONG "10 of 53 · 2 settled" |
| 10 countdown | "158 of 100 · 0 more before calibration speaks" | "158 settled · past the 100 needed, so calibration speaks here" |
| 11 health | "SlateAlreadyAnswered: … slate 20260905 …" | words; one bare "fs2" remained and is fixed in `0c5e79b` |
| 12 login count | 152 vs 107 | standing count (unit test; the login page's line follows) |
| 13 NBA picker | "(47)" beside "0 picks", false quiet-market reasons | no picker option, the season message, no quiet markets |
| 14 empty menu row | "FORECASTER" over nothing | row hidden |
| 17 tap targets | 19 px summary, 40/43 px tabs, 20 px dots | summaries 44, tabs 44 wide, dots 32×44 (recorded), arrows 44 |
| 18 /login | the form for a valid session | sent to `/` |
| 21 LEAN chip | 4.36:1 measured | no chip under 4.5:1 in the contrast scan at either width |
| 24 tabs filter | eight clicks, nothing changed | every tab shows its own picks; the zero tab shows none |
| keyboard walks | not from the top | 41/20/26/21 stops at 1440, 41/23/27/21 at 390, none covered or hidden |

**What the second drive still listed, and why none of it is a defect:**

- *"click 'None' (time 2)"* on show-all: the button hides after its one job,
  so the drive's "twice" cannot happen. The fix is the reason.
- *"come back online → the error box says [the server's sentence]"*: by
  design, the box clears on the next successful render, which the next step
  showed. The drive's expectation at that step was stricter than the design.
- *NCAAF tab clicks read the previous tab*: the drive's 400 ms settle sits just
  above NCAAF's paint. Measured alone (`u4_latency.py`): a tab click paints in
  **336–348 ms** on the 243-card slate (API 352 ms), 53–68 ms on MLB and NFL.
  Under half a second; under two browsers it was over the drive's wait. Not a
  finding.
- *the NBA early toggle* is disabled by design; *Next/Previous on NBA Results*
  are disabled by design; *the sign-in POST aborted by navigation* is finding
  20, noted.
- *"tab 'hits' says 3, renders 2"*: the third has settled, and the counts line
  now says "1 settled" — finding 9's design, DECISION 6 if the operator wants
  settled cards kept on the page instead.
- *every "the page scrolled"*: Playwright's own scroll-into-view.

### U4.1a Two findings the re-drive raised

**25. No slate, no live poll (MISLEADING → fixed `49d4ed4`).** With the race
fixed, the empty NBA payload polled `/api/live?week=null` every minute and
was refused with a 422 on every action — before, the NBA tab had been polling
for whichever sport's cards had leaked onto it. Test:
`tests/test_empty.py::test_a_sport_with_no_forecasts_starts_no_live_poll`
(failed before: the 422 in hand).

**11, follow-up (`0c5e79b`).** One bare "fs2" survived the humaniser in a
task detail that names the version without "factor set" before it.

### U4.2 The gate

Run on the committed tree at `49d4ed4` under `.venv` (`scratchpad/u4_verify.txt`): step 1 the full suite, **1,184 tests, no skips, no failures** (one test reaches the network by design and is named); step 2 **204 of 204 plantings caught**, the three new ones among them (the hidden-wins rule deleted, a late answer that still paints, a raw exception on the Health panel); steps 3–4 and every check green, **57 PASS, 0 FAIL**, the three new checks passing (hidden means not painted; one answer per question asked; the health panel speaks in words); exit 0.

### U4.3 The document

Every finding above carries its fix commit, its test, and its class fix where
one was made (U2). Corrections recorded: finding 1's first capture was
finding 2; finding 21's premise was an ancestor's opacity, not the token.

### U4.4 Desktop bundle

Rebuilt from `49d4ed4` at 2026-09-06T07:06Z (`dist/Gridiron/_internal/gridiron/build_stamp.json`), served on a spare port and answering `/api/health` 200 with build `49d4ed497767`; the Desktop and Start Menu shortcuts point at the same exe and are unchanged.
