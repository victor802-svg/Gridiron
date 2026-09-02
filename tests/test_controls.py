"""Tab records, the tier filter and the slate clock (E2).

Each of these puts a NUMBER in front of a reader, so each carries the two
things this project's laws demand of a number: which sport it belongs to
(LAW 6) and what it is out of (LAW 4).
"""

from __future__ import annotations

import pytest

from gridiron import config, language, views


def test_a_tab_record_names_one_sport_and_never_a_total(conn):
    """LAW 6 in the navigation.

    The tabs are the one place a combined figure would be most tempting and
    most wrong: a number mixing NFL spreads with MLB moneylines describes
    neither, and it flatters, because the easy sport dilutes the hard one.
    """
    summary = views.sports_summary(conn)
    assert "total" not in summary
    for sport in summary["sports"]:
        assert sport["label"] in sport["record_line"]
        assert sport["settled"] <= sport["written"]
    # And no key anywhere in the payload sums two sports.
    labels = {s["label"] for s in summary["sports"]}
    for sport in summary["sports"]:
        others = labels - {sport["label"]}
        for other in others:
            assert other not in sport["record_line"]


def test_a_sport_with_nothing_settled_says_so_rather_than_showing_a_record():
    """"0 settled", not "0-0" -- an absence, not a record of no wins (LAW 4)."""
    assert language.sport_record_line("NCAAF", 0, 0, 0) == "NCAAF 0 settled"
    assert language.sport_record_line("MLB", 33, 18, 51) == "MLB 33-18"


def test_the_hover_explains_the_gap_between_written_and_settled():
    """Voids are the difference nothing else on the tab accounts for."""
    detail = language.sport_record_detail("MLB", 33, 18, 51, 82, 10)
    assert "51 settled of 82 written" in detail
    assert "10 void" in detail
    # No voids, no clause about them.
    assert "void" not in language.sport_record_detail("NFL", 0, 0, 0, 104, 0)


def test_a_filtered_count_always_carries_its_denominator():
    """Four picks reads as a thin slate unless the whole is beside it."""
    assert language.tier_filter_line("STRONG", 4, 177) == "STRONG · 4 of 177 picks"
    assert language.tier_filter_line(None, 177, 177) == "177 picks"
    assert language.tier_filter_line(None, 1, 1) == "1 pick"


def test_every_filter_combination_has_a_line_written_for_it(conn):
    """The renderer looks one up; it never composes one."""
    for sport in config.SPORTS:
        glance = views.week(conn, sport)["glance"]
        lines = glance["count_lines"]
        assert "|" in lines, "the unfiltered line is missing"
        for key, line in lines.items():
            assert line, f"{sport}: {key!r} has no line"
            market, _, tier = key.partition("|")
            if tier:
                assert tier in line and " of " in line


def test_the_slate_states_are_the_three_that_exist(conn):
    for sport in config.SPORTS:
        glance = views.week(conn, sport)["glance"]
        assert glance["state"] in ("upcoming", "live", "complete")
        # An upcoming slate has no state line -- that one is a countdown, and
        # a countdown cannot be written once on the server.
        if glance["state"] == "upcoming":
            assert glance["state_line"] is None
        else:
            assert " of " in glance["state_line"]


def test_the_state_line_says_how_many_of_how_many():
    assert language.slate_state_line("live", 12, 60) == "in progress · 12 of 60 final"
    assert language.slate_state_line("complete", 60, 60) == "complete · 60 of 60 final"
    assert language.slate_state_line("upcoming", 0, 60) is None


def test_a_finished_slate_is_not_reported_as_upcoming(conn):
    """The field-name bug this caught, asserted so it cannot come back.

    `_glance` read `status` where the card calls it `game_status`, so every
    card looked unstarted: a completed slate would have counted as upcoming
    and the page would have counted down to a kickoff that had already
    happened.
    """
    for sport in config.SPORTS:
        data = views.week(conn, sport)
        cards = data["cards"]
        if not cards:
            continue
        finals = {c["game_id"] for c in cards if c.get("game_status") == "final"}
        games = {c["game_id"] for c in cards}
        assert data["glance"]["final"] == len(finals)
        if finals and len(finals) == len(games):
            assert data["glance"]["state"] == "complete"


def test_the_glance_panel_states_facts_and_does_not_narrate_itself(conn):
    """The caveats still exist -- they moved to the heading, not away."""
    for sport in config.SPORTS:
        glance = views.week(conn, sport)["glance"]
        assert "LAW 1" in glance["notes"]
        assert "league's clock" in glance["notes"]
