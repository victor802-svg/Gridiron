"""Session E: the walk-forward said no, and this keeps that answer binding.

WHAT WAS TESTED. `docs/DISTRIBUTIONAL.md` proposed replacing the rung with a
forecast distribution: write the mean and spread blind, then read P(over the
market's line) off it. The structural argument was strong -- a rung asked at
our own expectation confines P(over) to 45.8%-54.2%, while a read-out spans
3.4%-93.8%.

WHAT THE WALK-FORWARD FOUND. On 3,947 out-of-sample games across four arms,
the read-out was worse calibrated EVERY TIME, by 6 to 13 percentage points,
with a negative edge over always-the-base-rate in all four. The distributions
themselves were honest -- every PIT came back flat -- and that is the finding:
a distribution can be perfectly honest about its own error and still produce
badly calibrated probabilities at somebody else's number, because that number
is not a random point. It is a better forecast.

SO NOTHING SHIPPED, and these tests exist to keep it that way until a
walk-forward says otherwise.
"""

from __future__ import annotations

import pytest

from gridiron import audit, config
from gridiron.model import questions


# --- the verdicts ------------------------------------------------------------

def test_nothing_ships_and_the_record_says_why():
    """The result of Session E Part 2, asserted rather than remembered."""
    assert config.DISTRIBUTIONAL_MARKETS == frozenset(), (
        "a market is running distributionally; the walk-forward refused all "
        "four arms on 2026-09-04")
    for (sport, market), entry in config.DISTRIBUTIONAL_VERDICTS.items():
        assert entry["verdict"] in ("SHIP", "DO NOT SHIP", "NOT RUN")
        assert entry["why"], f"{sport}:{market} has a verdict and no reason"


@pytest.mark.parametrize("sport,market", [
    ("nfl", "total"), ("nfl", "spread"), ("nba", "total"), ("nba", "spread"),
])
def test_every_arm_that_ran_carries_its_evidence(sport, market):
    """LAW 4's habit applied to a decision: no verdict without its numbers."""
    entry = config.distributional_verdict(sport, market)
    assert entry is not None
    assert entry["verdict"] == "DO NOT SHIP"
    assert entry["n"] >= config.MIN_SAMPLE_FOR_EDGE_CLAIM, (
        f"{sport}:{market} decided on {entry['n']} games, below the "
        f"{config.MIN_SAMPLE_FOR_EDGE_CLAIM} this project requires of a claim")
    # The read-out lost, and by how much is on the record.
    assert entry["readout_gap_pts"] > entry["rung_gap_pts"]
    assert entry["readout_edge"] < 0
    # And the distribution itself was honest, which is the interesting half.
    assert entry["pit_flat"] is True


def test_the_distributions_were_honest_and_that_is_the_finding():
    """Every arm's PIT was flat. The forecast spread is right for the mean.

    This is asserted on its own because it is the part a later reader will
    most easily get backwards: the redesign did not fail because the model
    lied about its own uncertainty. It failed at the step after.
    """
    ran = [e for e in config.DISTRIBUTIONAL_VERDICTS.values()
           if e["verdict"] == "DO NOT SHIP"]
    assert len(ran) == 4
    assert all(e["pit_flat"] is True for e in ran)
    assert all(e["market_closer_share_pct"] > 50 for e in ran), (
        "the market's number was closer more often than ours in every arm, "
        "which is why reading a probability off our distribution at their "
        "number produced confident wrong claims")


def test_cfb_was_refused_by_its_own_expectation_not_by_line_coverage():
    """The brief said "fit it first, then include CFB". The fit answered."""
    entry = config.distributional_verdict("cfb", "total")
    assert entry["verdict"] == "NOT RUN"
    assert "0.93%" in entry["why"] or "0.109" in entry["why"]


# --- the guard ---------------------------------------------------------------

def test_the_verdicts_and_the_markets_agree():
    audit.check_distributional_verdicts()


def test_the_guard_sees_a_market_shipped_without_a_verdict():
    original = config.DISTRIBUTIONAL_MARKETS
    try:
        config.DISTRIBUTIONAL_MARKETS = frozenset({("nfl", "total")})
        assert audit.distributional_verdict_faults()
    finally:
        config.DISTRIBUTIONAL_MARKETS = original
    assert audit.distributional_verdict_faults() == []


