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
                    document.querySelectorAll('#today .face').length > 0""",
        timeout=15000,
    )
    # AND FOR THE ARRIVAL TO END (R4, 2026-09-05). The grid and the hero come
    # in from one per cent below over 200ms; a position measured a frame into
    # that reads the slide as movement. "Waiting for the slate" now includes
    # waiting for it to settle.
    page.wait_for_function(
        """() => ['week-cards', 'today'].every(id => {
            const el = document.getElementById(id);
            if (!el || el.hidden) return true;
            const cs = getComputedStyle(el);
            return cs.opacity === '1' && cs.transform === 'none';
        })""", timeout=5000)


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
        faces: document.querySelectorAll('#today .face').length,
        tabs: document.querySelectorAll('.market-tab').length,
        cards: document.querySelectorAll('#week-cards .card').length,
    })""")
    assert shape["tabs"] > 0, "the market tabs are absent at this width"
    assert shape["faces"] or shape["cards"], "no card rendered at all"


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


# --- what the hero's test protected, on the card that replaced it ----------
#
# `test_the_hero_says_which_question_it_is_answering` checked that the hero's
# tag matched the sort it was drawn under -- a hero labelled "sharpest
# disagreement" over a list ordered by confidence is a page contradicting
# itself. THE HERO WAS REMOVED ON 2026-09-08 and so was the sort, so there is
# no tag and no ordering to contradict; every card carries its own question in
# its own words, which `test_three_states.py` and the plain-words scan check.

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


def _shown_ids(page):
    """Every card id in the grid, with "show all" opened AND WAITED FOR.

    `show all` does not reveal hidden markup -- its handler sets a flag and
    calls `renderWeek()`, which RE-FETCHES and rebuilds the grid from scratch.
    Reading the DOM straight after the click catches the page mid-render, with
    `host.innerHTML = ''` already run and nothing appended yet.

    THAT RACE MADE FOUR TESTS SKIP RATHER THAN FAIL, which is worse: each one
    said "no cards on this slate" and passed as a skip while the slate had
    six. A helper that reports an empty page as an empty slate turns every
    test built on it into a test of nothing.
    """
    if page.evaluate("""() => {
            const b = document.getElementById('week-showall');
            return !!(b && !b.hidden && b.offsetParent !== null);
        }"""):
        with page.expect_response(lambda r: "/api/week" in r.url):
            page.evaluate(
                "() => document.getElementById('week-showall').click()")
        # The post-condition, not a duration: everything is shown exactly when
        # the control that offers to show it has nothing left to offer.
        page.wait_for_function(
            """() => {
                 const b = document.getElementById('week-showall');
                 return (!b || b.hidden) &&
                        document.querySelectorAll('#week-cards .card').length > 0;
               }""",
            timeout=15000)
    # THE HERO'S CARD COUNTS. It is not in the grid -- the grid drops the card
    # the hero leads with -- so a helper that returned only `#week-cards` would
    # report the largest pick on the page as absent from it.
    return set(page.evaluate(
        """(() => {
             const ids = [...document.querySelectorAll('#week-cards .card')]
                           .map(c => Number(c.dataset.id));
             const hero = document.getElementById('week-hero');
             if (hero && !hero.hidden && hero.dataset.id) {
               ids.push(Number(hero.dataset.id));
             }
             return ids;
           })()"""))


def _flag_ids(page, ids):
    """Route `/api/week` so exactly these prediction ids carry a method note."""
    wanted = set(ids)

    def handler(route):
        response = route.fetch()
        payload = response.json()
        for card in payload.get("cards") or []:
            if card.get("prediction_id") in wanted:
                card["method_note"] = _NOTE
        route.fulfill(response=response, json=payload)

    page.route("**/api/week*", handler)


#: THE FLAGGED NOTE, in the words the server sends. Declared here from
#: 2026-09-08: it lived with the three hero tests that were removed with the
#: hero, and one of them was the only thing declaring it.
_NOTE = "chosen from the model's own distribution, not from a market line"


def test_the_flagged_note_is_readable_without_a_tap(page):
    """A caveat behind a tap is a caveat most readers never reach.

    The reader taking the percentage at face value is precisely the one it is
    written for, so the note is asserted VISIBLE AT REST -- unlike the market
    hint beside it, which is deliberately a hover reveal.
    """
    _open_week(page, WIDE)
    ids = _shown_ids(page)
    if not ids:
        pytest.skip("no cards on this slate to flag")

    _flag_ids(page, ids)
    _open_week(page, WIDE)
    _shown_ids(page)
    shown = page.evaluate(
        """[...document.querySelectorAll('#week-cards .card')].map(c => {
             const n = c.querySelector('.card-note');
             return n ? { text: n.textContent.trim(),
                          seen: n.offsetParent !== null &&
                                getComputedStyle(n).opacity !== '0' }
                      : null;
           })""")
    drawn = [s for s in shown if s]
    assert drawn, "every card was flagged and not one drew a note"
    assert all(s["seen"] for s in drawn), (
        "a method note rendered and is not visible at rest, so the caveat is "
        "absent on every glance and on every touch device")
    assert all(s["text"] == _NOTE for s in drawn), (
        "the note on a card is not the sentence the server wrote")


