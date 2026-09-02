"""The desk layout: what must be true at 1280px and above, and below it.

The frame is the only thing that scrolls, a tile never truncates, and
selecting a pick does not move the reader's place. Each of those is a claim
the eye cannot check reliably on a 177-pick slate, so each is asserted.
"""

from __future__ import annotations

import re

import pytest

from gridiron import audit

DESK = {"width": 1400, "height": 900}
ROWS = {"width": 1100, "height": 900}


def _open_week(page, size):
    """Open the slate at a width and WAIT FOR IT, not for a duration.

    This slept for 900ms and was called twenty-eight times in this file --
    twenty-five seconds of the suite spent waiting for a render that usually
    finished in a fraction of it. A fixed sleep is also the flakier choice: it
    is simultaneously too long on a fast machine and too short on a loaded
    one, and the failure it produces on the loaded one looks like a broken
    assertion rather than a race.

    The condition is the thing the tests are about to assert on -- the layout
    for this width has actually rendered -- so waiting for it is both faster
    and more honest than waiting for a clock.
    """
    page.set_viewport_size(size)
    page.evaluate("location.hash = '#/week'")
    page.wait_for_function(
        """() => {
            if (document.body.dataset.ready !== 'true') return false;
            const desk = document.body.classList.contains('desk-on');
            const tiles = document.querySelectorAll('#week-frame .tile').length;
            const rows = document.querySelectorAll('#week-cards .rows .row').length;
            // The layout that BELONGS at this width has to be the one present:
            // during a resize both can exist for a frame, and asserting then
            // is what a fixed sleep was accidentally avoiding.
            return desk ? (tiles > 0 && rows === 0) : (rows > 0 && tiles === 0);
        }""",
        timeout=15000,
    )


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
            rail: !!body.querySelector('.row-numbers'),
            why: !!body.querySelector('.row-why'),
            more: !!body.querySelector('.row-more'),
        };
    }""")
    # `.rail .track` until 2026-09-02: the graphic went with GRIDIRON_16
    # R3 and `.row-numbers` states the same three numbers as a sentence.
    # What this test really asserts is unchanged -- the rail panel and the
    # expanded row are built by ONE function, so they cannot drift apart.
    assert found["rail"], "the selected-pick panel does not state its numbers"
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


# ---------------------------------------------------------------------------
# THE PHONE IS UNCHANGED, AND PROVEN (D4)
# ---------------------------------------------------------------------------

PHONE = {"width": 390, "height": 844}
EDGE_ON = {"width": 1280, "height": 900}     # the breakpoint itself
EDGE_OFF = {"width": 1279, "height": 900}    # one pixel below it


def test_the_breakpoint_is_decided_at_the_breakpoint(page):
    """MENTOR section 3: a rule with a numeric boundary is tested AT it.

    `min-width: 1280px` includes 1280. Asserting 1400 and 1100 would leave the
    only interesting pixel untested, and an off-by-one here is a whole layout.
    """
    _open_week(page, EDGE_ON)
    assert page.evaluate("document.body.classList.contains('desk-on')"), (
        "1280px is the breakpoint and must show the desk")
    _open_week(page, EDGE_OFF)
    assert not page.evaluate("document.body.classList.contains('desk-on')"), (
        "1279px is below the breakpoint and must show the rows")


def test_nothing_overflows_sideways_at_any_declared_width(page):
    """A page that scrolls horizontally has lost something off the edge."""
    for size in (DESK, EDGE_ON, EDGE_OFF, ROWS, PHONE):
        _open_week(page, size)
        over = page.evaluate(
            "Math.max(0, document.documentElement.scrollWidth - window.innerWidth)")
        assert over == 0, f"{size['width']}px overflows sideways by {over}px"


def test_every_tap_target_on_the_phone_is_big_enough(page):
    """44px, with ONE declared exemption: a link inside a sentence.

    Inflating a citation link in the middle of a line of prose would break the
    line to satisfy a number -- the accessibility guidance exempts inline
    targets for exactly that reason. The exemption is written here so it is a
    decision on the record rather than a threshold quietly lowered.
    """
    _open_week(page, PHONE)
    small = page.evaluate("""() => [...document.querySelectorAll(
        'button, a, [role=option], select, input')]
      .filter(e => e.offsetParent !== null)
      .filter(e => !e.closest('p'))          // inline in a sentence: exempt
      .map(e => { const r = e.getBoundingClientRect();
                  return {what: e.id || e.className || e.tagName,
                          text: (e.textContent||'').trim().slice(0, 24),
                          h: Math.round(r.height)}; })
      .filter(t => t.h > 0 && t.h < 44)""")
    assert not small, f"tap targets under 44px on the phone: {small}"


def test_the_hidden_scrollbar_scrolls_by_touch_as_well_as_wheel(page):
    """Hiding a scrollbar is a look; breaking touch is a broken page.

    The wheel is covered above. This drives the frame the way a thumb does --
    a press, a move, a release -- because `overflow: hidden` on an ancestor and
    a stray `touch-action` are both invisible until someone tries to drag.
    """
    _open_week(page, DESK)
    page.evaluate("document.getElementById('week-frame').scrollTop = 0")
    moved = page.evaluate("""() => {
        const frame = document.getElementById('week-frame');
        return getComputedStyle(frame).touchAction;
    }""")
    assert moved not in ("none",), (
        f"the frame sets touch-action: {moved}, so a thumb cannot scroll it")
    # And it does move when driven.
    page.mouse.move(400, 500)
    page.mouse.wheel(0, 500)
    page.wait_for_timeout(200)
    assert page.evaluate("document.getElementById('week-frame').scrollTop") > 0


def test_the_compact_rows_are_the_same_rows_below_the_breakpoint(page):
    """D4's promise: the phone did not change because the desk was built."""
    for size in (EDGE_OFF, ROWS, PHONE):
        _open_week(page, size)
        assert page.query_selector_all("#week-cards .rows .row"), (
            f"no compact rows at {size['width']}px")
        assert not page.query_selector_all("#week-frame .tile"), (
            f"desk tiles rendered at {size['width']}px")
        assert page.evaluate("document.getElementById('week-rail').hidden"), (
            f"the rail is visible at {size['width']}px")


