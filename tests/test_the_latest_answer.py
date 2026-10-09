"""A part of the page draws only the answer to the latest thing asked of it,
under what that answer was asked for (operator question 47; found by question
5's prover, 2026-10-08; built 2026-10-09 without a new ruling: step A's and
question 37's rule that a number is drawn under the words of what it is).

THE FINDING: `renderResults` kept no check that a later filter had superseded
its answer, and drew its Forecaster column from the select's value when the
answer landed. A search typed with its answer held, then the reasoning pass
chosen and its one-row table landed: the search's late answer then drew 51
rows, 50 of them the statistical model's chances, under "reasoning pass" with
no Forecaster column, captioned "51 predictions".

MEASURED ON d7a16c2 (451ab3d's code), every part of the page that draws an
answer to a filter or a choice, the earlier answer held inside the page and
released after the later one had landed: Results (the finding, and the
Forecaster column read from the select), the tier table (a market, a
forecaster), the Record page's weekly strip, the Props page (a week), the
entry check and the deposit match (an answer about a form changed since it
was asked, and two checks in flight), and Settings (a value saved twice, and a
read asked before a save) each drew the earlier answer under the later choice;
the slate held (`weekSeq`, since 2026-09-05).

Two halves. The page's script is read by `audit.latest_answer_faults` (the
gate's check and the planting's). The page itself is driven here in
Chromium, each part asked twice with the EARLIER answer held inside the page
-- before it is sent, or, for a save and a read of the settings, after the
appliance has answered -- and released only once the later one has landed:
the adverse order, never a sleep. Each test fails on d7a16c2.
"""
from __future__ import annotations

import ast
import contextlib
import os
from pathlib import Path

import pytest

from gridiron import api, audit, auth, config, db
from tests.conftest import REDRAW_LIMIT_MS, SMOKE_TOKEN, wait_for_the_render

REPO = Path(__file__).resolve().parents[1]
WIDE = {"width": 1300, "height": 900}


def _js() -> str:
    return (config.PACKAGE_ROOT / "web" / "app.js").read_text(encoding="utf-8")


def _named(faults, *words) -> bool:
    return any(all(w in f for w in words) for f in faults)


# --- the script, read --------------------------------------------------------

def test_the_shipped_page_draws_only_its_latest_answers():
    assert audit.latest_answer_faults() == []
    audit.check_every_part_draws_its_latest_answer()


#: EACH LATE ANSWER, as a part of the page drew it on d7a16c2 or one rule of
#: it broken: (anchor in the shipped script, what is planted, the words the
#: scan names it by).
FORMS = {
    "Results drawing a superseded answer": (
        "    if (stale(seq) || superseded('results', asked)) return;\n    requireN(data, 'history');",
        "    if (stale(seq)) return;\n    requireN(data, 'history');",
        "`renderResults` draws an answer without first asking"),
    "Results never the latest asked": (
        "    askedLatest('results', asked);\n", "",
        "`renderResults` never says it is the latest asked"),
    "the Forecaster column read from the select when the answer lands": (
        "    const showForecaster = !own.get('predictor');\n",
        "    const showForecaster = !document.getElementById('history-predictor').value;\n",
        "`renderResults` reads a control -- `getElementById('history-predictor').value`"),
    "the tier table drawing a superseded answer": (
        "    if (stale(seq) || superseded('tier-table', asked)) return;\n",
        "    if (stale(seq)) return;\n",
        "`refreshTierTable` draws an answer without first asking"),
    "the weekly strip handed no count": (
        "    parts.push(renderOverTime(market, predictor, asked).catch(showError));\n",
        "    parts.push(renderOverTime(market, predictor).catch(showError));\n",
        "`renderRecord` draws `renderOverTime` without handing it its count"),
    "the Props page reading its chip when its answer lands": (
        "    if (stale(seq) || superseded('props', asked)) return;\n"
        "    updating(host, 'props-updating', false);\n",
        "    if (stale(seq) || superseded('props', asked)) return;\n"
        "    active = state.propFamily || '';\n    updating(host, 'props-updating', false);\n",
        "`renderProps` reads a control -- `state.propFamily`"),
    "the Props page's failure drawn over a later answer": (
        "      if (!stale(seq) && !superseded('props', asked)) updating(host, 'props-updating', false);\n",
        "      if (!stale(seq)) updating(host, 'props-updating', false);\n",
        "`renderProps` draws its failure"),
    "the entry check's answer drawn about an entry changed since": (
        "      entry.changed = entry.edits !== edits;\n", "      entry.changed = false;\n",
        "`checkEntry` draws its answer without putting it aside"),
    "the deposit match drawing a superseded answer": (
        "      if (stale(seq) || superseded('deposit-match', asked)) return;\n",
        "      if (stale(seq)) return;\n",
        "`checkDeposit` draws an answer without first asking"),
    "a setting saved out of turn": (
        "      res = await inTurn(() => fetch('/api/settings', {\n",
        "      res = await Promise.resolve().then(() => fetch('/api/settings', {\n",
        "`saveSetting` sends 1 settings request(s) out of turn"),
    "a setting's superseded save drawn": (
        "    if (superseded('setting ' + name, asked)) return;\n", "",
        "`saveSetting` draws an answer without first asking"),
    # ITS PROVER'S (2026-10-09): My day, which two pages draw, and a fill.
    "My day drawn by a slate a later page superseded": (
        "    if (!superseded('my-day', asked)) renderMyDay(board);\n\n"
        "    const today = data.today || null;",
        "    renderMyDay(board);\n\n    const today = data.today || null;",
        "`renderGames` draws `renderMyDay` without asking"),
    "My day never the latest asked on the Props page": (
        "    askedLatest('my-day', asked);\n    let active = state.propFamily || '';",
        "    let active = state.propFamily || '';",
        "`renderProps` draws `renderMyDay`, a part another page draws too, without first"),
    "the deposit match's payout filled in again, uncounted": (
        "    if (JSON.stringify([deposit.payout, deposit.offered, deposit.confirmed]) !== was)"
        " depositChanged(false);\n", "",
        "`fillDepositPayout` fills the deposit's payout in again without counting"),
    "the entry's payout filled in again, uncounted": (
        "    if (JSON.stringify([entry.payout, entry.offered, entry.confirmed]) !== was)"
        " entryChanged(false);\n", "",
        "`fillEntryPayout` fills the entry's payout in again without counting"),
}


