"""The band line above every slate is one category's (operator question 46,
found 2026-10-08 by the prover of questions 33 and 34; built the same day,
without a new ruling, under LAW 4 -- "nothing claims an edge below 100
resolved predictions in that category" -- NO MERGED CURVES, and question 14's
ruling of 2026-09-27, "Every count on the Record page that states a gate
distance is rebuilt per forecaster (per tier for UFC) and per distinct bet,
through its record's standing rule", applied to this line).

THE LINE AS IT SHIPPED: "50-60% bucket: 370 settled · past the 100 needed, so
calibration speaks here" above UFC's slate (`views._record_movement`,
`language.bucket_countdown_line`, drawn as `#greet-countdown`) -- every
settled forecast of the sport in the band, every pass, both forecasters,
every market and every card -- where no UFC category's own band held more
than 36 (NFL said 315 where the fullest held 44; MLB 937, NCAAF 398).

Each test here fails on da4aea6 (`git archive`), which counts the sport
whole, names no category, and has no guard, no gate row and no words saying
what its pooled counts pool.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from gridiron import audit, calibration, config, db, language, settings, views

UFC_SEASON = config.SPORT_CURRENT_SEASON["ufc"]
NFL_SEASON = config.SPORT_CURRENT_SEASON["nfl"]

#: Each UFC card: (event, week, its start, bouts asked every market, bouts
#: asked the distance alone). Every bout's question is asked by both
#: forecasters, early and final, each forecast at 0.55 and settled: the sport
#: holds 216 + 8 settled forecasts in the 50-60% band and no category more
#: than 11 -- the line as it shipped said "past the 100 needed".
UFC_CARDS = {
    "fight_night": ("q46_fn", 1, "2026-09-05T19:00:00Z", 9, 2),
    "contender": ("q46_cs", 2, "2026-09-08T23:00:00Z", 6, 0),
    "numbered": ("q46_nc", 3, "2026-09-19T21:00:00Z", 3, 0),
}
#: Each category's own 50-60% band in that world, (market, card) -> count,
#: the same for both forecasters.
UFC_BANDS = {("moneyline", "fight_night"): 9, ("rounds", "fight_night"): 9,
             ("distance", "fight_night"): 11,
             ("moneyline", "contender"): 6, ("rounds", "contender"): 6,
             ("distance", "contender"): 6,
             ("moneyline", "numbered"): 3, ("rounds", "numbered"): 3,
             ("distance", "numbered"): 3}
UFC_POOLED = 2 * 2 * (3 * (9 + 6 + 3) + 2)        # 224 as it shipped

FULLEST_UFC = ("distance, Fight Night, statistical, 50-60%: 11 of 100 · 89 "
               "more before calibration speaks")


def _forecast(conn, sport, game, market, subject, line, prob, predictor,
              pass_kind, written, settled):
    conn.execute(
        "INSERT INTO predictions (created_utc, sport, game_id, market_type,"
        " subject, line_asked, model_prob, model_side, predictor, pass_kind,"
        " factor_set_version, factors_json, reasoning, resolved_utc, outcome)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'fs2', '{\"coverage\": 1.0}',"
        " 'test', ?, 1)",
        (written, sport, game, market, subject, line, prob,
         {"spread": "cover", "moneyline": "win", "distance": "yes"}.get(
             market, "over"), predictor, pass_kind, settled))


def _ufc_world(path):
    conn = db.open_db(path)
    for tier, (event, week, start, full, distance_only) in UFC_CARDS.items():
        conn.execute(
            "INSERT INTO ufc_events (id, name, event_utc, season, fetched_utc,"
            " event_tier) VALUES (?, ?, ?, ?, '2026-09-01T00:00:00Z', ?)",
            (event, f"UFC {event}", start, UFC_SEASON, tier))
        for i in range(full + distance_only):
            bout = f"{event}_{i}"
            conn.execute(
                "INSERT INTO ufc_bouts (id, event_id, bout_utc, scheduled_rounds,"
                " fighter_a, fighter_b, status, fetched_utc)"
                " VALUES (?, ?, ?, 3, 'A', 'B', 'final', '2026-09-01T00:00:00Z')",
                (bout, event, start))
            conn.execute(
                "INSERT INTO games (id, sport, season, week, game_type, home,"
                " away, kickoff_utc, status, league_date, home_score, away_score)"
                " VALUES (?, 'ufc', ?, ?, 'R', 'A', 'B', ?, 'final', ?, 1, 0)",
                (bout, UFC_SEASON, week, start, start[:10]))
            markets = (("distance", None),) if i >= full else (
                ("moneyline", None), ("rounds", 1.5), ("distance", None))
            for market, line in markets:
                for predictor in ("statistical", "llm"):
                    for pass_kind, hour in (("early", "08"), ("final", "10")):
                        _forecast(conn, "ufc", bout, market, "A", line, 0.55,
                                  predictor, pass_kind,
                                  f"{start[:10]}T{hour}:00:00Z",
                                  f"{start[:10]}T23:59:00Z")
    conn.commit()
    return conn


def _nfl_world(path, spreads=101, reasoning=30):
    """NFL: the model's point spread holds `spreads` settled questions in the
    50-60% band -- past the hundred -- and the reasoning pass's `reasoning`."""
    conn = db.open_db(path)
    for i in range(spreads):
        game = f"q46_nfl_{i}"
        week = 1 + i // 16
        start = f"2026-09-{10 + week:02d}T17:00:00Z"
        conn.execute(
            "INSERT INTO games (id, sport, season, week, game_type, home, away,"
            " kickoff_utc, status, league_date, home_score, away_score)"
            " VALUES (?, 'nfl', ?, ?, 'REG', 'KC', 'BUF', ?, 'final', ?, 24, 20)",
            (game, NFL_SEASON, week, start, start[:10]))
        _forecast(conn, "nfl", game, "spread", "KC", -3.5, 0.56, "statistical",
                  "final", f"{start[:10]}T09:00:00Z", f"{start[:10]}T23:00:00Z")
        if i < reasoning:
            _forecast(conn, "nfl", game, "spread", "KC", -3.5, 0.57, "llm",
                      "final", f"{start[:10]}T09:30:00Z", f"{start[:10]}T23:00:00Z")
    conn.commit()
    return conn


