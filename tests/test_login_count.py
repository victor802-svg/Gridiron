"""The login glance counts standing questions, as Picks does (UI audit
finding 12, 2026-09-05). It said "NFL 152 picks this week" against Picks'
"All 107": every unresolved row, early and final passes both. One clause
counts the record everywhere."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from gridiron import views


def _open_for(conn, sport):
    return next(s["open"] for s in views.login_glance(conn)["sports"] if s["sport"] == sport)


def test_two_passes_on_one_question_count_once(world_copy):
    conn = world_copy
    game = conn.execute("SELECT * FROM games WHERE sport IS NOT NULL LIMIT 1").fetchone()
    sport = game["sport"]
    before = _open_for(conn, sport)
    kickoff = (datetime.now(timezone.utc) + timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    conn.execute(
        "INSERT INTO games (id, sport, season, week, game_type, home, away, kickoff_utc, status, league_date)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'scheduled', ?)",
        ("test_pair_game", sport, game["season"], 99, game["game_type"], game["home"], game["away"],
         kickoff, kickoff[:10]))
    proto = conn.execute(
        "SELECT * FROM predictions WHERE sport = ? AND predictor = 'statistical' LIMIT 1", (sport,)).fetchone()
    first = (datetime.now(timezone.utc) - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    second = (datetime.now(timezone.utc) - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    for stamp, pass_kind in ((first, "early"), (second, "final")):
        conn.execute(
            "INSERT INTO predictions (created_utc, sport, game_id, market_type, subject, line_asked,"
            " model_prob, model_side, predictor, pass_kind, factor_set_version, factors_json, reasoning)"
            " VALUES (?, ?, 'test_pair_game', ?, ?, ?, 0.6, ?, 'statistical', ?, ?, '{}', 'test pair')",
            (stamp, sport, proto["market_type"], proto["subject"], proto["line_asked"],
             proto["model_side"], pass_kind, proto["factor_set_version"]))
    conn.commit()
    after = _open_for(conn, sport)
    assert after == before + 1, f"two passes on one question counted as {after - before}"
