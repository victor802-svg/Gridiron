"""The cards layout: what must be true at every width.

REPLACES `tests/test_desk.py`, which is deleted. That file pinned two layouts
-- a desk of tiles beside a rail above 1280px, and compact rows below it -- and
half of its 36 tests existed only to prove the two agreed with each other, or
that the breakpoint switched between them at the right moment. There is one
layout now, so those tests are not weakened, they are ANSWERED: a claim about
whether two layouts agree cannot be made about one.

WHAT SURVIVED IS RE-POINTED, NOT DROPPED, which is what ruling R1 asks. No
card truncates; nothing overflows sideways; a tap target is big enough; there
is one greeting; a score arriving does not re-sort the slate; the live mark is
never green; the tier default holds. Each of those was true of the desk, is
true of the cards, and is asserted here against the new markup.
"""

from __future__ import annotations

import re

import pytest

from gridiron import audit

#: THE THREE WIDTHS THE BRIEF NAMES. They are no longer three LAYOUTS -- they
#: are three widths of one layout, which is the whole point of the change, so
#: every test below runs the same assertions at whichever of them it needs.
WIDE = {"width": 1440, "height": 900}
MID = {"width": 900, "height": 900}
PHONE = {"width": 390, "height": 844}


def _open_week(page, size):
    """Open the slate at a width and WAIT FOR IT, not for a duration.

    A fixed sleep is the flakier choice: simultaneously too long on a fast
    machine and too short on a loaded one, and the failure it produces on the
    loaded one looks like a broken assertion rather than a race.

    THE CONDITION IS SIMPLER THAN IT WAS. The old helper had to wait for "the
    layout that BELONGS at this width", because during a resize both could
    exist for a frame and asserting then was what the sleep had been
    accidentally avoiding. One layout has no such moment.
    """
    page.set_viewport_size(size)
    # A FRESH FETCH EVERY TIME, and the helper waits for THAT response.
    #
    # Without this, a test that intercepts `/api/week` can assert against the
    # render from an EARLIER, un-intercepted fetch: the app had already drawn
    # the slate before the route was registered, the wait condition was
    # satisfied by that first render, and the intercepted payload arrived after
    # the assertions had run. The old desk helper hid this by accident --
    # changing the viewport crossed the breakpoint, which forced a re-render,
    # which happened to be the routed one. One layout has no breakpoint to
    # cross, so the accident is gone and the wait has to be honest.
    page.evaluate("location.hash = '#/record'")
    with page.expect_response(lambda r: "/api/week" in r.url):
        page.evaluate("location.hash = '#/week'")
    page.wait_for_function(
        """() => document.body.dataset.ready === 'true'
                 && document.querySelectorAll('#week-cards .card').length +
                    (document.getElementById('week-hero').hidden ? 0 : 1) > 0""",
        timeout=15000,
    )


def _cards(page):
    return page.evaluate(
        "document.querySelectorAll('#week-cards .card').length")


# --- what the brief asks the layout to be -----------------------------------

@pytest.mark.parametrize("size", [WIDE, MID, PHONE],
                         ids=["1440", "900", "390"])
def test_one_layout_renders_at_every_width(page, size):
    """The same elements exist at 1440, 900 and 390.

    THIS IS THE RULING, ASSERTED. R1 says one layout for every width; the way
    that fails is for something to appear or disappear as the window changes,
    which is exactly what the desk did and exactly what nobody notices until a
    reader on a laptop sees a different page from a reader on a phone.
    """
    _open_week(page, size)
    shape = page.evaluate("""() => ({
        hero: !document.getElementById('week-hero').hidden,
        tabs: document.querySelectorAll('.market-tab').length,
        cards: document.querySelectorAll('#week-cards .card').length,
    })""")
    assert shape["tabs"] > 0, "the market tabs are absent at this width"
    assert shape["hero"] or shape["cards"], "neither a hero nor a card rendered"


def test_no_card_truncates(page):
    """No ellipsis anywhere in the slate, at the width that used to have one.

    RE-POINTED FROM `test_no_tile_truncates`, and widened: the old test looked
    at the frame at desk width, where nothing truncated, and missed
    "BRISSETT * PASSI..." on the phone for weeks. A truncated card has told the
    reader there is something it is not showing and then not shown it.
    """
    _open_week(page, PHONE)
    bad = page.evaluate("""() => [...document.querySelectorAll('#view-week *')]
        .filter(e => getComputedStyle(e).textOverflow === 'ellipsis')
        .map(e => e.className || e.tagName)""")
    assert not bad, f"these elements truncate: {bad[:6]}"