@pytest.mark.parametrize("name", list(FORMS))
def test_each_late_answer_drawn_under_a_later_choice_is_named(name):
    anchor, planted, wanted = FORMS[name]
    js = _js()
    assert js.count(anchor) == 1, (name, js.count(anchor))
    faults = audit.latest_answer_faults(js.replace(anchor, planted))
    assert _named(faults, wanted), (name, faults)


def test_a_function_asking_for_an_answer_in_no_register_is_named(monkeypatch):
    routes = "  const ROUTES = {\n"
    about = ("  async function renderAbout() {\n"
             "    const data = await fetchJSON(withSport('/api/about?' + historyQuery()));\n"
             "    document.getElementById('view-about').textContent = data.colophon || '';\n"
             "  }\n\n")
    faults = audit.latest_answer_faults(_js().replace(routes, about + routes, 1))
    assert _named(faults, "`renderAbout` asks for an answer and is in no register"), faults
    monkeypatch.setitem(audit.LATEST_ASKED_RENDERS, "renderTheOldWeek", "'week'")
    monkeypatch.setitem(audit.LATEST_ASKED_EXEMPT, "loadTheOldTabs", "a reason with no date")
    faults = audit.latest_answer_faults()
    assert _named(faults, "`renderTheOldWeek` is in audit.LATEST_ASKED_RENDERS and gone"), faults
    assert _named(faults, "`loadTheOldTabs` is exempt in audit.LATEST_ASKED_EXEMPT"), faults
    # ITS PROVER'S REGISTERS (2026-10-09): a part two pages draw, and a fill.
    monkeypatch.setitem(audit.LATEST_ASKED_SHARED, "renderTheOldStrip", "'old-strip'")
    monkeypatch.setitem(audit.LATEST_ASKED_FILLS, "fillTheOldPayout", ("entry", "entryChanged"))
    faults = audit.latest_answer_faults()
    assert _named(faults, "`renderTheOldStrip` is in audit.LATEST_ASKED_SHARED and gone"), faults
    assert _named(faults, "`fillTheOldPayout` or `entryChanged` is in audit.LATEST_ASKED_FILLS"), faults


def test_the_gate_makes_the_call():
    """Read from the gate's syntax tree, so a comment naming the check cannot
    stand in for the call (question 20's planting is pinned the same way)."""
    gate = REPO / "tools" / "verify.py"
    step = next(node for node in ast.parse(gate.read_text(encoding="utf-8")).body
                if isinstance(node, ast.FunctionDef) and node.name == "step_2_guards")
    assert any(isinstance(node, ast.Attribute)
               and node.attr == "check_every_part_draws_its_latest_answer"
               and isinstance(node.value, ast.Name) and node.value.id == "audit"
               for node in ast.walk(step))


# --- the page, driven: the earlier answer held, released after the later ------
#
# THE PAGE'S OWN `fetch`, WRAPPED. A rule holds the next request whose address
# holds `part` (and whose method is `method`, if named): before it is sent
# ('ask'), or after its answer has come back, the appliance having done its
# work ('answer'). Every answer counts as READ a task after the page parsed it
# -- every step the page takes on it in its continuations has run (conftest's
# `watch_the_answers`, question 5) -- so "settled" means every answer asked is
# read, the held ones apart. A MessageChannel's task, never a timer.

_HOLD = """() => {
    if (window.__held) return;
    const h = window.__held = { rules: [], slots: [], inflight: 0 };
    const real = window.fetch;
    const counted = (p) => p.then(res => {
        const json = res.json.bind(res);
        res.json = () => json().then(body => {
            const after = new MessageChannel();
            after.port1.onmessage = () => { h.inflight -= 1; after.port1.close(); };
            after.port2.postMessage(null);
            return body;
        }, err => { h.inflight -= 1; throw err; });
        return res;
    }, err => { h.inflight -= 1; throw err; });
    window.fetch = function (input, init) {
        const url = typeof input === 'string' ? input : ((input && input.url) || String(input));
        const method = (init && init.method) || 'GET';
        h.inflight += 1;
        const at = h.rules.findIndex(r => url.includes(r.part) && (!r.method || r.method === method));
        if (at < 0) return counted(real.call(window, input, init));
        const rule = h.rules.splice(at, 1)[0];
        const slot = { url: url, ready: false, gone: false };
        h.slots.push(slot);
        if (rule.side === 'answer') {
            return counted(real.call(window, input, init).then(res => new Promise(go => {
                slot.go = () => { slot.gone = true; go(res); };
                slot.ready = true;
            })));
        }
        return counted(new Promise(go => {
            slot.go = () => { slot.gone = true; go(real.call(window, input, init)); };
            slot.ready = true;
        }));
    };
}"""


