"""Surfaces the audit of 2026-09-05 found leaking, each pinned here.

Every one of these reached a page because the browser suite's world leaves
the surface EMPTY: no task_runs row, no baseball slate, no college slate on
Results, no tiered sport on Record. A plain-words scan cannot see a string
that is never rendered, so each string is composed here from a seeded shape
and scanned directly.
"""
from __future__ import annotations

import re

import pytest

from gridiron import audit, calibration, config, db, language, tasks, views


@pytest.fixture
def mlb_season(monkeypatch):
    """Point the tasks at the fixture's season, as test_scheduler does."""
    seasons = dict(config.SPORT_CURRENT_SEASON)
    seasons["mlb"] = 2025
    monkeypatch.setattr(config, "SPORT_CURRENT_SEASON", seasons)


# --- the Health panel's task detail -----------------------------------------

def test_counted_never_writes_a_bracketed_plural():
    assert language.counted(1, "prediction") == "1 prediction"
    assert language.counted(41, "prediction") == "41 predictions"
    assert language.counted(0, "warning") == "0 warnings"


def test_a_slate_key_never_reaches_a_task_detail(conn):
    conn.execute(
        "INSERT INTO games (id, sport, season, week, game_type, kickoff_utc,"
        " home, away, status, league_date) VALUES ('cfb_probe','cfb',2026,"
        " 20260905,'REG','2026-09-05T23:30:00Z','UGA','CLEM','scheduled',"
        " '2026-09-05')")
    conn.execute(
        "INSERT INTO games (id, sport, season, week, game_type, kickoff_utc,"
        " home, away, status, league_date) VALUES ('mlb_probe','mlb',2026,"
        " 161,'REG','2026-09-05T02:10:00Z','SF','NYM','scheduled',"
        " '2026-09-04')")
    conn.commit()
    said = tasks._slate_words(conn, "cfb", 2026, 20260905)
    assert "20260905" not in said and "Saturday 5 September" in said
    said = tasks._slate_words(conn, "mlb", 2026, 161)
    assert "161" not in said and "Friday 4 September" in said, said
    assert audit.plain_words_violations(said) == []


def test_the_predict_task_reports_its_slate_in_words(mlb_league, mlb_season):
    out = tasks.run_task(mlb_league, "predict:mlb", use_llm=False)
    detail = out["detail"]
    assert "(s)" not in detail
    assert re.search(r"\bslate \d", detail) is None, detail
    assert audit.plain_words_violations(detail) == [], detail


# --- three surfaces the browser world leaves empty --------------------------

def _probe_game(conn, gid, sport, week, league_date, kickoff):
    conn.execute(
        "INSERT INTO games (id, sport, season, week, game_type, kickoff_utc,"
        " home, away, status, league_date) VALUES (?,?,2026,?,'REG',?,'HOM',"
        " 'AWY','scheduled',?)", (gid, sport, week, kickoff, league_date))


def _probe_prediction(conn, gid, sport, market="moneyline", side="win"):
    conn.execute(
        "INSERT INTO predictions (created_utc, sport, game_id, market_type,"
        " subject, line_asked, model_prob, model_side, predictor,"
        " factor_set_version, factors_json, reasoning)"
        " VALUES ('2026-09-01T00:00:00Z',?,?,?,'HOM',NULL,0.61,?,'statistical',"
        " 'fs2','{}','probe')", (sport, gid, market, side))


def test_the_slate_chooser_says_the_date_for_a_day_slate(conn):
    """Baseball keys a slate by an ordinal. "Day 155, 2026" is that ordinal
    with a word beside it, and it sat in the chooser on every MLB visit."""
    _probe_game(conn, "mlb_probe", "mlb", 161, "2026-09-04", "2026-09-05T02:10:00Z")
    _probe_prediction(conn, "mlb_probe", "mlb")
    conn.commit()
    labels = [w["label"] for w in views.available_weeks(conn, "mlb")]
    assert labels, "nothing to choose from"
    for label in labels:
        assert not re.search(r"\bDay \d", label), label
        assert audit.plain_words_violations(label) == [], label
    assert "Friday 4 September" in labels[0]