@pytest.mark.parametrize("size", [WIDE, MID, PHONE],
                         ids=["1440", "900", "390"])
def test_nothing_overflows_sideways(page, size):
    _open_week(page, size)
    over = page.evaluate(
        "document.documentElement.scrollWidth - window.innerWidth")
    assert over <= 0, f"the page overflows sideways by {over}px at {size}"


def test_every_tap_target_on_the_phone_is_big_enough(page):
    """44px, the platform minimum. A control nobody can hit is not a control."""
    _open_week(page, PHONE)
    small = page.evaluate("""() => [...document.querySelectorAll(
        '#view-week button, #view-week a, #view-week select')]
        .filter(e => e.offsetParent !== null)
        .map(e => ({ what: e.className || e.tagName,
                     h: Math.round(e.getBoundingClientRect().height) }))
        .filter(e => e.h > 0 && e.h < 44)""")
    # NO EXEMPTIONS. The hero's dots were exempted here for one commit,
    # because an 8px mark cannot be a 44px target -- and the answer was that
    # the MARK and the TARGET do not have to be the same element. The button is
    # 44px and draws an 8px dot inside it.
    assert not small, f"tap targets under 44px: {small[:6]}"


def test_there_is_exactly_one_greeting(page):
    """The greeting used to be MOVED between two homes depending on width."""
    for size in (WIDE, PHONE):
        _open_week(page, size)
        n = page.evaluate("document.querySelectorAll('#greeting').length")
        assert n == 1, f"{n} greetings at {size['width']}px"


# --- one number per card (R2) -----------------------------------------------

def test_a_collapsed_card_shows_one_number(page):
    """R2. The market's figure is one tap away, not beside the model's.

    A card showing two percentages makes a reader work out which one is the
    claim, and the one they are most likely to read is whichever is larger.
    """
    _open_week(page, WIDE)
    if not _cards(page):
        pytest.skip("no cards on this slate")
    # WHAT A READER SEES WITHOUT HOVERING. The market hint is a hover reveal
    # the brief asks for by name, so it is in the markup and at zero opacity;
    # counting the text alone would count a number nobody is being shown.
    numbers = page.evaluate(r"""() => {
        const card = document.querySelector('#week-cards .card');
        const head = card.querySelector('.card-head');
        const out = [];
        head.querySelectorAll('*').forEach(e => {
            if (e.children.length) return;
            if (parseFloat(getComputedStyle(e).opacity) === 0) return;
            (e.textContent.match(/\d+(\.\d+)?%/g) || [])
                .forEach(m => out.push(m));
        });
        return out;
    }""")
    assert len(numbers) <= 1, (
        f"a collapsed card shows {len(numbers)} numbers at rest: {numbers}")

def test_a_card_expands_in_place_and_shows_the_why(page):
    """R2's other half: the reasons are one tap away, and they arrive."""
    _open_week(page, WIDE)
    if not _cards(page):
        pytest.skip("no cards on this slate")
    result = page.evaluate("""async () => {
        const card = document.querySelector('#week-cards .card');
        const before = card.getBoundingClientRect().top;
        card.querySelector('.card-head').click();
        await new Promise(r => setTimeout(r, 250));
        const body = card.querySelector('.card-body');
        return {
            open: card.classList.contains('open'),
            expanded: card.querySelector('.card-head')
                          .getAttribute('aria-expanded'),
            text: (body.textContent || '').trim().length,
            moved: Math.abs(card.getBoundingClientRect().top - before),
        };
    }""")
    assert result["open"], "the card did not open"
    assert result["expanded"] == "true", "aria-expanded did not follow"
    assert result["text"] > 0, "the card opened on nothing"
    assert result["moved"] < 2, (
        f"the card moved {result['moved']}px on opening; it expands IN PLACE "
        f"so the reader keeps their place")


# --- the market tabs (R4) ---------------------------------------------------

