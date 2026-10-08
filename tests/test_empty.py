"""An empty slate leaves nothing of the previous one (UI audit finding 2,
2026-09-05).

The empty branch of the slate renderer (`renderWeek` then, `renderGames`
since GRIDIRON_BOARD, 2026-09-24) returned before it touched the hero, the
grid heading or the show-all button, so a sport with no forecasts opened on
the previous sport's lead. The tests that covered the empty state asserted the
message was present and stopped there; these assert that nothing else is.
"""
from __future__ import annotations

from tests.conftest import requests_asked, wait_for_the_render, watch_the_answers

WIDE = {"width": 1440, "height": 900}


def _open_week(page):
    page.set_viewport_size(WIDE)
    # THE HASH'S OWN RENDER, SAID LANDED (operator question 5, 2026-10-08):
    # this waited 300ms after the first row appeared, which the render before
    # the hash change may already have drawn.
    with wait_for_the_render(page, "games"):
        page.evaluate("location.hash = '#/games'")
    page.wait_for_selector("#games-rows .game, #games-notes .empty", timeout=15000)


def _nothing_but_the_message(page, where):
    # THE HERO IS GONE (2026-09-08). What the empty branch must still leave
    # behind is nothing of the last sport's slate: no cards, and no group
    # headings standing over an empty list.
    left = page.evaluate("document.querySelectorAll('#games-rows .game, #games-rows .game').length")
    assert left == 0, f"{where}: {left} card(s) of the last sport survive"
    # THE GRID'S OWN CHROME WENT WITH THE GRID (2026-09-08): the "More picks"
    # heading and the show-all button. The assertions that carry this test's
    # promise -- no cards from the last slate, exactly one message -- are
    # above and below this line and are unchanged.
    assert page.evaluate("document.querySelectorAll('#games-rows .game').length") == 0, f"{where}: cards survive"
    assert page.evaluate("document.querySelectorAll('#games-notes .empty').length") == 1, f"{where}: no single message"
    # the swipe and the arrows have nothing to step through
    asked = page.evaluate("window.Gridiron.rendersAsked()")
    page.evaluate("""() => { const h = document.getElementById('games-rows'); const r = h.getBoundingClientRect();
        const t = (type, x) => h.dispatchEvent(new TouchEvent(type, {bubbles: true, changedTouches: [new Touch({identifier: 1, target: h, clientX: x, clientY: 10})]}));
        t('touchstart', 200); t('touchend', 40); }""")
    # NOTHING ASKED, SO NOTHING TO WAIT FOR (operator question 5, 2026-10-08):
    # this waited 200ms for whatever a swipe might start. A touch is handled
    # as it is dispatched, and the page's count of renders asked moves the
    # moment one is asked, so a swipe that asked none can bring nothing back.
    assert page.evaluate("window.Gridiron.rendersAsked()") == asked, \
        f"{where}: a swipe asked the page to draw the slate again"
    assert page.evaluate("document.querySelectorAll('#games-rows .game').length") == 0, \
        f"{where}: a swipe brought the last sport's cards back"


def test_a_sport_with_no_forecasts_starts_no_live_poll(page):
    """UI audit finding 25 (2026-09-06, found in the re-drive): an empty
    payload has no week, and the live poll asked /api/live?week=null every
    minute and was refused with a 422 on every NBA visit."""
    _open_week(page)
    sports = page.evaluate("[...document.querySelectorAll('#sport-tabs button')].map(b => b.dataset.sport)")
    counts = {sp: page.evaluate(f"fetch('/api/week?sport={sp}').then(r => r.json()).then(j => (j.cards || []).length)") for sp in sports}
    empty = next(sp for sp, n in counts.items() if n == 0)
    # WHAT THE PAGE ASKED, READ INSIDE IT (operator question 5, 2026-10-08):
    # this listened 2.5s for a live request or a refusal. The slate's render
    # starts its live poll before it says it has landed, and the poll's first
    # tick asks at once, so once the empty sport's slate has landed the page's
    # own list holds every request the switch made and every answer it read.
    watch_the_answers(page)
    with wait_for_the_render(page, "games"):
        page.click(f"#sport-tabs button[data-sport='{empty}']")
    assert page.evaluate("window.Gridiron.state.sport") == empty
    refused = [(status, url) for url, status
               in page.evaluate("window.__theAnswers.answered") if status >= 400]
    seen = requests_asked(page, "/api/live") + refused
    assert not seen, f"an empty slate asked the live endpoint or was refused: {seen[:3]}"


def test_a_sport_with_no_forecasts_shows_nothing_of_the_last_one(page):
    _open_week(page)
    full = page.evaluate("window.Gridiron.state.sport")
    assert page.evaluate("document.querySelectorAll('#games-rows .game').length") > 0, \
        "the full sport has no cards to leave behind"
    sports = page.evaluate("[...document.querySelectorAll('#sport-tabs button')].map(b => b.dataset.sport)")
    counts = {sp: page.evaluate(f"fetch('/api/week?sport={sp}').then(r => r.json()).then(j => (j.cards || []).length)") for sp in sports}
    empty = next(sp for sp, n in counts.items() if n == 0)
    # THE SWITCH'S OWN SLATE, SAID LANDED (operator question 5, 2026-10-08):
    # this waited 400ms after the empty message appeared.
    with wait_for_the_render(page, "games"):
        page.click(f"#sport-tabs button[data-sport='{empty}']")
    page.wait_for_selector("#games-notes .empty", timeout=15000)
    _nothing_but_the_message(page, f"{empty} after {full}")
    with wait_for_the_render(page, "games"):
        page.click(f"#sport-tabs button[data-sport='{full}']")
    page.wait_for_selector("#games-rows .game", timeout=15000)
