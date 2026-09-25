"""The board (GRIDIRON_BOARD, operator ruling 2026-09-24).

What the Games rows and the Props tiles promise, asserted on the browser
suite's own world and in a real Chromium: a signal never renders without its
badge; every word a reader meets, tooltips included, is scanned; a live row
carries the score and the pregame figure and nothing that can be acted on;
the props rank by cushion against a declared multiple and say the venue is
not read; the jersey is drawn from the measured colours and nothing typed.
"""
from __future__ import annotations

import re

import pytest

from gridiron import audit, board, config, language, views
from gridiron.data.team_colours import TEAM_COLOURS

WIDE = {"width": 1440, "height": 900}


def _payload(conn, sport="nfl"):
    return views.week(conn, sport)


# --- the payload --------------------------------------------------------------

def test_every_row_and_tile_carries_its_badge_and_its_signal_is_one_of_four(world_copy):
    payload = _payload(world_copy)
    games = payload["board"]["games"]
    assert games, "the fixture slate has no games"
    for game in games:
        assert game["state"] in ("upcoming", "live", "final")
        pick = game["pick"]
        for block in ([pick] if pick else []) + game["questions"]:
            assert re.fullmatch(r"\d+/\d+", block["badge_words"]), block["badge_words"]
            assert block["badge_gate"] == config.MIN_SAMPLE_FOR_EDGE_CLAIM
            assert block["signal"] in ("clears", "costs", "won", "lost", "withdrawn", "none")
            assert "settled" in block["tips"]["badge"]
    for tile in payload["board"]["props"]["tiles"]:
        assert re.fullmatch(r"\d+/\d+", tile["badge_words"])
    assert audit.board_signal_faults(payload) == []


def test_every_word_on_the_board_is_scanned_tooltips_included(world_copy):
    payload = _payload(world_copy)
    assert audit.board_words_faults(payload) == []
    # AND THE SCAN READS THE TOOLTIPS: a planted one is named by its path.
    planted = {"board": {"games": [{"pick": {"tips": {"prob": "hot rushing_yards lock"}}}]}}
    faults = audit.board_words_faults(planted)
    assert any("a tooltip" in f and "rushing_yards" in f for f in faults), faults
    assert any("hot" in f for f in faults) and any("lock" in f for f in faults)


def test_a_live_row_carries_the_game_and_the_pregame_figure_only(world_copy):
    game = world_copy.execute(
        "SELECT g.id FROM games g JOIN predictions p ON p.game_id = g.id"
        " WHERE g.status = 'scheduled' ORDER BY g.kickoff_utc, g.id LIMIT 1").fetchone()[0]
    world_copy.execute(
        "UPDATE games SET status = 'in', home_score = 10, away_score = 7,"
        " live_period = '2nd Quarter', live_clock = '3:10', live_updated_utc = ?"
        " WHERE id = ?", (views.db.utcnow(), game))
    world_copy.commit()
    payload = _payload(world_copy)
    row = next(g for g in payload["board"]["games"] if g["game_id"] == game)
    assert row["state"] == "live"
    assert row["home"]["score"] == 10 and row["away"]["score"] == 7
    assert row["period_words"] and row["polled_words"] and row["score_words"]
    for block in [row["pick"]] + row["questions"]:
        assert "pregame" in (block.get("pregame_words") or "")
        for field in ("price_words", "pays_words", "size_words", "edge_words"):
            assert field not in block, field
    assert audit.live_card_faults(payload) == []