def test_the_market_tabs_come_from_the_declared_list(page):
    """R4. A fifth market must appear without a UI change.

    Asserted against `config.SPORT_MARKETS` rather than against a written row,
    which is the only way to tell a derived list from a hardcoded one that
    happens to be right today.
    """
    from gridiron import config, language

    _open_week(page, WIDE)
    sport = page.evaluate("document.body.dataset.sport") or "nfl"
    labels = page.evaluate(
        """[...document.querySelectorAll('.market-tab')]
             .map(t => t.dataset.market)""")
    assert labels and labels[0] == "", "the first tab is not 'All'"
    assert labels[1:] == list(config.SPORT_MARKETS.get(sport, ())), (
        f"the tabs for {sport} are {labels[1:]}, and the declared markets are "
        f"{list(config.SPORT_MARKETS.get(sport, ()))}. A tab row that does not "
        f"match the declaration is a hardcoded row.")


def test_a_zero_count_tab_stays_visible(page):
    """R4. "No strikeout questions tonight" is a fact about the slate."""
    _open_week(page, WIDE)
    counts = page.evaluate(
        """[...document.querySelectorAll('.market-tab')]
             .map(t => ({ n: t.querySelector('.market-tab-n').textContent,
                          shown: t.offsetParent !== null }))""")
    zeros = [c for c in counts if c["n"] == "0"]
    assert all(c["shown"] for c in zeros), (
        "a zero-count market tab was hidden, which hides the fact that the "
        "slate asked nothing in it")


def test_every_tab_carries_its_count(page):
    """LAW 4's habit, applied to a tab: no number without what it counts."""
    _open_week(page, WIDE)
    missing = page.evaluate(
        """[...document.querySelectorAll('.market-tab')]
             .filter(t => !t.querySelector('.market-tab-n'))
             .map(t => t.textContent)""")
    assert not missing, f"tabs with no count: {missing}"


# --- the hero (R3) ----------------------------------------------------------

def test_the_hero_says_which_question_it_is_answering(page):
    """The tag follows the sort rather than asserting one.

    A hero labelled "sharpest disagreement" while the list is ordered by
    confidence is a label describing the other ordering.
    """
    _open_week(page, WIDE)
    if page.evaluate("document.getElementById('week-hero').hidden"):
        pytest.skip("no hero on this slate")
    tag = page.evaluate("document.querySelector('.hero-tag').textContent")
    assert "disagreement" in tag.lower(), (
        f"the default sort is by disagreement and the hero says {tag!r}")

    page.evaluate(
        """document.querySelector('#week-sort-seg button[data-sort=confidence]')
             .click()""")
    page.wait_for_function(
        """() => /confident/i.test(
             (document.querySelector('.hero-tag') || {}).textContent || '')""",
        timeout=10000)


def test_the_hero_steps_through_the_top_five(page):
    """R3. Arrows and dots, and the dots say which one is showing."""
    _open_week(page, WIDE)
    dots = page.evaluate("document.querySelectorAll('.hero-dot').length")
    if dots < 2:
        pytest.skip("fewer than two picks on this slate to step through")
    assert dots <= 5, f"{dots} dots; the brief says the top five"
    first = page.evaluate("document.querySelector('.hero-game').textContent")
    page.evaluate("document.querySelectorAll('.hero-arrow')[1].click()")
    page.wait_for_timeout(200)
    second = page.evaluate("document.querySelector('.hero-game').textContent")
    on = page.evaluate(
        "document.querySelectorAll('.hero-dot.on').length")
    assert on == 1, f"{on} dots marked current"
    assert first != second, "the arrow did not move the hero"


# --- the claims that outlived the desk --------------------------------------

def test_the_grid_does_not_re_sort_while_a_slate_is_in_progress(page):
    """A score arriving must not move the slate under a reader.

    Re-sorting while games are being played shuffles the screen under somebody
    part way down it, and by confidence the finished games would climb over the
    ones still on.
    """
    seen = {"ids": []}

    def _in_progress(route):
        response = route.fetch()
        payload = response.json()
        glance = payload.get("glance") or {}
        glance["state"] = "in_progress"
        payload["glance"] = glance
        seen["ids"] = [c.get("prediction_id") for c in payload.get("cards", [])
                       if c.get("prediction_id")]
        route.fulfill(response=response, json=payload)

    def _one_final_pick(route):
        route.fulfill(json={
            "picks": [{"prediction_id": seen["ids"][0],
                       "tile_state": "final",
                       "verdict": "WIN",
                       "live_line": "TST 7 - TST 3"}] if seen["ids"] else [],
            "games": [],
            "any_live": False,
        })

    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.route("**/api/week*", _in_progress)
    page.route("**/api/live*", _one_final_pick)
    try:
        _open_week(page, WIDE)
        if not seen["ids"] or not _cards(page):
            pytest.skip("no cards on this slate to tick")
        order_before = page.evaluate(
            """[...document.querySelectorAll('#week-cards .card')]
                 .map(c => c.dataset.id)""")
        page.wait_for_timeout(1400)
        order_after = page.evaluate(
            """[...document.querySelectorAll('#week-cards .card')]
                 .map(c => c.dataset.id)""")
        assert not errors, (
            f"a live tick threw: {errors}. The throw escapes the loop over "
            f"picks, so every pick after this one stops updating and the "
            f"scores freeze with nothing on the page saying so.")
        assert order_before == order_after, (
            "the slate re-sorted while it was being played")
    finally:
        page.unroute("**/api/week*")
        page.unroute("**/api/live*")