def _movement(conn, sport, forecaster=None):
    return views.digest(conn, sport=sport, day="2026-10-08",
                        forecaster=forecaster)["movement"]


def _band(movement, market, card, band="50-60%"):
    found = [b for b in movement["bands"] if b["market"] == market
             and b["event_tier"] == card and b["band"] == band]
    assert len(found) == 1, (market, card, band, movement["bands"])
    return found[0]


# --- every band is one category's ---------------------------------------------

def test_each_band_is_one_categorys_count_and_names_it(tmp_path):
    conn = _ufc_world(tmp_path / "ufc.db")
    movement = _movement(conn, "ufc")
    assert movement["forecaster"] == "statistical"
    for (market, card), n in UFC_BANDS.items():
        band = _band(movement, market, card)
        assert band["n"] == n == band["recounted"], (market, card, band)
        assert band["predictor"] == "statistical"
        assert band["forecasters_counted"] == ["statistical"]
        assert band["tiers_counted"] == [card]
        assert band["needed"] == 100 - n and band["past_the_gate"] is False
        label = language.category_label(market, card, "statistical")
        assert band["category_label"] == label
        assert band["words"] == (f"{label}, 50-60%: {n} of 100 · {100 - n} more "
                                 "before calibration speaks")
    assert sum(b["n"] for b in movement["bands"]) == UFC_POOLED // 4
    assert all("speaks here" not in b["words"] for b in movement["bands"])


