"""Motion (R4, 2026-09-05): the tab switch arrives, the carousel swipes, the
movement bound holds, and reduced motion is the same layout with none."""
from __future__ import annotations

import pytest

from gridiron import audit, config
from tests.conftest import wait_for_the_render

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

def _open_props(page, size=WIDE):
    """RE-HOMED 2026-09-24 (GRIDIRON_BOARD): the market tabs went with the
    old Picks page; the Props chips are the control that swaps a panel's
    whole contents now, and the tiles are what arrive."""
    page.set_viewport_size(size)
    page.evaluate("location.hash = '#/record'")
    # THE TILES' OWN RENDER, SAID LANDED, ITS ARRIVAL ENDED (operator
    # question 5, 2026-10-08): this waited for the answer and the first chip,
    # which the render draws in the frame it begins to arrive.
    with wait_for_the_render(page, "props"):
        page.evaluate("location.hash = '#/props'")
    page.wait_for_selector("#props-chips .chip-btn", timeout=10000)


def test_a_chip_switch_arrives_through_the_motion_block(page):
    _open_props(page)
    props = page.evaluate("""() => {
        const cs = getComputedStyle(document.getElementById('props-tiles'));
        return {duration: cs.transitionDuration, property: cs.transitionProperty,
                timing: cs.transitionTimingFunction};
    }""")
    assert props["duration"].startswith("0.2s"), props
    # OPACITY ALONE from 2026-09-27 (operator question 20, (A)): the panel
    # holds tap targets, and a movement put them off whole pixels.
    assert props["property"] == "opacity", props
    assert "ease-out" in props["timing"]
    # The class the transition runs from is applied on the switch, and comes
    # off a frame later; a MutationObserver installed before the click sees it.
    page.evaluate("""() => {
        window.__arrivals = [];
        const obs = new MutationObserver(list => list.forEach(m => {
            if (m.target.classList.contains('arriving')) window.__arrivals.push(m.target.id);
        }));
        for (const id of ['games-rows', 'props-tiles']) {
            obs.observe(document.getElementById(id), {attributes: true, attributeFilter: ['class']});
        }
    }""")
    keys = page.evaluate("[...document.querySelectorAll('#props-chips .chip-btn')].map(b => b.dataset.key)")
    # A FAMILY CHIP: not the Kalshi ladder view, which took the empty "Alt
    # lines" chip's place (operator ruling C, 2026-10-05).
    target = next((k for k in keys if k and k != 'ladder'), keys[0])
    # AND THE FADE ACTUALLY RUNS, READ OFF THE FADE ITSELF (question 5's
    # prover, 2026-10-08). Until then a sampler read the grid's opacity on
    # every frame and asked that one frame sit strictly between zero and one
    # -- which a frame does inside a 200ms fade only if frames come less than
    # 200ms apart: with the document's timeline run fast (what a renderer
    # stalled for 200ms looks like to a sampler) it read [0, 1] and this went
    # red on a page that fades. The panel's own opacity transition is caught
    # the moment the arrival class comes off, read at half its duration and
    # played on (`_CATCH_THE_FADE`): the same reading however long a frame
    # takes. The render's own signal says when the arrival has ended.
    page.evaluate(_CATCH_THE_FADE)
    with wait_for_the_render(page, "props"):
        page.click(f"#props-chips .chip-btn[data-key='{target}']")
    page.wait_for_function("window.__arrivals.length > 0", timeout=5000)
    assert "props-tiles" in page.evaluate("window.__arrivals")
    assert page.evaluate(
        "document.getElementById('props-tiles').classList.contains('arriving')") is False
    fade = page.evaluate("window.__fade")
    assert fade and fade["found"], f"no opacity transition ran as the grid arrived: {fade}"
    assert fade["start"] == "0" and fade["keyframes"] == ["0", "1"], fade
    assert 0 < float(fade["half"]) < 1, f"the panel never faded: {fade}"
    assert page.evaluate(
        "getComputedStyle(document.getElementById('props-tiles')).opacity") == "1"


