"""The interactions a person performs and the tests never did (UI audit,
2026-09-05, class B): a second click before the first answer lands, a slow
answer, a key pressed after a re-render, a connection that drops.

Every test here asserts the thing a reader sees -- whose cards are on the
page, whether the menu is closed -- never the attribute or the log line that
stood in for it.
"""
from __future__ import annotations

import pytest

from tests.conftest import (REDRAW_LIMIT_MS, HeldAnswers, wait_for_the_redraw_it_starts,
                            wait_for_the_render, wait_until_read, watch_the_answers)

WIDE = {"width": 1440, "height": 900}


def _sports(page):
    return page.evaluate("[...document.querySelectorAll('#sport-tabs button')].map(b => b.dataset.sport)")


def _card_count_for(page, sport):
    return page.evaluate(f"fetch('/api/week?sport={sport}').then(r => r.json()).then(j => (j.cards || []).length)")


def _full_and_empty(page):
    counts = {sp: _card_count_for(page, sp) for sp in _sports(page)}
    full = max(counts, key=counts.get)
    empty = next((sp for sp, n in counts.items() if n == 0), None)
    assert counts[full] > 0, counts
    assert empty is not None, f"no sport without a slate in the fixture world: {counts}"
    return full, empty


def _select(page, sport):
    if page.evaluate("window.Gridiron.state.sport") == sport:
        return
    # THE SWITCH'S OWN SLATE, SAID LANDED (operator question 5, 2026-10-08):
    # this waited 400ms after the slate's answer arrived.
    with wait_for_the_render(page, "games"):
        page.click(f"#sport-tabs button[data-sport='{sport}']")


def _open_week(page):
    page.set_viewport_size(WIDE)
    # THE HASH'S OWN RENDER, SAID LANDED (operator question 5, 2026-10-08):
    # this waited 300ms after the first row appeared.
    with wait_for_the_render(page, "games"):
        page.evaluate("location.hash = '#/games'")
    page.wait_for_selector("#games-rows .game, #games-notes .empty", timeout=15000)


def test_a_slower_earlier_slate_does_not_take_the_page(page):
    """Click the sport whose slate answers slowly, then another sport before
    it has answered. The page belongs to the second click."""
    _open_week(page)
    full, empty = _full_and_empty(page)
    _select(page, empty)
    empty_weeks = page.evaluate(f"fetch('/api/weeks?sport={empty}').then(r => r.json()).then(j => j.weeks.map(w => w.label))")

    # THE SLOW REQUEST MUST ALREADY BE IN FLIGHT. A request not yet sent goes
    # out with whatever sport is current when it is made, so delaying it proves
    # nothing; the defect is an answer to a question asked BEFORE the second
    # click, arriving after it. So: click the first sport, wait until its slow
    # request has left, then click the second sport, then wait for the answer.
    #
    # HELD AND RELEASED, NEVER SLEPT (operator question 5, 2026-10-08: "a
    # held-and-released response"). The first sport's answer was made late
    # by `time.sleep(1.2)` in its route handler, and the test waited three
    # seconds for both sports. Now the answer is held until the second
    # sport's slate has said it landed, released, and waited for until the
    # page has read it -- so it always arrives after the second click, the
    # case the test is about, and is always seen to arrive.

    # Phase 1: the week picker. The weeks list for the first sport lands late.
    held = HeldAnswers(page, lambda url: "/api/weeks?" in url and f"sport={full}" in url)
    try:
        with page.expect_request(lambda r: "/api/weeks" in r.url and f"sport={full}" in r.url, timeout=10000):
            page.click(f"#sport-tabs button[data-sport='{full}']")
        with wait_for_the_render(page, "games"):
            page.click(f"#sport-tabs button[data-sport='{empty}']")
        assert held.release() == 1
        wait_until_read(page, "/api/weeks?", f"sport={full}")
    finally:
        held.close()
    assert page.evaluate("window.Gridiron.state.sport") == empty
    picker = page.evaluate("[...document.querySelectorAll('#week-picker option')].map(o => o.textContent)")
    assert picker == empty_weeks, f"the week picker holds {picker}, not {empty}'s {empty_weeks}"

    # Phase 2: the slate itself. The first sport's cards land late. ITS
    # ADDRESS EXACTLY: a glob's `?` is any one character, so
    # `**/api/week?*sport=...` held the weeks list too, which comes first.
    held = HeldAnswers(page, lambda url: "/api/week?" in url and f"sport={full}" in url)
    try:
        with page.expect_request(lambda r: "/api/week?" in r.url and f"sport={full}" in r.url, timeout=10000):
            page.click(f"#sport-tabs button[data-sport='{full}']")
        with wait_for_the_render(page, "games"):
            page.click(f"#sport-tabs button[data-sport='{empty}']")
        assert held.release() == 1
        wait_until_read(page, "/api/week?", f"sport={full}")
    finally:
        held.close()
    assert page.evaluate("window.Gridiron.state.sport") == empty
    assert page.get_attribute(f"#sport-tabs button[data-sport='{empty}']", "aria-pressed") == "true"
    cards = page.evaluate("document.querySelectorAll('#games-rows .game').length")
    assert cards == 0, f"{cards} of {full}'s cards are on {empty}'s page"
    assert page.evaluate("document.getElementById('error').hidden") is True
    _select(page, full)


