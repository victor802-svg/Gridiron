"""The reasoning pass runs on game markets only (ruling E1, 2026-09-06).

Declared and dated in config; a prop question the statistical model answers
is counted as routed off, never put to the LLM, and never `degraded`;
existing LLM prop rows stand and their curves say the count is final.
"""
from __future__ import annotations

import pytest

from gridiron import audit, config, horizon, language, run
from gridiron.factors import store
from gridiron.model import baseline
from tests.test_predict import StubClient


@pytest.fixture
def trained_all(league):
    store.sync_registry(league)
    baseline.train_all(league, (2025,), l2=1.0, note="test", min_rows=20)
    return league


def test_the_roster_is_game_markets_only_and_dated():
    assert config.LLM_ROUTING_DECLARED.startswith("2026-09-06")
    for sport in config.SPORTS:
        roster = config.LLM_MARKETS_BY_SPORT[sport]
        assert roster, sport
        for market in roster:
            assert market in config.SPORT_MARKETS[sport]
            assert market not in config.SPORT_PROP_MARKETS.get(sport, ())
    assert config.llm_routed("nfl", "spread")
    assert not config.llm_routed("nfl", "passing_yards")
    assert config.llm_routed("ufc", "moneyline") and not config.llm_routed("ufc", "rounds")
    assert audit.llm_routing_faults() == []


def test_a_prop_question_is_counted_off_and_the_llm_is_not_asked(trained_all):
    client = StubClient(['{"probability": 0.63, "reasoning": "The home rating is better."}'] * 200)
    result = run.run_week(trained_all, 2025, 7, include_props=True, use_llm=True, llm_client=client)
    rows = trained_all.execute(
        "SELECT predictor, market_type, COUNT(*) AS n FROM predictions"
        " GROUP BY predictor, market_type").fetchall()
    by = {(r["predictor"], r["market_type"]): r["n"] for r in rows}
    props_stat = by.get(("statistical", "prop"), 0)
    assert props_stat > 0, "the fixture wrote no prop questions; the test proves nothing"
    assert ("llm", "prop") not in by, "a prop question reached the reasoning pass"
    games_stat = sum(n for (p, m), n in by.items() if p == "statistical" and m != "prop")
    games_llm = sum(n for (p, m), n in by.items() if p == "llm")
    assert games_llm == games_stat, (by, "the LLM answered a different set of game questions")
    assert len(client.prompts) == games_llm, "the LLM was asked more than it answered"
    assert result["llm_routed_off"] == props_stat
    # counted, said, and not a degradation
    assert any("game markets only" in line for line in result.get("skipped", []) or [])
    assert not any("llm" in k for k in (result.get("degradations") or {}))


def test_the_guard_sees_a_prop_market_on_the_roster(monkeypatch):
    monkeypatch.setitem(config.LLM_MARKETS_BY_SPORT, "mlb", config.LLM_MARKETS_BY_SPORT["mlb"] + ("batter_hits",))
    faults = audit.llm_routing_faults()
    assert faults and "batter_hits" in faults[0] and "prop" in faults[0]
    with pytest.raises(audit.LawViolation):
        audit.check_llm_runs_on_game_markets_only()


def test_an_llm_prop_curve_says_its_count_is_final(world_copy):
    conn = world_copy
    sport = conn.execute("SELECT sport FROM predictions LIMIT 1").fetchone()[0]
    prop = next(iter(config.SPORT_PROP_MARKETS[sport]))
    out = horizon.llm_routed_off_outlook(conn, sport, prop)
    assert out["routed_off"]["since"] == config.LLM_ROUTING_DECLARED
    assert out["slates_remaining"] == 0 and out["expected"] == out["resolved"]
    assert out["message"] == language.llm_routed_off_line(out["resolved"], out["gate"], config.LLM_ROUTING_DECLARED)
    assert "final count" in out["message"] and audit.plain_words_violations(out["message"]) == []
    from gridiron import calibration
    sc = calibration.scorecard(conn, sport=sport)
    llm_props = [c for c in sc["categories"] if c["category"].endswith("/ llm") and c["market"] in config.SPORT_PROP_MARKETS[sport]]
    assert llm_props, "no LLM prop category on the scorecard"
    for c in llm_props:
        assert "final count" in c["outlook"]["message"], c["category"]
    game_llm = [c for c in sc["categories"] if c["category"].endswith("/ llm") and c["market"] in config.LLM_MARKETS_BY_SPORT[sport]]
    for c in game_llm:
        assert "outlook" not in c or "final count" not in (c.get("outlook") or {}).get("message", "")
