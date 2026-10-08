"""Every control does something (UI audit, 2026-09-05, class D).

The Record's Market select was filled and never wired; the forecaster picker
set a variable nothing read; the Settings switch wrote a line and never its
own face. No test acted on any of them and looked at the thing it governs.
These do: act, then assert a request was made or the region changed.
"""
from __future__ import annotations

from tests.conftest import wait_for_the_render

WIDE = {"width": 1440, "height": 900}


def _open_record(page):
    page.set_viewport_size(WIDE)
    # THE RECORD PAGE, EVERY PART OF IT LANDED (operator question 5,
    # 2026-10-08): this waited 300ms after the tier table's first row, which
    # the page draws before the parts it fetches on its own.
    with wait_for_the_render(page, "record"):
        page.evaluate("location.hash = '#/record'")
    page.wait_for_selector("#tier-table tr", timeout=15000)


def _caption(page):
    return page.evaluate("document.getElementById('tier-caption').textContent")


def _label(page, market):
    return page.evaluate(f"(window.Gridiron.state.marketLabels || {{}})[{market!r}] || {market!r}")


def test_the_market_select_fetches_the_tier_table_it_names(page):
    _open_record(page)
    options = page.evaluate("[...document.querySelectorAll('#tier-market option')].map(o => o.value)")
    assert len(options) >= 2, options
    seen = []
    for market in options[:3]:
        # THE TABLE IT ASKED FOR, SAID LANDED (operator question 5,
        # 2026-10-08): this waited 300ms after the answer arrived.
        with wait_for_the_render(page, "record", "tier-table"), \
                page.expect_response(lambda r, m=market: "/api/tier-table" in r.url and f"market={m}" in r.url, timeout=15000) as got:
            page.select_option("#tier-market", market)
        assert got.value.status == 200, got.value.url
        caption = _caption(page)
        assert _label(page, market) in caption, f"the caption {caption!r} does not name {market!r}"
        assert page.evaluate("document.querySelectorAll('#tier-table tbody tr, #tier-table tr').length") >= 2
        seen.append(caption)
    assert len(set(seen)) == len(seen), f"three markets, the same caption: {seen}"


def test_the_forecaster_picker_fetches_the_tier_table_it_names(page):
    _open_record(page)
    labels = page.evaluate("[...document.querySelectorAll('#forecaster-picker button')].map(b => [b.textContent.trim(), b.dataset.forecaster])")
    assert len(labels) == 2, labels
    other_label, other = next((l, f) for l, f in labels if f != "statistical")
    # THE FORECASTER'S TABLE, SAID LANDED (operator question 5, 2026-10-08):
    # this waited 300ms after each answer arrived.
    with wait_for_the_render(page, "record", "tier-table"), \
            page.expect_response(lambda r: "/api/tier-table" in r.url and f"forecaster={other}" in r.url, timeout=15000) as got:
        page.click(f"#forecaster-picker button[data-forecaster='{other}']")
    assert got.value.status == 200
    assert page.get_attribute(f"#forecaster-picker button[data-forecaster='{other}']", "aria-pressed") == "true"
    assert other_label in _caption(page), _caption(page)
    with wait_for_the_render(page, "record", "tier-table"), \
            page.expect_response(lambda r: "/api/tier-table" in r.url and "forecaster=statistical" in r.url, timeout=15000):
        page.click("#forecaster-picker button[data-forecaster='statistical']")
    assert "statistical" in _caption(page)


def test_the_tier_table_route_refuses_a_market_the_sport_does_not_ask(page):
    _open_record(page)
    sport = page.evaluate("window.Gridiron.state.sport")
    status = page.evaluate(f"fetch('/api/tier-table?sport={sport}&market=no_such_market').then(r => r.status)")
    assert status == 404


def test_every_record_control_asks_or_changes_something(page):
    """The generic form of the class: act on each control, and something the
    control governs must follow -- a request, or a change in its region."""
    _open_record(page)
    # EACH CONTROL'S REDRAW, SAID LANDED (operator question 5, 2026-10-08):
    # the chart selects draw the whole page again, the market select its
    # table, the search its cards; this waited 200ms and 300ms.
    checks = [
        ("#chart-market", "select", "/api/over-time", "view-record"),
        ("#chart-predictor", "select", "/api/over-time", "view-record"),
        ("#tier-market", "select", "/api/tier-table", "tier-table"),
    ]
    for selector, kind, expected_url, panel in checks:
        options = page.evaluate(f"[...document.querySelectorAll('{selector} option')].map(o => o.value)")
        current = page.evaluate(f"document.querySelector('{selector}').value")
        target = next(o for o in options if o != current)
        with wait_for_the_render(page, "record", panel), \
                page.expect_response(lambda r, u=expected_url: u in r.url, timeout=15000):
            page.select_option(selector, target)
    before = page.evaluate("[...document.querySelectorAll('#factors-cards > *')].filter(c => getComputedStyle(c).display !== 'none').length")
    with wait_for_the_render(page, "record", "factors-cards"):
        page.fill("#factors-search", "zzzz-no-such-factor")
    after = page.evaluate("[...document.querySelectorAll('#factors-cards > *')].filter(c => getComputedStyle(c).display !== 'none').length")
    assert after < before, "the factor search changed nothing"
    with wait_for_the_render(page, "record", "factors-cards"):
        page.fill("#factors-search", "")


def test_a_settings_switch_reads_what_it_saved(page):
    page.set_viewport_size(WIDE)
    # SETTINGS, AND THEN THE SAVE'S OWN ROW, EACH SAID LANDED (operator
    # question 5, 2026-10-08): this waited 300ms after the switches appeared,
    # after the save's answer arrived, and after putting it back.
    with wait_for_the_render(page, "settings"):
        page.evaluate("location.hash = '#/settings'")
    page.wait_for_selector("#settings-sections .set-switch", timeout=15000)
    before = page.get_attribute("#settings-sections .set-switch >> nth=0", "aria-pressed")
    word = page.text_content("#settings-sections .set-switch >> nth=0").strip()
    assert (before == "true") == (word == "on")
    want = "false" if before == "true" else "true"
    try:
        with wait_for_the_render(page, "settings", "settings-row"), \
                page.expect_response(lambda r: "/api/settings" in r.url and r.request.method == "POST", timeout=15000) as got:
            page.click("#settings-sections .set-switch >> nth=0")
        assert got.value.status == 200
        assert page.get_attribute("#settings-sections .set-switch >> nth=0", "aria-pressed") == want, "the switch face ignored its own save"
        assert page.text_content("#settings-sections .set-switch >> nth=0").strip() == ("on" if want == "true" else "off")
        line = page.evaluate("(() => { const b = document.querySelector('#settings-sections .set-switch'); const s = b.closest('.set').querySelector('.set-said'); return s ? s.textContent : ''; })()")
        assert "changed" in line, line
        page.reload()
        page.wait_for_function("document.body.dataset.ready === 'true'", timeout=20000)
        page.evaluate("location.hash = '#/settings'")
        page.wait_for_selector("#settings-sections .set-switch", timeout=15000)
        assert page.get_attribute("#settings-sections .set-switch >> nth=0", "aria-pressed") == want
    finally:
        # put the shared world back the way it was
        if page.get_attribute("#settings-sections .set-switch >> nth=0", "aria-pressed") != before:
            with wait_for_the_render(page, "settings", "settings-row"), \
                    page.expect_response(lambda r: "/api/settings" in r.url and r.request.method == "POST", timeout=15000):
                page.click("#settings-sections .set-switch >> nth=0")
    assert page.get_attribute("#settings-sections .set-switch >> nth=0", "aria-pressed") == before