#: THE GRID'S OWN FADE, CAUGHT AS IT BEGINS (question 5's prover, 2026-10-08):
#: installed before the switch, it sees the arrival class go on and, the
#: moment it comes off, takes the opacity transition that starts on the grid,
#: reads where it starts and its keyframes, pauses it, reads the grid at half
#: its duration, puts it back where it was and plays it on. Nothing here
#: depends on how many frames land inside the fade, or when.
_CATCH_THE_FADE = """() => {
    window.__fade = null;
    const el = document.getElementById('props-tiles');
    let on = false;
    const obs = new MutationObserver(() => {
        if (el.classList.contains('arriving')) { on = true; return; }
        if (!on) return;
        obs.disconnect();
        const fade = el.getAnimations().find(a => a.transitionProperty === 'opacity');
        if (!fade) { window.__fade = { found: false }; return; }
        const timing = fade.effect.getComputedTiming();
        const start = getComputedStyle(el).opacity;
        fade.pause();
        const back = fade.currentTime;
        fade.currentTime = timing.duration / 2;
        const half = getComputedStyle(el).opacity;
        fade.currentTime = back === null ? 0 : back;
        fade.play();
        window.__fade = { found: true, duration: timing.duration, start: start,
                          keyframes: fade.effect.getKeyframes().map(k => String(k.opacity)),
                          half: half };
    });
    obs.observe(el, {attributes: true, attributeFilter: ['class']});
}"""


def test_the_fade_is_read_the_same_however_long_a_frame_takes(page):
    """THE READING DOES NOT RIDE ON THE CLOCK (question 5's prover,
    2026-10-08; schema ruling 5: "No test in the gate may depend on elapsed
    real time"). The grid's fade is read on two chip switches: one on the
    document's own timeline, and one with the timeline run a thousand times
    fast through the DevTools protocol (`Animation.setPlaybackRate`), so the
    200ms fade ends inside a single frame -- what a renderer stalled for
    200ms looks like to anything that reads by frames. The sampler this
    replaced read [0, 1] there and went red (measured: scratchpad
    q5/prover/probe_fade_tree.txt); the fade caught as it begins reads the
    same at both speeds, strictly between zero and one."""
    _open_props(page)
    keys = page.evaluate("[...document.querySelectorAll('#props-chips .chip-btn')].map(b => b.dataset.key)")
    families = [k for k in keys if k and k != "ladder"]
    assert families, keys
    read = {}
    cdp = page.context.new_cdp_session(page)
    try:
        cdp.send("Animation.enable")
        for rate, key in ((1, families[0]), (1000, "")):
            cdp.send("Animation.setPlaybackRate", {"playbackRate": rate})
            page.evaluate(_CATCH_THE_FADE)
            with wait_for_the_render(page, "props"):
                page.click(f"#props-chips .chip-btn[data-key='{key}']")
            read[rate] = page.evaluate("window.__fade")
    finally:
        cdp.send("Animation.setPlaybackRate", {"playbackRate": 1})
        cdp.detach()
    assert read[1] and read[1]["found"] and read[1000] and read[1000]["found"], read
    assert 0 < float(read[1]["half"]) < 1, read
    assert read[1000]["half"] == read[1]["half"], (
        f"the fade read differently when frames came slower than it: {read}")


def test_reduced_motion_is_the_same_layout_with_no_transition(page):
    # After the arrival has finished: measured a frame into it, the grid sat
    # one per cent below its place and the comparison read a 3px lie. THE
    # TILES' OWN RENDER, SAID LANDED, its arrival ended (`_open_props`,
    # operator question 5, 2026-10-08): this waited 350ms after the chips
    # appeared.
    _open_props(page)
    boxes = "[...document.querySelectorAll('#props-tiles, #props-chips .chip-btn, #entry-rail')].map(e => { const r = e.getBoundingClientRect(); return [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)]; })"
    before = page.evaluate(boxes)
    page.emulate_media(reduced_motion="reduce")
    # THE PAGE READS REDUCED MOTION BEFORE IT IS MEASURED (operator question
    # 5, 2026-10-08): this waited 100ms. The media query answering is the
    # event; the measurement below lays the page out under it.
    page.wait_for_function(
        "() => matchMedia('(prefers-reduced-motion: reduce)').matches", timeout=5000)
    after = page.evaluate(boxes)
    assert after == before, "reduced motion changed the layout"
    duration = page.evaluate(
        "getComputedStyle(document.getElementById('props-tiles')).transitionDuration")
    assert duration == "0s", duration
    page.emulate_media(reduced_motion="no-preference")


# `test_the_carousel_keeps_its_dots_and_arrows_and_steps_on_a_swipe` was
# removed with the carousel on 2026-09-08. It checked that a swipe stepped the
# hero and that the dots followed. There is no hero and no carousel: every
# card is the same size and the page scrolls.

