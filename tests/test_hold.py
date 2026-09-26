"""A held market is not forecast, and the first screen says so (operator ruling
2026-09-24, "fs5 before it publishes", part 3).

Missing a day of forecasts costs nothing; a day of forecasts from a fit nobody
has checked costs the clean window. So a held market is not asked by either
forecaster, the run records why, and the day strip carries the line.
"""
from __future__ import annotations

from gridiron import audit, config, language, run, views
from gridiron.factors import store
from gridiron.model import activation, baseline
from tests.conftest import asks_only


def _hold(monkeypatch, *markets):
    monkeypatch.setattr(config, "HELD_MARKETS", {
        ("nfl", m): {"held": "2026-09-24", "reason": config.HELD_REASON}
        for m in markets})


def test_a_held_market_is_not_forecast(league, monkeypatch):
    store.sync_registry(league)
    baseline.train(league, "spread", (2025,), l2=1.0, note="test")
    activation.activate_in_a_scratch_world(league)
    asks_only(monkeypatch, "nfl", "spread")     # a spread world (item 2)
    _hold(monkeypatch, "spread")
    result = run.run_week(league, 2025, 7, include_props=False, use_llm=False)
    assert result["written"] == 0
    assert any("held, not forecast" in s for s in result["skipped"])
    # and lifting the hold is all it takes to forecast it again
    _hold(monkeypatch)
    assert run.run_week(league, 2025, 7, include_props=False,
                        use_llm=False)["written"] == 4


def test_the_strip_names_a_held_market(league, monkeypatch):
    store.sync_registry(league)
    for market in ("spread", "moneyline"):
        baseline.train(league, market, (2025,), l2=1.0, note="test")
    activation.activate_in_a_scratch_world(league)
    # the two markets it holds, and nothing else (item 2, 2026-09-26)
    asks_only(monkeypatch, "nfl", "spread", "moneyline")
    run.run_week(league, 2025, 7, include_props=False, use_llm=False)
    _hold(monkeypatch, "spread", "moneyline")
    block = views.freshness(league)
    entry = next(e for e in block["entries"] if e["job"] == "held")
    assert entry["stale"] and entry["sport"] == "nfl"
    assert "spread and moneyline" in entry["words"]
    audit.check_the_strip_shows_a_dead_job({"freshness": block})
    # a strip that drops the line is refused by name
    block["entries"] = [e for e in block["entries"] if e["job"] != "held"]
    assert any("held" in f for f in audit.freshness_faults({"freshness": block}))


def test_the_held_words_are_plain():
    words = language.held_line_words("nfl", ["spread", "moneyline"],
                                     config.HELD_REASON)
    assert audit.plain_words_violations(words) == [], words
    assert audit.advice_word_faults(words) == [], words


def test_a_forecast_written_before_the_hold_is_not_shown(league, monkeypatch):
    """24 September: forecasts were written from the fits a hold then held.
    They stay in the record; the page does not stand behind them."""
    store.sync_registry(league)
    baseline.train(league, "spread", (2025,), l2=1.0, note="test")
    activation.activate_in_a_scratch_world(league)
    asks_only(monkeypatch, "nfl", "spread")     # a spread world (item 2)
    run.run_week(league, 2025, 7, include_props=False, use_llm=False)
    shown = views.week(league, "nfl", 2025, 7)
    assert shown["n"] == 4
    _hold(monkeypatch, "spread")
    held = views.week(league, "nfl", 2025, 7)
    assert held["n"] == 0 and held["superseded"] == 0