def test_props_rank_by_cushion_against_the_declared_multiple(world_copy):
    payload = _payload(world_copy)
    props = payload["board"]["props"]
    assert props["multiple"] == config.PICKEM_TWO_PICK_MULTIPLE
    assert props["declared"] == config.PICKEM_TWO_PICK_DECLARED
    assert abs(props["breakeven"] - config.PICKEM_TWO_PICK_MULTIPLE ** -0.5) < 1e-12
    tiles = props["tiles"]
    assert tiles, "the fixture slate has no prop tiles"
    cushions = [t["cushion"] for t in tiles]
    assert cushions == sorted(cushions, reverse=True), "tiles are not ranked by cushion"
    for tile in tiles:
        assert abs(tile["cushion"] - (tile["prob"] - props["breakeven"])) < 1e-9
        # NO VENUE IS READ, and the tile says so in those words.
        assert tile["venue_words"] == "not read yet"
        assert "declared" in tile["tips"]["cushion"] and "not read" in tile["tips"]["cushion"]
        # A PROP WEARS NO OUTLINE for a cushion (the conservative reading).
        assert tile["signal"] in ("none", "won", "lost", "withdrawn")
        assert tile["alt"] is False and (tile["number"] is None or isinstance(tile["number"], int))
    keys = [c["key"] for c in props["chips"]]
    assert keys[:2] == ["", "alt"]
    assert keys[2:] == list(config.SPORT_PROP_MARKETS["nfl"])
    assert any(c["n"] == 0 for c in props["chips"]), "no zero-count family in the fixture"


def test_an_alt_tile_carries_the_high_end_badge_and_the_scan_demands_it():
    words = language.high_end_badge_words(12, 100)
    assert words.startswith("12/100")
    bare = {"board": {"props": {"tiles": [{"signal": "none", "badge_words": "5/100",
                                            "badge_n": 5, "alt": True,
                                            "high_end_badge_words": None}]}}}
    faults = audit.board_signal_faults(bare)
    assert faults and "high-end" in faults[0]


def test_the_jersey_colours_come_from_the_file_and_nothing_is_typed(world_copy):
    payload = _payload(world_copy)
    for tile in payload["board"]["props"]["tiles"]:
        club = tile["club"]
        if club["known"]:
            primary, on_white, how = TEAM_COLOURS["nfl"][club["tricode"]]
            assert club["colour"] == primary
            assert club["secondary"] == (on_white if how == "alternate" else None)
    assert audit.club_hex_faults() == []


def test_the_expanded_row_holds_both_forecasters_and_never_merges_them(world_copy):
    payload = _payload(world_copy)
    forecasters = {q["forecaster"] for g in payload["board"]["games"] for q in g["questions"]}
    assert "statistical" in forecasters
    # THE FIXTURE SEEDS ONE REASONING-PASS ROW; it is on its row, labelled.
    llm = [q for g in payload["board"]["games"] for q in g["questions"] if q["forecaster"] == "llm"]
    assert llm, "the seeded reasoning-pass row is not on the board"
    for q in llm:
        assert q["forecaster_label"] == config.FORECASTER_LABELS["llm"]
    # and the row's PICK is always the page's own forecaster
    for g in payload["board"]["games"]:
        if g["pick"]:
            assert g["pick"]["forecaster"] == payload["forecaster"]


def test_the_breakeven_is_declared_and_dated():
    assert config.PICKEM_TWO_PICK_MULTIPLE > 1
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T00:00:00Z", config.PICKEM_TWO_PICK_DECLARED)
    assert config.PICKEM_LEGS == 2
    assert abs(board.breakeven() - 0.5773502691896257) < 1e-12


# --- the page ------------------------------------------------------------------

def _open_games(page):
    page.set_viewport_size(WIDE)
    page.evaluate("location.hash = '#/games'")
    page.wait_for_selector("#games-rows .game", timeout=15000)
    page.wait_for_timeout(300)


def test_a_tooltip_shows_the_payloads_words_on_hover(page):
    """Explanations live in tooltips on the numbers."""
    _open_games(page)
    words = page.get_attribute("#games-rows .game .meta .badge", "data-tip")
    assert words and "settled" in words
    page.hover("#games-rows .game .meta .badge")
    page.wait_for_function("() => !document.getElementById('tooltip').hidden", timeout=5000)
    shown = page.text_content("#tooltip")
    assert shown.strip() == words.strip()
    assert audit.plain_words_violations(shown) == []


