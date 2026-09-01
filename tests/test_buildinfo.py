"""A build says what it is, and whether it is still the current one.

WHY THIS EXISTS: on 2026-09-01 the desktop bundle was three days old and
showing a live record through an interface that predated college football, the
desk and the rail. Nothing was broken. The record kept filling, the window kept
opening, and the screen was a photograph -- which is the most convincing kind
of wrong, because every check a person makes comes back fine.
"""

from __future__ import annotations

import json

import pytest

from gridiron import buildinfo, config, language


def test_running_from_source_is_not_an_error(tmp_path):
    """The ordinary case for anyone working on the code."""
    fresh = buildinfo.freshness(root=tmp_path, use_cache=False)
    assert fresh["from_source"] is True
    assert language.build_line(fresh) == "running from source"


def test_a_current_build_says_what_it_is_and_stops_there(tmp_path):
    stamp = {"commit": "0e23769" + "0" * 33, "built_utc": "2026-09-01T12:00:00Z"}
    (tmp_path / buildinfo.STAMP_NAME).write_text(json.dumps(stamp), encoding="utf-8")
    said = language.build_line({
        "from_source": False, "commit": stamp["commit"],
        "built_utc": stamp["built_utc"], "behind": 0, "stale": False,
    })
    assert said == "built 1 Sep from 0e23769"
    assert "behind" not in said


def test_a_stale_build_says_how_far_behind_and_what_to_do():
    said = language.build_line({
        "from_source": False, "commit": "abc1234" + "0" * 33,
        "built_utc": "2026-08-29T19:54:00Z", "behind": 4, "stale": True,
    })
    assert "4 commits behind" in said
    assert "rebuild" in said


def test_one_commit_behind_is_singular():
    """A boundary, and the kind that reads as sloppiness when it is wrong."""
    said = language.build_line({
        "from_source": False, "commit": "abc1234" + "0" * 33,
        "built_utc": "2026-08-29T19:54:00Z", "behind": 1, "stale": True,
    })
    assert "1 commit behind" in said
    assert "1 commits" not in said


def test_could_not_check_is_not_reported_as_up_to_date():
    """The distinction the whole notice depends on.

    `behind: None` means the comparison could not be made; `behind: 0` means it
    was made and came back clean. Rendered the same, the first would look like
    a clean bill of health -- a build of unknown age wearing a green tick.
    """
    unknown = language.build_line({
        "from_source": False, "commit": "abc1234" + "0" * 33,
        "built_utc": "2026-08-29T19:54:00Z", "behind": None, "stale": False,
    })
    assert "could not check" in unknown
    current = language.build_line({
        "from_source": False, "commit": "abc1234" + "0" * 33,
        "built_utc": "2026-08-29T19:54:00Z", "behind": 0, "stale": False,
    })
    assert "could not check" not in current


def test_an_identical_commit_is_zero_behind_without_asking_git():
    assert buildinfo.commits_behind("deadbeef", "deadbeef") == 0


def test_a_corrupt_stamp_reads_as_source_rather_than_crashing(tmp_path):
    (tmp_path / buildinfo.STAMP_NAME).write_text("{not json", encoding="utf-8")
    assert buildinfo.stamp(tmp_path) is None
    (tmp_path / buildinfo.STAMP_NAME).write_text('{"built_utc": "x"}', encoding="utf-8")
    assert buildinfo.stamp(tmp_path) is None, "a stamp with no commit is not a stamp"


def test_the_spec_ships_every_declared_sport():
    """THE DEFECT THIS CATCHES SHIPPED FOR THREE DAYS in the spec.

    `hiddenimports` named nfl, mlb and nba, written before college football
    existed. PyInstaller cannot see a dynamically imported adapter, so a build
    would have started, served, and quietly forecast three of four sports.
    Deriving the list from config.SPORTS is the same fix the four
    three-sport tests got.
    """
    spec = (config.PACKAGE_ROOT.parent / "desktop" / "gridiron.spec").read_text(
        encoding="utf-8")
    assert "_SPORT_MODULES" in spec, "the spec no longer derives its sport list"
    for sport in config.SPORTS:
        assert f'"gridiron.sports.{sport}"' not in spec, (
            f"the spec hardcodes {sport}; the next sport added will be left out")


def test_the_footer_carries_the_build(conn):
    from gridiron import views
    payload = views.meta(conn, config.SPORTS[0])
    assert "build" in payload
    assert language.build_line(payload["build"]) in payload["colophon"]