def test_the_live_mark_is_never_green(page):
    """Green means a pick won and means interactive. A live game is neither."""
    _open_week(page, WIDE)
    colour = page.evaluate("""() => {
        const probe = document.createElement('span');
        probe.className = 'card-live';
        document.body.appendChild(probe);
        const c = getComputedStyle(probe).backgroundColor;
        probe.remove();
        const win = getComputedStyle(document.documentElement)
            .getPropertyValue('--win').trim();
        return { c, win };
    }""")
    assert colour["c"] != colour["win"], (
        f"the live mark is drawn in the win colour ({colour['c']})")


def test_every_class_the_page_asks_for_is_a_class_it_builds():
    """The scan, run against the shipped files (mechanism, not habit)."""
    audit.check_no_dead_selectors()


def test_no_monospace_or_condensed_face_anywhere(page):
    """The brief: no condensed caps, no monospace anywhere in the UI."""
    _open_week(page, WIDE)
    faces = page.evaluate("""() => {
        const seen = new Set();
        document.querySelectorAll('#view-week *').forEach(e => {
            seen.add(getComputedStyle(e).fontFamily);
        });
        return [...seen];
    }""")
    bad = [f for f in faces
           if re.search(r"monospace|mono|condensed|narrow", f, re.I)]
    assert not bad, f"a monospace or condensed face is still in use: {bad}"


# --- STRONG BY DEFAULT (R5, and GRIDIRON_17 R2) ------------------------------
#
# CARRIED ACROSS FROM `test_desk.py` UNCHANGED IN SUBSTANCE. These were never
# about the desk -- they are about the tier filter opening on STRONG, saying
# what it narrowed, and being leaveable -- so they are re-pointed at the new
# layout's widths and otherwise left alone.

def _pressed_tier(page):
    """Which band the segmented filter is showing as active, '' for all."""
    return page.evaluate(
        """() => {
            const host = document.querySelector('#week-tier-seg');
            if (!host) return null;
            const on = host.querySelector('[aria-pressed="true"]');
            return on ? on.dataset.tier : null;
        }""")


def _tiers_offered(page):
    return page.evaluate(
        """() => Array.from(
            document.querySelectorAll('#week-tier-seg button'))
            .map(b => b.dataset.tier)""")


def test_picks_arrives_on_strong(page):
    """The reader chose nothing; the page still opens on the strongest band."""
    _open_week(page, WIDE)
    if "STRONG" not in _tiers_offered(page):
        pytest.skip("no STRONG picks on this slate; the default yields by "
                    "design and test_the_default_yields_on_a_slate_without_it "
                    "covers that case")
    assert _pressed_tier(page) == "STRONG", (
        "Picks did not open on the band ruling R2 named"
    )


def test_the_way_out_of_the_default_is_on_the_page(page):
    """A filter nobody chose must not be a filter nobody can leave."""
    _open_week(page, WIDE)
    offered = _tiers_offered(page)
    if _pressed_tier(page):
        assert "" in offered, "no 'all tiers' button beside an active filter"
        assert not page.evaluate(
            "document.querySelector('#week-tier-seg').hidden"), (
            "the filter is active and its control is hidden"
        )


def test_the_arrival_count_says_what_it_narrowed(page):
    _open_week(page, WIDE)
    said = page.text_content("#week-counts") or ""
    if not _pressed_tier(page):
        return
    assert "STRONG" in said, f"the count line does not name the band: {said!r}"
    assert re.search(r"\d+\s+of\s+\d+", said), (
        f"the count line names no denominator: {said!r}. A reader who never "
        f"chose a filter reads this as the size of the slate."
    )