def _hold(page, part: str, side: str = "ask", method: str | None = None) -> None:
    page.evaluate(_HOLD)
    page.evaluate("([part, side, method]) => window.__held.rules.push("
                  "{ part: part, side: side, method: method })", [part, side, method])


def _held(page) -> int:
    """Wait until the request held last is held; its place."""
    page.wait_for_function(
        "() => window.__held.slots.length > 0"
        " && window.__held.slots[window.__held.slots.length - 1].ready",
        timeout=REDRAW_LIMIT_MS)
    return page.evaluate("window.__held.slots.length - 1")


def _release(page, at: int) -> None:
    page.evaluate("(i) => window.__held.slots[i].go()", at)


def _settled(page) -> None:
    page.wait_for_function(
        "() => window.__held.inflight === window.__held.slots.filter(s => !s.gone).length",
        timeout=REDRAW_LIMIT_MS)


def _open(page, view):
    page.set_viewport_size(WIDE)
    if page.evaluate("location.hash") != "#/" + view:
        with wait_for_the_render(page, view):
            page.evaluate(f"location.hash = '#/{view}'")


def _choose(page, selector, value):
    """A control the page reads on its own `change`, set and announced (the
    week picker sits on the Games page; the page's own listener asks)."""
    page.evaluate("([s, v]) => { const n = document.querySelector(s); n.value = v;"
                  " n.dispatchEvent(new Event('change')); }", [selector, value])


_TABLE = """() => ({
    chosen: document.getElementById('history-predictor').value,
    heads: [...document.querySelectorAll('#history-table thead th')].map(t => t.textContent.trim()),
    rows: document.querySelectorAll('#history-table tbody tr').length,
    caption: document.getElementById('history-caption').textContent })"""


def test_a_late_search_is_not_drawn_under_the_forecaster_chosen_after_it(page):
    """THE FINDING. A search typed, its answer held; the reasoning pass chosen
    and its table landed; the search's answer released after it. On d7a16c2
    the table then showed the search's 51 rows, 50 of them the statistical
    model's, under "reasoning pass" with no Forecaster column, captioned "51
    predictions"."""
    _open(page, "results")
    both = page.evaluate(
        "fetch('/api/history?q=a&limit=100&offset=0&sport=' + Gridiron.state.sport)"
        ".then(r => r.json()).then(j => ({ n: j.n, by: [...new Set(j.items.map(i => i.predictor))] }))")
    llm = page.evaluate(
        "fetch('/api/history?q=a&predictor=llm&limit=100&offset=0&sport=' + Gridiron.state.sport)"
        ".then(r => r.json()).then(j => ({ n: j.n, by: [...new Set(j.items.map(i => i.predictor))] }))")
    assert both["n"] > llm["n"] > 0 and "statistical" in both["by"] and llm["by"] == ["llm"], (
        f"the world no longer shows the case: {both}, {llm}")
    _hold(page, "/api/history?q=a&")
    page.fill("#history-q", "a")
    held = _held(page)
    with wait_for_the_render(page, "results"):
        page.select_option("#history-predictor", "llm")
    landed = page.evaluate(_TABLE)
    assert landed["rows"] == llm["n"] and "Forecaster" not in landed["heads"], landed
    _release(page, held)
    _settled(page)
    late = page.evaluate(_TABLE)
    assert late == landed, (
        f"THE SEARCH'S LATE ANSWER WAS DRAWN UNDER THE REASONING PASS CHOSEN AFTER IT: "
        f"{late['rows']} rows ({both['n']} are the search's, every forecaster's), captioned "
        f"{late['caption']!r}, under {late['chosen']!r} with columns {late['heads']}")


def test_the_forecaster_column_is_read_from_the_tables_own_request(page):
    """The reasoning pass's table asked, its answer held; the select then set
    back to both forecasters WITHOUT asking (no event: the page never moves a
    control silently, so this is how a test reaches the reading); the answer
    released. The table is the reasoning pass's alone, and its Forecaster
    column is its own request's -- none. On d7a16c2 it was the select's when
    the answer landed, and the column was drawn over one forecaster's row."""
    _open(page, "results")
    _hold(page, "predictor=llm")
    page.select_option("#history-predictor", "llm")
    held = _held(page)
    page.evaluate("document.getElementById('history-predictor').value = ''")
    _release(page, held)
    _settled(page)
    drawn = page.evaluate(_TABLE)
    assert drawn["rows"] > 0 and "Forecaster" not in drawn["heads"], (
        f"THE FORECASTER COLUMN WAS READ FROM THE SELECT WHEN THE ANSWER LANDED, not from "
        f"the table's own request: {drawn}")
    with wait_for_the_render(page, "results"):
        page.select_option("#history-predictor", "")


_TIER = """() => ({ market: document.getElementById('tier-market').value,
    pressed: [...document.querySelectorAll('#forecaster-picker button[aria-pressed=true]')]
        .map(b => b.dataset.forecaster),
    caption: document.getElementById('tier-caption').textContent,
    rows: [...document.querySelectorAll('#tier-table tbody tr')].map(r => r.textContent) })"""


