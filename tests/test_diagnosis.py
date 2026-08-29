"""D1: the diagnosis is read-only, pre-registered, and its arithmetic is right.

A verdict is only as good as the statistic under it, and these are hand-rolled,
so they are checked against values that can be derived independently.
"""

from __future__ import annotations

import importlib.util
import sqlite3
import sys
from pathlib import Path

import pytest

from gridiron import config

REPO = config.REPO_ROOT


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "gridiron_diagnose", REPO / "tools" / "diagnose.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["gridiron_diagnose"] = module
    spec.loader.exec_module(module)
    return module


diagnose = _load_module()


# --- the statistics --------------------------------------------------------

def test_wilson_matches_a_known_interval():
    # 50/100 -> the textbook Wilson interval is about 40.4% to 59.6%.
    lo, hi = diagnose.wilson(50, 100)
    assert lo == pytest.approx(0.4038, abs=0.001)
    assert hi == pytest.approx(0.5962, abs=0.001)


def test_wilson_is_asymmetric_near_the_boundary():
    """The reason to use Wilson at all: it does not run off the end."""
    lo, hi = diagnose.wilson(0, 10)
    assert lo == 0.0
    assert 0.0 < hi < 0.35
    lo, hi = diagnose.wilson(10, 10)
    assert hi == 1.0
    assert 0.65 < lo < 1.0


def test_wilson_widens_as_the_sample_shrinks():
    wide = diagnose.wilson(15, 30)
    narrow = diagnose.wilson(150, 300)
    assert (wide[1] - wide[0]) > (narrow[1] - narrow[0]) * 2.5


def test_binomial_test_on_a_perfectly_typical_result_is_one():
    assert diagnose.binomial_p_two_sided(50, 100, 0.5) == pytest.approx(1.0)


def test_binomial_test_on_an_extreme_result_is_tiny():
    assert diagnose.binomial_p_two_sided(90, 100, 0.5) < 1e-15


def test_binomial_test_is_two_sided():
    low = diagnose.binomial_p_two_sided(30, 100, 0.5)
    high = diagnose.binomial_p_two_sided(70, 100, 0.5)
    assert low == pytest.approx(high, rel=1e-9), "both tails must be counted"


def test_binomial_test_against_a_non_half_baseline():
    # 30 successes in 100 against a 30% baseline is exactly typical.
    assert diagnose.binomial_p_two_sided(30, 100, 0.30) == pytest.approx(1.0)
    assert diagnose.binomial_p_two_sided(60, 100, 0.30) < 1e-8


def test_welch_t_is_zero_for_identical_samples():
    a = [1.0, 2.0, 3.0, 4.0]
    assert diagnose.welch_t(a, list(a)) == pytest.approx(0.0)


def test_welch_t_is_none_when_a_sample_is_too_small():
    assert diagnose.welch_t([1.0], [1.0, 2.0, 3.0]) is None


# --- pre-registration is real ---------------------------------------------

def test_all_four_briefed_hypotheses_are_declared():
    ids = {h.id for h in diagnose.HYPOTHESES}
    assert {"H1a", "H1b", "H2", "H3", "H4"} == ids
    for h in diagnose.HYPOTHESES:
        assert h.claim.strip() and h.test.strip()


def test_the_comparison_budget_counts_every_declared_slice():
    declared = sum(len(v) for v in diagnose.SLICE_GROUPS.values())
    declared += len(diagnose.MISSINGNESS_SLICES)
    assert diagnose.comparison_budget() == declared
    assert declared > 20, "the budget should reflect how many angles were tried"


def test_the_threshold_is_adjusted_for_the_budget():
    adjusted = diagnose.ALPHA / diagnose.comparison_budget()
    assert adjusted < diagnose.ALPHA / 20
    assert adjusted == pytest.approx(0.05 / 29, rel=1e-6)


def test_every_declared_slice_key_is_implemented():
    """A slice named in the pre-registration but not implemented would silently
    shrink the budget and inflate the threshold."""
    item = diagnose.Disagreement(
        prediction_id=1, game_id="2025_05_KC_BUF", season=2025, week=5,
        predictor="statistical", model_prob=0.62, model_side="cover",
        line_asked=-3.5, market_line=2.5, implied_prob=0.5, outcome=1,
        div_game=0, srs_basis="season", missing=[], contributions={},
        injury_report_present=True,
    )
    keys = [k for entries in diagnose.SLICE_GROUPS.values() for _, k in entries]
    keys += [k for _, k in diagnose.MISSINGNESS_SLICES]
    for key in keys:
        assert isinstance(item.in_slice(key), bool), key