def test_the_band_count_is_the_record_pages_curve(tmp_path):
    """The number the Record page's curve draws for that band: `curve`'s
    bucket, the category asked as `blind_categories` asks it."""
    conn = _ufc_world(tmp_path / "ufc.db")
    movement = _movement(conn, "ufc", "llm")
    for (market, card), n in UFC_BANDS.items():
        curve = calibration.curve(
            conn, sport="ufc", market_type=calibration.market_type_of("ufc", market),
            prop_type=calibration.prop_type_of("ufc", market), predictor="llm",
            event_tier=card)
        drawn = {b["label"]: b["n"] for b in curve["buckets"]}
        assert _band(movement, market, card)["n"] == drawn["50-60%"] == n


def test_the_line_is_the_fullest_band_of_the_pages_forecaster_named(tmp_path):
    conn = _ufc_world(tmp_path / "ufc.db")
    movement = _movement(conn, "ufc")
    assert movement["line"] == FULLEST_UFC
    assert "one market on one card" in movement["line_tip"]
    assert "UFC curve of the model" in movement["line_tip"]
    assert audit.plain_words_violations(movement["line"]) == []
    assert audit.plain_words_violations(movement["line_tip"]) == []
    # THE PAGE'S FORECASTER, from Settings, as the slate's is.
    settings.set_value(conn, "default_forecaster", "llm")
    assert views.page_forecaster(conn) == "llm"
    movement = _movement(conn, "ufc")
    assert movement["forecaster"] == "llm"
    assert movement["line"] == FULLEST_UFC.replace("statistical", "reasoning pass")
    assert views.week(conn, "ufc", UFC_SEASON, 1)["forecaster"] == "llm"


def test_calibration_speaks_only_of_a_category_past_the_hundred(tmp_path):
    conn = _nfl_world(tmp_path / "nfl.db")
    model = _movement(conn, "nfl", "statistical")
    assert model["line"] == ("point spread, statistical, 50-60%: 101 settled · "
                             "past the 100 needed, so calibration speaks here")
    assert _band(model, "spread", None)["past_the_gate"] is True
    reasoning = _movement(conn, "nfl", "llm")
    assert reasoning["line"] == ("point spread, reasoning pass, 50-60%: 30 of "
                                 "100 · 70 more before calibration speaks")
    # The UFC world: 224 settled forecasts in the band over the sport, and
    # no category past the hundred -- so nothing says calibration speaks.
    ufc = _movement(_ufc_world(tmp_path / "ufc.db"), "ufc")
    assert ufc["resolved_now"] == UFC_POOLED
    assert "speaks here" not in ufc["line"]


def test_a_sport_with_nothing_settled_draws_no_band(tmp_path):
    conn = _nfl_world(tmp_path / "nfl.db", spreads=0, reasoning=0)
    movement = _movement(conn, "nfl")
    assert movement["bands"] == [] and movement["line"] is None
    assert movement["line_tip"] is None


# --- the pooled counts stay, said as what they are ----------------------------

def test_the_pooled_counts_stay_said_as_what_they_are(tmp_path):
    conn = _ufc_world(tmp_path / "ufc.db")
    d = views.digest(conn, sport="ufc", since="2026-01-01T00:00:00Z")
    assert d["n"] == UFC_POOLED
    assert d["count_words"] == f"{UFC_POOLED} settled forecasts"
    assert d["counted_words"] == "every market, card and forecaster"
    assert d["headline"].startswith(
        f"Since you last looked: {UFC_POOLED} settled forecasts, every market, "
        "card and forecaster - ")
    movement = d["movement"]
    assert movement["resolved_now"] == UFC_POOLED
    assert movement["counted_words"] == "every market, card and forecaster"
    assert not {"buckets", "gate", "needed"} & set(movement)
    nfl = views.digest(_nfl_world(tmp_path / "nfl.db"), sport="nfl",
                       since="2026-01-01T00:00:00Z")
    assert nfl["counted_words"] == "every market and forecaster"
    for line in (d["headline"], nfl["headline"]):
        assert audit.plain_words_violations(line) == []