# `test_the_card_the_hero_refuses_is_still_on_the_page` was removed with the
# hero on 2026-09-08. It checked that the grid dropped the card the hero LED
# WITH by identity rather than by position, because `open.slice(1)` deletes a
# card from the page entirely once the hero can refuse the top one. There is
# no hero, no lead and no slice: the grid shows the slate.

def test_manrope_actually_loads_and_is_the_face_the_page_draws_in(page):
    """A file in the repository is not a font on the page.

    Everything else about ruling 4 is checkable without a browser -- the bytes
    hash, the licence is there, the stylesheet names files that exist. NONE OF
    THAT PROVES THE PAGE USES IT. An `@font-face` whose `src` 401s, or whose
    unicode-range excludes the text, fails SILENTLY: the stack falls through to
    the system face and the page looks fine, slightly wrong, forever.

    IT ALREADY FAILED ONCE THIS WAY. `auth.path_is_open` allowed `.css`, `.ico`
    and `.svg` under `/static/` and not `.woff2`, so the sign-in screen drew in
    a fallback face and said nothing but a console line.
    """
    _open_week(page, WIDE)
    page.evaluate("() => document.fonts.ready")
    loaded = page.evaluate(
        """() => [...document.fonts]
             .filter(f => f.family === 'Manrope' && f.status === 'loaded')
             .map(f => f.unicodeRange ? 'range' : 'all')""")
    assert loaded, (
        "no Manrope face reached `loaded`, so the page is drawing in the "
        "fallback stack and the vendored file is decoration")

    # AND IT IS THE FACE ACTUALLY USED, not merely one that downloaded.
    used = page.evaluate(
        """() => {
             const el = document.querySelector('.hero-game, .card-game, body');
             return getComputedStyle(el).fontFamily;
           }""")
    assert "Manrope" in used, f"the page draws in {used!r}"


def test_no_font_request_is_refused(page):
    """The 401 that started §5.4, asserted rather than remembered."""
    refused = []
    page.on("response", lambda r: refused.append((r.status, r.url))
            if ".woff2" in r.url and r.status >= 400 else None)
    _open_week(page, WIDE)
    page.evaluate("() => document.fonts.ready")
    assert not refused, f"font requests were refused: {refused}"


# --- the tier chip says what it is (2026-09-04) -----------------------------

def test_an_unproven_chip_says_so_where_a_reader_can_see_it(page):
    """MEASURED, and this is the fix. Across four live slates 362 of 379 tier
    chips named a band with no settled record behind it, and the sentence
    saying so reached a GRID card only through `title` -- a hover tooltip, so
    nothing at all on a phone. The hero was honest; the thirty cards behind it
    were not.

    ASSERTED ON THE PHONE, deliberately: `title` is exactly the mechanism that
    works where this test would not look and fails where a reader actually is.
    """
    _open_week(page, PHONE)
    if not _cards(page):
        pytest.skip("no cards on this slate")

    chips = page.evaluate(
        """[...document.querySelectorAll('#week-cards .card .tier')]
             .filter(t => t.className.indexOf('tier-none') === -1)
             .map(t => ({ text: t.textContent.trim(),
                          unproven: t.classList.contains('tier-unproven'),
                          seen: t.offsetParent !== null }))""")
    if not chips:
        pytest.skip("no tier chips on this slate")

    assert all(c["seen"] for c in chips), "a tier chip rendered and is hidden"
    for chip in chips:
        if chip["unproven"]:
            assert "unproven" in chip["text"], (
                f"a chip is marked unproven and does not say so: {chip['text']!r}")
        else:
            assert "unproven" not in chip["text"], chip["text"]


def test_the_chip_is_never_composed_in_the_browser(page):
    """The word comes from the server, like every other word on the page."""
    from gridiron import language

    _open_week(page, WIDE)
    texts = page.evaluate(
        """[...document.querySelectorAll('.tier')]
             .map(t => t.textContent.trim()).filter(Boolean)""")
    if not texts:
        pytest.skip("no tier chips on this slate")

    allowed = set()
    for band in ("LEAN", "SOLID", "STRONG"):
        allowed.add(language.tier_chip_label(band, True))
        allowed.add(language.tier_chip_label(band, False))
    unknown = sorted(set(texts) - allowed)
    assert not unknown, (
        f"these chip labels were not composed by language.tier_chip_label: "
        f"{unknown}")


# --- what the hero's flagged-market tests protected -------------------------
#
# Three tests were removed on 2026-09-08 with the feature they drove:
# `test_the_default_yields_on_a_slate_without_it` exercised the tier default,
# and `test_a_flagged_market_never_leads_the_page` and
# `test_every_card_flagged_means_no_hero_at_all` exercised the hero's refusal
# to promote a flagged market. There is no hero, no sort and no tier default.
#
# THE HALF THAT MATTERED IS STILL CHECKED. A flagged method says so on the
# card that carries it (`audit.check_flagged_methods`, on the gate), and
# nothing unproven leads because the bar decides a card's group and a card
# below its market's gate says "no measured edge" on its own face.

