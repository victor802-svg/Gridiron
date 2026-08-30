"""T2/F2: since you last looked.

The proof that matters is `test_the_panel_lists_exactly_what_resolved_since`:
seed resolutions either side of a marked last_seen, and assert the panel names
the later ones and only those, with the movement matching a direct SQL count
rather than the panel's own arithmetic. A digest that is merely plausible is a
digest nobody can trust the next morning.
"""

from __future__ import annotations

import json

import pytest

from gridiron import config, db, views


def _resolve(conn, sport, game_id, subject, prob, outcome, at):
    conn.execute(
        "INSERT INTO predictions (created_utc, sport, game_id, market_type,"
        " subject, model_prob, model_side, predictor, factor_set_version,"
        " factors_json, reasoning, resolved_utc, outcome)"
        " VALUES (?,?,?,'moneyline',?,?,'win','statistical',?,'{}','x',?,?)",
        (at, sport, game_id, subject, prob, config.FACTOR_SET_VERSION, at, outcome),
    )
    conn.commit()


def _final_games(conn, n):
    return [
        r["id"]
        for r in conn.execute(
            "SELECT id FROM games WHERE sport='mlb' AND status='final' LIMIT ?", (n,)
        )
    ]


def test_the_panel_lists_exactly_what_resolved_since(mlb_league):
    """Seeded either side of the marker; only the later ones may appear."""
    games = _final_games(mlb_league, 3)
    _resolve(mlb_league, "mlb", games[0], "OLD1", 0.60, 1, "2026-01-01T10:00:00Z")
    _resolve(mlb_league, "mlb", games[1], "NEW1", 0.55, 1, "2026-01-03T10:00:00Z")
    _resolve(mlb_league, "mlb", games[2], "NEW2", 0.52, 0, "2026-01-03T11:00:00Z")

    d = views.digest(mlb_league, sport="mlb", since="2026-01-02T00:00:00Z")
    assert {s["subject"] for s in d["settled"]} == {"NEW1", "NEW2"}
    assert (d["n"], d["correct"], d["wrong"]) == (2, 1, 1)

    # ...and the movement matches a DIRECT count, not the panel's own sums.
    total = mlb_league.execute(
        "SELECT COUNT(*) FROM predictions WHERE sport='mlb'"
        " AND resolved_utc IS NOT NULL"
    ).fetchone()[0]
    assert d["movement"]["resolved_now"] == total
    assert d["movement"]["resolved_before"] == total - 2


def test_the_brier_matches_the_predictions_it_names(mlb_league):
    games = _final_games(mlb_league, 2)
    _resolve(mlb_league, "mlb", games[0], "A", 0.60, 1, "2026-01-03T10:00:00Z")
    _resolve(mlb_league, "mlb", games[1], "B", 0.40, 0, "2026-01-03T11:00:00Z")
    d = views.digest(mlb_league, sport="mlb", since="2026-01-02T00:00:00Z")
    assert d["brier"] == round((((0.60 - 1) ** 2) + ((0.40 - 0) ** 2)) / 2, 4)


def test_a_voided_prediction_never_appears(mlb_league):
    from gridiron import resolve

    game = _final_games(mlb_league, 1)[0]
    _resolve(mlb_league, "mlb", game, "VOIDED", 0.55, 1, "2026-01-03T10:00:00Z")
    row = mlb_league.execute(
        "SELECT id FROM predictions ORDER BY id DESC LIMIT 1"
    ).fetchone()
    resolve.void_prediction(mlb_league, row["id"], "voided for the test")
    d = views.digest(mlb_league, sport="mlb", since="2026-01-02T00:00:00Z")
    assert "VOIDED" not in {s["subject"] for s in d["settled"]}


def test_the_empty_state_is_plain_words_and_names_the_next_game(mlb_league):
    d = views.digest(mlb_league, sport="mlb", since=db.utcnow())
    assert d["n"] == 0
    assert "Nothing resolved since you last looked" in d["headline"]
    assert "Next MLB games" in d["headline"]