def test_a_history_row_names_its_slate_in_words(conn):
    """Results printed `'wk ' + week`, which on a college row is the key."""
    _probe_game(conn, "cfb_probe", "cfb", 20260905, "2026-09-05", "2026-09-05T23:30:00Z")
    _probe_prediction(conn, "cfb_probe", "cfb")
    conn.commit()
    item = views.history(conn, sport="cfb")["items"][0]
    assert item["slate_label"].startswith("Saturday 5 September")
    assert audit.plain_words_violations(item["slate_label"]) == []
    js = audit._without_comments(
        (config.PACKAGE_ROOT / "web" / "app.js").read_text(encoding="utf-8"), "js")
    assert "'wk ' + i.week" not in js, "the renderer composes the slate key again"
    assert "i.slate_label" in js


def test_a_tier_category_is_labelled_in_words(conn):
    """The UFC record printed `fight_night` on every tiered row."""
    for payload in (calibration.scorecard(conn, sport="ufc")["categories"],
                    [c for v in calibration.version_comparison(conn, sport="ufc")["versions"]
                     for c in v["categories"]]):
        tiered = [c for c in payload if c.get("event_tier")]
        assert tiered, "no tiered category to label"
        for c in tiered:
            assert "_" not in c["category_label"], c["category_label"]
            assert c["category_label"].startswith(
                language.MARKET_WORDS.get(c["market"], c["market"]))
            assert language.tier_label(c["event_tier"]) in c["category_label"]
            assert audit.plain_words_violations(c["category_label"]) == []
    js = (config.PACKAGE_ROOT / "web" / "app.js").read_text(encoding="utf-8")
    assert "c.category_label" in js, "the renderer ignores the server's words"


# --- the hero on a slate with no line ---------------------------------------

def test_the_hero_tag_does_not_claim_a_disagreement_without_a_line():
    """On the UFC slate of 2026-09-05 a card reading "no line to compare it
    with" led the page under "Sharpest disagreement tomorrow"."""
    tags = language.hero_tags("Tomorrow")
    assert "disagreement" not in tags["no_line"].lower()
    assert "no line" in tags["no_line"]
    assert tags["no_line"].endswith("against") or "compare" in tags["no_line"]
    js = (config.PACKAGE_ROOT / "web" / "app.js").read_text(encoding="utf-8")
    assert "'no_line'" in js, "the renderer never picks the no-line sentence"


def test_lineless_cards_rank_by_confidence_among_themselves():
    """Every lineless card tied at -1, so the leader was whichever the query
    returned first."""
    cards = [{"abs_gap": -1.0, "model_prob": 0.61},
             {"abs_gap": -1.0, "model_prob": 0.80},
             {"abs_gap": 0.05, "model_prob": 0.55}]
    cards.sort(key=views._card_order, reverse=True)
    assert [c["model_prob"] for c in cards] == [0.55, 0.80, 0.61]



# --- one standing clause for every count --------------------------------------

def _settled_pair(conn):
    game = conn.execute(
        "SELECT id, kickoff_utc FROM games WHERE sport = 'nfl'"
        " AND kickoff_utc IS NOT NULL LIMIT 1").fetchone()
    conn.execute("UPDATE games SET status = 'final', home_score = 30,"
                 " away_score = 20 WHERE id = ?", (game["id"],))
    for pass_kind, created in (("early", "2025-01-01T00:00:00Z"),
                               ("final", "2025-01-01T12:00:00Z")):
        conn.execute(
            "INSERT INTO predictions (created_utc, sport, game_id, market_type,"
            " subject, line_asked, model_prob, model_side, predictor, pass_kind,"
            " factor_set_version, factors_json, reasoning, resolved_utc, outcome)"
            " VALUES (?,'nfl',?,'spread','PAIR',-3.5,0.6,'cover','statistical',"
            " ?,?,'{}','pair',?,1)",
            (created, game["id"], pass_kind, config.FACTOR_SET_VERSION,
             db.utcnow()))
    conn.commit()


def test_the_version_table_counts_forecasts_not_rows(league):
    _settled_pair(league)
    entry = next(v for v in calibration.version_comparison(league, sport="nfl")["versions"]
                 if v["version"] == config.FACTOR_SET_VERSION)
    assert entry["n"] == 1, "an early row a final pass superseded was counted"
    assert entry["predictions_written"] == 1


def test_the_pace_counts_standing_rows_only(league):
    _settled_pair(league)
    n, days = calibration.recent_settled(league, sport="nfl", since="2000-01-01T00:00:00Z")
    assert (n, days) == (1, 1)