def _open_props(page):
    """RE-HOMED 2026-09-24 (GRIDIRON_BOARD): the market tabs went with the
    old Picks page; the Props chips are the rapid-click control now.

    ITS REDRAW WAITED FOR INSIDE THE PAGE (the board merge, 2026-09-29): the
    board brought a 300ms wait here, under a name the clock register did not
    hold; question 28's helper waits for the tiles' arrival instead, and the
    register only shrinks."""
    with wait_for_the_redraw_it_starts(page, "props-tiles"):
        page.evaluate("location.hash = '#/props'")
    page.wait_for_selector("#props-chips .chip-btn", timeout=15000)


def _tiles_by_id(page, sport):
    return page.evaluate(
        f"fetch('/api/week?sport={sport}').then(r => r.json()).then(j => "
        "Object.fromEntries(j.board.props.tiles.map(t => [String(t.prediction_id), t.family])))")


#: EVERY ANSWER TO ONE SPORT'S SLATE, HELD INSIDE THE PAGE until the test lets
#: it go, one at a time and in the order the test chooses (question 5's
#: prover, 2026-10-08): the page's own `fetch` is wrapped, so the request is
#: sent when it is let go -- a Playwright route released from the test would
#: release them together, in the order asked. `__unholdSlates` puts the
#: page's `fetch` back.
_HOLD_THE_SLATE = """(sport) => {
    const held = window.__heldSlates = [];
    const ask = window.fetch;
    window.fetch = function (input, init) {
        const url = typeof input === 'string' ? input : ((input && input.url) || String(input));
        if (url.includes('/api/week?') && url.includes('sport=' + sport)) {
            return new Promise(go => held.push(go)).then(() => ask.call(window, input, init));
        }
        return ask.apply(this, arguments);
    };
    window.__unholdSlates = () => { window.fetch = ask; };
}"""


def test_two_chips_in_quick_succession_leave_the_second_one(page):
    _open_week(page)
    full, _ = _full_and_empty(page)
    _select(page, full)
    _open_props(page)
    keys = page.evaluate("[...document.querySelectorAll('#props-chips .chip-btn')].map(b => b.dataset.key)")
    # FAMILY CHIPS: not the Kalshi ladder view, which took the empty "Alt
    # lines" chip's place (operator ruling C, 2026-10-05).
    families = [k for k in keys if k and k != "ladder"]
    assert len(families) >= 2, keys
    first, second = families[0], families[1]
    # BOTH RENDERS SEEN TO LAND, INSIDE THE PAGE (the board merge,
    # 2026-09-29): this waited 2.5s for them. Two chips ask for the slate
    # twice, and the helper waits for two arrivals of the tiles to start and
    # the last to end. THE LATER ANSWER FIRST, HELD AND RELEASED (operator
    # question 5, 2026-10-08: "a held-and-released response"): the second
    # chip was pressed 60ms after the first by a timer in the page, then (as
    # first rebuilt) in the same task; either way the answers came back in
    # whatever order the server gave them, and in the order asked the first
    # chip's render drew before the second's, so a page that drew the chip it
    # was asked for, not the one chosen when its answer came, passed
    # (question 5's prover, measured on such a page). Both answers are held
    # inside the page, the second chip's let go first and read, then the
    # first chip's: the late answer always lands last, the case this is
    # about.
    watch_the_answers(page)
    page.evaluate(_HOLD_THE_SLATE, full)
    try:
        with wait_for_the_redraw_it_starts(page, "props-tiles", count=2):
            page.click(f"#props-chips .chip-btn[data-key='{first}']")
            page.click(f"#props-chips .chip-btn[data-key='{second}']")
            page.wait_for_function("window.__heldSlates.length === 2", timeout=REDRAW_LIMIT_MS)
            page.evaluate("window.__heldSlates[1]()")
            wait_until_read(page, "/api/week?", f"sport={full}")
            page.evaluate("window.__heldSlates[0]()")
            wait_until_read(page, "/api/week?", f"sport={full}", count=2)
    finally:
        page.evaluate("() => { if (window.__unholdSlates) window.__unholdSlates(); }")
    assert page.evaluate("(document.querySelector('#props-chips .chip-btn[aria-pressed=\"true\"]') || {dataset: {}}).dataset.key") == second
    by_id = _tiles_by_id(page, full)
    shown = page.evaluate("[...document.querySelectorAll('#props-tiles .prop')].map(c => c.dataset.id)")
    wrong = [i for i in shown if by_id.get(i) != second]
    assert not wrong, f"tiles from another chip are on the page: {wrong[:5]}"
    with wait_for_the_redraw_it_starts(page, "props-tiles"):
        page.click("#props-chips .chip-btn[data-key='']")