def test_the_greeting_counts_each_settled_forecast_once(tmp_path):
    """"Settled forecasts" is what the count is only if each is counted once:
    a LEFT JOIN on the market's snapshots gave a forecast read at the venue
    twice two rows -- counted, scored and listed twice ("632 resolved" since
    the start of NFL's record on the copy of 2026-10-08, where 524 forecasts
    had settled). Its market figure is its first snapshot, as Results reads
    it."""
    conn = _nfl_world(tmp_path / "nfl.db", spreads=2, reasoning=0)
    first = conn.execute("SELECT MIN(id) FROM predictions").fetchone()[0]
    for kind, at, implied in (("open_at_predict", "T09:00:05Z", 0.40),
                              ("near_start", "T16:30:00Z", 0.47)):
        conn.execute(
            "INSERT INTO market_snapshots (prediction_id, fetched_utc, source,"
            " implied_prob, kind) VALUES (?, ?, 'test', ?, ?)",
            (first, "2026-09-11" + at, implied, kind))
    conn.commit()
    d = views.digest(conn, sport="nfl", since="2026-01-01T00:00:00Z")
    assert (d["n"], d["correct"], len(d["settled"])) == (2, 2, 2)
    assert d["count_words"] == "2 settled forecasts"
    assert {s["prediction_id"]: s["market_prob"] for s in d["settled"]}[first] == 0.40
    assert d["brier"] == round((0.44 ** 2 + 0.44 ** 2) / 2, 4)


def test_the_slates_forecasts_waiting_are_said_as_what_they_are():
    line = language.slate_forecasts_line("NFL", 178, False, 0.262, "HOU @ TEN")
    assert line == ("178 NFL forecasts waiting to settle on the current slate, "
                    "every market and forecaster · sharpest disagreement +26.2 "
                    "on HOU @ TEN")
    assert language.slate_forecasts_line("UFC", 1, True) == (
        "1 UFC forecast waiting to settle on the current slate, every market, "
        "card and forecaster")


# --- the guard, inside the builder ---------------------------------------------

def _as_it_shipped(conn, sport):
    """The movement as da4aea6 built it: every settled forecast of the sport
    in each band, the first drawn, the gate beside the pooled counts."""
    buckets = []
    for lo, hi, label in calibration.BUCKETS:
        n = conn.execute(
            "SELECT COUNT(*) FROM predictions WHERE sport = ? AND resolved_utc"
            " IS NOT NULL AND model_prob >= ? AND model_prob < ?",
            (sport, lo, hi)).fetchone()[0]
        if n:
            buckets.append({"label": label, "n": n, "countdown": (
                f"{label} bucket: {n:,} settled · past the 100 needed, so "
                "calibration speaks here")})
    return {"sport": sport, "resolved_before": 0, "resolved_now": 0,
            "gained": 0, "buckets": buckets, "gate": 100}


def test_the_line_as_it_shipped_is_refused_by_name(tmp_path):
    conn = _ufc_world(tmp_path / "ufc.db")
    shipped = _as_it_shipped(conn, "ufc")
    assert shipped["buckets"][0]["n"] == UFC_POOLED
    with pytest.raises(calibration.PooledBandLine, match="QUESTION 46"):
        calibration.assert_no_pooled_band_line(shipped)
    lawful = _movement(conn, "ufc")
    calibration.assert_no_pooled_band_line(lawful)
    pooled_band = dict(lawful["bands"][0], n=UFC_POOLED, needed=0,
                       past_the_gate=True)
    pooled_band["words"] = language.bucket_countdown_line(
        pooled_band["category_label"], "50-60%", UFC_POOLED, 100)
    for change in (
            {"bands": [pooled_band] + lawful["bands"][1:],
             "line": pooled_band["words"]},
            {"line": "50-60% bucket: 224 settled · past the 100 needed, so "
                     "calibration speaks here"},
            {"bands": [dict(lawful["bands"][0], event_tier=None)]
             + lawful["bands"][1:]},
            {"bands": [dict(lawful["bands"][0], forecasters_counted=[
                "llm", "statistical"])] + lawful["bands"][1:]},
            {"bands": [dict(lawful["bands"][0], tiers_counted=[
                "contender", "fight_night", "numbered"])] + lawful["bands"][1:]},
            {"bands": [dict(lawful["bands"][0], words="50-60% bucket: 9 of 100 "
                       "· 91 more before calibration speaks")]
             + lawful["bands"][1:]},
            {"line": lawful["bands"][0]["words"]},
            {"forecaster": "all"},
            {"gate": 100},
            {"counted_words": None}):
        with pytest.raises(calibration.PooledBandLine, match="QUESTION 46"):
            calibration.assert_no_pooled_band_line(dict(lawful, **change))


