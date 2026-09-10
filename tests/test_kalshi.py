"""Kalshi as a read-only market source (ruling D3, 2026-09-06): the ticker
crosswalk measured and aliased by name, the ladder parsed into quote rows,
the rows refused before a prediction exists (LAW 1), the name quarantined."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from gridiron import audit, db
from gridiron.data import sources as http
from gridiron.market import kalshi

FIX = Path(__file__).parent / "fixtures" / "kalshi"


def _game(home, away, day, gid="2026_01_NE_SEA"):
    return {"id": gid, "home": home, "away": away, "league_date": day, "kickoff_utc": day + "T00:20:00Z"}


def test_the_event_ticker_is_the_series_the_league_date_and_away_then_home():
    assert kalshi.event_ticker("nfl", "spread", _game("SEA", "NE", "2026-09-09")) == "KXNFLSPREAD-26SEP09NESEA"
    assert kalshi.event_ticker("nfl", "total", _game("KC", "DEN", "2026-09-14")) == "KXNFLTOTAL-26SEP14DENKC"
    # the two measured aliases, written the venue's way
    assert kalshi.event_ticker("nfl", "spread", _game("LA", "SF", "2026-09-10")) == "KXNFLSPREAD-26SEP10SFLAR"
    assert kalshi.event_ticker("nfl", "spread", _game("JAX", "CLE", "2026-09-13")) == "KXNFLSPREAD-26SEP13CLEJAC"
    assert kalshi.event_ticker("cfb", "spread", _game("UTAH", "ARK", "2026-09-12")) == "KXNCAAFSPREAD-26SEP12ARKUTAH"
    assert kalshi.event_ticker("cfb", "spread", _game("KU", "MIZ", "2026-09-11")) == "KXNCAAFSPREAD-26SEP11MIZZKU"
    # no series for the pair, or no date: none, never a guess
    assert kalshi.event_ticker("ufc", "moneyline", _game("A", "B", "2026-09-12")) is None
    assert kalshi.event_ticker("nfl", "spread", {"home": "SEA", "away": "NE", "league_date": None, "kickoff_utc": None}) is None


def test_the_measured_crosswalk_matches_every_open_nfl_event():
    events = json.loads((FIX / "nfl_spread_events.json").read_text(encoding="utf-8"))["events"]
    ours = [("SEA", "NE", "2026-09-09"), ("LA", "SF", "2026-09-10"), ("CAR", "CHI", "2026-09-13"),
            ("CIN", "TB", "2026-09-13"), ("DET", "NO", "2026-09-13"), ("HOU", "BUF", "2026-09-13"),
            ("IND", "BAL", "2026-09-13"), ("JAX", "CLE", "2026-09-13"), ("PIT", "ATL", "2026-09-13"),
            ("TEN", "NYJ", "2026-09-13"), ("LAC", "ARI", "2026-09-13"), ("LV", "MIA", "2026-09-13"),
            ("MIN", "GB", "2026-09-13"), ("PHI", "WAS", "2026-09-13"), ("NYG", "DAL", "2026-09-13"),
            ("KC", "DEN", "2026-09-14")]
    composed = {kalshi.event_ticker("nfl", "spread", _game(h, a, d)) for h, a, d in ours}
    theirs = {e["event_ticker"] for e in events}
    assert composed == theirs, (composed - theirs, theirs - composed)
    assert kalshi.CROSSWALK_MEASURED["nfl"]["matched"] == 16
    assert kalshi.CROSSWALK_MEASURED["nfl"]["measured_utc"].startswith("2026-09-06")


def test_the_spread_ladder_is_read_from_the_home_side():
    payload = json.loads((FIX / "nfl_spread_NESEA.json").read_text(encoding="utf-8"))
    game = _game("SEA", "NE", "2026-09-09")
    quotes, unreadable = kalshi.parse_markets("nfl", "spread", game, payload)
    assert unreadable == [] and len(quotes) == len(payload["markets"])
    by = {q["ticker"]: q for q in quotes}
    sea5 = by["KXNFLSPREAD-26SEP09NESEA-SEA5"]      # "Seattle wins by over 4.5 points"
    assert sea5["yes_side"] == "home" and sea5["line"] == -4.5 and sea5["quantity"] == "home_margin"
    assert sea5["yes_bid"] == 0.45 and sea5["yes_ask"] == 0.46 and sea5["last_price"] == 0.45
    ne6 = by["KXNFLSPREAD-26SEP09NESEA-NE6"]        # "New England wins by over 5.5 points"
    assert ne6["yes_side"] == "away" and ne6["line"] == 5.5
    # the same ladder read for a game whose sides are the other way round
    flipped, _ = kalshi.parse_markets("nfl", "spread", _game("NE", "SEA", "2026-09-09"), payload)
    assert {q["ticker"]: q for q in flipped}["KXNFLSPREAD-26SEP09NESEA-SEA5"]["yes_side"] == "away"
    # a code that is neither side is counted, not attached
    _, bad = kalshi.parse_markets("nfl", "spread", _game("KC", "DEN", "2026-09-09"), payload)
    assert len(bad) == len(payload["markets"])


def test_the_total_and_the_winner_are_read():
    payload = json.loads((FIX / "nfl_total_DENKC.json").read_text(encoding="utf-8"))
    quotes, unreadable = kalshi.parse_markets("nfl", "total", _game("KC", "DEN", "2026-09-14"), payload)
    assert unreadable == [] and quotes
    assert quotes[0]["quantity"] == "total" and quotes[0]["yes_side"] == "over" and quotes[0]["line"] == 63.5
    winner = {"markets": [{"ticker": "KXNFLGAME-26SEP14DENKC-KC", "event_ticker": "KXNFLGAME-26SEP14DENKC",
                           "yes_bid_dollars": "0.6", "yes_ask_dollars": "0.62"},
                          {"ticker": "KXNFLGAME-26SEP14DENKC-DEN", "event_ticker": "KXNFLGAME-26SEP14DENKC",
                           "yes_bid_dollars": "0.38", "yes_ask_dollars": "0.4"}]}
    quotes, unreadable = kalshi.parse_markets("nfl", "moneyline", _game("KC", "DEN", "2026-09-14"), winner)
    assert unreadable == [] and {q["yes_side"] for q in quotes} == {"home", "away"}
    assert all(q["quantity"] == "home_win" and q["line"] is None for q in quotes)


# THE FIXTURE'S CLOCK IS RELATIVE, NOT A DATE (2026-09-10).
#
# These fixtures hard-coded `2026-09-10T00:20:00Z` as the kickoff. The claim
# writer refuses a game already under way, so the moment the wall clock passed
# that instant every claim was refused and the tests failed on code nobody had
# touched. A test that passes only before a certain date is a test with an
# expiry.
#
# TWO DAYS OUT, which is comfortably clear of any window the pipeline cares
# about: the near-start pass looks two hours ahead, and nothing here is about
# what happens close to a start.
def _soon(hours: int = 48) -> str:
    """A kickoff far enough ahead that the fixture is never mid-game."""
    from datetime import datetime, timedelta, timezone
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).strftime(
        "%Y-%m-%dT%H:%M:%SZ")



def _world(tmp_path):
    conn = db.open_db(tmp_path / "venue.db")
    conn.execute("INSERT INTO games (id, sport, season, week, game_type, home, away, kickoff_utc, status, league_date)"
                 " VALUES ('2026_01_NE_SEA', 'nfl', 2026, 1, 'REG', 'SEA', 'NE', ?, 'scheduled', '2026-09-09')",
                 (_soon(),))
    conn.commit()
    return conn


def test_a_quote_cannot_exist_before_a_prediction_for_its_game(tmp_path):
    conn = _world(tmp_path)
    with pytest.raises(sqlite3.IntegrityError, match="LAW 1"):
        conn.execute("INSERT INTO venue_quotes (venue, ticker, event_ticker, sport, game_id, market, quantity,"
                     " line, yes_side, fetched_utc) VALUES ('kalshi', 't', 'e', 'nfl', '2026_01_NE_SEA',"
                     " 'spread', 'home_margin', -4.5, 'home', '2026-09-06T00:00:00Z')")


def test_capture_writes_the_ladder_after_the_rows_exist_and_counts_the_rest(tmp_path, monkeypatch):
    conn = _world(tmp_path)
    conn.execute("INSERT INTO predictions (created_utc, sport, game_id, market_type, subject, line_asked,"
                 " model_prob, model_side, predictor, pass_kind, factor_set_version, factors_json, reasoning)"
                 " VALUES ('2026-09-06T00:00:00Z', 'nfl', '2026_01_NE_SEA', 'spread', 'SEA', -3.5, 0.6, 'cover',"
                 " 'statistical', 'final', 'fs5', '{}', 'test')")
    conn.commit()
    pid = conn.execute("SELECT id FROM predictions").fetchone()[0]
    spread = (FIX / "nfl_spread_NESEA.json").read_bytes()
    asked = []

    def fake_fetch(_conn, url, **kw):
        asked.append(url)
        if "KXNFLSPREAD" in url:
            return spread
        if "KXNFLTOTAL" in url:
            return b'{"markets": []}'
        raise http.SourceUnavailable(url)

    monkeypatch.setattr(http, "fetch", fake_fetch)
    # under the suite's guard the venue is off: nothing asked, and it says so
    assert kalshi.capture_for_predictions(conn, [pid]).get("disabled") == 1 and asked == []
    # the guard turned the venue off; this test stubs the fetch and turns it on
    from gridiron import config
    monkeypatch.setattr(config, "VENUE_CAPTURE", True)
    counts = kalshi.capture_for_predictions(conn, [pid])
    assert counts["games"] == 1 and counts["events"] == 1
    assert counts["quotes"] == 25 and counts["no_event"] == 1 and counts["unavailable"] == 1
    assert all(u.startswith(kalshi.BASE + "/markets?event_ticker=") for u in asked)
    rows = conn.execute("SELECT * FROM venue_quotes WHERE game_id = ? AND market = 'spread'"
                        " ORDER BY line", ("2026_01_NE_SEA",)).fetchall()
    assert len(rows) == 25 and rows[0]["venue"] == "kalshi"
    assert all(r["fetched_utc"] >= "2026-09-06T00:00:00Z" for r in rows)
    # a prop-only prediction asks the venue nothing
    conn.execute("INSERT INTO predictions (created_utc, sport, game_id, market_type, prop_type, subject, line_asked,"
                 " model_prob, model_side, predictor, pass_kind, factor_set_version, factors_json, reasoning)"
                 " VALUES ('2026-09-06T00:00:00Z', 'nfl', '2026_01_NE_SEA', 'prop', 'passing_yards', 'QB', 250.5, 0.6, 'over',"
                 " 'statistical', 'final', 'fs2', '{}', 'test')")
    conn.commit()
    prop_id = conn.execute("SELECT MAX(id) FROM predictions").fetchone()[0]
    asked.clear()
    assert kalshi.capture_for_predictions(conn, [prop_id])["games"] == 0 and asked == []


def test_the_name_stays_inside_the_market_module():
    assert audit.market_source_faults() == []
    assert Path(kalshi.__file__).parent.name == "market"
    assert "kalshi" in audit.MARKET_SOURCE_IDENTIFIERS
    audit.check_prediction_closure()
