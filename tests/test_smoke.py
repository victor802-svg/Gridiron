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

import socket
import threading
import time

import pytest

from gridiron import api, resolve, run
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


@pytest.fixture(scope="function")
def served(league, db_path):
    import uvicorn

    store.sync_registry(league)
    # Six markets: the spread plus each prop type, fitted separately.
    baseline.train_all(league, (2025,), l2=1.0, note="smoke", min_rows=20)
    run.run_week(league, 2025, 7, include_props=True, use_llm=False)
    run.run_week(league, 2025, 8, include_props=True, use_llm=False)
    resolve.resolve_all(league)
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
        page.goto(served, wait_until="networkidle")
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
        ("#/week", "#week-cards .card"),
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