def test_an_undeclared_slice_is_refused():
    item = diagnose.Disagreement(
        prediction_id=1, game_id="2025_05_KC_BUF", season=2025, week=5,
        predictor="statistical", model_prob=0.62, model_side="cover",
        line_asked=-3.5, market_line=2.5, implied_prob=0.5, outcome=1,
        div_game=0, srs_basis="season", missing=[], contributions={},
        injury_report_present=True,
    )
    with pytest.raises(KeyError):
        item.in_slice("whatever_looks_good")


# --- small slices are never findings ---------------------------------------

def _fake(n: int, wins: int, week: int = 5) -> list:
    out = []
    for i in range(n):
        out.append(
            diagnose.Disagreement(
                prediction_id=i, game_id="2025_05_KC_BUF", season=2025, week=week,
                predictor="statistical", model_prob=0.62, model_side="cover",
                line_asked=-3.5, market_line=2.5, implied_prob=0.5,
                outcome=1 if i < wins else 0, div_game=1, srs_basis="season",
                missing=[], contributions={}, injury_report_present=True,
            )
        )
    return out


def test_a_slice_below_thirty_is_insufficient_however_extreme():
    """29 out of 29 is as extreme as a result gets. It is still insufficient."""
    result = diagnose.evaluate_slice(_fake(29, 29), "divisional", "divisional", 0.5)
    assert result.n == 29
    assert result.sufficient is False
    assert result.rate is None and result.p_value is None


def test_a_slice_at_thirty_is_evaluated():
    result = diagnose.evaluate_slice(_fake(30, 30), "divisional", "divisional", 0.5)
    assert result.sufficient is True
    assert result.rate == 1.0
    assert result.p_value < 1e-8


def test_h2_reports_not_supported_when_nothing_clears_the_bar():
    items = _fake(200, 111)          # ~55.5%, no structure
    finding, grouped = diagnose.run_h2(items, 0.5556, 0.05 / 29)
    assert finding.verdict in ("NOT SUPPORTED", "INSUFFICIENT SAMPLE")
    assert grouped, "the slice tables must still be produced for the report"


def test_h4_is_insufficient_when_one_forecaster_has_no_record():
    """The LLM path contributed nothing to the backtest; that is untested, not
    refuted, and the verdict must say so."""
    finding, rows = diagnose.run_h4(_fake(200, 111), 0.5556)
    assert finding.verdict == "INSUFFICIENT SAMPLE"
    assert any(r.label == "llm" and r.n == 0 for r in rows)


# --- the phase is read-only ------------------------------------------------

def test_the_diagnosis_opens_the_database_read_only(tmp_path, monkeypatch):
    from gridiron import db

    path = tmp_path / "d.db"
    conn = db.open_db(path)
    conn.close()

    opened = db.open_db(path)
    opened.execute("PRAGMA query_only = ON")
    with pytest.raises(sqlite3.OperationalError):
        opened.execute(
            "INSERT INTO factors (name, added_utc, rationale) VALUES"
            " ('x', '2026-01-01T00:00:00Z', 'a rationale long enough to pass')"
        )
    opened.close()


def test_the_tool_declares_itself_read_only_in_its_own_source():
    source = (REPO / "tools" / "diagnose.py").read_text(encoding="utf-8")
    assert "PRAGMA query_only = ON" in source
    assert "READ-ONLY" in source


# --- the report ------------------------------------------------------------

@pytest.mark.slow
def test_the_committed_report_states_a_verdict_for_every_hypothesis():
    report = (REPO / "docs" / "DIAGNOSIS.md")
    if not report.exists():
        pytest.skip("docs/DIAGNOSIS.md has not been generated")
    text = report.read_text(encoding="utf-8")
    for h in diagnose.HYPOTHESES:
        assert f"| {h.id} |" in text, f"{h.id} has no verdict row"
    assert "Bonferroni" in text
    assert "pre-registered comparisons" in text
    # LAW 4 applies to a diagnosis as much as to a scorecard.
    assert "insufficient" in text.lower()
    assert "n=207" in text or "| 207 |" in text