def test_a_late_tier_table_is_not_drawn_under_a_later_market(page):
    """The moneyline's table asked, held; the total's asked and landed; the
    moneyline's released: on d7a16c2 it stood, captioned the moneyline's,
    under a select reading "total"."""
    _open(page, "record")
    now = page.evaluate("document.getElementById('tier-market').value")
    options = [v for v in page.evaluate(
        "[...document.querySelectorAll('#tier-market option')].map(o => o.value)") if v != now]
    first, second = options[0], options[1]
    _hold(page, f"market={first}&")
    page.select_option("#tier-market", first)
    held = _held(page)
    with wait_for_the_render(page, "record", "tier-table"):
        page.select_option("#tier-market", second)
    landed = page.evaluate(_TIER)
    _release(page, held)
    _settled(page)
    late = page.evaluate(_TIER)
    assert late == landed and late["market"] == second, (
        f"THE {first.upper()} TABLE'S LATE ANSWER WAS DRAWN UNDER {second!r}: {late['caption']!r}")


def test_a_late_tier_table_is_not_drawn_under_a_later_forecaster(page):
    """The reasoning pass's table asked, held; the model's asked and landed;
    the reasoning pass's released: on d7a16c2 it stood under the model's
    button."""
    _open(page, "record")
    _hold(page, "forecaster=llm")
    page.click("#forecaster-picker button[data-forecaster='llm']")
    held = _held(page)
    with wait_for_the_render(page, "record", "tier-table"):
        page.click("#forecaster-picker button[data-forecaster='statistical']")
    landed = page.evaluate(_TIER)
    _release(page, held)
    _settled(page)
    late = page.evaluate(_TIER)
    assert late == landed and late["pressed"] == ["statistical"], (
        f"THE REASONING PASS'S LATE TABLE WAS DRAWN UNDER THE MODEL'S BUTTON: {late['caption']!r}")


_STRIP = "() => document.getElementById('overtime-caption').textContent"


def test_a_late_weekly_strip_is_not_drawn_under_a_later_chart(page):
    """From the total, the point spread chosen (its weekly strip held), then
    receptions (landed); the point spread's strip released: on d7a16c2 it drew
    "8 resolved across 2 weeks" under a chart of receptions' 3."""
    _open(page, "record")
    sport = page.evaluate("Gridiron.state.sport")
    def strip(query):
        return page.evaluate(f"fetch('/api/over-time?predictor=statistical&{query}&sport={sport}')"
                             ".then(r => r.json()).then(j => [j.n, j.points.length])")
    spread = strip("market_type=spread")
    receptions = strip("market_type=prop&prop_type=receptions")
    assert spread[0] != receptions[0], f"the world no longer tells the strips apart: {spread}"
    with wait_for_the_render(page, "record"):
        page.select_option("#chart-market", "total")
    _hold(page, "market_type=spread")
    page.select_option("#chart-market", "spread")
    held = _held(page)
    with wait_for_the_render(page, "record"):
        page.select_option("#chart-market", "receptions")
    landed = page.evaluate(_STRIP)
    assert f"{receptions[0]} resolved across {receptions[1]} weeks" in landed, landed
    _release(page, held)
    _settled(page)
    late = page.evaluate(_STRIP)
    assert late == landed, (
        f"THE POINT SPREAD'S LATE STRIP WAS DRAWN UNDER RECEPTIONS: {late!r} where receptions' "
        f"is {landed!r}")


_PROPS = """() => ({ week: document.getElementById('week-picker').value,
    headline: document.getElementById('props-headline').textContent,
    tiles: [...document.querySelectorAll('#props-tiles .prop')].map(t => t.dataset.id) })"""


def test_a_late_week_is_not_drawn_on_the_props_page_under_a_later_one(page):
    """Another week asked, held; this week asked again and landed; the other
    week released: on d7a16c2 it drew week 8's eight tiles, headed "Week 8,
    2025", under the picker's week 18."""
    _open(page, "props")
    now = page.evaluate("document.getElementById('week-picker').value")
    sport = page.evaluate("Gridiron.state.sport")
    heads = {w: page.evaluate(
        f"fetch('/api/week?season=' + JSON.parse({w!r}).season + '&week=' + JSON.parse({w!r}).week"
        f" + '&sport={sport}').then(r => r.json()).then(j => j.headline)")
        for w in page.evaluate("[...document.querySelectorAll('#week-picker option')].map(o => o.value)")}
    other = next(w for w in heads if heads[w] != heads[now])
    week = other.split('"week":')[1].rstrip("}")
    _hold(page, f"week={week}&")
    _choose(page, "#week-picker", other)
    held = _held(page)
    with wait_for_the_render(page, "props"):
        _choose(page, "#week-picker", now)
    landed = page.evaluate(_PROPS)
    assert landed["headline"] == heads[now], landed
    _release(page, held)
    _settled(page)
    late = page.evaluate(_PROPS)
    assert late == landed, (
        f"ANOTHER WEEK'S LATE ANSWER WAS DRAWN ON THE PROPS PAGE: headed {late['headline']!r}, "
        f"{len(late['tiles'])} tiles, under the picker's {heads[now]!r}")