def test_the_jersey_is_drawn_from_the_payload_and_no_hex_is_typed(page):
    page.set_viewport_size(WIDE)
    page.evaluate("location.hash = '#/props'")
    page.wait_for_selector("#props-tiles .prop .jsvg", timeout=15000)
    fills = page.evaluate("""() => [...document.querySelectorAll('#props-tiles .prop .jsvg [fill]')]
        .map(e => e.getAttribute('fill'))""")
    assert fills
    clubs = {p for s in TEAM_COLOURS.values() for p, _o, _h in s.values()}
    for fill in fills:
        assert fill.startswith(("#", "var(", "url(", "none")), fill
    typed = {f.lstrip("#").lower() for f in fills if f.startswith("#")}
    # every hex on the jersey is a club's measured colour handed over by the
    # payload, never one the renderer typed
    assert typed <= clubs, typed - clubs
    names = page.evaluate("[...document.querySelectorAll('#props-tiles .prop .jersey-name')].map(e => e.textContent)")
    assert names and all(n for n in names), names
    # RULING a, 2026-09-25: the number is drawn where the record holds one
    # and the slot stays empty where it does not -- the fixture roster leaves
    # one receiver without a number on purpose.
    drawn = page.evaluate("""[...document.querySelectorAll('#props-tiles .prop')].map(p => ({
        id: p.dataset.id, number: (p.querySelector('.jersey-number') || {}).textContent || null,
        shoulders: p.querySelectorAll('.jersey-shoulder').length }))""")
    tiles = page.evaluate("fetch('/api/week').then(r => r.json()).then(d => d.board.props.tiles.map(t => ({id: String(t.prediction_id), number: t.number})))")
    by_id = {t["id"]: t["number"] for t in tiles}
    assert drawn, "no tiles"
    for d in drawn:
        expected = by_id.get(d["id"])
        if expected is None:
            assert d["number"] is None and d["shoulders"] == 0, f"a number drawn with none on record: {d}"
        else:
            assert d["number"] == str(expected) and d["shoulders"] == 2, f"the number drawn is not the record's: {d} vs {expected}"
    assert any(d["number"] is None for d in drawn) or all(by_id[d["id"]] is not None for d in drawn)


def test_the_entry_rail_reads_the_typed_multiple_and_nothing_is_placed(page):
    page.set_viewport_size(WIDE)
    page.evaluate("location.hash = '#/props'")
    page.wait_for_selector("#props-tiles .prop", timeout=15000)
    assert page.evaluate("document.getElementById('entry-pays').value") == str(config.PICKEM_TWO_PICK_MULTIPLE).rstrip("0").rstrip(".")
    assert page.evaluate("document.querySelectorAll('#entry-lines .entry-line').length") == 0, (
        "lines rendered with no legs")
    assert not page.evaluate("document.getElementById('entry-empty').hidden")
    text = page.text_content("#entry-rail")
    for word in ("placed", "balance"):
        assert word in text
    assert audit.pressure_word_faults(text) == []
    assert not re.search(r"\bslip\b|\bparlay\b", text, re.I)


def test_the_row_expands_in_place_to_every_question_on_the_game(page):
    _open_games(page)
    counts = page.evaluate("""[...document.querySelectorAll('#games-rows .game')].map(g => ({
        said: g.querySelector('.game-count').textContent,
        tiles: g.querySelectorAll('.game-more .q').length,
        open: !g.querySelector('.game-more').hidden }))""")
    for c in counts:
        assert not c["open"]
        n = int(re.match(r"(\d+)", c["said"]).group(1))
        assert n == c["tiles"], c
    page.click("#games-rows .game .game-head")
    page.wait_for_function("() => !document.querySelector('#games-rows .game .game-more').hidden", timeout=5000)
    assert page.get_attribute("#games-rows .game .car", "aria-expanded") == "true"


