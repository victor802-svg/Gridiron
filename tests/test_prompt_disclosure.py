"""The prompt disclosure, rendered (the ruling of 2026-09-25: "The page and
the Record page show reconstructed rows' prompts labelled 'reconstructed' in
those words").

A WORLD OF ITS OWN, served on its own port: the browser world, copied, with
one reasoning forecast written before its release instant and reconstructed,
beside the world's own reasoning forecast and the prompt it was sent; both
ranked, and the default forecaster set to the reasoning pass so the page
shows them as cards. The shared world is left exactly as it was.

Each disclosure is opened and its text compared with the stored request,
byte for byte, at a desk width and at a phone's, where nothing may run past
the edge with it open.
"""
from __future__ import annotations

import json

import pytest

from gridiron import api, audit, db, language, settings, shortlist
from gridiron.model import llm, prompt_record
from tests import conftest

pytestmark = pytest.mark.browser

WIDTHS = ((1120, 900), (390, 844))


@pytest.fixture(scope="module")
def prompt_world(_shared_world, tmp_path_factory):
    target = tmp_path_factory.mktemp("prompts") / "world.db"
    source = db.read_only(_shared_world["db"],
                          "copying the browser world for the prompt disclosure")
    copy = db.connect(target)
    source.backup(copy)
    source.close()
    copy.close()
    conn = db.open_db(target)
    sent = conn.execute("SELECT id FROM predictions WHERE predictor = 'llm'"
                        " ORDER BY id DESC LIMIT 1").fetchone()[0]
    # A REASONING FORECAST FROM BEFORE THE RELEASE: an upcoming question of
    # the unplayed slate, dated before the world's release instant, and its
    # reconstruction through the one door.
    stat = conn.execute(
        "SELECT p.* FROM predictions p JOIN games g ON g.id = p.game_id"
        " WHERE p.predictor = 'statistical' AND p.market_type = 'spread'"
        "   AND g.status != 'final' AND p.id != ? ORDER BY p.id LIMIT 1",
        (sent,)).fetchone()
    factors = json.loads(stat["factors_json"])
    claim = factors["question"]["claim"]
    rebuilt = conn.execute(
        "INSERT INTO predictions (created_utc, sport, game_id, market_type,"
        " subject, line_asked, model_prob, model_side, predictor, pass_kind,"
        " factor_set_version, factors_json, reasoning)"
        " VALUES ('2025-10-01T00:00:00Z',?,?,?,?,?,?,?,'llm','final',?,?,"
        " 'The home side rates better on the season so far.')",
        (stat["sport"], stat["game_id"], stat["market_type"], stat["subject"],
         stat["line_asked"], 0.79, stat["model_side"],
         stat["factor_set_version"], json.dumps(factors))).lastrowid
    conn.commit()
    prompt_record.keep_reconstructed(
        conn, prediction_id=rebuilt, game_id=stat["game_id"], claim=claim,
        request_json=prompt_record.canonical(llm.reasoning_request(
            llm.build_prompt(claim, [], ["planted for the page"]))),
        code_version="48628e53df75" + "0" * 28,
        provenance=language.reconstruction_provenance(
            commit_utc="2026-09-02T05:44:27Z", before_merged_only=True,
            no_task_run=True))
    conn.commit()
    shortlist.rank_rows(conn, [sent, rebuilt])
    settings.set_value(conn, "default_forecaster", "llm",
                       note="the prompt disclosure's own world")
    conn.commit()
    base, server, thread = conftest._serve(target)
    yield {"base": base, "db": target, "sent": sent, "rebuilt": rebuilt}
    server.should_exit = True
    thread.join(timeout=10)
    conn.close()
    api.set_database(None)


def _stored(world, pid) -> dict:
    conn = db.read_only(world["db"], "the stored prompt, compared with the page")
    try:
        return prompt_record.record_for(conn, pid)
    finally:
        conn.close()


