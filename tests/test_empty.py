"""An empty slate leaves nothing of the previous one (UI audit finding 2,
2026-09-05).

The empty branch of `renderWeek` returned before it touched the hero, the
grid heading or the show-all button, so a sport with no forecasts opened on
the previous sport's lead. The tests that covered the empty state asserted the
message was present and stopped there; these assert that nothing else is.
"""
from __future__ import annotations

WIDE = {"width": 1440, "height": 900}


def _open_week(page):
    page.set_viewport_size(WIDE)
    page.evaluate("location.hash = '#/week'")
    page.wait_for_selector("#week-cards .card, #week-cards .empty", timeout=15000)
    page.wait_for_timeout(300)


def _nothing_but_the_message(page, where):
    # THE HERO IS GONE (2026-09-08). What the empty branch must still leave
    # behind is nothing of the last sport's slate: no cards, and no group
    # headings standing over an empty list.
    left = page.evaluate("document.querySelectorAll('#today .face, #week-cards .card').length")
    assert left == 0, f"{where}: {left} card(s) of the last sport survive"
    assert page.evaluate("document.getElementById('week-grid-heading').hidden") is True, f"{where}: the 'More picks' heading survives"
    assert page.evaluate("document.getElementById('week-showall').hidden") is True, f"{where}: the show-all button survives"
    assert page.evaluate("document.querySelectorAll('#week-cards .card').length") == 0, f"{where}: cards survive"
    assert page.evaluate("document.querySelectorAll('#week-cards .empty').length") == 1, f"{where}: no single message"
    # the swipe and the arrows have nothing to step through
    page.evaluate("""() => { const h = document.getElementById('today'); const r = h.getBoundingClientRect();
        const t = (type, x) => h.dispatchEvent(new TouchEvent(type, {bubbles: true, changedTouches: [new Touch({identifier: 1, target: h, clientX: x, clientY: 10})]}));
        t('touchstart', 200); t('touchend', 40); }""")
    page.wait_for_timeout(200)
    assert page.evaluate("document.querySelectorAll('#today .face').length") == 0, \
        f"{where}: a swipe brought the last sport's cards back"


def test_a_sport_with_no_forecasts_starts_no_live_poll(page):
    """UI audit finding 25 (2026-09-06, found in the re-drive): an empty
    payload has no week, and the live poll asked /api/live?week=null every
    minute and was refused with a 422 on every NBA visit."""
    _open_week(page)
    sports = page.evaluate("[...document.querySelectorAll('#sport-tabs button')].map(b => b.dataset.sport)")
    counts = {sp: page.evaluate(f"fetch('/api/week?sport={sp}').then(r => r.json()).then(j => (j.cards || []).length)") for sp in sports}
    empty = next(sp for sp, n in counts.items() if n == 0)
    seen = []
    page.on("response", lambda r: seen.append((r.status, r.url)) if "/api/live" in r.url or r.status >= 400 else None)
    with page.expect_response(lambda r: "/api/week" in r.url and f"sport={empty}" in r.url, timeout=20000):
        page.click(f"#sport-tabs button[data-sport='{empty}']")
    page.wait_for_timeout(2500)
    assert not seen, f"an empty slate asked the live endpoint or was refused: {seen[:3]}"


def test_a_sport_with_no_forecasts_shows_nothing_of_the_last_one(page):
    _open_week(page)
    full = page.evaluate("window.Gridiron.state.sport")
    assert page.evaluate("document.querySelectorAll('#today .face').length") > 0, \
        "the full sport has no cards to leave behind"
    sports = page.evaluate("[...document.querySelectorAll('#sport-tabs button')].map(b => b.dataset.sport)")
    counts = {sp: page.evaluate(f"fetch('/api/week?sport={sp}').then(r => r.json()).then(j => (j.cards || []).length)") for sp in sports}
    empty = next(sp for sp, n in counts.items() if n == 0)
    with page.expect_response(lambda r: "/api/week" in r.url and f"sport={empty}" in r.url, timeout=20000):
        page.click(f"#sport-tabs button[data-sport='{empty}']")
    page.wait_for_selector("#week-cards .empty", timeout=15000)
    page.wait_for_timeout(400)
    _nothing_but_the_message(page, f"{empty} after {full}")
    with page.expect_response(lambda r: "/api/week" in r.url and f"sport={full}" in r.url, timeout=20000):
        page.click(f"#sport-tabs button[data-sport='{full}']")
    page.wait_for_selector("#week-cards .card", timeout=15000)
