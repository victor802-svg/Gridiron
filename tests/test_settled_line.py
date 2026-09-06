"""A finished slate says how many picks have settled off the page (UI audit
finding 9, 2026-09-05). "53 picks" stood over a page of 40 because settled
picks leave the grid once a slate is not live and nothing said so."""
from __future__ import annotations

from gridiron import language, views

WIDE = {"width": 1440, "height": 900}


def _resolved_slate(conn):
    row = conn.execute(
        "SELECT p.sport, g.season, g.week FROM predictions p JOIN games g ON g.id = p.game_id"
        " WHERE p.resolved_utc IS NOT NULL GROUP BY p.sport, g.season, g.week"
        " ORDER BY COUNT(*) DESC LIMIT 1").fetchone()
    return row["sport"], row["season"], row["week"]


def test_the_glance_carries_a_settled_line_for_every_filter_that_has_any(world_copy):
    sport, season, week = _resolved_slate(world_copy)
    data = views.week(world_copy, sport, season=season, wk=week)
    settled = [c for c in data["cards"] if c["resolved_utc"] is not None or c.get("voided")]
    assert settled, "the chosen slate has nothing settled"
    lines = data["glance"]["settled_lines"]
    assert lines["|"] == language.settled_count_line(len(settled))
    for key, line in lines.items():
        assert line.endswith(" settled"), (key, line)
        market, _, tier = key.partition("|")
        n = len([c for c in settled
                 if (not market or c["market"] == market)
                 and (not tier or (c.get("tier") or {}).get("tier") == tier)])
        assert line == language.settled_count_line(n), (key, line, n)
    # the keys are the count lines' keys, so the renderer looks one up beside the other
    assert set(lines) <= set(data["glance"]["count_lines"])


def test_an_open_slate_has_no_settled_line(world_copy):
    sport = world_copy.execute("SELECT sport FROM predictions WHERE resolved_utc IS NULL LIMIT 1").fetchone()[0]
    data = views.week(world_copy, sport)
    if any(c["resolved_utc"] is not None for c in data["cards"]):
        return
    assert data["glance"]["settled_lines"] == {}


def test_the_counts_line_names_the_settled_picks(page):
    page.set_viewport_size(WIDE)
    page.evaluate("location.hash = '#/week'")
    page.wait_for_selector("#week-cards .card", timeout=15000)
    page.evaluate("document.querySelector('.week-more').open = true")
    options = page.evaluate("[...document.querySelectorAll('#week-picker option')].map(o => o.value)")
    assert len(options) >= 2, options
    resolved = options[-1]
    with page.expect_response(lambda r: "/api/week" in r.url, timeout=20000):
        page.select_option("#week-picker", resolved)
    page.wait_for_timeout(600)
    counts = page.text_content("#week-counts")
    assert " settled" in counts, f"the counts line on a finished slate reads {counts!r}"
    with page.expect_response(lambda r: "/api/week" in r.url, timeout=20000):
        page.select_option("#week-picker", options[0])
    page.wait_for_timeout(300)
    page.evaluate("document.querySelector('.week-more').open = false")