def _fill_deposit(page, playthrough):
    page.wait_for_selector("#deposit-form input.entry-input", timeout=REDRAW_LIMIT_MS)
    inputs = "#deposit-form input.entry-input"
    page.fill(f"{inputs} >> nth=0", "3")
    page.check("#deposit-form .entry-confirm input")
    page.fill(f"{inputs} >> nth=1", "1")
    page.fill(f"{inputs} >> nth=2", str(playthrough))


_DEPOSIT = """() => ({ text: document.getElementById('deposit-lines').textContent,
    verdict: (document.querySelector('#deposit-lines .verdict') || {}).textContent || null,
    lines: [...document.querySelectorAll('#deposit-lines .entry-line')].map(r => r.textContent) })"""


def test_a_deposit_match_about_an_offer_changed_since_is_put_aside(page):
    """Worked out at a 5x playthrough, the answer held; the playthrough typed
    as 9; the answer released. It is about the offer as it was, so it is put
    aside as an earlier answer is. On d7a16c2 it was drawn -- "5 units per
    unit of bonus", "-0.25 per unit of bonus" -- under the form's 9x."""
    _open(page, "props")
    _fill_deposit(page, 5)
    _hold(page, "/api/deposit-match", method="POST")
    page.click("#deposit-check")
    held = _held(page)
    page.fill("#deposit-form input.entry-input >> nth=2", "9")
    _release(page, held)
    _settled(page)
    drawn = page.evaluate(_DEPOSIT)
    assert drawn["verdict"] is None and not drawn["lines"] and drawn["text"].startswith("Changed since"), (
        f"AN ANSWER ABOUT THE OFFER AT 5x WAS DRAWN UNDER THE FORM'S 9x: {drawn}")


def test_a_late_deposit_match_is_not_drawn_under_a_later_one(page):
    """Worked out at 5x, held; the form drawn again (its size chosen again,
    its button with it) and worked out at 9x, landed; the first released: on
    d7a16c2 its 5x figures were drawn under the form's 9x."""
    _open(page, "props")
    _fill_deposit(page, 5)
    _hold(page, "/api/deposit-match", method="POST")
    page.click("#deposit-check")
    held = _held(page)
    sizes = page.evaluate(
        "[...document.querySelectorAll('#deposit-form .entry-head-row select')[2].options].map(o => o.value)")
    page.select_option("#deposit-form .entry-head-row select >> nth=2", sizes[-1])
    page.select_option("#deposit-form .entry-head-row select >> nth=2", sizes[0])
    _fill_deposit(page, 9)
    with wait_for_the_render(page, "props", "deposit-lines"):
        page.click("#deposit-check")
    landed = page.evaluate(_DEPOSIT)
    assert any(line.endswith("9 units per unit of bonus") for line in landed["lines"]), landed
    _release(page, held)
    _settled(page)
    late = page.evaluate(_DEPOSIT)
    assert late == landed, f"THE 5x ANSWER WAS DRAWN UNDER THE FORM'S 9x: {late['lines']}"


# --- on a copy of the world: what is kept -------------------------------------
#
# The entry check keeps the payout he confirmed, and a setting saved is a row:
# these run on a copy of the browser world served on its own port, so the
# shared world is left as every other browser test finds it (the entry
# check's own tests do the same).

@pytest.fixture(scope="module")
def _a_copy(_shared_world, tmp_path_factory):
    from tests import conftest

    target = tmp_path_factory.mktemp("latest-answer") / "world.db"
    source = db.read_only(_shared_world["db"],
                          "copying the browser world for question 47's tests, which keep a "
                          "payout and save a setting")
    copy = db.connect(target)
    source.backup(copy)
    source.close()
    copy.close()
    base, server, thread = conftest._serve(target)
    yield {"base": base, "db": target, "shared": _shared_world["db"]}
    server.should_exit = True
    thread.join(timeout=10)
    api.set_database(_shared_world["db"])


@contextlib.contextmanager
def _on_the_copy(world, browser):
    api.set_database(world["db"])
    os.environ[auth.TOKEN_VAR] = SMOKE_TOKEN
    context = browser.new_context(viewport=WIDE)
    page = context.new_page()
    try:
        # THE SIGN-IN PAGE'S LOAD, AN EVENT (operator question 5): conftest's
        # `page` says why.
        page.goto(world["base"] + "/login")
        page.fill("#token", SMOKE_TOKEN)
        page.click("#submit")
        page.wait_for_url(world["base"] + "/", timeout=15000)
        page.wait_for_function("document.body.dataset.ready === 'true'", timeout=15000)
        yield page
    finally:
        context.close()
        api.set_database(world["shared"])


def _one_game(world):
    """The copy's first NFL game still to come, and a player of each club."""
    conn = db.read_only(world["db"], "question 47's entry check: a game and two players")
    try:
        game = conn.execute("SELECT home, away, season FROM games WHERE sport = 'nfl'"
                            " AND status = 'scheduled' ORDER BY kickoff_utc, id LIMIT 1").fetchone()
        def player(club):
            return conn.execute("SELECT player_name FROM player_week_stats WHERE season = ?"
                                " AND team = ? ORDER BY week DESC, player_name LIMIT 1",
                                (game["season"], club)).fetchone()[0]
        return game["home"], player(game["home"]), game["away"], player(game["away"])
    finally:
        conn.close()


