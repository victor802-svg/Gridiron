"""The view menu on Picks (R2, 2026-09-05)."""
from __future__ import annotations

import re

import pytest

from gridiron import audit, config

WIDE = {"width": 1440, "height": 900}


def _open_week(page):
    page.set_viewport_size(WIDE)
    page.evaluate("location.hash = '#/record'")
    with page.expect_response(lambda r: "/api/week" in r.url):
        page.evaluate("location.hash = '#/week'")
    page.wait_for_selector("#week-view-button", timeout=10000)
    page.wait_for_function(
        "document.getElementById('week-view-tag').textContent.includes('·')", timeout=10000)


def test_the_menu_is_a_tap_target_that_opens_and_closes(page):
    _open_week(page)
    box = page.query_selector("#week-view-button").bounding_box()
    assert box["height"] >= 44, f"the view menu button is {box['height']:.0f}px tall"
    assert page.get_attribute("#week-view-button", "aria-expanded") == "false"
    assert page.evaluate("document.getElementById('week-view-panel').hidden") is True
    # HIDDEN MEANS NOT PAINTED, not an attribute: the first version checked the
    # attribute and passed while `.view-panel { display: grid }` overrode it
    # and the panel sat open under an unexpanded button.
    assert not page.is_visible("#week-view-panel"), "the closed panel is painted"
    assert page.evaluate(
        "getComputedStyle(document.getElementById('week-view-panel')).display") == "none"
    page.click("#week-view-button")
    assert page.get_attribute("#week-view-button", "aria-expanded") == "true"
    assert page.is_visible("#week-view-panel")
    # Closes on a click elsewhere.
    page.click("#week-headline")
    assert page.evaluate("document.getElementById('week-view-panel').hidden") is True
    assert not page.is_visible("#week-view-panel")
    # And on Escape, handing focus back to the button.
    page.click("#week-view-button")
    page.keyboard.press("Escape")
    assert page.evaluate("document.getElementById('week-view-panel').hidden") is True
    assert page.evaluate("document.activeElement.id") == "week-view-button"


def test_the_menu_is_reachable_by_keyboard(page):
    _open_week(page)
    page.focus("#week-view-button")
    page.keyboard.press("Enter")
    assert page.get_attribute("#week-view-button", "aria-expanded") == "true"
    page.keyboard.press("Tab")
    focused = page.evaluate("document.activeElement.closest('#week-view-panel') !== null")
    assert focused, "Tab from the open menu did not land inside it"


def test_the_tag_says_the_current_choice_in_a_word_each(page):
    _open_week(page)
    tag = page.text_content("#week-view-tag").strip()
    assert re.fullmatch(r"\S+ · (final|early)", tag), tag
    assert tag == "statistical · final"
    page.click("#week-view-button")
    labels = page.evaluate(
        "[...document.querySelectorAll('#week-view-panel .view-choice-label')].map(e => e.textContent)")
    assert labels == ["Forecaster", "Forecast"]
    segs = page.evaluate("document.querySelectorAll('#week-view-panel .seg').length")
    assert segs == 2, "two small labelled toggles"


def test_choosing_the_other_forecaster_updates_the_tag_and_is_remembered_per_sport(page):
    _open_week(page)
    page.click("#week-view-button")
    with page.expect_response(lambda r: "forecaster=llm" in r.url):
        page.click("#week-forecaster-seg [data-forecaster='llm']")
    page.wait_for_function(
        "document.getElementById('week-view-tag').textContent.startsWith('LLM')", timeout=10000)
    assert page.text_content("#week-view-tag").strip() == "LLM · final"
    # Another sport gets its own default; coming back finds the choice kept.
    other = next(s for s in config.SPORTS if s != "nfl")
    with page.expect_response(lambda r: "/api/week" in r.url):
        page.click(f"#sport-tabs button[data-sport='{other}']")
    page.wait_for_function(
        "document.getElementById('week-view-tag').textContent.includes('·')", timeout=10000)
    assert not page.text_content("#week-view-tag").startswith("LLM")
    with page.expect_response(lambda r: "forecaster=llm" in r.url):
        page.click("#sport-tabs button[data-sport='nfl']")
    page.wait_for_function(
        "document.getElementById('week-view-tag').textContent.startsWith('LLM')", timeout=10000)


# --- the guard ---------------------------------------------------------------

def test_the_shipped_page_has_exactly_two_control_rows_above_the_hero():
    html = (config.PACKAGE_ROOT / "web" / "index.html").read_text(encoding="utf-8")
    assert audit.picks_control_rows(html) == list(audit.PICKS_CONTROL_ROWS)
    assert audit.picks_control_row_faults(html) == []


def test_the_guard_sees_a_third_control_row():
    html = (config.PACKAGE_ROOT / "web" / "index.html").read_text(encoding="utf-8")
    anchor = '<section id="week-hero"'
    third = html.replace(anchor, '<div class="extra"><button type="button">x</button></div>' + anchor, 1)
    faults = audit.picks_control_row_faults(third)
    assert faults and "extra" in faults[0]
    # A collapsed details with selects is not a row until it is opened.
    assert "week-more" not in audit.picks_control_rows(html)
