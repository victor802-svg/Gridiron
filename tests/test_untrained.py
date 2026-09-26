"""A market the run asks and cannot answer fails the run by name, and the day
strip shows it (GRIDIRON_REPAIR item 2; the operator's ruling of 2026-09-23,
built 2026-09-26).

"run.py:99 may never skip an untrained market silently -- a predict run with a
skipped market fails by name, and the day strip shows it."

From 6 to 23 September the NFL and college spread and moneyline were declared
on a factor set nobody trained on the record. Every predict run left them out,
reported success on props and totals or was refused as having answered "every
market it asks", and the daily-run age on the strip stayed fresh because
baseball kept succeeding. These tests hold the three halves of the repair: the
run fails and names the market; the markets that have a model are still
written; the first screen says which market is not forecast and why.
"""
from __future__ import annotations

import dataclasses

import pytest

from gridiron import audit, config, language, run, tasks, views
from gridiron.factors import registry, store
from gridiron.model import activation, baseline


def _world(league, *markets):
    """The synthetic league with the named NFL game markets trained and
    activated, and nothing else."""
    store.sync_registry(league)
    for market in markets:
        baseline.train(league, market, (2025,), l2=1.0, note="test")
    activation.activate_in_a_scratch_world(league)
    return league


def _written(league) -> dict:
    return {r[0]: r[1] for r in league.execute(
        "SELECT market_type, COUNT(*) FROM predictions GROUP BY market_type")}


def test_an_untrained_market_fails_the_run_by_name(league):
    _world(league, "spread", "total")
    with pytest.raises(run.MarketNotTrained, match="moneyline") as caught:
        run.run_week(league, 2025, 7, include_props=False, use_llm=False)
    assert [(m["market"], m["why"]) for m in caught.value.markets] == [
        ("moneyline", "none_active")]
    assert "not forecast" in str(caught.value)
    # WHAT HAS A MODEL IS STILL WRITTEN, and what has none is not.
    assert _written(league) == {"spread": 4, "total": 4}
    assert caught.value.result["written"] == 8


def test_the_scheduled_run_is_recorded_failed_in_plain_words(league, monkeypatch):
    seasons = dict(config.SPORT_CURRENT_SEASON)
    seasons["nfl"] = 2025
    monkeypatch.setattr(config, "SPORT_CURRENT_SEASON", seasons)
    _world(league, "spread", "total")
    result = tasks.run_task(league, "predict:nfl", use_llm=False)
    assert result["result"] == "failed"
    assert result["detail"].startswith("MarketNotTrained: ")
    assert "moneyline" in result["detail"]
    # The Health panel's words: the class name is gone and nothing in the
    # sentence is an identifier.
    words = language.task_detail_words(result["detail"])
    assert not words.startswith("MarketNotTrained")
    assert audit.plain_words_violations(words) == [], words


def test_a_rerun_of_an_open_slate_fails_again_and_writes_nothing_twice(league):
    """THE REFUSAL THAT HID IT: the rerun is no longer refused as answered
    over a market it never asked."""
    _world(league, "spread", "total")
    with pytest.raises(run.MarketNotTrained):
        run.run_week(league, 2025, 7, include_props=False, use_llm=False)
    first = _written(league)
    with pytest.raises(run.MarketNotTrained, match="moneyline"):
        run.run_week(league, 2025, 7, include_props=False, use_llm=False)
    assert _written(league) == first
    assert not run.already_answered(league, "nfl", 2025, 7,
                                    include_props=False)["refuse"]


def test_once_the_market_has_a_model_the_run_passes_and_a_rerun_is_refused(league):
    _world(league, "spread", "total")
    with pytest.raises(run.MarketNotTrained):
        run.run_week(league, 2025, 7, include_props=False, use_llm=False)
    baseline.train(league, "moneyline", (2025,), l2=1.0, note="test")
    activation.activate_in_a_scratch_world(league)
    result = run.run_week(league, 2025, 7, include_props=False, use_llm=False)
    assert result["written"] == 4          # the moneyline, and only it
    with pytest.raises(run.SlateAlreadyAnswered, match="answered once"):
        run.run_week(league, 2025, 7, include_props=False, use_llm=False)


def test_a_version_declared_and_never_trained_fails_the_run(league, monkeypatch):
    """The act of 6 September: a new factor set declared for a market whose
    model in use was fitted to the old one."""
    _world(league, "spread", "moneyline", "total")
    monkeypatch.setitem(config.FACTOR_SET_VERSIONS, ("nfl", "moneyline"),
                        "fs-declared-never-trained")
    with pytest.raises(run.MarketNotTrained,
                       match="another set of factors") as caught:
        run.run_week(league, 2025, 7, include_props=False, use_llm=False)
    assert [(m["market"], m["why"]) for m in caught.value.markets] == [
        ("moneyline", "another_set")]
    assert "fs-declared" not in str(caught.value)


def test_a_fit_reading_a_retired_factor_fails_the_run(league, monkeypatch):
    """The skip one question at a time (2026-09-24) is no longer silent
    either: the markets whose fit reads the retired factor are named."""
    _world(league, "spread", "moneyline", "total")
    reads = [m for m in ("spread", "moneyline", "total")
             if "srs_diff" in baseline.load_fit(league, f"nfl:{m}").names]
    assert reads, "the fixture's fits should read the rating"
    monkeypatch.setitem(registry.REGISTRY, "srs_diff", dataclasses.replace(
        registry.REGISTRY["srs_diff"], active=False))
    with pytest.raises(run.MarketNotTrained,
                       match="no longer computed") as caught:
        run.run_week(league, 2025, 7, include_props=False, use_llm=False)
    assert sorted(m["market"] for m in caught.value.markets) == sorted(reads)
    assert {m["why"] for m in caught.value.markets} == {"factor_not_computed"}
    assert set(_written(league)) == {"spread", "moneyline", "total"} - set(reads)