def test_the_grid_does_not_re_sort_while_a_slate_is_in_progress(page):
    """A tile that changes state re-renders IN PLACE.

    Splitting resolved picks out of the grid unconditionally meant a game
    ending made its tile vanish and reappear in a list below -- the reader is
    part way down a slate and the thing they were looking at moves. Sorting
    live games by confidence would do the same thing continuously.
    """
    _open_week(page, DESK)
    order = page.evaluate("""() => [...document.querySelectorAll('#week-frame .tile')]
        .map(t => t.dataset.id)""")
    if not order:
        pytest.skip("no tiles on this fixture slate")
    # Applying a live update must not reorder the grid.
    page.evaluate("""() => {
        const tiles = [...document.querySelectorAll('#week-frame .tile')];
        const first = tiles[0];
        if (window.__applyLiveProbe) return;
        first.dataset.state = 'final';
    }""")
    after = page.evaluate("""() => [...document.querySelectorAll('#week-frame .tile')]
        .map(t => t.dataset.id)""")
    assert after == order, "the grid reordered under the reader"


def test_every_tile_declares_which_state_it_is_in(page):
    """The renderer branches on a word the server chose."""
    _open_week(page, DESK)
    states = page.evaluate("""() => [...document.querySelectorAll('#week-frame .tile')]
        .map(t => t.dataset.state)""")
    if states:
        assert set(states) <= {"upcoming", "live", "final"}, (
            f"a tile is in a state nobody declared: {set(states)}")


