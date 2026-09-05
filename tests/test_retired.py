"""A retired market is not asked (R1, 2026-09-05)."""
from __future__ import annotations

import pytest

from gridiron import audit, calibration, config, horizon, language, views
from gridiron.model import questions
from gridiron.model.question import Question
from gridiron.sports import mlb as mlb_sport

RETIRED = ("mlb", "batter_home_runs")


def test_the_retirement_is_declared_and_dated():
    entry = config.retired_market(*RETIRED)
    assert entry == {"retired": "2026-09-05", "reason": "operator ruling"}
    assert config.RETIRED_MARKETS_DECLARED == "2026-09-05"
    assert config.retired_market("mlb", "batter_hits") is None


def test_the_declared_roster_keeps_it_and_the_active_roster_does_not():
    assert "batter_home_runs" in config.SPORT_MARKETS["mlb"], "retired, not deleted"
    assert "batter_home_runs" not in config.active_markets("mlb")
    assert "batter_home_runs" not in config.active_prop_markets("mlb")
    assert config.active_prop_markets("mlb") == (
        "batter_hits", "batter_total_bases", "batter_strikeouts", "pitcher_strikeouts")
    assert config.active_markets("nfl") == config.SPORT_MARKETS["nfl"]


def _hr_question(created=None):
    return Question(sport="mlb", game_id="g", market_type="prop", market="batter_home_runs",
                    subject="Someone batter_home_runs", line_asked=0.5,
                    claim="Someone hits a home run", yes_label="over", no_label="under",
                    player_id="1", stat="batter_home_runs")


def test_questions_skip_and_refuse_a_retired_market():
    hits = Question(sport="mlb", game_id="g", market_type="prop", market="batter_hits",
                    subject="Someone batter_hits", line_asked=0.5, claim="c",
                    yes_label="over", no_label="under", player_id="1", stat="batter_hits")
    kept = questions.without_retired([_hr_question(), hits])
    assert [q.stat for q in kept] == ["batter_hits"]
    with pytest.raises(questions.RetiredMarket) as exc:
        questions.assert_market_active(_hr_question())
    assert "batter_home_runs" in str(exc.value) and "2026-09-05" in str(exc.value)
    questions.assert_market_active(hits)


def test_the_props_cap_fills_without_it(conn, monkeypatch):
    """A retired market takes no share of the day's cap."""
    def candidates(_conn, game):
        return [{"game_id": game["id"], "market": m, "subject_id": i, "team": "HOM",
                 "volume": 4.0, "line_asked": 0.5}
                for i, m in enumerate(("batter_home_runs", "batter_hits",
                                       "batter_total_bases", "pitcher_strikeouts"))]
    monkeypatch.setattr(mlb_sport, "prop_candidates", candidates)
    chosen = mlb_sport.select_day_props(conn, [{"id": "g1"}], cap=10)
    assert chosen and all(c["market"] != "batter_home_runs" for c in chosen)


def test_picks_has_no_tab_for_it_and_record_keeps_a_greyed_row(conn):
    offered = [t["market"] for t in views._market_tabs("mlb", [])]
    assert "batter_home_runs" not in offered and "batter_hits" in offered
    assert audit.retired_in_picks_faults() == []
    cats = [c for c in calibration.scorecard(conn, sport="mlb")["categories"]
            if c["market"] == "batter_home_runs"]
    assert cats and all(c["retired"]["retired"] == "2026-09-05" for c in cats)
    assert all(c["category_label"].startswith("home runs · retired") for c in cats)
    hits = [c for c in calibration.scorecard(conn, sport="mlb")["categories"]
            if c["market"] == "batter_hits"]
    assert hits and all(c["retired"] is None for c in hits)


def test_the_market_words_say_retired_and_the_outlook_projects_nothing(conn):
    assert language.market_words("mlb", "batter_home_runs") == "home runs · retired"
    assert language.market_words("mlb", "batter_hits") == "hits"
    out = horizon.market_outlook(conn, "mlb", "batter_home_runs", season=2026)
    assert out["retired"] and out["expected_is_an_extrapolation"] is False
    assert "retired" in out["message"] and "final count" in out["message"]
    assert audit.plain_words_violations(out["message"]) == []


def test_a_row_at_the_retirement_boundary_is_named_and_one_before_is_not(conn):
    conn.execute(
        "INSERT INTO games (id, sport, season, week, game_type, kickoff_utc,"
        " home, away, status) VALUES ('rt','mlb',2026,170,'REG',"
        " '2026-09-06T23:00:00Z','HOM','AWY','scheduled')")
    row = ("INSERT INTO predictions (created_utc, sport, game_id, market_type,"
           " prop_type, subject, line_asked, model_prob, model_side, predictor,"
           " pass_kind, factor_set_version, factors_json, reasoning)"
           " VALUES (?,'mlb','rt','prop','batter_home_runs',?,0.5,0.77,'under',"
           " 'statistical','early','fs2','{}','t')")
    conn.execute(row, ("2026-09-04T23:59:59Z", "Before batter_home_runs"))
    conn.execute(row, ("2026-09-05T00:00:00Z", "At batter_home_runs"))
    conn.commit()
    before, at = [r[0] for r in conn.execute("SELECT id FROM predictions ORDER BY id")]
    faults = audit.retired_market_faults(conn)
    assert [f.split()[1] for f in faults] == [str(at)], faults
    assert "2026-09-05" in faults[0] and "operator ruling" in faults[0]
    assert str(before) not in " ".join(faults)
