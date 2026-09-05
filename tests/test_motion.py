"""Motion (R4, 2026-09-05): the tab switch arrives, the carousel swipes, the
movement bound holds, and reduced motion is the same layout with none."""
from __future__ import annotations

import pytest

from gridiron import audit, config

WIDE = {"width": 1440, "height": 900}


def _css():
    return (config.PACKAGE_ROOT / "web" / "style.css").read_text(encoding="utf-8")


# --- the guard, AT the boundary ----------------------------------------------

def test_the_shipped_stylesheet_is_inside_the_bound():
    assert audit.transform_faults(_css()) == []
    assert audit.motion_faults(_css()) == []


@pytest.mark.parametrize("probe, allowed", [
    ("translateY(2%)", True), ("translateY(-2%)", True), ("translateY(2.01%)", False),
    ("translateY(1%)", True), ("translateY(12px)", False), ("translateY(1em)", False),
    ("scale(1.02)", True), ("scale(0.98)", True), ("scale(1.021)", False),
    ("scale(1.1)", False), ("translateX(1%)", False), ("rotate(3deg)", False),
    ("none", True),
])
def test_the_movement_bound_is_held_at_the_boundary(probe, allowed):
    faults = audit.transform_faults(f".probe {{ transform: {probe}; }}")
    assert (faults == []) is allowed, (probe, faults)


def test_text_transform_is_not_a_transform():
    assert audit.transform_faults(".probe { text-transform: uppercase; }") == []


def test_a_duration_over_the_ceiling_is_named():
    faults = audit.motion_faults(".probe { transition: opacity 400ms ease-out; }")
    assert faults and "ceiling" in faults[0]


# --- the page ---------------------------------------------------------------------

def _open_week(page, size=WIDE):
    page.set_viewport_size(size)
    page.evaluate("location.hash = '#/record'")
    with page.expect_response(lambda r: "/api/week" in r.url):
        page.evaluate("location.hash = '#/week'")
    page.wait_for_selector("#week-market-tabs .market-tab", timeout=10000)


def test_a_tab_switch_arrives_through_the_motion_block(page):
    _open_week(page)
    props = page.evaluate("""() => {
        const cs = getComputedStyle(document.getElementById('week-cards'));
        return {duration: cs.transitionDuration, property: cs.transitionProperty,
                timing: cs.transitionTimingFunction};
    }""")
    assert props["duration"].startswith("0.2s"), props
    assert "opacity" in props["property"] and "transform" in props["property"]
    assert "ease-out" in props["timing"]
    # The class the transition runs from is applied on the switch, and comes
    # off a frame later; a MutationObserver installed before the click sees it.
    page.evaluate("""() => {
        window.__arrivals = [];
        const obs = new MutationObserver(list => list.forEach(m => {
            if (m.target.classList.contains('arriving')) window.__arrivals.push(m.target.id);
        }));
        for (const id of ['week-cards', 'week-hero']) {
            obs.observe(document.getElementById(id), {attributes: true, attributeFilter: ['class']});
        }
    }""")
    tabs = page.evaluate("[...document.querySelectorAll('.market-tab')].map(b => b.dataset.market)")
    target = next((t for t in tabs if t), tabs[0])
    # AND THE FADE ACTUALLY RUNS: a sampler started by the same observer reads
    # the grid's opacity every frame for a quarter second, and at least one
    # frame must sit strictly between zero and one. The first version of this
    # test checked only that the class toggled, and passed while the start
    # state animated towards zero and was reversed a frame later.
    page.evaluate("""() => {
        window.__opacity = [];
        const el = document.getElementById('week-cards');
        const obs = new MutationObserver(() => {
            obs.disconnect();
            const t0 = performance.now();
            const tick = () => {
                window.__opacity.push(parseFloat(getComputedStyle(el).opacity));
                if (performance.now() - t0 < 260) requestAnimationFrame(tick);
            };
            requestAnimationFrame(tick);
        });
        obs.observe(el, {attributes: true, attributeFilter: ['class']});
    }""")
    page.click(f".market-tab[data-market='{target}']")
    page.wait_for_function("window.__arrivals.length > 0", timeout=5000)
    page.wait_for_timeout(400)
    assert "week-cards" in page.evaluate("window.__arrivals")
    assert page.evaluate(
        "document.getElementById('week-cards').classList.contains('arriving')") is False
    samples = page.evaluate("window.__opacity")
    assert any(0 < s < 1 for s in samples), f"the grid never faded: {samples}"
    assert samples[-1] == 1


def test_reduced_motion_is_the_same_layout_with_no_transition(page):
    _open_week(page)
    # After the arrival has finished: measured a frame into it, the grid sits
    # one per cent below its place and the comparison reads a 3px lie.
    page.wait_for_timeout(350)
    boxes = "[...document.querySelectorAll('#week-hero, #week-cards, .market-tab')].map(e => { const r = e.getBoundingClientRect(); return [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)]; })"
    before = page.evaluate(boxes)
    page.emulate_media(reduced_motion="reduce")
    page.wait_for_timeout(100)
    after = page.evaluate(boxes)
    assert after == before, "reduced motion changed the layout"
    duration = page.evaluate(
        "getComputedStyle(document.getElementById('week-cards')).transitionDuration")
    assert duration == "0s", duration
    page.emulate_media(reduced_motion="no-preference")


def test_the_carousel_keeps_its_dots_and_arrows_and_steps_on_a_swipe(served, _browser):
    """A touch context of its own: `phone` lives in test_smoke, not conftest."""
    from tests.conftest import SMOKE_TOKEN

    context = _browser.new_context(viewport={"width": 390, "height": 844},
                                   device_scale_factor=3, is_mobile=True, has_touch=True)
    phone = context.new_page()
    phone.goto(served + "/login", wait_until="networkidle")
    phone.fill("#token", SMOKE_TOKEN)
    phone.click("#submit")
    phone.wait_for_url(served + "/", timeout=15000)
    phone.wait_for_function("document.body.dataset.ready === 'true'", timeout=15000)
    phone.evaluate("location.hash = '#/week'")
    phone.wait_for_selector("#week-hero:not([hidden])", timeout=10000)
    dots = phone.evaluate("document.querySelectorAll('.hero-dot').length")
    arrows = phone.evaluate("document.querySelectorAll('.hero-arrow').length")
    if dots < 2:
        pytest.skip("fewer than two picks on this slate to step through")
    assert arrows == 2
    first = phone.evaluate("document.querySelector('.hero-game').textContent")
    phone.evaluate("""() => {
        const host = document.getElementById('week-hero');
        const touch = (x) => new Touch({identifier: 1, target: host, clientX: x, clientY: 200});
        host.dispatchEvent(new TouchEvent('touchstart', {changedTouches: [touch(300)], bubbles: true}));
        host.dispatchEvent(new TouchEvent('touchend', {changedTouches: [touch(120)], bubbles: true}));
    }""")
    phone.wait_for_timeout(250)
    second = phone.evaluate("document.querySelector('.hero-game').textContent")
    assert second != first, "a swipe left did not step the hero"
    on = phone.evaluate("document.querySelectorAll('.hero-dot.on').length")
    assert on == 1
    context.close()