def _fill_entry(page, world, multiple, app="prizepicks", go=True):
    """The entry typed: `app`, two legs, and -- where `multiple` is given --
    that payout typed and confirmed. `go` opens the Props page first."""
    if go:
        with wait_for_the_render(page, "props"):
            page.evaluate("location.hash = '#/props'")
    page.wait_for_selector("#entry-form .entry-head-row select", timeout=REDRAW_LIMIT_MS)
    home, home_player, away, away_player = _one_game(world)
    page.select_option("#entry-form .entry-head-row select >> nth=0", app)
    for i, (player, club, line) in enumerate(((home_player, home, 250.5),
                                              (away_player, away, 60.5))):
        leg = f"#entry-legs .entry-leg >> nth={i}"
        page.fill(f"{leg} >> input >> nth=0", player)
        page.select_option(f"{leg} >> select >> nth=0", club)
        page.fill(f"{leg} >> input >> nth=1", "passing yards")
        page.fill(f"{leg} >> input >> nth=2", str(line))
    if multiple is not None:
        page.fill("#entry-payout .entry-pays-rows input", multiple)
    page.check("#entry-payout .entry-confirm input")


_ENTRY = """() => ({ text: document.getElementById('entry-lines').textContent,
    verdict: (document.querySelector('#entry-lines .verdict') || {}).textContent || null,
    legs: [...document.querySelectorAll('#entry-lines .entry-read-words')].map(r => r.textContent) })"""


def test_an_entry_check_about_an_entry_changed_since_is_put_aside(_a_copy, _browser):
    """Checked, the answer held; a leg's line changed from 250.5 to 300.5; the
    answer released. It is about the entry as it was, so it is put aside as an
    earlier answer is. On d7a16c2 it was drawn as the verdict, its legs read
    "over 250.5", beside a form reading 300.5."""
    with _on_the_copy(_a_copy, _browser) as page:
        _fill_entry(page, _a_copy, "3")
        _hold(page, "/api/entry-check", method="POST")
        page.click("#entry-check")
        held = _held(page)
        page.fill("#entry-legs .entry-leg >> nth=0 >> input >> nth=2", "300.5")
        _release(page, held)
        _settled(page)
        drawn = page.evaluate(_ENTRY)
        assert drawn["verdict"] is None and drawn["text"].startswith("Changed since"), (
            f"AN ANSWER ABOUT THE LEG AT 250.5 WAS DRAWN BESIDE THE FORM'S 300.5: {drawn}")


def test_a_late_entry_check_is_not_drawn_under_a_later_one(_a_copy, _browser):
    """Checked at 3x, held; the app chosen again (the form drawn again, its
    button with it), 5x confirmed and checked, landed; the first released: on
    d7a16c2 its 3x verdict -- "Costs at coin flips", 57.74% a leg -- was drawn
    under the form's 5x."""
    with _on_the_copy(_a_copy, _browser) as page:
        _fill_entry(page, _a_copy, "3")
        _hold(page, "/api/entry-check", method="POST")
        page.click("#entry-check")
        held = _held(page)
        apps = page.evaluate("[...document.querySelectorAll('#entry-form .entry-head-row select')[0]"
                             ".options].map(o => o.value)")
        page.select_option("#entry-form .entry-head-row select >> nth=0",
                           next(a for a in apps if a and a != "prizepicks"))
        page.fill("#entry-payout .entry-pays-rows input", "5")
        page.check("#entry-payout .entry-confirm input")
        with wait_for_the_render(page, "props", "entry-lines"):
            page.click("#entry-check")
        landed = page.evaluate(_ENTRY)
        assert (landed["verdict"] or "").startswith("Clears the bar"), landed
        _release(page, held)
        _settled(page)
        late = page.evaluate(_ENTRY)
        assert late == landed, f"THE 3x VERDICT WAS DRAWN UNDER THE FORM'S 5x: {late['verdict']!r}"


# --- its prover's (2026-10-09): a fill is a change, and My day has two pages --
#
# Found on the change as handed, each failing there and on d7a16c2. A payout
# the PAGE filled in is filled again from a newer row on every redraw of the
# Props page, and unticked -- with no count of a change, so the answer worked
# out from the payout as it was stood beside the new one as if about it. And
# My day, under the header on every page, is drawn by the slate and by the
# Props page, which `weekSeq` and the Props page's own count each tell apart
# only from themselves.

def _a_payout_kept(world, app, legs, multiple, typed_utc):
    """A payout kept for `app`, power, `legs` legs, typed at `typed_utc`: as
    step 1 keeps one, on the copy (another device's, or an earlier day's)."""
    conn = db.connect(world["db"])
    try:
        conn.execute("INSERT INTO pickem_payouts_typed (typed_utc, app, entry_type, legs,"
                     " multiplier, flex_table) VALUES (?, ?, 'power', ?, ?, NULL)",
                     (typed_utc, app, legs, float(multiple)))
        conn.commit()
    finally:
        conn.close()


def _drawn_again(page):
    """The Props page drawn again by its own control: its order chosen."""
    now = page.evaluate("document.getElementById('props-sort').value")
    with wait_for_the_render(page, "props"):
        page.select_option("#props-sort", "time" if now != "time" else "edge")


_DEPOSIT_FORM = """() => ({
    payout: document.querySelector('#deposit-form input.entry-input').value,
    ticked: document.querySelector('#deposit-form .entry-confirm input').checked,
    text: document.getElementById('deposit-lines').textContent,
    verdict: (document.querySelector('#deposit-lines .verdict') || {}).textContent || null })"""


