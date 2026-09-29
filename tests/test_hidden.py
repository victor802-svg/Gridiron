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
    "#/games": "#games-rows .game, #games-notes .empty",
    "#/props": "#props-tiles .prop, #props-notes .empty",
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


def test_a_hidden_control_is_hidden_to_the_accessibility_tree_too(page):
    """RE-POINTED 2026-09-08. This was written against `#week-showall`, the
    grid's show-all button, which was removed with the grid. THE RULE IS
    UNCHANGED and is the one that was actually broken once: a control with the
    `hidden` attribute must not be painted anyway by a stylesheet rule that
    sets `display`. `.show-all { display: block }` did exactly that.

    It now checks the menu (GRIDIRON_BOARD, 2026-09-24), which is the
    surviving control that spends most of its life hidden."""
    page.set_viewport_size({"width": 1440, "height": 900})
    _open(page, "#/games")
    menu = page.query_selector("#menu")
    assert menu is not None, "the menu is not on the page at all"
    assert page.evaluate("document.getElementById('menu').hidden"), "the menu opens on its own"
    assert page.evaluate(
        "getComputedStyle(document.getElementById('menu')).display") == "none"
    assert page.evaluate("document.getElementById('menu').getAttribute('hidden')") is not None


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