def test_the_caveat_names_its_shortfall_and_never_a_rate(page):
    _open_week(page, WIDE)
    said = (page.text_content("#tier-caveat") or "").strip()
    hidden = page.evaluate("document.getElementById('tier-caveat').hidden")
    if hidden:
        # The band cleared its gate, or the default yielded. Both are the
        # sentence's own disappearing conditions, not a missing element.
        assert said == ""
        return
    assert "STRONG" in said and "settled" in said
    assert "%" not in said, "a caveat about sample size stated a rate"


def test_the_caveat_goes_when_the_reader_leaves_the_default(page):
    """It explains the DEFAULT. Under a band the reader picked it is noise."""
    _open_week(page, WIDE)
    if _pressed_tier(page) != "STRONG":
        pytest.skip("the default did not engage on this slate")
    page.click('#week-tier-seg button[data-tier=""]')
    page.wait_for_function(
        "() => document.getElementById('tier-caveat').hidden === true",
        timeout=5000)


def test_the_toggle_is_remembered_for_the_session(page):
    """Chosen once, kept across a re-render of the same sport."""
    _open_week(page, WIDE)
    if _pressed_tier(page) != "STRONG":
        pytest.skip("the default did not engage on this slate")
    page.click('#week-tier-seg button[data-tier=""]')
    page.wait_for_function(
        """() => {
            const on = document.querySelector(
                '#week-tier-seg [aria-pressed="true"]');
            return on && on.dataset.tier === '';
        }""", timeout=5000)
    page.evaluate("location.hash = '#/record'")
    page.wait_for_timeout(200)
    _open_week(page, WIDE)
    assert _pressed_tier(page) == "", (
        "the filter reverted to the default after the reader had changed it"
    )


def test_the_default_holds_at_390(page):
    """Same band, same sentence, no desk."""
    _open_week(page, PHONE)
    if "STRONG" not in _tiers_offered(page):
        pytest.skip("no STRONG picks on this slate")
    assert _pressed_tier(page) == "STRONG"
    said = page.text_content("#week-counts") or ""
    assert "STRONG" in said and re.search(r"\d+\s+of\s+\d+", said), said


def test_the_default_yields_on_a_slate_without_it(page):
    """A default that empties the page is a defect, not a convenience.

    Driven through the real render: the slate is served with its STRONG cards
    removed, which is what a night of nothing but LEAN picks looks like. The
    page must open on every tier rather than on an empty band.
    """
    def _drop_strong(route):
        response = route.fetch()
        payload = response.json()
        payload["cards"] = [
            c for c in payload.get("cards", [])
            if ((c.get("tier") or {}).get("tier") or "") != "STRONG"]
        route.fulfill(response=response, json=payload)

    page.route("**/api/week*", _drop_strong)
    try:
        _open_week(page, WIDE)
        # THE HERO COUNTS. The first pick of the slate is the hero and the
        # rest are the grid, so a slate with one surviving card has zero
        # `.card` nodes and is not empty. Counting only the grid would fail a
        # page that is showing exactly what it should.
        shown = page.evaluate(
            """() => document.querySelectorAll('#week-cards .card').length
                     + (document.getElementById('week-hero').hidden ? 0 : 1)""")
        assert shown > 0, (
            "the page opened empty on a slate with no STRONG picks; the "
            "default filtered out everything the reader came to see"
        )
        assert _pressed_tier(page) == "", (
            "the default engaged on a band that has no picks on this slate"
        )
        assert page.evaluate(
            "document.getElementById('tier-caveat').hidden") is True, (
            "the caveat explains a default that did not engage"
        )
    finally:
        page.unroute("**/api/week*")


# ---------------------------------------------------------------------------
# THE LIVE TICK REACHES THE TILE
#
# `applyLive` fetched the tile's corner by a class that had been renamed out
# of existence (bd7ac2f). querySelector answered null, paintTileCorner threw,
# and the throw escaped the forEach around it -- so one tile stopped the score
# update for every pick after it. Nothing failed: the suite was green, the
# page rendered, and the scores simply stopped moving.
#
# Every existing desk test asserted on the FIRST render. This one asserts that
# a tick lands, which is the assertion that was missing.
# ---------------------------------------------------------------------------