def test_a_deposit_match_is_put_aside_when_the_page_fills_its_payout_again(_a_copy, _browser):
    """ONE PAGE, NO OTHER DEVICE. The offer worked out at the 3x step 1 last
    kept for Chalkboard's 2-pick power, filled in and ticked; 5x then typed,
    confirmed and checked in step 1 above it, which keeps it; the page drawn
    again. The deposit match's payout is filled again as 5x and unticked, so
    the 3x answer is about an offer that is no longer the one on screen, and
    is put aside. On the change as handed, and on d7a16c2, it was drawn as
    the answer -- "-0.25 per unit of bonus" -- beside 5x."""
    _a_payout_kept(_a_copy, "chalkboard", 2, 3, "2026-10-01T12:00:00Z")
    with _on_the_copy(_a_copy, _browser) as page:
        with wait_for_the_render(page, "props"):
            page.evaluate("location.hash = '#/props'")
        page.wait_for_selector("#deposit-form .entry-head-row select", timeout=REDRAW_LIMIT_MS)
        page.select_option("#deposit-form .entry-head-row select >> nth=0", "chalkboard")
        inputs = "#deposit-form input.entry-input"
        assert page.input_value(f"{inputs} >> nth=0") == "3"
        page.check("#deposit-form .entry-confirm input")
        page.fill(f"{inputs} >> nth=1", "1")
        page.fill(f"{inputs} >> nth=2", "5")
        with wait_for_the_render(page, "props", "deposit-lines"):
            page.click("#deposit-check")
        worked = page.evaluate(_DEPOSIT)
        assert worked["verdict"] and any(
            line.endswith("-0.25 per unit of bonus") for line in worked["lines"]), worked
        _fill_entry(page, _a_copy, "5", app="chalkboard", go=False)
        with wait_for_the_render(page, "props", "entry-lines"):
            page.click("#entry-check")
        _drawn_again(page)
        drawn = page.evaluate(_DEPOSIT_FORM)
        assert drawn["payout"] == "5" and not drawn["ticked"], (
            f"the page no longer fills the payout step 1 last kept: {drawn}")
        assert drawn["verdict"] is None and drawn["text"].startswith("Changed since"), (
            f"THE 3x ANSWER WAS DRAWN BESIDE THE PAYOUT THE PAGE FILLED IN AGAIN AS "
            f"{drawn['payout']}x: {drawn}")


_ENTRY_FORM = """() => ({
    payout: document.querySelector('#entry-payout .entry-pays-rows input').value,
    ticked: document.querySelector('#entry-payout .entry-confirm input').checked,
    text: document.getElementById('entry-lines').textContent,
    verdict: (document.querySelector('#entry-lines .verdict') || {}).textContent || null })"""


def test_an_entry_check_is_put_aside_when_the_page_fills_its_payout_again(_a_copy, _browser):
    """Checked at the 3x the page filled in for Chalkboard's 2-pick power and
    he ticked; a newer 5x kept for the same app, type and size (typed on
    another device); the page drawn again, filling the payout again as 5x,
    unticked. The 3x verdict is put aside. On the change as handed, and on
    d7a16c2, it was drawn beside 5x."""
    _a_payout_kept(_a_copy, "chalkboard", 2, 3, "2026-10-01T12:00:00Z")
    with _on_the_copy(_a_copy, _browser) as page:
        _fill_entry(page, _a_copy, None, app="chalkboard")
        assert page.input_value("#entry-payout .entry-pays-rows input") == "3"
        with wait_for_the_render(page, "props", "entry-lines"):
            page.click("#entry-check")
        assert page.evaluate(_ENTRY_FORM)["verdict"], page.evaluate(_ENTRY_FORM)
        _a_payout_kept(_a_copy, "chalkboard", 2, 5, "2026-10-02T12:00:00Z")
        _drawn_again(page)
        drawn = page.evaluate(_ENTRY_FORM)
        assert drawn["payout"] == "5" and not drawn["ticked"], (
            f"the page no longer fills the payout last kept: {drawn}")
        assert drawn["verdict"] is None and drawn["text"].startswith("Changed since"), (
            f"THE 3x VERDICT WAS DRAWN BESIDE THE PAYOUT THE PAGE FILLED IN AGAIN AS "
            f"{drawn['payout']}x: {drawn}")


_MY_DAY = """() => ({ counts: document.getElementById('my-day-counts').textContent,
    chips: [...document.querySelectorAll('#my-day .my-chip')].map(c => c.textContent) })"""


def _taken_on(page, week_value) -> int:
    sport = page.evaluate("Gridiron.state.sport")
    return page.evaluate(
        f"fetch('/api/week?season=' + JSON.parse({week_value!r}).season + '&week='"
        f" + JSON.parse({week_value!r}).week + '&sport={sport}')"
        ".then(r => r.json()).then(j => j.board.my_day.n)")