def test_a_settled_pick_is_painted_solid_and_its_words_are_ink(page):
    """THE FILL IS ON THE PAGE, not only in the payload. The first render of
    this lost to the tile's own ground -- both rules one class deep, the
    tile's declared later -- and no test saw it; a computed-style probe did."""
    _open_games(page)
    page.evaluate("document.querySelector('.week-more').open = true")
    options = page.evaluate("[...document.querySelectorAll('#week-picker option')].map(o => o.value)")
    with page.expect_response(lambda r: "/api/week" in r.url, timeout=20000):
        page.select_option("#week-picker", options[-1])
    page.wait_for_selector("#games-rows .game.game-final", timeout=15000)
    page.click("#games-rows .game .game-head")
    page.wait_for_function("() => !document.querySelector('#games-rows .game .game-more').hidden", timeout=5000)
    painted = page.evaluate("""() => {
        const rgb = (h) => 'rgb(' + [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16)).join(', ') + ')';
        const r = getComputedStyle(document.documentElement);
        const win = rgb(r.getPropertyValue('--win').trim().toLowerCase());
        const loss = rgb(r.getPropertyValue('--loss').trim().toLowerCase());
        const ink = rgb(r.getPropertyValue('--ink').trim().toLowerCase());
        return [...document.querySelectorAll('#games-rows .pick.sig-won, #games-rows .pick.sig-lost, #games-rows .q.sig-won, #games-rows .q.sig-lost')]
            .map(e => ({ cls: e.className, bg: getComputedStyle(e).backgroundColor,
                         line: getComputedStyle(e.querySelector('.pick-line, .q-line')).color,
                         win, loss, ink }));
    }""")
    assert painted, "the settled slate painted no verdict"
    for p in painted:
        want = p["win"] if "sig-won" in p["cls"] else p["loss"]
        assert p["bg"] == want, f"{p['cls']} is painted {p['bg']}, not its fill {want}"
        assert p["line"] == p["ink"], f"the words on a fill are {p['line']}, not the ink"


def test_the_roster_file_fills_player_numbers_and_never_guesses(league, monkeypatch):
    """RULING a, 2026-09-25: jersey numbers come from nflverse's roster file,
    keyed by the id the stats file already carries, at the NFL refresh. A row
    with no number is stored as NULL and drawn as an empty slot."""
    from gridiron.data import loader, sources

    rows = [
        {"season": "2025", "team": "KC", "gsis_id": "QB-KC", "jersey_number": "15", "full_name": "KC Quarterback"},
        {"season": "2025", "team": "KC", "gsis_id": "WR-KC", "jersey_number": "", "full_name": "KC Receiver"},
        {"season": "2025", "team": "", "gsis_id": "X", "jersey_number": "1"},
    ]
    seen = []
    monkeypatch.setattr(sources, "fetch_csv", lambda conn, url, **kw: seen.append(url) or rows)
    n = loader.load_rosters(league, 2025)
    assert n == 2 and seen == [sources.ROSTERS_URL.format(season=2025)]
    got = dict(league.execute("SELECT player_id, jersey_number FROM player_numbers WHERE team = 'KC'").fetchall())
    assert got["QB-KC"] == 15 and got["WR-KC"] is None
    from gridiron import board
    assert board._player_number(league, "nfl", "KC Quarterback", "KC") == 15
    assert board._player_number(league, "nfl", "KC Receiver", "KC") is None
    assert board._player_number(league, "nfl", "KC Quarterback", "BUF") is None, "a number followed the name to another club"
    assert config.ROSTER_NUMBERS_DECLARED.endswith("Z")


def test_a_priced_question_carries_its_price_in_words_and_as_a_number():
    """CAUGHT BY LOOKING, 2026-09-25: a priced row said "venue has not listed
    this yet" beside a payout, because the Today card carried the words and
    the payout and not the price. The block reads the number now, and a live
    row carries neither number nor words."""
    card = {"prediction_id": 1, "market": "total", "market_type": "total",
            "shown_prob": 0.64, "phrase": "over 41.5", "side_words": "over 41.5",
            "line_asked": 41.5, "subject": "over", "model_side": "over"}
    entry = {"price": 0.54, "payout": 1.85, "group": "clears", "edge_cents": 8.0,
             "edge_line_words": "+8.0¢"}
    block = board._question_block(card, entry, state="upcoming", taken=False,
                                  forecaster="statistical", n_settled=12, hours=3.0,
                                  unit_dollars=None)
    assert block["price"] == 0.54 and block["pays"] == 1.85
    assert "54" in block["price_words"] and "not listed" not in block["price_words"]
    assert block["pays_words"]
    live = board._question_block(card, entry, state="live", taken=False,
                                 forecaster="statistical", n_settled=12, hours=3.0,
                                 unit_dollars=None)
    assert live["price"] is None and live["pays"] is None
    for field in audit.LIVE_FORBIDDEN:
        assert not live.get(field), field


