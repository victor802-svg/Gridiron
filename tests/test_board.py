"""The board (GRIDIRON_BOARD, operator ruling 2026-09-24).

What the Games rows and the Props tiles promise, asserted on the browser
suite's own world and in a real Chromium: a signal never renders without its
badge; every word a reader meets, tooltips included, is scanned; a live row
carries the score and the pregame figure and nothing that can be acted on;
each prop tile is one player and one stat, with no break-even until the
operator types a payout and no main line while the venue's prop ladders are
not read (operator ruling C, 2026-10-05; until then the props ranked by a
cushion against a declared multiple); the jersey is drawn from the measured
colours and nothing typed.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta

import pytest

from gridiron import audit, board, calibration, config, language, views
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
        # AND NO CHANCE BESIDE THE PREGAME FIGURE (LIVE TAB, re-homed by the
        # board merge, 2026-09-29): the payload carried `prob` and
        # `prob_words` on a live row, which the row never drew.
        assert "prob" not in block and "prob_words" not in block, block
    assert audit.live_card_faults(payload) == []
    assert audit.live_tab_faults(payload) == []


def test_props_are_legs_with_no_breakeven_until_a_payout_is_typed(world_copy):
    """OPERATOR RULING C (2026-10-05; built 2026-10-06). Until this date the
    tiles ranked by a cushion against the declared 3x
    (`config.PICKEM_TWO_PICK_MULTIPLE`, gone) and every tile showed "57.7% to
    break even". Now each upcoming tile is a leg: its projection, the venue's
    main line (none while the venue's prop ladders are not read), the
    break-even of each typed power payout (none typed in the fixture, so none
    shown, and the page asks), no pick, and "Nothing worth taking today"."""
    payload = _payload(world_copy)
    props = payload["board"]["props"]
    for gone in ("multiple", "declared", "breakeven", "legs", "alt_empty_words"):
        assert gone not in props, gone
    assert not hasattr(config, "PICKEM_TWO_PICK_MULTIPLE")
    tiles = props["tiles"]
    assert tiles, "the fixture slate has no prop tiles"
    assert props["payouts"]["typed"] is False
    assert [e["multiple"] for e in props["payouts"]["entries"]] == [None, None]
    assert "Type what a 2-pick power entry and a 3-pick power entry pay" in (
        props["payouts"]["ask_words"])
    assert props["nothing_words"] == "Nothing worth taking today"
    assert props["ladder"]["rows"] == [] and props["ladder"]["empty_words"]
    for tile in tiles:
        for gone in ("cushion", "cushion_words", "breakeven_words", "venue_words"):
            assert gone not in tile, gone
        assert tile["signal"] in ("none", "won", "lost", "withdrawn")
        assert tile["multiple_source"] == "untyped"
        assert tile["alt"] is False and (tile["number"] is None or isinstance(tile["number"], int))
        if tile["state"] != "upcoming":
            continue
        assert tile["pick"] is False and tile["pick_words"] is None
        assert tile["main_line"] is None and tile["main_chance"] is None
        assert tile["main_words"] == "not listed by the venue"
        assert [e["legs"] for e in tile["entries"]] == [2, 3]
        for e in tile["entries"]:
            assert e["breakeven"] is None and e["edge"] is None and not e["clears"]
            assert e["breakeven_words"].endswith("payout not typed")
        assert tile["own_question_words"].startswith("The model's own question: ")
    keys = [c["key"] for c in props["chips"]]
    assert keys[:2] == ["", "ladder"]
    assert keys[2:] == list(config.SPORT_PROP_MARKETS["nfl"])
    assert any(c["n"] == 0 for c in props["chips"]), "no zero-count family in the fixture"
    assert audit.props_board_faults(payload, typed=audit._typed_pickem_payouts(world_copy)) == []


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


def test_the_breakeven_is_a_typed_power_payouts():
    """C.3 (2026-10-05) and reading (c): a leg of a power entry of N legs
    paying M breaks even at M**(-1/N), of a payout the operator typed; the
    bar is B.2's three points, dated."""
    assert abs(board.breakeven(3, 2) - 0.5773502691896257) < 1e-12
    assert abs(board.breakeven(6, 3) - 6 ** (-1 / 3)) < 1e-12
    assert config.PICKEM_POWER_ENTRIES == ((2, "pickem_two_pick_power"),
                                           (3, "pickem_three_pick_power"))
    assert config.PICK_MIN_EDGE == audit.PICK_MIN_EDGE_AS_RULED == 0.03
    assert config.PICK_MIN_EDGE_RULED == "2026-10-05"
    for name in ("PICKEM_TWO_PICK_MULTIPLE", "PICKEM_TWO_PICK_DECLARED", "PICKEM_LEGS"):
        assert not hasattr(config, name), name


# --- the page ------------------------------------------------------------------

def _open_games(page):
    # THE REDRAW THE HASH STARTS, WAITED FOR INSIDE THE PAGE (the board
    # merge, 2026-09-29): this waited 300ms after the first row appeared,
    # which the render before the hash change had already drawn. The clock
    # register only shrinks; question 28's helper is the signal.
    from tests.conftest import wait_for_the_redraw_it_starts

    page.set_viewport_size(WIDE)
    with wait_for_the_redraw_it_starts(page):
        page.evaluate("location.hash = '#/games'")
    page.wait_for_selector("#games-rows .game", timeout=15000)


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
    # AND A READER CAN READ IT (the board merge, 2026-09-29, found by looking
    # at the render): the words were drawn in the page's own colour on the
    # panel's, dark on dark. The text colour of every other word on the page,
    # at a contrast of 4.5 to 1 or more against the box.
    got = page.evaluate("""() => {
        const box = document.getElementById('tooltip');
        const rgb = s => s.match(/[\\d.]+/g).slice(0, 3).map(Number);
        const lum = ([r, g, b]) => [r, g, b].map(v => { v /= 255;
            return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); })
            .reduce((a, v, i) => a + v * [0.2126, 0.7152, 0.0722][i], 0);
        const cs = getComputedStyle(box);
        const probe = document.createElement('span');
        document.body.appendChild(probe);
        probe.style.color = 'var(--chrome)';
        const chrome = getComputedStyle(probe).color;
        probe.remove();
        const a = lum(rgb(cs.color)), b = lum(rgb(cs.backgroundColor));
        return { colour: cs.color, chrome,
                 ratio: (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05) }; }""")
    assert got["colour"] == got["chrome"], got
    assert got["ratio"] >= 4.5, got


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
    # NO PAYOUT IS FILLED IN THAT NOBODY TYPED (operator ruling C.3,
    # 2026-10-05): the field held the declared 3x until 2026-10-06. FROM THE
    # ENTRY CHECK'S STEP 1 (2026-10-07; readings (e) and (f)) the rail is
    # "Check an entry": no app is chosen for him, so nothing is filled; no box
    # is ticked; and nothing is answered before he asks.
    page.wait_for_selector("#entry-payout .entry-pays-rows input", timeout=15000)
    assert page.input_value("#entry-payout .entry-pays-rows input") == ""
    assert not page.is_checked("#entry-payout .entry-confirm input")
    assert page.evaluate("document.getElementById('entry-lines').children.length") == 0, (
        "an answer drawn before the entry was checked")
    text = page.text_content("#entry-rail")
    # "placed" stays: nothing is placed. "balance" went with the rail's old
    # note (2026-10-07), whose readings at the model's chance are gone; the
    # entry check's note says units only, never dollars.
    for word in ("placed", "Units only"):
        assert word in text
    assert audit.pressure_word_faults(text) == []
    assert not re.search(r"\bslip\b|\bparlay\b|\bboost|\bsame[- ]game\b", text, re.I)


def test_the_row_expands_in_place_to_every_question_on_the_game(page):
    _open_games(page)
    counts = page.evaluate("""[...document.querySelectorAll('#games-rows .game')].map(g => ({
        said: g.querySelector('.game-count').textContent,
        tiles: g.querySelectorAll('.game-more .q').length,
        open: !g.querySelector('.game-more').hidden }))""")
    for c in counts:
        assert not c["open"]
        # EACH FORECASTER'S COUNT, SAID APART (the merge's prover,
        # 2026-09-29): "3 questions from the model · 1 from the reasoning
        # pass" heads four tiles.
        n = sum(int(x) for x in re.findall(r"\d+", c["said"]))
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


def test_the_roster_numbers_are_named_only_where_declared_loaded_and_drawn():
    """THE OPERATOR'S RULING OF 2026-09-29: "player_numbers: a loaded roster
    table, refreshed each load, not append-only; say so in its description.
    ... It is display only: nothing that forecasts, grades, fits or measures
    may read it, and a scan refuses any such read." The package passes the
    scan (gate step 2); the allow-list names the schema's declaration, the
    loader's write and its tally, the jersey's read and the scan's own name,
    and nothing that may never name the table; and the description says what
    the table is, in the schema and in the loader."""
    assert audit.roster_numbers_read_faults() == []
    import ast
    source = (config.REPO_ROOT / "tools" / "verify.py").read_text(encoding="utf-8")
    step = next(node for node in ast.parse(source).body
                if isinstance(node, ast.FunctionDef) and node.name == "step_2_guards")
    assert ("audit.check_the_roster_numbers_are_display_only"
            in ast.get_source_segment(source, step)), "gate step 2 does not run the scan"
    assert set(audit.ROSTER_NUMBERS_ALLOWED) == {
        ("gridiron/schema.sql", "table player_numbers"),
        ("gridiron/data/loader.py", "load_rosters"),
        ("gridiron/data/loader.py", "load_all"),
        ("gridiron/board.py", "_player_number"),
        ("gridiron/audit.py", "module level"),
    }
    never = audit._roster_numbers_never(config.PACKAGE_ROOT)
    for where, _function in audit.ROSTER_NUMBERS_ALLOWED:
        assert audit._roster_never_why(never, where) is None, where
    # EVERY MODULE LAW 1 WALKS may never name it, and the measuring ones.
    for where in ("gridiron/model/predict.py", "gridiron/db.py", "gridiron/calibration.py",
                  "gridiron/priced/shape.py", "gridiron/market/recommend.py",
                  "gridiron/shortlist.py", "gridiron/resolve.py"):
        assert audit._roster_never_why(never, where), where
    schema = (config.PACKAGE_ROOT / "schema.sql").read_text(encoding="utf-8")
    comment = schema[:schema.index("CREATE TABLE IF NOT EXISTS player_numbers")]
    comment = comment[comment.rindex("\n\n"):]
    from gridiron.data import loader
    for text in (comment, loader.load_rosters.__doc__):
        flat = " ".join(text.replace("--", " ").split()).lower()
        for words in ("a loaded roster", "refreshed at each load",
                      "not append-only", "display only"):
            assert words in flat, (words, flat)


def test_the_roster_scan_sees_the_name_by_another_name(tmp_path):
    """THE PROVER OF THE RULING OF 2026-09-29. Each of these read the
    roster's numbers where nothing that forecasts, grades, fits or measures
    may, and the scan as first built said nothing to any: the scan's own
    constant, imported under an alias or read off the module, in an f-string;
    `board._player_number`, the jersey's reader, imported or looked up by
    `getattr`; the whole name written in constants a template is filled in
    with (`.format`, `%`); and the constant in a function of the audit that
    is not the scan. Each is refused by name now -- and a page may still
    call the jersey's reader, and a template filled in with other words
    names nothing."""
    import shutil
    root = tmp_path / "gridiron"
    shutil.copytree(config.PACKAGE_ROOT, root,
                    ignore=shutil.ignore_patterns("__pycache__"))
    plants = {
        "calibration.py": (
            "def by_an_alias(conn):\n"
            "    from gridiron.audit import ROSTER_NUMBERS_TABLE as shirts\n"
            "    return conn.execute(f'SELECT * FROM {shirts}')\n"),
        "drift.py": (
            "def read_off_the_audit(conn):\n"
            "    from gridiron import audit as gate\n"
            "    return conn.execute('SELECT * FROM ' + gate.ROSTER_NUMBERS_TABLE)\n"),
        "shortlist.py": (
            "def through_the_jersey(conn, player_id):\n"
            "    from gridiron.board import _player_number as number\n"
            "    return number(conn, player_id)\n"),
        "horizon.py": (
            "def through_getattr(conn, player_id):\n"
            "    import gridiron.board as page\n"
            "    return getattr(page, '_player_number')(conn, player_id)\n"),
        "recount.py": (
            "def formatted(conn):\n"
            "    return conn.execute('SELECT * FROM {}_{}'.format('player', 'numbers'))\n"
            "def formatted_with_other_words(conn):\n"
            "    return conn.execute('SELECT * FROM {}_{}'.format('player', 'games'))\n"),
        "correction.py": (
            "def by_percent(conn):\n"
            "    return conn.execute('SELECT * FROM %(a)s_%(b)s' % {'a': 'player', 'b': 'numbers'})\n"),
        "audit.py": (
            "def in_the_gate(conn):\n"
            "    return conn.execute(f'SELECT * FROM {ROSTER_NUMBERS_TABLE}')\n"),
        "views.py": (
            "def a_page_drawing_the_jersey(conn, player_id):\n"
            "    from gridiron.board import _player_number\n"
            "    return _player_number(conn, player_id)\n"),
    }
    for module, text in plants.items():
        path = root / module
        path.write_text(path.read_text(encoding="utf-8") + "\n\n" + text,
                        encoding="utf-8")
    faults = audit.roster_numbers_read_faults(root)
    wanted = {
        "(by_an_alias)": "the calibration",
        "(read_off_the_audit)": "the drift record",
        "(through_the_jersey)": "names `_player_number`",
        "(through_getattr)": "names `_player_number`",
        "(formatted)": "the recounts",
        "(by_percent)": "the correction",
        "(in_the_gate)": "does not list",
    }
    for marker, words in wanted.items():
        assert any(marker in f and words in f for f in faults), (marker, faults)
    assert all(any(marker in f for marker in wanted) for f in faults), faults


def test_a_priced_question_carries_its_price_in_words_and_as_a_number():
    """CAUGHT BY LOOKING, 2026-09-25: a priced row said "venue has not listed
    this yet" beside a payout, because the Today card carried the words and
    the payout and not the price. The block reads the number now, and a live
    row carries neither number nor words."""
    card = {"prediction_id": 1, "market": "total", "market_type": "total",
            "shown_prob": 0.64, "phrase": "over 41.5", "side_words": "over 41.5",
            "line_asked": 41.5, "subject": "over", "model_side": "over"}
    # THE SIDE IS PLACED, as every priced entry's is (the ruling of
    # 2026-09-30): an over names the claim's own proposition. A priced entry
    # with no placed side is refused by the block, by name
    # (test_the_side_is_placed.py).
    # THE CONTRACT'S WORDS TRAVEL WITH ITS NUMBERS (pick-number step A,
    # 2026-09-30): a Today card carries the words of the contract its numbers
    # belong to, and the block draws them -- here the question's own line.
    entry = {"price": 0.54, "payout": 1.85, "group": "clears", "edge_cents": 8.0,
             "edge_line_words": "+8.0¢", "question_takes_the_proposition": True,
             "line_words": "Over 41.5 total", "question": "over 41.5"}
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


def _ladder_at_each_own_line(conn, sport, cards):
    """The venue's ladder HANDED IN, in the test server's process only (no
    prop ladder is read on any record -- operator ruling C's measurement of
    2026-10-06): the rung priced nearest an even chance at each prop
    question's own line, so its leg's chance at the main line is the
    model's own answer."""
    out = {}
    for c in cards:
        if c.get("line_asked") is None:
            continue
        line = float(c["line_asked"])
        out[board.ladder_key(c)] = [{"line": line - 10.0, "price": 0.74, "ticker": "lo"},
                                    {"line": line, "price": 0.52, "ticker": "main"},
                                    {"line": line + 10.0, "price": 0.27, "ticker": "hi"}]
    return out, None


def test_the_rail_verdict_wears_the_colour_a_prop_earns_from_the_typed_multiple(page, monkeypatch):
    """RULING c, 2026-09-25: a prop tile wears no outline against an assumed
    multiple; the entry rail's verdict, from the multiple the operator typed,
    is where the colour is earned. FROM RULING C (2026-10-05) a leg's chance
    was the model's chance at its main line, so the venue's ladder is handed
    in.

    FROM THE ENTRY CHECK'S STEP 1 (2026-10-07; reading (h)) THE RAIL IS THE
    ENTRY CHECK and has no model: its verdict wears the colour reading (h)
    gives the payout he typed and confirmed for the entry, at an even chance
    on every leg -- green where each leg's break-even is three points or more
    under an even chance, red where the entry returns less than it costs,
    none between -- and the outline is the server's. Until that date the
    verdict read the model's chance on each leg's main line beside the
    thinnest leg's record badge; the verdict now rests on no record (its
    note says so, "No model and no record is behind these numbers"), so no
    record badge stands beside it. The payout he confirms is not kept here
    (`entry_check.remember` answers that nothing was written), so the shared
    world is not written."""
    from gridiron import entry_check

    monkeypatch.setattr(board, "_venue_prop_ladders", _ladder_at_each_own_line)
    monkeypatch.setattr(entry_check, "remember", lambda conn, form: False)
    page.set_viewport_size(WIDE)
    page.evaluate("location.hash = '#/props'")
    page.wait_for_selector("#props-tiles .prop[data-state='upcoming'] .chk", timeout=15000)
    assert page.evaluate(
        "[...document.querySelectorAll('#props-tiles .prop')].every(p => !p.classList.contains('sig-clears') && !p.classList.contains('sig-costs'))"), \
        "a prop tile wears an outline"
    page.wait_for_selector("#entry-legs .entry-leg", timeout=15000)
    page.select_option("#entry-form .entry-head-row select >> nth=0", "underdog")
    for i in range(2):
        leg = f"#entry-legs .entry-leg >> nth={i} >> input"
        page.fill(f"{leg} >> nth=0", f"A Player {i + 1}")
        page.fill(f"{leg} >> nth=1", "passing yards")
        page.fill(f"{leg} >> nth=2", "250.5")

    def verdict(multiple, breakeven):
        page.fill("#entry-payout .entry-pays-rows input", str(multiple))
        page.check("#entry-payout .entry-confirm input")
        page.click("#entry-check")
        # THE ANSWER FOR THIS PAYOUT, read when the rail says it: its
        # break-even per leg is drawn beside it.
        page.wait_for_function(
            "(b) => { const v = document.querySelector('#entry-lines .verdict');"
            " return !!v && document.getElementById('entry-lines').textContent.includes(b); }",
            arg=breakeven, timeout=10000)
        return page.evaluate("""() => { const v = document.querySelector('#entry-lines .verdict');
            return { cls: v.className, words: v.textContent,
                     badge: !!document.querySelector('#entry-lines .badge') }; }""")

    clears = verdict(5, "44.72%")
    assert "sig-clears" in clears["cls"] and not clears["badge"], clears
    assert clears["words"].startswith("Clears the bar at coin flips")
    between = verdict(4.5, "47.14%")
    assert "sig-clears" not in between["cls"] and "sig-costs" not in between["cls"], between
    assert between["words"].startswith("No outline")
    costs = verdict(3, "57.74%")
    assert "sig-costs" in costs["cls"], costs
    assert costs["words"].startswith("Costs at coin flips")
    assert "worth" not in (clears["words"] + between["words"] + costs["words"]).lower()
    assert not page.page_errors, page.page_errors


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
    # EACH REDRAW WAITED FOR INSIDE THE PAGE (the board merge, 2026-09-29):
    # this waited 300ms after each answer, three times; the answer lands
    # before its render does, and question 28's helper waits for the render's
    # arrival to start and end. The clock register only shrinks.
    from tests.conftest import wait_for_the_redraw_it_starts

    page.set_viewport_size(WIDE)
    with wait_for_the_redraw_it_starts(page):
        page.evaluate("location.hash = '#/games'")
    page.wait_for_selector("#games-rows .game", timeout=15000)
    page.wait_for_selector("#games-sort option", state="attached", timeout=15000)
    # NEVER BY THE MODEL'S CHANCE (operator ruling B.1, 2026-10-05; built
    # 2026-10-07): the sort offers the start time and the edge, and "edge"
    # puts the rows a pick leads first by its edge and keeps every other row
    # in its start order. Until then this chose "the model's chance" and held
    # the rows to it.
    options = page.evaluate("[...document.querySelectorAll('#games-sort option')].map(o => o.value)")
    assert options == ["time", "edge"], options
    with wait_for_the_redraw_it_starts(page):
        page.select_option("#games-sort", "edge")
    order = page.evaluate("[...document.querySelectorAll('#games-rows .game')].map(g => g.dataset.game)")
    want = page.evaluate(
        "(() => { const gs = window.Gridiron.state.slate.board.games"
        ".filter(g => (g.questions || []).length);"
        " const e = g => (g.pick && g.pick.pick) ? g.pick.edge_points : null;"
        " const picks = gs.filter(g => e(g) !== null).sort((a, b) => e(b) - e(a));"
        " return picks.concat(gs.filter(g => e(g) === null)).map(g => g.game_id); })()")
    assert order == want, (order, want)
    assert page.evaluate("(() => { try { return localStorage.getItem('gridiron.games.sort'); } catch (e) { return 'refused'; } })()") in ("edge", "refused")
    with wait_for_the_redraw_it_starts(page):
        page.check("#games-clears")
    rows = page.evaluate("[...document.querySelectorAll('#games-rows .game')].map(g => g.querySelector('.pick').className)")
    assert all("sig-clears" in c for c in rows), rows
    if not rows:
        # "PICKS ONLY" WITH NO PICK: the page says "Nothing worth taking
        # today" above the rows (B.4, 2026-10-07), where the notes said the
        # old sentence.
        said = (page.text_content("#games-nothing") or "").strip()
        assert said or page.text_content("#games-notes").strip(), \
            "the filter hid every row and said nothing"
    with wait_for_the_redraw_it_starts(page):
        page.uncheck("#games-clears")
    with wait_for_the_redraw_it_starts(page):
        page.select_option("#games-sort", "time")


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
    # THE PAGE SAYS IT MOVED (the board merge, 2026-09-29): this waited 200ms
    # and then read the scroll; the chip scrolls at once, so the reading is
    # the signal, with an upper limit only.
    page.wait_for_function("window.scrollY > 0", timeout=5000)
    assert page.evaluate("window.scrollY") > 0, "tapping a chip did not move to its game"
    assert " taken" in page.text_content("#my-day-counts")
    strip = page.text_content("#my-day")
    assert "$" not in strip and "stake" not in strip.lower()


def test_stale_rows_never_read_as_settled_while_a_new_slate_is_fetched(page):
    """THE ORDER-DEPENDENT FAILURE OF 2026-09-25, at its root: the rows were
    cleared only after the answer arrived, so during a fetch the previous
    render stood on the page as current -- a reader could open a row the
    answer then replaced under them, and two tests measured exactly that.
    RULED the same day: the previous rows stay on screen, dimmed, untouchable
    and marked busy, with an "updating" label, until the new ones land."""
    page.set_viewport_size(WIDE)
    page.evaluate("location.hash = '#/games'")
    page.wait_for_selector("#games-rows .game", timeout=15000)
    page.wait_for_function("getComputedStyle(document.getElementById('games-rows')).opacity === '1'", timeout=5000)
    held = []
    page.route("**/api/week*", lambda route: held.append(route))
    page.evaluate("location.hash = '#/record'")
    # THE RECORD PAGE IS ON SCREEN, read off the page (the board merge,
    # 2026-09-29): this waited 200ms for the route to change.
    page.wait_for_selector("#view-record:not([hidden])", timeout=10000)
    page.evaluate("location.hash = '#/games'")
    page.wait_for_function("document.getElementById('games-rows').classList.contains('updating')", timeout=5000)
    probe = page.evaluate("""() => { const rows = document.getElementById('games-rows');
        const cs = getComputedStyle(rows);
        return { rows: rows.querySelectorAll('.game').length, opacity: cs.opacity, pointer: cs.pointerEvents,
                 busy: rows.getAttribute('aria-busy'), label: document.getElementById('games-updating').textContent,
                 labelShown: !document.getElementById('games-updating').hidden }; }""")
    assert probe["rows"] > 0, "the slate went empty during a fetch although a previous render existed"
    assert probe["pointer"] == "none", "the old rows could still be tapped while the new slate was being fetched"
    assert probe["busy"] == "true" and probe["labelShown"] and probe["label"], probe
    assert 0 < float(probe["opacity"]) < 1, "the old rows read as the current slate while the new one was still being fetched"
    for r in held:
        r.continue_()
    page.unroute("**/api/week*")
    page.wait_for_function("!document.getElementById('games-rows').classList.contains('updating') && document.querySelectorAll('#games-rows .game').length > 0", timeout=15000)
    page.wait_for_function("getComputedStyle(document.getElementById('games-rows')).opacity === '1'", timeout=5000)
    assert page.evaluate("document.getElementById('games-updating').hidden")
    assert page.evaluate("document.getElementById('games-rows').getAttribute('aria-busy')") is None


def test_the_dim_is_applied_at_once_and_never_transitioned():
    """The ruling's own words: the dim is instant. The stylesheet's updating
    rule carries `transition: none`, and the motion scan still passes."""
    css = (config.PACKAGE_ROOT / "web" / "style.css").read_text(encoding="utf-8")
    rule = re.search(r"#games-rows\.updating[^{]*\{([^}]*)\}", css)
    assert rule and "transition: none" in rule.group(1) and "pointer-events: none" in rule.group(1), rule and rule.group(0)
    audit.check_motion_vocabulary()


def test_the_first_load_says_it_is_loading_in_words_and_nothing_moves(served, _browser):
    """RULED 2026-09-25: before any slate answer exists the page shows a static
    placeholder in its own words -- no spinner, no motion -- and the first
    answer replaces it."""
    from tests.conftest import SMOKE_TOKEN
    context = _browser.new_context(viewport={"width": 1300, "height": 900})
    page = context.new_page()
    held = []
    # `/api/week` and `/api/week?…` only: `/api/weeks` is the picker the boot
    # awaits, and holding it would hold the boot.
    page.route(re.compile(r"/api/week(\?|$)"), lambda route: held.append(route))
    page.goto(served + "/login", wait_until="networkidle")
    page.fill("#token", SMOKE_TOKEN)
    # THE SLATE HAS BEEN ASKED FOR AND IS HELD (the board merge, 2026-09-29):
    # this waited 300ms after the view appeared before probing. The page has
    # done all it will do before its first answer once the request for the
    # slate has gone out -- which is an event, not a duration.
    with page.expect_request(re.compile(r"/api/week(\?|$)"), timeout=20000):
        page.click("#submit")
    page.wait_for_url(served + "/", timeout=15000)
    page.wait_for_selector("#view-games:not([hidden])", timeout=15000)
    probe = page.evaluate("""() => { const p = document.getElementById('games-loading'); const cs = getComputedStyle(p);
        return { shown: !p.hidden && cs.display !== 'none', words: p.textContent.trim(), animation: cs.animationName,
                 transition: cs.transitionProperty, rows: document.querySelectorAll('#games-rows .game').length,
                 spinners: document.querySelectorAll('[class*="spinner"], [class*="spin"]').length }; }""")
    assert probe["shown"] and probe["words"] == "Loading today's games", probe
    assert probe["rows"] == 0 and probe["spinners"] == 0, probe
    assert probe["animation"] in ("none", "") and probe["transition"] in ("all", "none", ""), probe
    assert audit.plain_words_violations(probe["words"]) == []
    for r in held:
        r.continue_()
    page.unroute(re.compile(r"/api/week(\?|$)"))
    page.wait_for_selector("#games-rows .game", timeout=15000)
    assert page.evaluate("document.getElementById('games-loading').hidden")
    context.close()


# --- question 18: an open card stays open across any redraw -------------------
#
# Operator question 18, ruled 2026-09-27 (third set): "fixed in the board, not
# the old UI: an open card stays open across any redraw. A test proves it."
# And the merge checklist's third-set addition to step 3: "an open card stays
# open across a redraw it didn't cause and one the operator started. Each gets
# a test." Built by the board merge (2026-09-29). NO FIXED WAIT: each redraw
# is known to have landed by what the page itself shows -- every row a new
# node, the updating state gone, the arrival ended (question 28's helper).

#: Every row on the slate now, remembered by node so a redraw is seen to have
#: replaced them. A JS property, not an attribute: nothing on the page moves.
_REMEMBER_THE_ROWS = """() => {
    window.__rowsBefore = new Set(document.querySelectorAll('#games-rows .game'));
}"""

#: The redraw has landed: the slate is not updating, it holds rows, and not
#: one of them is a node from before it.
_THE_ROWS_WERE_REDRAWN = """() => {
    const rows = document.getElementById('games-rows');
    const now = [...rows.querySelectorAll('.game')];
    return !rows.classList.contains('updating') && now.length > 0
        && now.every(r => !window.__rowsBefore.has(r));
}"""

#: Is the game's row open, by every mark the row carries?
_OPEN = """(game) => {
    const row = document.querySelector(`#games-rows .game[data-game="${game}"]`);
    if (!row) return null;
    const more = row.querySelector('.game-more');
    return row.classList.contains('open') && !more.hidden
        && row.querySelector('.car').getAttribute('aria-expanded') === 'true'
        && row.querySelector('.game-head').getAttribute('aria-expanded') === 'true';
}"""


def _open_the_first_row(page):
    """Open the slate's first row by its head, as a reader does, and say
    which game it is."""
    from tests.conftest import wait_for_the_redraw_it_starts

    page.set_viewport_size(WIDE)
    with wait_for_the_redraw_it_starts(page):
        page.evaluate("location.hash = '#/games'")
    row = page.locator("#games-rows .game").first
    game = row.get_attribute("data-game")
    row.locator(".game-head").click()
    page.wait_for_function(_OPEN, arg=game, timeout=10000)
    return game


def _redrawn(page, action, *, panel="games-rows"):
    """Do `action`, and return once the redraw it starts has replaced every
    row and its arrival has ended -- read inside the page, never timed."""
    from tests.conftest import wait_for_the_redraw_it_starts

    page.evaluate(_REMEMBER_THE_ROWS)
    with wait_for_the_redraw_it_starts(page, panel):
        action()
    page.wait_for_function(_THE_ROWS_WERE_REDRAWN, timeout=15000)


def test_an_open_card_stays_open_across_a_redraw_it_did_not_cause(page):
    """A render the reader did not start -- the slate drawn again from inside
    the page, its answer held so the UPDATING STATE is on screen, then let
    land -- leaves the row the reader opened open: while the stale slate is
    dimmed, and on the new rows once they land. Before the merge every render
    rebuilt every row closed (question 18)."""
    game = _open_the_first_row(page)
    held = []
    week = re.compile(r"/api/week(\?|$)")
    page.route(week, lambda route: held.append(route))
    page.evaluate(_REMEMBER_THE_ROWS)
    # NOT AWAITED: its answer is held, so the promise would never settle.
    page.evaluate("() => { window.Gridiron.route(); }")
    page.wait_for_function(
        "document.getElementById('games-rows').classList.contains('updating')",
        timeout=10000)
    assert page.evaluate(_OPEN, game) is True, \
        "the open row closed as soon as the slate began to update"
    from tests.conftest import wait_for_the_redraw_it_starts
    with wait_for_the_redraw_it_starts(page):
        for route in held:
            route.continue_()
        page.unroute(week)
    page.wait_for_function(_THE_ROWS_WERE_REDRAWN, timeout=15000)
    assert page.evaluate(_OPEN, game) is True, (
        "a redraw the reader did not start landed and the row they had opened "
        "is closed (operator question 18)")
    # AND AGAIN, WITH NOTHING HELD: a second unasked render, straight through.
    _redrawn(page, lambda: page.evaluate("() => { window.Gridiron.route(); }"))
    assert page.evaluate(_OPEN, game) is True
    # THE READER'S OWN CLOSE STANDS TOO: closed by its head, a redraw leaves
    # it closed.
    page.click(f"#games-rows .game[data-game='{game}'] .game-head")
    page.wait_for_function("(g) => !document.querySelector("
                           "`#games-rows .game[data-game=\"${g}\"]`).classList.contains('open')",
                           arg=game, timeout=5000)
    _redrawn(page, lambda: page.evaluate("() => { window.Gridiron.route(); }"))
    assert page.evaluate(_OPEN, game) is False, "a row the reader closed came back open"


def test_an_open_card_stays_open_across_every_redraw_the_operator_starts(page):
    """The sort, a filter, a page tab and the took button each redraw the
    slate, and each leaves the row the reader opened open (operator question
    18; the checklist: "one the operator started")."""
    game = _open_the_first_row(page)
    # THE SORT (by edge from ruling B, 2026-10-07: "the model's chance" is
    # gone).
    _redrawn(page, lambda: page.select_option("#games-sort", "edge"))
    assert page.evaluate(_OPEN, game) is True, "the sort closed the open row"
    _redrawn(page, lambda: page.select_option("#games-sort", "time"))
    assert page.evaluate(_OPEN, game) is True
    # A FILTER: the market of one of the open game's own questions, so the
    # row is still on the filtered slate.
    market = page.evaluate(
        "(g) => { const t = document.querySelector("
        "`#games-rows .game[data-game=\"${g}\"] .q`);"
        " return t ? (window.Gridiron.state.slate.board.games.find(x => x.game_id === g)"
        ".questions.find(q => String(q.prediction_id) === t.dataset.id) || {}).market : null; }",
        game)
    assert market, "the open row holds no question to filter by"
    _redrawn(page, lambda: page.select_option("#week-market", market))
    assert page.evaluate(_OPEN, game) is True, "the market filter closed the open row"
    _redrawn(page, lambda: page.select_option("#week-market", ""))
    assert page.evaluate(_OPEN, game) is True
    # A PAGE TAB: to Props and back to Games.
    page.click("#nav a[data-route='props']")
    page.wait_for_selector("#view-props:not([hidden])", timeout=10000)
    _redrawn(page, lambda: page.click("#nav a[data-route='games']"))
    assert page.evaluate(_OPEN, game) is True, "a page tab closed the open row"
    # THE TOOK BUTTON on a question inside the open row.
    took = page.locator(
        f"#games-rows .game[data-game='{game}'] .game-more "
        ".q[data-state='upcoming'] .chk:not([disabled])")
    if took.count():
        _redrawn(page, lambda: took.first.click())
        assert page.evaluate(_OPEN, game) is True, "the took button closed the open row"


# --- the board's figures, through the repair's doors (the merge) -------------
#
# The board merge's step 2 (2026-09-29): every count and figure the board
# states goes through the door repair built for it -- the badge on question
# 17's key per forecaster, the standing pass by question 27's order, a priced
# chance corrected through question 32's door. Each is read here off the
# payload and worked out again through the door.

def test_every_badge_counts_the_edge_gates_own_questions(world_copy):
    """A row's and a tile's record badge is `shortlist.settled_for_gate` --
    one forecaster's settled questions, each once on question 17's key,
    standing by question 27's order -- the count the signal's gate opens on."""
    from gridiron import shortlist

    payload = _payload(world_copy)
    blocks = [q for g in payload["board"]["games"] for q in g["questions"]]
    blocks += payload["board"]["props"]["tiles"]
    assert blocks
    for block in blocks:
        row = world_copy.execute(
            "SELECT sport, market_type, prop_type, predictor FROM predictions"
            " WHERE id = ?", (block["prediction_id"],)).fetchone()
        want = shortlist.settled_for_gate(world_copy, row["sport"], row["market_type"],
                                          row["prop_type"], row["predictor"])
        assert block["badge_n"] == want, (block["prediction_id"], block["badge_n"], want)
        assert block["badge_words"] == language.badge_words(
            want, config.MIN_SAMPLE_FOR_EDGE_CLAIM)


def test_the_other_forecasters_row_stands_by_the_one_clause(world_copy):
    """The other forecaster's question on an expanded row is its STANDING row:
    a final pass written before the start over an early pass written after it
    (operator question 27). The board kept a rule of its own -- the latest
    written before the start -- which stood the early pass here."""
    game = world_copy.execute(
        "SELECT p.game_id, g.kickoff_utc FROM predictions p JOIN games g"
        "  ON g.id = p.game_id WHERE p.predictor = 'llm' AND g.status != 'final'"
        " ORDER BY p.id LIMIT 1").fetchone()
    assert game, "the world holds no reasoning-pass row on an open game"
    stat = world_copy.execute(
        "SELECT * FROM predictions WHERE game_id = ? AND predictor = 'statistical'"
        " AND market_type != 'prop' ORDER BY id LIMIT 1", (game["game_id"],)).fetchone()
    kickoff = datetime.fromisoformat(game["kickoff_utc"].replace("Z", "+00:00"))

    def before(hours):
        return (kickoff - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")

    ids = {}
    for pass_kind, hours in (("final", 3), ("early", 1)):
        ids[pass_kind] = world_copy.execute(
            "INSERT INTO predictions (created_utc, sport, game_id, market_type,"
            " subject, line_asked, model_prob, model_side, predictor, pass_kind,"
            " factor_set_version, factors_json, reasoning)"
            " VALUES (?,?,?,?,?,?,?,?,'statistical',?,'fs-merge-test',?,'x')",
            (before(hours), stat["sport"], stat["game_id"], stat["market_type"],
             stat["subject"], stat["line_asked"], 0.61, stat["model_side"],
             pass_kind, stat["factors_json"])).lastrowid
    world_copy.commit()
    payload = views.week(world_copy, "nfl", forecaster="llm")
    row = next(g for g in payload["board"]["games"] if g["game_id"] == game["game_id"])
    theirs = {q["prediction_id"] for q in row["questions"]
              if q["forecaster"] == "statistical"}
    assert ids["final"] in theirs, (ids, sorted(theirs))
    assert ids["early"] not in theirs and stat["id"] not in theirs, (ids, sorted(theirs))
    # and it is the row the one clause keeps
    kept = world_copy.execute(
        "SELECT p.id FROM predictions p JOIN games g ON g.id = p.game_id"
        " WHERE p.id = ?" + calibration.standing_row_clause(False),
        (ids["final"],)).fetchone()
    assert kept is not None


def test_a_priced_chance_is_the_corrected_one_and_a_live_row_carries_none():
    """A priced question's chance is the Today entry's corrected fair value,
    turned to the side the question names -- the old card's model chip --
    and a live row's block carries no chance at all (LIVE TAB)."""
    card = {"prediction_id": 1, "market": "total", "market_type": "total",
            "shown_prob": 0.64, "phrase": "over 41.5", "side_words": "over 41.5",
            "line_asked": 41.5, "subject": "over", "model_side": "over"}

    def block(entry, state="upcoming"):
        return board._question_block(card, entry, state=state, taken=False,
                                      forecaster="statistical", n_settled=12,
                                      hours=3.0, unit_dollars=None)

    # the Today card's words for its numbers travel with them (step A)
    entry = {"price": 0.54, "payout": 1.85, "group": "clears", "edge_cents": 8.0,
             "fair_value": 0.58, "question_takes_the_proposition": True,
             "line_words": "Over 41.5 total", "question": "over 41.5"}
    assert block(entry)["prob"] == 0.58
    assert block(dict(entry, question_takes_the_proposition=False))["prob"] == \
        pytest.approx(0.42)
    assert block(None)["prob"] == 0.64, "an unpriced question keeps its stored number"
    live = block(entry, state="live")
    assert "prob" not in live and "prob_words" not in live
    assert "prob" not in live["tips"]
    assert "pregame" in live["pregame_words"]
    assert audit.live_tab_faults({"board": {"games": [{
        "state": "live", "pick_label_words": language.pick_label_words("live", "none"),
        "pick": live, "questions": [live]}]}}) == []


# --- the merge's prover (2026-09-29): what got through the merge --------------

def _priced_away_pick(tmp_path, monkeypatch):
    """test_recommend's world: the away side at 57% (a claim of 43% on the
    home side) against a 48.5c home price, with a correction in force that
    makes the home side 53.58% -- so the chip reads 46c on the away side."""
    from gridiron.priced import coverage
    from tests import test_recommend as rec

    monkeypatch.setattr(coverage, "priceable", lambda conn, sport, market, **_: {
        "priceable": True, "market": market, "why": "covered, in this test"})
    conn = rec._world(tmp_path, kickoff="2099-01-01T00:00:00Z")
    pid = rec._away_pick(conn)
    rec._correct(conn)
    return conn, pid


def _block_and_card(payload, pid):
    card = next(c for group in ("clears", "below_floor", "watching")
                for c in payload["today"][group] if c["prediction_id"] == pid)
    block = next(q for g in payload["board"]["games"] for q in g["questions"]
                 if q["prediction_id"] == pid)
    return block, card


def test_a_priced_row_is_its_cards_corrected_number_on_the_side_it_names(tmp_path, monkeypatch):
    """ON A REAL PAYLOAD (the merge's prover, 2026-09-29). The merge read the
    entry's corrected `fair_value` for a priced question's chance, from a
    Today card that never carried it -- the test above hands the block a dict
    made by hand -- so on the page the chance stayed the stored number; and
    the price and the payout were the claim's fixed proposition's, unturned:
    this away side's question read 57% beside the home side's 48c and 2.06x
    where the card's chip said 46c against 52c (the wrong-side defect of
    2026-09-07, and GRIDIRON_REPAIR item 3's chip).

    AND FROM OPERATOR QUESTION 37 (ruled 2026-10-05: "headline the contract
    the recommendation buys; the model's own side named beside it"): the
    correction in force makes the home side 53.58% against its 48.5c, so the
    recommendation buys the home side, AAA -- the other side of the model's
    words -- and the card and the row headline AAA at its corrected 54%, its
    48.5c and 2.06x, the model's own side (BBB, 46%) beside it. Until the
    ruling this asserted the row at BBB's 46%, 51.5c and 1.94x beside AAA's
    size and outline."""
    from gridiron.market import recommend

    conn, pid = _priced_away_pick(tmp_path, monkeypatch)
    entry = recommend.for_predictions(conn, [pid])[0]
    assert entry["question_takes_the_proposition"] is False
    assert entry["fair_value"] == pytest.approx(0.5358, abs=1e-4)
    assert entry["side"] == "yes"
    payload = views.week(conn, "mlb", 2026, 1)
    block, card = _block_and_card(payload, pid)
    assert card["question_takes_the_proposition"] is True and card["question"] == "AAA to win"
    assert block["prob"] == pytest.approx(entry["fair_value"]), block["prob"]
    assert block["prob_words"] == card["model_words"].replace("¢", "%") == "54%"
    assert block["price"] == pytest.approx(0.485)
    assert block["pays"] == recommend.payout_multiple(0.485)
    assert block["price_words"].startswith("48"), block["price_words"]
    assert block["own_side_words"] == "The model's own side: BBB to win, 46%"
    assert audit.board_price_side_faults(payload) == []
    assert audit.headline_faults(payload) == []
    # AS THE MERGE LEFT IT: the Today card without the two numbers.
    real = views._today_card

    def as_merged(*args, **kwargs):
        out = real(*args, **kwargs)
        out.pop("fair_value", None)
        out.pop("question_takes_the_proposition", None)
        return out

    monkeypatch.setattr(views, "_today_card", as_merged)
    # FROM 2026-09-30 THE BOARD REFUSES THAT SHAPE ITSELF: a priced card with
    # no placed side is not drawn at all (the ruling of 2026-09-30) -- where
    # the merge drew 57% beside the home side's 48c.
    from gridiron import subjects

    with pytest.raises(subjects.UnplaceableSide, match="cannot be said"):
        views.week(conn, "mlb", 2026, 1)
    # AND THE CHECK STILL NAMES IT, on the payload the merge produced: the
    # card without the two numbers, the row at the stored 57% and 48.5c.
    monkeypatch.setattr(views, "_today_card", real)
    merged = views.week(conn, "mlb", 2026, 1)
    block, card = _block_and_card(merged, pid)
    card.pop("fair_value")
    card.pop("question_takes_the_proposition")
    block.update({"prob": 0.57, "prob_words": "57%", "price": 0.485,
                  "pays": recommend.payout_multiple(0.485)})
    faults = audit.board_price_side_faults(merged)
    assert faults and "carries no `fair_value`" in faults[0], faults
    # AND A BLOCK LEFT ON THE OTHER SIDE'S PRICE is named by its numbers
    # (from operator question 37 the side its words name is AAA, the
    # proposition, so the other side's is BBB's 51.5c).
    monkeypatch.setattr(views, "_today_card", real)
    fixed = views.week(conn, "mlb", 2026, 1)
    block, _ = _block_and_card(fixed, pid)
    block["price"], block["pays"] = 0.515, recommend.payout_multiple(0.515)
    faults = audit.board_price_side_faults(fixed)
    assert any("wrong-side" in f for f in faults) and any("payout" in f for f in faults), faults


def test_my_day_counts_a_taken_prop_once(world_copy):
    """A prop question is on its game's row and is a tile, and My day read
    both: one tap, two chips, "2 taken" (the merge's prover, 2026-09-29)."""
    from gridiron import db

    # A PROP NOBODY HAS TAKEN YET (2026-10-06): the copy is of the shared
    # world, where an earlier browser test taps the first prop tile, and from
    # operator ruling C the tiles are ordered by edge and then by start, so
    # that first tile is the lowest-numbered prop this read used to take.
    prop = world_copy.execute(
        "SELECT p.id FROM predictions p JOIN games g ON g.id = p.game_id"
        " WHERE g.status = 'scheduled' AND p.predictor = 'statistical'"
        "   AND p.market_type = 'prop'"
        "   AND p.id NOT IN (SELECT prediction_id FROM picks_taken"
        "                    WHERE prediction_id IS NOT NULL)"
        " ORDER BY p.id LIMIT 1").fetchone()[0]
    world_copy.execute("INSERT INTO picks_taken (prediction_id, taken_utc) VALUES (?, ?)",
                       (prop, db.utcnow()))
    world_copy.commit()
    payload = _payload(world_copy)
    board_ = payload["board"]
    assert any(t["prediction_id"] == prop and t["taken"] for t in board_["props"]["tiles"])
    assert any(q["prediction_id"] == prop and q["taken"]
               for g in board_["games"] for q in g["questions"])
    day = board_["my_day"]
    chips = [e for e in day["entries"] if e["prediction_id"] == prop]
    assert len(chips) == 1, f"one tapped prop is {len(chips)} chips"
    assert chips[0]["prop"] is True
    tile = next(t for t in board_["props"]["tiles"] if t["prediction_id"] == prop)
    assert chips[0]["club"]["tricode"] == tile["club"]["tricode"]
    assert day["n"] == len(day["entries"]) == len({e["prediction_id"] for e in day["entries"]})
    assert audit.board_count_faults(payload) == []
    # AS THE MERGE BUILT IT: the prop entered from its row and from its tile.
    doubled = dict(payload, board=dict(board_, my_day=dict(
        day, n=day["n"] + 1, entries=day["entries"] + chips)))
    faults = audit.board_count_faults(doubled)
    assert faults and "more than once" in faults[0], faults


def test_a_rows_questions_are_counted_for_each_forecaster_apart(world_copy):
    """The row said "4 questions on this game" over three of the model's and
    one of the reasoning pass's (the merge's prover, 2026-09-29): one figure
    over both forecasters, the pooled count questions 14 and 22 took off every
    other panel. Each forecaster's standing questions, on question 17's key."""
    from gridiron import bet

    payload = _payload(world_copy)
    rows = [g for g in payload["board"]["games"]
            if len({q["forecaster"] for q in g["questions"]}) > 1]
    assert rows, "the world's reasoning-pass row is on no game row"
    for g in payload["board"]["games"]:
        mine = [q for q in g["questions"] if q["forecaster"] == payload["forecaster"]]
        assert g["questions_n"].get(payload["forecaster"]) == len(mine)
    row = rows[0]
    own = row["questions_n"]["statistical"]
    assert row["questions_n"]["llm"] == 1
    assert row["questions_words"] == (
        f"{own} questions from the model · 1 from the reasoning pass"), row["questions_words"]
    # each forecaster's count is its standing questions on the key
    stats = world_copy.execute(
        "SELECT p.* FROM predictions p JOIN games g ON g.id = p.game_id"
        " WHERE p.game_id = ? AND p.predictor = 'statistical'"
        + calibration.standing_row_clause(False), (row["game_id"],)).fetchall()
    assert own == bet.count(stats)
    assert audit.board_count_faults(payload) == []
    pooled = dict(payload, board=dict(payload["board"], games=[
        dict(g, questions_words=f"{len(g['questions'])} questions on this game")
        if g is row else g for g in payload["board"]["games"]]))
    faults = audit.board_count_faults(pooled)
    assert faults and "each forecaster's apart" in faults[0], faults


def test_results_settled_tiles_are_the_questions_its_heading_counts(world_copy):
    """Results heads its settled tiles with the Today block's "Settled -- N
    questions"; the board drew every question on every finished row beneath
    it, the other forecaster's included (the merge's prover, 2026-09-29)."""
    import json as _json

    from gridiron import db
    from gridiron.model import prompt_record as _prompts
    from tests.conftest import seed_a_sent_prompt

    row = world_copy.execute(
        "SELECT p.game_id, p.market_type, p.subject, p.line_asked,"
        "       p.factor_set_version, p.factors_json, p.model_side"
        "  FROM predictions p JOIN games g ON g.id = p.game_id"
        " WHERE g.season = 2025 AND g.week = 8 AND g.status = 'final'"
        "   AND p.predictor = 'statistical' AND p.market_type = 'spread'"
        " ORDER BY p.id LIMIT 1").fetchone()
    question = _json.loads(row["factors_json"])["question"]
    cite = seed_a_sent_prompt(world_copy, game_id=row["game_id"], claim=question["claim"])
    world_copy.execute(
        "INSERT INTO predictions (created_utc, game_id, market_type, subject,"
        " line_asked, model_prob, model_side, predictor, factor_set_version,"
        " factors_json, reasoning) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (db.utcnow(), row["game_id"], row["market_type"], row["subject"],
         row["line_asked"], 0.66, row["model_side"], "llm", row["factor_set_version"],
         _json.dumps({"prob_yes": 0.66, "question": question, _prompts.CITE: cite}),
         "The home side is the stronger team here."))
    world_copy.commit()
    payload = views.week(world_copy, "nfl", 2025, 8)
    board_ = payload["board"]
    heading = [c["prediction_id"] for c in payload["today"]["settled"]]
    assert heading and sorted(board_["settled_ids"]) == sorted(heading)
    finals = [q for g in board_["games"] if g["state"] == "final" for q in g["questions"]]
    assert any(q["forecaster"] == "llm" for q in finals), "the added row is on no finished row"
    # WHAT RESULTS DRAWS: the finished rows' blocks the heading counts.
    drawn = [q for q in finals if q["prediction_id"] in set(board_["settled_ids"])]
    assert len(drawn) == len(heading)
    assert str(len(heading)) in payload["today"]["settled_heading"]
    assert audit.board_count_faults(payload) == []
    # AS THE MERGE DREW IT: every question on every finished row.
    every = dict(payload, board=dict(board_, settled_ids=[q["prediction_id"] for q in finals]))
    faults = audit.board_count_faults(every)
    assert faults and "settled heading counts" in faults[0], faults


def test_the_taken_comparison_counts_a_question_once_whichever_pass_was_tapped(world_copy):
    """"Taken, passed over, every forecast" on the Record page splits one
    forecaster's questions on question 17's key: a tap on another pass of a
    question takes the question that stands (the board matched a tap to the
    standing row's number alone, and counted this one passed over)."""
    from gridiron import bet, db

    standing = calibration.resolved(world_copy, sport="nfl", market_type="spread",
                                    predictor="statistical")
    assert standing
    stands = standing[0]
    row = world_copy.execute("SELECT * FROM predictions WHERE id = ?",
                             (stands.id,)).fetchone()
    earlier = (datetime.fromisoformat(row["created_utc"].replace("Z", "+00:00"))
               - timedelta(seconds=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    before = calibration.taken_comparison(world_copy, sport="nfl", market_type="spread")
    # ANOTHER PASS OF THE SAME QUESTION, written first: it never stands.
    other = world_copy.execute(
        "INSERT INTO predictions (created_utc, sport, game_id, market_type,"
        " subject, line_asked, model_prob, model_side, predictor, pass_kind,"
        " factor_set_version, factors_json, reasoning)"
        " VALUES (?,?,?,?,?,?,?,?,'statistical','early','fs-merge-test',?,'x')",
        (earlier, row["sport"], row["game_id"], row["market_type"], row["subject"],
         row["line_asked"], row["model_prob"], row["model_side"],
         row["factors_json"])).lastrowid
    world_copy.execute("INSERT INTO picks_taken (prediction_id, taken_utc) VALUES (?, ?)",
                       (other, db.utcnow()))
    world_copy.commit()
    after = calibration.taken_comparison(world_copy, sport="nfl", market_type="spread")
    assert after["predictor"] == "statistical"
    assert after["n"] == before["n"], "a question was counted twice, or lost"
    assert bet.of(calibration.resolved(world_copy, sport="nfl", market_type="spread",
                                       predictor="statistical")[0]) == bet.of(stands)
    assert after["taken"]["n"] == before["taken"]["n"] + 1, (before["taken"]["n"],
                                                             after["taken"]["n"])
    assert after["not_taken"]["n"] == before["not_taken"]["n"] - 1
    # and the Record page says whose, and carries no total over markets
    record = views.scorecard(world_copy, "nfl")["taken_record"]
    assert "n" not in record
    for entry in record["markets"]:
        assert entry["market_label"].endswith(", statistical"), entry["market_label"]


def test_load_rosters_writes_the_rows_the_upsert_wrote(league, monkeypatch, tmp_path):
    """`load_rosters` is written plainly (the board merge, 2026-09-29; the
    replacing-write register frozen at 35): an update where the key is
    stored, a plain insert where it is not. The rows it leaves are the rows
    the board's `ON CONFLICT ... DO UPDATE` left, for a first load, a reload
    with numbers changed and a new club, and a file that names one key twice."""
    from gridiron import db
    from gridiron.data import loader, sources

    loads = [
        [{"season": "2025", "team": "KC", "gsis_id": "A", "jersey_number": "15"},
         {"season": "2025", "team": "KC", "gsis_id": "B", "jersey_number": ""},
         {"season": "", "team": "BUF", "gsis_id": "C", "jersey_number": "17"},
         {"season": "2025", "team": "", "gsis_id": "X", "jersey_number": "1"}],
        [{"season": "2025", "team": "KC", "gsis_id": "A", "jersey_number": "10"},
         {"season": "2025", "team": "KC", "gsis_id": "B", "jersey_number": "88"},
         {"season": "2025", "team": "KC", "gsis_id": "B", "jersey_number": "89"},
         {"season": "2025", "team": "NYJ", "gsis_id": "A", "jersey_number": "10"}],
    ]
    clock = iter(["2026-09-29T00:00:00Z"] * 2 + ["2026-09-29T01:00:00Z"] * 2)
    monkeypatch.setattr(loader, "utcnow", lambda: next(clock))

    def the_upsert(conn, rows, season):
        # THE BOARD'S STATEMENT, as it was written on a63463a.
        now = loader.utcnow()
        with conn:
            for r in rows:
                player_id = (r.get("gsis_id") or "").strip()
                team = (r.get("team") or "").strip()
                if not player_id or not team:
                    continue
                conn.execute(
                    "INSERT INTO player_numbers (season, player_id, team, jersey_number, fetched_utc)"
                    " VALUES (?,?,?,?,?)"
                    " ON CONFLICT(season, player_id, team) DO UPDATE SET"
                    " jersey_number=excluded.jersey_number, fetched_utc=excluded.fetched_utc",
                    (loader._int(r.get("season")) or season, player_id, team,
                     loader._int(r.get("jersey_number")), now))

    def rows(conn):
        return [tuple(r) for r in conn.execute(
            "SELECT * FROM player_numbers WHERE player_id IN ('A', 'B', 'C')"
            " ORDER BY season, player_id, team")]

    upserted = db.open_db(tmp_path / "upsert.db")
    try:
        for load in loads:
            monkeypatch.setattr(sources, "fetch_csv", lambda conn, url, _l=load, **kw: _l)
            loader.load_rosters(league, 2025)
            the_upsert(upserted, load, 2025)
            assert rows(league) == rows(upserted)
        assert rows(league) == [
            (2025, "A", "KC", 10, "2026-09-29T01:00:00Z"),
            (2025, "A", "NYJ", 10, "2026-09-29T01:00:00Z"),
            (2025, "B", "KC", 89, "2026-09-29T01:00:00Z"),
            (2025, "C", "BUF", 17, "2026-09-29T00:00:00Z")]
    finally:
        upserted.close()
    # AND NOTHING IN THE LOADER IS AN UPSERT the gate's scan would name
    assert not [f for f in audit.replacing_write_faults() if "loader.py" in f]


# --- the laws the old routes carried, re-homed on the board (the merge) -------

def test_the_old_routes_render_nothing_of_their_own(page):
    """THE OLD PICKS, LIVE AND TODAY ROUTES ARE REMOVED (the board merge,
    2026-09-29; the checklist: "removed in this release and not before"):
    no view, no panel and no renderer of theirs is left, and every address a
    reader kept for them lands on Games."""
    html = (config.PACKAGE_ROOT / "web" / "index.html").read_text(encoding="utf-8")
    js = (config.PACKAGE_ROOT / "web" / "app.js").read_text(encoding="utf-8")
    for gone in ('id="view-week"', 'id="today"', 'id="state-tabs"', 'id="today-live"',
                 'id="week-market-tabs"', 'data-route="week"'):
        assert gone not in html, gone
    for gone in ("function renderWeek", "function todayCard", "function applyStateTab",
                 "'face-why'", "getElementById('today')"):
        assert gone not in js, gone
    for old in ("week", "picks", "live", "today"):
        page.evaluate(f"location.hash = '#/{old}'")
        page.wait_for_function("location.hash === '#/games'", timeout=10000)
        page.wait_for_selector("#view-games:not([hidden])", timeout=10000)


def test_a_dead_job_is_on_the_first_screen_of_the_board(served, _browser):
    """FIRST SCREEN, re-homed (the board merge, 2026-09-29): a job that fails
    is visible on the first screen the operator opens. The day strip that
    carried the pulse left with the old Picks route; the board's header
    carries it on every page, from `/api/pulse` and every slate. A job past
    its threshold is marked in the header on the first screen at 390px, in
    the warning ink and never in a value colour, its words carrying the
    threshold."""
    from tests.conftest import SMOKE_TOKEN

    def stale(route):
        response = route.fetch()
        body = response.json()
        entries = (body.get("freshness") or {}).get("entries") or []
        if entries:
            entries[0] = dict(entries[0], stale=True,
                              words="daily run 40 hours ago, past 36h")
        route.fulfill(response=response, json=body)

    context = _browser.new_context(viewport={"width": 390, "height": 844},
                                   device_scale_factor=3, is_mobile=True, has_touch=True)
    try:
        page = context.new_page()
        page.route(re.compile(r"/api/(pulse|week)(\?|$)"), stale)
        page.goto(served + "/login", wait_until="networkidle")
        page.fill("#token", SMOKE_TOKEN)
        page.click("#submit")
        page.wait_for_url(served + "/", timeout=15000)
        page.wait_for_selector("#view-games:not([hidden])", timeout=15000)
        page.wait_for_selector("#day-jobs .day-job-stale", timeout=15000)
        got = page.evaluate("""() => {
            const e = document.querySelector('#day-jobs .day-job-stale');
            const r = e.getBoundingClientRect();
            const probe = document.createElement('span');
            document.body.appendChild(probe);
            const colour = v => { probe.style.color = 'var(' + v + ')';
                                  return getComputedStyle(probe).color; };
            const out = { top: r.top, bottom: r.bottom, h: innerHeight,
                          words: e.textContent, colour: getComputedStyle(e).color,
                          warn: colour('--warn-ink'), win: colour('--win'),
                          loss: colour('--loss') };
            probe.remove();
            return out; }""")
    finally:
        context.close()
    assert 0 <= got["top"] and got["bottom"] <= got["h"], got
    assert "past 36h" in got["words"]
    assert got["colour"] == got["warn"] and got["colour"] not in (got["win"], got["loss"]), got


def test_the_pulse_the_header_reads_passes_the_first_screen_check(world_copy):
    """`/api/pulse`, the header's own read on every page, is the freshness
    block the slate carries, and FIRST SCREEN's check reads it as it reads a
    slate (`audit.check_the_strip_shows_a_dead_job`)."""
    payload = {"freshness": views.freshness(world_copy)}
    audit.check_the_strip_shows_a_dead_job(payload)
    assert payload["freshness"]["entries"]
    assert payload == {"freshness": views.week(world_copy, "nfl")["freshness"]}


def test_headings_are_plain_words_and_version_names_are_tooltips(world_copy):
    """Operator question 19 (ruled 2026-09-27; built by the board merge,
    2026-09-29): no heading index.html writes carries a version name or an
    identifier, the renderer paints no `..._version` field as text, and each
    version name the pages speak of travels as a tooltip: the blend's and the
    ordering's beside their headings, the factor set's on Settings."""
    from gridiron import settings as settings_mod

    assert audit.heading_words_faults() == []
    assert audit.version_painted_faults() == []
    sc = views.scorecard(world_copy, "nfl")
    assert sc["priced"]["version_tip"] == language.version_tip("blend", config.PRICED_VERSION)
    assert sc["ranker"]["version_tip"] == language.version_tip("ranker", config.RANKER_VERSION)
    row = next(r for r in settings_mod.fenced() if r["name"] == "FACTOR_SET_VERSION")
    assert audit.plain_words_violations(row["value"]) == [], row["value"]
    assert config.FACTOR_SET_VERSION in row["tip"]
    assert audit.plain_words_violations(row["tip"], in_a_tooltip=True) == []
    assert audit.plain_words_violations(row["tip"]), "the name passed outside a tooltip"


def test_the_record_page_shows_no_version_name_and_its_headings_carry_them(page):
    """Rendered (question 19): the Record page's priced and ordering headings
    say what they are in words and carry the name only as their title."""
    page.set_viewport_size(WIDE)
    page.evaluate("location.hash = '#/record'")
    page.wait_for_selector("#priced-record:not([hidden])", timeout=20000)
    got = page.evaluate("""() => {
        const h = document.getElementById('priced-heading');
        return { text: h.textContent.trim(), title: h.title }; }""")
    assert got["text"] == "Priced, and against the close", got
    assert config.PRICED_VERSION in got["title"]
    visible = page.evaluate("""() => {
        const clone = document.getElementById('view-record').cloneNode(true);
        clone.querySelectorAll('.factor-code, td.wide, .code-literal').forEach(e => e.remove());
        return clone.innerText; }""")
    assert audit.version_name_violations(visible) == []


def test_a_declared_factors_phrase_in_a_tooltip_is_not_advice():
    """THE LIVE RECORD'S NFL SLATE FAILED THE BOARD'S OWN SCAN (the board
    merge, 2026-09-29, read-only through `db.read_the_live_record`): twelve
    pick tooltips carry the old card's Why sentences -- "Mostly it comes down
    to how many plays both offences run" -- and the advice scan read "plays"
    as a verb. The phrase is a declared factor's own name, which the scan
    already spared as `factor_words`; it is spared inside a sentence too, and
    the rest of the sentence is still read."""
    from gridiron.factors import registry

    phrase = next(f.why for f in registry.REGISTRY.values()
                  if f.why and "plays" in f.why)
    said = {"board": {"games": [{"pick": {"tips": {
        "line": f"Mostly it comes down to {phrase}."}}}]}}
    assert audit.board_words_faults(said) == []
    planted = {"board": {"games": [{"pick": {"tips": {
        "line": f"Mostly it comes down to {phrase}. Back it: it plays."}}}]}}
    assert any("plays" in f for f in audit.board_words_faults(planted))