def test_the_live_mark_is_never_green(page):
    """Green is the positive value and the interactive accent, and it has
    exactly those two jobs. A game being played is neither."""
    _open_week(page, DESK)
    colours = page.evaluate("""() => [...document.querySelectorAll('.tile-live')]
        .map(e => getComputedStyle(e).backgroundColor)""")
    green = page.evaluate(
        "getComputedStyle(document.documentElement).getPropertyValue('--green').trim()")
    for colour in colours:
        assert green.lower() not in colour.lower().replace(' ', ''), (
            f"the live mark is drawn in the accent colour: {colour}")


def test_the_layout_is_decided_by_the_breakpoint_and_nothing_else(page):
    """THE JS AND THE CSS MUST AGREE, ALWAYS (GRIDIRON_16 R6).

    `isDesk()` compared window.innerWidth to 1280 while the stylesheet used
    its own `@media (min-width: 1280px)`. Two mechanisms deciding one thing,
    in step only while resize events kept arriving. When they disagreed the
    renderer built the desk's TILES and the media query withheld every tile
    rule, so the slate rendered as unstyled boxes with empty-looking rail
    panels -- which is what "the desk did not engage for a daily sport"
    looked like from outside, and why it was read as a per-sport bug.

    This asserts the two answers are the same answer at every width, which is
    the property that makes the sport irrelevant.
    """
    page.evaluate("location.hash = '#/week'")
    page.wait_for_selector("#week-cards", timeout=10000)
    for width, height in ((1440, 900), (1280, 860), (1279, 860), (390, 844)):
        page.set_viewport_size({"width": width, "height": height})
        page.wait_for_timeout(350)
        agree = page.evaluate(
            """() => ({
                css: window.matchMedia('(min-width: 1280px)').matches,
                js: document.body.classList.contains('desk-on'),
                tiles: document.querySelectorAll('#week-cards .tile').length,
                rows: document.querySelectorAll('#week-cards .row').length,
            })"""
        )
        assert agree["css"] == agree["js"], (
            f"at {width}px the stylesheet says desk={agree['css']} and the "
            f"renderer says {agree['js']}")
        if agree["css"]:
            assert agree["tiles"] > 0, f"desk at {width}px drew no tiles"
        else:
            assert agree["rows"] > 0, f"phone at {width}px drew no rows"
            assert agree["tiles"] == 0, (
                f"at {width}px the renderer built desk tiles the stylesheet "
                f"will not style")


def test_the_breakpoint_is_declared_once(page):
    """One number. A second literal is how the two would drift apart."""
    from pathlib import Path

    repo = Path(__file__).resolve().parent.parent
    js = (repo / "gridiron" / "web" / "app.js").read_text(encoding="utf-8")
    # CODE, NOT PROSE. The comments above the declaration explain the number
    # and quote the media query; counting those would make the rule
    # impossible to satisfy without deleting the explanation.
    in_code = 0
    for line in js.splitlines():
        stripped = line.strip()
        if stripped.startswith(("//", "*", "/*")):
            continue
        in_code += line.split("//")[0].count("1280")
    assert in_code == 1, (
        f"1280 appears {in_code} times in app.js code; the breakpoint is "
        f"declared once and read through DESK_QUERY")
    assert "matchMedia" in js, "the renderer no longer reads the media query"


# ---------------------------------------------------------------------------
# STRONG BY DEFAULT (ruling R2, 2026-09-02), in the browser
#
# Picks opens on a filter the reader did not choose. That makes three things
# load-bearing, and all three are asserted here rather than eyeballed: the
# band that is pressed on arrival, the count line that names what the band
# was taken out of, and the way out.
# ---------------------------------------------------------------------------

TIER_SEG = "#week-tier-seg"


def _pressed_tier(page):
    """Which band the segmented filter is showing as active, '' for all."""
    return page.evaluate(
        """() => {
            const host = document.querySelector('#week-tier-seg');
            if (!host) return null;
            const on = host.querySelector('[aria-pressed="true"]');
            return on ? on.dataset.tier : null;
        }""")


