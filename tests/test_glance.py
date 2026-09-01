"""The at-a-glance panel: counted once, from the slate already in hand.

Every claim on that panel is a count with its denominator. The one thing it
must never do is pool a hit rate across markets to say how the model is doing
overall -- that is the merge LAW 4 forbids, and it flatters, because the easy
market dilutes the hard one.
"""

from __future__ import annotations

import pytest

from gridiron import config, language, views
from gridiron.data import reference


def test_a_kickoff_belongs_to_exactly_one_declared_window():
    """No hour falls through, and none falls into two."""
    for hour in range(24):
        hits = [name for first, last, name in language.KICKOFF_WINDOWS
                if first <= hour <= last]
        assert len(hits) == 1, f"hour {hour} matched {hits}"
        assert language.kickoff_window(hour) == hits[0]


def test_the_window_boundaries_are_tested_at_the_boundary():
    """MENTOR section 3: a rule with a numeric edge is tested AT the edge."""
    for first, last, name in language.KICKOFF_WINDOWS:
        assert language.kickoff_window(first) == name, f"{name} rejects its first hour"
        assert language.kickoff_window(last) == name, f"{name} rejects its last hour"
    # And the hour after the last window is nobody's.
    highest = max(last for _, last, _ in language.KICKOFF_WINDOWS)
    assert language.kickoff_window(highest + 1) is None


def test_an_unknown_kickoff_belongs_to_no_window():
    """Absent is absent: a game with no time is counted separately, not early."""
    assert reference.eastern_hour(None) is None
    assert reference.eastern_hour("not a time") is None
    assert language.kickoff_window(None) is None


def test_the_league_clock_is_not_the_readers():
    """A 7pm Eastern kickoff is 23:00 or 00:00 UTC and still a night game."""
    assert reference.eastern_hour("2026-09-05T23:00:00Z") == 19
    assert language.kickoff_window(reference.eastern_hour("2026-09-05T23:00:00Z")) == "night"
    # The same instant, in high summer and in December, differs by the hour
    # the DST rule adds -- which is the reason this is not a fixed offset.
    assert reference.eastern_hour("2026-01-05T23:00:00Z") == 18


def test_the_tier_line_is_a_count_and_never_a_rate():
    """The one rate-shaped claim on the panel, kept a count."""
    unproven = language.tier_status_line("NCAAF", 0, 12, 3, 20)
    assert "3 of 20 settled" in unproven
    assert "%" not in unproven, f"a rate reached the tier line: {unproven!r}"
    proven = language.tier_status_line("NFL", 5, 12, 480, 20)
    assert proven == "5 of 12 NFL tiers proven"
    assert "%" not in proven


def test_coverage_says_priced_of_asked_in_that_order():
    """Ruling R-A: coverage is REPORTED. The denominator is what was asked.

    Printed the other way round -- asked of priced -- the line would read as
    though the market decided which questions got formed, which is the exact
    thing LAW 1 stops from happening.
    """
    line = language.coverage_line("spread", 44, 60)
    assert line == "spread · 44 of 60 priced"


def test_the_sharpest_line_says_apart_not_edge():
    """The gap is a distance between two opinions, not a claim to be right."""
    line = language.sharpest_line(0.19, "Vanderbilt, the under")
    # PERCENTAGE points, said in full. On a page whose picks are measured in
    # football points, "+19 points apart" is two units one word apart.
    assert line.startswith("+19 percentage points apart")
    assert "edge" not in line
    assert language.sharpest_line(None, None) == "no market comparison on this slate"


def test_a_slate_with_no_lines_still_produces_a_glance(conn):
    """A summary that vanishes when the market is quiet is a summary that
    only works on the days a reader least needs it."""
    for sport in config.SPORTS:
        data = views.week(conn, sport)
        glance = data["glance"]
        assert glance["games"] <= glance["picks"] or glance["picks"] == 0, (
            f"{sport}: more games than picks, so games are being counted per pick")
        for row in glance["coverage"]:
            assert row["priced"] <= row["asked"], (
                f"{sport}: {row['market']} priced {row['priced']} of {row['asked']}")
        assert glance["tiers"]["needed"] > 0
        assert glance["sharpest"]["line"]


def test_the_glance_names_its_scope_where_the_greeting_would_collide():
    """Two panels, one screen, and they must not both say the same words.

    The greeting reports the sharpest disagreement among predictions that
    arrived since the reader last looked; the glance reports it across the
    whole slate. Different sets, different numbers, and in the render they sat
    eight inches apart both labelled "sharpest disagreement".
    """
    assert language.glance_label("sharpest") == "sharpest on this slate"
    assert "this slate" in language.GLANCE_LABELS["sharpest"]


def test_every_glance_label_is_written_on_the_server(conn):
    """The ruling of 2026-08-31: no visible phrase is composed in the browser."""
    for sport in config.SPORTS:
        labels = views.week(conn, sport)["glance"]["labels"]
        assert set(labels) == {"sharpest", "tiers"}
        for key, text in labels.items():
            assert text and not text.startswith(key.upper())
            assert "_" not in text, f"{sport}: an identifier reached a label: {text!r}"