def test_a_day_is_linkable_and_does_not_depend_on_a_marker(mlb_league):
    games = _final_games(mlb_league, 2)
    _resolve(mlb_league, "mlb", games[0], "ONDAY", 0.55, 1, "2026-01-03T10:00:00Z")
    _resolve(mlb_league, "mlb", games[1], "OTHER", 0.55, 1, "2026-01-05T10:00:00Z")
    d = views.digest(mlb_league, sport="mlb", day="2026-01-03")
    assert {s["subject"] for s in d["settled"]} == {"ONDAY"}
    assert d["day"] == "2026-01-03"


# --- the marker -------------------------------------------------------------

def _session(conn, sid):
    conn.execute(
        "INSERT INTO sessions (id, created_utc, expires_utc)"
        " VALUES (?, ?, '2099-01-01T00:00:00Z')",
        (sid, db.utcnow()),
    )
    conn.commit()


def test_the_marker_is_per_sport(mlb_league):
    """A single marker per device meant that opening football burned
    baseball's: the panel then reported "nothing resolved" across six results
    that had landed minutes earlier. It was confidently wrong about the only
    thing it exists to say."""
    _session(mlb_league, "s1")
    views.mark_seen(mlb_league, "s1", "nfl")
    assert views.seen_marker(mlb_league, "s1", "mlb") is None, (
        "reading football moved baseball's marker"
    )
    views.mark_seen(mlb_league, "s1", "mlb")
    assert views.seen_marker(mlb_league, "s1", "mlb") is not None


def test_marking_returns_the_previous_value_so_nothing_is_missed(mlb_league):
    _session(mlb_league, "s2")
    views.mark_seen(mlb_league, "s2", "mlb")
    previous = views.seen_marker(mlb_league, "s2", "mlb")
    assert views.mark_seen(mlb_league, "s2", "mlb") == previous, (
        "the digest would be computed against the NEW marker and always be empty"
    )


# --- warnings travel to the front page --------------------------------------

def test_warnings_reach_the_front_page(mlb_league):
    """A panel nobody visits cannot warn anybody."""
    mlb_league.execute(
        "INSERT INTO task_runs (task, started_utc, finished_utc, result, detail,"
        " payload_json) VALUES ('predict:mlb', '2020-01-01T00:00:00Z',"
        " '2020-01-01T00:00:01Z', 'missed', 'slate 5 began and was not forecast', ?)",
        (json.dumps({"week": 5}),),
    )
    mlb_league.commit()
    d = views.digest(mlb_league, sport="mlb", since=db.utcnow())
    assert "missed" in {w["kind"] for w in d["warnings"]}


def test_a_silent_task_reaches_the_front_page(mlb_league):
    d = views.digest(mlb_league, sport="mlb", since=db.utcnow())
    # Nothing has ever run in a fresh fixture, so every task is silent.
    assert "silent" in {w["kind"] for w in d["warnings"]}


# --- LAW 3 and LAW 6 --------------------------------------------------------

def test_the_digest_writes_nothing(mlb_league):
    before = mlb_league.execute("SELECT COUNT(*) FROM predictions").fetchone()[0]
    views.digest(mlb_league, sport="mlb", since="2026-01-01T00:00:00Z")
    after = mlb_league.execute("SELECT COUNT(*) FROM predictions").fetchone()[0]
    assert before == after


def test_the_api_serves_the_digest_from_the_read_only_handle(db_path, monkeypatch):
    """The web layer's record connection is opened `PRAGMA query_only = ON`, so
    the digest path holds no write capability at all — not by convention, by
    the database refusing (LAW 3)."""
    from fastapi.testclient import TestClient

    from gridiron import api, auth

    monkeypatch.setenv(auth.TOKEN_VAR, "digest-token")
    api.set_database(db_path)
    try:
        with TestClient(api.app) as client:
            client.post("/auth/login", json={"token": "digest-token"})
            assert client.get("/api/digest?sport=mlb").status_code == 200
            with pytest.raises(Exception):
                api.get_conn().execute(
                    "INSERT INTO predictions (created_utc, sport, game_id,"
                    " market_type, subject, model_prob, model_side, predictor,"
                    " factor_set_version, factors_json, reasoning)"
                    " VALUES ('x','mlb','g','moneyline','s',0.5,'win',"
                    "'statistical','fs2','{}','r')"
                )
    finally:
        api.set_database(None)


def test_law_6_the_digest_names_its_sport(mlb_league):
    from gridiron import calibration

    with pytest.raises(calibration.CrossSportAggregation):
        views.digest(mlb_league, sport="all", since=None)
