"""The desk layout: what must be true at 1280px and above, and below it.

The frame is the only thing that scrolls, a tile never truncates, and
selecting a pick does not move the reader's place. Each of those is a claim
the eye cannot check reliably on a 177-pick slate, so each is asserted.
"""

from __future__ import annotations

import pytest

DESK = {"width": 1400, "height": 900}
ROWS = {"width": 1100, "height": 900}


def _open_week(page, size):
    page.set_viewport_size(size)
    page.evaluate("location.hash = '#/week'")
    page.wait_for_timeout(900)


def test_the_desk_appears_only_at_the_declared_breakpoint(page):
    """1280px, and the same number in the CSS, the JS and the mockup.

    Below it the compact rows render exactly as they did before the desk
    existed -- which is the whole of D4's promise, asserted here rather than
    left to a screenshot.
    """
    _open_week(page, DESK)
    assert page.evaluate("document.body.classList.contains('desk-on')")
    assert page.query_selector_all("#week-frame .tile"), "no tiles on the desk"
    assert not page.query_selector_all("#week-cards .row"), (
        "compact rows rendered alongside the desk; the two layouts are "
        "different DOM and must not both exist"
    )

    _open_week(page, ROWS)
    assert not page.evaluate("document.body.classList.contains('desk-on')")
    assert not page.query_selector_all("#week-frame .tile"), (
        "tiles rendered below the breakpoint"
    )


def test_the_page_does_not_scroll_but_the_frame_does(page):
    """The controls stay put while the slate moves under them.

    `overflow: hidden` on body alone was not enough -- the viewport scroll
    belongs to the root element, and the document still moved 414px. Both are
    pinned now, and this is what proves it.
    """
    _open_week(page, DESK)
    moved = page.evaluate("""() => {
        window.scrollTo(0, 600);
        const y = window.scrollY;
        const f = document.getElementById('week-frame');
        f.scrollTop = 100000;          // past the end; the browser clamps
        return {page: y, frame: f.scrollTop, frame_can: f.scrollHeight > f.clientHeight};
    }""")
    assert moved["page"] == 0, f"the page scrolled {moved['page']}px; only the frame may"
    assert moved["frame_can"], "the frame does not scroll, so nothing does"
    # SCROLLED PAST THE END ON PURPOSE. Asserting an exact scrollTop meant
    # asserting the fixture's slate is a particular length: the synthetic
    # league has far fewer picks than the live record, so 300 clamped to 98 and
    # the test failed on the size of its own fixture rather than on the page.
    assert moved["frame"] > 0, "the frame refused to scroll at all"


def test_the_hidden_scrollbar_does_not_break_scrolling(page):
    """A scrollbar hidden in CSS must still scroll by wheel.

    Hiding the bar is a look; breaking the wheel is a broken page, and the two
    are one property apart.
    """
    _open_week(page, DESK)
    page.mouse.move(400, 500)
    page.mouse.wheel(0, 600)
    page.wait_for_timeout(200)
    assert page.evaluate("document.getElementById('week-frame').scrollTop") > 0, (
        "the wheel did not scroll the frame"
    )


def test_no_tile_truncates(page):
    """No ellipsis anywhere in the frame.

    A truncated tile has told the reader there is something it is not showing
    and then not shown it. The tile grows instead.
    """
    _open_week(page, DESK)
    bad = page.evaluate("""() => [...document.querySelectorAll('#week-frame *')]
        .filter(e => getComputedStyle(e).textOverflow === 'ellipsis')
        .map(e => e.className || e.tagName)""")
    assert not bad, f"these elements in the frame truncate: {bad[:6]}"


def test_selecting_a_tile_does_not_move_the_frame(page):
    """Looking at a pick must not cost the reader their place."""
    _open_week(page, DESK)
    result = page.evaluate("""() => {
        const f = document.getElementById('week-frame');
        f.scrollTop = 420;
        const before = f.scrollTop;
        const tiles = [...document.querySelectorAll('#week-frame .tile')];
        const wasSelected = document.querySelector('.tile[aria-selected="true"]');
        tiles[Math.min(10, tiles.length - 1)].click();
        return {before, after: f.scrollTop,
                changed: document.querySelector('.tile[aria-selected="true"]') !== wasSelected};
    }""")
    assert result["after"] == result["before"], (
        f"selecting moved the frame from {result['before']} to {result['after']}"
    )
    assert result["changed"], "clicking a tile did not select it"


def test_one_tile_is_selected_on_arrival(page):
    """The rail is always populated, so something is always selected."""
    _open_week(page, DESK)
    assert page.query_selector('.tile[aria-selected="true"]'), (
        "no tile is selected, so the rail would open empty"
    )


def test_the_rank_is_the_position_in_the_current_sort(page):
    """A rank that survived a re-sort is another ordering's opinion."""
    _open_week(page, DESK)
    first = page.evaluate(
        "document.querySelector('#week-frame .tile .tile-rank').textContent")
    assert first == "1"
    ranks = page.evaluate("""() => [...document.querySelectorAll('#week-frame .tile-rank')]
        .slice(0, 5).map(e => e.textContent)""")
    assert ranks == ["1", "2", "3", "4", "5"], f"ranks are not sequential: {ranks}"


def test_arrow_keys_move_through_the_tiles(page):
    """Three across, so down moves by three -- the distance the eye moves."""
    _open_week(page, DESK)
    moved = page.evaluate("""() => {
        const tiles = [...document.querySelectorAll('#week-frame .tile')];
        tiles[0].focus();
        const start = document.activeElement;
        return {focusable: start === tiles[0], count: tiles.length};
    }""")
    assert moved["focusable"], "a tile cannot take focus, so keys cannot reach it"
    page.keyboard.press("ArrowRight")
    page.wait_for_timeout(80)
    after = page.evaluate("""() => {
        const tiles = [...document.querySelectorAll('#week-frame .tile')];
        return tiles.indexOf(document.activeElement);
    }""")
    assert after == 1, f"ArrowRight moved focus to index {after}, expected 1"
    page.keyboard.press("ArrowDown")
    page.wait_for_timeout(80)
    after_down = page.evaluate("""() => {
        const tiles = [...document.querySelectorAll('#week-frame .tile')];
        return tiles.indexOf(document.activeElement);
    }""")
    assert after_down == 4, f"ArrowDown moved to {after_down}, expected 4 (one row of three)"