def _signed_in(browser, base, width, height):
    context = browser.new_context(viewport={"width": width, "height": height})
    page = context.new_page()
    page.page_errors = []
    page.on("pageerror", lambda e: page.page_errors.append(str(e)))
    page.goto(base + "/login", wait_until="networkidle")
    page.fill("#token", conftest.SMOKE_TOKEN)
    page.click("#submit")
    page.wait_for_url(base + "/", timeout=15000)
    page.wait_for_function("document.body.dataset.ready === 'true'", timeout=15000)
    return context, page


def _open_and_read(page, box):
    """Open one disclosure and wait for its text; return its parts' text."""
    box.locator("summary").click()
    box.locator("pre.prompt-text").first.wait_for(timeout=10000)
    return box.locator("pre.prompt-text").all_text_contents()


#: What a reader sees of an open disclosure, less the literal blocks (the
#: prompt verbatim, the model's name, the commit), which are exempt from the
#: plain-words law as every `.code-literal` is. Read off the box itself, so
#: the Results table's `td.wide` exclusion in the page-wide scan cannot hide it.
_BOX_WORDS = """(box) => {
    const clone = box.cloneNode(true);
    clone.querySelectorAll('.code-literal').forEach(e => e.remove());
    return clone.innerText;
}"""


def _check(page, box, record, kind):
    label = box.locator("summary").inner_text().strip()
    assert label == language.prompt_label(kind), label
    if kind == "reconstructed":
        assert "reconstructed" in label
    else:
        assert "reconstructed" not in label.lower()
    parts = _open_and_read(page, box)
    request = json.loads(record["request_json"])
    assert parts == [request["system"], request["messages"][0]["content"]], \
        "the page does not show the stored request byte for byte"
    assert box.locator("code.prompt-model").inner_text() == request["model"]
    # THE WORD BESIDE EVERY BLOCK OF TEXT (render check, 2026-09-25): the
    # first render headed a reconstruction "What it was told before the
    # question", as though it were the prompt sent, with the one
    # "reconstructed" thousands of pixels above on a phone.
    headings = [h.strip() for h in box.locator("h4.prompt-part").all_inner_texts()]
    assert len(headings) == len(parts), headings
    note = box.locator("p.prompt-note").inner_text()
    if kind == "reconstructed":
        assert all(h.endswith(", reconstructed") for h in headings), headings
        assert "not it" in note, note
    else:
        assert not [h for h in headings if "reconstructed" in h.lower()], headings
        assert "reconstructed" not in note.lower() and "sent" in note, note
    words = box.evaluate(_BOX_WORDS)
    assert audit.plain_words_violations(words) == [], words


@pytest.mark.parametrize("width,height", WIDTHS)
def test_results_shows_each_reasoning_row_the_prompt_it_carries(
        prompt_world, _browser, width, height):
    context, page = _signed_in(_browser, prompt_world["base"], width, height)
    try:
        page.evaluate("location.hash = '#/results'")
        page.wait_for_selector("#history-table tbody tr", timeout=15000)
        page.select_option("#history-predictor", "llm")
        page.wait_for_selector("#history-table details.prompt-box", timeout=15000)
        for pid, kind in ((prompt_world["rebuilt"], "reconstructed"),
                          (prompt_world["sent"], "sent")):
            box = page.locator(f"#history-table details.prompt-box"
                               f"[data-prompt-kind='{kind}']").first
            _check(page, box, _stored(prompt_world, pid), kind)
            # THE ROW'S FACTS STAY BESIDE ITS SENTENCE (render check,
            # 2026-09-25): opened, the prompt made the row thousands of
            # pixels tall and the date, model, tier and result floated to
            # its middle, out of sight of the row they belong to.
            drift = box.evaluate("""(box) => {
                const row = box.closest('tr');
                const top = n => { const r = document.createRange();
                                   r.selectNodeContents(n);
                                   return r.getBoundingClientRect().top; };
                const first = top(row.cells[0]);
                return [...row.cells].slice(1).map(td => Math.round(top(td) - first));
            }""")
            assert max(drift) < 60, \
                f"the {kind} row's facts sit {drift}px below its sentence at {width}"
        overflow = page.evaluate("document.documentElement.scrollWidth"
                                 " - document.documentElement.clientWidth")
        assert overflow <= 0, f"{overflow}px past the edge with the prompts open"
        assert page.page_errors == []
    finally:
        context.close()


