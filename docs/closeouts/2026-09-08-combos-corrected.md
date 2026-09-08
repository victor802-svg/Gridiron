# Close-out — GRIDIRON_COMBOS, corrected (2026-09-08)

Against `docs/briefs/2026-09-08-combos-corrected.md`. The declined first draft
and its close-out stay at `2026-09-08-combos.md`.

**The headline, and it is a finding rather than a shortfall: the group shipped
empty and truthful.** Measured against the venue on the day the record opened,
there was no package this project could price in any sport it forecasts. The
machinery to price one exists, is tested, is planted against, and is wired into
the daily read; what does not exist is a package worth a card.

| phase | verdict | evidence |
|---|---|---|
| **The LAW 5 amendment** | **DONE** | `CLAUDE.md` carries "PACKAGES ARE GRADED, NEVER BUILT", dated 2026-09-08, with the operator's reason and the old "SINGLES ONLY" text kept beneath it in a blockquote. The four bulleted prohibitions are untouched. The enforcement table's parlay row is replaced by the four new plantings. |
| **C1 — the retirement, by name** | **DONE** | `recommend.price_parlay` and `recommend.SinglesOnly` are gone, replaced in the source by a dated note saying what took over. `plant.py::plant_a_parlay` is gone, replaced by a dated comment in the same position. `tests/test_recommend.py` now fails if either name comes back. |
| **C1 — grading, and the four refusals** | **DONE** | `market/combos.py::classify` returns `priceable` or one of six counted reasons. `audit.check_combo_package` fails by name — "A PACKAGE IS GRADED, NEVER BUILT" — on a priced same-game, cross-sport, four-leg or unforecast-leg package. All four plantings fire: `plant_a_priced_same_game_package`, `plant_a_priced_cross_sport_package`, `plant_a_priced_four_leg_package`, `plant_a_priced_package_with_an_unforecast_leg`. |
| **C1 — reading the venue** | **DONE** | `kalshi.read_packages` / `capture_packages`, `venue_packages` table (append-only, with a trigger refusing a priced row that carries no games or carries a reason against it). Wired into `lines.snapshot_many`, so packages are read on every daily run, after the prediction rows exist. |
| **C2 — the arithmetic** | **DONE** | `fair_value` (product of the legs' published probabilities), `legs_multiply_to`, `package_edge` (fair − price − fee, and return on stake), `singles_alternative`. Measured and asserted: the fee per dollar is **1.67×** the singles' rate on two 60¢ legs and **2.78×** on three. Every card prints the margin line and the singles line; ranked by return on stake, capped at three, and no two shown packages share a leg. |
| **C3 — size** | **DONE** | `combos.size_for`: 0.5u on two legs, 0.25u on three below the gate, flat and unadjusted by odds or by the model's probability; above the gate, quarter-Kelly **capped at the flat fraction**, so a package can never be staked above what an unproven one would have been. |
| **C4 — record, gate, kill** | **DONE** | `config.COMBO_MARKETS = ("combo_2", "combo_3")` with `combo_market(legs)`; `calibration.clv_minimum` gives a package **100** closes against a single leg's 50, dated `COMBO_CLV_DECLARED`; `config.COMBO_KILL_AFTER = 50` and `COMBO_KILL_DECLARED`, with `calibration.combo_kill_verdict` reporting from day one and never editing the registry itself. `picks_taken` was **rebuilt** to admit a package tap: `prediction_id` is nullable, `package_id` added, a CHECK admits exactly one, and a trigger refuses a tap before the package was read. `calibration.taken_packages` is its own line and never enters a leg's curve. |
| **C5 — words** | **DONE** | "combo" left `PRESSURE_WORDS` with a dated reason; "parlay", "same game", "boost", "builder", "add leg" and "slip" stay banned. The day scan now reads a package card's own strings — the legs arrive as the *venue* wrote them, which is the one place on the page where the text is somebody else's. `plant_a_same_game_label_on_a_combo_card` fires. |
| **C6 — where** | **DONE** | Third group on Upcoming, beneath Watching: heading, counts line, cost line (with the cards), cards, empty sentence. Measured in the browser at **1100px** and **390px**: no horizontal overflow at either, the group hides on Live and returns on Upcoming, and the cost sentence hides when there are no cards to print it on. |
| **The close-out's own measurement** | **DONE** | See below. |

## What the venue actually had open, 2026-09-08

Measured before anything was built, and again after:

* `KXNCAAMBSGP` — college-basketball **same-game** parlays. One market read in
  full, on request, before the commit:

      ticker  KXNCAAMBSGP-26APR06CONNMICHSPREAD-MICHU144
      title   Michigan covers -7.5 and UConn and Michigan collectively score
              under 144.5 total points
      legs    "Michigan -7.5", "Under 144.5 points"
      sport   cbb, from the KXNCAAMBSGP prefix

  **The tag is right.** UConn against Michigan on 6 April 2026 is the men's
  college BASKETBALL final; `cbb` is not `cfb`, this record's college football,
  and is not in `config.SPORTS` at all. `classify` refuses it
  `unforecast_sport` — no forecast exists to price it with.

  **And a claim in an earlier draft of this file was wrong.** It said C1
  refuses these "as same-game, by name". It did not: the sport check comes
  first. Worse, the same package in a sport this record DOES forecast would
  have been counted "with a leg this record does not forecast", because "Under
  144.5 points" names no club and lands in no game. So `SAME_GAME_SERIES` now
  declares the venue's own SGP naming, checked straight after the sport, and
  the reason printed is the one a reader needs.
* `KXNBAPREPACK2ML`, `KXNBAPREPACK3ML`, `KXNFLCOMBO`, `KXNCAAMB2ML` — expose
  **no markets in any status**. The series exist and list historical events.
* **No baseball game package exists at all**, so `COMBO_SERIES` declares none
  for MLB. `KXMLBAWARDCOMBO` pairs two season awards, which this record does
  not forecast, and is deliberately absent from the map.

So: **priceable packages on the day the combo record opened — none, in any
sport.** That sentence is what the group prints.

## Two things that went wrong, both recorded rather than smoothed over

**A verification wrote to the live record.** Proving the package tap end to
end, I ran it against `var/gridiron.db` instead of a temporary database. It
wrote a package the venue never published (`KXTEST-1`, legs in games `g1` and
`g2`, which are not games) and a tap on it — and `calibration.taken_packages`
then read that tap and said "1 of 1 priced packages marked", a false statement
about the operator's own choices.

**HOW THE TAP WAS FIRST REMOVED, exactly, because the operator asked.** With a
plain `DELETE FROM picks_taken WHERE id = ?` on an ordinary connection. Nothing
was bypassed: `picks_taken` had three triggers — `picks_taken_no_update`,
`picks_taken_after_the_prediction` and this brief's
`picks_taken_after_the_package` — and **no no-delete trigger, ever**. The
table's own comment said "append-only"; the schema did not enforce it, and I
took the comment's word for what the schema allowed instead of reporting that
the two disagreed. That is the finding.

**Corrected on the operator's ruling, the same day:**

* `picks_taken_no_delete` now refuses the delete, by name, and
  `plant_a_deleted_tap` proves it fires.
* `picks_retracted` is built — the append-only companion CARD_FACE F3 asked for
  and that close-out recorded SKIPPED. Same shape as `prediction_voids`: one
  row per retracted tap, with a reason of at least ten characters. A retraction
  is terminal, like a void, and that limitation is in `FOLLOWUPS.md`.
* **The synthetic tap and its retraction now both stand as rows.** The tap
  carries its original timestamp; the retraction carries the whole story in its
  reason — that it was written by a verification run and not by the operator,
  that it was first removed by a DELETE, and that nothing refused that DELETE
  because no trigger existed.
* **The package row stays.** `venue_packages_no_delete` forbids removing it and
  that trigger is right: the row is a true record that this text was written to
  the table at that moment.
* **And the counts were tightened, which is a real correction rather than a way
  to hide it:** a package whose legs point at games this record does not hold
  was never priceable here, whoever wrote it. `taken_packages`, the
  sports-without-packages sentence, and `take_package` all now require the
  package to be placed in games the record holds.

## Verification can no longer touch the live record at all

The operator ruled that this closes in this brief rather than as a followup.

* `db.connect` raises **`LiveRecordTouched`**, naming the file and the caller,
  when anything under pytest (`PYTEST_CURRENT_TEST`) or under
  `tools/guards/plant.py` (`GRIDIRON_VERIFYING`) opens `var/gridiron.db`. The
  path is compared **resolved**, so a different spelling of the same file is
  the same file.
* `open_db` runs `init`, which writes — so it is refused on the live path
  before any migration runs.
* **One door, narrow and named:** `db.read_the_live_record(why)` takes a reason
  in words (ten characters minimum, no reason no handle) and returns a
  connection with `PRAGMA query_only = ON`, so **SQLite itself** refuses a
  write through it. Twenty-six call sites across eight test files and
  `plant.py` were converted; each now states in a sentence what it is asking
  the record. Every one is a read about *this deployment* — whether a venue
  credential sits in it, whether every card agrees with its own arithmetic —
  which a scratch database cannot answer, because an empty record agrees with
  everything.
* **The gate's own live step is now read-only too.** `verify.py` step 4 used
  `open_db(config.DB_PATH)`, which migrated the operator's file in order to
  report what it said; it now uses the read handle.
* **A planting had been writing through the API to whatever database was
  configured** — `plant_an_unauthenticated_settings_write` POSTs a settings
  change, and with no `set_database` that is the live one. Found by the new
  guard on its first run. It now uses a scratch database.

Three plantings, all firing: `plant_a_test_that_opens_the_live_record`,
`plant_a_write_through_the_live_read_handle`, `plant_a_deleted_tap`.

**What this does NOT cover, stated rather than implied:** `verify.py` steps 3
and 4 run outside pytest and outside `plant.py`, so the flag is not set for
them; step 3 attaches the live file read-only to copy facts into a temporary
database, and step 4 now holds a query-only handle. Neither can write, but
neither is stopped by the guard — they are stopped by what they hold.

**LAW 5's credential scan fired on this brief's own code, and the code moved.**
`combos.game_tokens` and its `token` variables tripped
`audit.venue_credential_faults`, which refuses that word inside a market
module. It was a false positive. The scan is one of the four things LAW 5 marks
**not amendable by a later session**, so it was left exactly as it is and the
function was renamed `club_index` with `name`/`names` throughout — better names
anyway, in a project whose own convention bans jargon. A scan that can be
argued out of a false positive can be argued out of a real one.

## What rendering the card found, which is why it was rendered

The venue offers no priceable package, so the card face would have shipped
unseen. It was built instead on a slate in a TEMPORARY database — two games,
two moneyline forecasts with quotes, one cross-game package and one same-game
one — and looked at, at both widths. **Five defects, none of which any test
would have caught:**

1. **`Payspays 3.33x`.** The payout box is labelled "Pays" and the chip said
   "pays 3.33x" beneath it. Fixed in `payout_chip_words`, and it was true of
   the SINGLE card too — no pick on the live slate has carried a price since
   the chip was built on 2026-09-08, so nobody had ever seen either.
2. **"One flat unit" above a half-unit package.** `_units_words` printed the
   same phrase for every flat size while the money beside it said $7.50 — two
   numbers disagreeing, with nothing to tell a reader which to believe. Now
   "Half a flat unit" and "A quarter of a flat unit".
3. **Five invented class names.** `price-cell`, `price-label`, `price-under`,
   `payout-cell` and `club-pill` are in no stylesheet, so the card rendered as
   a run of unstyled text. It now uses the classes the single card has had all
   along; the only new rule is the accent border.
4. **The tap would have been refused.** It sent `X-Gridiron-CSRF`; this app's
   header is `X-Gridiron-Form`. Every package tap would have come back 403,
   invisible, because no package had ever rendered a button to press.
5. **"Taken today · nothing marked yet" beneath a card reading "taken".** The
   running list read prediction taps only. It now lists package taps too, with
   the venue's price as it stood at the reading the tap points at.

Proved after the fixes, end to end on the temporary slate: the card renders in
the page's own grammar, the tap writes one row carrying a package id, and
`calibration.taken_packages` reads it back as "1 of 1 priced packages marked".
No horizontal overflow at 1100px or 390px; the legs wrap at phone width.

## Evidence

* `pytest tests/test_combos.py` — 36 tests, all passing: the four refusals, the
  permitted shape, the two-hit rule, the side a leg names, the arithmetic, the
  two fee ratios, the size fractions and their cap, the two gates, the kill's
  wording before it can fire, the tap, the CHECK, the words, and the empty
  group on a fresh record.
* `python tools/guards/plant.py` — the five new plantings fire; the retired one
  is gone by name.
* The full suite and `tools/verify.py` are recorded in the session report.
