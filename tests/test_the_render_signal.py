"""The page says when a render it started has landed (operator question 5,
ruled (A) on 2026-09-27, second set: "After the merge: the app emits a
render-finished signal, every fixed wait is rebuilt on it, on a
held-and-released response or on page.clock; upper-limit timeouts stay. Its
own step, with renders."; built 2026-10-08).

ONE EVENT, `gridiron:rendered`, on the document, once a render the page
started has landed -- its DOM written and its arrival ended -- naming the
view, the panel and the render's count (its place in the order the page
asked for renders). Every view and every redraw says so; a live tick, a
render a later one superseded, and an answer that failed never do; and it
carries no number the page draws.

Two halves. The page's script is read by `audit.render_signal_faults` --
the gate's check and the plantings' -- for a render that never says so, says
so before it lands, or says so on a live tick. The page itself is driven
here in Chromium: every view and every redraw the browser world can show, the
signal's moment, a superseded render and a live tick.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from gridiron import audit, config
from tests.conftest import (RENDER_SIGNAL, REDRAW_LIMIT_MS, VIEW_PANELS,
                            wait_for_the_render, wait_until_read,
                            watch_the_answers)

REPO = Path(__file__).resolve().parents[1]
WIDE = {"width": 1300, "height": 900}


def _js() -> str:
    return (config.PACKAGE_ROOT / "web" / "app.js").read_text(encoding="utf-8")


def _named(faults, *words) -> bool:
    return any(all(w in f for w in words) for f in faults)


# --- the script, read --------------------------------------------------------

def test_every_render_of_the_shipped_page_says_when_it_has_landed():
    assert audit.render_signal_faults() == []
    audit.check_every_render_says_it_landed()


def test_every_view_of_the_page_is_a_render_that_says_so():
    views = set(re.findall(r"^\s+(\w+): render\w+", _js().split("const ROUTES = {")[1]
                           .split("}")[0], re.M))
    assert views == set(VIEW_PANELS), views
    said = {v for v in audit.RENDERS_THAT_SAY_THEY_LANDED.values() if v}
    assert views <= said, views - said


def test_a_render_that_never_says_it_landed_is_named():
    """A view whose redraw lands with no signal (planting (e), its static
    half): the call taken out of Results' render, the count taken out of the
    Settings render, and a new view routed to a render in no register."""
    js = _js()
    said = "    rendered(asked, 'results', 'history-table');\n"
    assert js.count(said) == 1
    faults = audit.render_signal_faults(js.replace(said, ""))
    assert _named(faults, "`renderResults` renders and never says it has landed"), faults

    asked = ("  async function renderSettings() {\n"
             "    // ITS COUNT, TAKEN BEFORE IT ASKS (operator question 5, 2026-10-08).\n"
             "    const asked = renderAsked();\n")
    assert js.count(asked) == 1
    faults = audit.render_signal_faults(js.replace(
        asked, "  async function renderSettings() {\n    const asked = 0;\n"))
    assert _named(faults, "`renderSettings` never takes its count"), faults

    routes = "  const ROUTES = {\n"
    about = ("  async function renderAbout() {\n"
             "    const data = await fetchJSON('/api/meta');\n"
             "    document.getElementById('view-about').textContent = data.colophon || '';\n"
             "  }\n\n")
    faults = audit.render_signal_faults(
        js.replace(routes, about + routes + "    about: renderAbout,\n", 1))
    assert _named(faults, "`renderAbout` draws from an answer it asks for"), faults
    assert _named(faults, "the 'about' view renders by `renderAbout`"), faults


#: A FRAME'S CALL, built so that this file's own strings hold none: the scan
#: of the clock reads every string a test hands anything for a reading of the
#: page frame by frame (question 5's prover, 2026-10-08), and these are
#: app.js's own lines, handed only to the audit.
_A_FRAME = "requestAnimation" + "Frame"


def test_a_signal_before_its_render_lands_is_named():
    """The signal emitted before its render lands (planting (e), its static
    half): dispatched at once, said before the answer is awaited, said about
    a panel other than the one that arrives, said before the Record page's
    parts, and said on a live tick."""
    js = _js()
    forms = {
        "at once": (
            f"    {_A_FRAME}(settle);\n  }}\n  // --- the yesterday strip",
            "    document.dispatchEvent(new CustomEvent(RENDERED,\n"
            "      { detail: { view: view, panel: what, count: count } }));\n"
            f"    {_A_FRAME}(settle);\n  }}\n  // --- the yesterday strip",
            ("`rendered` dispatches the signal at once",)),
        "before its answer": (
            "    const asked = renderAsked();\n    // THE OLD ROWS ARE STALE",
            "    const asked = renderAsked();\n    rendered(asked, 'games', rows);\n"
            "    // THE OLD ROWS ARE STALE",
            ("`renderGames` says it has landed before the last answer",)),
        "about another panel": (
            "    rendered(asked, 'games', rows);\n  }",
            "    rendered(asked, 'games', notes);\n  }",
            ("`renderGames` arrives `rows` and says ['notes'] landed",)),
        "before the Record page's parts": (
            "    await Promise.all(parts);\n",
            "    rendered(asked, 'record', 'view-record');\n    await Promise.all(parts);\n",
            ("`renderRecord` says it has landed before the last answer",)),
        "on a live tick": (
            "      put('.game-clock', pick.clock_line);\n",
            "      put('.game-clock', pick.clock_line);\n"
            "      rendered(renderAsked(), 'games', 'games-rows');\n",
            ("`applyLive` says a render landed on a live tick",)),
    }
    for name, (anchor, planted, wanted) in forms.items():
        assert js.count(anchor) == 1, (name, js.count(anchor))
        faults = audit.render_signal_faults(js.replace(anchor, planted))
        for w in wanted:
            assert _named(faults, w), (name, w, faults)


#: `rendered`'s first test, as first built (question 5's prover, 2026-10-08):
#: the panel's own arrival class alone.
_SETTLE_AS_FIRST_BUILT = "      if (panel && panel.classList.contains('arriving')) {\n"
_SETTLE_AS_SHIPPED = ("      if (panel && (panel.classList.contains('arriving')\n"
                      "                    || panel.querySelector('.arriving, .filling'))) {\n")


def test_a_start_state_the_signal_does_not_wait_for_is_named():
    """A START STATE -- a class the page puts on what it draws and takes off a
    frame later -- is read off the script, and `rendered` must read each
    inside what it drew before it dispatches (question 5's prover,
    2026-10-08). As first built it read the panel's own arrival class alone,
    so the probability bar's `filling` went unread: the static half of the
    browser test below."""
    js = _js()
    assert audit._js_start_states(js) == {"arriving": "arrive", "filling": "probBar"}
    assert js.count(_SETTLE_AS_SHIPPED) == 1
    faults = audit.render_signal_faults(js.replace(_SETTLE_AS_SHIPPED, _SETTLE_AS_FIRST_BUILT))
    assert _named(faults, "without reading the `filling` start state", "`probBar`"), faults
    assert _named(faults, "without reading the `arriving` start state", "`arrive`"), faults
    # A START STATE ADDED LATER is read off the script too, and named until
    # `rendered` waits for it.
    routes = "  const ROUTES = {\n"
    dimmed = ("  function dimIn(node) {\n"
              "    node.classList.add('dimming');\n"
              f"    {_A_FRAME}(() => node.classList.remove('dimming'));\n"
              "  }\n\n")
    faults = audit.render_signal_faults(js.replace(routes, dimmed + routes, 1))
    assert _named(faults, "the `dimming` start state", "`dimIn`"), faults
    assert not _named(faults, "the `filling` start state"), faults


def test_the_signal_carries_the_view_the_panel_and_the_count_and_nothing_else():
    js = _js()
    detail = "{ detail: { view: view, panel: what, count: count } }"
    assert js.count(detail) == 1
    faults = audit.render_signal_faults(js.replace(
        detail, "{ detail: { view: view, panel: what, count: count, rows: panel.children.length } }"))
    assert _named(faults, "the signal carries ['view', 'panel', 'count', 'rows']"), faults


def test_a_register_naming_what_the_page_no_longer_has_is_named(monkeypatch):
    monkeypatch.setitem(audit.RENDERS_THAT_SAY_THEY_LANDED, "renderTheOldWeek", "games")
    monkeypatch.setitem(audit.RENDER_SIGNAL_EXEMPT, "loadTheOldTabs", "a reason with no date")
    faults = audit.render_signal_faults()
    assert _named(faults, "`renderTheOldWeek` is in audit.RENDERS_THAT_SAY_THEY_LANDED and gone"), faults
    assert _named(faults, "`loadTheOldTabs` is exempt"), faults


def test_the_gate_makes_the_call():
    """Read from the gate's syntax tree, so a comment naming the check cannot
    stand in for the call (question 20's planting is pinned the same way)."""
    gate = REPO / "tools" / "verify.py"
    step = next(node for node in ast.parse(gate.read_text(encoding="utf-8")).body
                if isinstance(node, ast.FunctionDef) and node.name == "step_2_guards")
    assert any(isinstance(node, ast.Attribute)
               and node.attr == "check_every_render_says_it_landed"
               and isinstance(node.value, ast.Name) and node.value.id == "audit"
               for node in ast.walk(step))


# --- the page, driven -----------------------------------------------------------
#
# EVERY VIEW AND EVERY REDRAW THE BROWSER WORLD CAN SHOW. Each case opens its
# view (said landed), arms on the page's count, acts, and waits for the
# signal naming the view and the panel; a redraw that lands with no signal
# fails here BY ITS NAME. What this world cannot show -- a combo taken, a
# calendar day picked (its calendar holds no settled day), a payout saved
# (it would write the shared world) -- is held by the script's reading
# above: each is a render in its register or draws through one that is.

def _open(page, view):
    route = "#/" + view
    if page.evaluate("location.hash") != route:
        with wait_for_the_render(page, view):
            page.evaluate(f"location.hash = '{route}'")


def _another(page, selector):
    """A value of the select other than the one it holds."""
    values = page.evaluate(f"[...document.querySelectorAll('{selector} option')].map(o => o.value)")
    now = page.evaluate(f"document.querySelector('{selector}').value")
    other = next((v for v in values if v != now), None)
    assert other is not None, f"{selector} offers nothing to choose: {values}"
    return other


def _the_other_sport(page):
    return page.evaluate("""() => [...document.querySelectorAll('#sport-tabs button')]
        .map(b => b.dataset.sport).find(s => s !== document.querySelector(
            '#sport-tabs button[aria-current="true"]').dataset.sport)""")


def _a_family_chip(page):
    keys = page.evaluate("[...document.querySelectorAll('#props-chips .chip-btn')].map(b => b.dataset.key)")
    return next(k for k in keys if k and k != "ladder")


REDRAWS = {
    # name: (the view opened first, or None; the action; the signal's view and panel)
    "games, the hash": (None, lambda p: p.evaluate("location.hash = '#/games'"), "games", "games-rows"),
    "games, the week picker": (
        "games", lambda p: (p.evaluate("document.querySelector('.week-more').open = true"),
                            p.select_option("#week-picker", _another(p, "#week-picker"))),
        "games", "games-rows"),
    "games, the market filter": (
        "games", lambda p: p.select_option("#week-market", _another(p, "#week-market")),
        "games", "games-rows"),
    "games, the sort": ("games", lambda p: p.select_option("#games-sort", "edge"), "games", "games-rows"),
    "games, picks only": ("games", lambda p: p.check("#games-clears"), "games", "games-rows"),
    "games, a sport": (
        "games", lambda p: p.click(f"#sport-tabs button[data-sport='{_the_other_sport(p)}']"),
        "games", "games-rows"),
    "games, the greeting": (
        "games", lambda p: p.click(f"#sport-tabs button[data-sport='{_the_other_sport(p)}']"),
        "games", "greeting", ("games", "games-rows")),
    "games, a row opened": (
        "games", lambda p: p.locator("#games-rows .game .game-head").first.click(),
        "games", "game-more"),
    "props, the hash": (None, lambda p: p.evaluate("location.hash = '#/props'"), "props", "props-tiles"),
    "props, a chip": (
        "props", lambda p: p.click(f"#props-chips .chip-btn[data-key='{_a_family_chip(p)}']"),
        "props", "props-tiles"),
    "props, the sort": ("props", lambda p: p.select_option("#props-sort", "time"), "props", "props-tiles"),
    "props, the ladder": (
        "props", lambda p: p.click("#props-chips .chip-btn[data-key='ladder']"), "props", "props-tiles"),
    "props, the entry check's answer": (
        "props", lambda p: p.click("#entry-check"), "props", "entry-lines"),
    "props, the deposit match's answer": (
        "props", lambda p: p.click("#deposit-check"), "props", "deposit-lines"),
    # QUESTION 5'S PROVER (2026-10-08): a payout the settings door refuses
    # (one that pays back no more than it costs, ruling C) is drawn in its
    # row's own line, and nothing is written to the shared world.
    "props, a payout refused": (
        "props", lambda p: (p.fill("#payout-2", "1"),
                            p.click("#props-payouts .payout-save >> nth=0")),
        "props", "payout-said"),
    "record, the hash": (None, lambda p: p.evaluate("location.hash = '#/record'"), "record", "view-record"),
    "record, the chart's market": (
        "record", lambda p: p.select_option("#chart-market", _another(p, "#chart-market")),
        "record", "view-record"),
    "record, the chart's forecaster": (
        "record", lambda p: p.select_option("#chart-predictor", _another(p, "#chart-predictor")),
        "record", "view-record"),
    "record, the tier table's market": (
        "record", lambda p: p.select_option("#tier-market", _another(p, "#tier-market")),
        "record", "tier-table"),
    "record, the forecaster": (
        "record", lambda p: p.click("#forecaster-picker button[aria-pressed='false']"),
        "record", "tier-table"),
    "record, the factor search": (
        "record", lambda p: p.fill("#factors-search", "zzzz-no-such-factor"),
        "record", "factors-cards"),
    "results, the hash": (None, lambda p: p.evaluate("location.hash = '#/results'"), "results", "history-table"),
    "results, the forecaster filter": (
        "results", lambda p: p.select_option("#history-predictor", "statistical"),
        "results", "history-table"),
    "results, the outcome filter": (
        "results", lambda p: p.select_option("#history-outcome", "resolved"),
        "results", "history-table"),
    "results, the search": ("results", lambda p: p.fill("#history-q", "a"), "results", "history-table"),
    "results, a prompt opened": (
        "results", lambda p: p.locator("#history-table details.prompt-box summary").first.click(),
        "results", "prompt-box"),
    "settings, the hash": (None, lambda p: p.evaluate("location.hash = '#/settings'"),
                           "settings", "settings-sections"),
}


#: Every request of the page's own counted while in flight, from here on: a
#: case ends only when none is, so no request of it is left running on the
#: suite's shared server when its page closes (the lesson of question 46's
#: build, 2026-10-08: a sport switch's requests cut off at a test's end were
#: followed by a later module's failure).
_COUNT_IN_FLIGHT = """() => {
    if (window.__inFlight !== undefined) return;
    window.__inFlight = 0;
    const ask = window.fetch;
    window.fetch = function () {
        window.__inFlight += 1;
        return ask.apply(this, arguments).finally(() => { window.__inFlight -= 1; });
    };
}"""


@pytest.mark.parametrize("name", list(REDRAWS))
def test_every_view_and_every_redraw_says_it_has_landed(page, name):
    """A view whose redraw lands with no signal is named here (planting (e),
    the page's half)."""
    first, act, view, panel = REDRAWS[name][:4]
    # WHAT THE WHOLE REDRAW ENDS WITH, where the panel named is not its last
    # step (a sport switch draws its greeting first).
    last = REDRAWS[name][4] if len(REDRAWS[name]) > 4 else (view, panel)
    page.set_viewport_size(WIDE)
    page.evaluate(_COUNT_IN_FLIGHT)
    if first:
        _open(page, first)
    before = page.evaluate("window.Gridiron.rendersAsked()")
    try:
        with wait_for_the_render(page, *last):
            with wait_for_the_render(page, view, panel):
                act(page)
    except AssertionError as missed:
        asked = page.evaluate("window.Gridiron.rendersAsked()") - before
        raise AssertionError(
            f"{name}: the page asked for {asked} render(s) and never said the "
            f"{view} view's {panel} had landed (operator question 5: every view "
            f"and every redraw says so). {missed}") from None
    detail = page.evaluate("window.__theRender")
    assert detail["landed"] and min(detail["landed"]) > before, detail
    # NOTHING LEFT IN FLIGHT: a sport switch goes on past its greeting, and
    # the forecaster's prompt list past its table.
    page.wait_for_function("() => window.__inFlight === 0", timeout=REDRAW_LIMIT_MS)


def test_a_setting_saved_says_its_row_has_landed(page):
    """Settings' own redraw from an answer: a switch saved, then put back,
    each said landed (the shared world is left as it was)."""
    page.set_viewport_size(WIDE)
    _open(page, "settings")
    switch = "#settings-sections .set-switch >> nth=0"
    before = page.get_attribute(switch, "aria-pressed")
    try:
        with wait_for_the_render(page, "settings", "settings-row"):
            page.click(switch)
        assert page.get_attribute(switch, "aria-pressed") != before
    finally:
        if page.get_attribute(switch, "aria-pressed") != before:
            with wait_for_the_render(page, "settings", "settings-row"):
                page.click(switch)
    assert page.get_attribute(switch, "aria-pressed") == before


#: Heard inside the page from now on: for each signal, what the panel it
#: names looked like at that moment -- arriving, updating, transitions still
#: running -- read in the listener, in the same task as the dispatch.
_HEAR_EACH_SIGNAL = """(signal) => {
    window.__heard = [];
    document.addEventListener(signal, (event) => {
        const d = event.detail || {};
        const node = document.getElementById(d.panel);
        const running = node ? node.getAnimations({ subtree: true }).filter(a => {
            const t = a.effect && a.effect.getComputedTiming();
            return !t || t.iterations !== Infinity; }).length : null;
        window.__heard.push({ view: d.view, panel: d.panel, count: d.count,
            keys: Object.keys(d).sort(),
            arriving: node ? node.classList.contains('arriving') : null,
            updating: node ? node.classList.contains('updating') : null,
            running: running,
            rows: node ? node.children.length : null });
    });
}"""


def test_the_signal_comes_once_the_render_has_landed_and_carries_nothing_drawn(page):
    """At the moment of each signal the panel it names is drawn: not
    arriving, not dimmed for an answer still in flight, nothing still moving
    on it; and the detail is the view, the panel and the count, no number
    the page draws."""
    page.set_viewport_size(WIDE)
    page.evaluate(_HEAR_EACH_SIGNAL, RENDER_SIGNAL)
    _open(page, "games")
    with wait_for_the_render(page, "games"):
        page.select_option("#games-sort", "edge")
    _open(page, "props")
    with wait_for_the_render(page, "props"):
        page.click(f"#props-chips .chip-btn[data-key='{_a_family_chip(page)}']")
    heard = page.evaluate("window.__heard")
    drawn = [h for h in heard if h["panel"] in ("games-rows", "props-tiles")]
    assert len(drawn) >= 4, heard
    for h in drawn:
        assert h["keys"] == ["count", "panel", "view"], h
        assert not h["arriving"] and not h["updating"] and h["running"] == 0, h
    assert all(h["rows"] > 0 for h in drawn if h["panel"] == "games-rows"), drawn
    counts = [h["count"] for h in heard]
    assert all(isinstance(c, int) and c > 0 for c in counts), counts


def test_while_its_answer_is_held_a_render_says_nothing(page):
    """The slate's answer held: the page goes to Results, whose render lands
    and says so -- and the held slate has said nothing; released, it says so.
    A render that said it had landed before its answer would have spoken
    first: its signal is asked a frame after it starts, before any answer of
    the Results render can come back."""
    page.set_viewport_size(WIDE)
    _open(page, "games")
    page.evaluate(_HEAR_EACH_SIGNAL, RENDER_SIGNAL)
    held = []
    week = re.compile(r"/api/week(\?|$)")

    def hold_the_first(route):
        # THE SLATE'S OWN, AND NOTHING AFTER IT: Results asks for the slate
        # too, for its settled tiles.
        if held:
            route.continue_()
        else:
            held.append(route)

    page.route(week, hold_the_first)
    try:
        with wait_for_the_render(page, "games"):
            page.evaluate("() => { window.Gridiron.route(); }")
            page.wait_for_function(
                "document.getElementById('games-rows').classList.contains('updating')",
                timeout=REDRAW_LIMIT_MS)
            with wait_for_the_render(page, "results"):
                page.evaluate("location.hash = '#/results'")
            early = [h for h in page.evaluate("window.__heard") if h["view"] == "games"]
            assert early == [], f"the slate said it landed with its answer held: {early}"
            assert len(held) == 1
            for route in held:
                route.continue_()
            page.unroute(week)
    finally:
        page.unroute(week)
    late = [h for h in page.evaluate("window.__heard") if h["panel"] == "games-rows"]
    assert len(late) == 1, late


def test_a_render_a_later_one_superseded_says_nothing(page):
    """Two slates asked, the first answer held until the second has landed:
    the first is dropped (the page's `weekSeq`), and only the second says it
    landed -- by its own count."""
    page.set_viewport_size(WIDE)
    _open(page, "games")
    held = []
    week = re.compile(r"/api/week(\?|$)")

    def hold_the_first(route):
        if held:
            route.continue_()
        else:
            held.append(route)

    watch_the_answers(page)
    page.route(week, hold_the_first)
    try:
        armed = page.evaluate("window.Gridiron.rendersAsked()")
        with wait_for_the_render(page, "games"):
            page.evaluate("() => { window.Gridiron.route(); }")
            page.select_option("#games-sort", "edge")
        landed = page.evaluate("window.__theRender.landed")
        assert landed == [armed + 2], (armed, landed)
        page.evaluate(_HEAR_EACH_SIGNAL, RENDER_SIGNAL)
        for route in held:
            route.continue_()
        wait_until_read(page, "/api/week", count=2)
        assert page.evaluate("window.__heard") == [], "a superseded render said it landed"
        assert page.evaluate("window.Gridiron.rendersAsked()") == armed + 2
    finally:
        page.unroute(week)


#: Heard inside the page from now on: for each signal about the Games rows,
#: every probability bar showing inside them at that moment -- still at its
#: start (`filling`, opacity 0) or not -- read in the listener, in the same
#: task as the dispatch.
_HEAR_THE_BARS = """(signal) => {
    window.__bars = [];
    document.addEventListener(signal, (event) => {
        const d = event.detail || {};
        if (d.panel !== 'games-rows') return;
        const shown = [...document.querySelectorAll('#games-rows .pbar-fill')]
            .filter(f => f.offsetParent !== null);
        window.__bars.push({ count: d.count, shown: shown.length,
            filling: shown.filter(f => f.classList.contains('filling')).length,
            opacity: shown.map(f => getComputedStyle(f).opacity) });
    });
}"""


def test_the_rows_say_they_landed_only_once_no_bar_is_at_its_start(page):
    """THE SIGNAL BEFORE ITS RENDER LANDS, FOUND BY QUESTION 5'S PROVER
    (2026-10-08). A row the reader opened is drawn open again by the next
    redraw, its tiles' probability bars drawn at their start (`filling`,
    opacity 0) and cleared two frames later. Under reduced motion, on a slate
    of one game, nothing else runs for `rendered` to wait on, and as first
    built the rows said they had landed with the open row's bars still at
    opacity 0 (measured: four bars). The slate's answer is cut to its first
    game with questions in flight (fulfilled, never slept); at the moment the
    rows say they have landed every bar showing is drawn whole."""
    def one_game(route):
        response = route.fetch()
        payload = response.json()
        board = payload.get("board") or {}
        games = board.get("games") or []
        board["games"] = [g for g in games if g.get("questions")][:1] or games[:1]
        route.fulfill(response=response, json=payload)

    page.set_viewport_size(WIDE)
    page.emulate_media(reduced_motion="reduce")
    week = re.compile(r"/api/week(\?|$)")
    page.route(week, one_game)
    try:
        _open(page, "games")
        assert page.evaluate("document.querySelectorAll('#games-rows .game').length") == 1
        with wait_for_the_render(page, "games", "game-more"):
            page.locator("#games-rows .game .game-head").first.click()
        page.evaluate(_HEAR_THE_BARS, RENDER_SIGNAL)
        now = page.evaluate("document.getElementById('games-sort').value")
        with wait_for_the_render(page, "games"):
            page.select_option("#games-sort", "edge" if now != "edge" else "time")
        bars = page.evaluate("window.__bars")
        assert len(bars) == 1 and bars[0]["shown"] > 0, (
            f"the redraw drew no bar on the open row to read: {bars}")
        assert bars[0]["filling"] == 0 and set(bars[0]["opacity"]) == {"1"}, (
            f"THE ROWS SAID THEY HAD LANDED WITH {bars[0]['filling']} OF "
            f"{bars[0]['shown']} BARS STILL AT THEIR START (opacity "
            f"{bars[0]['opacity']}): the signal before its render lands")
    finally:
        page.unroute(week)
        page.emulate_media(reduced_motion="no-preference")


def test_a_live_tick_says_nothing(page):
    """The live tick patches scores in place and redraws nothing: once its
    answer is read the page has asked for no render and heard no signal
    after the slate's own (question 5's reading (a))."""
    def in_progress(route):
        response = route.fetch()
        payload = response.json()
        glance = payload.get("glance") or {}
        glance["state"] = "in_progress"
        payload["glance"] = glance
        route.fulfill(response=response, json=payload)

    page.set_viewport_size(WIDE)
    _open(page, "games")
    week = re.compile(r"/api/week(\?|$)")
    page.route(week, in_progress)
    page.route("**/api/live*", lambda route: route.fulfill(json={
        "picks": [], "games": [], "any_live": False}))
    watch_the_answers(page)
    try:
        with wait_for_the_render(page, "games"):
            page.evaluate("() => { window.Gridiron.route(); }")
        slate = page.evaluate("window.__theRender.landed[0]")
        page.evaluate(_HEAR_EACH_SIGNAL, RENDER_SIGNAL)
        wait_until_read(page, "/api/live")
        assert page.evaluate("window.Gridiron.rendersAsked()") == slate
        assert page.evaluate("window.__heard") == []
    finally:
        page.unroute(week)
        page.unroute("**/api/live*")