@pytest.mark.parametrize("door", ["without the card", "without the forecaster",
                                  "every card's rows named as the asked card's",
                                  # EACH POOL THE FINDING NAMES, ALONE (its
                                  # prover, 2026-10-08): the passes and the
                                  # markets beside the forecasters and cards.
                                  "without its standing rule (every pass)",
                                  "without the market (every market)"])
def test_a_band_counted_over_a_pool_is_refused_by_the_builder(tmp_path,
                                                             monkeypatch, door):
    conn = _ufc_world(tmp_path / "ufc.db")
    real = calibration.resolved

    def pooled(conn, **kw):
        if door == "without the card":
            return real(conn, **dict(kw, event_tier=None))
        if door == "without the forecaster":
            return real(conn, **dict(kw, predictor=None))
        if door == "without the market (every market)":
            return real(conn, **dict(kw, market_type=None, prop_type=None))
        rows = real(conn, **dict(kw, event_tier=None))
        for r in rows:
            r.event_tier = kw.get("event_tier")
        return rows

    if door == "without its standing rule (every pass)":
        # Every pass of a question counted: its early and final forecast two.
        monkeypatch.setattr(calibration, "standing_row_clause", lambda *a, **k: "")
    else:
        monkeypatch.setattr(calibration, "resolved", pooled)
    with pytest.raises(calibration.PooledBandLine, match="QUESTION 46"):
        views.digest(conn, sport="ufc", day="2026-10-08")


def test_the_door_will_not_count_for_nobody_in_particular(tmp_path):
    conn = _ufc_world(tmp_path / "ufc.db")
    with pytest.raises(calibration.PooledCount, match="QUESTION 46"):
        calibration.band_lines(conn, sport="ufc", predictor="all")