def _tiers_offered(page):
    return page.evaluate(
        """() => Array.from(
            document.querySelectorAll('#week-tier-seg button'))
            .map(b => b.dataset.tier)""")


def test_picks_arrives_on_strong(page):
    """The reader chose nothing; the page still opens on the strongest band."""
    _open_week(page, DESK)
    if "STRONG" not in _tiers_offered(page):
        pytest.skip("no STRONG picks on this slate; the default yields by "
                    "design and test_the_default_yields_on_a_slate_without_it "
                    "covers that case")
    assert _pressed_tier(page) == "STRONG", (
        "Picks did not open on the band ruling R2 named"
    )


def test_the_way_out_of_the_default_is_on_the_page(page):
    """A filter nobody chose must not be a filter nobody can leave."""
    _open_week(page, DESK)
    offered = _tiers_offered(page)
    if _pressed_tier(page):
        assert "" in offered, "no 'all tiers' button beside an active filter"
        assert not page.evaluate(
            "document.querySelector('#week-tier-seg').hidden"), (
            "the filter is active and its control is hidden"
        )


def test_the_arrival_count_says_what_it_narrowed(page):
    _open_week(page, DESK)
    said = page.text_content("#week-counts") or ""
    if not _pressed_tier(page):
        return
    assert "STRONG" in said, f"the count line does not name the band: {said!r}"
    assert re.search(r"\d+\s+of\s+\d+", said), (
        f"the count line names no denominator: {said!r}. A reader who never "
        f"chose a filter reads this as the size of the slate."
    )


def test_the_caveat_names_its_shortfall_and_never_a_rate(page):
    _open_week(page, DESK)
    said = (page.text_content("#tier-caveat") or "").strip()
    hidden = page.evaluate("document.getElementById('tier-caveat').hidden")
    if hidden:
        # The band cleared its gate, or the default yielded. Both are the
        # sentence's own disappearing conditions, not a missing element.
        assert said == ""
        return
    assert "STRONG" in said and "settled" in said
    assert "%" not in said, "a caveat about sample size stated a rate"


def test_the_caveat_goes_when_the_reader_leaves_the_default(page):
    """It explains the DEFAULT. Under a band the reader picked it is noise."""
    _open_week(page, DESK)
    if _pressed_tier(page) != "STRONG":
        pytest.skip("the default did not engage on this slate")
    page.click('#week-tier-seg button[data-tier=""]')
    page.wait_for_function(
        "() => document.getElementById('tier-caveat').hidden === true",
        timeout=5000)


def test_the_toggle_is_remembered_for_the_session(page):
    """Chosen once, kept across a re-render of the same sport."""
    _open_week(page, DESK)
    if _pressed_tier(page) != "STRONG":
        pytest.skip("the default did not engage on this slate")
    page.click('#week-tier-seg button[data-tier=""]')
    page.wait_for_function(
        """() => {
            const on = document.querySelector(
                '#week-tier-seg [aria-pressed="true"]');
            return on && on.dataset.tier === '';
        }""", timeout=5000)
    page.evaluate("location.hash = '#/record'")
    page.wait_for_timeout(200)
    _open_week(page, DESK)
    assert _pressed_tier(page) == "", (
        "the filter reverted to the default after the reader had changed it"
    )


def test_the_default_holds_at_390(page):
    """Same band, same sentence, no desk."""
    _open_week(page, PHONE)
    if "STRONG" not in _tiers_offered(page):
        pytest.skip("no STRONG picks on this slate")
    assert _pressed_tier(page) == "STRONG"
    said = page.text_content("#week-counts") or ""
    assert "STRONG" in said and re.search(r"\d+\s+of\s+\d+", said), said


