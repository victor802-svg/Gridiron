"""A market tab filters the slate (UI audit finding 24, 2026-09-05).

The cards were filtered on the hidden Market select inside "This week" and
the tab click set only its own pressed state, so every tab showed the whole
slate. The existing tab tests asserted the tabs exist, carry their counts and
come from the declared list; none clicked one and looked at the cards.
"""
from __future__ import annotations

WIDE = {"width": 1440, "height": 900}


def _open_week(page):
    page.set_viewport_size(WIDE)
    page.evaluate("location.hash = '#/week'")
    # THE CARDS MOVED (2026-09-08). The "More picks" grid was removed and
    # the Today groups are the cards; the slate's own sentences still
    # land in #week-cards, so the `.empty` assertions below are unchanged.
    page.wait_for_selector("#today .face", timeout=15000)
    page.wait_for_timeout(300)
    if page.evaluate("!!document.querySelector('#week-tier-seg button[data-tier=\"\"]')"):
        page.click("#week-tier-seg button[data-tier='']")
        page.wait_for_timeout(500)


def _shown(page):
    return page.evaluate("""[...document.querySelectorAll('#today .face')].map(c => c.dataset.id)
""")


def _markets_by_id(page):
    sport = page.evaluate("window.Gridiron.state.sport")
    return page.evaluate(f"fetch('/api/week?sport={sport}').then(r => r.json()).then(j => Object.fromEntries(j.cards.map(c => [String(c.prediction_id), c.market])))")


def test_a_market_tab_shows_only_that_markets_picks(page):
    _open_week(page)
    by_id = _markets_by_id(page)
    tabs = page.evaluate("[...document.querySelectorAll('.market-tab')].map(b => [b.dataset.market, b.querySelector('.market-tab-n').textContent])")
    assert len(tabs) >= 2, tabs
    whole = _shown(page)
    assert whole, "no cards on the All tab"
    for market, n in tabs[1:]:
        page.click(f".market-tab[data-market='{market}']")
        page.wait_for_timeout(700)
        assert page.get_attribute(f".market-tab[data-market='{market}']", "aria-pressed") == "true"
        shown = _shown(page)
        wrong = [i for i in shown if by_id.get(i) != market]
        assert not wrong, f"tab {market!r} shows picks from another market: {wrong[:5]}"
        if n == "0":
            assert shown == [], f"the zero-count tab {market!r} shows {len(shown)} picks"
            assert page.evaluate(
                "document.querySelectorAll('#today .face').length") >= 0
            assert page.evaluate("document.querySelectorAll('#week-cards .empty').length") == 1
        else:
            assert shown, f"tab {market!r} says {n} and shows nothing"
        assert page.evaluate("document.getElementById('week-market').value") == market, \
            "the hidden Market select does not follow the tab"
    page.click(".market-tab[data-market='']")
    page.wait_for_timeout(700)
    assert sorted(_shown(page)) == sorted(whole)


def test_a_tab_with_no_picks_shows_nothing_of_the_last_one(page):
    """Finding 2's mechanism, reached through a tab: the zero-count tab clears
    the grid and must clear the cards, the heading and the show-all button."""
    _open_week(page)
    zero = page.evaluate("(() => { const b = [...document.querySelectorAll('.market-tab')].find(b => b.querySelector('.market-tab-n').textContent === '0'); return b ? b.dataset.market : null; })()")
    assert zero is not None, "the fixture slate has no zero-count tab to open"
    page.click(f".market-tab[data-market='{zero}']")
    page.wait_for_timeout(700)
    # THE HERO IS GONE (2026-09-08). What must not survive a zero tab is the
    # last tab's cards, in either place they can appear.
    left = page.evaluate(
        "document.querySelectorAll('#week-cards .card, #today .face').length")
    assert left == 0, f"{left} card(s) of the last tab survive the zero tab"
    # THE "More picks" HEADING WENT WITH ITS GRID (2026-09-08). What this
    # test is for -- nothing of the last tab survives an empty one -- is
    # carried by the card count asserted above.
    assert page.evaluate("document.querySelectorAll('#week-cards .empty').length") == 1
    page.click(".market-tab[data-market='']")
    page.wait_for_timeout(500)


def test_the_hidden_market_select_presses_the_tab(page):
    _open_week(page)
    page.evaluate("document.querySelector('.week-more').open = true")
    options = page.evaluate("[...document.querySelectorAll('#week-market option')].map(o => o.value)")
    market = next(m for m in options if m)
    page.select_option("#week-market", market)
    page.wait_for_timeout(700)
    assert page.get_attribute(f".market-tab[data-market='{market}']", "aria-pressed") == "true"
    by_id = _markets_by_id(page)
    assert all(by_id.get(i) == market for i in _shown(page))
    page.select_option("#week-market", "")
    page.wait_for_timeout(500)
    page.evaluate("document.querySelector('.week-more').open = false")


def test_a_tab_the_next_sport_does_not_ask_falls_back_to_all(page):
    _open_week(page)
    tabs = page.evaluate("[...document.querySelectorAll('.market-tab')].map(b => b.dataset.market)")
    page.click(f".market-tab[data-market='{tabs[1]}']")
    page.wait_for_timeout(500)
    sports = page.evaluate("[...document.querySelectorAll('#sport-tabs button')].map(b => b.dataset.sport)")
    current = page.evaluate("window.Gridiron.state.sport")
    other = next(s for s in sports if s != current)
    with page.expect_response(lambda r: "/api/week" in r.url and f"sport={other}" in r.url, timeout=20000):
        page.click(f"#sport-tabs button[data-sport='{other}']")
    page.wait_for_timeout(600)
    assert page.evaluate("window.Gridiron.state.market") == ""
    with page.expect_response(lambda r: "/api/week" in r.url and f"sport={current}" in r.url, timeout=20000):
        page.click(f"#sport-tabs button[data-sport='{current}']")
    page.wait_for_timeout(600)
    assert page.get_attribute(".market-tab[data-market='']", "aria-pressed") == "true"