def test_a_held_market_is_not_untrained(league, monkeypatch):
    """A held market is not asked, and the strip already has its own line."""
    _world(league, "spread", "total")
    monkeypatch.setattr(config, "HELD_MARKETS", {("nfl", "moneyline"): {
        "held": "2026-09-26", "reason": config.HELD_REASON}})
    result = run.run_week(league, 2025, 7, include_props=False, use_llm=False)
    assert result["written"] == 8
    assert baseline.untrained_markets(league, "nfl", include_props=False) == []


def test_a_retired_market_is_not_untrained(league, monkeypatch):
    """A retired market is over, not missing (R1)."""
    _world(league, "spread", "total")
    monkeypatch.setitem(config.RETIRED_MARKETS, ("nfl", "moneyline"), {
        "retired": "2026-09-01", "from": "2026-09-01T00:00:00Z",
        "reason": "a test world that retires it"})
    result = run.run_week(league, 2025, 7, include_props=False, use_llm=False)
    assert result["written"] == 8
    assert baseline.untrained_markets(league, "nfl", include_props=False) == []


def test_a_run_that_asks_no_props_is_not_failed_by_them(league):
    _world(league, "spread", "moneyline", "total")
    result = run.run_week(league, 2025, 7, include_props=False, use_llm=False)
    assert result["written"] == 12
    assert baseline.untrained_markets(league, "nfl", include_props=False) == []
    assert {m["market"] for m in baseline.untrained_markets(league, "nfl")} == set(
        config.SPORT_PROP_MARKETS["nfl"])


def test_the_strip_names_the_market_that_is_not_forecast(league):
    _world(league, "spread", "total")
    with pytest.raises(run.MarketNotTrained):
        run.run_week(league, 2025, 7, include_props=False, use_llm=False)
    block = views.freshness(league)
    entry = next(e for e in block["entries"] if e["job"] == "untrained")
    assert entry["stale"] and entry["sport"] == "nfl"
    assert "moneyline" in entry["markets"]
    assert entry["words"].startswith("NFL ")
    assert "moneyline" in entry["words"] and "not forecast" in entry["words"]
    audit.check_the_strip_shows_a_dead_job({"freshness": block})
    # A strip that drops the line is refused by name.
    block["entries"] = [e for e in block["entries"] if e["job"] != "untrained"]
    faults = audit.freshness_faults({"freshness": block})
    assert any("moneyline is not forecast, for want of a model" in f
               for f in faults), faults


def test_a_sport_never_forecast_is_not_listed(league):
    """Never having written is not having stopped: a sport with no forecast
    at all has nothing on the strip, whatever it has not trained."""
    store.sync_registry(league)
    block = views.freshness(league)
    assert block["untrained"] == []
    assert [e["job"] for e in block["entries"]] == [
        "daily_run", "venue_read", "reasoning"]


def test_a_sport_whose_first_run_failed_by_name_is_listed(league, monkeypatch):
    """...BUT A RUN THAT FAILED FOR WANT OF A MODEL HAS STOPPED (found by the
    prover of item 2, 2026-09-26). A sport whose first run meets no model
    writes nothing, so it never holds a forecast; the strip that waited for
    one said nothing while the run failed by name on the Health panel."""
    seasons = dict(config.SPORT_CURRENT_SEASON)
    seasons["nfl"] = 2025
    monkeypatch.setattr(config, "SPORT_CURRENT_SEASON", seasons)
    # The failure is the point; a notice on the desktop is not.
    monkeypatch.setenv("GRIDIRON_NOTIFY_FAILURES", "0")
    store.sync_registry(league)
    assert not tasks.failed_for_want_of_a_model(league, "nfl")
    result = tasks.run_task(league, "predict:nfl", use_llm=False)
    assert result["result"] == "failed" and "point spread" in result["detail"]
    assert _written(league) == {}
    assert tasks.failed_for_want_of_a_model(league, "nfl")
    assert not tasks.failed_for_want_of_a_model(league, "mlb")
    block = views.freshness(league)
    entry = next(e for e in block["entries"] if e["job"] == "untrained")
    assert entry["stale"] and entry["sport"] == "nfl"
    assert entry["words"].startswith("NFL point spread, moneyline")
    audit.check_the_strip_shows_a_dead_job({"freshness": block})
    # ONCE IT HAS A MODEL THE LINE GOES, failure or no: the door decides.
    for market in config.active_markets("nfl"):
        kind = (f"prop:{market}" if market in config.SPORT_PROP_MARKETS["nfl"]
                else market)
        baseline.train(league, kind, (2025,), l2=1.0, note="test", min_rows=20)
    activation.activate_in_a_scratch_world(league)
    assert views.freshness(league)["untrained"] == []


@pytest.mark.parametrize("why", baseline.UNTRAINED_WHY)
def test_the_words_are_plain(why):
    for markets in ([{"market": "moneyline", "why": why}],
                    [{"market": "spread", "why": why},
                     {"market": "passing_yards", "why": why}]):
        for words in (language.untrained_line_words("cfb", markets),
                      language.untrained_run_words("cfb", markets, 3)):
            assert words.startswith("NCAAF ")
            assert audit.plain_words_violations(words) == [], words
            assert audit.advice_word_faults(words) == [], words
            assert audit.pressure_word_faults(words) == [], words
            assert "not forecast" in words
    assert set(language.UNTRAINED_WHY_WORDS) == set(baseline.UNTRAINED_WHY)