def test_a_pooled_band_line_is_refused_by_the_api(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from gridiron import api, auth

    conn = _ufc_world(tmp_path / "ufc.db")
    conn.close()
    real = calibration.resolved
    monkeypatch.setattr(calibration, "resolved",
                        lambda conn, **kw: real(conn, **dict(kw, event_tier=None)))
    token = "test-token-for-the-band-line-per-category"
    monkeypatch.setenv(auth.TOKEN_VAR, token)
    api.set_database(tmp_path / "ufc.db")
    try:
        with TestClient(api.app) as client:
            client.post("/auth/login", json={"token": token})
            peek = client.get("/api/digest", params={"sport": "ufc", "peek": "true"})
            day = client.get("/api/digest", params={"sport": "ufc",
                                                    "day": "2026-09-05"})
    finally:
        api.set_database(None)
    assert peek.status_code == 500 and day.status_code == 500
    assert "QUESTION 46" in peek.json()["detail"]


# --- the gate ----------------------------------------------------------------

def test_the_gate_names_a_pooled_band_line(tmp_path, monkeypatch):
    conn = _ufc_world(tmp_path / "ufc.db")
    audit.check_the_greeting_band_line_is_one_categorys(conn)    # lawful
    real = calibration.resolved
    monkeypatch.setattr(calibration, "resolved",
                        lambda conn, **kw: real(conn, **dict(kw, predictor=None)))
    with pytest.raises(audit.LawViolation, match="NOT ONE CATEGORY'S") as caught:
        audit.check_the_greeting_band_line_is_one_categorys(conn)
    assert "ufc, statistical" in str(caught.value)


def test_the_gate_makes_the_call():
    """Step 2 of `tools/verify.py` calls the check."""
    source = (Path(config.PACKAGE_ROOT).parent / "tools" / "verify.py").read_text(
        encoding="utf-8")
    step = next(n for n in ast.parse(source).body
                if isinstance(n, ast.FunctionDef) and n.name == "step_2_guards")
    called = {n.attr for n in ast.walk(step) if isinstance(n, ast.Attribute)}
    assert "check_the_greeting_band_line_is_one_categorys" in called


# --- the page -----------------------------------------------------------------

def test_the_page_draws_the_line_and_its_tip_and_never_another_sports():
    """The renderer places the server's line and tooltip, and a greeting
    refused for a pooled band takes its line with it: left standing, the line
    above this sport's slate was the PREVIOUS sport's (LAW 6)."""
    source = (Path(config.PACKAGE_ROOT) / "web" / "app.js").read_text(encoding="utf-8")
    paint = source[source.index("function paintDigest"):
                   source.index("async function renderGreeting")]
    assert "movement.line" in paint and "movement.line_tip" in paint
    assert "buckets" not in paint
    assert "data.count_words" in paint and "data.counted_words" in paint
    greet = source[source.index("async function renderGreeting"):]
    failed = greet[greet.index("catch (err)"):greet.index("console.error('greeting failed")]
    assert re.search(r"greet-countdown", failed) and "textContent = ''" in failed


def test_the_drawn_line_is_the_servers_in_chromium(page):
    drawn = page.evaluate("""async () => {
        const node = document.getElementById('greet-countdown');
        const sport = (document.querySelector('#sport-tabs button[aria-current="true"]')
                       || {}).dataset;
        const d = await (await fetch('/api/digest?peek=true&sport=' + (sport ? sport.sport : 'nfl'))).json();
        return { text: node.textContent, title: node.title, hidden: node.hidden,
                 line: (d.movement || {}).line, tip: (d.movement || {}).line_tip,
                 today: (d.today || {}).line, msg: document.getElementById('greet-msg').textContent };
    }""")
    assert drawn["line"] or drawn["today"], drawn
    if drawn["line"]:
        assert drawn["text"] == drawn["line"] and drawn["title"] == drawn["tip"], drawn
        assert re.match(r"^[a-z][^:]*, (statistical|reasoning pass), \d", drawn["text"]), drawn
    else:
        assert drawn["text"] == drawn["today"] and "every market" in drawn["text"], drawn
    assert "bucket" not in drawn["text"]
    assert page.page_errors == []


def test_a_refused_greeting_leaves_no_other_sports_line_in_chromium(page):
    before = page.evaluate("document.getElementById('greet-countdown').textContent")
    assert before, "the first sport's greeting drew no line to leave behind"
    page.route("**/api/digest**", lambda route: route.fulfill(
        status=500, content_type="application/json",
        body='{"detail": "QUESTION 46: refused for the test"}'))
    other = page.evaluate("""() => [...document.querySelectorAll('#sport-tabs button')]
        .map(b => b.dataset.sport).find(s => s !== document.querySelector(
            '#sport-tabs button[aria-current="true"]').dataset.sport)""")
    page.click(f"#sport-tabs button[data-sport='{other}']")
    page.wait_for_function(
        "() => { const n = document.getElementById('greet-countdown');"
        " return n.hidden && n.textContent === ''; }", timeout=15000)
    # THE SWITCH IS LET FINISH BEFORE THE PAGE CLOSES (2026-10-08): the rest
    # of it -- the other sport's meta, record and slate -- is asked of the
    # suite's shared server after the greeting fails. As first written the
    # test ended with those requests in flight, and the whole suite failed a
    # later test on the shared world (the Results table's redraw race in
    # `test_prompt_disclosure.py`) three runs of three, where with this
    # module set aside, or its two browser tests deselected, it passed.
    # Waited on the slate's own sport pill, never a clock.
    label = page.evaluate(
        f"() => document.querySelector(\"#sport-tabs button[data-sport='{other}']\")"
        ".firstChild.textContent.trim()")
    page.wait_for_function(
        "(label) => ((document.getElementById('games-sport') || {}).textContent"
        " || '').trim() === label"
        " && !document.getElementById('games-updating').offsetParent",
        arg=label, timeout=30000)
    page.unroute("**/api/digest**")