def test_a_double_clicked_chip_renders_each_tile_once(page):
    _open_week(page)
    full, _ = _full_and_empty(page)
    _select(page, full)
    _open_props(page)
    keys = page.evaluate("[...document.querySelectorAll('#props-chips .chip-btn')].map(b => b.dataset.key)")
    family = next(k for k in keys if k and k != "ladder")
    # BOTH RENDERS A DOUBLE CLICK ASKS FOR, SEEN TO LAND (the board merge,
    # 2026-09-29): this waited 1.5s; the helper waits for two arrivals.
    with wait_for_the_redraw_it_starts(page, "props-tiles", count=2):
        page.dblclick(f"#props-chips .chip-btn[data-key='{family}']")
    ids = page.evaluate("[...document.querySelectorAll('#props-tiles .prop')].map(c => c.dataset.id)")
    assert len(ids) == len(set(ids)), "a tile is on the page twice"
    with wait_for_the_redraw_it_starts(page, "props-tiles"):
        page.click("#props-chips .chip-btn[data-key='']")


# `test_escape_closes_the_menu_after_a_choice_and_focus_stays_on_it` was
# retired with the View menu on 2026-09-08. What it protected -- that a
# control returns focus to the thing that opened it -- is carried by the
# menu button, the row heads and the chips, which are ordinary buttons with
# focus rings.

def test_offline_says_so_in_words_and_a_later_success_clears_it(page):
    """Go offline, tap a chip, come back, tap again. The box says the server's
    sentence -- not "Failed to fetch" -- and clears when the next tap lands."""
    _open_week(page)
    full, _ = _full_and_empty(page)
    _select(page, full)
    _open_props(page)
    line = page.evaluate("window.Gridiron.state.meta.unreachable_line")
    assert line and "Failed to fetch" not in line
    keys = page.evaluate("[...document.querySelectorAll('#props-chips .chip-btn')].map(b => b.dataset.key)")
    family = next(k for k in keys if k and k != "ladder")
    page.context.set_offline(True)
    try:
        page.evaluate("window.dispatchEvent(new Event('offline'))")
        page.evaluate(f"document.querySelector(\"#props-chips .chip-btn[data-key='{family}']\").click()")
        # THE FAILED ANSWER SAID ON THE PAGE (operator question 5,
        # 2026-10-08): this waited 1.5s. A render whose answer failed lands
        # nothing and says nothing; what it draws is the error box, and that
        # box shown is the event.
        page.wait_for_selector("#error:not([hidden])", state="attached", timeout=15000)
        assert page.is_visible("#offline-bar")
        assert page.evaluate("document.getElementById('error').hidden") is False
        shown = page.text_content("#error").strip()
        assert shown == line, f"the error box says {shown!r}"
    finally:
        page.context.set_offline(False)
    page.evaluate("window.dispatchEvent(new Event('online'))")
    # THE NEXT TAP'S TILES, SAID LANDED (operator question 5, 2026-10-08):
    # this waited 600ms after the answer arrived.
    with wait_for_the_redraw_it_starts(page, "props-tiles"):
        page.evaluate("document.querySelector(\"#props-chips .chip-btn[data-key='']\").click()")
    assert page.evaluate("document.getElementById('error').hidden") is True, "the error survived the next success"
    assert not page.is_visible("#offline-bar")


def test_the_guard_names_a_fetch_that_paints_unchecked():
    from gridiron import audit, config
    js = (config.PACKAGE_ROOT / "web" / "app.js").read_text(encoding="utf-8")
    assert audit.render_guard_faults(js) == []
    broken = js.replace("    if (seq !== weekSeq) return;\n", "", 1)
    assert broken != js
    faults = audit.render_guard_faults(broken)
    assert faults and "superseded" in faults[0]
    unchecked = js.replace("    if (stale(seq)) return;\n", "", 1)
    faults = audit.render_guard_faults(unchecked)
    assert faults and "without checking" in faults[0]