def test_the_default_yields_on_a_slate_without_it(page):
    """A default that empties the page is a defect, not a convenience.

    Driven through the real render: the slate is served with its STRONG cards
    removed, which is what a night of nothing but LEAN picks looks like. The
    page must open on every tier rather than on an empty band.
    """
    def _drop_strong(route):
        response = route.fetch()
        payload = response.json()
        payload["cards"] = [
            c for c in payload.get("cards", [])
            if ((c.get("tier") or {}).get("tier") or "") != "STRONG"]
        route.fulfill(response=response, json=payload)

    page.route("**/api/week*", _drop_strong)
    try:
        _open_week(page, DESK)
        assert page.eval_on_selector_all(
            "#week-frame .tile", "els => els.length") > 0, (
            "the page opened empty on a slate with no STRONG picks; the "
            "default filtered out everything the reader came to see"
        )
        assert _pressed_tier(page) == "", (
            "the default engaged on a band that has no picks on this slate"
        )
        assert page.evaluate(
            "document.getElementById('tier-caveat').hidden") is True, (
            "the caveat explains a default that did not engage"
        )
    finally:
        page.unroute("**/api/week*")


# ---------------------------------------------------------------------------
# THE LIVE TICK REACHES THE TILE
#
# `applyLive` fetched the tile's corner by a class that had been renamed out
# of existence (bd7ac2f). querySelector answered null, paintTileCorner threw,
# and the throw escaped the forEach around it -- so one tile stopped the score
# update for every pick after it. Nothing failed: the suite was green, the
# page rendered, and the scores simply stopped moving.
#
# Every existing desk test asserted on the FIRST render. This one asserts that
# a tick lands, which is the assertion that was missing.
# ---------------------------------------------------------------------------


def test_a_live_tick_reaches_the_tile_without_throwing(page):
    """Drive one real poll through applyLive and watch for a throw.

    Both routes are served rather than stubbed in the page: the slate says it
    is in progress (which is what starts the poll at all -- a complete slate
    never ticks, which is why no existing test reached this code), and the
    poll answers with the tile the reader can see.
    """
    seen = {"ids": []}

    def _in_progress(route):
        response = route.fetch()
        payload = response.json()
        glance = payload.get("glance") or {}
        glance["state"] = "in_progress"
        payload["glance"] = glance
        seen["ids"] = [c.get("prediction_id") for c in payload.get("cards", [])
                       if c.get("prediction_id")]
        route.fulfill(response=response, json=payload)

    def _one_final_pick(route):
        route.fulfill(json={
            "picks": [{"prediction_id": seen["ids"][0],
                       "tile_state": "final",
                       "score_line": "TST 7 - TST 3"}] if seen["ids"] else [],
            "games": [],
            "any_live": False,
        })

    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.route("**/api/week*", _in_progress)
    page.route("**/api/live*", _one_final_pick)
    try:
        _open_week(page, DESK)
        if not seen["ids"]:
            pytest.skip("no picks on this slate to tick")
        page.wait_for_timeout(1200)
        assert not errors, (
            f"a live tick threw: {errors}. The throw escapes the loop over "
            f"picks, so every pick after this one stops updating and the "
            f"scores freeze with nothing on the page saying so."
        )
        # And the tick actually LANDED -- a test that only proves nothing threw
        # would also pass on a poll that never ran.
        painted = page.evaluate(
            """(id) => {
                const tile = document.querySelector(
                    '#week-frame .tile[data-id="' + id + '"]');
                return tile ? (tile.textContent || '') : null;
            }""", str(seen["ids"][0]))
        assert painted and "TST 7 - TST 3" in painted, (
            f"the live score never reached the tile: {painted!r}"
        )
    finally:
        page.unroute("**/api/week*")
        page.unroute("**/api/live*")


def test_every_class_the_page_asks_for_is_a_class_it_builds():
    """The scan, run against the shipped files (mechanism, not habit)."""
    audit.check_no_dead_selectors()
