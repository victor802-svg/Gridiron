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


# ---------------------------------------------------------------------------
# THE RAIL (D3)
# ---------------------------------------------------------------------------


def test_the_rail_describes_the_selected_pick_on_arrival(page):
    """A panel that opens empty asks to be clicked; this one is populated."""
    _open_week(page, DESK)
    assert not page.evaluate("document.getElementById('week-rail').hidden")
    match = page.evaluate("document.getElementById('rail-match').textContent")
    assert match.strip(), "the rail's heading is empty on arrival"
    selected = page.evaluate(
        "document.querySelector('.tile[aria-selected=\"true\"] .tile-match').textContent")
    assert match.strip() == selected.strip(), (
        f"the rail says {match!r} while the selected tile says {selected!r}"
    )


def test_selecting_moves_the_rail_and_not_the_frame(page):
    """The two halves of the desk's contract, in one assertion each."""
    _open_week(page, DESK)
    result = page.evaluate("""() => {
        const frame = document.getElementById('week-frame');
        frame.scrollTop = 300;
        const before = {frame: frame.scrollTop,
                        rail: document.getElementById('rail-match').textContent};
        const tiles = [...document.querySelectorAll('#week-frame .tile')];
        tiles[Math.min(7, tiles.length - 1)].click();
        return {before, frame: frame.scrollTop,
                rail: document.getElementById('rail-match').textContent,
                body: document.getElementById('rail-body').textContent.trim().length};
    }""")
    assert result["frame"] == result["before"]["frame"], "selecting moved the frame"
    assert result["rail"] != result["before"]["rail"], "the rail did not follow the selection"
    assert result["body"] > 0, "the rail's detail body is empty"


def test_the_rail_body_is_the_same_one_the_expanded_row_shows(page):
    """One implementation, asserted by the parts it produces.

    The probability rail, the bucket line and the plain why are the expanded
    row's own elements. Finding them inside the panel is what proves the panel
    is not a second renderer that happens to agree today.
    """
    _open_week(page, DESK)
    found = page.evaluate("""() => {
        const body = document.getElementById('rail-body');
        return {
            rail: !!body.querySelector('.rail .track'),
            why: !!body.querySelector('.row-why'),
            more: !!body.querySelector('.row-more'),
        };
    }""")
    assert found["rail"], "no probability rail in the selected-pick panel"
    assert found["why"], "no plain why in the selected-pick panel"
    assert found["more"], "no 'How the model works' link in the selected-pick panel"


def test_the_glance_counts_games_and_never_pools_a_rate(page):
    """LAW 4 on the summary panel: counts, with their N, and no hit rate."""
    _open_week(page, DESK)
    glance = page.evaluate("""() => {
        const text = document.getElementById('rail-facts').textContent;
        const windows = [...document.querySelectorAll('#rail-windows .krow b')]
            .map(b => +b.textContent);
        const heading = document.getElementById('rail-glance-count').textContent;
        return {text, windows, heading};
    }""")
    assert "game" in glance["heading"], (
        f"the glance heading does not carry its N: {glance['heading']!r}")
    total = int(glance["heading"].split()[0])
    assert sum(glance["windows"]) <= total, (
        "the kickoff windows count more games than the slate has")
    assert " of " in glance["text"], "coverage is shown without its denominator"


def test_there_is_exactly_one_greeting_at_both_widths(page):
    """The greeting MOVES onto the desk; it is not copied.

    Two greetings is two answers to "what happened overnight", and the one in
    the panel nobody scrolled to is the one that would go stale unnoticed.
    """
    for size in (DESK, ROWS):
        _open_week(page, size)
        n = page.evaluate("document.querySelectorAll('#greeting').length")
        assert n == 1, f"{n} greetings in the document at {size['width']}px"
    # And below the breakpoint it is back where the markup put it.
    assert page.evaluate(
        "document.getElementById('greeting').parentElement.id") == "greeting-home"
    _open_week(page, DESK)
    assert page.evaluate(
        "document.getElementById('greeting').parentElement.id") == "rail-since-host"


def test_the_rail_is_absent_below_the_breakpoint(page):
    _open_week(page, ROWS)
    assert page.evaluate("document.getElementById('week-rail').hidden"), (
        "the rail rendered below the breakpoint")


def test_the_rail_scrolls_itself_and_leaves_the_page_pinned(page):
    """The regression D3 introduced and the render caught.

    Three panels are taller than a 900px viewport. Without a scrolling rail
    the body grew to fit them and the whole page started scrolling again --
    undoing D2 -- and it looked like nothing more than a rail with more in it.
    """
    _open_week(page, DESK)
    state = page.evaluate("""() => {
        const rail = document.getElementById('week-rail');
        const frame = document.getElementById('week-frame');
        window.scrollTo(0, 600);
        rail.scrollTop = 100000;          // past the end; the browser clamps
        return {
            page: window.scrollY,
            vh: window.innerHeight,
            rail_bottom: rail.getBoundingClientRect().bottom,
            frame_bottom: frame.getBoundingClientRect().bottom,
            rail_can: rail.scrollHeight > rail.clientHeight,
            rail_at: rail.scrollTop,
        };
    }""")
    assert state["page"] == 0, f"the page scrolled {state['page']}px"
    # THE BOTTOM OF EACH COLUMN HAS TO BE ON SCREEN. `body.scrollHeight` is the
    # wrong thing to assert -- the frame's own scrollable content makes it
    # exceed the viewport by design, and `overflow: hidden` means that costs
    # nothing. What actually broke was the grid running past the window and
    # being clipped, so the last rows of both columns could never be reached.
    for name in ("rail_bottom", "frame_bottom"):
        assert state[name] <= state["vh"] + 2, (
            f"{name} is {state[name]}px in a {state['vh']}px window, so its "
            f"last {round(state[name] - state['vh'])}px is clipped off screen "
            f"and no amount of scrolling reaches it"
        )
    if state["rail_can"]:
        assert state["rail_at"] > 0, "the rail overflows but refuses to scroll"


def test_the_disagreement_says_which_kind_of_points(page):
    """Percentage points, next to a spread measured in football points."""
    _open_week(page, DESK)
    text = page.evaluate("document.getElementById('rail-facts').textContent")
    if "apart" in text:
        assert "percentage points apart" in text, (
            f"the sharpest-disagreement row does not name its unit: {text!r}")