@pytest.mark.parametrize("width,height", WIDTHS)
def test_the_record_page_shows_the_prompts_when_the_reasoning_pass_is_picked(
        prompt_world, _browser, width, height):
    context, page = _signed_in(_browser, prompt_world["base"], width, height)
    try:
        page.evaluate("location.hash = '#/record'")
        page.wait_for_selector("#forecaster-picker button", timeout=15000)
        assert page.locator("#prompt-record").is_hidden(), \
            "the model's own record grew a panel about the other forecaster"
        page.click("#forecaster-picker button[data-forecaster='llm']")
        page.wait_for_selector("#prompt-record-list details.prompt-box", timeout=15000)
        line = page.inner_text("#prompt-record-line")
        assert "with the prompt reconstructed" in line and "as sent" in line, line
        # BOTH KINDS ON THE RECORD PAGE (render check, 2026-09-25): the sent
        # one says it was sent, the reconstruction says so in that word.
        for pid, kind in ((prompt_world["rebuilt"], "reconstructed"),
                          (prompt_world["sent"], "sent")):
            box = page.locator("#prompt-record-list details.prompt-box"
                               f"[data-prompt-kind='{kind}']").first
            _check(page, box, _stored(prompt_world, pid), kind)
        overflow = page.evaluate("document.documentElement.scrollWidth"
                                 " - document.documentElement.clientWidth")
        assert overflow <= 0, f"{overflow}px past the edge with the prompts open"
        assert page.page_errors == []
    finally:
        context.close()


@pytest.mark.parametrize("width,height", WIDTHS)
def test_a_reasoning_card_shows_its_prompt_inside_why(
        prompt_world, _browser, width, height):
    context, page = _signed_in(_browser, prompt_world["base"], width, height)
    try:
        page.evaluate("location.hash = '#/week'")
        for pid, kind in ((prompt_world["rebuilt"], "reconstructed"),
                          (prompt_world["sent"], "sent")):
            card = page.locator(f"article.face[data-id='{pid}']")
            card.first.wait_for(timeout=15000)
            box = card.first.locator("details.prompt-box")
            assert box.count() == 1 and not box.is_visible(), \
                "the prompt sits on the card face instead of inside Why"
            card.first.locator("button.expand").click()
            # COLLAPSED INSIDE WHY: one line, its label, and nothing of the
            # prompt until it is opened (render check, 2026-09-25).
            box.wait_for(state="visible", timeout=5000)
            assert not box.evaluate("b => b.open")
            assert box.locator("p.prompt-note").is_hidden()
            _check(page, box, _stored(prompt_world, pid), kind)
        overflow = page.evaluate("document.documentElement.scrollWidth"
                                 " - document.documentElement.clientWidth")
        assert overflow <= 0, f"{overflow}px past the edge with the prompts open"
        assert page.page_errors == []
    finally:
        context.close()


def test_the_disclosure_keeps_the_tap_floor_on_a_phone(prompt_world, _browser):
    context, page = _signed_in(_browser, prompt_world["base"], 390, 844)
    try:
        page.evaluate("location.hash = '#/results'")
        page.wait_for_selector("#history-table tbody tr", timeout=15000)
        page.select_option("#history-predictor", "llm")
        # THE FILTERED TABLE, not the one it replaces: its Forecaster column
        # goes when one forecaster is shown.
        page.wait_for_function(
            """() => {
                const heads = [...document.querySelectorAll('#history-table thead th')];
                return heads.length > 0
                    && heads.every(th => th.textContent.trim() !== 'Forecaster')
                    && !!document.querySelector('#history-table details.prompt-box');
            }""", timeout=15000)
        heights = page.evaluate(
            """() => [...document.querySelectorAll('#history-table details.prompt-box summary')]
                .map(s => s.getBoundingClientRect().height)""")
        assert heights and min(heights) >= 44, f"summary heights at 390: {heights}"
    finally:
        context.close()
