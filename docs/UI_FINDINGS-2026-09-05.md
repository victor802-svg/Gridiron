# UI findings — 2026-09-05 (GRIDIRON_UI_AUDIT)

«VERDICT»

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
- **Why no test caught it:** «U2»
- **Fix / test:** «U3»

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
- **Why no test caught it:** «U2»
- **Fix / test:** «U3»

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
- **Why no test caught it:** «U2»
- **Fix / test:** «U3»

### 4. Escape does not close the View menu once a choice has been made

- **Route / width:** Picks, both widths (keyboard).
- **Steps:** UFC, click View, click "LLM", press Escape.
- **What happened:** the menu stays open; `document.activeElement` is the
  body. Choosing re-renders the toggles and drops focus, and the Escape
  handler listens on the menu, so a key pressed on the body never reaches it.
  (Escape straight after opening works, which is what the test checks.)
- **What should happen:** Escape closes the menu whenever it is open; focus
  stays on the chosen toggle after the re-render.
- **Why no test caught it:** «U2»
- **Fix / test:** «U3»

### 5. A Settings switch ignores its own save

- **Route / width:** Settings, both widths.
- **Steps:** click "Tell me when results land" (reads "on").
- **What happened:** the line says "Tell me when results land changed from 1
  to 0." and the switch still reads "on" (`aria-pressed="true"`). A second
  click: "is already 0." Reload: "off". `saveSetting` writes the line and
  never the face.
- **What should happen:** the switch reads what was saved.
- **Why no test caught it:** «U2»
- **Fix / test:** «U3»

### 6. The Market select above the tier table does nothing

- **Route / width:** Record, both widths.
- **Steps:** Record, MLB, choose "hits" (or any market) in the select above
  "When it says STRONG, is it?".
- **What happened:** the table, its caption ("92 settled") and its headline
  ("LEAN picks in the 50-60% band … over 87") do not change; no request is
  made. The select is filled (`loadTierMarkets`) and never wired; the
  scorecard route takes no market.
- **What should happen:** the table shows the chosen market, with its N.
- **Why no test caught it:** «U2»
- **Fix / test:** «U3»

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
- **Why no test caught it:** «U2»
- **Fix / test:** «U3»

### 8. Offline says "Failed to fetch", and keeps saying it

- **Route / width:** Picks, both widths.
- **Steps:** go offline; click a market tab; come back online; click a tab.
- **What happened:** the OFFLINE banner appears (correct). The error box says
  "Failed to fetch" — the browser's own string. Back online, the next tab
  click succeeds and the box still says "Failed to fetch"; only a route
  change clears it.
- **What should happen:** a sentence the server wrote, and the box clears
  when the next request succeeds.
- **Why no test caught it:** «U2»
- **Fix / test:** «U3»

### 9. The counts line and the grid disagree on a finished slate

- **Route / width:** Picks, both widths.
- **Steps:** MLB after its card is complete: "All tiers", then STRONG.
- **What happened:** "tonight · 53 picks" with 40 on the page; "STRONG · 10 of
  53 picks" with 8. Once a slate is not live, settled picks are dropped from
  the grid (`open = cards.filter(!settled)`) and nothing says so.
- **What should happen:** the line says how many have settled, or the settled
  cards stay with their stamps.
- **Why no test caught it:** «U2»
- **Fix / test:** «U3»

### 10. Past the gate, the countdown counts to zero

- **Route / width:** Picks (the glance strip), both widths.
- **Steps:** MLB, read the line under the notices.
- **What happened:** "50-60% bucket: 158 of 100 · 0 more before calibration
  speaks". `max(0, gate - n)` keeps the sentence's shape after the gate is
  passed.
- **What should happen:** past the gate the line says the bucket is graded.
- **Why no test caught it:** «U2»
- **Fix / test:** «U3»

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
- **Why no test caught it:** «U2»
- **Fix / test:** «U3»

### 12. The login page and Picks count the same slate differently

- **Route / width:** login, both widths.
- **Steps:** sign out, read the login glance; sign in, read Picks.
- **What happened:** "NFL 152 picks this week" against "All 107"; "NCAAF …
  262 picks tonight" against 243. `login_glance` counts every unresolved row,
  early and final passes both; Picks counts standing questions.
- **What should happen:** one count, the standing one.
- **Why no test caught it:** «U2»
- **Fix / test:** «U3»

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
- **Why no test caught it:** «U2»
- **Fix / test:** «U3»

### 14. The View menu on an empty slate shows a "Forecaster" row with nothing in it

- **Route / width:** Picks, both widths.
- **Steps:** NBA, click View.
- **What happened:** "FORECASTER" with no choices, then "FORECAST final / early
  view (disabled)" (`viewmenu_nba_open_probe3.png`). `data.forecasters` is
  empty for an empty slate and the row renders anyway.
- **What should happen:** the row names the one forecaster or is not shown.
- **Why no test caught it:** «U2»
- **Fix / test:** «U3»

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
  Everything else measured at or above 44 px.

### 18. `/login` while signed in shows the form again

- A signed-in reader opening `/login` gets the token form, not the app.

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
### 22. Disabled pager buttons 3.04:1 — disabled, so acceptable; noted.
### 23. Footer "LLM spend today $0.0000 of $2.00" — four decimals of nothing.

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

«U2»

«U4»
