"""Hidden means not painted (UI audit, 2026-09-05).

Three elements shipped with `hidden` set and a class rule setting `display`:
the view panel, the show-all button, the yesterday strip. Each was hidden to
every assertion that read the attribute and painted for every reader. The
tests here ask the thing, not the proxy: for every `[hidden]` element on every
route, at both widths, is its computed display `none`?
"""
from __future__ import annotations

import pytest

from gridiron import audit, config

ROUTES = {
    "#/week": "#week-cards .card, #week-cards .empty",
    "#/record": "#tier-table tr",
    "#/results": "#history-table tbody tr, #history-table .empty",
    "#/settings": "#settings-health .set",
}

PAINTED_JS = """() => [...document.querySelectorAll('[hidden]')]
  .filter(e => getComputedStyle(e).display !== 'none')
  .map(e => e.tagName.toLowerCase() + (e.id ? '#' + e.id : '')
       + (typeof e.className === 'string' && e.className ? '.' + e.className.trim().split(/\\s+/)[0] : '')
       + ' display=' + getComputedStyle(e).display)"""


def _open(page, route):
    page.evaluate(f"location.hash = '{route}'")
    page.wait_for_selector(ROUTES[route], timeout=15000)
    page.wait_for_timeout(300)


@pytest.mark.parametrize("width", [1440, 390])
def test_nothing_hidden_is_painted_on_any_route(page, width):
    page.set_viewport_size({"width": width, "height": 900})
    for route in ROUTES:
        _open(page, route)
        painted = page.evaluate(PAINTED_JS)
        assert painted == [], f"{route} at {width}: hidden but painted: {painted}"


def test_the_show_all_button_is_not_painted_once_it_has_shown_all(page):
    """The button that showed the rest of the grid must not stay on the page,
    painted and clickable, doing nothing. It had `hidden` set; `.show-all
    { display: block }` painted it anyway."""
    page.set_viewport_size({"width": 1440, "height": 900})
    _open(page, "#/week")
    if page.evaluate("!!document.querySelector('#week-tier-seg button[data-tier=\"\"]')"):
        page.click("#week-tier-seg button[data-tier='']")
        page.wait_for_timeout(500)
    button = page.query_selector("#week-showall")
    assert button is not None
    if page.evaluate("!document.getElementById('week-showall').hidden"):
        page.click("#week-showall")
        page.wait_for_timeout(600)
    assert page.evaluate("document.getElementById('week-showall').hidden") is True
    assert page.evaluate("getComputedStyle(document.getElementById('week-showall')).display") == "none"
    assert not page.is_visible("#week-showall")
    box = page.evaluate("(() => { const r = document.getElementById('week-showall').getBoundingClientRect(); return r.width * r.height; })()")
    assert box == 0, "the hidden show-all button still has a box"


def test_the_stylesheet_declares_that_hidden_wins():
    css = (config.PACKAGE_ROOT / "web" / "style.css").read_text(encoding="utf-8")
    assert audit.hidden_rule_faults(css) == []
    assert "!important" in css.split("[hidden]", 1)[1].split("}", 1)[0]


def test_the_guard_sees_the_rule_deleted():
    css = (config.PACKAGE_ROOT / "web" / "style.css").read_text(encoding="utf-8")
    without = css.replace("[hidden] { display: none !important; }", "", 1)
    assert without != css
    faults = audit.hidden_rule_faults(without)
    assert faults and "!important" in faults[0]
    # A copy of the rule inside a comment does not satisfy the guard (LAW: a
    # scanner reads code, not comments).
    commented = without + "\n/* [hidden] { display: none !important; } */\n"
    assert audit.hidden_rule_faults(commented)
