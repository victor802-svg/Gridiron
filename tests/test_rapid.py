"""The interactions a person performs and the tests never did (UI audit,
2026-09-05, class B): a second click before the first answer lands, a slow
answer, a key pressed after a re-render, a connection that drops.

Every test here asserts the thing a reader sees -- whose cards are on the
page, whether the menu is closed -- never the attribute or the log line that
stood in for it.
"""
from __future__ import annotations

import time

import pytest

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
    with page.expect_response(lambda r: "/api/week" in r.url and f"sport={sport}" in r.url, timeout=20000):
        page.click(f"#sport-tabs button[data-sport='{sport}']")
    page.wait_for_timeout(400)


def _open_week(page):
    page.set_viewport_size(WIDE)
    page.evaluate("location.hash = '#/week'")
    page.wait_for_selector("#week-cards .card, #week-cards .empty", timeout=15000)
    page.wait_for_timeout(300)


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
    def slow(route, request):
        time.sleep(1.2)
        route.continue_()

    # Phase 1: the week picker. The weeks list for the first sport lands late.
    page.route(f"**/api/weeks?*sport={full}*", slow)
    try:
        with page.expect_request(lambda r: "/api/weeks" in r.url and f"sport={full}" in r.url, timeout=10000):
            page.click(f"#sport-tabs button[data-sport='{full}']")
        page.click(f"#sport-tabs button[data-sport='{empty}']")
        page.wait_for_timeout(3000)
    finally:
        page.unroute(f"**/api/weeks?*sport={full}*")
    assert page.evaluate("window.Gridiron.state.sport") == empty
    picker = page.evaluate("[...document.querySelectorAll('#week-picker option')].map(o => o.textContent)")
    assert picker == empty_weeks, f"the week picker holds {picker}, not {empty}'s {empty_weeks}"

    # Phase 2: the slate itself. The first sport's cards land late.
    page.route(f"**/api/week?*sport={full}*", slow)
    try:
        with page.expect_request(lambda r: "/api/week?" in r.url and f"sport={full}" in r.url, timeout=10000):
            page.click(f"#sport-tabs button[data-sport='{full}']")
        page.click(f"#sport-tabs button[data-sport='{empty}']")
        page.wait_for_timeout(3000)
    finally:
        page.unroute(f"**/api/week?*sport={full}*")
    assert page.evaluate("window.Gridiron.state.sport") == empty
    assert page.get_attribute(f"#sport-tabs button[data-sport='{empty}']", "aria-pressed") == "true"
    cards = page.evaluate("document.querySelectorAll('#week-cards .card').length")
    assert cards == 0, f"{cards} of {full}'s cards are on {empty}'s page"
    assert page.evaluate("document.getElementById('error').hidden") is True
    _select(page, full)


def test_two_tabs_in_quick_succession_leave_the_second_one(page):
    _open_week(page)
    full, _ = _full_and_empty(page)
    _select(page, full)
    tabs = page.evaluate("[...document.querySelectorAll('.market-tab')].map(b => b.dataset.market)")
    assert len(tabs) >= 3, tabs
    first, second = tabs[1], tabs[2]
    page.evaluate(f"""() => {{
        document.querySelector(".market-tab[data-market='{first}']").click();
        setTimeout(() => document.querySelector(".market-tab[data-market='{second}']").click(), 60);
    }}""")
    page.wait_for_timeout(2500)
    assert page.evaluate("(document.querySelector('.market-tab[aria-pressed=\"true\"]') || {dataset: {}}).dataset.market") == second
    by_id = page.evaluate(f"fetch('/api/week?sport={full}').then(r => r.json()).then(j => Object.fromEntries(j.cards.map(c => [String(c.prediction_id), c.market])))")
    shown = page.evaluate("[...document.querySelectorAll('#week-cards .card')].map(c => c.dataset.id)")
    wrong = [i for i in shown if by_id.get(i) != second]
    assert not wrong, f"cards from another tab are on the page: {wrong[:5]}"
    page.click(".market-tab[data-market='']")
    page.wait_for_timeout(400)


def test_a_double_clicked_tab_renders_each_pick_once(page):
    _open_week(page)
    full, _ = _full_and_empty(page)
    _select(page, full)
    tabs = page.evaluate("[...document.querySelectorAll('.market-tab')].map(b => b.dataset.market)")
    page.dblclick(f".market-tab[data-market='{tabs[1]}']")
    page.wait_for_timeout(1500)
    ids = page.evaluate("[...document.querySelectorAll('#week-cards .card')].map(c => c.dataset.id)")
    assert len(ids) == len(set(ids)), "a pick is on the page twice"
    page.click(".market-tab[data-market='']")
    page.wait_for_timeout(400)


# `test_escape_closes_the_menu_after_a_choice_and_focus_stays_on_it` was
# retired with the View menu on 2026-09-08. What it protected -- that a
# control returns focus to the thing that opened it -- is carried by the state
# tabs and the Why buttons, which are ordinary buttons with focus rings and no
# panel to close.

def test_offline_says_so_in_words_and_a_later_success_clears_it(page):
    """Go offline, tap a tab, come back, tap again. The box says the server's
    sentence -- not "Failed to fetch" -- and clears when the next tap lands."""
    _open_week(page)
    full, _ = _full_and_empty(page)
    _select(page, full)
    line = page.evaluate("window.Gridiron.state.meta.unreachable_line")
    assert line and "Failed to fetch" not in line
    tabs = page.evaluate("[...document.querySelectorAll('.market-tab')].map(b => b.dataset.market)")
    page.context.set_offline(True)
    try:
        page.evaluate("window.dispatchEvent(new Event('offline'))")
        page.evaluate(f"document.querySelector(\".market-tab[data-market='{tabs[1]}']\").click()")
        page.wait_for_timeout(1500)
        assert page.is_visible("#offline-bar")
        assert page.evaluate("document.getElementById('error').hidden") is False
        shown = page.text_content("#error").strip()
        assert shown == line, f"the error box says {shown!r}"
    finally:
        page.context.set_offline(False)
    page.evaluate("window.dispatchEvent(new Event('online'))")
    with page.expect_response(lambda r: "/api/week" in r.url, timeout=20000):
        page.evaluate(f"document.querySelector(\".market-tab[data-market='{tabs[0]}']\").click()")
    page.wait_for_timeout(600)
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