def test_the_rail_verdict_wears_the_colour_a_prop_earns_from_the_typed_multiple(page):
    """RULING c, 2026-09-25: a prop tile wears no outline; the entry rail's
    verdict, from the multiple the operator typed, is where the colour is
    earned -- and it never stands without a leg's record badge beside it."""
    page.set_viewport_size(WIDE)
    page.evaluate("location.hash = '#/props'")
    page.wait_for_selector("#props-tiles .prop[data-state='upcoming'] .chk", timeout=15000)
    assert page.evaluate(
        "[...document.querySelectorAll('#props-tiles .prop')].every(p => !p.classList.contains('sig-clears') && !p.classList.contains('sig-costs'))"), \
        "a prop tile wears an outline"
    with page.expect_response(lambda r: "/api/taken/" in r.url, timeout=20000):
        page.click("#props-tiles .prop[data-state='upcoming'] .chk")
    page.wait_for_selector("#entry-legs .entry-leg", timeout=15000)
    def verdict(multiple):
        page.fill("#entry-pays", str(multiple))
        page.wait_for_timeout(200)
        return page.evaluate("""() => { const v = document.querySelector('#entry-lines .verdict');
            return { cls: v ? v.className : null, words: v ? v.textContent : '',
                     badge: v ? !!v.querySelector('.badge') : false }; }""")
    high = verdict(9)
    assert "sig-clears" in high["cls"] and high["badge"], high
    assert "Clears the bar" in high["words"] and "9" in high["words"]
    low = verdict(1.1)
    assert "sig-costs" in low["cls"] and low["badge"], low
    assert "Falls short" in low["words"]
    assert "worth" not in (high["words"] + low["words"]).lower()


# --- 3a, 3b, 3c (visual pass, 2026-09-25) --------------------------------------

def test_my_day_holds_the_taken_picks_and_never_money(world_copy):
    """3b: chips for the taken picks on the slate, counts of picks, and not a
    stake, payout or total anywhere on them."""
    from gridiron import db
    pid = world_copy.execute(
        "SELECT p.id FROM predictions p JOIN games g ON g.id = p.game_id"
        " WHERE g.status = 'scheduled' AND p.predictor = 'statistical' ORDER BY p.id LIMIT 1").fetchone()[0]
    world_copy.execute("INSERT INTO picks_taken (prediction_id, taken_utc) VALUES (?, ?)", (pid, db.utcnow()))
    world_copy.commit()
    day = _payload(world_copy)["board"]["my_day"]
    assert day["n"] >= 1 and any(e["prediction_id"] == pid for e in day["entries"])
    for e in day["entries"]:
        assert e["status_words"] in ("upcoming", "won", "lost", "settled", "withdrawn") or e["status_words"].startswith("live")
        assert e["badge_words"] and e["club"]["tricode"]
        for key in e:
            assert "stake" not in key and "payout" not in key and "total" not in key and "size" not in key, key
    words = " ".join(str(v) for e in day["entries"] for v in e.values() if isinstance(v, str)) + day["counts_words"]
    assert "$" not in words and "stake" not in words.lower() and "payout" not in words.lower()
    assert audit.board_words_faults({"board": {"my_day": day}}) == []


def test_the_detail_panel_says_every_absence_in_words(world_copy):
    """3a: form from the record's own finished games, injuries, weather and
    factors; each absent thing says so, nothing is fetched."""
    games = _payload(world_copy)["board"]["games"]
    assert games
    for g in games:
        d = g["detail"]
        for side in ("home", "away"):
            marks = d[f"{side}_form_marks"]
            assert all(m in ("W", "L", "D") for m in marks) and len(marks) <= 5
            assert d[f"{side}_form_words"] and d[f"{side}_form_tip"]
        assert d["injuries_words"]
        assert d["weather_words"]
        assert d["factors"] or d["factors_words"]
        for f in d["factors"]:
            assert f["factor_words"] and "_" not in f["factor_words"], f


def test_the_controls_bar_is_the_one_declared_row():
    """3c: the sort-and-filter bar is declared by name and a second row is
    still a fault."""
    assert audit.picks_control_row_faults() == []
    assert audit.PICKS_CONTROL_ROWS == ("games-controls",)


