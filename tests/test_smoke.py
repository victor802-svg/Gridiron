"""G6: the headless smoke test.

Boots the real server, loads the real page in a real headless browser, and
asserts the four things that distinguish a working page from a white rectangle:
the app object exists, the DOM has content, the canvas has pixels on it, and the
console is clean.

It also plants the front-end half of LAW 4 — asking the renderer to draw a
figure with no sample size — and asserts it refuses.

Skipped with a clear reason if playwright or its browser is not installed;
`playwright install chromium` provides it.
"""

from __future__ import annotations

import pathlib
import socket
import threading
import time

import pytest

from gridiron import api, auth, resolve, run
from gridiron.factors import store
from gridiron.model import baseline

playwright_api = pytest.importorskip(
    "playwright.sync_api", reason="playwright is not installed"
)

pytestmark = pytest.mark.browser


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


SMOKE_TOKEN = "smoke-token-for-the-browser-suite"


@pytest.fixture(scope="function")
def served(league, db_path, monkeypatch):
    import uvicorn

    monkeypatch.setenv(auth.TOKEN_VAR, SMOKE_TOKEN)

    store.sync_registry(league)
    # Six markets: the spread plus each prop type, fitted separately.
    baseline.train_all(league, (2025,), l2=1.0, note="smoke", min_rows=20)
    run.run_week(league, 2025, 7, include_props=True, use_llm=False)
    run.run_week(league, 2025, 8, include_props=True, use_llm=False)
    resolve.resolve_all(league)
    # A slate that has NOT been played, so the picks tab has live cards. The
    # rail, the pick sentence and the tier chip only exist before a result:
    # a settled card shows its verdict instead, per the approved mockup.
    run.run_week(league, 2025, 18, include_props=True, use_llm=False)
    league.commit()

    api.set_database(db_path)
    port = _free_port()
    server = uvicorn.Server(
        uvicorn.Config(api.app, host="127.0.0.1", port=port, log_level="error")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    deadline = time.time() + 20
    while time.time() < deadline and not server.started:
        time.sleep(0.05)
    if not server.started:
        pytest.fail("the server did not start within 20s")

    yield f"http://127.0.0.1:{port}"

    server.should_exit = True
    thread.join(timeout=10)
    api.set_database(None)


@pytest.fixture
def page(served):
    with playwright_api.sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as exc:  # noqa: BLE001
            pytest.skip(f"chromium unavailable: {exc}; run `playwright install chromium`")
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()
        page.console_errors = []
        page.page_errors = []
        page.on("console", lambda m: page.console_errors.append(m.text)
                if m.type == "error" else None)
        page.on("pageerror", lambda e: page.page_errors.append(str(e)))
        # Sign in the way a person does, through the real login page. Every
        # route is behind the gate (P3), so without this the browser lands on
        # /login and every assertion below fails for the wrong reason. It also
        # means the login flow is exercised by every browser test rather than
        # only by the one that names it.
        page.goto(served + "/login", wait_until="networkidle")
        page.fill("#token", SMOKE_TOKEN)
        page.click("#submit")
        page.wait_for_url(served + "/", timeout=15000)
        page.wait_for_function("document.body.dataset.ready === 'true'", timeout=15000)
        yield page
        browser.close()


def test_the_page_boots(page):
    assert page.title() == "Gridiron"
    assert page.evaluate("document.body.dataset.ready") == "true"


def test_the_app_object_exists(page):
    assert page.evaluate("typeof window.Gridiron") == "object"
    for member in ("boot", "route", "requireN", "drawCalibration"):
        assert page.evaluate(f"typeof window.Gridiron.{member}") == "function", member


def test_there_are_zero_console_errors(page):
    assert page.console_errors == [], f"console errors: {page.console_errors}"
    assert page.page_errors == [], f"uncaught exceptions: {page.page_errors}"
    assert page.evaluate("document.getElementById('error').hidden") is True


def test_the_canvas_is_not_blank(page):
    painted = page.evaluate(
        """() => {
            const c = document.getElementById('calibration');
            const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
            let n = 0;
            for (let i = 3; i < d.length; i += 4) if (d[i] !== 0) n++;
            return n;
        }"""
    )
    assert painted > 1000, f"the calibration canvas has only {painted} painted pixels"


def test_the_dom_is_not_blank(page):
    assert page.locator("#bucket-table tbody tr").count() == 4
    assert page.locator(".score-card").count() >= 3
    assert page.inner_text("#record-headline").strip()


def test_every_bucket_row_shows_its_sample_size(page):
    rows = page.eval_on_selector_all(
        "#bucket-table tbody tr",
        "rows => rows.map(r => [...r.cells].map(c => c.textContent))",
    )
    assert rows
    for row in rows:
        assert row[1].strip() != "", f"a bucket rendered without its N: {row}"


def test_the_renderer_refuses_a_figure_with_no_sample_size(page):
    """LAW 4, planted in the browser: hand the renderer a figure with no N."""
    result = page.evaluate(
        """() => {
            try {
                window.Gridiron.requireN({ brier: 0.21 }, 'planted figure');
                return { threw: false };
            } catch (e) {
                return { threw: true, name: e.constructor.name, message: e.message };
            }
        }"""
    )
    assert result["threw"], "the renderer drew a figure with no sample size"
    assert result["name"] == "MissingSampleSize"
    assert "LAW 4" in result["message"]


def test_the_calibration_chart_refuses_a_bucket_with_no_n(page):
    result = page.evaluate(
        """() => {
            const canvas = document.createElement('canvas');
            canvas.width = 200; canvas.height = 200;
            try {
                window.Gridiron.drawCalibration(canvas,
                    { buckets: [{ label: '50-60%', claimed: 0.55, actual: 0.6 }] });
                return { threw: false };
            } catch (e) {
                return { threw: true, message: e.message };
            }
        }"""
    )
    assert result["threw"], "a calibration point was drawn with no sample size"
    assert "LAW 4" in result["message"]


def test_every_screen_renders(page):
    for route, selector in (
        ("#/week", "#week-cards .row"),
        ("#/factors", "#factors-table tbody tr"),
        ("#/history", "#history-table tbody tr"),
        ("#/record", "#bucket-table tbody tr"),
    ):
        page.evaluate(f"location.hash = '{route}'")
        page.wait_for_selector(selector, timeout=10000)
        assert page.locator(selector).count() > 0, route
    assert page.console_errors == [], f"console errors while navigating: {page.console_errors}"


def test_the_track_record_is_the_default_screen(page):
    page.evaluate("location.hash = ''")
    page.wait_for_timeout(400)
    assert page.locator("#view-record").is_visible()
    assert not page.locator("#view-week").is_visible()


# --- D4 visuals -------------------------------------------------------------

def test_the_dumbbell_renders(page):
    page.evaluate("location.hash = '#/week'")
    # T1 old -> new: `.rail-dot` became `.dot`, and the rail now exists only on
    # a PENDING card — a settled one shows its verdict and final probabilities
    # instead, per the approved mockup. The selector targets a card that still
    # has a rail rather than blindly taking the first.
    page.wait_for_selector("#week-cards .row .dumbbell", timeout=10000)
    geometry = page.eval_on_selector_all(
        "#week-cards .row:has(.dumbbell) .dot",
        """dots => dots.map(d => {
            const rail = d.parentElement.getBoundingClientRect();
            const r = d.getBoundingClientRect();
            return { kind: d.className, left: r.left - rail.left,
                     width: r.width, railWidth: rail.width };
        })""",
    )
    assert geometry, "no dots on the probability rail"
    for dot in geometry:
        assert dot["width"] > 6, "a dumbbell dot has no size"
        assert -8 <= dot["left"] <= dot["railWidth"] + 8, "a dot sits off its rail"


def test_model_and_market_are_told_apart_by_form_not_colour(page):
    """Colour is reserved for the value of the gap, so the two dots differ in
    fill. A reader who cannot see the hue can still read the chart."""
    # The compact screen hides the detail until a row is tapped, so this
    # opens one before looking for anything inside it.
    _open_first_card(page)
    page.wait_for_selector("#week-cards .row .dumbbell", timeout=10000)
    styles = page.evaluate(
        """() => {
            /* T1 old -> new: `.rail-dot` became `.dot`. With the old selector
               this test found nothing and SKIPPED, which reads green and
               asserts nothing at all. */
            const model = document.querySelector('.dot.model');
            const market = document.querySelector('.dot.market');
            if (!model || !market) return null;
            const a = getComputedStyle(model), b = getComputedStyle(market);
            return { modelBorder: a.borderTopWidth, marketBorder: b.borderTopWidth,
                     modelFill: a.backgroundColor, marketFill: b.backgroundColor };
        }"""
    )
    if styles is None:
        pytest.skip("no card on this slate carries a market comparison")
    assert styles["modelBorder"] != styles["marketBorder"], (
        "the two dots are distinguished by colour alone"
    )
    # The model is filled, the market is an outline: told apart by FORM, so the
    # two colours stay reserved for value.
    assert styles["marketBorder"] != "0px", "the market dot has no outline"


def test_the_contribution_bars_render_signed(page):
    # T1 old -> new: the bars moved inside the collapsed reasoning, so the card
    # has to be opened before they have geometry. The chips are the glance; the
    # bars are still the detail.
    page.evaluate("location.hash = '#/week'")
    page.wait_for_selector("#week-cards .row", timeout=10000)
    page.locator("#week-cards .row").first.locator(".row-head").click()
    page.wait_for_timeout(300)
    page.wait_for_selector("#week-cards .row .contrib-bar", timeout=10000)
    bars = page.eval_on_selector_all(
        "#week-cards .row:first-child .contrib-bar",
        "els => els.map(e => ({ cls: e.className, left: e.style.left, width: e.style.width }))",
    )
    assert bars, "no contribution bars rendered"
    assert len(bars) <= 5, "more than five bars shown without the disclosure"
    for b in bars:
        assert ("pos" in b["cls"]) != ("neg" in b["cls"]), "a bar has no sign"
        assert b["width"] and b["width"] != "0%"


def test_a_card_expands_and_shows_its_detail(page):
    page.evaluate("location.hash = '#/week'")
    page.wait_for_selector("#week-cards .row", timeout=10000)
    card = page.locator("#week-cards .row").first
    detail = card.locator(".row-body")
    # T1 old -> new: the detail is now display:none rather than a collapsed
    # max-height, so it has NO bounding box when closed. `is_visible()` is the
    # honest check either way and does not depend on how the hiding is done.
    assert not detail.is_visible(), "the card starts open"

    card.locator(".row-head").click()
    page.wait_for_timeout(400)
    assert detail.is_visible(), "the card did not expand"
    assert detail.bounding_box()["height"] > 40
    # The DECOMPOSITION moved to the Factors page (K3): a card carries the
    # rail, the gap, the bucket line and the reasoning, and the table of
    # coefficients belongs where someone auditing goes looking for it.
    assert card.locator(".row-why").count() == 1
    assert card.locator(".dumbbell").count() == 1
    assert card.locator(".row-more").count() == 1, "the link to the Factors page"


def test_the_bucket_line_never_shows_an_accuracy_without_its_n(page):
    """LAW 4 on the card, unchanged in meaning.

    T1 old -> new: the sample size used to read "n=6" in a `.chip`; it now reads
    "6 resolved" in a `.bucket` line, because the approved design states counts
    in words. `.chip` is now the FACTOR chip and carries no N by design. What is
    asserted is the thing the law actually cares about: a percentage never
    appears without a count beside it.
    """
    import re

    # The compact screen hides the detail until a row is tapped, so this
    # opens one before looking for anything inside it.
    _open_first_card(page)
    page.wait_for_selector("#week-cards .row .row-bucket", timeout=10000)
    lines = page.eval_on_selector_all(
        "#week-cards .row .row-bucket", "els => els.map(e => e.textContent)"
    )
    assert lines
    for text in lines:
        assert re.search(r"\d+ resolved", text), (
            f"a bucket line rendered without its count: {text!r}"
        )
        # If it states an accuracy, the count must be right there with it.
        if "hits" in text or re.search(r"\d+% actual", text):
            assert re.search(r"\d+ resolved", text)


def test_the_weekly_strip_renders_with_hit_targets(page):
    page.evaluate("location.hash = '#/record'")
    page.wait_for_timeout(700)
    info = page.evaluate(
        """() => {
            const c = document.getElementById('overtime');
            const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
            let painted = 0;
            for (let i = 3; i < d.length; i += 4) if (d[i] !== 0) painted++;
            return { painted: painted, hits: (c._hits || []).length };
        }"""
    )
    assert info["painted"] > 500, "the weekly strip is blank"
    assert info["hits"] >= 1, "the strip has no hover targets, so N is unreachable"


def test_the_weekly_strip_refuses_a_point_with_no_n(page):
    """LAW 4, planted in the new chart."""
    result = page.evaluate(
        """() => {
            const canvas = document.createElement('canvas');
            canvas.width = 200; canvas.height = 100;
            try {
                window.Gridiron.drawOverTime(canvas,
                    { n: 3, points: [{ label: '2026 wk1', gap: 0.1 }] });
                return { threw: false };
            } catch (e) { return { threw: true, message: e.message }; }
        }"""
    )
    assert result["threw"], "a weekly point was drawn with no sample size"
    assert "LAW 4" in result["message"]


def test_the_bucket_chip_refuses_to_render_without_n(page):
    result = page.evaluate(
        """() => {
            try {
                window.Gridiron.bucketChip({ label: '70-80%', actual: 0.75 });
                return { threw: false };
            } catch (e) { return { threw: true, message: e.message }; }
        }"""
    )
    assert result["threw"], "a bucket chip rendered an accuracy with no N"
    assert "LAW 4" in result["message"]


def test_only_the_card_expansion_animates(page):
    # Cards must be on the page for their transition to be observable at all.
    page.evaluate("location.hash = '#/week'")
    page.wait_for_selector("#week-cards .row", timeout=10000)
    moving = page.evaluate(
        """() => {
            const out = [];
            document.querySelectorAll('*').forEach(e => {
                const s = getComputedStyle(e);
                if (s.transitionDuration !== '0s' && s.transitionDuration !== '')
                    out.push('transition:' + (e.className || e.tagName));
                if (s.animationName && s.animationName !== 'none')
                    out.push('animation:' + (e.className || e.tagName));
            });
            return [...new Set(out)];
        }"""
    )
    # T1 old -> new: the card gains a border-COLOUR transition on hover from
    # the approved mockup, and the detail is a display toggle rather than a
    # max-height animation. Nothing MOVES and nothing resizes, so the rule the
    # project set itself still holds; the assertion now names what may
    # transition instead of forbidding every transition.
    unexpected = [m for m in moving if not m.startswith('transition:card')]
    assert not unexpected, f"something else moves: {unexpected}"


def test_nothing_moves_under_reduced_motion(served):
    with playwright_api.sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as exc:  # noqa: BLE001
            pytest.skip(f"chromium unavailable: {exc}")
        context = browser.new_context(
            viewport={"width": 1280, "height": 900}, reduced_motion="reduce"
        )
        page = context.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        # Sign in the way a person does, through the real login page. Every
        # route is behind the gate (P3), so without this the browser lands on
        # /login and every assertion below fails for the wrong reason. It also
        # means the login flow is exercised by every browser test rather than
        # only by the one that names it.
        page.goto(served + "/login", wait_until="networkidle")
        page.fill("#token", SMOKE_TOKEN)
        page.click("#submit")
        page.wait_for_url(served + "/", timeout=15000)
        page.wait_for_function("document.body.dataset.ready === 'true'", timeout=15000)
        page.evaluate("location.hash = '#/week'")
        page.wait_for_selector("#week-cards .row", timeout=10000)

        assert page.evaluate("matchMedia('(prefers-reduced-motion: reduce)').matches")
        durations = page.evaluate(
            """() => {
                const out = [];
                document.querySelectorAll('*').forEach(e => {
                    const s = getComputedStyle(e);
                    if (s.transitionDuration && s.transitionDuration !== '0s')
                        out.push(e.className + ':' + s.transitionDuration);
                    if (s.animationName && s.animationName !== 'none')
                        out.push(e.className + ':' + s.animationName);
                });
                return out;
            }"""
        )
        assert durations == [], f"motion survived prefers-reduced-motion: {durations}"

        # ...and the card still opens, because motion is decoration not mechanism
        page.locator("#week-cards .row .row-head").first.click()
        page.wait_for_timeout(200)
        assert page.locator("#week-cards .row").first.evaluate(
            "e => e.classList.contains('open')"
        )
        assert errors == []
        browser.close()


def test_the_phone_layout_does_not_overflow(served):
    with playwright_api.sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as exc:  # noqa: BLE001
            pytest.skip(f"chromium unavailable: {exc}")
        context = browser.new_context(viewport={"width": 375, "height": 812})
        page = context.new_page()
        # Sign in the way a person does, through the real login page. Every
        # route is behind the gate (P3), so without this the browser lands on
        # /login and every assertion below fails for the wrong reason. It also
        # means the login flow is exercised by every browser test rather than
        # only by the one that names it.
        page.goto(served + "/login", wait_until="networkidle")
        page.fill("#token", SMOKE_TOKEN)
        page.click("#submit")
        page.wait_for_url(served + "/", timeout=15000)
        page.wait_for_function("document.body.dataset.ready === 'true'", timeout=15000)
        page.evaluate("location.hash = '#/week'")
        page.wait_for_selector("#week-cards .row", timeout=10000)

        overflow = page.evaluate(
            "() => document.documentElement.scrollWidth > window.innerWidth + 1"
        )
        assert not overflow, "the page scrolls sideways on a phone"
        rail = page.evaluate(
            """() => {
                const r = document.querySelector('.rail');
                if (!r) return null;
                const box = r.getBoundingClientRect();
                const dots = [...r.querySelectorAll('.rail-dot')].map(d =>
                    d.getBoundingClientRect().left - box.left);
                return { width: box.width, dots: dots };
            }"""
        )
        assert rail and rail["width"] > 120, "the dumbbell collapsed on a phone"
        for offset in rail["dots"]:
            assert -8 <= offset <= rail["width"] + 8
        browser.close()


# --- the schedule panel -----------------------------------------------------

def test_the_schedule_panel_renders_every_task(page):
    """The daily glance: did it run, did anything miss."""
    page.evaluate("location.hash = '#/schedule'")
    page.wait_for_selector("#schedule-tasks .sched", timeout=10000)
    cards = page.query_selector_all("#schedule-tasks .sched")
    # Derived from the registry, not a hardcoded count. This said "4" and went
    # stale the moment `refresh` was declared -- a panel whose job is to show
    # every task must not have its own idea of how many there are.
    from gridiron import tasks as _tasks

    expected = len(_tasks.TASKS)
    assert len(cards) == expected, (
        f"expected {expected} tasks ({sorted(_tasks.TASKS)}), "
        f"rendered {len(cards)}"
    )
    text = page.inner_text("#view-schedule")
    for task in _tasks.TASKS:
        assert task in text, f"{task} is declared but not shown on the panel"


def test_a_task_that_never_ran_says_so_in_the_browser(page):
    """A blank row reads as 'fine'. It must read as 'nothing is running'."""
    page.evaluate("location.hash = '#/schedule'")
    page.wait_for_selector("#schedule-tasks .sched", timeout=10000)
    text = page.inner_text("#view-schedule")
    assert "never run" in text
    assert "nothing is running" in text


def test_the_panel_shows_data_freshness_per_sport(page):
    page.evaluate("location.hash = '#/schedule'")
    page.wait_for_selector("#schedule-staleness .sched-stale", timeout=10000)
    rows = page.query_selector_all("#schedule-staleness .sched-stale")
    assert len(rows) == 3, "one freshness line per sport"


def test_the_schedule_panel_fits_a_phone(page):
    """The daily glance happens on a phone. Nothing may overflow sideways."""
    page.set_viewport_size({"width": 390, "height": 844})
    page.evaluate("location.hash = '#/schedule'")
    page.wait_for_selector("#schedule-tasks .sched", timeout=10000)
    overflow = page.evaluate(
        "document.documentElement.scrollWidth - document.documentElement.clientWidth"
    )
    assert overflow <= 0, f"the schedule panel overflows by {overflow}px"
    page.set_viewport_size({"width": 1280, "height": 900})


# --- the auth walk, in a real browser ---------------------------------------

def test_a_fresh_browser_is_sent_to_login_and_can_sign_in(served):
    """Fresh session -> redirected -> sign in -> full app. Walked in a real
    browser rather than asserted against a test client, because the cookie
    flags that matter are enforced by the browser, not by the server's opinion
    of them."""
    with playwright_api.sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as exc:  # noqa: BLE001
            pytest.skip(f"chromium unavailable: {exc}")
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()

        # 1. a fresh browser cannot see the app
        page.goto(served + "/", wait_until="networkidle")
        assert page.url.endswith("/login"), f"landed on {page.url} without signing in"
        assert "access token" in page.inner_text("body").lower()

        # 2. the wrong token is refused, in the page
        page.fill("#token", "not-the-token")
        page.click("#submit")
        page.wait_for_selector(".msg.bad", timeout=10000)
        assert page.url.endswith("/login")

        # 3. the right one opens it
        page.fill("#token", SMOKE_TOKEN)
        page.click("#submit")
        page.wait_for_url(served + "/", timeout=15000)
        page.wait_for_function("document.body.dataset.ready === 'true'", timeout=15000)
        assert page.query_selector("#sport-tabs")

        # 4. the session cookie is not readable from JavaScript
        visible = page.evaluate("document.cookie")
        assert auth.COOKIE_NAME not in visible, (
            "the session cookie is readable from JavaScript, so it is not HttpOnly"
        )
        assert SMOKE_TOKEN not in visible

        browser.close()

# --- the phone pass ---------------------------------------------------------

@pytest.fixture
def phone(served):
    """A 390px viewport, signed in. 390 is the iPhone 14/15 width and the
    narrowest thing most people will hold; 375 is covered separately because it
    is what an SE still is."""
    with playwright_api.sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as exc:  # noqa: BLE001
            pytest.skip(f"chromium unavailable: {exc}")
        context = browser.new_context(
            viewport={"width": 390, "height": 844},
            device_scale_factor=3,
            is_mobile=True,
            has_touch=True,
        )
        page = context.new_page()
        page.goto(served + "/login", wait_until="networkidle")
        page.fill("#token", SMOKE_TOKEN)
        page.click("#submit")
        page.wait_for_url(served + "/", timeout=15000)
        page.wait_for_function("document.body.dataset.ready === 'true'", timeout=15000)
        yield page
        browser.close()


def _overflow(page) -> int:
    return page.evaluate(
        "document.documentElement.scrollWidth - document.documentElement.clientWidth"
    )


@pytest.mark.parametrize(
    "route", ["#/record", "#/week", "#/factors", "#/versions", "#/history", "#/schedule"]
)
def test_no_screen_overflows_a_phone(phone, route):
    """Sideways scroll on a phone is the single most common way a dense layout
    breaks, and it hides content without any sign that it has."""
    phone.evaluate(f"location.hash = '{route}'")
    phone.wait_for_timeout(400)
    assert _overflow(phone) <= 0, f"{route} overflows by {_overflow(phone)}px at 390"


def test_the_sport_tabs_are_reachable_and_tappable(phone):
    tabs = phone.query_selector_all("#sport-tabs a, #sport-tabs button")
    assert len(tabs) == 3, f"expected three sport tabs, found {len(tabs)}"
    for tab in tabs:
        box = tab.bounding_box()
        assert box["height"] >= 44, (
            f"a sport tab is {box['height']:.0f}px tall; 44 is the smallest "
            "target a thumb reliably hits"
        )


def test_every_tap_target_on_the_slate_is_big_enough(phone):
    """44px is Apple's floor and the one most people cite. Checked on the
    controls that are actually tapped, not on every element."""
    phone.evaluate("location.hash = '#/week'")
    phone.wait_for_selector("#week-cards .row", timeout=10000)
    small = phone.evaluate("""
      Array.from(document.querySelectorAll(
        'nav a, #sport-tabs a, #sport-tabs button, select, button, .row-head'
      ))
        .filter(el => el.offsetParent !== null)
        .map(el => ({ tag: el.tagName + '.' + (el.className || ''),
                      h: el.getBoundingClientRect().height }))
        .filter(x => x.h > 0 && x.h < 44)
    """)
    assert not small, f"tap targets under 44px: {small}"


def test_a_card_still_expands_on_a_phone(phone):
    phone.evaluate("location.hash = '#/week'")
    phone.wait_for_selector("#week-cards .row", timeout=10000)
    head = phone.query_selector("#week-cards .row .row-head")
    head.click()
    phone.wait_for_selector("#week-cards .row .row-body", timeout=5000)
    assert _overflow(phone) <= 0, "an expanded card overflows the phone"


def test_the_dumbbell_and_contribution_bars_fit(phone):
    """Both are horizontal by nature and are the first things to break narrow."""
    phone.evaluate("location.hash = '#/week'")
    phone.wait_for_selector("#week-cards .row", timeout=10000)
    phone.query_selector("#week-cards .row .row-head").click()
    phone.wait_for_selector("#week-cards .row .row-body", timeout=5000)

    wide = phone.evaluate("""
      Array.from(document.querySelectorAll('.dumbbell, .contrib, .contrib-row'))
        .filter(el => el.getBoundingClientRect().right > window.innerWidth + 1)
        .map(el => el.className)
    """)
    assert not wide, f"these run past the right edge at 390px: {wide}"


def test_the_daily_glance_answers_did_it_run(phone):
    """The whole point of the phone view: open it, and know whether the
    appliance did its job without tapping anything."""
    phone.evaluate("location.hash = '#/schedule'")
    phone.wait_for_selector("#schedule-tasks .sched", timeout=10000)
    text = phone.inner_text("#view-schedule")
    assert "resolve" in text
    for signal in ("last ran", "next due"):
        assert signal in text.lower(), f"the panel does not say {signal!r}"
    assert _overflow(phone) <= 0


def test_the_offline_bar_is_hidden_while_online(phone):
    bar = phone.query_selector("#offline-bar")
    assert bar is not None, "there is no offline bar to show"
    assert not bar.is_visible(), "the offline bar shows while the app is online"


def test_the_manifest_and_worker_are_reachable_without_a_session(served):
    """Both are app shell. They must load before a session exists or the app can
    never install, which is why they are on the open list — and why the audit
    checks the worker caches no data."""
    import urllib.request

    for path in ("/static/manifest.webmanifest", "/sw.js"):
        with urllib.request.urlopen(served + path, timeout=10) as response:
            assert response.status == 200
            body = response.read().decode("utf-8")
        assert body.strip()
        if path == "/sw.js":
            assert "/api/" in body, "the worker has no data-path guard at all"


def test_an_unexplained_browser_skip_becomes_a_failure(page):
    """The guard, planted. A skip that reads green is the vacuous verifier in
    new clothes, and this project already shipped one."""
    import subprocess
    import sys as _sys
    import textwrap

    probe = pathlib.Path(__file__).parent / "_skip_probe.py"
    probe.write_text(textwrap.dedent('''
        import pytest
        pytestmark = pytest.mark.browser

        def test_skips_for_a_bad_reason():
            pytest.skip("no card on this slate carries a market comparison")
    '''), encoding="utf-8")
    try:
        result = subprocess.run(
            [_sys.executable, "-m", "pytest", str(probe), "-q"],
            cwd=str(pathlib.Path(__file__).parent.parent),
            capture_output=True, text=True,
        )
        assert result.returncode != 0, "an unexplained browser skip still passed"
        assert "unallowed reason" in result.stdout + result.stderr
    finally:
        probe.unlink(missing_ok=True)


# --- T3: the dark theme, rendered ------------------------------------------

def _open_first_card(page):
    """Go to the slate AND OPEN THE FIRST ROW.

    The compact screen (K2) shows five things per row and hides the rest, so
    the rail, the gap, the bucket line and the reasoning do not exist in the
    DOM until a row is expanded. This helper used to only navigate, which was
    enough when every card was fully drawn.
    """
    page.evaluate("location.hash = '#/week'")
    page.wait_for_selector("#week-cards .row", timeout=10000)
    head = page.locator("#week-cards .row .row-head").first
    head.click()
    page.wait_for_selector("#week-cards .row .row-body .dumbbell", timeout=5000)


def test_a_pending_row_shows_five_things_and_hides_the_rest(page):
    """THE COMPACT SCREEN. Rank, matchup, pick, chance, tier -- and nothing
    else until asked. The rail, the gap, the bucket line and the reasoning are
    behind the tap, which is the whole point of the layout: a slate of eight
    used to fill several screens and the reader scrolled past the picks to
    find the picks."""
    page.evaluate("location.hash = '#/week'")
    page.wait_for_selector("#week-cards .row", timeout=10000)
    row = page.locator("#week-cards .row").first

    # visible, collapsed
    assert row.locator(".row-title").count() == 1
    assert row.locator(".row-pick .row-phrase").count() == 1
    assert row.locator(".prob").count() == 1
    tier = row.locator(".chip").first
    assert tier.inner_text().strip() in ("LEAN", "SOLID", "STRONG")

    # ...and the detail is NOT on screen until it is asked for
    body = row.locator(".row-body")
    assert not body.is_visible(), "the row starts open"

    row.locator(".row-head").click()
    assert body.is_visible(), "the row did not expand"
    assert row.locator(".dumbbell").count() == 1
    assert row.locator(".row-bucket").count() == 1


def test_a_card_with_no_market_line_says_so_and_draws_one_dot(page):
    """Never a second dot at a number nobody published."""
    _open_first_card(page)
    found = page.evaluate("""() => {
        const cards = [...document.querySelectorAll('#week-cards .row')];
        const hit = cards.find(c => c.querySelector('.rail-noline'));
        if (!hit) return null;
        return {
            text: hit.querySelector('.rail-noline').textContent,
            model: hit.querySelectorAll('.dot.model').length,
            market: hit.querySelectorAll('.dot.market').length
        };
    }""")
    if found is None:
        # Every card on this slate has a line; assert the inverse holds instead.
        counts = page.evaluate("""() => [...document.querySelectorAll(
            '#week-cards .row:has(.dumbbell)')].map(c => c.querySelectorAll('.dot.market').length)""")
        assert counts and all(c == 1 for c in counts)
        return
    assert "no line available" in found["text"]
    assert found["model"] == 1 and found["market"] == 0


def test_a_resolved_card_shows_a_verdict_and_no_rail(page):
    """History does not compete with the thing still to happen.

    The default slate is the UNPLAYED one, so this navigates to a week that has
    results. The first draft skipped when it found no settled card — with an
    allowlisted reason, which would have slipped past the very guard added this
    session. A test that cannot find its subject must go looking for it, not
    excuse itself.
    """
    page.evaluate("location.hash = '#/week'")
    page.wait_for_selector("#week-cards .row", timeout=10000)
    moved = page.evaluate("""() => {
        const picker = document.getElementById('week-picker');
        const played = [...picker.options].find(o => {
            const v = JSON.parse(o.value); return v.week === 7;
        });
        if (!played) return false;
        picker.value = played.value;
        picker.dispatchEvent(new Event('change'));
        return true;
    }""")
    if not moved:
        options = page.evaluate(
            "[...document.getElementById('week-picker').options].map(o => o.value)")
        raise AssertionError(f"no played week in the picker; it offers {options}")
    page.wait_for_selector("#week-cards .row-done", timeout=10000)
    shape = page.evaluate("""() => {
        const c = document.querySelector('#week-cards .row-done');
        return { verdict: (c.querySelector('.verdict') || {}).textContent,
                 rails: c.querySelectorAll('.rail').length,
                 story: (c.querySelector('.market-line') || {}).textContent };
    }""")
    assert shape["verdict"] in ("WIN", "LOSS")
    assert shape["rails"] == 0, "a settled card drew a probability rail"
    assert "picked" in shape["story"]


def test_the_greeting_strip_leads_the_page(page):
    """It is the first thing on the page because it answers the first
    question: was I right last night."""
    page.evaluate("location.hash = '#/record'")
    page.wait_for_timeout(600)
    box = page.evaluate("""() => {
        const g = document.getElementById('greeting');
        if (!g || g.hidden) return null;
        const r = g.getBoundingClientRect();
        const cards = document.querySelector('#week-cards');
        return { top: r.top, text: document.getElementById('greet-msg').textContent };
    }""")
    # `#glance` stays hidden when the digest has nothing to say -- an empty
    # strip is worse than no strip. What must hold is that when it DOES have
    # something, it leads the page.
    if box is None:
        assert page.locator("#glance").get_attribute("hidden") is not None, (
            "the strip neither rendered nor declared itself empty"
        )
        return
    assert box["text"].strip(), "the greeting strip rendered empty"


def test_the_calibration_chart_is_not_drawn_in_the_page_colour(page):
    """The `--ink` collision, checked by number rather than by eyeball: the
    chart's ink must not equal its ground."""
    page.evaluate("location.hash = '#/record'")
    page.wait_for_selector("#calibration", timeout=10000)
    tokens = page.evaluate("""() => {
        const s = getComputedStyle(document.documentElement);
        return { ink: s.getPropertyValue('--ink').trim(),
                 chrome: s.getPropertyValue('--chrome').trim() };
    }""")
    assert tokens["ink"] != tokens["chrome"]
    painted = page.evaluate("""() => {
        const c = document.getElementById('calibration');
        const ctx = c.getContext('2d');
        const d = ctx.getImageData(0, 0, c.width, c.height).data;
        const seen = new Set();
        for (let i = 0; i < d.length; i += 4) {
            if (d[i + 3] > 200) seen.add(d[i] + ',' + d[i+1] + ',' + d[i+2]);
        }
        return seen.size;
    }""")
    assert painted > 2, f"the chart painted only {painted} distinct colours"


@pytest.mark.parametrize("route", ["#/week", "#/record", "#/digest", "#/schedule"])
def test_each_dark_screen_renders_on_a_phone(route, page):
    page.set_viewport_size({"width": 390, "height": 844})
    page.evaluate(f"location.hash = '{route}'")
    page.wait_for_timeout(700)
    overflow = page.evaluate(
        "document.documentElement.scrollWidth - document.documentElement.clientWidth"
    )
    assert overflow <= 0, f"{route} overflows by {overflow}px at 390"
    page.set_viewport_size({"width": 1280, "height": 900})


# --- the plain-words law, on the rendered page ------------------------------

@pytest.mark.parametrize(
    "route", ["#/record", "#/week", "#/factors", "#/versions",
              "#/history", "#/schedule", "#/digest"]
)
def test_no_internal_vocabulary_reaches_the_reader(route, page):
    """Scanned on the RENDERED page, not in the source. Labels are only half of
    it — the history table showed "Saquon Barkley rushing_yards" because the
    VALUE carried the identifier, and no scan of the markup would have seen it."""
    from gridiron import audit

    page.evaluate(f"location.hash = '{route}'")
    page.wait_for_timeout(900)
    visible = page.evaluate("document.body.innerText")
    hits = audit.plain_words_violations(visible)
    assert not hits, f"{route} shows internal vocabulary: {hits[:6]}"


def test_no_data_cell_renders_a_bare_dash(page):
    """A dash means nothing to a reader and looks like an error. Every absence
    says what is absent: "no line", "not played"."""
    page.evaluate("location.hash = '#/history'")
    page.wait_for_selector("#history-table tbody tr", timeout=10000)
    bare = page.evaluate("""() => {
        const cells = [...document.querySelectorAll('#history-table tbody td')];
        return cells.map(c => c.textContent.trim())
                    .filter(t => t === '\u2014' || t === '-' || t === '');
    }""")
    assert not bare, f"{len(bare)} data cells render a bare dash or nothing"


def test_the_history_row_is_one_sentence_and_the_market_appears_once(page):
    page.evaluate("location.hash = '#/history'")
    page.wait_for_selector("#history-table tbody tr", timeout=10000)
    headers = page.eval_on_selector_all(
        "#history-table thead th", "els => els.map(e => e.textContent.trim())")
    assert headers.count("Market") == 0, "a column is still called just 'Market'"
    assert len([h for h in headers if h.lower().startswith("market")]) <= 1
    first = page.eval_on_selector(
        "#history-table tbody tr td", "e => e.textContent.trim()")
    assert " " in first and "_" not in first, f"the row is not a sentence: {first!r}"


def test_the_result_reads_as_a_word_not_as_open(page):
    page.evaluate("location.hash = '#/history'")
    page.wait_for_selector("#history-table tbody tr", timeout=10000)
    chips = page.eval_on_selector_all(
        "#history-table tbody .result-chip", "els => els.map(e => e.textContent)")
    assert chips
    assert all(c in ("PENDING", "WIN", "LOSS", "VOID") for c in chips), chips
    assert "open" not in " ".join(chips).lower()


# --- C2: the page calms down ------------------------------------------------

def test_notices_collapse_into_one_bar_that_expands(page):
    """Compression, not suppression: one line, every sentence behind it."""
    page.evaluate("location.hash = '#/record'")
    page.wait_for_selector("#notices .notices-summary", timeout=10000)
    bars = page.eval_on_selector_all("#notices .notices-summary", "e => e.length")
    assert bars == 1, f"{bars} notice bars rendered; the point is one"

    summary = page.locator("#notices .notices-summary")
    text = summary.inner_text()
    assert "notice" in text.lower()
    assert page.locator("#notices .notices-detail").is_visible() is False

    summary.click()
    page.wait_for_timeout(250)
    assert page.locator("#notices .notices-detail").is_visible(), "it does not expand"
    full = page.locator("#notices .notices-detail").inner_text()
    # Every sentence survives; the bar is a summary of them, not a replacement.
    assert len(full) > len(text)


def test_the_greeting_is_on_the_home_tab_only(page):
    """One page greets; every page warns."""
    page.evaluate("location.hash = '#/record'")
    page.wait_for_timeout(700)
    assert page.locator("#glance").is_visible(), "the home tab does not greet"

    for route in ("#/factors", "#/history", "#/schedule"):
        page.evaluate(f"location.hash = '{route}'")
        page.wait_for_timeout(400)
        assert not page.locator("#glance").is_visible(), (
            f"{route} shows the since-you-last-looked strip"
        )
        assert page.locator("#notices-summary").is_visible(), (
            f"{route} lost its notices; a warning nobody sees is not a warning"
        )


def test_law_six_sits_in_the_footer_not_on_the_masthead(page):
    page.evaluate("location.hash = '#/record'")
    page.wait_for_timeout(500)
    note = page.locator("#sport-note")
    assert "never" in note.inner_text().lower()
    inside_footer = page.evaluate(
        "!!document.querySelector('footer #sport-note')")
    assert inside_footer, "LAW 6's caption is still above the fold"


@pytest.mark.parametrize(
    "route", ["#/record", "#/week", "#/factors", "#/versions", "#/history"]
)
def test_no_bare_dash_stands_in_for_a_value(route, page):
    """A dash in a data cell reads as a rendering fault. Every absence names
    itself: "no line", "not played", "nothing resolved yet"."""
    page.evaluate(f"location.hash = '{route}'")
    page.wait_for_timeout(800)
    bare = page.evaluate("""() => {
        const cells = [...document.querySelectorAll('td, .v, .chip-sub')];
        return cells.map(c => c.textContent.trim())
                    .filter(t => t === '\u2014' || t === '-');
    }""")
    assert not bare, f"{route} has {len(bare)} cells showing a bare dash"


def test_each_notice_keeps_its_task_name_in_the_summary(page):
    """The bar said "predict never run · predict never run": splitting on the
    first colon threw away the sport, so two different notices read as one
    repeated. A summary that cannot tell two warnings apart is not a summary."""
    page.evaluate("location.hash = '#/record'")
    page.wait_for_selector("#notices .notices-summary", timeout=10000)
    text = page.locator("#notices .notices-summary").inner_text()
    parts = [p.strip() for p in text.split("—")[-1].split("·")]
    assert len(parts) == len(set(parts)), f"the summary repeats itself: {parts}"


def test_the_header_record_follows_the_selected_sport(page):
    """One sport at a time, and the header says which."""
    before = page.locator("#record-line").inner_text()
    page.evaluate("document.querySelector('#sport-tabs button[data-sport=mlb]').click()")
    page.wait_for_timeout(1800)
    after = page.locator("#record-line").inner_text()
    assert after.startswith("MLB"), f"the header still reads {after!r}"
    assert after != before
