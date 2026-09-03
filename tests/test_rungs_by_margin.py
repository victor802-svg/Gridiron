"""The spread rung is chosen against the expected margin (ruling R4).

Measured before it was ruled on, and the measurement is the point: on the
college slate of 2026-09-05, 76% of all 177 picks claimed 70% or better, and
the spread confidence sat exactly where the rung was furthest from the answer
-- 77% of cross-division games claimed 90%+ against 20% of FBS-against-FBS
ones. It was never a scale bug; the probability path has no standard deviation
in it at all.
"""

from __future__ import annotations

import pytest

from gridiron import audit
from gridiron.model import questions


LADDER = questions.CFB_SPREAD_LADDER


def test_the_rung_is_the_nearest_one_to_a_coin_flip():
    """A side expected to win by fourteen is asked at -14.5, not at a hash."""
    assert questions.cfb_spread_rung("g1", 14.0) == -14.5
    assert questions.cfb_spread_rung("g1", 7.0) == -7.5
    assert questions.cfb_spread_rung("g1", 0.0) == -0.5
    assert questions.cfb_spread_rung("g1", -6.0) == 6.5


def test_the_same_margin_gives_the_same_rung_whatever_the_game_is():
    """The game id must not reach the choice once a margin exists.

    This is the whole of the change: the rung used to be a hash of the id, and
    a hash is indifferent to what the game actually is.
    """
    rungs = {questions.cfb_spread_rung(f"game-{i}", 21.0) for i in range(200)}
    assert rungs == {-24.5}, f"the id still moves the rung: {sorted(rungs)}"


def test_a_margin_exactly_between_two_rungs_resolves_the_same_way_every_time():
    """THE BOUNDARY, tested AT the boundary (MENTOR section 3).

    -14.5 and -7.5 are 7 apart, so a margin of 11.0 sits exactly between them.
    A tie broken by dictionary order or by whichever rung the iteration reached
    first would be stable today and move the day the ladder is reordered, and
    nobody would notice because both answers look reasonable.
    """
    midpoint = 11.0
    assert abs((-midpoint) - (-14.5)) == abs((-midpoint) - (-7.5)), (
        "this test no longer sits on the boundary it claims to")
    first = questions.cfb_spread_rung("a", midpoint)
    assert first == -14.5, "the tie must break toward the lower rung, declared"
    assert all(questions.cfb_spread_rung(f"g{i}", midpoint) == first
               for i in range(50)), "the tie break is not stable"
    # And the same again with the ladder handed over in the other order.
    assert first == min(sorted(LADDER, reverse=True),
                        key=lambda r: (abs(r + midpoint), r))


def test_an_absent_rating_falls_back_to_the_rotation_and_says_so():
    """A team new to the record has no rating, and that is an absence.

    Absent is never a guessed margin -- the explicit-absent rule -- so the
    fallback is the old rotation rather than a zero, which would silently mean
    'evenly matched'.
    """
    assert questions.cfb_expected_margin(None, 3.0) is None
    assert questions.cfb_expected_margin(3.0, None) is None
    rung = questions.cfb_spread_rung("some-game", None)
    assert rung in LADDER


def test_the_expected_margin_carries_the_home_field():
    """Two evenly rated sides are not a coin flip; the home one is favoured.

    THE CONSTANTS BECAME MEASURED ON 2026-09-03 and the property did not
    change. This asserted `== CFB_HOME_MARGIN` and a slope of exactly 1.0 --
    both of which were assumptions the data did not support. What the test is
    actually about is that home advantage is carried and that a rating edge
    moves the expectation in the right direction, and it says that now.
    """
    intercept, slope = questions.EXPECTED_MARGIN_FIT["cfb"]

    level = questions.cfb_expected_margin(0.0, 0.0)
    assert level == pytest.approx(intercept)
    assert level > 0, "the home side is not favoured between equal teams"

    better = questions.cfb_expected_margin(10.0, 3.0)
    assert better == pytest.approx(intercept + slope * 7.0)
    assert better > level, "a seven-point rating edge did not raise the margin"

    # A RATING EDGE DOES NOT BUY ITS OWN VALUE IN MARGIN, which is the thing
    # the old assumption got wrong: seven points of rating buys less than
    # seven points of expected margin.
    assert better - level < 7.0


def test_the_guard_catches_a_rotation_on_the_live_path():
    assert audit.rung_selection_faults(audit.RUNG_FIXTURE_POSITIVE)
    assert not audit.rung_selection_faults(audit.RUNG_FIXTURE_NEGATIVE)


def test_the_shipped_selector_is_clean():
    audit.check_the_rung_is_chosen_by_margin()