def test_sort_and_filter_persist_and_the_clears_filter_speaks_when_empty(page):
    page.set_viewport_size(WIDE)
    page.evaluate("location.hash = '#/games'")
    page.wait_for_selector("#games-rows .game", timeout=15000)
    page.wait_for_selector("#games-sort option", state="attached", timeout=15000)
    with page.expect_response(lambda r: "/api/week" in r.url, timeout=20000):
        page.select_option("#games-sort", "prob")
    page.wait_for_timeout(300)
    probs = page.evaluate("[...document.querySelectorAll('#games-rows .game .pick-prob')].map(e => parseFloat(e.textContent))")
    assert probs == sorted(probs, reverse=True), probs
    assert page.evaluate("(() => { try { return localStorage.getItem('gridiron.games.sort'); } catch (e) { return 'refused'; } })()") in ("prob", "refused")
    with page.expect_response(lambda r: "/api/week" in r.url, timeout=20000):
        page.check("#games-clears")
    page.wait_for_timeout(300)
    rows = page.evaluate("[...document.querySelectorAll('#games-rows .game')].map(g => g.querySelector('.pick').className)")
    assert all("sig-clears" in c for c in rows), rows
    if not rows:
        assert page.text_content("#games-notes").strip(), "the filter hid every row and said nothing"
    with page.expect_response(lambda r: "/api/week" in r.url, timeout=20000):
        page.uncheck("#games-clears")
    with page.expect_response(lambda r: "/api/week" in r.url, timeout=20000):
        page.select_option("#games-sort", "time")
    page.wait_for_timeout(300)


def test_a_my_day_chip_scrolls_to_its_game(page):
    page.set_viewport_size({"width": 1300, "height": 500})
    page.evaluate("location.hash = '#/games'")
    page.wait_for_selector("#games-rows .game", timeout=15000)
    chip = page.query_selector("#my-day .my-chip:not(.sig-won):not(.sig-lost)")
    if chip is None:
        with page.expect_response(lambda r: "/api/taken/" in r.url, timeout=20000):
            page.click("#games-rows .game[data-state='upcoming'] .meta .chk")
        page.wait_for_selector("#my-day .my-chip", timeout=15000)
    page.evaluate("window.scrollTo(0, 0)")
    page.click("#my-day .my-chip")
    page.wait_for_timeout(200)
    top = page.evaluate("""() => { const c = document.querySelector('#my-day .my-chip'); return null; }""")
    assert page.evaluate("window.scrollY") > 0, "tapping a chip did not move to its game"
    assert " taken" in page.text_content("#my-day-counts")
    strip = page.text_content("#my-day")
    assert "$" not in strip and "stake" not in strip.lower()


def test_stale_rows_never_read_as_settled_while_a_new_slate_is_fetched(page):
    """THE ORDER-DEPENDENT FAILURE OF 2026-09-25, at its root: the rows were
    cleared only after the answer arrived, so during a fetch the previous
    render stood on the page as current -- a reader could open a row the
    answer then replaced under them, and two tests measured exactly that.
    Now the container is in its arriving state from the moment a slate is
    asked for until the new rows land."""
    page.set_viewport_size(WIDE)
    page.evaluate("location.hash = '#/games'")
    page.wait_for_selector("#games-rows .game", timeout=15000)
    page.wait_for_function("getComputedStyle(document.getElementById('games-rows')).opacity === '1'", timeout=5000)
    held = []

    def slow(route):
        held.append(route)   # answered later, by hand

    page.route("**/api/week*", slow)
    page.evaluate("location.hash = '#/record'")
    page.wait_for_timeout(200)
    page.evaluate("location.hash = '#/games'")
    page.wait_for_function("document.getElementById('games-rows').classList.contains('arriving')", timeout=5000)
    assert page.evaluate("getComputedStyle(document.getElementById('games-rows')).opacity") == "0", (
        "the old rows read as the current slate while the new one was still being fetched")
    assert page.evaluate("getComputedStyle(document.getElementById('games-rows')).pointerEvents") == "none", (
        "the old rows could still be tapped while the new slate was being fetched")
    for r in held:
        r.continue_()
    page.unroute("**/api/week*")
    page.wait_for_function("!document.getElementById('games-rows').classList.contains('arriving') && document.querySelectorAll('#games-rows .game').length > 0", timeout=15000)
    page.wait_for_function("getComputedStyle(document.getElementById('games-rows')).opacity === '1'", timeout=5000)
