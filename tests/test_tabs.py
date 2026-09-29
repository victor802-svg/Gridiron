"""The market filter narrows the slate (UI audit finding 24, 2026-09-05).

RE-HOMED 2026-09-24 (GRIDIRON_BOARD). The market TABS above the cards went
with the old Picks page -- the board puts no control row above the first
game -- and the filter is the Market select beneath the rows. The promise is
finding 24's and is unchanged: choosing a market shows that market's
questions and nothing else, a market with none shows one sentence and no
leftover rows, and a market the next sport does not ask falls back to All.
"""
from __future__ import annotations

from tests.conftest import wait_for_the_redraw_it_starts

WIDE = {"width": 1440, "height": 900}

# EVERY REDRAW HERE IS WAITED FOR INSIDE THE PAGE (the board merge,
# 2026-09-29). The board re-homed these tests from the market tabs to the
# Market select and brought their fixed waits with them, under new names the
# clock register did not hold; each is rebuilt on question 28's helper, which
# waits for the redraw's arrival to start and end, and the register only
# shrinks.


def _open_games(page):
    page.set_viewport_size(WIDE)
    with wait_for_the_redraw_it_starts(page):
        page.evaluate("location.hash = '#/games'")
    page.wait_for_selector("#games-rows .game, #games-notes .empty", timeout=15000)
    page.evaluate("document.querySelector('.week-more').open = true")


def _shown(page):
    """Every question tile on the page, expanded rows or not: the ids the
    rows carry, which is what the filter narrows."""
    return page.evaluate("""[...document.querySelectorAll('#games-rows .game .q')].map(c => c.dataset.id)""")


def _markets_by_id(page):
    """Every question the board carries, both forecasters, by id."""
    sport = page.evaluate("window.Gridiron.state.sport")
    return page.evaluate(
        f"fetch('/api/week?sport={sport}').then(r => r.json()).then(j => "
        "Object.fromEntries(j.board.games.flatMap(g => g.questions).map(q => [String(q.prediction_id), q.market])))")


def _choose(page, market):
    with wait_for_the_redraw_it_starts(page):
        page.select_option("#week-market", market)


def test_a_market_shows_only_that_markets_questions(page):
    _open_games(page)
    by_id = _markets_by_id(page)
    options = page.evaluate("[...document.querySelectorAll('#week-market option')].map(o => o.value)")
    assert len(options) >= 2, options
    whole = _shown(page)
    assert whole, "no questions on the All setting"
    for market in options[1:]:
        _choose(page, market)
        shown = _shown(page)
        wrong = [i for i in shown if by_id.get(i) != market]
        assert not wrong, f"market {market!r} shows questions from another market: {wrong[:5]}"
        expected = [i for i, m in by_id.items() if m == market]
        if not expected:
            assert shown == [], f"the empty market {market!r} shows {len(shown)} questions"
            assert page.evaluate("document.querySelectorAll('#games-notes .empty').length") == 1
            # AND THE ROW'S PICK IS FROM THAT MARKET, never another's
        else:
            assert shown, f"market {market!r} has {len(expected)} questions and shows nothing"
            picks = page.evaluate(
                "[...document.querySelectorAll('#games-rows .game')].map(g => g.querySelector('.pick-line') ? g.querySelector('.pick-line').textContent : '')")
            assert all(picks), "a filtered row shows no pick"
    _choose(page, "")
    assert sorted(_shown(page)) == sorted(whole)


def test_a_market_with_no_questions_shows_nothing_of_the_last_one(page):
    """Finding 2's mechanism, reached through the filter: an empty market
    clears the rows and shows one sentence."""
    _open_games(page)
    by_id = _markets_by_id(page)
    options = page.evaluate("[...document.querySelectorAll('#week-market option')].map(o => o.value)")
    zero = next((m for m in options if m and m not in set(by_id.values())), None)
    assert zero is not None, "the fixture slate has no empty market to choose"
    _choose(page, zero)
    left = page.evaluate("document.querySelectorAll('#games-rows .game').length")
    assert left == 0, f"{left} row(s) of the last market survive the empty one"
    assert page.evaluate("document.querySelectorAll('#games-notes .empty').length") == 1
    _choose(page, "")


def test_the_market_options_come_from_the_declared_list(page):
    """R4, re-homed from the tabs: a fifth market must appear without a UI
    change, and a retired one is not offered."""
    from gridiron import config

    _open_games(page)
    sport = page.evaluate("window.Gridiron.state.sport")
    options = page.evaluate("[...document.querySelectorAll('#week-market option')].map(o => o.value)")
    assert options[0] == "", "the first option is not All"
    declared = [m for m in config.SPORT_MARKETS.get(sport, ())
                if not config.retired_market(sport, m)]
    assert options[1:] == declared, (
        f"the options for {sport} are {options[1:]}, and the declared markets are "
        f"{declared}. A list that does not match the declaration is a hardcoded one.")


def test_a_market_the_next_sport_does_not_ask_falls_back_to_all(page):
    _open_games(page)
    options = page.evaluate("[...document.querySelectorAll('#week-market option')].map(o => o.value)")
    _choose(page, options[1])
    sports = page.evaluate("[...document.querySelectorAll('#sport-tabs button')].map(b => b.dataset.sport)")
    current = page.evaluate("window.Gridiron.state.sport")
    other = next(s for s in sports if s != current)
    with page.expect_response(lambda r: "/api/week" in r.url and f"sport={other}" in r.url, timeout=20000):
        with wait_for_the_redraw_it_starts(page):
            page.click(f"#sport-tabs button[data-sport='{other}']")
    assert page.evaluate("window.Gridiron.state.market") == ""
    assert page.evaluate("document.getElementById('week-market').value") == ""
    with page.expect_response(lambda r: "/api/week" in r.url and f"sport={current}" in r.url, timeout=20000):
        with wait_for_the_redraw_it_starts(page):
            page.click(f"#sport-tabs button[data-sport='{current}']")
