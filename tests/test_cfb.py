"""College football's declared spread ladder.

The ladder is the instrument that decides what question each game is asked,
so a ladder that bunches is a record that measures the schedule rather than
the model. Extended by operator ruling on 2026-09-02 after the top rung was
found taking 27% of games -- and 45 of the 58 rated games on 2026-09-05.
"""

from __future__ import annotations

import pytest




# ---------------------------------------------------------------------------
# THE LADDER EXTENSION (ruling CFB-1, 2026-09-02)
# ---------------------------------------------------------------------------

def test_the_ladder_was_extended_and_nothing_moved():
    """An EXTENSION, not a re-spacing. Predictions already asked at the old
    rungs stand (LAW 3), so the numbers they were asked at stay on the
    ladder."""
    from gridiron.model import questions

    old = (-24.5, -14.5, -7.5, -0.5, 6.5)
    for rung in old:
        assert rung in questions.CFB_SPREAD_LADDER, f"{rung} was retired"
    assert questions.CFB_SPREAD_LADDER == (
        -41.5, -31.5, -24.5, -14.5, -7.5, -0.5, 6.5)
    assert questions.CFB_SPREAD_LADDER_EXTENDED.startswith("2026-09-02")
    # The original declaration date is kept: the ladder was extended, not
    # re-declared, and backdating a factor or a ladder is what the registry
    # guard refuses elsewhere.
    assert questions.CFB_SPREAD_LADDER_DECLARED.startswith("2026-08-31")


def test_a_mismatch_beyond_the_ladder_fails_loudly():
    """Clamping would store a confident claim about a number nobody chose, on
    exactly the games where the model is least tested."""
    from gridiron.model import questions

    with pytest.raises(questions.RungOffTheLadder, match="never stretched"):
        questions.cfb_spread_rung("g", 60.0)
    with pytest.raises(questions.RungOffTheLadder):
        questions.cfb_spread_rung("g", -40.0)


def test_a_mismatch_inside_the_ladder_is_still_asked():
    """The refusal must not swallow ordinary games."""
    from gridiron.model import questions

    for margin in (-3.0, 0.0, 7.0, 14.0, 24.0, 31.0, 41.0, 45.0):
        rung = questions.cfb_spread_rung("g", margin)
        assert rung in questions.CFB_SPREAD_LADDER


def test_the_top_rung_is_reached_by_under_a_tenth_of_games():
    """The ruling's own test, on the population it was measured over."""
    import collections

    from gridiron import db
    from gridiron.model import questions
    from gridiron.sports import cfb as cfb_sport

    conn = db.connect()
    rows = conn.execute(
        "SELECT id FROM games WHERE sport='cfb' AND status='final'"
        " AND home_score IS NOT NULL AND season IN (2024, 2025)").fetchall()
    if len(rows) < 500:
        pytest.skip("this database has too little college history to measure")
    counts, asked = collections.Counter(), 0
    for r in rows:
        try:
            ctx = cfb_sport.build_context(conn, r["id"])
        except Exception:
            continue
        margin = questions.cfb_expected_margin(ctx.home_rating, ctx.away_rating)
        if margin is None:
            continue
        asked += 1
        try:
            counts[questions.cfb_spread_rung(r["id"], margin)] += 1
        except questions.RungOffTheLadder:
            pass
    top = min(questions.CFB_SPREAD_LADDER)
    share = counts[top] / asked
    assert share < 0.10, f"the top rung takes {share:.1%} of games"