def test_the_guard_sees_a_ship_verdict_its_numbers_refuse():
    """A decision rule that can be edited after the numbers is not a rule."""
    key = ("nfl", "total")
    original = dict(config.DISTRIBUTIONAL_VERDICTS[key])
    try:
        config.DISTRIBUTIONAL_VERDICTS[key] = {**original, "verdict": "SHIP"}
        faults = audit.distributional_verdict_faults()
        assert any("WORSE calibrated" in f for f in faults), faults
    finally:
        config.DISTRIBUTIONAL_VERDICTS[key] = original


def test_the_guard_sees_a_ladder_deleted_under_a_market_still_on_rungs():
    """The likelier accident: a migration that half-lands."""
    saved = questions.NFL_TOTAL_LADDER
    try:
        questions.NFL_TOTAL_LADDER = None
        faults = audit.distributional_verdict_faults()
        assert any("is gone" in f for f in faults), faults
    finally:
        questions.NFL_TOTAL_LADDER = saved
    assert audit.distributional_verdict_faults() == []


def test_every_market_with_a_verdict_has_a_known_ladder():
    """A market the migration check cannot see is a market it does not check."""
    for key in config.DISTRIBUTIONAL_VERDICTS:
        assert key in audit.LADDERS_BY_MARKET, (
            f"{key} has a verdict and no entry in LADDERS_BY_MARKET")


# --- the measured spreads ----------------------------------------------------

def test_the_forecast_spread_is_declared_dated_and_refuses_a_guess():
    assert questions.FORECAST_SPREAD_DECLARED
    assert questions.forecast_spread("nfl", "total") == 14.28
    with pytest.raises(questions.UnmeasuredForecastSpread):
        questions.forecast_spread("mlb", "total")


def test_the_forecast_spread_is_not_the_market_residual():
    """The mistake this project has already made once, at 4.71 vs 4.534.

    `MARGIN_SD_BY_SPORT` holds SD(actual - THE MARKET'S line); `FORECAST_SPREAD`
    holds SD(actual - OUR expectation). The market forecasts better than we do,
    so ours must be the wider of the two -- and if they were ever equal it
    would mean somebody had copied one into the other.
    """
    from gridiron.market import lines

    for sport in ("nfl", "nba"):
        ours = questions.forecast_spread(sport, "spread")
        theirs = lines.margin_sd(sport)
        assert ours > theirs, (
            f"{sport}: our forecast spread {ours} is not wider than the "
            f"market's residual {theirs}, which would mean we forecast the "
            f"margin at least as well as the market does")


def test_every_measured_spread_carries_its_sample_size():
    assert set(questions.FORECAST_SPREAD) == set(questions.FORECAST_SPREAD_N)
    for key, n in questions.FORECAST_SPREAD_N.items():
        assert n >= config.MIN_SAMPLE_FOR_EDGE_CLAIM, key


def test_neither_mlb_nor_cfb_totals_got_a_gaussian():
    """Both were refused, for different measured reasons.

    MLB's total is right-skewed at +0.64 -- runs are counts and a symmetric
    distribution cannot hold that shape. CFB's expectation explains under 1%
    of the variance, so there is no forecast to put a distribution around.
    """
    assert ("mlb", "total") not in questions.FORECAST_SPREAD
    assert ("cfb", "total") not in questions.FORECAST_SPREAD


# --- the stale comment, and the arithmetic that found it ---------------------

def test_cfb_reads_the_fitted_margin_and_the_comment_now_says_so():
    """The comment claimed the opposite for three days.

    Caught by arithmetic rather than by reading: the CFB margin's measured
    bias is +0.05, and the pre-fit constants (intercept 9.79 against the
    fitted 4.85) would have produced a bias of roughly five points.
    """
    src = (config.PACKAGE_ROOT / "model" / "questions.py").read_text(
        encoding="utf-8")
    assert "CFB'S ENTRY IS RECORDED AND NOT YET USED" not in src
    assert "CFB'S ENTRY IS LIVE" in src

    intercept, slope = questions.EXPECTED_MARGIN_FIT["cfb"]
    assert questions.cfb_expected_margin(10.0, 0.0) == pytest.approx(
        intercept + slope * 10.0)
    assert intercept != questions.CFB_HOME_MARGIN_ASSUMED