def test_a_late_props_page_does_not_draw_my_day_under_a_later_week(_a_copy, _browser):
    """My day is under the header on every page, drawn by the slate and by the
    Props page. The order an operator can make: the Props page opened for a
    week holding a taken pick, its answer held; Games opened (that week's
    slate lands), and another week, holding none, chosen on its picker (that
    slate lands); the Props page's answer released. On the change as handed,
    and on d7a16c2, its late answer drew its week's "1 taken" in My day over
    "Nothing taken on this slate yet." under the Games picker's other week --
    the Props page's own count told it only from a later Props page, and the
    slate's `weekSeq` only from a later slate."""
    with _on_the_copy(_a_copy, _browser) as page:
        now = page.evaluate("document.getElementById('week-picker').value")
        if not _taken_on(page, now):
            with wait_for_the_render(page, "games"), \
                    page.expect_response(lambda r: "/api/taken/" in r.url, timeout=20000):
                page.click("#games-rows .game[data-state='upcoming'] .meta .chk")
        assert _taken_on(page, now) > 0
        weeks = page.evaluate("[...document.querySelectorAll('#week-picker option')].map(o => o.value)")
        other = next(w for w in weeks if w != now and _taken_on(page, w) == 0)
        season, week = (now.split('"season":')[1].split(",")[0],
                        now.split('"week":')[1].rstrip("}"))
        _hold(page, f"/api/week?season={season}&week={week}&")
        page.evaluate("location.hash = '#/props'")
        held = _held(page)
        with wait_for_the_render(page, "games"):
            page.evaluate("location.hash = '#/games'")
        assert page.evaluate(_MY_DAY)["chips"], page.evaluate(_MY_DAY)
        with wait_for_the_render(page, "games"):
            _choose(page, "#week-picker", other)
        landed = page.evaluate(_MY_DAY)
        assert not landed["chips"], landed
        _release(page, held)
        _settled(page)
        late = page.evaluate(_MY_DAY)
        assert late == landed, (
            f"THE PROPS PAGE'S LATE ANSWER DREW ITS WEEK'S MY DAY, {late['counts']!r}, UNDER THE "
            f"GAMES PICKER'S OTHER WEEK, WHOSE IS {landed['counts']!r}")


_ROW = """(label) => {
    const rows = [...document.querySelectorAll('#settings-sections .set')];
    const at = rows.findIndex(r => (r.querySelector('.set-k b') || {}).textContent === label);
    if (at < 0) return null;
    return { at: at, face: rows[at].querySelector('input.inp').value,
             said: (rows[at].querySelector('.set-said') || {}).textContent || null }; }"""

_THE_APPLIANCE_HOLDS = """(label) => fetch('/api/settings').then(r => r.json())
    .then(d => d.sections.flatMap(s => s.settings).filter(s => s.label === label)[0].value)"""

#: A setting the browser world holds as a number the operator types.
_SETTING = "Quiet hours start"


def _put_back(page, field, value):
    page.fill(field, value)
    page.dispatch_event(field, "change")
    _settled(page)


def test_a_setting_saved_twice_shows_what_the_appliance_holds(_a_copy, _browser):
    """Saved as 21, the save's ANSWER held after the appliance wrote it; saved
    as 22; the first answer released. The row shows what the appliance holds.
    On d7a16c2 the second save was answered first and the first's late answer
    drew "21" and "changed from 23 to 21" over it, the appliance holding 22."""
    with _on_the_copy(_a_copy, _browser) as page:
        _open(page, "settings")
        page.evaluate(_HOLD)
        row = page.evaluate(_ROW, _SETTING)
        field = f"#settings-sections .set >> nth={row['at']} >> input.inp"
        original = row["face"]
        first, second = ("21", "22") if original not in ("21", "22") else ("20", "19")
        try:
            _hold(page, "/api/settings", side="answer", method="POST")
            page.fill(field, first)
            page.dispatch_event(field, "change")
            held = _held(page)
            page.fill(field, second)
            page.dispatch_event(field, "change")
            _settled(page)
            _release(page, held)
            _settled(page)
            shown = page.evaluate(_ROW, _SETTING)
            holds = page.evaluate(_THE_APPLIANCE_HOLDS, _SETTING)
            assert holds == second, holds
            assert shown["face"] == holds and shown["said"].endswith(f"to {second}."), (
                f"THE ROW SHOWS {shown['face']!r} -- {shown['said']!r} -- WHILE THE APPLIANCE "
                f"HOLDS {holds!r}")
        finally:
            _put_back(page, field, original)


def test_a_read_asked_before_a_save_does_not_draw_the_row_back(_a_copy, _browser):
    """Settings drawn; the page left and opened again, its read's ANSWER held
    (the appliance read before the save); a value saved on the rows still
    drawn; the read released. The row shows what the appliance holds. On
    d7a16c2 the save landed and the read then drew the row back to the value
    before it."""
    with _on_the_copy(_a_copy, _browser) as page:
        _open(page, "settings")
        row = page.evaluate(_ROW, _SETTING)
        field = f"#settings-sections .set >> nth={row['at']} >> input.inp"
        original = row["face"]
        value = "21" if original != "21" else "20"
        with wait_for_the_render(page, "games"):
            page.evaluate("location.hash = '#/games'")
        try:
            _hold(page, "/api/settings", side="answer", method="GET")
            page.evaluate("location.hash = '#/settings'")
            held = _held(page)
            page.fill(field, value)
            page.dispatch_event(field, "change")
            _settled(page)
            _release(page, held)
            _settled(page)
            shown = page.evaluate(_ROW, _SETTING)
            holds = page.evaluate(_THE_APPLIANCE_HOLDS, _SETTING)
            assert holds == value, holds
            assert shown["face"] == holds, (
                f"THE READ ASKED BEFORE THE SAVE DREW THE ROW BACK TO {shown['face']!r} WHILE THE "
                f"APPLIANCE HOLDS {holds!r}")
        finally:
            _put_back(page, field, original)
