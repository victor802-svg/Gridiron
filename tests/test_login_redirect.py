"""A signed-in reader who opens /login lands in the app (UI audit finding 18,
2026-09-05): the token form came up again for a session that was valid."""
from __future__ import annotations


def test_a_signed_in_reader_opening_login_lands_in_the_app(page, served):
    page.goto(served + "/login")
    page.wait_for_load_state("load")
    page.wait_for_function("document.body.dataset.ready === 'true'", timeout=20000)
    assert page.url.rstrip("/") == served.rstrip("/"), page.url
    assert page.query_selector("#token") is None, "the token form is on screen for a valid session"


def test_a_stranger_opening_login_gets_the_form(_browser, served):
    context = _browser.new_context()
    try:
        fresh = context.new_page()
        fresh.goto(served + "/login")
        fresh.wait_for_selector("#token", timeout=10000)
        assert "/login" in fresh.url
    finally:
        context.close()
